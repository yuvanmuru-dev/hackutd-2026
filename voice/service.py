"""Signed provider webhooks. The forwarded scam call never has a media stream."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import secrets
import time
from urllib.parse import parse_qsl
import xml.etree.ElementTree as ET

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
import httpx
from starlette.datastructures import FormData
from twilio.request_validator import RequestValidator

from brain import Brain
from config import Settings, phone

log = logging.getLogger("titan.voice")
TERMINAL = {"completed", "busy", "failed", "no-answer", "canceled"}


def emit(event: str, **fields) -> None:
    log.info(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "level": "info", "event": event, **fields}))


def xml(root: ET.Element) -> Response:
    return Response(ET.tostring(root, encoding="unicode"), media_type="application/xml")


def reject() -> Response:
    root = ET.Element("Response")
    ET.SubElement(root, "Reject", reason="rejected")
    return xml(root)


@dataclass
class ForwardedCall:
    call_id: str
    other_hash: str
    created: float
    started: dict | None = None
    ended: dict | None = None
    sent_started: bool = False
    sent_ended: bool = False
    terminal: bool = False


def create_app(settings: Settings | None = None, brain: Brain | None = None, probe_runner=None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(base_url=settings.brain_url, timeout=8) as client:
            app.state.brain = brain or Brain(client)
            emit("voice.started", port=8100, milestone="bridge", intervention_ready=False)
            yield

    app = FastAPI(title="Titan voice bridge", lifespan=lifespan)
    app.state.settings = settings
    calls: dict[str, ForwardedCall] = {}
    grants: dict[str, tuple[str, float]] = {}
    lock = asyncio.Lock()

    def require_ready(**kwargs) -> None:
        missing = settings.missing(**kwargs)
        if missing:
            raise HTTPException(503, {"configuration_required": missing})

    def digest(value: str) -> str:
        return hmac.new(settings.hash_salt.encode(), value.encode(), hashlib.sha256).hexdigest()

    async def signed_form(request: Request) -> FormData:
        require_ready()
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
            raise HTTPException(415, "Expected provider form data")
        # Bound the body while reading, including chunked requests.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                raise HTTPException(413, "Provider payload too large")
        try:
            form = FormData(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
        except (UnicodeError, ValueError):
            raise HTTPException(400, "Invalid provider payload") from None
        target = settings.public_url + request.url.path
        if request.url.query:
            target += "?" + request.url.query
        if not RequestValidator(settings.auth_token).validate(target, form, request.headers.get("x-twilio-signature", "")):
            raise HTTPException(401, "Invalid provider signature")
        if form.get("AccountSid") != settings.account_sid:
            raise HTTPException(401, "Unexpected provider account")
        return form

    def allowed(value: str) -> bool:
        try:
            return phone(value) in settings.allowlist
        except ValueError:
            return False

    def prune() -> None:
        now = time.monotonic()
        for token, (_, expires) in list(grants.items()):
            if expires <= now:
                del grants[token]
        # Call state is retained for a day to absorb duplicate/late callbacks.
        # Restarting voice loses this state; finish calls before restarting the demo.
        for sid, call in list(calls.items()):
            if call.terminal and now - call.created > 86400:
                del calls[sid]

    def event(call: ForwardedCall, kind: str, ts: datetime, data: dict) -> dict:
        return {"event_id": f"evt_voice_{call.call_id[5:]}_{kind}", "user_id": "usr_maya",
                "type": f"call.{kind}", "ts": ts.isoformat(), "source": "voice",
                "call_id": call.call_id, "data": data}

    def start(call: ForwardedCall, ts: datetime) -> None:
        call.started = event(call, "started", ts, {
            "direction": "in", "other_number_hash": call.other_hash,
            "caller_name": settings.caller_name, "attestation": settings.attestation,
            "seen_before": settings.seen_before, "scam_label": settings.scam_label,
        })

    async def flush(call: ForwardedCall) -> None:
        try:
            if call.started and not call.sent_started:
                await app.state.brain.event(call.started)
                call.sent_started = True
                emit("carrier.call_started", call_id=call.call_id, metadata="simulated")
            if call.ended and not call.sent_ended:
                await app.state.brain.event(call.ended)
                call.sent_ended = True
                emit("carrier.call_ended", call_id=call.call_id)
        except httpx.HTTPError:
            # Returning non-2xx lets the provider retry the same deterministic event.
            # Never log an HTTP exception: its URL/body may contain private data.
            emit("brain.delivery_failed", call_id=call.call_id)
            raise HTTPException(503, "Brain unavailable; retry callback") from None

    @app.get("/health")
    async def health():
        return {"ok": True, "milestone": "bridge", "intervention_ready": False,
                "forwarding_configuration_required": settings.missing(forwarding=True),
                "probe_enabled": settings.probe_enabled,
                "probe_configuration_required": settings.missing(speech=True)}

    @app.post("/webhooks/twilio/inbound")
    async def inbound(request: Request):
        form = await signed_form(request)
        require_ready(forwarding=True)
        if not allowed(form.get("From", "")):
            return reject()
        sid = form.get("CallSid", "")
        if not sid or len(sid) > 128:
            raise HTTPException(422, "Missing or invalid call ID")
        async with lock:
            prune()
            if sid not in calls:
                if len(calls) >= 1000:
                    raise HTTPException(503, "Demo call capacity reached")
                calls[sid] = ForwardedCall("call_voice_" + digest(sid)[:32], "h_" + digest(phone(form["From"])), time.monotonic())
        root = ET.Element("Response")
        dial = ET.SubElement(root, "Dial", answerOnBridge="true", record="do-not-record",
                             callerId=settings.twilio_number)
        ET.SubElement(dial, "Number", statusCallback=settings.public_url + "/webhooks/twilio/forward-status",
                      statusCallbackEvent="answered completed", statusCallbackMethod="POST").text = settings.maya_number
        return xml(root)

    @app.post("/webhooks/twilio/forward-status")
    async def forward_status(request: Request):
        form = await signed_form(request)
        parent = form.get("ParentCallSid", "")
        status = form.get("CallStatus")
        async with lock:
            call = calls.get(parent)
            if call is None:
                # Do not guess events from an unknown/restarted call.
                raise HTTPException(409, "Unknown parent call; inspect demo state")
            now = datetime.now(timezone.utc)
            if status == "in-progress" and not call.terminal and call.started is None:
                start(call, now)
            if status in TERMINAL and not call.terminal:
                try:
                    duration = int(form.get("CallDuration", "0"))
                    if duration < 0 or duration > 86400:
                        raise ValueError
                except ValueError:
                    raise HTTPException(422, "Invalid call duration") from None
                # Completion can arrive before answered. Deliver start, then end, so
                # a late answered callback cannot reopen shield mode in the brain.
                if call.started is None and (status == "completed" or duration > 0):
                    start(call, now - timedelta(seconds=duration))
                if call.started:
                    call.ended = event(call, "ended", now, {"duration_s": duration})
                call.terminal = True
            await flush(call)
        return Response(status_code=204)

    @app.post("/webhooks/twilio/bridge-probe")
    async def bridge_probe(request: Request):
        form = await signed_form(request)
        if not settings.probe_enabled:
            raise HTTPException(404, "Bridge probe is disabled")
        require_ready(speech=True)
        if not allowed(form.get("From", "")):
            return reject()
        sid = form.get("CallSid", "")
        if not sid or len(sid) > 128:
            raise HTTPException(422, "Missing or invalid call ID")
        async with lock:
            prune()
            if sid in calls:
                raise HTTPException(409, "A forwarded call cannot enter the audio probe")
            if len(grants) >= 100:
                raise HTTPException(503, "Probe capacity reached")
            token = secrets.token_urlsafe(32)
            grants[token] = (sid, time.monotonic() + 90)
        root = ET.Element("Response")
        stream = ET.SubElement(ET.SubElement(root, "Connect"), "Stream",
                               url=settings.public_url.replace("https://", "wss://", 1) + "/ws/bridge")
        ET.SubElement(stream, "Parameter", name="bridge_token", value=token)
        return xml(root)

    @app.websocket("/ws/bridge")
    async def bridge_socket(websocket: WebSocket):
        target = settings.public_url.replace("https://", "wss://", 1) + "/ws/bridge"
        signature = websocket.headers.get("x-twilio-signature", "")
        validator = RequestValidator(settings.auth_token)
        if (not settings.probe_enabled or settings.missing(speech=True)
                or not any(validator.validate(url, {}, signature) for url in (target, target + "/"))):
            await websocket.close(code=1008)
            return
        # Twilio delivers the token over its signed TwiML fetch, in start.customParameters.
        # The one-use grant is bound to this call and expires in 90 seconds. No model
        # or audio pipeline is created before it is checked.
        await websocket.accept()
        try:
            async with asyncio.timeout(10):
                connected = await websocket.receive_json()
                if connected.get("event") != "connected":
                    await websocket.close(code=1008)
                    return
                message = await websocket.receive_json()
            data = message.get("start", {})
            token = data.get("customParameters", {}).get("bridge_token", "")
            if not isinstance(token, str):
                await websocket.close(code=1008)
                return
            async with lock:
                prune()
                grant = grants.get(token)
                if (message.get("event") != "start" or not grant or grant[0] != data.get("callSid")
                        or data.get("accountSid") != settings.account_sid or not data.get("streamSid")
                        or data.get("mediaFormat") != {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1}
                        or data.get("callSid") in calls):
                    await websocket.close(code=1008)
                    return
                del grants[token]
            runner = probe_runner
            if runner is None:
                from bot import run_probe
                runner = run_probe
            await runner(websocket, data, settings)
        except (TimeoutError, ValueError, TypeError, AttributeError):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass

    return app


# dotenv is loaded by bot.py before uvicorn imports this module in normal startup.
app = create_app()
