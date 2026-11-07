# Lane 4 checkpoint

Branch: `lane/voice`. Scope: bridge milestone. All edits remain inside `voice/`.

Implemented: signed provider routes, metadata-only forwarding, shared-schema HTTP
client, one-use probe grants, Pipecat TTS probe (ElevenLabs default/Magpie option),
locked dependencies, configuration preflight, and offline tests against the
existing MOCK brain. The probe has no ASR or conversation behavior.

Live bridge status: **TTS verified; SIP/call test still blocked on configuration**.
No credential values or phone numbers were present during the initial checks;
the user subsequently supplied a `.env` at the outer workspace root. See the
latest checkpoint below. This is not evidence that Photon SIP failed. No
fallback was selected and no call was placed. Do not report the voice lane or
bridge as working end to end yet.

Checks run on 2026-11-07:

- From `voice/`, `.venv/Scripts/python.exe -m pytest -q -o faulthandler_timeout=20`:
  `18 passed, 1 warning in 8.65s`. The warning is an upstream deprecated Pipecat
  class imported by its TTS module. No checks were skipped or weakened.
- `.venv/Scripts/python.exe smoke.py --offline`: both factories constructed;
  `OFFLINE PASS: shared fixtures valid; pipecat-ai=1.15.0`.
- `.venv/Scripts/python.exe smoke.py --live`: exit 1, `LIVE BLOCKED` with missing
  configuration names. No provider calls made.
- From root, `python scripts/validate_contracts.py`:
  `PASS 56 fixtures/events valid`.
- `git diff --check`: no output (new files remain untracked); a separate Python
  scan of voice source files printed `PASS voice source whitespace`.

Tests requiring Windows asyncio ran outside the restricted network sandbox after
faulthandler showed its loopback socket-pair blocked inside it. This did not
change test behavior. All started test processes were stopped or completed.

Not verified: Photon/Twilio account setup or SIP transport, live phone audio,
listener-perceived first-word latency, real TTS credentials/voices, Magpie cloud
synthesis, signed callbacks from an actual provider, or external availability
on venue Wi-Fi. `gitleaks` is not installed; no secrets scan/hook was claimed.
ASR, LLM conversation, internal outbound calls, transcripts, and approvals are
later milestones and have not been implemented or tested here.

```text
QUESTION FOR LANE 1
Lane / issue / branch: 4 voice / #32 / lane/voice
Blocked on: Live Photon bridge test needs the teammate line, SIP configuration, and local credentials.
Context: voice/ now has a signed bridge probe, metadata-only forwarding, .env.example, smoke checks, and setup instructions; live verification cannot run yet.
What the docs say: docs/handoff/lane-4-voice.md, Build order 1: prove Photon SIP by T+2; Stop and ask: decide the Twilio fallback together if the bridge fails. D-023: teammates' numbers only.
Options: A) Provision the existing Photon Spectrum line, Twilio SIP Domain, selected TTS credentials, and teammate allowlist locally, then run the bridge test. B) If the T+2 deadline has expired, approve and coordinate testing with an existing Twilio number while Photon keeps texting.
My recommendation: A while the bridge window remains open; B requires Lane 1's decision at the cutoff. Missing credentials alone does not establish bridge failure.
Can I keep working meanwhile? yes: offline bridge protocol, contract, audio framing, and MOCK-brain integration checks; no live call or provider switch.
```

Next milestone after bridge verification: Nemotron ASR/Nano conversation, then
`POST /internal/call`, case transcript lines, and one spoken approval per pending
action. Preserve the brain's 409 protections and do not claim facts or actions
that the brain did not provide.

## Live configuration checkpoint, 2026-11-07

- Loaded the user's outer-workspace `.env` explicitly, without moving or editing
  it. The configured bridge fields pass `Settings.missing(...)` through the
  application's dotenv parser. `VOICE_BRIDGE_PROBE_ENABLED` is false.
- Started the existing MOCK brain on localhost:8000 with `VOICE_URL` and
  `MESSAGING_URL` removed from that process, so it cannot dispatch outbound calls
  or messages. Brain `/health`: HTTP 200, `ok: true`, `mock: true`.
- Started voice on localhost:8100 using the outer-workspace dotenv file.
  Local and configured public `/health`: HTTP 200, Titan bridge identity confirmed.
- Exact reproducible preflight command from `voice/`:
  `.venv/Scripts/python.exe -m dotenv -f ../../.env run -- .venv/Scripts/python.exe smoke.py --live`.
  Result before the voice-ID correction: `LIVE: brain health OK`, then
  `SMOKE FAILED: HTTPStatusError`. Direct lookup identified HTTP 400,
  `voice_not_found`; the key's voice-list request returned HTTP 200.
- After the user supplied an updated ID, lookup still returned `voice_not_found`.
  Comparing with the account's voice list found one near-match: Amanda's ID is
  `tKBQrlxp4oMJNdRuKqwM`. A sanitized Python diagnostic used
  `dataclasses.replace(Settings.from_env(), elevenlabs_voice=...)` in memory and
  called the existing `discover_voice()` and `synthesize()` functions. Output:
  `LIVE: selected TTS voice returned by provider discovery` and
  `LIVE TTS PASS: 69690 PCM bytes synthesized with the verified Amanda voice; no file saved or call placed`.
  The source `.env` was not edited. Update the field and restart voice before
  attempting the probe; the running process still has the earlier ID.
- Read-only Twilio account lookup: HTTP 200, account active. Configured number
  lookup returned no owned number and no verified caller ID. Account listing
  returned zero voice-capable owned numbers and zero SIP Domains. No Twilio
  account resource was created or changed.
- Photon project identifier indicates Beta 2.0, while the handoff references
  Spectrum Stable. No Photon credentials were sent to either API and no provider
  routing was changed. Coordinate the actual SIP configuration with Lane 1.
- `NVIDIA_API_KEY` remains absent; this does not block the ElevenLabs bridge
  greeting, but it is required for the later Nemotron ASR/Nano conversation.

Services were left running for continued setup: MOCK brain PID 57744 and voice
PID 49252. Stop the voice process before starting a replacement; finish any call
before restarting. These PIDs identify only processes started in this checkpoint.

Still unverified: Photon-to-Twilio SIP delivery, the real phone greeting, signed
provider callbacks, first-word latency at the phone, forwarding to the teammate,
and the later ASR/conversation/approval milestones.

```text
QUESTION FOR LANE 1
Lane / issue / branch: 4 voice / #32 / lane/voice
Blocked on: Which voice-capable Photon line and Twilio SIP account should this bridge use?
Context: Public voice health and real ElevenLabs synthesis pass. The provided Photon project is Beta 2.0; the provided Twilio account has no SIP Domains, owned voice-capable numbers, or matching verified caller ID.
What the docs say: D-017 specifies Spectrum; docs/handoff/lane-4-voice.md Build order 1 requires Photon SIP → Twilio SIP Domain → Pipecat and coordinated Twilio fallback at T+2 if it fails. Outbound calls remain teammate-only (D-023).
Options: A) Confirm the team's Photon Beta 2.0 SIP route and suitable existing Twilio account/line for the primary bridge. B) At the cutoff, coordinate the documented Twilio-number fallback using a suitable existing account/number.
My recommendation: A if the team already has a voice-capable Photon line; confirm routing/account ownership before changing shared provider settings. Do not infer SIP failure from missing setup or purchase a new number as part of this check.
Can I keep working meanwhile? yes: TTS validation and local/public service readiness; the live call needs the actual SIP routing and valid caller ID.
```
