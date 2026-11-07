# Game plan (read this first)

Status: tracks not announced. NVIDIA is our confirmed track (Nemotron / NVIDIA models required).
Second track: open. Nothing below is tied to a domain until we pick one at kickoff.

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

## The 4 "not ChatGPT" features (domain-agnostic; every idea must support them)
1. **Ask-the-other-party email**: agent drafts + sends an email (AgentMail) to the counterparty about the contradictions it found, then reads the reply in the same thread and updates the report.
2. **Watchlist + alerts**: save a subject; a scheduler re-runs the check and notifies by email or phone call on change.
3. **On-the-spot voice**: phone the agent mid-situation (touring a property, at a dealership, after an accident). It answers with tools and tells you what to ask.
4. **Evidence view**: map/visual layer next to each finding (map if the domain is location-based, document highlight if doc-based).

## NVIDIA model stack (more NVIDIA surface area = stronger NVIDIA judging)
Verify every slug on build.nvidia.com at kickoff; swap in `.env` if one 404s.
| Job | Model family |
|---|---|
| Planner / tool-calling brain | Nemotron Super (`nvidia/nemotron-3-super-120b-a12b`) |
| Fast voice LLM | Nemotron Nano (`nvidia/nemotron-3-nano-30b-a3b`) |
| Speech in / out | Nemotron ASR streaming + Magpie TTS (NVCF, Pipecat services) |
| Read photos, PDFs, flyers, bills | Nemotron Nano VL (vision) |
| Search our own docs (policies, manuals) | NeMo Retriever embed + rerank NIMs |
| Guardrail on transcripts / outbound messages | Nemotron Safety Guard |

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
| T+14 | All 4 "not ChatGPT" features working on the happy path. |
| T+18 | **Feature freeze.** Only bug fixes, polish, demo mode. |
| T+20 | Record backup demo video (offline DEMO_MODE). |
| T+21 | Devpost written, repo cleaned, pitch rehearsed 3×. |

## Rules that win hackathons
- **The demo path never breaks.** Every lane keeps `main` runnable. DEMO_MODE replays cached tool results when Wi-Fi dies.
- **Cut order if behind at T+14:** map view → watchlist scheduler (fake it with a "re-check now" button) → outbound call. Never cut: web live run, voice inbound, email reply.
- **Disclose** the starter kit (agent loop + tools + vendored skills) as pre-event boilerplate in the Devpost.
- 3-minute pitch: problem (20s) → live phone call on speaker (45s) → email receipt + counterparty email (40s) → web run with streaming steps + evidence view (45s) → why-not-ChatGPT table + NVIDIA stack (30s).
