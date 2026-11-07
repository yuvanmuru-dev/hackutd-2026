"""Groundtruth agent (working name): checks a real-estate listing's claims against public data.

Why this fits both tracks:
  NVIDIA: Nemotron plans, calls external APIs as tools, loops until done (not a chatbot).
  CBRE:   turns a listing into a "trust report": every claim gets a verdict + a source link.

Run:
  python nemotron_agent.py --address "800 W Campbell Rd, Richardson, TX 75080" \
      --listing "Not in a flood zone. Walkable to grocery and transit. Priced below the area median."
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOL_SCHEMAS, TOOLS

load_dotenv()

MODEL = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-super-120b-a12b")
MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "10"))

SYSTEM = """You are a real-estate due-diligence agent. You do not chat. You run a workflow:
1. PLAN: list each factual claim in the listing and which tool can check it.
2. EXECUTE: call tools. Always geocode first. Never invent a tool result.
3. VERIFY: compare each claim to the tool data.
4. REPORT: when done, reply with ONLY a JSON object:
{"address": str,
 "claims": [{"claim": str, "verdict": "supported"|"contradicted"|"unverifiable",
             "evidence": str, "source": str}],
 "trust_score": int 0-100,
 "summary": str}
If a tool errors, mark affected claims "unverifiable" and say why. Do not guess."""


def make_client() -> OpenAI:
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        sys.exit("Set NVIDIA_API_KEY in agent/.env (get one at build.nvidia.com, starts with nvapi-)")
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=key)


def run_tool(name: str, args_json: str) -> dict:
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    try:
        args = json.loads(args_json or "{}")
        return fn(**args)
    except Exception as e:  # report the failure to the model instead of crashing the demo
        return {"error": f"{type(e).__name__}: {e}"}


def run_agent(client, address: str, listing: str, on_step=print) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Address: {address}\n\nListing text:\n{listing}"},
    ]
    for step in range(1, MAX_STEPS + 1):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.6,  # NVIDIA's suggested setting for tool calling
            top_p=0.95,
            max_tokens=4096,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                result = run_tool(tc.function.name, tc.function.arguments)
                on_step(f"[step {step}] {tc.function.name}({tc.function.arguments}) -> {json.dumps(result)[:200]}")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
            continue
        # No tool call means the model thinks it's done. Parse the report.
        text = (msg.content or "").strip()
        start, end = text.find("{"), text.rfind("}")
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": "Reply with ONLY the JSON report object."})
    return {"error": f"agent hit MAX_STEPS={MAX_STEPS} without a report"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--address", required=True)
    p.add_argument("--listing", required=True)
    a = p.parse_args()
    report = run_agent(make_client(), a.address, a.listing)
    print(json.dumps(report, indent=2))
