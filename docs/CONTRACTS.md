# Contracts v0.2 (domain-agnostic, owned by Lane 1)

Every lane builds against these shapes. Lane 1 freezes **v1** by T+1:15 and then changes them only
with a PR titled `contract:` that every lane owner acks. JSON Schemas live in `contracts/`,
example payloads in `contracts/fixtures/`. The mock server (Lane 1, first task at T0) serves the fixtures.

Brain base URL: `http://localhost:8000` locally, `BRAIN_URL` env var everywhere else.

## Endpoints
| Method | Path | Body → Response | Used by |
|---|---|---|---|
| GET | `/health` | → `{ok, pack, tools[]}` | everyone |
| POST | `/runs` | `RunRequest` → `Report` (blocking) | email, voice "full check" |
| POST | `/runs/stream` | `RunRequest` → SSE of `StepEvent`, last event `type:"done"` carries the `Report` | web |
| GET | `/runs/{run_id}` | → `Report` | share page, email links |
| GET | `/runs` | `?subject=&limit=` → `Report[]` (summaries) | web history |
| GET | `/tools` | → OpenAI tool schemas for the active pack | voice bot registers these |
| POST | `/tools/{name}` | `{...args}` → tool result (always has `source`) | voice quick answers |
| POST | `/actions` | `ActionRequest` → `Action` | web buttons, voice ("email them"), email |
| GET | `/actions/{action_id}` | → `Action` (status, counterparty reply if any) | web |
| PATCH | `/actions/{action_id}` | `{status, reply?, thread_id?}` → `Action` | email service when a reply arrives |
| POST | `/watches` | `WatchRequest` → `Watch` | web, voice, email |
| GET | `/watches` | → `Watch[]` | web |
| POST | `/watches/{watch_id}/tick` | → `Report` (forces a re-check now; demo button) | web, demo |
| POST | `/actions/{action_id}/approve` | `ApprovalRequest` → `Action` | web button, SMS/email "YES" reply, voice "go ahead" |
| GET | `/cases` | `?phone=&email=` → `Case[]` | voice (caller ID lookup), email (sender lookup), web |
| GET | `/cases/{case_id}` | → `CaseDetail` (case, latest report, actions, watches, full cross-channel timeline) | web case page |
| GET | `/cases/{case_id}/stream` | → SSE of every new `StepEvent` in the case, from any channel | web case page (live call view) |
| POST | `/cases/{case_id}/events` | `StepEvent` (no run_id) → `{ok}` | voice posts `transcript` + `channel_event`; email posts `channel_event` |

## Core shapes (see `contracts/*.schema.json` for the exact JSON Schema)

**Case**: one subject (a property, a car, a claim...) and everything that happened about it on any channel.
The brain resolves `case_id` when a request doesn't send one: match `reply_to.phone` / `reply_to.email` + subject, else create a new case.
This is what lets a returning caller hear "welcome back, they replied to your email."
`Case { case_id, subject_label, owner{email?, phone?, name?}, latest_score?, open_actions?, created_at, updated_at }`

**RunRequest**
```json
{ "input": { "text": "...", "subject": "optional label/address/VIN", "attachments": [{ "url": "...", "mime": "application/pdf" }] },
  "channel": "web | voice | email | sms | watch | mcp",
  "case_id": "optional",
  "pack": "optional; defaults to ACTIVE_PACK",
  "reply_to": { "email": "optional", "phone": "optional" } }
```

**StepEvent** (one per SSE `data:` line; `event:` name equals `type`)
```json
{ "run_id": "r_... (optional if case_id is set)", "case_id": "c_...", "channel": "web", "seq": 3, "ts": "ISO-8601",
  "type": "plan | tool_call | tool_result | finding | verify | action_proposed | approval_needed | transcript | channel_event | error | done",
  "label": "Human-readable one-liner for the timeline",
  "data": { } }
```
`data` by type: `plan` → `{steps:[str]}` · `tool_call` → `{tool, args}` · `tool_result` → `{tool, ok, summary, source}` ·
`finding` → `Finding` · `verify` → `{verified:[id], downgraded:[id]}` · `action_proposed` → `SuggestedAction` ·
`approval_needed` → `{action_id}` · `transcript` → `{speaker: "caller"|"agent", text}` ·
`channel_event` → `{kind: "call_started"|"call_ended"|"email_sent"|"email_received"|"sms_received"|"approved"|"alert"|"case_opened", ...}` ·
`error` → `{message, recoverable}` · `done` → `Report`.

