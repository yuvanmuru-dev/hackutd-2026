# D-050 current route: Photon + LiveKit SIP

The active route is **Photon line -> LiveKit outbound SIP trunk -> isolated LiveKit room -> Pipecat bot**. No Twilio account, Twilio Media Streams, forwarding or public tunnel is required for this route. The older bridge notes below are retained for the Lane 1-approved fallback only.

Current live result: after Photon support supplied the new endpoint, voice-enabled caller ID and generated SIP credentials, the single authorized greeting-only probe completed without SIP error. The teammate confirmed both ringing and the audible Titan bridge-test greeting on the second authorized probe. Earlier shared-line/project-API-key attempts returned SIP 503; those settings are obsolete.

## Route 3 configuration

Use only ignored `voice/.env`; `.env.example` contains the names and defaults:

- `VOICE_TRANSPORT=livekit`
- `LIVEKIT_URL` (WSS origin), `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `LIVEKIT_SIP_OUTBOUND_TRUNK_ID` (provisioning saves the generated ID)
- `PHOTON_SIP_USERNAME`, `PHOTON_SIP_PASSWORD` (separately generated under the voice Default profile; select SHA-256 and Enable outbound)
- `PHOTON_PROJECT_ID`, `PHOTON_SECRET_KEY` remain project API credentials and are never used as SIP authentication.
- `PHOTON_PHONE_NUMBER` (that project's owned iMessage line in E.164)
- `MAYA_PHONE_NUMBER`, `OUTBOUND_ALLOWLIST`, `HASH_SALT`
- Existing NVIDIA/ElevenLabs settings and D-035 Lightning model settings.
- `VOICE_CONVERSATION_ENABLED=false` until the brain approval-boundary gate passes.

Install with `uv sync --locked --cache-dir .cache/uv`. The lock now includes the Pipecat LiveKit extra. The application remains Pipecat; LiveKit supplies room transport and SIP, not inference or another agent framework.

From `voice/`:

```powershell
.venv/Scripts/python.exe livekit_setup.py --provision
.venv/Scripts/python.exe livekit_setup.py --check
.venv/Scripts/python.exe livekit_setup.py --probe
```

`--provision` updates the explicitly configured trunk in place with `sip.photon.codes:5061`, TLS, the voice-enabled caller ID and dedicated outbound SIP username/password. Without a configured ID it creates/reuses a matching trunk and saves its ID locally. It never substitutes the Photon project API key; known API-key values are rejected. It does not buy a number or enable a Photon profile. Enable outbound on the Default profile with SHA-256 selected first; inbound can remain disabled. Registration is not used. Keep certificate verification enabled.

**`--probe` places one real call to Maya's configured allowlisted number.** It joins the bot first, waits for the SIP participant to answer, speaks the labeled bridge greeting and ends. It does not transcribe incoming audio or approve anything. Confirm the audible result with the teammate before reporting success. Check the actual project allowances; LiveKit's pricing page currently lists 1,000 Build-plan third-party SIP minutes, distinct from its 50 included US local inbound minutes. Photon usage is separate. Keep probes short.

## Route 3 lifecycle and safety

The same contract `POST /internal/call` validates case ownership, dedupes identical work and starts the guarded conversation in a background task. The LiveKit provider checks the configured trunk endpoint/TLS/line, creates a random two-participant room, and gives the bot a room-scoped, five-minute token. Only after the bot connects does it call `CreateSIPParticipant` with Maya's allowlisted destination and Photon caller ID. Greeting waits for `wait_until_answered` to complete. Ring timeout is 30 seconds; call duration is capped at three minutes. A bot failure during dialing cancels the request and deletes the room; normal completion, failures and cancellation all clean up the room and client.

Transcript and approval HTTP calls remain unchanged. Nemotron ASR -> Lightning intent interpretation (thinking disabled) -> guarded ElevenLabs Flash output remains the conversation pipeline. No recording is enabled. The local worker shares the same redaction, interruption and one-question approval controls across transports.

**D-054 approval fix is verified:** after PR #60 merged, `.venv/Scripts/python.exe scripts/check_brain_approval_boundary.py` passes both transcript and customer.reply cases. Audit text cannot approve; one explicit voice decision advances one recovery question. `VOICE_CONVERSATION_ENABLED=false` still interlocks dispatch with HTTP 503 while Photon SIP 503 is investigated, preventing automatic retries. Enable it only when the provider is ready for a coordinated call test. The greeting probe does not use approval paths.

For the scam beat, use the console's simulated carrier `call.started` event while the scammer calls Maya's actual phone (D-050); no forwarding or scam audio collection is needed. Optional Photon inbound SIP/LiveKit dispatch is not implemented in this milestone.

Runtime: `.venv/Scripts/python.exe bot.py`, localhost:8100. LiveKit outbound rooms use outbound WSS/WebRTC; no cloudflared restart is required. Health retains the existing bridge identity for compatibility and does not claim phone readiness. Legacy signed Twilio code remains available only as a fallback; the legacy probe is disabled in the current environment.

References: [Pipecat LiveKit transport](https://docs.pipecat.ai/api-reference/server/services/transport/livekit), [LiveKit SIP API](https://docs.livekit.io/reference/telephony/sip-api/), [Photon outbound SIP](https://photon.codes/docs/spectrum-ts/providers/voice/outbound-calls), [LiveKit SIP troubleshooting](https://docs.livekit.io/reference/telephony/troubleshooting/), [LiveKit pricing](https://livekit.com/pricing).

---

## Historical Twilio bridge notes (superseded by D-050)

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

### Conversation response timing

`voice.response_delay` reports the elapsed time from VAD-estimated incoming speech end to the next transport audio-start event. It subtracts the VAD silence window; it does not measure handset/network playback. The live approval test is still in progress: the long prompt tail caused natural YES replies to interrupt the completion gate. Approval questions now end at the natural question mark; complete-question and interruption safeguards remain enforced. Keep conversation dispatch disabled until the corrected phone test passes.


### Noise and interruptions

Turn starts now require recognized speech rather than VAD activity alone. While Titan is speaking, at least two transcribed words are required to interrupt (for example, "please stop"); a cough, clatter or isolated backchannel does not cut off the question. Once playback ends, a single "yes" or "no" is accepted. Silero uses confidence 0.8, a 250 ms start window and a 300 ms stop window; turn end allows 800 ms for the caller to continue after a pause.

An interrupted approval question is not actionable. Titan repeats the current pending question, and a later explicit answer can approve only that fully spoken step. Completed actions are not repeated. No microphone recordings, speaker identification or new provider is added. Background speech/TV can still be recognized as words; these settings are noise tolerance, not speaker authentication. Test handset volume and representative venue noise before relying on the live demo.


### SIP rejection diagnostics

LiveKit SDK server failures now include `provider_code`, `provider_http_status`, `provider_message` and `provider_metadata` in `intervention.setup_failed`; provisioning CLI failures use the same sanitizer. Reason phrases and support call IDs remain readable. Configured credentials, signed URLs, SIP URIs, phone numbers and sensitive metadata fields are redacted, and nested payloads are bounded. Non-LiveKit/model/customer exceptions do not expose their message. Do not log `str(error)` or raw SIP headers. This logging cannot reconstruct messages discarded by older processes; inspect Telephony -> Calls -> Events for historical rejections. Reading logs never requires another call.


### D-063 contextual Nemotron turns

The voice agent now sends verified CallRequest facts, the current pending action label, up to eight redacted user/assistant messages (four exchanges), and the current utterance to Nemotron. It requires strict JSON intent/reply output. Exact YES/NO stays a fast path; natural agreement is interpreted by Nemotron. Only the fully spoken current action can be decided, and only safer recovery kinds can be approved. Questions receive a short generated response plus the current question; unclear input gets one confirmation question. Model failures use guarded templates. Generated text must pass speech_policy, the unchanged NVIDIA Safety Guard protocol, and a separate Nemotron check against verified facts. If moderation is unavailable for templates too, the pipeline fails closed rather than speaking unchecked text. Action acknowledgements always reflect the brain result, never a model claim.

Optional NEMOTRON_NANO_BASE_URL / NEMOTRON_NANO_SELF_MODEL / NEMOTRON_NANO_SELF_KEY configure the approved Brev nano role. VOICE_LLM_BASE_URL remains supported; hosted NVIDIA Lightning is the automatic fallback for a custom primary. Requests disable thinking, request JSON output, bound context/reply sizes and set a Brev-compatible User-Agent. No local voice service or test call is needed for the offline suite. Production remains on Yuvan's laptop; one coordinated phone test is still required.
