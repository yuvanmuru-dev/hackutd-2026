"""Offline integration gate: audit/reply text must not approve a voice action.

Run from voice/: .venv/Scripts/python.exe scripts/check_brain_approval_boundary.py
Uses the actual brain HTTP routes/recovery loop; only NVIDIA interpretation is
substituted. No server process, provider access, call, or message is created.
"""
import asyncio
from contextlib import suppress
import os
from pathlib import Path
import sys

os.environ["MOCK"] = "1"
os.environ.pop("VOICE_URL", None)
os.environ.pop("MESSAGING_URL", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))

import httpx
import server
from core import workflow
from core.store import store
from brain import Brain


async def check(kind):
    store.reset()
    case = store.new_case("usr_maya", "Synthetic voice approval boundary", None)
    cid = case["case_id"]
    run = workflow.Run(store, case, "coached", {"type": "transfer_pin.requested"})
    async def interpret(*args):
        # External-model substitution: a clear YES interpreted as YES. The
        # production brain must keep audit/unbound voice text out of this path.
        return {"intent": "yes"}
    run.call = interpret
    task = asyncio.create_task(run.recover())
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://brain.test") as client:
            brain = Brain(client)
            async with asyncio.timeout(2):
                while not case["actions"]:
                    await asyncio.sleep(.01)
            if kind == "transcript":
                await brain.transcript(cid, "in", "Yes.")
            else:
                await brain.reply(cid, "usr_maya", "Yes.")
            await asyncio.sleep(.1)
            applied = [a for a in case["actions"] if a["status"] == "applied"]
            if applied:
                print(f"FAIL {kind}: uncorrelated voice text approved {len(applied)} recovery action(s)")
                return False
            first = case["actions"][0]
            await brain.decide(first["action_id"], True)
            async with asyncio.timeout(2):
                while len(store.outbox) < 2:
                    await asyncio.sleep(.01)
            assert len([a for a in case["actions"] if a["status"] == "applied"]) == 1
            assert store.outbox[-1]["payload"]["action_id"] == case["actions"][1]["action_id"]
            print(f"PASS {kind}: audit/reply did not approve; explicit voice decision advanced one text question")
            return True
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        workflow._inbox.pop(cid, None)
        workflow._wakes.pop(cid, None)
        store.reset()


async def main():
    results = [await check(kind) for kind in ("transcript", "customer.reply")]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
