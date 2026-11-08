"""Record one live rehearsal of every demo scenario so DEMO_MODE can replay Nemotron's answers on stage.

1. Start the brain in record mode (needs your NVIDIA key in agent/.env):
     cd agent && MOCK=0 LLM_CACHE=record REPLY_TIMEOUT_S=5 RECOVERY_TIMEOUT_S=30 \\
       uv run --no-project --with-requirements requirements.txt uvicorn server:app --port 8000
2. Run:  python scripts/record_demo.py            (BRAIN_URL defaults to http://localhost:8000)
3. On stage: start the brain with DEMO_MODE=1 (MOCK=0). Matching prompts are answered from
   agent/core/recordings/llm_cache.json; anything new runs live. The dashboard labels the run.
Re-record after changing prompts, tools or data. Recording texts nobody: it never sets MESSAGING_URL or VOICE_URL itself.
"""
import base64
import json
import os
import pathlib
import sys
import time
import urllib.request

B = os.getenv("BRAIN_URL", "http://localhost:8000").rstrip("/")
ROOT = pathlib.Path(__file__).resolve().parent


def call(method: str, path: str, body=None):
    req = urllib.request.Request(B + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def finish(cid: str, timeout: float = 240):
    end, approved = time.time() + timeout, False
    while time.time() < end:
        d = call("GET", f"/cases/{cid}")
        if d["status"] == "recovering" and not approved:  # Maya says yes to every recovery step, as in the demo
            approved = True
            for a in [a for a in d["actions"] if a["status"] == "awaiting_approval"]:
                call("POST", f"/actions/{a['action_id']}/approve", {"via": "voice"})
        if d["steps"] and d["steps"][-1]["type"] == "done":
            return d
        time.sleep(0.5)
    raise SystemExit(f"case {cid} did not finish in {timeout}s")


def newest(prefix: str = "") -> str:
    for _ in range(40):
        cases = [c for c in call("GET", "/cases") if c["title"].startswith(prefix)]
        if cases:
            return sorted(cases, key=lambda c: c["created_at"])[-1]["case_id"]
        time.sleep(0.5)
    raise SystemExit(f"no case starting with {prefix!r}")


def main():
    h = call("GET", "/health")
    if h.get("mock") or h.get("llm_cache", {}).get("mode") != "record":
        sys.exit("Start the brain with MOCK=0 LLM_CACHE=record first (see the top of this file).")
    t0 = time.time()
    call("POST", "/demo/reset")
    call("POST", "/demo/play/t2")
    time.sleep(6)
    d = finish(newest())
    print(f"t2 coached: {d['threat']} · {len(d['steps'])} steps")
    call("POST", "/events", {"event_id": f"evt_rec_{time.time_ns()}", "user_id": "usr_maya", "type": "call.ended",
                             "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "voice",
                             "call_id": d["call"]["call_id"], "data": {"duration_s": 600}})
    call("POST", "/demo/play/t5")
    time.sleep(2)
    print("t5 repeat scam:", call("GET", f"/cases/{newest('Reported scam')}")["messages"][-1]["text"][:70], "…")
    for scn, prefix in (("t1", "SIM swap"), ("t3", "Forwarded")):
        call("POST", "/demo/reset")
        call("POST", f"/demo/play/{scn}")
        time.sleep(3)
        d = finish(newest(prefix))
        print(f"{scn}: {d['threat']} · {len(d['steps'])} steps")
    call("POST", "/demo/reset")
    img = base64.b64encode((ROOT / "demo_assets" / "scam_screenshot.png").read_bytes()).decode()
    r = call("POST", "/events", {"event_id": f"evt_rec_{time.time_ns()}", "user_id": "usr_maya", "type": "message.forwarded",
                                 "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "messaging", "call_id": None,
                                 "data": {"channel": "imessage", "image_url": "data:image/png;base64," + img}})
    d = finish(r["case_id"])
    print(f"screenshot: {d['threat']} · {len(d['steps'])} steps")
    call("POST", "/demo/reset")
    print(f"recorded in {time.time() - t0:.0f}s ->", call("GET", "/health")["llm_cache"])


if __name__ == "__main__":
    main()
