# Game plan (read this first)

Status: **LOCKED 2026-11-07. Tracks: NVIDIA + T-Mobile (Safe Signal) + Photon. Product: behavioral scam guard, see docs/PACK_SPEC.md.**
PACK_SPEC.md overrides anything domain-specific below (idea bank, demo beats).

## The bet
We are not building a chatbot. We are building **one agent brain with many doors** that
**checks claims against real data, takes actions in the world, and keeps watching after you leave.**
The domain (real estate, insurance, cars, health bills, energy ops...) is a swappable "pack".

### Answer to "why not just use ChatGPT/Claude?" (memorize this, it's the pitch)
| ChatGPT | Us |
|---|---|
| Answers from training data / web pages | Queries authoritative live data (gov APIs, docs) for *your* exact case; every verdict links its source |
| You have to go to it | It's where you are: call it, email/forward it, or use the web. Same brain, same answer |
| Talks | **Acts**: emails the other party, places the call, files the form, tracks the reply |
| Forgets | **Watches**: re-checks on a schedule and calls/emails you when something changes |
| Opinion | **Receipt**: timestamped, shareable evidence record you can hand to a lender, landlord, adjuster, lawyer |

Judges should see all five in the demo. Each is a feature, not a slide.

## Core features (domain-agnostic; every idea must support them)
Approved: 1–5 must ship. 6–9 are what turns the brain into an ecosystem.

| # | Feature | Why judges care | Owner |
|---|---|---|---|
| 1 | **One case across every channel.** Every run, call, email, text and watch about one subject shares a `case_id`. Caller ID / sender email finds your case. | "Welcome back, they replied to your email." Memory + continuity ChatGPT doesn't have | L1 (model), L4/L5 (lookup) |
| 2 | **Live call on the web.** The voice bot streams its transcript + tool calls to the case page while you talk. | Judges *see* the agent think while it speaks | L4 (emit), L3 (case page) |
| 3 | **Second-pass verification.** A second Nemotron call checks each finding against raw tool output; unsupported findings get downgraded. "Checked twice" badge. | Direct answer to "why trust an AI?" + more NVIDIA surface | L1 |
| 4 | **Accuracy number.** 10–15 golden cases with known verdicts; `evals/` script prints % correct. Number goes in the pitch. | Almost no team shows a measured number | L2 |
| 5 | **Approve-before-act.** Every outbound email/call to a third party waits for YES (web button, SMS/email reply, or "go ahead" on the call). Safety Guard screens drafts. | Trust + safety story; also stops stray test emails | L1 (flow), L5 (SMS/email YES), L3 (button) |
| 6 | **Ask-the-other-party email** that tracks the reply in-thread and updates the case | It acts, not just talks | L5 |
| 7 | **Watchlist + alerts** by email or outbound call | It keeps working after you leave | L5 (watcher), L4 (alert call) |
| 8 | **On-the-spot voice** (call mid-situation, get what to ask) | Meets the user where they are | L4 |
| 9 | **Evidence view** (map or document highlight beside each finding) | Visual proof on the projector | L3 |

Stretch only if ahead at T+14: MCP server door (brain usable inside ChatGPT/Claude), SMS photo door (Nemotron VL on MMS).

