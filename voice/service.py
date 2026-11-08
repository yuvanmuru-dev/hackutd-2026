"""Signed provider webhooks. The forwarded scam call never has a media stream."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
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

from brain import Brain, validate
from config import Settings, phone
from diagnostics import provider_diagnostics
from conversation import Conversation
from models import NvidiaModels, speech_policy, spoken_fact, verify_asr
from telephony import TwilioCalls
from jsonschema import ValidationError

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


@dataclass
class Intervention:
    conversation: Conversation
    created: float
    sid: str | None = None
    connected: bool = False
    finished: bool = False
    plan: object | None = None
    status: str = "preparing"
    expires: float = 0
    audited_statuses: set[str] = field(default_factory=set)


def create_app(settings: Settings | None = None, brain: Brain | None = None, probe_runner=None,
               call_provider=None, model_provider=None, asr_check=None, conversation_runner=None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(base_url=settings.brain_url, timeout=20) as client:
            app.state.brain = brain or Brain(client)
            app.state.models = model_provider or NvidiaModels(client, settings)
            if settings.voice_transport == "livekit":
                from livekit_calls import LiveKitCalls
                app.state.calls = call_provider or LiveKitCalls(settings)
            else:
                app.state.calls = call_provider or TwilioCalls(client, settings)
            app.state.tasks = set()
            emit("voice.started", port=8100, milestone="bridge", intervention_ready=False)
            try:
                yield
            finally:
                for task in list(app.state.tasks):
                    task.cancel()
                await asyncio.gather(*app.state.tasks, return_exceptions=True)

    app = FastAPI(title="Titan voice bridge", lifespan=lifespan)
    app.state.settings = settings
    calls: dict[str, ForwardedCall] = {}
    grants: dict[str, tuple[str, float]] = {}
    interventions: dict[str, Intervention] = {}
    fingerprints: dict[str, str] = {}
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
            emit("provider.signature_rejected", path=request.url.path,
                 signature_present=bool(request.headers.get("x-twilio-signature")),
                 account_matches=form.get("AccountSid") == settings.account_sid)
            raise HTTPException(401, "Invalid provider signature")
        if form.get("AccountSid") != settings.account_sid:
            emit("provider.account_rejected", path=request.url.path)
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
        for fingerprint, token in list(fingerprints.items()):
            entry = interventions[token]
            if now - entry.created > 600 and (entry.finished or not entry.connected):
                del fingerprints[fingerprint]
                del interventions[token]

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
                "probe_configuration_required": settings.missing(speech=True),
                "intervention_api": "implemented",
                "intervention_configuration_required": settings.conversation_missing()}

    async def place_intervention(entry: Intervention, token: str) -> None:
        cid = entry.conversation.request["case_id"]
        try:
            await app.state.models.verify()
            await (asr_check or verify_asr)(settings)
            entry.plan = await entry.conversation.begin()
            if settings.voice_transport == "livekit":
                await app.state.brain.delivery(cid, "Titan voice room preparing; the Photon call is not yet confirmed.")
                await app.state.calls.run(entry.conversation.request["user_id"], entry.conversation, entry.plan)
                entry.finished = True
                entry.status = "completed"
                await app.state.brain.delivery(cid, "Titan voice session ended; see case transcripts for delivered speech.")
                return
            entry.expires = time.monotonic() + 120
            sid = await app.state.calls.place(entry.conversation.request["user_id"], token)
            async with lock:
                if entry.sid and entry.sid != sid:
                    raise ValueError("Provider call ID mismatch")
                entry.sid = sid
                if not entry.finished and not entry.connected:
                    entry.status = "queued"
            await app.state.brain.delivery(cid, "Titan voice call placed; waiting for the phone to answer.")
            emit("intervention.placed", case_id=cid)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            entry.finished = True
            entry.status = "failed"
            status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
            emit("intervention.setup_failed", case_id=cid, exception_type=type(error).__name__, http_status=status,
                 **provider_diagnostics(error, settings))
            try:
                await app.state.brain.delivery(cid, "Titan voice setup failed; no successful conversation was confirmed.")
            except Exception:
                emit("intervention.delivery_audit_failed", case_id=cid)

    @app.post("/internal/call", status_code=202)
    async def internal_call(request: Request):
        # This is a same-laptop brain endpoint. Tunnel/proxy callers are rejected
        # even if the local tunnel agent connects from loopback. No new auth field
        # or header is required by the existing brain contract.
        if (request.client is None or request.client.host not in {"127.0.0.1", "::1"}
                or any(h in request.headers for h in ["cf-ray", "cf-connecting-ip", "x-forwarded-for",
                    "x-forwarded-host", "x-forwarded-proto", "forwarded"])):
            raise HTTPException(403, "Only the local brain may request an outbound call")
        if not settings.conversation_enabled:
            raise HTTPException(503, "Conversation calls are disabled until the brain approval-boundary integration gate passes")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                raise HTTPException(413, "Call request too large")
        try:
            payload = validate("CallRequest", json.loads(body))
            speech_policy(payload["opening_line"])
            payload["facts"] = [spoken_fact(fact) for fact in payload["facts"]]
        except (ValueError, ValidationError):
            raise HTTPException(422, "Invalid or unsafe CallRequest") from None
        if payload["user_id"] != "usr_maya":
            raise HTTPException(404, "No teammate mapping for this user")
        missing = settings.conversation_missing()
        if missing:
            raise HTTPException(503, {"configuration_required": missing})
        controller = Conversation(payload, app.state.brain, app.state.models)
        try:
            detail = await controller.case()
        except (httpx.HTTPError, ValidationError, ValueError):
            raise HTTPException(409, "Case is unavailable or does not belong to the requested user") from None
        pending = {a["action_id"] for a in detail["actions"] if a["status"] == "awaiting_approval"}
        if not set(payload["pending_action_ids"]).issubset(pending):
            raise HTTPException(409, "Pending actions changed; refresh the case")
        fingerprint = digest(json.dumps(payload, sort_keys=True))
        async with lock:
            prune()
            if fingerprint in fingerprints:
                return Response(status_code=202)
            if len(interventions) >= 100:
                raise HTTPException(503, "Intervention capacity reached")
            token = secrets.token_urlsafe(32)
            entry = Intervention(controller, time.monotonic())
            interventions[token] = entry
            fingerprints[fingerprint] = token
            task = asyncio.create_task(place_intervention(entry, token))
            app.state.tasks.add(task)
            task.add_done_callback(app.state.tasks.discard)
        return Response(status_code=202)

    @app.post("/webhooks/twilio/intervention-status")
    async def intervention_status(request: Request):
        form = await signed_form(request)
        token = request.query_params.get("request", "")
        sid, status = form.get("CallSid"), form.get("CallStatus")
        if status not in TERMINAL | {"queued", "initiated", "ringing", "in-progress"} or not sid:
            raise HTTPException(422, "Invalid call status callback")
        async with lock:
            entry = interventions.get(token)
            if entry is None or (entry.sid is not None and entry.sid != sid):
                raise HTTPException(409, "Unknown intervention call")
            if status in entry.audited_statuses or (entry.finished and status not in TERMINAL):
                return Response(status_code=204)
            try:
                await app.state.brain.delivery(entry.conversation.request["case_id"], "Titan voice call status: " + status + ".")
            except httpx.HTTPError:
                raise HTTPException(503, "Brain unavailable for call status") from None
            entry.sid = sid
            entry.status = status
            entry.audited_statuses.add(status)
            if status in TERMINAL:
                entry.finished = True
        return Response(status_code=204)

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
        if ((not settings.probe_enabled and not interventions) or settings.missing(speech=True)
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
                entry = interventions.get(token)
                valid_probe = bool(settings.probe_enabled and grant and grant[0] == data.get("callSid"))
                valid_intervention = bool(entry and entry.plan and not entry.connected and not entry.finished
                    and entry.expires > time.monotonic() and (entry.sid is None or entry.sid == data.get("callSid")))
                if (message.get("event") != "start" or not (valid_probe or valid_intervention)
                        or data.get("accountSid") != settings.account_sid or not data.get("streamSid")
                        or data.get("mediaFormat") != {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1}
                        or data.get("callSid") in calls):
                    await websocket.close(code=1008)
                    return
                if valid_probe:
                    del grants[token]
                else:
                    entry.sid = data["callSid"]
                    entry.connected = True
                    entry.status = "in-progress"
            if valid_probe:
                runner = probe_runner
                if runner is None:
                    from bot import run_probe
                    runner = run_probe
                await runner(websocket, data, settings)
            else:
                runner = conversation_runner
                if runner is None:
                    from bot import run_conversation
                    runner = run_conversation
                try:
                    await runner(websocket, data, settings, entry.conversation, entry.plan)
                finally:
                    entry.finished = True
        except (TimeoutError, ValueError, TypeError, AttributeError):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass

    return app


# dotenv is loaded by bot.py before uvicorn imports this module in normal startup.
app = create_app()
