# Architecture: Titan

What we build and why: docs/PLAN.md. Details per area: PACK_SPEC (data, ML), DATABASE, SECURITY, CONTRACTS.

## System purpose
Titan sits on top of T-Mobile's existing protections. When a sensitive account action happens during a suspicious call, it (1) pauses the customer instantly, (2) runs a team of Nemotron agents to work out what's going on, (3) makes the account safer through T-Mobile's own protections, and (4) reaches the customer on iMessage and a phone call through Photon, then (5) walks her through recovery and sends an incident summary.

Constraints: 24-hour build, 7 coding agents in parallel, free tiers, synthetic data only, demo on venue Wi-Fi, NVIDIA free-tier rate limits.

## Stack decisions
| Layer | Choice | Reason | Constraint |
|---|---|---|---|
| Brain (API + agents) | Python 3.11, FastAPI, SSE, OpenAI SDK → build.nvidia.com | Starter kit already runs this; SSE is simple for live streams | Free-tier rate limit: retry with backoff, own key per person |
| Agents | Our own workflow engine (no LangChain) | Every step must stream to the dashboard; we control it fully | Keep each agent's prompt + tools small |
| LLMs | Nemotron Super (Context, Risk, Verifier, Response), Nano (Messaging, Voice), VL (screenshots), Safety Guard, NeMo Retriever | NVIDIA track | Endpoints from env so Brev can swap in |
| ML | scikit-learn, XGBoost, SHAP | Fast, explainable, trains in seconds | Runs in-process in the brain |
| Web | Next.js (App Router), TypeScript, Tailwind v4 | One app for portal, case page, dashboard, console | Typed client generated from contracts |
| Messaging | TypeScript, Photon `spectrum-ts`, Hono | Photon's SDK is TypeScript only | Webhooks at least once: dedupe |
| Voice | Python, Pipecat, Nemotron ASR, ElevenLabs TTS (Magpie fallback) | Real-time voice pipeline | Photon SIP bridge, Twilio fallback at T+2 |
| Database | Supabase Postgres; in-memory fallback | Free, hosted, SQL | Brain must run with no DB (MOCK / in-memory) |
| Auth | None (hardcoded synthetic personas) | Hackathon demo | Out of scope; say so |
| Hosting | Everything runs on one demo laptop; ngrok for Photon/Twilio webhooks | No deploy risk; venue Wi-Fi | Hotspot fallback; backup video |
| Optional GPU | Brev (one box, off the critical path) | Free credits | Env switch back to hosted in one minute |

## Components
```
          Scammer's phone ──call──▶ Photon number ──forwards──▶ Maya's iPhone
                                       │ call started/ended                ▲ iMessage + Titan call
                                       ▼                                   │
 web/ portal ──check / action──▶ ┌──────────────── BRAIN (agent/) ─────────────────┐
 (pause screen, /case)           │ Event ingest ─▶ Gate (rules + ML, <300ms)       │
 web/ console ──scripted events─▶│        │ trigger                                │
                                 │        ▼                                        │
                                 │ Workflow engine: Context → Risk → Verifier →    │
                                 │                  Response → (wait for reply) →  │
                                 │                  Recovery → Summary → Watch     │
                                 │ Tools: mock protections, account data, call     │
                                 │        context, ML score, scam-link checks,     │
                                 │        policy lookup                            │
                                 │ Case store + SSE fan-out                        │
                                 └───────┬───────────────────┬─────────────┬───────┘
                                         │ /internal/send    │ /internal/call   │ SSE
                                         ▼                   ▼                  ▼
                                  messaging/ (Photon)   voice/ (Pipecat)   web/ guardian dashboard
                                  iMessage in/out       Titan's calls      + customer /case page
                                         ▲                   ▲
                                         └─ replies ─────────┴─ spoken answers ─▶ POST back to brain
 watcher/ ── 24h watch ──▶ POST /events
```

