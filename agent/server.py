"""The one brain every channel calls: website, phone (Pipecat voice bot), and email (AgentMail webhook).

Run:  uvicorn server:app --reload --port 8000
Docs: http://localhost:8000/docs

Rule for the whole ecosystem: channels never call Census/FEMA/etc. directly.
They call this API, so the website, the phone agent and the email agent always
give the same answer, and a fix here fixes all three.
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import nemotron_agent as agent
from tools import TOOL_SCHEMAS, TOOLS

app = FastAPI(title="Groundtruth brain")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_client = None


def client():
    global _client
    if _client is None:
        _client = agent.make_client()
    return _client


class CheckRequest(BaseModel):
    address: str
    listing: str
    channel: str = "web"  # web | voice | email, for logs and the report


@app.get("/health")
def health():
    return {"ok": True, "tools": list(TOOLS)}


@app.get("/tools")
def list_tools():
    """Same schemas Nemotron sees. The voice bot registers these as its function-calling tools."""
    return TOOL_SCHEMAS


@app.post("/tools/{name}")
def call_tool(name: str, args: dict):
    """Run one tool directly. The voice bot uses this so a caller can ask one quick question."""
    if name not in TOOLS:
        raise HTTPException(404, f"unknown tool {name}")
    return agent.run_tool(name, json.dumps(args))


@app.post("/check")
def check(req: CheckRequest):
    """Full agent run, returns the trust report. Email agent and simple clients use this."""
    report = agent.run_agent(client(), req.address, req.listing, on_step=lambda s: None)
    report["channel"] = req.channel
    return report


@app.post("/check/stream")
def check_stream(req: CheckRequest):
    """Same run, streamed as Server-Sent Events so the website can show each step live."""
    def events():
        steps = []
        report = agent.run_agent(client(), req.address, req.listing, on_step=steps.append)
        for s in steps:
            yield f"event: step\ndata: {json.dumps(s)}\n\n"
        report["channel"] = req.channel
        yield f"event: report\ndata: {json.dumps(report)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")
