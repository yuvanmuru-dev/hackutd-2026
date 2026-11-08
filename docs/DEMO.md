# Demo plan: a 2-minute video and 5-minute judging

> **Domain locked.** The video beats for Tell are in docs/PACK_SPEC.md and replace the generic table below. Editing rules, judging format, pre-stage checklist and Q&A prep here still apply.

Two formats, one story. Every beat shows a core feature (GAMEPLAN #1–9), never a slide about one.
Fill the domain-specific lines at T+1 in PACK_SPEC.md. Timing is fixed now.

## The story (both formats)
"You're in the middle of [situation]. Someone is telling you [claims]. You call our number..."
Then the agent checks the claims against real data, asks you before it acts, follows up for you, and remembers when you call back.

## 2-minute video (record at T+20, edit, cap 2:00)
| Time | Beat | On screen | Features |
|---|---|---|---|
| 0:00–0:10 | Hook: the problem in one sentence + product name | Face cam or bold title over the real situation | |
| 0:10–0:40 | **Phone call** on speaker. Split screen: phone left, `/case/[id]` right with transcript + tool calls animating in | Live call view | 8, 2 |
| 0:40–1:00 | Agent's answer → open the report: contradicted finding, source link, "checked twice" badge, map | Report page | 3, 9 |
| 1:00–1:20 | Agent asks "want me to email them?" → **text YES** → email sent → counterparty reply lands in the same thread and the case updates | Phone SMS + inbox + case timeline | 5, 6 |
| 1:20–1:35 | "Re-check now" on the watch → change detected → **phone rings** with an alert. Caller: "any update?" → "Welcome back, they replied..." | Phone + case page | 7, 1 |
| 1:35–1:52 | Accuracy number from evals + NVIDIA stack strip (Nemotron Super, Nano, ASR, Magpie, VL, Safety Guard) | One clean frame | 4 |
| 1:52–2:00 | Name, tagline, team | End card | |

**Editing rules for time**
- Show any agent wait at real speed for about 2s so it's believable, then speed-ramp 3–4× **with a visible "4×" label**. Judges punish hidden edits more than slow agents.
- Record each beat as its own clip at 1440×900 (OBS or QuickTime) in DEMO_MODE, so takes are repeatable. Record the voiceover separately and lay it over.
- Cut dead air between channels with a hard cut. Never cut inside a tool result.
- Captions on: judges often watch muted.
- Voiceover: record it with ElevenLabs (one consistent narrator voice, regenerate any line in seconds). This doesn't touch the product's model rules.
- If DEMO_MODE served the tool results, the voiceover says "replaying a recorded run" or the frame says it. Stay honest.

## 5-minute live judging (about 2:30 talking, about 2:30 questions)
| Time | Beat |
|---|---|
| 0:00–0:20 | Hook + the why-not-ChatGPT line: "ChatGPT gives you an opinion. We give you evidence, act on it, and keep watching." |
| 0:20–1:20 | **Live call on speaker** while the judges watch `/case/[id]` on the laptop. This is the one live AI moment. |
| 1:20–1:50 | Text YES → show the email that went out + the counterparty reply that came back (pre-staged earlier, say so) |
| 1:50–2:15 | Call back: "Welcome back..." → case memory across channels |
| 2:15–2:30 | Accuracy number + NVIDIA stack. Stop talking. |
| 2:30–5:00 | Questions |

**DEMO_MODE: the safety net for Wi-Fi and rate limits**
- Record once after the final prompt/data changes: brain with `MOCK=0 LLM_CACHE=record`, then `python scripts/record_demo.py` (plays T2 → T5, T1, T3 and a forwarded screenshot; texts nobody). Commit `agent/core/recordings/llm_cache.json`.
- On stage: brain with `MOCK=0 DEMO_MODE=1`. Matching Nemotron prompts are answered from the recording at their recorded pace; anything new runs live. Verified: 29/29 calls replayed across T2, T1, T3 with no network to NVIDIA needed.
- The dashboard shows "Demo mode: replaying recorded Nemotron answers…". Say it if asked; never present a replay as live inference.
- Re-record after any change to agent prompts, tools, data or models (stale recordings just fall through to live).

**Pre-stage before every judging slot** (owner: Lane 2 checklist)
- [ ] DEMO_MODE on and cache warmed. Brain, voice and email are up. Tunnels are up.
- [ ] One case already has history: report done, counterparty reply already received. Long waits happen *before* judges arrive.
- [ ] Laptop: tab 1 `/case/[id]` full screen, tab 2 report. Phone on speaker, number saved as a contact.
- [ ] The 2-minute video is queued in a tab as the fallback if anything fails. Switch to it without apologizing.
- [ ] Hotspot on.

## Rehearsal and judging runbook (Titan)
**Roles** (decide once, keep them): **Maya** holds the demo iPhone and drives the portal laptop · **Scammer** calls Maya's number from a second phone · **Narrator** stands at the projector (dashboard) · **Console** runs `/console` backstage and watches the preflight.

**T-10 min: set up (console person)**
1. One machine runs everything: `MOCK=0 bash scripts/dev.sh` (add `DEMO_MODE=1` for judging). Karthik's messaging service must be running with his Photon credentials (it's what actually sends iMessages). Voice too, if the upgraded Twilio number is live.
2. `python scripts/preflight.py` (or `--for judging`). Fix every ❌ before going on. Warnings are OK if you know why.
3. `curl -X POST localhost:8000/demo/reset`. Open on the projector: `/guardian` (it waits for the case). On the portal laptop: `/portal/security`.
4. Maya's phone: Messages open, sound on. Scammer's phone: Maya's number ready to dial.

