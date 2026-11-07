# Titan voice: bridge milestone

Lane 4 owns this folder only. This milestone provides a **bridge probe** and
metadata-only call forwarding against the existing brain HTTP API. It does not yet
provide the intervention conversation, `POST /internal/call`, ASR, Nano turns,
transcript delivery, or spoken approvals. `/health` explicitly reports
`intervention_ready: false`. A local test passing is not a successful live call.

Choices: Python 3.11–3.13 on Windows, Pipecat 1.15.0, Twilio Media Streams
WebSocket transport on port 8100, hosted ElevenLabs Flash v2.5 TTS by default,
hosted NVIDIA Magpie multilingual selected with `TTS_PROVIDER=magpie`. English
probe greeting, one demo call at a time, no GPU or additional voice platform.
The later conversation pipeline remains Nemotron streaming ASR → Nemotron Nano →
the selected TTS. No other LLM provider is used here.

## Install and check locally

From the repository root in PowerShell:

```powershell
Set-Location voice
uv sync --locked --cache-dir .cache/uv
uv run --locked python -m pytest -q
uv run --locked python smoke.py --offline
Copy-Item .env.example .env
```

Fill in `.env` locally; never put keys or phone numbers in chat or git. Process
environment variables override `.env`. `bot.py` loads this folder's `.env` even
when launched elsewhere. Do not copy `agent/.env` into the voice directory.

If your configured file is at the outer workspace root (`HackUTD2026/.env`),
keep it there and run these commands from `voice/` after installing dependencies:

```powershell
.venv/Scripts/python.exe -m dotenv -f ../../.env run -- .venv/Scripts/python.exe smoke.py --live
.venv/Scripts/python.exe -m dotenv -f ../../.env run -- .venv/Scripts/python.exe bot.py
```

Use the application's `python-dotenv` parser for this file. In the current setup,
`uv --env-file` rejected an unquoted allowlist containing spaces. Neither command
above prints configuration values, and the preflight does not place a call.

- `VOICE_PUBLIC_URL`: exact public HTTPS origin from an ngrok tunnel to 8100.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`: account serving the SIP Domain.
- `TWILIO_PHONE_NUMBER`: owned/verified Twilio caller ID for forwarding.
- `MAYA_PHONE_NUMBER`: teammate receiving forwarded calls.
- `OUTBOUND_ALLOWLIST`: E.164 teammate numbers, including Maya and the test caller.
- `HASH_SALT`: local random secret; changing it changes call/number hashes.
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`: chosen voice accessible to the key.
- For `TTS_PROVIDER=magpie`, use `NVIDIA_API_KEY` and a `MAGPIE_VOICE_ID` returned
  by the running service's `GetRivaSynthesisConfig`. No voice is guessed.

`PHOTON_PROJECT_ID` and `PHOTON_SECRET_KEY` are documented for the manual Spectrum
SIP setup; this milestone does not call a Photon REST API or manage its account.

## T+2 bridge test: Photon first

The implemented route follows **Photon Spectrum Stable** (`spectrum-ts`, project
ID/secret), matching D-017. If the actual project is Photon 2.0 (`pho_prj_` / bearer
key), stop and ask Lane 1 before mixing protocols or credential types.

1. Start the brain in MOCK mode using its documented command. Then run
   `ngrok http 8100`, set the resulting HTTPS origin in `VOICE_PUBLIC_URL`, and
   set `VOICE_BRIDGE_PROBE_ENABLED=true` in `voice/.env`.
2. Run `uv run --locked python smoke.py --live`. This checks configuration,
   brain liveness, provider voice discovery, and actual synthesis through the same
   Pipecat TTS factory. It creates no phone call and stores no audio. It must pass
   before trying the phone. No ASR/LLM checks apply to this TTS-only bridge probe.
3. Start `uv run --locked python bot.py`. Health is at
   `http://localhost:8100/health`. The root `scripts/dev.sh` also launches this
   entry point via `requirements.txt`; the locked setup above is preferred.
4. In the Twilio Console, create/select a Programmable Voice **SIP Domain**. Add
   an authentication credential list. Set its Voice URL, method POST, to
   `VOICE_PUBLIC_URL/webhooks/twilio/bridge-probe`.
5. In the Spectrum dashboard, register the iMessage line's inbound SIP route to
   `sips:agent@YOUR_DOMAIN.sip.twilio.com:5061`. Use the Twilio SIP Domain's
   username/password for this inbound route. Use TLS, G.711 PCMU/PCMA, and the
   domain hostname rather than an IP. Secure Media/SRTP is a separate setting:
   enable it only after both ends negotiate it; TLS signaling alone does not
   prove encrypted media. Do not buy a new service or number for this test.
6. Call the Photon line **from an allowlisted teammate phone**. Hear:
   “Hello. This is the Titan voice bridge test. I will never ask you for a PIN or
   a code.” The probe drains the audio and ends the call. It intentionally does
   not listen, transcribe, or conduct a conversation.
