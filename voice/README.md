# Titan voice

Lane 4 owns `voice/`. The service implements signed Twilio webhooks, metadata-only forwarding, a TTS bridge probe and local `POST /internal/call`. Titan's conversation uses Pipecat 1.15, Nemotron streaming ASR, Nemotron 3.5 Lightning (D-035), NVIDIA Safety Guard and ElevenLabs Flash v2.5. Magpie is the configured TTS fallback. English, Windows, no GPU, teammate numbers only.

**Live intervention approvals are blocked pending a brain fix.** The current brain feeds incoming transcript audit lines into its recovery reply interpreter. One spoken YES could approve an unheard or additional step. See `STATUS.md`. Do not enable brain dispatch or run the real outbound example until Lane 1 fixes this boundary. The TTS-only bridge probe can still be tested.

## Install and configure

From the repository root in PowerShell:

```powershell
Set-Location voice
uv sync --locked --cache-dir .cache/uv
Copy-Item .env.example .env  # first setup only; preserve an existing .env
.venv/Scripts/python.exe -m pytest -q -o faulthandler_timeout=25
.venv/Scripts/python.exe smoke.py --offline
```

Use `voice/.env` (D-041), which is ignored by git. `bot.py` loads it regardless of launch directory; process environment variables take precedence. Keep keys and numbers out of chat, logs and commits. Use python-dotenv: `uv --env-file` can reject an unquoted allowlist with spaces.

- `BRAIN_URL`: local brain, normally `http://localhost:8000`.
- `VOICE_PUBLIC_URL`: exact HTTPS origin of a tunnel to 8100, without a path. Cloudflare and ngrok both work. This is your service's public address for Twilio callbacks and its `wss://.../ws/bridge` audio stream.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`: the account owning the trial number.
- `TWILIO_PHONE_NUMBER`: an owned, voice-capable number in that account.
- `MAYA_PHONE_NUMBER`, `OUTBOUND_ALLOWLIST`: E.164 teammate numbers. Include Maya and the simulated caller in the comma-separated allowlist.
- `HASH_SALT`: locally generated random secret for HMAC hashes.
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`: TTS access and an accessible voice; Voices read permission supports discovery. This service uses the TTS WebSocket API, never ElevenLabs Agents.
- `NVIDIA_API_KEY`: ASR, Lightning and Safety Guard access.
- `VOICE_LLM_BASE_URL=https://integrate.api.nvidia.com/v1` and `NEMOTRON_VOICE_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b` (D-035). Raw HTTP requests include `chat_template_kwargs: {enable_thinking: false}`.
- For `TTS_PROVIDER=magpie`, select `MAGPIE_VOICE_ID` from the actual `GetRivaSynthesisConfig` response. Default TTS is ElevenLabs.

Photon credentials are listed for separately coordinated Photon 2.0 SIP setup (D-040); this Python service does not manage Photon routing or purchase resources.

## Bridge probe: Twilio first (D-030/D-046)

1. Start the MOCK brain using the repository command. For provider-only checks, leave `VOICE_URL` and `MESSAGING_URL` unset in that brain process.
2. Run a tunnel to 8100. For example, `cloudflared tunnel --url http://localhost:8100` prints an HTTPS origin. Put that current origin in `voice/.env`; Quick Tunnel hostnames change after a tunnel restart.
3. Set `VOICE_BRIDGE_PROBE_ENABLED=true`. Run `.venv/Scripts/python.exe smoke.py --live`: voice discovery and real Pipecat TTS synthesis in memory, without a phone call or saved audio.
4. Start `.venv/Scripts/python.exe bot.py`. GET local and public `/health`; expect the Titan bridge identity and `probe_enabled: true`. Health proves liveness/configuration only. `intervention_ready: false` is deliberate.
5. Twilio Console -> owned trial number -> **A call comes in** -> Webhook `<VOICE_PUBLIC_URL>/webhooks/twilio/bridge-probe`, POST. Save. Do not add `/twilio/voice` or curl-POST the signed probe.
6. Call the trial number from an allowlisted, trial-verified teammate phone. Expect: “Hello. This is the Titan voice bridge test. I will never ask you for a PIN or a code.” It drains the greeting and hangs up; it does not listen or transcribe.
7. Report the actual result to Lane 1. Greeting = stream works on trial. A trial restriction or Twilio error needs its error code; Yuvan decides on upgrades. Missing account setup does not establish a trial restriction.

