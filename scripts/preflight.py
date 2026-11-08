"""Preflight: one command that says whether the demo will work, before every rehearsal and before judging.

  python scripts/preflight.py                 # real rehearsal: MOCK=0, live texts and calls
  python scripts/preflight.py --for judging   # same, plus DEMO_MODE on and a recording present
  python scripts/preflight.py --for dev       # mock brain is fine; doors optional
  python scripts/preflight.py --no-models     # skip the live Nemotron ping

Prints only names and yes/no, never key values or phone numbers. Exit code 1 if anything is red.
URLs: BRAIN_URL (8000), WEB_URL (3000), MESSAGING_URL (8200), VOICE_URL (8100).
"""
import argparse
import json
import subprocess
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OK, WARN, BAD = "✅", "⚠️ ", "❌"
problems, warnings = [], []


def line(status, label, detail=""):
    print(f"  {status} {label}" + (f": {detail}" if detail else ""))
    if status == BAD:
        problems.append(label)
    elif status == WARN:
        warnings.append(label)


def get(url, timeout=4):
    """(status_code, json_or_None). Any HTTP response means the service is up."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read()
            try:
                return r.status, json.loads(body or b"null")
            except json.JSONDecodeError:
                return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:  # noqa: BLE001
        return None, None


def env_file(path):
    vals = {}
    p = ROOT / path
    if not p.exists():
        return None
    for raw in p.read_text().splitlines():
        if "=" in raw and not raw.lstrip().startswith("#"):
            k, v = raw.split("=", 1)
            vals[k.strip()] = v.split(" #", 1)[0].strip()
    return vals


def need(env, path, names, label):
    if env is None:
        line(BAD, label, f"{path} not found")
        return
    missing = [n for n in names if not env.get(n)]
    line(BAD if missing else OK, label, ("missing: " + ", ".join(missing)) if missing else "all set")


def numbers(env, *names):
    out = set()
    for n in names:
        out |= {x.strip() for x in (env or {}).get(n, "").split(",") if x.strip()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--for", dest="mode", choices=["rehearsal", "judging", "dev"], default="rehearsal")
    ap.add_argument("--no-models", action="store_true")
    a = ap.parse_args()
    real = a.mode != "dev"
    brain = os.getenv("BRAIN_URL", "http://localhost:8000").rstrip("/")
    web = os.getenv("WEB_URL", "http://localhost:3000").rstrip("/")
    msg = os.getenv("MESSAGING_URL", "http://localhost:8200").rstrip("/")
    voice = os.getenv("VOICE_URL", "http://localhost:8100").rstrip("/")
    print(f"Titan preflight ({a.mode})")

    print("Brain")
    code, h = get(brain + "/health")
    if code != 200 or not h:
        line(BAD, "brain running", f"no answer at {brain}; start: bash scripts/dev.sh")
    else:
        line(OK, "brain running", f"contract v{h.get('version')}")
        if real:
            line(BAD if h.get("mock") else OK, "real agents (MOCK=0)", "brain is in MOCK mode" if h.get("mock") else "")
        cache = h.get("llm_cache", {})
        if a.mode == "judging":
            line(OK if cache.get("mode") == "replay" else BAD, "DEMO_MODE on", f"cache mode {cache.get('mode')}")
            line(OK if cache.get("entries", 0) >= 20 else BAD, "recording present", f"{cache.get('entries', 0)} recorded answers")
        doors = h.get("doors", {})
        if real:
            line(OK if doors.get("messaging_url_set") else BAD, "brain → messaging address set", "" if doors.get("messaging_url_set") else "brain started without MESSAGING_URL: no texts will go out")
            line(OK if doors.get("voice_url_set") else WARN, "brain → voice address set", "" if doors.get("voice_url_set") else "no Titan calls")
        cases = len((get(brain + "/cases")[1]) or [])
        line(OK if cases == 0 else WARN, "clean slate", "no cases" if cases == 0 else f"{cases} case(s) left over: POST {brain}/demo/reset")
    agent_env = env_file("agent/.env")
    need(agent_env, "agent/.env", ["NVIDIA_API_KEY"], "agent/.env keys")
    rec = ROOT / "agent/core/recordings/llm_cache.json"
    if rec.exists():
        try:  # git rewrites file times on checkout; the last commit (or local edit, if newer) tells the real age
            committed = int(subprocess.run(["git", "log", "-1", "--format=%ct", "--", str(rec)], capture_output=True, text=True,
                                           cwd=ROOT).stdout.strip() or 0)
        except Exception:  # noqa: BLE001
            committed = 0
        dirty = subprocess.run(["git", "status", "--porcelain", "--", str(rec)], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        age_h = (time.time() - (rec.stat().st_mtime if dirty or not committed else committed)) / 3600
        line(OK if age_h < 12 else WARN, "DEMO_MODE recording file", f"{len(json.loads(rec.read_text()))} answers, recorded {age_h:.1f} h ago")
    else:
        line(WARN if a.mode != "judging" else BAD, "DEMO_MODE recording file", "none: run python scripts/record_demo.py")

    self_base = (agent_env or {}).get("NEMOTRON_NANO_BASE_URL", "").rstrip("/")
    if self_base:
        print("Self-hosted Nemotron (Brev)")
        code, models = get(self_base + "/models", timeout=8)
        served = [m.get("id") for m in (models or {}).get("data", [])] if isinstance(models, dict) else []
        want = (agent_env or {}).get("NEMOTRON_NANO_SELF_MODEL", "")
        if code == 200:
            line(OK if not want or want in served else BAD, "Brev endpoint up",
                 f"serves {', '.join(served) or 'unknown'}" + ("" if not want or want in served else f"; NEMOTRON_NANO_SELF_MODEL '{want}' not served"))
        else:
            line(WARN, "Brev endpoint up", "not reachable: the brain falls back to the hosted API (box stopped?)")
    if not a.no_models and agent_env and agent_env.get("NVIDIA_API_KEY"):
        print("Nemotron")
        sys.path.insert(0, str(ROOT / "agent"))
        os.chdir(ROOT / "agent")
        os.environ.setdefault("DEMO_MODE", "0")
        os.environ["LLM_CACHE"] = "off"
        try:
            from core import llm  # noqa: E402
            for role in ("nano", "super"):
                t = time.time()
                try:
                    llm.chat(role, [{"role": "user", "content": 'Reply with exactly: {"ok": true}'}], max_tokens=20)
                    line(OK, f"{role} model answers", f"{llm.model_for(role)} in {time.time() - t:.1f}s")
                except Exception as e:  # noqa: BLE001
                    line(BAD if a.mode != "judging" else WARN, f"{role} model answers", f"{type(e).__name__}" + (" (DEMO_MODE replay can cover this)" if a.mode == "judging" else ""))
        except Exception as e:  # noqa: BLE001
            line(WARN, "model ping skipped", type(e).__name__)

    print("Web")
    for path in ("/", "/portal/security", "/guardian", "/console"):
        code, _ = get(web + path, timeout=8)
        line(OK if code == 200 else BAD, f"page {path}", "" if code == 200 else f"status {code}; start: cd web && npm run dev")

    print("Messaging (Photon iMessage)")
    code, _ = get(msg + "/")
    line(OK if code else (BAD if real else WARN), "messaging running", "" if code else f"no answer at {msg}")
    menv = env_file("messaging/.env")
    need(menv, "messaging/.env", ["PHOTON_API_KEY", "PHOTON_PROJECT_ID", "USER_PHONE_usr_maya", "OUTBOUND_ALLOWLIST"], "messaging/.env keys")
    if menv and menv.get("USER_PHONE_usr_maya"):
        inside = menv["USER_PHONE_usr_maya"] in numbers(menv, "OUTBOUND_ALLOWLIST")
        line(OK if inside else BAD, "Maya's phone on the messaging allowlist", "" if inside else "texts to Maya will be refused")

    print("Voice (Titan's call)")
    code, vh = get(voice + "/health")
    if not code:
        line(WARN, "voice running", f"no answer at {voice} (demo can run text-only)")
    else:
        line(OK, "voice running")
        if vh:
            line(OK if vh.get("intervention_ready") else WARN, "Titan call ready", "" if vh.get("intervention_ready") else "voice says the intervention call isn't ready yet")
            miss = vh.get("forwarding_configuration_required") or []
            line(OK if not miss else WARN, "call forwarding configured", ("missing: " + ", ".join(miss)) if miss else "")
    venv = env_file("voice/.env")
    if venv is not None:
        if venv.get("VOICE_PUBLIC_URL"):
            code, _ = get(venv["VOICE_PUBLIC_URL"].rstrip("/") + "/health", timeout=8)
            line(OK if code == 200 else BAD, "voice tunnel reachable", "" if code == 200 else "tunnel down or URL changed: update Twilio's webhook")
        if venv.get("MAYA_PHONE_NUMBER") and menv and menv.get("USER_PHONE_usr_maya"):
            same = venv["MAYA_PHONE_NUMBER"] == menv["USER_PHONE_usr_maya"]
            line(OK if same else WARN, "same phone is Maya for texts and calls", "" if same else "voice and messaging point at different phones")

    print()
    if problems:
        print(f"{BAD} NOT READY: {len(problems)} problem(s): " + "; ".join(problems))
    else:
        print(f"{OK} READY" + (f" ({len(warnings)} warning(s))" if warnings else ""))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
