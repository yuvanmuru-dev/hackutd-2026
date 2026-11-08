"""Tools the Context agent calls, plus the risk score.

Uses Lane 2a's `packs.guard.tools` (TOOLS dict of name -> fn(store, **args)) and Lane 2b's `packs.guard.ml.score`
when they exist; until then, these placeholders read the brain's store so the workflow runs end to end.
Every tool returns {"summary": one line for the dashboard, "result": data, "source": Source}.
"""
from __future__ import annotations

import re

from core.store import Store, parse

HOME_REGION = {"usr_maya": "Dallas, TX", "usr_dev": "Austin, TX", "usr_priya": "Houston, TX",
               "usr_marcus": "Dallas, TX", "usr_elena": "San Antonio, TX"}


def _events(store: Store, uid: str, typ: str | None = None) -> list[dict]:
    return sorted((e for e in store.events.values() if e["user_id"] == uid and (typ is None or e["type"] == typ)),
                  key=lambda e: e["ts"])


def call_context(store: Store, user_id: str, **_):
    call = store.active_call(user_id)
    if not call:
        return {"summary": "Not on a call", "result": {"active": False}, "source": {"name": "Call record (simulated carrier signal)"}}
    s = store.call_summary(call)
    during = [e["type"] for e in _events(store, user_id) if e.get("call_id") == call["call_id"] and e["type"] != "call.started"]
    verified = call["attestation"] == "A"
    res = {"active": True, "minutes": s["duration_s"] // 60, "caller_name": call["caller_name"], "attestation": call["attestation"],
           "verified": verified, "seen_before": call["seen_before"], "scam_label": call["scam_label"],
           "suspicious": store.suspicious(call), "actions_during_call": during}
    summary = (f"On a call for {res['minutes']} min · {'verified' if verified else 'unverified (' + call['attestation'] + ')'}"
               f" · {'seen before' if call['seen_before'] else 'never contacted her'}"
               + (f" · caller ID \"{call['caller_name']}\"" if call["caller_name"] else ""))
    return {"summary": summary, "result": res, "source": {"name": "Call record (simulated carrier signal)", "record": f"calls/{call['call_id']}"}}


def protection_status(store: Store, user_id: str, **_):
    state = store.protection_state(user_id)
    changes = [{"name": e["data"]["name"], "enabled": e["data"]["enabled"], "ts": e["ts"], "during_call": bool(e.get("call_id"))}
               for e in _events(store, user_id, "protection.changed")][-5:]
    off_during_call = [c["name"] for c in changes if not c["enabled"] and c["during_call"]]
    summary = ("Turned off during the call: " + ", ".join(n.replace("_", " ") for n in off_during_call)) if off_during_call \
        else "No protection turned off during a call"
    return {"summary": summary, "result": {"state": state, "recent_changes": changes, "off_during_call": off_during_call},
            "source": {"name": "Protection log", "record": f"protections/{user_id}"}}


def account_history(store: Store, user_id: str, **_):
    evs = _events(store, user_id)
    pins = [e for e in evs if e["type"] == "transfer_pin.requested"]
    logins = [e for e in evs if e["type"] == "login"]
    devices = sorted({e["data"]["device_hash"] for e in logins})
    res = {"transfer_pins_before": max(0, len(pins) - 1), "devices_seen": devices, "logins": len(logins),
           "home_region": HOME_REGION.get(user_id), "persona": store.users[user_id].get("persona")}
    pin_txt = ("No transfer PIN requests on record" if not pins else
               "First transfer PIN request on record" if res["transfer_pins_before"] == 0 else f"{len(pins)} transfer PIN requests on record")
    summary = f"{pin_txt} · {len(devices) or 'no'} known device(s)"
    return {"summary": summary, "result": res, "source": {"name": "Account history (synthetic)", "record": f"users/{user_id}"}}


def device_sim_status(store: Store, user_id: str, **_):
    logins = _events(store, user_id, "login")
    last = logins[-1]["data"] if logins else None
    swaps = _events(store, user_id, "sim_swap.requested")
    res = {"last_login_new_device": bool(last and last.get("new_device")), "last_login_device": last and last.get("device_hash"),
           "sim_swap_requests": len(swaps)}
    summary = ("Last sign-in from a NEW device" if res["last_login_new_device"] else "Usual device") + \
              (f" · {len(swaps)} SIM swap request(s)" if swaps else "")
    return {"summary": summary, "result": res, "source": {"name": "Device registry", "record": f"devices/{user_id}"}}