Coordinate the Photon attempt separately with its owner: existing Photon SIP route -> Twilio SIP Domain, TLS 5061, G.711. Do not purchase a number or upgrade the account. Photon can keep texting while Twilio handles voice.

## Metadata-only forwarding

After the probe, use `<VOICE_PUBLIC_URL>/webhooks/twilio/inbound`, POST, on the chosen number/SIP Domain and disable the probe. It returns `<Dial record="do-not-record">` to the allowlisted Maya phone, with no Stream, Gather or Record. The forwarded scam call never enters an ASR/model pipeline.

Signed child-call callbacks at `/webhooks/twilio/forward-status` emit `call.started` on answer and `call.ended` on completion with the same HMAC-based call ID. Duplicate/out-of-order callbacks are absorbed. Brain delivery failures return 503 for retry. Unanswered calls do not open active call windows.

Check brain `GET /users/usr_maya/timeline` and `GET /protections/usr_maya`: answer enables shield mode; completion clears it. Caller name, attestation, seen-before and scam label are configured **simulated carrier metadata**, never inferred from audio.

## Intervention implementation

`POST /internal/call` accepts the shared-schema `CallRequest` only from the local brain. Public tunnel/proxy requests are denied. It resolves `usr_maya` to the allowlisted teammate, checks case ownership and pending actions, then returns 202 for accepted background work. Identical requests dedupe for ten minutes in memory. Delivery failures go to the case; 202 does not claim the phone answered.

Before dialing, it verifies Lightning and hosted ASR and guards the opening script. Twilio receives a non-recording call with a short-lived, one-use, call-bound stream grant. Titan's own call does not emit carrier `call.started` events or replace the suspicious call window.

Replies become bounded NVIDIA intents; model prose cannot reach TTS or invoke actions. Spoken text uses brain-provided opening/facts and fixed action labels, checked by local policy and Safety Guard. Volunteered digits are redacted before context/model/case delivery. Incoming and actually emitted outgoing transcript lines use the brain HTTP API. Queued or interrupted questions cannot arm approval. A strict YES/NO after a complete question selects one explicit action endpoint. Brain 409 preserves the hold and asks her to hang up first. **This local gating still requires the brain fix described above.**

The brain owns recovery planning, summary, watch and texting. D-042 makes it text the next recovery step after a voice/web/text decision. Voice does not invent a sent text or completed protection.

```powershell
.venv/Scripts/python.exe smoke.py --conversation
```

This provider check synthesizes a known help request in memory, recognizes it with hosted ASR, validates Lightning's intent, guards a bounded response and synthesizes its reply. It stores no audio, places no call and proves no phone latency.

After Lane 1 fixes the transcript/reply boundary, run `.venv/Scripts/python.exe scripts/check_brain_approval_boundary.py` against the current checkout before enabling real dispatch. It must pass both transcript and customer.reply cases. Then the fixture can exercise the endpoint against a matching existing case:

```powershell
$body = Get-Content ../contracts/fixtures/callreq.t2.json -Raw
Invoke-WebRequest http://localhost:8100/internal/call -Method Post -ContentType application/json -Body $body
```

Case and pending action IDs must exist in that brain; the fixture does not create them. This command places a real teammate call.

## Diagnostics and limits

Provider routes require Twilio signatures and the configured account. Stream grants also check the call ID and audio format. JSON logs contain stages, timing and sanitized error types. No raw numbers, tokens, signed URLs, text bodies or audio are logged. Upstream Pipecat logs are suppressed because they can contain text or provider responses.

`bridge.first_audio_sent` and `voice.first_audio_sent` measure app-observed transport output, not listener-perceived latency. First words under two seconds remains unmeasured on a phone. Magpie cloud synthesis and Photon SIP remain unverified. A successful provider check is not a phone exchange.

Ctrl-C stops voice. Finish calls before restarting: dedupe/call/grant state is in memory. Unknown callbacks after restart return 409. Keep the tunnel and provider webhook origin synchronized. Startup makes no provider calls.

### Shared trial console (D-048)

The new shared trial number may not appear under IncomingPhoneNumbers in the API. Use One Console -> Voice -> Try out Voice -> Receive a call -> Custom to configure its webhook. The signed probe URL was saved successfully through that console. Zero owned-number API results alone do not mean no trial number exists. Keep the tunnel running and perform the incoming teammate test; only the audible result or an actual Twilio error establishes whether streaming works on trial.
