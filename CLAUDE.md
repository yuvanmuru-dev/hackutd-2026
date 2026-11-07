# CLAUDE.md

Claude Code reads this file at the start of every session. Keep it short.

@AGENTS.md

## Hackathon mode (HackUTD 2026, 24 hours)
- Tracks: NVIDIA confirmed (Nemotron/NVIDIA models, multi-step agent, real tool/API use, not a chatbot). Tracks locked: NVIDIA + T-Mobile + Photon. Product: Titan, see docs/PACK_SPEC.md.
- Priority: working demo > judge-visible polish > code quality > tests. Never break the demo path.
- This session (Claude Code) is Lane 1 "Spine" and the integrator. See docs/LANES.md.
- Before writing code for a new feature: plan in 5 bullets max and wait for "go".

## Design rules (UI work)
- Use `design-taste-frontend` for any page. After building, run `web-design-guidelines` on changed files.
- Call single domain skills while building (`better-typography`, `better-layout`, `better-writing`). Run `better-interface` once before demo polish.
- Screenshot with playwright-cli at 1440px and 390px and fix what looks off.
- If I paste a Figma link, pull the frame with the Figma MCP before coding it.
