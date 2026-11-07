# Lanes: 5 agents, zero merge conflicts

Each lane owns its folders. **Touch another lane's folder only through a PR that owner approves.**
Lane 1 is the integrator: it owns `contracts/`, `agent/server.py`, `agent/core/`, `CLAUDE.md`, `AGENTS.md`, and merges to `main`.
Tasks live as GitHub Issues labeled `lane:spine`, `lane:packs`, `lane:web`, `lane:voice`, `lane:email`. Pick the lowest-numbered open one.

| Lane | Human · agent | Owns (folders) | Branch | Done = |
|---|---|---|---|---|
| 1 Spine | Yuvan · Claude Code | `agent/server.py`, `agent/core/`, `contracts/`, `docs/`, `scripts/`, root md files | `lane/spine` | Mock mode, real SSE streaming, cases + case stream, verification pass, approval flow, speed budget met |
| 2 Packs + data → QA | Yuvan · Codex | `agent/packs/<pack>/`, `agent/cache/`, `evals/` | `lane/packs` | Domain tools with `source`, DEMO_MODE replay, Nemotron VL doc reading, accuracy evals. **From T+10: QA** |
| 3 Web | saikarthikbattula / rigshank / Ish0212 (assign) · Codex | `web/` | `lane/web` | Run page (live timeline), report with verified badges, approval buttons, **case page with live call view**, share page, evidence view |
| 4 Voice + SMS | (assign) · Codex | `voice/` | `lane/voice` | Inbound call with caller-ID case memory, streams transcript to the case, "go ahead" approvals, outbound alert call, SMS YES approvals |
| 5 Email + memory | (assign) · Codex | `email/`, `db/`, `watcher/`, `DEVPOST.md` | `lane/email` | Forward-to-inbox → report reply; counterparty email + reply tracking; email YES approvals; Supabase schema; watcher loop |

## Git rules (every agent follows these)
- Branch from `main`, commit small, `git pull --rebase origin main` at least every hour and before every PR.
- PR into `main` with title `[lane N] what changed` and `Closes #<issue>`. Lane 1 merges. Never force-push `main`.
- CI must be green: contract fixtures validate against the schema, and gitleaks finds no secrets.
- Contract change? Open a PR titled `contract: ...` touching only `contracts/` + `docs/CONTRACTS.md`. Don't hand-edit around it.
- `main` must always run. If your merge breaks the demo path, revert first, fix second.
- Never commit `.env*` (except `.env.example`). Add new env var *names* to the `.env.example` in your folder.

## Phase 0 prompts (paste at T0, before the domain is final; everything builds against the mock)

All Codex prompts start with:
> Read AGENTS.md, docs/GAMEPLAN.md, docs/CONTRACTS.md and the Lane N section of docs/LANES.md. Skills are in `.claude/skills/<name>/SKILL.md`; read the ones I name before starting. Work through the open GitHub Issues labeled lane:<lane> in order. Plan in 5 bullets, then build. Stay inside your lane's folders.

**Lane 1 (Claude Code):**
> Build the brain spine in agent/ to docs/CONTRACTS.md. (1) `MOCK=1` mode serving contracts/fixtures for every endpoint, SSE replayed at 400ms per event; ship within 30 min. Also `scripts/dev.sh` (starts brain, web, voice, email, tunnels) and generated types from contracts/schema.json (TS for web/, Pydantic for Python lanes). (2) Real `/runs/stream`: agent loop on a worker thread, typed StepEvents through a queue, independent tool calls in parallel. (3) Cases: resolve/create from reply_to + subject, store every event on the case timeline, `/cases/{id}/stream` fan-out, `POST /cases/{id}/events`. (4) Verification pass + structured final report call. (5) Approval flow with Safety Guard on drafts. (6) Pack loader via `ACTIVE_PACK`. Supabase via db/ from lane 5, in-memory fallback.

