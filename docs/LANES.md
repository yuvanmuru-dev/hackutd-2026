# Lanes: 7 agents in parallel, zero merge conflicts

Product: **Titan** (see docs/PACK_SPEC.md). Tracks: NVIDIA + T-Mobile + Photon. Pack name `guard`.

## How parallel works here
1. **Every agent owns folders nobody else touches.** Need a change elsewhere? Ask the owner or open a PR they approve.
2. **Contracts first.** Lane 1 ships contracts v0.3 + fixtures + a `MOCK=1` brain in the first hour. Everyone builds against the mock, so nobody waits on anybody.
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
| T+1:00 | 1 | contracts v0.3 + fixtures + `MOCK=1` brain + `scripts/dev.sh` | everyone |
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

## Prompts (paste into your agent)
Every prompt starts with:
> Read AGENTS.md, docs/PACK_SPEC.md, docs/CONTRACTS.md and your lane's row and prompt in docs/LANES.md. Skills are in `.claude/skills/<name>/SKILL.md`; read the ones named. Work through the open GitHub Issues labeled `<your label>` + `phase-1`, lowest number first. Plan in 5 bullets, then build. Stay inside your folders. Build against the `MOCK=1` brain until the real endpoint exists.

**Lane 1 · Yuvan · Claude:** contracts v0.3 (`AccountEvent`, `DeviceSimStatus`, `ProtectionState`/`ProtectionEvent`, `CallContext`, `PortalSignals`, `Signal`, `RiskScore`, `RiskDecision`, face result, dataset schema), fixtures for T1/T1b/T2/T3, `MOCK=1` brain, `scripts/dev.sh`. Then `POST /events` ingest + per-user timeline, trigger → Guardian run with real SSE streaming, Verifier pass, approvals + the pause-until-reply step, pack loader `ACTIVE_PACK=guard`.

**Lane 2a · Yuvan · Codex:** in `agent/packs/guard/` (not `ml/`): seeded generator for 5 personas × 90 days of account events + device/SIM registry + protection events + trigger snapshots (call context, location match), labeled scenarios T1–T5 + hard negatives (~300), written to the dataset schema. Commit a small seed set by T+1:30. Mock carrier protections service (state + actions: re-lock, transfer-PIN cool-off, revoke, reset PIN, sign out sessions, report to Scam ID). Tools with `source`: `account_history`, `device_sim_status`, `protection_status`, `call_context`, `location_match`, `portal_signals`, `check_message` (lookalike domain, RDAP age, URLhaus), `recent_scam_reports`, `policy_lookup` (NeMo Retriever over a short carrier policy + FTC guidance we write). Follow the data rule in PACK_SPEC: nothing from the "cut on purpose" list.

**Lane 2b · Ishan · Codex #2:** in `agent/packs/guard/ml/` and `evals/`: (1) per-persona Isolation Forest on normal sessions → anomaly 0–1. (2) XGBoost risk classifier (`takeover/coached/legit`) with isotonic calibration and SHAP top-5 reasons. (3) Scam text classifier: NeMo Retriever embeddings + logistic regression. (4) `score(user_id, event) -> RiskScore` matching contracts; ship a stub with the real shape by T+3. (5) `evals/run.py`: held-out scenarios built with unseen generator settings; precision, recall, false-positive rate per threat; calibration plot; ablation rules → +anomaly → +classifier. Start on the seed set; retrain when the full set lands.

**Lane 3a · Ishan · Claude:** read design-taste-frontend, better-layout, better-typography. Build `/guardian/[case]`, the projector hero screen, inside `web/app/guardian/` and `web/components/guardian/`, using 3b's shell and API client. Live from `/cases/{id}/stream`: the customer's timeline with the triggering sequence highlighted, the Guardian's plan and tool calls streaming in, risk score with calibrated confidence and top reasons, "checked twice" mark from the Verifier, protection actions taken, iMessage thread and call transcript in the same timeline, recovery steps checking off, and a "data used" panel listing exactly which records were read. Must read from the back of a room.

**Lane 3b · Ishan · Codex #1:** scaffold `web/` first (Next.js App Router, TypeScript, Tailwind v4, layout, theme tokens, typed API client from contracts) and push by T+0:45. Then `/portal`: neutral, unbranded carrier account (login with one-time code, SIM swap, add line, change email, Security page mirroring SIM Protection, Port Out Protection, transfer PIN generator, account PIN, call-blocking toggle). Behavior script in `web/lib/behavior/` sending derived numbers only (page path, time per step, hesitation, paste into PIN, `visibilitychange`, pointer speed, typing-rhythm summary), consent screen, no motion sensors. Sensitive actions → brain → show the decision ("Your PIN will be ready tomorrow"). `/console`: demo buttons that inject scripted events via `POST /events`. Last: optional face check toggle (`@vladmandic/human`, descriptor only in IndexedDB, blink/head-turn, sends `{match, similarity, liveness, antispoof}`).

**Lane 4 · Krishang · Codex:** read nemotron-voice-agent-builder. Build `voice/` (Pipecat, Nemotron Nano/Lightning, Nemotron ASR, Magpie TTS, `TTS_PROVIDER` switch, every endpoint from env). First 2 hours: Photon line → SIP (TLS 5061, G.711) → Twilio SIP Domain → `<Connect><Stream>` → Pipecat (or LiveKit SIP). Not working by T+2 → Twilio number, tell Lane 1. Our number sits in front of the demo phone and forwards to it, so each call emits a call-context event (active, duration, seen before, attestation) to `POST /events`. Never record or analyze the scammer-to-customer call. Titan's outbound call: talk her off the scam call, take spoken YES/NO and recovery approvals (`POST /actions/{id}/approve`), every transcript line to `POST /cases/{id}/events`. Target: first words < 2s.

**Lane 5 · Karthik · Codex:** create `messaging/` in TypeScript with Photon `spectrum-ts` (webhook mode, dedupe on `message.id`). Messaging agent: forwarded text or screenshot → `POST /runs` (channel `sms`) → reply with verdict + sources; alerts from `POST /internal/send`; free-form replies → YES/NO/question via Nemotron Nano → approve/reject or answer from the case; recovery walk-through one approval at a time; trusted contact only after approval. Check whether Photon 2.0 beta gives an SMS number; tell Lane 1. Then `db/` (Supabase schema for users, events, cases, runs, actions, watches, messages) and `watcher/` (24h watch, wakes the Guardian via `POST /events`).

## QA (Lane 2a from T+10, once data + tools are done)
> Every hour: pull main, start everything with scripts/dev.sh in DEMO_MODE, run the T2 scenario from PACK_SPEC end to end with playwright-cli plus a scripted call. Time each beat. File each failure or slow beat as an issue labeled with the owning lane and `demo-blocker` or `polish`.

## Integration checkpoints
T+4 web ↔ real brain · T+8 portal → Guardian → iMessage end to end · T+12 T2 full scenario incl. voice call · T+16 everything incl. ML + face · T+18 freeze.
At each checkpoint, everyone merges and Lane 1 runs the T2 scenario with a stopwatch.
