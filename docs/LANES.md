# Lanes: 7 agents in parallel, zero merge conflicts

Product: **Titan** (see docs/PACK_SPEC.md). Tracks: NVIDIA + T-Mobile + Photon. Pack name `guard`.

## How parallel works here
1. **Every agent owns folders nobody else touches.** Need a change elsewhere? Ask the owner or open a PR they approve.
2. **Contracts first.** Contracts v0.3 + fixtures + the `MOCK=1` brain are on main (PR #40). Everyone builds against the mock, so nobody waits on anybody.
3. **Interfaces, not files, connect lanes.** Data ↔ ML talk through the dataset schema in `contracts/`. Web, voice and messaging talk to the brain only over HTTP from docs/CONTRACTS.md.
4. **One branch per agent** (exact names in the table; CI checks them), PR to `main`, Lane 1 merges. Integration checkpoints below.

| # | Lane | Person · agent | Owns (only these) | Branch | Label | Working by |
|---|---|---|---|---|---|---|
| 1 | Spine | Yuvan · Claude | `agent/server.py`, `agent/core/`, `contracts/`, `docs/`, `scripts/`, root md files | `lane/spine` | `lane:spine` | Mock T+1, real brain T+6 |
| 2a | Data + protections | Yuvan · Codex | `agent/packs/guard/` **except** `ml/` | `lane/data` | `lane:data` | Seed data T+1:30, tools T+5 |
| 2b | ML model | Ishan · Codex #2 | `agent/packs/guard/ml/` | `lane/ml` | `lane:ml` | stub now, model T+10 |
| 2c | Evals (independent) | Yuvan · Codex | `evals/` | `lane/evals` | `lane:evals` | split now, numbers T+10 |
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

## Hand-off and prompts
**Everything a teammate and their agent need is in [docs/handoff/](handoff/README.md):** the 10-minute start, the exact prompt to paste, one detailed file per lane (story, existing pieces, exact interfaces, build order with checks, decisions, stop-and-ask list, definition of done, and a teammate guide for steering), and the question loop to Lane 1.

| Lane | Hand-off file |
|---|---|
| 2a Data + tools | [handoff/lane-2a-data.md](handoff/lane-2a-data.md) |
| 2b ML + evals | [handoff/lane-2b-ml.md](handoff/lane-2b-ml.md) |
| 3a Guardian | [handoff/lane-3a-guardian.md](handoff/lane-3a-guardian.md) |
| 3b Portal + shell | [handoff/lane-3b-portal.md](handoff/lane-3b-portal.md) |
| 4 Voice | [handoff/lane-4-voice.md](handoff/lane-4-voice.md) |
| 5 Messaging + db + watcher | [handoff/lane-5-messaging.md](handoff/lane-5-messaging.md) |

**Guardrails:** stop rules in AGENTS.md; settled choices in docs/DECISIONS.md; CI `lane-guardrails` fails a PR that edits another lane's folders, points at a non-NVIDIA LLM, uses the T-Mobile logo, or makes Titan ask for a PIN.

## QA (Lane 2a from T+10, once data + tools are done)
> Every hour: pull main, start everything with scripts/dev.sh in DEMO_MODE, run the T2 scenario from PACK_SPEC end to end with playwright-cli plus a scripted call. Time each beat. File each failure or slow beat as an issue labeled with the owning lane and `demo-blocker` or `polish`.

## Integration checkpoints
T+4 web ↔ real brain · T+8 portal → Guardian → iMessage end to end · T+12 T2 full scenario incl. voice call · T+16 everything incl. ML + face · T+18 freeze.
At each checkpoint, everyone merges and Lane 1 runs the T2 scenario with a stopwatch.
