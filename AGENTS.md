# AGENTS.md (read by Codex and Claude Code)

7 agents build this repo in parallel. These rules keep us from colliding.

## Read first
0. docs/PLAN.md + docs/PACK_SPEC.md: what we are building (Titan). They win over older docs
0b. docs/ARCHITECTURE.md (+ DATABASE.md, SECURITY.md): how it fits together
1. docs/GAMEPLAN.md: architecture and why it beats ChatGPT
2. docs/CONTRACTS.md + contracts/schema.json: the API every lane builds against
3. docs/LANES.md: your lane, your folders, your branch
4. docs/DEMO.md: the 2-minute video and the 5-minute judging script. Build for those beats first
5. docs/PACK_SPEC.md (once it exists): the chosen domain

## Architecture in one line
One brain (`agent/`, FastAPI + Nemotron) with many doors (`web/`, `voice/`, `messaging/`) plus `watcher/`.
Doors call only the brain's HTTP API. Only the brain calls data APIs. Domains are packs in `agent/packs/<pack>/`.

## Hard rules
- **Stay in your lane's folders.** Need a change elsewhere? Ask the owner or open a PR they approve.
- **Contracts are law.** Don't change a request/response shape locally. Open a `contract:` PR (Lane 1 merges).
- **Build against the mock** (`MOCK=1` brain) until the real endpoint exists. Don't block on other lanes.
- **All reasoning runs on NVIDIA models** (Nemotron LLMs, Nemotron VL, NeMo Retriever, Safety Guard) via build.nvidia.com with `NVIDIA_API_KEY`. No other LLM providers.
- **Speech:** Nemotron ASR for speech-to-text. **ElevenLabs is the default TTS** (`TTS_PROVIDER=elevenlabs`, Flash model for latency); Magpie TTS is the NVIDIA fallback. ElevenLabs is never used as the LLM.
- **Every fact shown to a user has a source URL.** No source → verdict `unverifiable`.
- **Never commit secrets.** Keys live in `*/.env` (gitignored). Add new var names to that folder's `.env.example`.
- `main` always runs. Pull with rebase hourly. Small commits. PR title: `[lane N] what changed`.
- Outbound email/calls only go to teammates' own addresses and numbers during the hackathon.
- Before coding: plan in ≤5 bullets. After: say what you ran and what you didn't verify.

## Skills (in `.claude/skills/<name>/SKILL.md`; Codex should open and read them)
- UI: `design-taste-frontend`, `web-design-guidelines`, `better-layout`, `better-typography`, `better-colors`, `better-ui`, `better-accessibility`, `better-writing`, `find-animation-opportunities`, `better-interface` (full review, once)
- Image/mockup/screenshot → code: `screenshot-to-code` (in this repo: target is `web/`, Next.js App Router + Tailwind v4; use `playwright-cli` for the render-and-compare step; apply `design-taste-frontend` tokens over guessed ones)
- Voice: `nemotron-voice-agent-builder` (cloud profile, no GPU)
- Email: `agentmail`, `agentmail-toolkit`
- Browser testing/screenshots: `playwright-cli`

## Commands (verified)
- Everything: `bash scripts/dev.sh` (brain in MOCK mode + any doors present; `TUNNEL=1` adds ngrok)
- Brain only: `cd agent && MOCK=1 uv run --no-project --with-requirements requirements.txt uvicorn server:app --reload --port 8000` → http://localhost:8000/docs
- Play the demo story: `curl -X POST localhost:8000/demo/play/t2` (also `t1`, `t3`), then `GET /cases`
- Brain tests: `cd agent && python test_loop_offline.py && python test_mock_offline.py`
- Contracts: `python scripts/validate_contracts.py`; after a contract change: `bash scripts/gen_types.sh`
- Web: `cd web && npm run dev` (3000) · Voice: 8100 · Messaging: 8200

## Pre-event code
`agent/` (agent loop + 4 public-data tools), `scripts/`, and `.claude/skills/` came from a starter kit prepared before the event. Disclose this in the Devpost.