**The run (about 2 minutes)**
| Beat | Who | Action | Judges see |
|---|---|---|---|
| 1 | Scammer | Calls Maya's demo number; Maya answers on speaker | Heads-up iMessage on Maya's phone; dashboard call bar "unverified" |
| 2 | Maya | On the portal, turns off Port Out Protection | **Pause screen**; Maya taps "I'm doing this on my own" (shows a coached victim pushing through) |
| 3 | Maya | Taps "Generate transfer PIN" | "Ready in 24 hours" hold; dashboard: Context → Risk → Verifier → Response light up; verdict "Coached victim" |
| 4 | Narrator | Points at the dashboard | Port Out Protection re-locked, PIN held; alert iMessage arrives |
| 5 | Maya | Doesn't reply (or replies NO) | Titan calls Maya as a second call (if voice is live); otherwise recovery questions arrive by text |
| 6 | Maya | Answers YES to each recovery step | Steps check off on the dashboard |
| 7 | Narrator | Shows Maya's phone / `/case` page | Incident summary: what happened, what Titan did, "spot it next time" |
| 8 | Console | `POST /demo/play/t5` | "Reported number calling again" heads-up: the after-the-scam protection |

**If something breaks**: switch the projector to the backup video without apologizing; or play the same beat from `/console` (Play T2) with DEMO_MODE on. Never claim a replay is live.

## Speed budget (engineering targets, see CONTRACTS.md)
- Voice: first words < 2s (Nemotron Nano, short tool answers; `full_check` speaks while the run continues).
- Web run: first step < 1.5s, full report < 25s live, < 8s in DEMO_MODE (cached tools, still real model calls).
- Parallel tool calls. The verification pass checks findings in parallel.
- If a beat runs over budget at the T+14 checkpoint, pre-stage that beat instead of shrinking the feature.

## Q&A prep (everyone memorizes the answer for their lane)
| Likely question | Answer owner | Answer shape |
|---|---|---|
| Why not just use ChatGPT? | Yuvan | Evidence from live authoritative data with sources, acts with your approval, remembers across phone/email/web, keeps watching |
| How accurate is it? | Lane 2 | The eval number, how many cases, what it gets wrong |
| What about hallucinations? | Lane 1 | Every finding needs a source; a second Nemotron pass downgrades anything unsupported. Show a downgraded example |
| What if a data source is down? | Lane 2 | Finding becomes `unverifiable` with the reason; cache; never guesses |
| Is it safe to let an AI email or call people? | Lane 5 | Nothing goes out without your YES; Safety Guard screens drafts; full audit trail on the case |
| Why these NVIDIA models? | Lane 4 | Super for planning/tool calls, Lightning/Nano for voice latency, Nemotron ASR for speech-to-text (ElevenLabs voice, Magpie as fallback), VL for documents, Safety Guard for outbound. Voice models optionally self-hosted on Brev for the judging slot |
| What's real vs mocked? | Lane 1 | Be exact. Name anything pre-staged or cached |
| Who pays / what's next? | Yuvan | One sentence, from PACK_SPEC |