def location_match(store: Store, user_id: str, **_):
    """Is the device making the request in the same region as the phone on the line right now?"""
    logins = _events(store, user_id, "login")
    lines = _events(store, user_id, "line.region")
    region = logins[-1]["data"].get("region") if logins else None
    line = lines[-1]["data"]["region"] if lines else None
    if not region or not line:
        return {"summary": "Line location unknown (unverifiable)", "result": {"request_region": region, "line_region": line, "match": None},
                "source": {"name": "Login region vs line serving region (simulated carrier signal)"}}
    match = region == line
    return {"summary": f"Request from {region} · her phone is in {line} · {'match' if match else 'MISMATCH'}",
            "result": {"request_region": region, "line_region": line, "match": match},
            "source": {"name": "Login region vs line serving region (simulated carrier signal)", "record": f"events/{lines[-1]['event_id']}"}}


def _rhythm_text(dist) -> str | None:
    """Typing rhythm vs her on-device baseline (timing only, D-006: no key values ever leave the portal)."""
    if not isinstance(dist, (int, float)) or isinstance(dist, bool) or dist < 0:
        return None
    if dist < 1:
        return "typing matches her usual rhythm"
    return f"typing rhythm {dist:.1f}× off her usual"


def portal_signals(store: Store, user_id: str, **_):
    sig = _events(store, user_id, "portal.signals")
    d = sig[-1]["data"] if sig else None
    if not d:
        return {"summary": "No portal behavior recorded", "result": None, "source": {"name": "Portal behavior (derived)"}}
    summary = f"{round(d['hesitation_ms'] / 1000)} s hesitation · left the page {d['tab_switches']}× · paste into PIN: {'yes' if d['paste_into_pin'] else 'no'}"
    rhythm = _rhythm_text(d.get("typing_rhythm_distance"))
    if rhythm:
        summary += f" · {rhythm}"
    # Evidence for the agents and dashboards only: rules_score and the frozen ML pack (D-053) never read the rhythm.
    return {"summary": summary,
            "result": d, "source": {"name": "Portal behavior (derived numbers)", "record": f"events/{sig[-1]['event_id']}"}}


