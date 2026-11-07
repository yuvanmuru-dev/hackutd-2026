"""Read-only external checks for customer-forwarded text and security policy.

Only provider metadata is queried. This module never fetches a URL found in a
message, changes a protection, or sends a customer message.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests


AGENT_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = AGENT_DIR / "cache"
POLICY_DIR = Path(__file__).resolve().parent / "data" / "policy"
SYNTHETIC_REGISTRY = Path(__file__).resolve().parent / "data" / "synthetic_registry.json"
SYNTHETIC_SOURCE = "Synthetic demo registry (simulated RDAP)"
IANA_RDAP_BOOTSTRAP = "https://data.iana.org/rdap/dns.json"
URLHAUS_URL = "https://urlhaus-api.abuse.ch/v1/url/"
URLHAUS_HOST = "https://urlhaus-api.abuse.ch/v1/host/"
EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
EMBED_MODEL = "nvidia/nemotron-3.5-embed-1b"
TIMEOUT_S = 4
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
BARE_DOMAIN_RE = re.compile(
    r"(?<![a-z0-9_@.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}\b",
    re.IGNORECASE,
)
URGENT_RE = re.compile(r"\b(?:locked|suspend(?:ed)?|verify now|urgent|immediately|act now)\b", re.IGNORECASE)
RESERVED_TLDS = {"example", "invalid", "local", "localhost", "test"}
MULTIPART_SUFFIXES = {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "co.nz", "com.br"}


def _cache_path(kind: str, value: str) -> Path:
    digest = hashlib.sha256((kind + "\0" + value).encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{kind}-{digest}.json"


def _cache_get(kind: str, value: str, ttl_s: int) -> dict | None:
    try:
        cached = json.loads(_cache_path(kind, value).read_text())
        lifetime = min(ttl_s, cached.get("ttl_s", ttl_s))
        if time.time() - cached["stored_at"] <= lifetime and isinstance(cached["result"], dict):
            return cached["result"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _cache_set(kind: str, value: str, result: dict, ttl_s: int | None = None) -> None:
    """Write atomically; cache failures must never change a verdict."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CACHE_DIR, delete=False) as handle:
            entry = {"stored_at": time.time(), "result": result}
            if ttl_s is not None:
                entry["ttl_s"] = ttl_s
            json.dump(entry, handle, separators=(",", ":"))
            temp = Path(handle.name)
        temp.replace(_cache_path(kind, value))
    except OSError:
        if "temp" in locals():
            temp.unlink(missing_ok=True)


def _clean_host(host: str | None) -> str | None:
    if not host:
        return None
    try:
        host = host.rstrip(".").lower().encode("idna").decode("ascii")
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass  # A domain name, not an IP address.
    except UnicodeError:
        return None
    labels = host.split(".")
    if len(labels) < 2 or not labels[-1].isalpha() or len(labels[-1]) < 2:
        return None
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in labels):
        return None
    return host


def _extract(text: str) -> list[tuple[str, str | None]]:
    found: list[tuple[str, str | None]] = []
    used = set()
    remainder = list(text)
    for match in URL_RE.finditer(text):
        token = match.group().rstrip(".,;:!?)]}")
        try:
            parsed = urlsplit(token)
            host = _clean_host(parsed.hostname)
        except ValueError:
            host = None
        if host:
            pair = (host, token)
            if pair not in used:
                found.append(pair)
                used.add(pair)
        remainder[match.start():match.end()] = " " * (match.end() - match.start())
    for match in BARE_DOMAIN_RE.finditer("".join(remainder)):
        host = _clean_host(match.group())
        if host and not any(h == host for h, _ in found):
            found.append((host, None))
    return found[:5]


def _registered_domain(host: str) -> str:
    labels = host.split(".")
    tail = ".".join(labels[-2:])
    if tail in MULTIPART_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return tail


def _lookalike(host: str) -> bool:
    if host == "t-mobile.com" or host.endswith(".t-mobile.com"):
        return False
    normalized = host.replace("-", "").replace("0", "o").replace("1", "l")
    return "tmobile" in normalized