**Report**
```json
{ "run_id": "r_...", "case_id": "c_...", "pack": "string", "channel": "web",
  "subject": { "label": "string", "location": { "lat": 0, "lon": 0 } },
  "findings": [ { "id": "f1", "claim": "string", "verdict": "supported | contradicted | unverifiable | info",
                  "severity": "low | medium | high", "evidence": "string",
                  "sources": [ { "label": "FEMA NFHL", "url": "https://...", "retrieved_at": "ISO" } ],
                  "evidence_view": { "kind": "map | doc | none", "data": {} },
                  "verification": { "status": "verified | downgraded | unchecked", "note": "string", "original_verdict": "if downgraded" } } ],
  "score": { "value": 0, "label": "string", "rationale": "string" },
  "summary": "string (2-3 sentences, also used as the voice answer)",
  "suggested_actions": [ { "id": "a1", "kind": "email_counterparty | call | watch | share", "label": "string", "draft": "optional text" } ],
  "created_at": "ISO" }
```

**ActionRequest** `{ run_id, kind, params }` → **Action**
`{ action_id, case_id, run_id, kind, status, draft{to, subject, body}, safety{ok, categories[], model}, approved_via?, detail?, thread_id?, reply? }`
Status flow: `awaiting_approval → approved | rejected → queued → sent → replied | failed`.
**Every outbound action to a third party starts in `awaiting_approval`.** The brain runs Nemotron Safety Guard on the draft first.
The user approves on the web, by replying YES to the SMS/email, or by saying "go ahead" on a call (`ApprovalRequest { decision, via, edited_body? }`).

**Verification pass**: after findings are drafted, the brain makes a second Nemotron call that sees only each finding plus the raw tool outputs.
It marks each finding `verified` or `downgraded` (verdict becomes `unverifiable`, `original_verdict` kept), then emits one `verify` event.

**WatchRequest** `{ run_id, every: "1h|1d|demo-30s", notify: { email?, phone? } }` → **Watch** `{ watch_id, run_id, every, last_checked_at, last_change? }`

## Internal channel endpoints (brain → channel, for outbound actions)
Channels never call data APIs, but the brain does call channels to *act*:
| Service | Port | Endpoint | Body |
|---|---|---|---|
| email/ | 8200 | `POST /internal/send` | `{to, subject, html, run_id, thread_id?}` → `{thread_id, message_id}` |
| email/ | 8200 | `POST /webhooks/agentmail` | AgentMail inbound webhook (replies update the Action via `PATCH /actions/{id}` on the brain) |
| voice/ | 8100 | `POST /internal/call` | `{to, run_id, purpose: "alert" \| "counterparty"}` → `{call_sid}` |
| watcher/ | n/a | loop process | reads due watches from DB → `POST /runs` with `channel:"watch"` → diff vs last report → notify via email/voice internal endpoints |

Ports: brain 8000 · web 3000 · voice 8100 · email 8200. Public webhooks go through one ngrok/cloudflared tunnel per service.

## Rules
- Channels never call data APIs directly. Only the brain does.
- Every tool result includes `source` (URL). A finding without a source is `unverifiable`.
- `summary` must be speakable in under 15 seconds (voice reads it verbatim).
- Every StepEvent that happens on a case is also stored on that case's timeline and pushed to `/cases/{id}/stream`.
- Speed budget (demo-critical): first StepEvent < 1.5s, full web run < 25s, voice first words < 2s. Run independent tool calls in parallel.
- Errors: HTTP 4xx/5xx with `{ "error": { "code": "string", "message": "string" } }`.
