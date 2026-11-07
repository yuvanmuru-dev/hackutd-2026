# HackUTD 2026: Titan

**Tracks: NVIDIA + T-Mobile (Safe Signal) + Photon.**
Titan sits on top of T-Mobile's existing protections and uses behavioral biometrics plus a Nemotron agent to catch account takeovers and coached-victim scams at the moment they happen, then reaches the customer on iMessage or a call through Photon.

Start here, in order:
1. **docs/PLAN.md**: the merged plan on one page (read this first)
1a. **docs/ARCHITECTURE.md**: components, the fast gate + agent workflow, endpoints, folders
1b. docs/PACK_SPEC.md: full details: data rules, threats, ML, demo
2. docs/TRACKS.md: all track prompts and why we picked these three
3. docs/LANES.md: who owns what, plus the prompt to paste into your agent
4. docs/CONTRACTS.md + contracts/: the API everyone builds against (v0.3 for Titan is in progress)
5. AGENTS.md: rules every coding agent follows
6. docs/GAMEPLAN.md, docs/DEMO.md, docs/KICKOFF.md: architecture, timeline, judging plan (PACK_SPEC wins where they differ)

Starter quick check (pre-event boilerplate):
`cd agent && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python test_loop_offline.py`