## System boundaries
- **Brain owns:** every decision, every agent, all model calls (except the voice/messaging agents' own conversation turns), the mock T-Mobile protections, the case record, approvals.
- **Doors (web, messaging, voice) own:** talking to people and providers. They never decide; they send events and approvals to the brain and render what it streams.
- **External services own:** Nemotron (reasoning), Photon (iMessage/SMS/voice delivery), ElevenLabs (speech out), Nemotron ASR (speech in), Supabase (storage), RDAP/URLhaus (link checks). Each has a failure path below.
- **Out of scope:** real T-Mobile systems, real customer data, auth/accounts, production deployment.

## The two paths (the key design choice)
**Fast path, synchronous, under 300 ms:** the portal asks `POST /check` *before* applying a sensitive action. The **gate** uses only deterministic rules + the ML score (no LLM), so the pause screen appears instantly:
- returns `allow`, `pause` (show the pause screen), or `hold` (apply, but put it on a 24h hold, e.g. transfer PIN).
- Hard rules: protection turned off / transfer PIN / login code sent **during an unverified call** → at least `pause`. Shield mode: while such a call is active, protections need the pause screen (and the face check if enabled) to be turned off.

**Slow path, asynchronous, ~5–15 s, streamed:** the same event triggers a **workflow run** on a background worker. The agents investigate, act and reach the customer, and every step streams to the dashboard and case page.

## Workflow engine (one run per incident)
```
triggered → context → risk → verify → respond ─┬─▶ awaiting_reply ──(YES)──▶ released ─▶ summary ─▶ watching ─▶ closed
                                               │        │ (no reply 60s) → call via voice
                                               │        └──(NO / "help me")──▶ recovering (one approval per step) ─▶ summary ─▶ watching
                                               └─▶ heads_up only (unverified "T-Mobile" call, no action yet)
```
- **Stages:** Context agent (parallel tool calls) → Risk agent (ML score + Nemotron reasoning) → Verifier (second Nemotron pass; drops/downgrades unsupported claims) → Response agent (actions through protections, chooses channel, writes messages).
- **Pause and resume:** a run in `awaiting_reply` is persisted. It resumes on an event: an iMessage reply, a spoken answer, a portal button ("I'm on a call: help me"), or a timer (60 s → escalate to a call; 24 h → end watch).
- **Safety rule for agent actions:** agents may only make the account **safer** on their own (re-lock, hold, require step-up). Anything that **loosens** protection (release a hold, cancel a lock) needs the customer's approval *and* no suspicious call active (or a face check).
- **Every outbound message/script** passes Safety Guard, then is checked by the Verifier against the case facts.
- **Streaming:** each stage emits typed `StepEvent`s (plan, tool_call, tool_result, score, verify, action, message, transcript, approval, summary, done) to the case's SSE stream.

## Request and data flow (the T2 demo)
1. Scammer calls the Photon number → messaging/voice service posts `call.started` (number hash, caller-ID name, attestation, seen_before) to `POST /events`. The brain opens a **call window** for Maya. If the caller ID claims "T-Mobile" and isn't verified → heads-up run (text only).
2. Maya taps "Turn off Port Out Protection" in the portal → portal sends behavior features + `POST /check` → gate returns `pause` → pause screen. She taps "I'm doing this on my own" → portal calls `POST /protections/{user}/port_out_protection` (off). The mock protections service applies it and emits `protection.changed` with `during_call` set.
3. She requests a transfer PIN → gate returns `hold` → PIN issued on hold → `transfer_pin.requested` event → **workflow run starts**.
4. Context → Risk ("coached victim", calibrated 0.87 + top reasons) → Verifier → Response: re-locks Port Out Protection, keeps the PIN on hold, `POST /internal/send` (iMessage via Photon).
5. No reply in 60 s → `POST /internal/call` → voice service calls Maya through Photon; transcript lines stream into the case.
6. Spoken answers → `POST /actions/{id}/approve` per recovery step → protections service applies each.
7. Response agent writes the incident summary → Verifier → Safety Guard → `POST /internal/send`. Case page and dashboard show it. Watcher starts a 24 h watch.
Failure at any step → the dashboard shows the error step; the run continues with what it has (see Operations).

## Interfaces (contracts v0.3, Lane 1 writes `contracts/schema.json`)
| Method + path | Caller | Purpose |
|---|---|---|
| `POST /events` | doors, console, watcher | Ingest any event (call, protection, login, code, forwarded text, portal signals). Idempotent on `event_id` |
| `POST /check` | portal | Fast gate before a sensitive action → `allow \| pause \| hold` + reason |
| `GET/POST /protections/{user}[/{name}]` | portal | Mock T-Mobile protections: read state, apply a change (emits events) |
| `GET /users/{id}/timeline` | web | Recent events + call windows |
| `GET /cases/{id}` · `GET /cases/{id}/stream` | web | Case detail · live SSE of StepEvents |
| `POST /cases/{id}/events` | voice, messaging | Transcript lines, delivery receipts |
| `POST /actions/{id}/approve` · `/reject` | portal, voice, messaging | Customer approvals (`approved_via` web/sms/voice) |
| `POST /internal/send` (messaging) · `POST /internal/call` (voice) | brain | Outbound iMessage/SMS · outbound call |
| `GET /health`, `GET /tools` | anyone | Liveness, tool list |
Mock mode: `MOCK=1` serves fixtures for every endpoint and replays the T2 stream, so all lanes build without the real brain.

## Project structure
```
agent/                      Lane 1 (brain) unless noted
  server.py                 FastAPI app, routes
  core/
    events.py               ingest, idempotency, call windows
    gate.py                 fast path: rules + ML → allow/pause/hold
    workflow.py             run state machine, pause/resume, timers
    agents/                 context.py risk.py verifier.py response.py (prompts + tool sets)
    llm.py                  model router (env base URLs), 429 retry/backoff, timeouts
    cases.py  stream.py     case store, SSE fan-out
    approvals.py            approve/reject, safer-only rule
    store/                  memory.py, supabase.py (same interface)
  packs/guard/              Lane 2a: data/, generator.py, protections.py (mock T-Mobile), tools.py
    ml/                     Lane 2b: anomaly.py, risk_model.py, text_clf.py, score()
  cache/                    DEMO_MODE tool-result cache
evals/                      Lane 2b
web/                        Lane 3a (app/guardian, components/guardian) · Lane 3b (everything else)
  app/portal  app/case/[id]  app/console  app/guardian/[case]  lib/api  lib/behavior
messaging/                  Lane 5 (TypeScript, Photon)
voice/                      Lane 4 (Pipecat)
watcher/  db/               Lane 5
contracts/  scripts/  docs/ Lane 1
```

## Operations
- **Run:** `scripts/dev.sh` starts brain (8000), web (3000), voice (8100), messaging (8200), watcher, and ngrok tunnels. Env from each folder's `.env` (names in `.env.example`).
- **Modes:** `MOCK=1` fixtures only · `DEMO_MODE=1` cached tool results, live models · default live.
- **Failure behavior:** Nemotron 429/timeout → retry with backoff (3×), then fall back to Nano for that step and mark it on the dashboard · Photon down → Twilio SMS/voice fallback · Supabase down → in-memory store · ML not ready → rules-only score, confidence marked "rules only" · RDAP/URLhaus down → that check reads `unverifiable`.
- **Speed budget:** gate < 300 ms · first StepEvent < 1.5 s · run to first customer message < 15 s live, < 8 s in DEMO_MODE · voice first words < 2 s.
- **Logs:** structured JSON, phone numbers hashed, no message bodies at info level (see SECURITY.md).
- **Rollback:** `main` always runs; revert the merge that broke the demo, then fix.

## Decisions and unknowns
| Item | Status | Owner |
|---|---|---|
| Fast gate (rules + ML) + async agents | Decided | Lane 1 |
| Agents only make things safer on their own | Decided | Lane 1 |
| ElevenLabs default TTS, Nemotron ASR | Decided | Lane 4 |
| Photon voice via SIP bridge | Unknown until T+2, Twilio fallback | Lane 4 |
| Photon SMS number available? | Unknown | Lane 5 |
| Supabase vs in-memory for the demo | Supabase if ready by T+8, else memory | Lane 5 / Lane 1 |
| Brev self-hosted Nano | Optional, after T+5 | Yuvan's Codex (#39) |
| Face check | Optional, first to cut | Lane 3b |