## NVIDIA model stack (more NVIDIA surface area = stronger NVIDIA judging)
Verify every slug on build.nvidia.com at kickoff; swap in `.env` if one 404s.
| Job | Model family |
|---|---|
| Planner / tool-calling brain | Nemotron Super (`nvidia/nemotron-3-super-120b-a12b`) |
| Fast voice LLM | Nemotron Nano (`nvidia/nemotron-3.5-lightning-30b-a3b`) |
| Speech in / out | Nemotron ASR streaming (speech-to-text) + **ElevenLabs TTS by default** (Yuvan's Starter plan); Magpie TTS kept as the NVIDIA fallback via `TTS_PROVIDER`. Decided at kickoff |
| Read photos, PDFs, flyers, bills | Nemotron Nano VL (vision) |
| Search our own docs (policies, manuals) | NeMo Retriever embed + rerank NIMs |
| Guardrail on transcripts / outbound messages | Nemotron Safety Guard |

### Brev GPU ($60 credits for the whole team): use it, off the critical path
Free, so we use it, but nothing depends on it. Everything is built and demoed against hosted build.nvidia.com first; Brev is switched on by env vars and switched off the same way.
- **Owner:** Yuvan's Codex (data lane), after the data + tools are done (~T+5). Never Krishang (voice bridge is the riskiest lane).
- **One box** (L40S or A100; check Brev's console price first). Easiest path: a Brev Launchable / NIM container, not a hand-built stack.
- **Job 1, GPU training (30 min):** train the XGBoost risk classifier with `device="cuda"` (and RAPIDS cuML if easy) on the box. Pitch line: "trained on an NVIDIA GPU on Brev."
- **Job 2, self-hosted Nemotron Nano (1–2 h):** serve Nano (OpenAI-compatible) for the Messaging and Voice agents. Switch with `VOICE_LLM_BASE_URL` / a `MESSAGING_LLM_BASE_URL`. Removes rate-limit risk during rehearsals and judging.
- **Hours budget (~$60):** 2h at T+6 to set up and test, then stop · 4–6h for rehearsals from T+16 · on through judging. Stop it every time it's idle; owner posts start/stop in the team chat. **Never leave it running overnight.**
- **Fallback:** any problem → point the env vars back at build.nvidia.com and restart. One minute.

## Idea bank (score these at kickoff against the announced tracks)
All fit the same brain + doors + packs. Pick the one whose second track has the best prize *and* the best free data.

| # | Idea | Claim → evidence | Action | Watch | Free data that makes it real |
|---|---|---|---|---|---|
| A | **Groundtruth** (real estate / commercial lease) | Listing or broker flyer claims vs gov data | Email broker about contradictions | Price / flood-map change | Census geocoder, FEMA NFHL + National Risk Index, ACS, OSM |
| B | **Lemon check** (car buying) | Dealer claims vs VIN history | Email dealer to negotiate with evidence | New recall on your VIN | NHTSA vPIC decode, recalls, complaints, safety ratings (all free, no key) |
| C | **Claim copilot** (insurance) | Call after a storm/accident; agent corroborates with weather + photos | Drafts and sends the claim, follows up with the adjuster | Claim status / new storm alerts | NOAA/NWS alerts, NOAA storm events, FEMA disasters, photo via Nemotron VL |
| D | **Bill auditor** (medical / utility) | Forward a bill; agent checks charges vs published prices | Emails a dispute letter, calls the provider | Re-check when a new statement arrives | CMS price transparency, Medicare fee schedules, ERCOT/EIA rates |
| E | **Field-ops voice** (energy / industrial) | Tech calls hands-free; agent checks the manual + sensor data | Opens a work order, emails the supervisor | Equipment alerts | Uploaded manuals via NeMo Retriever, EIA, NWS |
| F | **Benefits navigator** (social good / fintech) | User describes situation by phone in any language | Fills and emails the application, schedules a reminder call | Deadline + status | Gov eligibility rules, multilingual Magpie TTS |

### Kickoff scoring (15 minutes, then commit, no re-litigating)
Score each 1–5, multiply prize weight: second-track fit ×2, free real data available ×2,
demo wow on stage ×2, all 4 features fit ×1, a teammate knows the domain ×1. Highest total wins.

## Timeline (T0 = hacking starts)
| When | What |
|---|---|
| T-3h → T0 | Accounts, repo, docs, env setup on every laptop (see KICKOFF.md). No product code. |
| T0 → T+0:30 | Tracks announced → score ideas → commit. Fill PROJECT_BRIEF.md. |
| T+0:30 → T+1:15 | Lane 1 freezes contracts v1 + mock server. All other lanes build against the mock. |
| T+4 | Integration 1: web shows a real streamed run from the brain. |
| T+8 | Integration 2: all three doors end-to-end on the real brain. |
| T+10 | Lane 2 switches to QA: runs the demo script hourly with playwright-cli, files bugs as GitHub Issues for the owning lane. |
| T+14 | Features 1–9 working on the happy path. Demo inputs locked. |
| T+18 | **Feature freeze.** Only bug fixes, polish, demo mode. |
| T+20 | Record the 2-minute video (see docs/DEMO.md). |
| T+21 | Devpost written, repo cleaned, pitch rehearsed 3×. |

## Rules that win hackathons
- **The demo path never breaks.** Every lane keeps `main` runnable. DEMO_MODE replays cached tool results when Wi-Fi dies.
- **Cut order if behind at T+14:** evidence map → watchlist scheduler (keep the "re-check now" button) → outbound alert call → accuracy evals. Never cut: web live run, voice inbound with case memory, live call on web, verification, approve-before-act.
- **Disclose** the starter kit (agent loop + tools + vendored skills) as pre-event boilerplate in the Devpost.
- Demo and judging scripts, timing and Q&A prep: docs/DEMO.md.
