# Lane 4: voice (Photon/Twilio calls, Titan's phone call)

**Owner:** Krishang · Codex · **Branch:** `lane/voice` · **Issue:** #32 · **Label:** `lane:voice`
**You own:** `voice/` only.
**Skills to read:** `.claude/skills/nemotron-voice-agent-builder` (cloud profile), Photon voice docs (SIP), Pipecat docs.

## Your piece of the story
Two jobs. (1) **See the scam call like a carrier would:** the scammer calls our number, it rings through to Maya's phone, and you tell the brain when the call starts and ends (metadata only). (2) **Titan's phone call:** when Maya doesn't answer the alert, Titan calls her as a second incoming call, talks her off the scam call, finds out what she shared, and takes spoken approvals for recovery. The Photon "Voice Call" prize is judged on this.

## What already exists
- Brain `MOCK=1`. With `VOICE_URL=http://localhost:8100` (dev.sh sets it) the brain POSTs `CallRequest` to your `POST /internal/call`. Before you exist, see it at `GET /demo/outbox`.
- Examples: `contracts/fixtures/event.call_started.json`, `callreq.t2.json`, `caseevent.transcript.json`.
- The call script: docs/PLAN.md and the summary in this file.

## Interfaces
| Direction | Endpoint | Type |
|---|---|---|
| you → brain | `POST /events` | `call.started` (`CallData`: direction, other_number_hash, caller_name, attestation, seen_before, scam_label) and `call.ended` (`{duration_s}`), with the same `call_id` |
| brain → you | `POST /internal/call` (port 8100) | `CallRequest {case_id, user_id, purpose, opening_line, facts[], pending_action_ids[]}` |
| you → brain | `POST /cases/{id}/events` | `CaseEventRequest {channel:"voice", direction: out\|in, kind:"transcript", text, agent:"voice"}` for every line |
| you → brain | `GET /cases/{id}` | pending `actions` with `status:"awaiting_approval"` to read out |
| you → brain | `POST /actions/{id}/approve` / `reject` | `{via:"voice"}`; 409 → she's still on the scam call: ask her to hang up first |

For the demo, `attestation`, `seen_before` and `caller_name` of the scammer's number come from config (`voice/.env`: `SCAM_CALLER_NAME="T-Mobile Support"`, `SCAM_ATTESTATION=C`). Say in the pitch that this is the simulated carrier signal.

## The Titan call script (follow it; never ask for a PIN, code or password)
1. "Hi Maya, this is Titan, your account security. I'll never ask you for a PIN or a code. You'll see my text in your Messages from this same number."
2. "The person you're on the phone with isn't T-Mobile. Their number isn't verified. Please hang up on them. I'll stay on the line."
3. "Your number is safe. I turned Port Out Protection back on, and that PIN won't work for 24 hours." (use `facts`)
4. "Did you give them your account PIN, a code we texted you, or the transfer PIN?" → post her answer as a transcript line.
5. Read each pending action, one at a time: "Want me to reset your account PIN?" → yes/no → approve/reject.
6. "You're protected. I'll text you a summary, and I'll watch your account for 24 hours."
Edge: "it was me, I'm switching carriers" while the scam call is still active → don't approve anything looser; ask her to hang up first.

## Build order
1. **Bridge go/no-go by T+2:** Photon line → SIP (TLS 5061, G.711) → Twilio SIP Domain → `<Connect><Stream>` → Pipecat (or LiveKit SIP). If it isn't working by T+2, use a Twilio number for calls and **tell Yuvan** (Photon still does texting). Check: you can call the number and hear the bot.
2. **Call forwarding + events:** inbound call to our number forwards to Maya's phone (teammate); post `call.started`/`call.ended`. Never record or analyze that call. Check: the brain's `GET /users/usr_maya/timeline` shows the call; `GET /protections/usr_maya` shows `shield_mode: true`.
3. **Pipecat bot** (`voice/bot.py`): Nemotron ASR → Nemotron Nano (`VOICE_LLM_BASE_URL`, model from env) → **ElevenLabs TTS Flash** (`TTS_PROVIDER=elevenlabs`, `ELEVENLABS_VOICE_ID`), Magpie fallback. System prompt = the script + `facts`. Check: first words < 2 s.
4. **`POST /internal/call`:** place the outbound call, run the script, post transcript lines, approvals by voice. Check: `curl -X POST localhost:8100/internal/call -H 'content-type: application/json' -d @contracts/fixtures/callreq.t2.json` → your phone rings.
5. Polish: barge-in, short sentences, calm voice; measure latency for the NVIDIA Q&A.

## Decisions already made
D-016 ElevenLabs TTS default, Nemotron ASR, Nano · D-012 never ask for secrets · D-005 never record the scammer call · D-023 teammates' numbers only · D-021 Brev optional (don't block on it).

## Stop and ask Lane 1 if...
- the Photon SIP bridge fails (decide fallback together at T+2).
- you need anything from the brain that isn't in `CallRequest` / `CaseDetail`.
- you're tempted to use a hosted voice-agent platform (Vapi, Retell, ElevenLabs Agents) instead of Pipecat: ask first.

## Definition of done
Titan's call works end to end on a teammate's phone with transcript on the case and spoken approvals; call events flow; PR `[lane 4] ...` with `Closes #32`.

## Teammate guide (Krishang)
- **Good first answer:** puts the T+2 bridge test first and names the Twilio fallback.
- **Check-in:** "Call me." · "How long until first words?" · "What does it say if I ask for my PIN to be read back?" (must refuse)
- **Red flags:** records/transcribes the scammer call; asks for PINs; uses a non-NVIDIA LLM; spends 3 hours on SIP without telling anyone.
