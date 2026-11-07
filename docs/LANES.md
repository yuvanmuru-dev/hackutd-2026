# Lanes: 5 agents, zero merge conflicts

Fill names at kickoff. Each lane owns its folders. **Touch another lane's folder only through a PR that owner approves.**
Lane 1 is the integrator: owns `contracts/`, `agent/server.py`, `agent/core/`, `CLAUDE.md`, `AGENTS.md`, and merges to `main`.

| Lane | Human · agent | Owns (folders) | Branch | Done = |
|---|---|---|---|---|
| 1 Spine | Yuvan · Claude Code | `agent/server.py`, `agent/core/`, `contracts/`, `docs/`, root md files | `lane/spine` | Real SSE streaming run with typed events, runs/actions/watches endpoints, DB writes, mock mode |
| 2 Packs + data | Yuvan · Codex | `agent/packs/<pack>/` (tools, prompt, fixtures), `agent/cache/` | `lane/packs` | Domain tools with `source` on every result, DEMO_MODE replay, Nemotron VL doc reading |
| 3 Web | [Teammate A] · Codex | `web/` | `lane/web` | Landing + run page (live timeline) + report + evidence view + share page + watch list |
| 4 Voice | [Teammate B] · Codex | `voice/` | `lane/voice` | Inbound call answers with tools; outbound alert call; "email me the receipt" |
| 5 Email + memory | [Teammate C] · Codex | `email/`, `db/`, `watcher/`, `DEVPOST.md` | `lane/email` | Forward-to-inbox → report reply; counterparty email + reply tracking; Supabase schema; watcher loop |

## Git rules (every agent follows these)
- Branch from `main`, commit small, `git pull --rebase origin main` at least every hour and before every PR.
- PR into `main` with title `[lane N] what changed`. Lane 1 merges. Never force-push `main`.
- Contract change? Open a PR titled `contract: ...` touching only `contracts/` + `docs/CONTRACTS.md`. Don't hand-edit around it.
- `main` must always run. If your merge breaks the demo path, revert first, fix second.
- Never commit `.env*` (except `.env.example`). Add new env var *names* to the `.env.example` in your folder.

## Phase 0 prompts (paste at T0, before the domain is final; everything builds against the mock)

All Codex prompts start with:
> Read AGENTS.md, docs/GAMEPLAN.md, docs/CONTRACTS.md and the Lane N section of docs/LANES.md. Skills are in `.claude/skills/<name>/SKILL.md`; read the ones I name before starting. Plan in 5 bullets, then build. Stay inside your lane's folders.

**Lane 1 (Claude Code):**
> Build the brain spine in agent/ to docs/CONTRACTS.md. (1) `MOCK=1` mode that serves contracts/fixtures for every endpoint, with SSE replayed at 400ms per event. Ship that within 30 min and tell the team. (2) Real `/runs/stream`: run the agent loop on a worker thread, push typed StepEvents through a queue, so the browser sees steps as they happen. (3) Pack loader: `ACTIVE_PACK` env picks `agent/packs/<pack>/` (tools.py exporting TOOL_SCHEMAS + TOOLS, prompt.md). (4) Final report via a separate structured call so parsing never fails. (5) runs/actions/watches stored in Supabase via db/ schema from lane 5; in-memory fallback if no DB.

**Lane 2 (Codex):**
> Build agent/packs/ infrastructure: a tool-result cache keyed by (tool, args) on disk under agent/cache/, `DEMO_MODE=1` that serves only cached results, and a record script that warms the cache for our demo inputs. Port the existing agent/tools.py into agent/packs/example/ as the reference pack. Add a `read_document` tool using a Nemotron vision model on build.nvidia.com (verify the slug) that turns a PDF or image into text plus extracted claims. Every tool returns a `source` URL.

**Lane 3 (Codex):**
> Read .claude/skills/design-taste-frontend, better-layout, better-typography. Create web/ with Next.js (App Router, TypeScript) + Tailwind. `NEXT_PUBLIC_BRAIN_URL` points to the brain (mock is fine). Pages: `/` input (text + file drop), `/run/[id]` live timeline from /runs/stream (each StepEvent animates in; tool calls show tool + source), then the report: score, finding cards by verdict with source links, suggested-action buttons that POST /actions, "Watch this" that POSTs /watches. `/r/[id]` read-only share page. Leave an `<EvidenceView>` slot that renders a MapLibre map when evidence_view.kind=="map". No domain copy yet; use neutral placeholders.

**Lane 4 (Codex):**
> Read .claude/skills/nemotron-voice-agent-builder (cloud profile, no GPU). Build voice/ as a Pipecat bot with Twilio Media Streams: Nemotron ASR streaming + Magpie TTS via NVCF, LLM nvidia/nemotron-3-nano-30b-a3b via integrate.api.nvidia.com. On start, load tools from GET $BRAIN_URL/tools and run them via POST /tools/{name}; add one extra tool `full_check(text)` that POSTs /runs with channel "voice" and speaks `summary`, and `email_receipt(email)` that POSTs /actions. Also expose POST /internal/call for outbound alert calls. Use the mock brain until lane 1 is live.

**Lane 5 (Codex):**
> Read .claude/skills/agentmail and agentmail-toolkit. (1) db/: Supabase SQL migration for runs, steps, actions, watches, messages (owner_ref text, no auth for the demo; RLS off is OK for the hackathon, note it in docs/SECURITY.md). (2) email/: FastAPI service on 8200 with POST /webhooks/agentmail: inbound mail → POST $BRAIN_URL/runs (channel email, attachments passed through) → reply in-thread with the report as clean HTML with source links. POST /internal/send for outbound counterparty emails; when a counterparty replies, PATCH the action on the brain. (3) watcher/: loop that re-runs due watches, diffs findings vs the last report, and notifies via email/voice internal endpoints when something changed.

## Phase 1 (after the idea is chosen)
Lane 1 posts a short `docs/PACK_SPEC.md` (claims we check, tools + data sources, demo inputs, counterparty, the 3-minute demo script).
Every lane then gets a one-line follow-up prompt: "Read docs/PACK_SPEC.md and apply it to your lane: domain copy, demo inputs, and the parts of the demo script you own."

## Integration checkpoints
T+4 web ↔ real brain · T+8 all doors on the real brain · T+14 all four "not ChatGPT" features · T+18 freeze.
At each checkpoint, everyone merges, Lane 1 runs the demo script end to end, and bugs go to the owning lane.
