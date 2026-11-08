# Lane 1 takeover (Karthik's Codex, from ~10:05 am Nov 8)

You are now **Lane 1: Spine + integrator** for Titan. Read `AGENTS.md`, `CLAUDE.md`, `docs/DECISIONS.md` (D-001 → D-064) and `docs/DEMO_SCRIPT.md` first.

## Rules that do not change
- **Merge only with Yuvan's explicit OK** ("yes, merge #N"). Review first: CI green, files stay in the lane, run the relevant offline tests. If it touches the demo path, try it live.
- Decisions go in `docs/DECISIONS.md` **on main only** (commit straight to main), as `D-0xx`.
- Never print or commit secrets (`*/.env`). Share keys only by DM/AirDrop.
- Titan never asks for a PIN/code/password, never sends links (defang `x[.]co`), and only automates **safer** changes. Loosening needs Maya's approval and no suspicious call (brain returns 409). One approval rule for text and voice (D-063): a clear yes approves the one pending **safer-only** step.
- The ML model is **frozen** (`67fe7df`, D-053). Never edit `agent/packs/guard/ml/`. Routing: calls → hybrid ML+rules, forwarded texts → rules (D-060).
- **One Titan machine only** (Karthik's laptop) on the Photon line: two copies double every text/call. `scripts/record_demo.py` must run against a brain with `MESSAGING_URL= VOICE_URL=` (it auto-approves; it refuses otherwise).
- Photon throttles back-to-back calls (D-061): one call per take; read `/demo/outbox` + `[voice]` logs before retrying.

## State at handoff (main = `e90e7c4` + PR #80 open)
- Merged today: #45/#48/#75 (T-Mobile-style portal + guardian), #57 ML, #59/#65/#66/#69 sealed eval + Devpost numbers, #61/#71/#74 Photon voice (Nemotron-led, D-063), #62/#63 Brev, #64/#68/#70 brain text + SSE fixes, #67 routing, #72 STATUS/LOCK/HELP texts (D-062), #73 Face ID (off by default, D-064), #76 typing rhythm, #77/#79 "help me" calls immediately and always.
- **Open: PR #80**: call facts made speakable (voice refused a fact with a 3+ digit number → SpeechBlocked). Tests pass; needs Yuvan's OK, then `git pull` on the Titan machine and one call to confirm.
- Brev: `nemotron-nano` at the URL in `agent/.env` (Brev box must be **started**, then `docker start nano` in its Jupyter terminal). Brain falls back to hosted NVIDIA if it's down. **Stop, then delete the Brev box after judging** ($4.08/hr).

## Run it (Titan machine)
- `MOCK=0 bash scripts/dev.sh` (brain 8000, web 3000, messaging 8200, voice 8100). `voice/.env` needs `VOICE_CONVERSATION_ENABLED=true` until judging ends.
- `uv run --no-project --with-requirements agent/requirements.txt python scripts/preflight.py` (ignore the stale "voice tunnel" / "different phones" lines).
- Before every take: console **Reset demo data** → reload the portal → **Call starts** first. No `git pull` or file edits during a take (auto-reload wipes the in-memory case).
- Debug a missing call: `curl -s localhost:8000/demo/outbox` → `call -> http 202` means voice accepted it; then read the `[voice]` lines (`intervention.setup_failed`, `sip_status_code`, `SpeechBlocked`).

## Tests
`cd agent && for t in test_mock_offline test_workflow_offline test_demo_mode_offline test_llm_offline test_commands_offline test_rhythm_offline test_help_call_offline test_face_offline; do python $t.py; done` · `python scripts/validate_contracts.py` · `python scripts/check_lane.py <branch> origin/main`.

## Remaining before judging (~noon)
1. Merge #80 (Yuvan OK), confirm one live call on Karthik's laptop.
2. Rehearse `docs/DEMO_SCRIPT.md` once, record the video (`REPLY_TIMEOUT_S=15` for recording only).
3. Optional backup: DEMO_MODE recording with doors off (see `scripts/record_demo.py` header), then judging brain with `DEMO_MODE=1` only if Wi-Fi/models fail.
4. Devpost: numbers from `evals/DEVPOST_NUMBERS.md`; disclose pre-event starter code (AGENTS.md).
5. After judging: Brev stop → delete; set `VOICE_CONVERSATION_ENABLED=false`.