def _synthetic_record(host: str) -> dict | None:
    """Listed demo names always bypass live providers, including subdomains."""
    entries = json.loads(SYNTHETIC_REGISTRY.read_text(encoding="utf-8"))["entries"]
    matches = [entry for entry in entries
               if host == entry["domain"] or host.endswith("." + entry["domain"])]
    if not matches:
        return None
    entry = max(matches, key=lambda item: len(item["domain"]))
    source = {"name": SYNTHETIC_SOURCE,
              "record": f"packs/guard/data/synthetic_registry.json#{entry['domain']}"}
    return {"domain": host, "synthetic": True, "source": source,
            "rdap": {"status": "synthetic", "age_days": entry["registered_days_ago"],
                     "registrar": entry["registrar"], "lookalike_of": entry["lookalike_of"],
                     "source": source},
            "urlhaus": {"status": "not_queried_synthetic", "known_malicious": None,
                        "note": "Demo registry names are never sent to live providers."}}


def _registry_rdap_url(domain: str) -> tuple[str | None, str]:
    """Select the longest matching registry URL from IANA's RDAP bootstrap."""
    cached = _cache_get("rdap-bootstrap", "dns-v1", 7 * 86400)
    if cached is None:
        try:
            response = requests.get(IANA_RDAP_BOOTSTRAP, timeout=TIMEOUT_S)
            if response.status_code != 200:
                _cache_set("rdap-bootstrap", "dns-v1", {"status": "unverifiable_bootstrap"}, 60)
                return None, "unverifiable_bootstrap"
            services = response.json().get("services")
            if not isinstance(services, list):
                _cache_set("rdap-bootstrap", "dns-v1", {"status": "unverifiable_bootstrap"}, 60)
                return None, "unverifiable_bootstrap"
            cached = {"services": services}
            _cache_set("rdap-bootstrap", "dns-v1", cached)
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            _cache_set("rdap-bootstrap", "dns-v1", {"status": "unverifiable_bootstrap"}, 60)
            return None, "unverifiable_bootstrap"
    if not isinstance(cached.get("services"), list):
        return None, "unverifiable_bootstrap"
    best_url = None
    best_labels = 0
    for service in cached.get("services", []):
        if not isinstance(service, list) or len(service) != 2:
            continue
        entries, bases = service
        if not isinstance(entries, list) or not isinstance(bases, list):
            continue
        for entry in entries:
            if not isinstance(entry, str) or not entry:
                continue
            entry = entry.lower()
            if domain != entry and not domain.endswith("." + entry):
                continue
            count = len(entry.split("."))
            if count <= best_labels:
                continue
            for base in bases:
                if not isinstance(base, str):
                    continue
                try:
                    parsed = urlsplit(base)
                except ValueError:
                    continue
                if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
                    best_url = base.rstrip("/") + "/domain/" + domain
                    best_labels = count
                    break
    return best_url, "found" if best_url else "unverifiable_no_registry"


