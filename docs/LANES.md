# Lanes: 7 agents in parallel, zero merge conflicts

Product: **Titan** (see docs/PACK_SPEC.md). Tracks: NVIDIA + T-Mobile + Photon. Pack name `guard`.

## How parallel works here
1. **Every agent owns folders nobody else touches.** Need a change elsewhere? Ask the owner or open a PR they approve.
2. **Contracts first.** Contracts v0.3 + fixtures + the `MOCK=1` brain are on main (PR #40). Everyone builds against the mock, so nobody waits on anybody.
3. **Interfaces, not files, connect lanes.** Data ↔ ML talk through the dataset schema in `contracts/`. Web, voice and messaging talk to the brain only over HTTP from docs/CONTRACTS.md.
4. **One branch per agent**, PR to `main`, Lane 1 merges. Integration checkpoints below.

| # | Lane | Person · agent | Owns (only these) | Branch | Label | Working by |
|---|---|---|---|---|---|---|
| 1 | Spine | Yuvan · Claude | `agent/server.py`, `agent/core/`, `contracts/`, `docs/`, `scripts/`, root md files | `lane/spine` | `lane:spine` | Mock T+1, real brain T+6 |
| 2a | Data + protections | Yuvan · Codex | `agent/packs/guard/` **except** `ml/` | `lane/data` | `lane:data` | Seed data T+1:30, tools T+5 |
| 2b | ML + evals | Ishan · Codex #2 | `agent/packs/guard/ml/`, `evals/` | `lane/ml` | `lane:ml` | T+9 |
| 3a | Web: guardian | Ishan · Claude | `web/app/guardian/`, `web/components/guardian/` | `lane/web-guardian` | `lane:web-guardian` | T+8 |
| 3b | Web: portal + shell | Ishan · Codex #1 | everything else in `web/` (scaffold, `package.json`, layout, theme, `web/lib/`, `/portal`, `/console`, face check) | `lane/web-portal` | `lane:web-portal` | Scaffold T+0:45, portal T+8, face T+12 |
| 4 | Voice | Krishang · Codex | `voice/` | `lane/voice` | `lane:voice` | Bridge go/no-go T+2, done T+10 |
| 5 | Messaging + memory | Karthik · Codex | `messaging/` (TypeScript), `db/`, `watcher/`, `DEVPOST.md` | `lane/messaging` | `lane:messaging` | T+8 |

Usernames: Ishan = Ish0212, Karthik = saikarthikbattula, Krishang = rigshank (confirm).
Old Phase 0 issues (#1–#28) are background only. **Work from the `phase-1` issues for your label.**

## Hand-offs that unblock others (do these first)
| By | Who | Delivers | Unblocks |
|---|---|---|---|
| T+0:45 | 3b | `web/` scaffold pushed (Next.js, Tailwind, layout, typed API client) | 3a |
| ✅ done | 1 | contracts v0.3 + fixtures + `MOCK=1` brain + `scripts/dev.sh` (PR #40) | everyone |
| T+1:30 | 2a | small seed dataset matching the dataset schema in `contracts/` | 2b |
| T+2:00 | 4 | Photon voice bridge works or not (tell Lane 1) | demo plan |
| T+3:00 | 2b | `score()` stub returning the real `RiskScore` shape | Lane 1 Guardian tools |
| T+3:00 | 5 | inbound iMessage → brain → reply works against the mock | Lane 1 approvals |

## Git rules (every agent follows these)
- Branch from `main`, commit small, `git pull --rebase origin main` at least every hour and before every PR.
- PR into `main` with title `[lane N] what changed` and `Closes #<issue>`. Lane 1 merges. Never force-push `main`.
- CI must be green: contract fixtures validate against the schema, and gitleaks finds no secrets.
- Contract change? Open a PR titled `contract: ...` touching only `contracts/` + `docs/CONTRACTS.md`. Don't hand-edit around it.
- `main` must always run. If your merge breaks the demo path, revert first, fix second.
- Never commit `.env*` (except `.env.example`). Add new env var *names* to the `.env.example` in your folder.

## Hand-off: start here (every teammate, ~10 minutes)
1. Accept the GitHub invite, then `git clone https://github.com/yuvanmuru-dev/hackutd-2026 && cd hackutd-2026`.
2. `brew install gitleaks && bash scripts/install-hooks.sh` (blocks commits that contain keys).
3. Copy `agent/.env.example` → `agent/.env` and fill in **your own** NVIDIA key (+ your lane's keys). Never commit it.
4. Run the brain: `bash scripts/dev.sh` → open http://localhost:8000/docs → `curl -X POST localhost:8000/demo/play/t2` → `curl localhost:8000/cases`. If you see a case, you're set.
5. Read docs/PLAN.md (5 min) and docs/CONTRACTS.md (the API you build against).
6. `git checkout -b <your branch from the table>`, open your agent (Codex/Claude) in the repo, and paste the shared opening line + your lane's prompt below.
7. Your issue is assigned to you. PR into `main` with `[lane N] ...`; Yuvan merges.

## Prompts (paste into your agent)
Every prompt starts with:
> Read AGENTS.md, docs/PLAN.md, docs/CONTRACTS.md, docs/ARCHITECTURE.md and your lane's row and prompt in docs/LANES.md. Skills are in `.claude/skills/<name>/SKILL.md`; read the ones named. Work through the open GitHub Issues labeled `<your label>` + `phase-1`, lowest number first. Plan in 5 bullets, then build. Stay inside your folders. Build against the `MOCK=1` brain (`bash scripts/dev.sh`); use the TypeScript types in `contracts/generated/types.ts` and the examples in `contracts/fixtures/`. Never change a contract shape locally: ask Lane 1.

**Lane 1 · Yuvan · Claude:** done: contracts v0.3, fixtures, MOCK brain (gate, events, triggers, mock protections in `core/store.py`, SSE, approvals), `dev.sh`, types. Next: real workflow (`core/llm.py`, `core/agents/` Context/Risk/Verifier/Response, `core/workflow.py` pause/resume), `MOCK=0`, Supabase store adapter.

**Lane 2a · Yuvan · Codex:** in `agent/packs/guard/` (not `ml/`). (1) Seeded generator → `agent/packs/guard/data/`: 5 personas (PACK_SPEC) × 90 days of `Event`s, plus ~300 labeled `DatasetScenario`s (T1 takeover, T1b code relay, T2 coached, T3 scam text, T4 bot, T5 recovery scam) and hard negatives (Marcus new state, Priya 3am, Dev store activation, Maya long call with her daughter). Exact shapes: `Event`, `DatasetScenario` in `contracts/schema.json`; examples `contracts/fixtures/scenario.*.json`. Commit a 20-scenario seed set first (unblocks ML). (2) Tools in `agent/packs/guard/tools.py` with these exact names, each returning data + a `Source`: `account_history`, `device_sim_status`, `protection_status`, `call_context`, `location_match`, `portal_signals`, `check_message` (lookalike domain, RDAP age, URLhaus), `recent_scam_reports`, `policy_lookup` (NeMo Retriever over a short carrier policy + FTC guidance we write in `data/policy/`). Read from the brain's store interface (`core/store.py`); don't own protection state (the brain does). Data rule in PACK_SPEC: nothing from the "cut on purpose" list. From T+10: QA (below).

**Lane 2b · Ishan · Codex #2:** in `agent/packs/guard/ml/` and `evals/`. (1) `score(user_id, event, history) -> RiskScore` (exact shape in schema; example `contracts/fixtures/risk.t2.json`). Ship a stub returning that shape within the first hour. (2) Per-persona Isolation Forest on legit scenarios → `anomaly`. (3) XGBoost `takeover/coached/legit` (+ `bot`) with isotonic calibration, SHAP → `top_reasons` with plain-English `text`. (4) Scam text classifier: NeMo Retriever embeddings + logistic regression (T3). (5) `evals/run.py`: held-out scenarios from unseen generator variants; precision, recall, false-positive rate per threat; calibration; ablation rules → +anomaly → +classifier. Train on Lane 2a's seed set first; retrain on the full set. Optional: GPU training on Brev with #39.

**Lane 3a · Ishan · Claude:** read design-taste-frontend, better-layout, better-typography. Build `/guardian/[case]` (the "under the hood" projector view) inside `web/app/guardian/` and `web/components/guardian/`, using 3b's shell and API client. Data: `GET /cases/{id}` (`CaseDetail`) + live `GET /cases/{id}/stream` (`StepEvent`s, then `Case` heads). Show: the call window bar with actions taken during the call highlighted (`timeline` events with `call_id`), the four agent stages lighting up (Context → Risk → Verifier → Response) from `StepEvent.agent/stage`, tool calls streaming in, the risk card (`RiskScore`: threat, plain confidence, top 3 reasons, "checked twice" from `verification`), protection actions taken, iMessage thread + call transcript (`messages`), recovery steps checking off (`actions`), and a "data used" panel (`data_used`). Must read from the back of a room. Test with `POST /demo/play/t2`.

**Lane 3b · Ishan · Codex #1:** scaffold `web/` first (Next.js App Router, TypeScript, Tailwind v4, layout, theme tokens; `web/lib/api/` typed client using `contract-types.ts` from `scripts/gen_types.sh`) and push within 45 min. Then, as Maya, a neutral **unbranded** carrier portal (our own "T" glyph, no T-Mobile logo): `/portal` login, Security page (SIM Protection, Port Out Protection, Scam Block toggles, "Generate transfer PIN", account PIN), using `GET/POST /protections/{user}...` and `POST /transfer-pin/{user}`. **Pause screen:** before turning a protection off, call `POST /check`; if `decision: pause`, show `pause_screen` (title, body, two buttons); "help me" → `POST /check` with `customer_choice: on_call_help`; "doing it myself" → `customer_choice: doing_it_myself` then send the change with `check_id`. Show hold messages ("Your PIN will be ready in 24 hours"). Behavior script in `web/lib/behavior/` → `POST /events` type `portal.signals` (derived numbers only; consent screen; no motion sensors). Customer **`/case/[id]`** page (the "T-Life app" view of the incident summary, `CaseDetail.summary`). `/console`: buttons for `POST /demo/play/{t1|t2|t3}`, `/demo/reset`, and single scripted events. Last and optional: face check toggle (`@vladmandic/human`, on-device, sends `face.result`).

**Lane 4 · Krishang · Codex:** read nemotron-voice-agent-builder. Build `voice/` (Pipecat; Nemotron Nano for the conversation via `VOICE_LLM_BASE_URL`; Nemotron ASR; **ElevenLabs TTS** Flash via `ELEVENLABS_VOICE_ID`, Magpie fallback via `TTS_PROVIDER`). First 2 hours: Photon line → SIP (TLS 5061, G.711) → Twilio SIP Domain → `<Connect><Stream>` → Pipecat (or LiveKit SIP); not working by T+2 → Twilio number, tell Yuvan. (1) Calls to the demo number forward to Maya's phone and post `call.started` / `call.ended` to `POST /events` (example `contracts/fixtures/event.call_started.json`; attestation/seen_before come from config for the demo). Never record or analyze the scammer-to-Maya call. (2) Serve `POST /internal/call` (`CallRequest`, example `callreq.t2.json`): call Maya, follow the call script in docs/PLAN.md (never ask for a PIN or code), post every line to `POST /cases/{id}/events` (`CaseEventRequest`, kind `transcript`), and send spoken yes/no to `POST /actions/{id}/approve|reject` with `via: voice`. Edge rule: "it was me" while the scam call is still active → don't release, ask her to hang up first. Target: first words < 2 s. Port 8100.

**Lane 5 · Karthik · Codex:** create `messaging/` in TypeScript with Photon `spectrum-ts` (webhook mode, dedupe on `message.id`, verify HMAC). Port 8200. (1) Serve `POST /internal/send` (`SendRequest`, example `send.alert.json`): deliver by iMessage (SMS fallback), never add links. Kinds: `heads_up`, `alert`, `question`, `recovery_step`, `summary` (render `IncidentSummary` as one readable text). (2) Inbound: forwarded text/screenshot → `POST /events` type `message.forwarded`; any reply → `POST /events` type `customer.reply` (with `case_id`) and `POST /cases/{id}/events`. Use Nemotron Nano (`MESSAGING_LLM_BASE_URL`) to read free-form replies: YES/NO → `POST /actions/{id}/approve|reject` with `via: sms`; REPORT → FTC draft; UNDO → safe-release flow (the brain refuses while a suspicious call is active). Trusted contact only after approval. (3) Tell Yuvan whether Photon 2.0 gives an SMS number. (4) `db/`: Supabase migration from docs/DATABASE.md; `watcher/`: 24 h watch that posts events back to the brain.

## QA (Lane 2a from T+10, once data + tools are done)
> Every hour: pull main, start everything with scripts/dev.sh in DEMO_MODE, run the T2 scenario from PACK_SPEC end to end with playwright-cli plus a scripted call. Time each beat. File each failure or slow beat as an issue labeled with the owning lane and `demo-blocker` or `polish`.

## Integration checkpoints
T+4 web ↔ real brain · T+8 portal → Guardian → iMessage end to end · T+12 T2 full scenario incl. voice call · T+16 everything incl. ML + face · T+18 freeze.
At each checkpoint, everyone merges and Lane 1 runs the T2 scenario with a stopwatch.
