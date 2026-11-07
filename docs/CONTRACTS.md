# Contracts v0.3 (Titan)

**Source of truth:** `contracts/schema.json` (JSON Schema 2020-12, 36 types in `$defs`). This page is the map.
TypeScript types: `contracts/generated/types.ts` (copy into your app with `scripts/gen_types.sh`).
Python: validate with `core.contracts.errors("TypeName", obj)` in the brain, or `jsonschema` against the same file.
Examples for every type: `contracts/fixtures/` (the T2 coached-victim story, plus T1, T1b, T3 events). CI validates them all.

**Change a contract:** edit `scripts/schema/build_schema.py` → `python scripts/schema/build_schema.py contracts/schema.json` → `bash scripts/gen_types.sh` → `python scripts/validate_contracts.py` → PR titled `contract: ...`. Lane 1 merges.

## Run the brain against the contract today
```
cd agent && MOCK=1 uv run --no-project --with-requirements requirements.txt uvicorn server:app --reload --port 8000
curl -X POST localhost:8000/demo/play/t2      # plays the whole coached-victim story
open http://localhost:8000/docs               # every endpoint, try it live
```
`MOCK=1`: real gate rules + real in-memory store; workflow runs **replay the fixture run** step by step (`MOCK_STEP_MS`, default 400 ms). When the Nemotron workflow lands, the StepEvents look identical. Set `MESSAGING_URL` / `VOICE_URL` and the brain also POSTs outbound messages and calls to your door; otherwise see them at `GET /demo/outbox`.

## Endpoints (brain, port 8000)
| Method + path | Who calls | Body → Response |
|---|---|---|
| `GET /health` | anyone | `{ok, mock, version}` |
| `GET /tools` | voice, docs | tool names + descriptions |
| `GET /users` · `GET /users/{id}/timeline` | web | `User[]` · `Timeline` (events, calls, active_call) |
| `POST /events` | voice, messaging, portal, console, watcher | `Event` → `{accepted, duplicate, case_id, trigger}`. Idempotent on `event_id`. 422 if it breaks the contract |
| `POST /check` | portal, before any sensitive action | `CheckRequest` → `CheckResponse` (`allow \| pause \| hold \| block`, reasons, pause_screen). Rules only, < 300 ms |
| `GET /protections/{user}` | portal | `ProtectionState` (protections, shield_mode, transfer_pin) |
| `POST /protections/{user}/{name}` | portal | `ProtectionChangeRequest` → `ProtectionState`. Turning one **off** during an unverified call → **409** unless `check_id` is from an `allow` check |
| `POST /transfer-pin/{user}` | portal | → `{check: CheckResponse, protections: ProtectionState}`; `hold` during a suspicious call (starts a run) |
| `GET /cases?user_id=` · `GET /cases/{id}` | web | `Case[]` · `CaseDetail` (everything the dashboard and `/case` page need) |
| `GET /cases/{id}/stream` | web | SSE: `event: step` (`StepEvent`) then `event: case` (`Case`) per step; history first; ends after `type: done` |
| `POST /cases/{id}/events` | voice, messaging | `CaseEventRequest` (transcript lines, replies) → `Message` |
| `POST /actions/{id}/approve` · `/reject` | portal, voice, messaging | `ApprovalRequest {via}` → `Action`. **409** if it loosens protection during a suspicious call |
| `GET /demo/outbox` · `POST /demo/reset` · `POST /demo/play/{t1\|t2\|t3}` | console, testing | demo helpers |

## Doors expose (the brain calls these)
| Door | Endpoint | Body |
|---|---|---|
| messaging (8200) | `POST /internal/send` | `SendRequest` (case_id, user_id, channel, kind, text, expects_reply). Never links. Resolve the phone number yourself |
| voice (8100) | `POST /internal/call` | `CallRequest` (purpose, opening_line, facts, pending_action_ids) |

## Events (`POST /events`, `Event.type` → `data` shape)
| type | data | Sent by |
|---|---|---|
| `call.started` | `CallData` (direction, other_number_hash, caller_name, attestation A/B/C/none, seen_before, scam_label) | voice (from the Photon/Twilio webhook) |
| `call.ended` | `{duration_s}` | voice |
| `login` | `{device_hash, region, new_device, succeeded}` | portal |
| `otp.sent` / `otp.entered` | `{purpose}` | portal / brain |
| `pin.attempt` | `{ok, channel}` | portal |
| `protection.changed` | `{name, enabled, via}` | portal (the brain emits it for you on `POST /protections/...`) |
| `transfer_pin.requested` | `{}` | portal (via `POST /transfer-pin/{user}`) |
| `sim_swap.requested` | `{new_device_hash, channel}` | portal |
| `portal.signals` | `PortalSignals` (derived numbers only) | portal behavior script |
| `message.forwarded` | `{channel, text?, image_url?, from_hash?}` | messaging |
| `customer.reply` | `{channel, text, case_id?}` | messaging, voice |
| `face.result` | `{match, similarity, liveness, antispoof}` | portal (computed on the device) |
| `line.region` | `{region}`: where the phone on the line is right now (simulated carrier signal, sent only at trigger snapshots) | voice / generator / console (D-034) |
The brain stamps `call_id` on any event that happens during an active call: that's how "actions taken during the call" works.

## Triggers (what starts a run)
- `call.started`, unverified, caller ID says T-Mobile → **heads-up** text; opens the case for that call.
- `transfer_pin.requested` or `otp.sent` during a suspicious call → **coached** run (same case as the call).
- Pause screen "I'm on a call: help me" (`POST /check` with `customer_choice: on_call_help`) → `block` + coached run now.
- `sim_swap.requested` right after a new-device login → **takeover** run.
- `message.forwarded` → **scam_text** run.
"Suspicious call" = active, not seen before, and attestation not A (or labeled scam).

## Key shapes (see schema for every field)
- **StepEvent** `{seq, case_id, run_id, ts, agent: system|context|risk|verifier|response|messaging|voice, stage: trigger|context|risk|verify|respond|reach|await|recover|summary|watch, type: plan|tool_call|tool_result|signal|score|verify|action|message|call|transcript|approval_needed|approved|summary|error|done, title, data}`. `title` is the dashboard line.
- **RiskScore** `{threat, probability, calibrated, confidence: low|medium|high, anomaly, top_reasons[{feature, contribution, text}], model}`. Lane 2b's `score()` returns exactly this.
- **Action** `{action_id, kind, direction: safer|looser, status, requires_approval, approved_via, description}`.
- **IncidentSummary** `{case_number, what_happened, why_we_stepped_in, confidence_text, what_we_did[], you_approved[], next_steps[], spot_it_next_time, data_we_looked_at[], replies[]}`.
- **DatasetScenario** (Lane 2a → 2b) `{scenario_id, user_id, label, hard_negative, trigger_event_id, events[], generator{seed, variant}}`.

## Rules
- Every fact shown to a customer or on the dashboard comes with a `Source` (`Signal.source`).
- Agents may only make things **safer** on their own. Looser actions need approval and no suspicious call (enforced by the brain, 409).
- Titan never asks for a PIN, code or password and never sends a link.
- Speed: `/check` < 300 ms · first StepEvent < 1.5 s · first customer message < 15 s live.