_DOMAIN = re.compile(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b", re.I)


def check_message(store: Store, text: str = "", **_):
    domains = [d.lower() for d in _DOMAIN.findall(text or "")]
    lookalike = [d for d in domains if ("t-mobile" in d or "tmobile" in d) and not d.endswith("t-mobile.com")]
    urgent = bool(re.search(r"(?i)locked|suspend|verify now|urgent|immediately", text or ""))
    res = {"domains": domains, "lookalike_domains": lookalike, "urgent_language": urgent,
           "domain_age_days": None, "known_malicious": None, "note": "placeholder: RDAP/URLhaus come from Lane 2a"}
    summary = (f"Lookalike domain {lookalike[0]}" if lookalike else "No lookalike domain") + (" · urgent language" if urgent else "")
    return {"summary": summary, "result": res, "source": {"name": "Message check (placeholder)"}}


def recent_scam_reports(store: Store, **_):
    return {"summary": "No prior reports (placeholder)", "result": [], "source": {"name": "Scam reports (placeholder)"}}


POLICY = ["T-Mobile never calls customers and asks them to turn off SIM Protection or Port Out Protection.",
          "T-Mobile never asks customers to read out a PIN, one-time code, or transfer PIN on a call.",
          "A transfer PIN lets another carrier take the number; scammers use it to take over bank and email accounts."]


def policy_lookup(store: Store, question: str = "", **_):
    return {"summary": "Policy: T-Mobile never asks you to turn off protection or share a PIN on a call",
            "result": POLICY, "source": {"name": "Carrier security policy (our summary)"}}


PLACEHOLDERS = {f.__name__: f for f in (call_context, protection_status, account_history, device_sim_status, location_match,
                                        portal_signals, check_message, recent_scam_reports, policy_lookup)}


def tools() -> dict:
    try:  # Lane 2a's real tools win when present
        from packs.guard.tools import TOOLS as real  # type: ignore
        return PLACEHOLDERS | dict(real)
    except Exception:  # noqa: BLE001
        return PLACEHOLDERS


def run_tool(store: Store, name: str, args: dict) -> dict:
    fn = tools().get(name)
    if not fn:
        return {"summary": f"unknown tool {name}", "result": None, "source": {"name": "n/a"}, "error": True}
    try:
        out = fn(store, **args)
        out.setdefault("summary", name)
        out.setdefault("source", {"name": name})
        return out
    except Exception as e:  # noqa: BLE001
        return {"summary": f"{name} failed: {type(e).__name__}", "result": None, "source": {"name": name}, "error": True}


# ---------- risk score (Lane 2b's ml.score wins when present)
def _conf(p: float) -> str:
    return "high" if p >= 0.8 else "medium" if p >= 0.5 else "low"


def rules_score(store: Store, user_id: str, event: dict) -> dict:
    cc = call_context(store, user_id)["result"]
    ps = protection_status(store, user_id)["result"]
    ah = account_history(store, user_id)["result"]
    ds = device_sim_status(store, user_id)["result"]
    lm = location_match(store, user_id)["result"]
    pt = portal_signals(store, user_id)["result"] or {}
    reasons = []

    def add(feature, w, text):
        reasons.append({"feature": feature, "contribution": w, "text": text})

    if event["type"] == "message.forwarded":
        text = event["data"].get("text", "")
        cm = check_message(store, text)["result"]
        # D-052: pressure wording alone is not a scam. Scam needs a lookalike, a non-official link, or a request for secrets/money.
        official = ("t-mobile.com", "tmobile.com")
        links = [d for d in cm["domains"] if not d.endswith(official)]
        asks = re.search(r"(?i)\b(verification code|one[- ]time code|passcode|password|\bPIN\b|gift ?cards?|wire (?:money|transfer)|"
                         r"crypto|bitcoin|zelle|venmo|cash ?app|send (?:money|payment))", text)
        if cm["lookalike_domains"]:
            p = 0.9
            add("lookalike_domain", 0.5, f"{cm['lookalike_domains'][0]} imitates T-Mobile")
        elif asks:
            p = 0.8
            add("asks_for_secret_or_money", 0.4, "Asks for a code, PIN, password or money")
        elif links:
            p = 0.6
            add("unknown_link", 0.3, f"Link to {links[0]}, not an official T-Mobile site")
        else:
            p = 0.35 if cm["urgent_language"] else 0.2
        if cm["urgent_language"]:
            add("urgent_language", 0.2 if p >= 0.5 else 0.1,
                "Pressure language (locked, verify now)" + ("" if p >= 0.5 else ": worth a look, but not a scam by itself"))
        return {"threat": "scam_text" if p >= 0.5 else "legit", "probability": p, "calibrated": False, "confidence": _conf(p),
                "anomaly": None, "top_reasons": reasons or [{"feature": "none", "contribution": 0, "text": "Nothing suspicious found"}], "model": "rules"}

    if ds["last_login_new_device"] and lm["match"] is False:
        add("new_device", 0.35, "A device never seen on this account")
        add("region_mismatch", 0.35, f"Request from {lm['request_region']} while her line is in {lm['line_region']}")
        p, threat = 0.9, "takeover"
    else:
        p, threat = 0.1, "legit"
        if cc.get("suspicious"):
            p += 0.25
            add("unverified_call", 0.25, f"On a {cc['minutes']}-minute call from an unverified number that never contacted her")
            if ps["off_during_call"]:
                p += 0.3
                add("protection_off_during_call", 0.3, "A protection was turned off during that call")
            if event["type"] in ("transfer_pin.requested", "otp.sent"):
                p += 0.2
                add("sensitive_action_during_call", 0.2, "Transfer PIN or login code requested during that call")
            if ah["transfer_pins_before"] == 0 and event["type"] == "transfer_pin.requested":
                p += 0.05
                add("first_time_action", 0.05, "First transfer PIN request on record")
            if pt.get("tab_switches", 0) >= 2 or pt.get("hesitation_ms", 0) > 20000:
                p += 0.05
                add("portal_hesitation", 0.05, "Long pauses and leaving the page mid-flow")
            if not ds["last_login_new_device"] and lm["match"] is not False:
                add("known_device_home_region", -0.05, "Her own device and area: it is really her")
            threat = "coached" if p >= 0.5 else "legit"
        p = min(p, 0.95)
    reasons.sort(key=lambda r: -abs(r["contribution"]))
    return {"threat": threat, "probability": round(p, 2), "calibrated": False, "confidence": _conf(p), "anomaly": None,
            "top_reasons": reasons[:5] or [{"feature": "none", "contribution": 0, "text": "Nothing unusual"}], "model": "rules"}


def score(store: Store, user_id: str, event: dict) -> dict:
    # D-060: forwarded texts go to the rules (sealed test: rules 28/30 scam texts vs ML 6/30); calls, logins,
    # SIM swaps and PIN requests use the hybrid ML+rules model (30/30 coached calls vs rules 21/30).
    if event.get("type") == "message.forwarded":
        return rules_score(store, user_id, event)
    try:
        from packs.guard.ml import score as ml_score  # type: ignore
        history = [e for e in store.events.values() if e["user_id"] == user_id]
        out = ml_score(user_id, event, sorted(history, key=lambda e: parse(e["ts"])))
        if out and out.get("threat"):
            return out
    except Exception:  # noqa: BLE001
        pass
    return rules_score(store, user_id, event)