**Lane 2 (Codex):**
> Build agent/packs/ infrastructure: tool-result cache keyed by (tool, args) under agent/cache/, `DEMO_MODE=1` serving only cached results, and a record script that warms the cache for our demo inputs. Port agent/tools.py into agent/packs/example/ as the reference pack and merge the 5 sequential Overpass calls into one query. Add `read_document` using a Nemotron vision model on build.nvidia.com (verify the slug). Then `evals/`: a folder of golden cases (input + expected verdict per claim) and `evals/run.py` that calls POST /runs and prints % of verdicts correct plus a per-case table. Every tool returns a `source` URL.

**Lane 3 (Codex):**
> Read .claude/skills/design-taste-frontend, better-layout, better-typography and screenshot-to-code. Create web/ with Next.js (App Router, TypeScript) + Tailwind. `NEXT_PUBLIC_BRAIN_URL` points to the brain (mock is fine). Pages: `/` input (text + file drop). `/run/[id]` live timeline from /runs/stream, then the report: score, finding cards by verdict with source links and a "checked twice" badge when verification.status is verified, and suggested-action buttons. Actions in awaiting_approval show the draft + Approve/Reject (POST /actions/{id}/approve). `/case/[id]` is the hero screen: everything that happened on the case across channels from /cases/{id}/stream, with a live call panel where transcript lines and tool calls animate in as the phone call happens. `/r/[id]` read-only share page. `<EvidenceView>` renders MapLibre when evidence_view.kind=="map". Neutral placeholder copy until the domain is picked.

**Lane 4 (Codex):**
> Read .claude/skills/nemotron-voice-agent-builder (cloud profile, no GPU). Build voice/ as a Pipecat bot with Twilio Media Streams: Nemotron ASR streaming + Magpie TTS via NVCF, LLM nvidia/nemotron-3-nano-30b-a3b. On call start, look up the caller with GET /cases?phone= and greet returning callers with their case status. Load tools from GET $BRAIN_URL/tools and run them via POST /tools/{name}. Add `full_check(text)` (POST /runs, channel voice, speak `summary`), `email_receipt(email)`, and `approve(action_id)` for "go ahead". Post every transcript line and tool call to POST /cases/{id}/events as they happen. Make TTS switchable with `TTS_PROVIDER=magpie|elevenlabs` (Pipecat has an ElevenLabs TTS service; use a Flash model for latency, voice from `ELEVENLABS_VOICE_ID`). Expose POST /internal/call for outbound alert calls, and a Twilio SMS webhook on the same number: a "YES" reply approves the pending action. Target: first words < 2s.

**Lane 5 (Codex):**
> Read .claude/skills/agentmail and agentmail-toolkit. (1) db/: Supabase SQL migration for cases, runs, events (the case timeline), actions, watches, messages. RLS off for the hackathon; note it in docs/SECURITY.md. (2) email/: FastAPI on 8200. POST /webhooks/agentmail: inbound mail → find the case via GET /cases?email= → POST $BRAIN_URL/runs (channel email, attachments passed through) → reply in-thread with the report as clean HTML with source links. A reply of "YES" to an approval email approves the action. POST /internal/send for outbound counterparty emails; when the counterparty replies, PATCH the action and post a channel_event to the case. (3) watcher/: loop that re-runs due watches, diffs findings vs the last report, and notifies via email/voice internal endpoints on change.

## Phase 1 (after the idea is chosen)
Lane 1 posts a short `docs/PACK_SPEC.md` (claims we check, tools + data sources, demo inputs, counterparty, demo script timing).
Every lane then gets a one-line follow-up prompt: "Read docs/PACK_SPEC.md and apply it to your lane: domain copy, demo inputs, and the parts of docs/DEMO.md you own."

## Phase 2: QA (Lane 2 from T+10)
> Every hour: pull main, start everything with scripts/dev.sh in DEMO_MODE, and run the docs/DEMO.md script with playwright-cli (web) plus a scripted call. Time each beat against the budget. File each failure or slow beat as a GitHub Issue labeled with the owning lane and `demo-blocker` or `polish`.

## Integration checkpoints
T+4 web ↔ real brain · T+8 all doors on the real brain + case memory · T+14 features 1–9 · T+18 freeze.
At each checkpoint, everyone merges and Lane 1 runs the demo script end to end with a stopwatch.