7. Capture the actual result, caller-ID line, audio quality, and measured delay
   from connection to first words. JSON event `bridge.first_audio_sent` measures
   application-observed output timing, not what a listener hears. There is no
   measured live latency yet. The goal is first words under two seconds.

**At T+2:** if the bridge fails, stop and send the question in `STATUS.md` to
Yuvan/Lane 1. Coordinate the documented Twilio-number fallback; do not silently
switch providers. The fallback uses an existing Twilio number's Voice URL with
the same probe endpoint. Photon continues texting. This implementation has not
selected or exercised that fallback.

## Forward the simulated scam call, with metadata only

After the bridge test, change the SIP Domain's Voice URL to
`VOICE_PUBLIC_URL/webhooks/twilio/inbound`, POST. Disable the probe. The inbound
route returns `<Dial record="do-not-record">` to the configured allowlisted Maya
number. It never returns `<Stream>`, `<Gather>`, or `<Record>`. The original
caller's raw number is discarded after creating a salted HMAC hash.

Twilio's child-call status callback sends `answered`/`completed` to
`/webhooks/twilio/forward-status`; the answered callback's `CallStatus` is
`in-progress`. This emits contract-valid `call.started` and `call.ended` for
`usr_maya` with the same `call_id`. Ringing and unanswered calls do not create
active call windows. Stable event IDs support brain idempotency and failed
deliveries return 503 for retry. Completion before the answered callback sends
start then end; a late answered callback cannot reopen the window.

```powershell
Invoke-RestMethod http://localhost:8000/users/usr_maya/timeline
Invoke-RestMethod http://localhost:8000/protections/usr_maya
```

While connected, expect `active_call` and `shield_mode: true`; after hanging up,
expect no active call and `shield_mode: false`. Caller name, attestation, seen
before, and scam label come from `.env`. Tell judges these are **simulated carrier
signals**. Only the teammate numbers are real; account data remains synthetic.

The forwarded call and probe are deliberately separate provider routes. Never
point a scam-forwarding call at the probe. The probe accepts a signed Twilio
handshake plus a short-lived, one-use, call-bound token obtained through signed
TwiML; caller allowlisting happens before any grant. No audio enters ASR/models.

## Diagnostics and stopping

The service starts without keys so other lanes can run. Unconfigured webhooks
return 503 with missing variable names; they never claim a call was delivered.
There are no provider calls during startup. Webhooks always require Twilio
signatures and the configured account. The public origin is taken from config,
not untrusted forwarded headers. Keep the tunnel current after restarting ngrok.

Logs are JSON on stdout: `voice.started`, `carrier.call_started`,
`carrier.call_ended`, `brain.delivery_failed`, `bridge.pipeline_started`,
`bridge.first_audio_sent`, `bridge.service_latency`, `bridge.provider_error`,
`bridge.failed`, `bridge.session_finished`. No phone numbers, transcripts,
credential values, raw audio, provider response bodies, or signed URLs are logged.
Upstream Pipecat logging is suppressed because its debug/error messages may
contain text. Errors retain stack locations/types and sanitized categories.
There is no transcript/debug switch for this milestone. Use private provider
diagnostics to inspect authentication, SIP, or media errors.

Ctrl-C stops `bot.py`; stop the separate ngrok and brain processes in their own
terminals. Finish calls before restarting voice: call/grant state is in memory.
Unknown callbacks after a restart return 409 rather than inventing history. For
the demo, hang up and reset the MOCK brain before rehearsing again.

For silent audio, verify `/health`, run live smoke, inspect Twilio SIP errors,
confirm Photon line routing, then check G.711 and Media Streams WebSocket access.
Do not spend more than 30 minutes on one problem. See the repository skill's
`references/operations/troubleshoot.md` for the first failed speech stage.

## References used

- [Photon Spectrum inbound SIP](https://photon.codes/docs/spectrum-ts/providers/voice/inbound-calls)
- [Photon Spectrum outbound SIP](https://photon.codes/docs/spectrum-ts/providers/voice/outbound-calls)
- [Twilio SIP interface](https://www.twilio.com/docs/voice/api/sip-interface)
- [Twilio forwarding callbacks](https://www.twilio.com/docs/voice/twiml/number)
- [Twilio signature validation](https://www.twilio.com/docs/usage/security)
- [Pipecat Twilio transport](https://docs.pipecat.ai/pipecat/telephony/twilio-websockets)
- [Pipecat ElevenLabs TTS](https://docs.pipecat.ai/api-reference/server/services/tts/elevenlabs)
- [Pipecat NVIDIA TTS](https://docs.pipecat.ai/api-reference/server/services/tts/nvidia)
- [ElevenLabs voice discovery](https://elevenlabs.io/docs/api-reference/voices/get)

The user approved the official `docs.pipecat.ai/llms.txt` fallback because the
Pipecat docs MCP is unavailable. Dependency versions were resolved from PyPI;
`uv.lock` records the exact transitive versions. No provider account setup or
spoken exchange has been verified in this checkout.
