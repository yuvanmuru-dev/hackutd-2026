# Lane 4 checkpoint

Branch: `lane/voice`. Scope: bridge milestone. All edits remain inside `voice/`.

Implemented: signed provider routes, metadata-only forwarding, shared-schema HTTP
client, one-use probe grants, Pipecat TTS probe (ElevenLabs default/Magpie option),
locked dependencies, configuration preflight, and offline tests against the
existing MOCK brain. The probe has no ASR or conversation behavior.

Live bridge status: **blocked on configuration, not tested**. No credential values
or phone numbers were present in this checkout or process during initial checks.
This is not evidence that Photon SIP failed. No fallback was selected and no call
was placed. Do not report the voice lane or bridge as working end to end yet.

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