def _rdap(domain: str) -> dict:
    if domain.split(".")[-1] in RESERVED_TLDS:
        return {"status": "unverifiable_reserved", "age_days": None, "source_url": None}
    cached = _cache_get("rdap-registry", domain, 24 * 3600)
    if cached is not None:
        return cached
    url, lookup_status = _registry_rdap_url(domain)
    if url is None:
        return {"status": lookup_status, "age_days": None, "source_url": IANA_RDAP_BOOTSTRAP}
    result = {"status": "unverifiable", "age_days": None, "source_url": url}
    try:
        response = requests.get(url, headers={"Accept": "application/rdap+json"}, timeout=TIMEOUT_S)
        if response.status_code != 200:
            return result
        payload = response.json()
        registration = next(
            (event.get("eventDate") for event in payload.get("events", [])
             if event.get("eventAction") == "registration"),
            None,
        )
        if not registration:
            return result
        created = datetime.fromisoformat(registration.replace("Z", "+00:00"))
        if created.tzinfo is None:
            return result
        age = int((datetime.now(timezone.utc) - created).total_seconds() // 86400)
        if age < 0:
            return result
        result = {"status": "checked", "age_days": age, "registered_at": registration, "source_url": url}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass
    finally:
        _cache_set("rdap-registry", domain, result, None if result["status"] == "checked" else 60)
    return result


def _urlhaus(host: str, url: str | None) -> dict:
    api_key = os.getenv("URLHAUS_AUTH_KEY")
    if not api_key:
        return {"status": "unverifiable", "known_malicious": None,
                "note": "URLHAUS_AUTH_KEY is missing", "source_url": "https://urlhaus-api.abuse.ch/"}
    target = url or host
    kind = "urlhaus-url" if url else "urlhaus-host"
    cached = _cache_get(kind, target, 3600)
    if cached is not None:
        return cached
    endpoint = URLHAUS_URL if url else URLHAUS_HOST
    result = {"status": "unverifiable", "known_malicious": None,
              "note": "URLhaus lookup failed", "source_url": "https://urlhaus-api.abuse.ch/"}
    try:
        response = requests.post(
            endpoint, data={"url" if url else "host": target},
            headers={"Auth-Key": api_key, "Accept": "application/json"}, timeout=TIMEOUT_S,
        )
        if response.status_code != 200:
            result["note"] = f"URLhaus HTTP {response.status_code}"
            return result
        payload = response.json()
        status = payload.get("query_status")
        if status == "ok":
            result = {
                "status": "reported_malware", "known_malicious": True,
                "source_url": payload.get("urlhaus_reference", "https://urlhaus.abuse.ch/"),
                "url_status": payload.get("url_status"),
            }
        elif status == "no_results":
            # URLhaus is a malware URL database; absence is not proof of safety.
            result = {"status": "no_report", "known_malicious": None, "source_url": "https://urlhaus.abuse.ch/"}
        else:
            return result
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass
    finally:
        _cache_set(kind, target, result, 60 if result["status"] == "unverifiable" else None)
    return result


def check_message(store, text: str = "", **_args) -> dict:
    """Inspect only text voluntarily forwarded to Titan."""
    text = (text or "")[:4096]
    items = _extract(text)
    hosts = list(dict.fromkeys(host for host, _ in items))
    lookalikes = [host for host in hosts if _lookalike(host)]
    checks = []
    for host, url in items:
        synthetic = _synthetic_record(host)
        if synthetic is not None:
            checks.append(synthetic)
            continue
        domain = _registered_domain(host)
        checks.append({
            "domain": host,
            "rdap": _rdap(domain),
            "urlhaus": (
                {"status": "unverifiable_reserved", "known_malicious": None, "source_url": "https://urlhaus.abuse.ch/"}
                if domain.split(".")[-1] in RESERVED_TLDS else _urlhaus(host, url)
            ),
        })
    preferred = next((c for c in checks if c["domain"] in lookalikes), checks[0] if checks else None)
    age = preferred["rdap"]["age_days"] if preferred else None
    reported = any(c["urlhaus"]["known_malicious"] is True for c in checks)
    summary = f"Lookalike domain {lookalikes[0]}" if lookalikes else "No T-Mobile lookalike domain found"
    if age is not None:
        summary += (f" · registered {age} days ago (simulated RDAP)" if preferred.get("synthetic")
                    else f" · RDAP age {age} days")
    if reported:
        summary += " · URLhaus malware report"
    elif any(not c.get("synthetic") for c in checks):
        summary += " · URLhaus does not establish safety"
    result = {
        "domains": hosts, "lookalike_domains": lookalikes,
        "urgent_language": bool(URGENT_RE.search(text)),
        "domain_age_days": age, "known_malicious": True if reported else None,
        "checks": checks, "urlhaus_scope": "malware distribution, not all phishing",
        "verification_status": "partial" if checks and any(c["rdap"]["status"] == "checked" or
            c["urlhaus"]["status"] in {"reported_malware", "no_report"} for c in checks) else "unverifiable",
    }
    rdap_checked = next((c["rdap"] for c in checks if c["rdap"]["status"] == "checked"), None)
    urlhaus_checked = next((c["urlhaus"] for c in checks if c["urlhaus"]["status"] in
                            {"reported_malware", "no_report"}), None)
    if preferred and preferred.get("synthetic"):
        source = preferred["source"]
        result["source"] = source
        result["verification_status"] = "synthetic" if all(c.get("synthetic") for c in checks) else "partial"
    elif rdap_checked:
        source = {"name": "Forwarded text and RDAP registration record", "url": rdap_checked["source_url"]}
    elif urlhaus_checked:
        source = {"name": "Forwarded text and URLhaus lookup", "url": urlhaus_checked["source_url"]}
    else:
        source = {"name": "Forwarded text (local domain check; external checks unavailable)"}
    return {
        "summary": summary, "result": result, "source": source,
    }


def _policy_passages() -> list[dict]:
    passages = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        for section in re.split(r"(?=^## )", path.read_text(encoding="utf-8"), flags=re.MULTILINE):
            if not section.startswith("## "):
                continue
            lines = section.strip().splitlines()
            source = next((line[8:].strip() for line in lines if line.startswith("Source: ")), None)
            body = " ".join(line.strip() for line in lines[1:] if line.strip() and not line.startswith("Source: "))
            if source and body:
                passages.append({"title": lines[0][3:].strip(), "text": body, "url": source})
    return passages


def _embed(texts: list[str], input_type: str, key: str) -> list[list[float]]:
    response = requests.post(
        EMBED_URL,
        json={"model": EMBED_MODEL, "input": texts, "input_type": input_type, "truncate": "END"},
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=8,
    )
    response.raise_for_status()
    data = response.json()["data"]
    vectors = [None] * len(texts)
    for index, item in enumerate(data):
        slot = item.get("index", index)
        if not isinstance(slot, int) or slot < 0 or slot >= len(texts):
            raise ValueError("Invalid embedding index")
        vector = item["embedding"]
        if not isinstance(vector, list) or not vector or not all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in vector
        ):
            raise ValueError("Invalid embedding vector")
        vectors[slot] = vector
    if any(vector is None for vector in vectors):
        raise ValueError("Incomplete embedding response")
    return vectors


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions differ")
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


