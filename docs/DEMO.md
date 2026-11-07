# Demo plan: a 2-minute video and 5-minute judging

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

**Pre-stage before every judging slot** (owner: Lane 2 checklist)
- [ ] DEMO_MODE on and cache warmed. Brain, voice and email are up. Tunnels are up.
- [ ] One case already has history: report done, counterparty reply already received. Long waits happen *before* judges arrive.
- [ ] Laptop: tab 1 `/case/[id]` full screen, tab 2 report. Phone on speaker, number saved as a contact.
- [ ] The 2-minute video is queued in a tab as the fallback if anything fails. Switch to it without apologizing.
- [ ] Hotspot on.

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
| Why these NVIDIA models? | Lane 4 | Super for planning/tool calls, Nano for voice latency, ASR + Magpie for speech, VL for documents, Safety Guard for outbound |
| What's real vs mocked? | Lane 1 | Be exact. Name anything pre-staged or cached |
| Who pays / what's next? | Yuvan | One sentence, from PACK_SPEC |
