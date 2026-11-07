# Kickoff checklist (T-3h → T+0:30)

## Before hacking starts (no product code; accounts + setup only)
Owner in brackets. Tick in the team chat, not here.
- [ ] [Yuvan] Repo created, all 3 teammates added as collaborators, everyone has cloned it
- [ ] [Yuvan] build.nvidia.com API key works: `curl` one chat completion with `nvidia/nemotron-3-super-120b-a12b` and one with the nano model. Note any slug that 404s.
- [ ] [Voice owner] Twilio trial account, one phone number, every teammate's phone verified as a caller ID
- [ ] [Voice owner] NVCF access for Nemotron ASR + Magpie TTS confirmed with the same NVIDIA key
- [ ] [Yuvan] ElevenLabs API key in `agent/.env` (`ELEVENLABS_API_KEY`). Pick the agent's voice ID in the Voice Library and note it
- [ ] [Email owner] AgentMail: console.agentmail.to → API key → create 1 inbox, note the address
- [ ] [Email owner] Supabase project created; URL + service key shared **via a password manager or DM, never in git or the group chat**
- [ ] [Yuvan] Claim the team's $60 Brev credits (one pool for the whole team). Don't start a GPU yet
- [ ] [Voice owner] Note Brev's hourly price for A100 80GB / H100 / L40S, and which have stock
- [ ] [Everyone] Each person uses **their own** NVIDIA API key, so 5 agents don't share one rate limit
- [ ] [Everyone] ngrok or cloudflared installed and logged in (Twilio + AgentMail need public webhooks)
- [ ] [Everyone] Python 3.11+, Node 20+, `uv`, Codex CLI working; open the repo once in Codex so it reads AGENTS.md
- [ ] [Everyone] `brew install gitleaks && bash scripts/install-hooks.sh` (blocks commits that contain keys)
- [ ] [Everyone] Copy `agent/.env.example` → `agent/.env` and fill in your own keys
- [ ] [Web owner] Pick 2–3 visual references (Dribbble, Mobbin, awesome-design-md) for the design-taste skill
- [ ] [Anyone] Read the idea bank in GAMEPLAN.md; come with one opinion each

## T0 → T+0:30 (tracks announced)
1. Read every track prompt and prize. Paste them into `docs/TRACKS.md` (5 min). Check two things: is there an ElevenLabs prize (MLH events often have one), and does the NVIDIA track text say anything about non-NVIDIA speech models? Those two answers set `TTS_PROVIDER`.
2. Score the idea bank with the kickoff rubric in GAMEPLAN.md (15 min). Commit. No re-litigating after this.
3. Fill `docs/PROJECT_BRIEF.md` for the chosen idea (5 min, Lane 1 with Claude).
4. Everyone pastes their Phase 0 prompt from LANES.md. Lane 1 ships MOCK mode first.
5. Lane 1 writes `docs/PACK_SPEC.md` (by T+1:00), then everyone pastes the Phase 1 follow-up.

## Demo safety (owner: Lane 2, by T+18)
- DEMO_MODE cache warmed for all 3 demo inputs
- Backup video recorded
- Phone hotspot as the Wi-Fi fallback