def _local_policy_fallback(passages: list[dict], question: str, reason: str) -> dict:
    """Return source text using deterministic word overlap, with no model claim."""
    stopwords = {"a", "an", "and", "are", "can", "do", "for", "i", "if", "in", "is", "it",
                 "me", "my", "of", "on", "or", "should", "the", "to", "what", "when", "with"}

    def terms(value: str) -> set[str]:
        words = re.findall(r"[a-z0-9]+", value.lower())
        return {word[:-1] if len(word) > 4 and word.endswith("s") else word
                for word in words if word not in stopwords}

    query_terms = terms(question)
    ranked = sorted(
        ({**passage, "keyword_hits": len(query_terms & terms(passage["title"] + " " + passage["text"]))}
         for passage in passages),
        key=lambda item: (-item["keyword_hits"], item["title"]),
    )
    matches = ranked[:2]
    summary = (f"Local policy fallback: {matches[0]['title']}"
               if matches else "Local policy fallback unavailable")
    return {
        "summary": summary,
        "result": {"status": "local_fallback", "matches": matches, "reason": reason},
        "source": ({"name": "Local policy keyword fallback", "url": matches[0]["url"]}
                   if matches else {"name": "Local policy keyword fallback"}),
    }


def policy_lookup(store, question: str = "", **_args) -> dict:
    """Retrieve sourced policy passages with NVIDIA NeMo Retriever embeddings."""
    passages = _policy_passages()
    if not passages or not (question or "").strip():
        return {
            "summary": "Policy lookup unverifiable: no question or policy passages",
            "result": {"status": "unverifiable", "matches": []},
            "source": {"name": "Local policy documents"},
        }
    question = question.strip()[:1024]
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        return _local_policy_fallback(passages, question, "NVIDIA_API_KEY missing")
    corpus_key = hashlib.sha256(json.dumps(passages, sort_keys=True).encode("utf-8")).hexdigest() + EMBED_MODEL
    try:
        cached = _cache_get("policy-passages", corpus_key, 30 * 86400)
        vectors = cached["vectors"] if cached else _embed([p["text"] for p in passages], "passage", key)
        if cached is None:
            _cache_set("policy-passages", corpus_key, {"vectors": vectors})
        query_key = EMBED_MODEL + "\0" + question
        query_cached = _cache_get("policy-query", query_key, 7 * 86400)
        query_vector = query_cached["vector"] if query_cached else _embed([question], "query", key)[0]
        if query_cached is None:
            _cache_set("policy-query", query_key, {"vector": query_vector})
        matches = sorted(
            ({**passage, "score": round(_cosine(query_vector, vector), 4)}
             for passage, vector in zip(passages, vectors)),
            key=lambda item: item["score"], reverse=True,
        )[:2]
    except (requests.RequestException, ValueError, KeyError, TypeError, OSError) as exc:
        return _local_policy_fallback(passages, question, f"Retriever unavailable: {type(exc).__name__}")
    return {
        "summary": f"Policy: {matches[0]['title']}",
        "result": {"status": "retrieved", "matches": matches, "model": EMBED_MODEL},
        "source": {"name": "NeMo Retriever over local policy", "url": matches[0]["url"]},
    }
