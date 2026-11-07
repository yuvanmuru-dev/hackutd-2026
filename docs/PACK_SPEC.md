# PACK_SPEC: behavioral scam guard (pack `guard`)

Tracks: **NVIDIA + T-Mobile (Safe Signal) + Photon**. Locked 2026-11-07.
Working name: **Tell** (a "tell" is the habit that gives someone away). PROPOSAL, rename freely. Don't use "Scam Shield" (T-Mobile's real product).

## The pitch in two sentences
Face ID proves it's you. It can't prove you're not being scammed. Tell can, because a carrier sees how your phone lives: who you talk to, where you go, which device you use. When the pattern breaks, Nemotron investigates, explains with honest confidence, and reaches you on iMessage or a call through Photon before your number or money is gone.
**Behavior is always on. The face check is optional.**

## Data: synthetic by design
T-Mobile's slide says "you create the data: synthetic scam messages and scenarios, no real customer data." So we build a **synthetic carrier**: a generator that produces 60 days of realistic network life for a set of personas, plus labeled attack scenarios. It is our demo world, our training baseline and our eval set. Live events from our real voice line, Photon messages and the web portal flow into the same timeline during the demo.

## Four behavior layers (main signal first)
| Layer | What we model per person | Source in the hackathon | Catches |
|---|---|---|---|
| **1. Network life pattern** (main, carrier only) | Contact graph (who you call/text, hashed), call lengths and hours, usual cell towers (home, work, commute), sleep window, device ID + SIM history, roaming, account activity and support channels you use | **Synthetic generator** (60 days/persona) + **live call events from our voice line** | T1 new device / SIM / location; T2 a long call from a never-seen number right before a sensitive action |
| **2. How you talk to Tell** | Reply speed, message length, punctuation/emoji, language. Stretch: voiceprint with NVIDIA TitaNet speaker verification (open source) | Photon iMessage replies (only messages sent to Tell), voice calls | Someone else answering "YES" for her; a different voice on the call |
| **3. How you handle the phone** (stretch) | Grip angle and tremor (motion sensors), tap position offsets, swipe shape | Mobile web `devicemotion` (one iOS permission prompt) | Different person holding her phone |
| **4. How you use the portal** | Page path and order, time per page, hesitation, paste into PIN fields, leaving the page (`visibilitychange`), typing rhythm as one small input | Behavior SDK in the web portal, derived numbers only | T1 attacker going straight to SIM swap; T2 dictated input, switching to the call/texts |

The scam tell is usually a **sequence across layers**, e.g. "22-minute call from a never-contacted number showing 'T-Mobile Support' → 3 minutes later a port-out PIN request from her own phone at home, with long pauses and an app switch." Numbers alone don't say *why*; that's the job for Nemotron.

## Synthetic carrier: what the generator makes (Lane 2)
- **Personas (5)**, each with a real routine so "unusual" means something:
  - Maya, 68, retired teacher. Small contact circle, home all day, never calls support.
  - Dev, 24, student. Many contacts, irregular hours, phone upgrades often.
  - Priya, 41, ER nurse on nights. 3am activity is normal for her.
  - Marcus, 35, sales rep. Travels weekly, new towers are normal for him.
  - Elena, 52. Mostly texts in Spanish, calls family abroad.
- **Event types:** `call`, `sms_meta`, `tower`, `device`, `sim`, `account` (login, setting change, SIM swap, port-out PIN), `portal_session` (layer 4 features), `tell_message` (layer 2 features). Metadata only, no content, except the scam texts users forward.
- **Attack scenarios, labeled:** T1 account takeover → SIM swap, T2 coached victim → port-out PIN, T3 smishing text, T4 bot credential stuffing, T5 follow-up "recovery scam" after T1/T2.
- **Hard negatives, labeled legit** (these make the false-positive rate honest): Marcus logs in from a new city, Priya changes a setting at 3am, Dev activates a new phone bought at a store, Maya has a long call with her real bank then updates her email.
- About **300 labeled scenarios**, seeded and reproducible. Nemotron writes the varied scam scripts and texts; Python generates the numeric events.

## How it works (fits the existing brain + doors)
1. **Events in:** synthetic history is preloaded; live events arrive from the voice line (`call` with caller ID, duration), Photon (`tell_message`), the portal (`portal_session`, `account`), and the **demo console** that injects scripted events on cue.
2. **Baselines + scoring (deterministic, fast):** per person and per layer: contact novelty, call-length percentile, tower familiarity, hour-of-day likelihood, device/SIM age, portal path likelihood, message-style distance. Output: signals with numbers and the baseline they're compared against. Nemotron never makes up numbers.
3. **Investigate (Nemotron Super agent):** a sensitive action starts a run. Tools: `get_timeline(user, window)`, `score_layers(user, event)`, `contact_history(user, number)`, `line_status(user)`, `device_history`, `tower_familiarity`, `check_message` (lookalike domain, RDAP domain age, URLhaus), `recent_scam_reports`, `policy_lookup` (carrier security policy + FTC guidance via NeMo Retriever). It reads the cross-layer sequence, picks `allow | step_up_face | hold_and_alert | block`, and writes the explanation.
4. **Verify (second pass):** Nemotron checks each claimed signal against raw tool output; unsupported claims are downgraded. Confidence is a band with reasons, never a fake 99%.
5. **Face check (optional, off by default):** open source, in the browser, `@vladmandic/human` (MIT): face match + antispoof + liveness scores and a blink/head-turn challenge. The face descriptor stays on the device (IndexedDB); the brain gets only `{match, similarity, liveness, antispoof}`. Needs HTTPS (ngrok). A step-up, never the only factor.
6. **Reach the user (Photon):** iMessage (SMS fallback) "Was this you?" YES/NO; NO locks and opens recovery. High risk → Tell calls her through Photon voice. Trusted contact alerted only with her approval.
7. **After:** recovery plan as approve-before-act actions (lock, reset PIN, report to FTC + 7726, warn trusted contact) and a 24h watch for T5 follow-ups. A confirmed "it was me" updates her baseline.

## The threats we demo
| # | Threat | What gives it away (layers) | What Tell does |
|---|---|---|---|
| T1 | Account takeover → SIM swap | New device + tower she's never used (1), straight-to-SIM path, unfamiliar typing (4) | Hold → face check fails if enabled → iMessage "Was this you?" → NO → locked + recovery |
| T2 | **Coached victim → port-out PIN** (the novel one) | Long call from a never-seen number with a spoofed "support" caller ID, still active (1), dictated input + app switching (4), her own device and home tower (so it *is* her) | Face check passes. Tell still pauses it, texts and calls her: "We never ask for your PIN on a call. Hang up, I'll wait." |
| T3 | Scam text | Lookalike domain, 3-day-old domain, known script | Verdict + sources in iMessage, raises her risk for 24h |

## Straight verdict
- **Viable:** yes. The main signal is generated data we control plus a few live events, the scoring is simple math, and Nemotron does the part it's good at: reasoning over a timeline and explaining it.
- **Not new as a category:** BioCatch, LexisNexis BehavioSec, NuData and TypingDNA sell behavioral biometrics to banks; BioCatch uses "active call" as a signal. **Our angle:** the carrier's network life pattern (banks can't see it), an agent that explains every decision, and reaching you in Messages within seconds. Don't claim we invented behavioral biometrics.
- **Legal footing:** US carrier privacy rules (CPNI, 47 U.S.C. §222) allow carriers to use network data to protect customers from fraud. Verify wording before saying it to judges.
- **Don't claim:** voice stress or lie detection. Speaker identity is fine; emotion is not.
- **Synthetic-data question judges will ask:** "Would this work on real data?" Answer: hard negatives in the set, false-positive rate reported, and the baselines are per person, so a traveler isn't flagged for traveling.

## Privacy by design (T-Mobile scores it)
- Metadata only, never call or message content (except what the user forwards to Tell). Contacts stored as salted hashes.
- Face is opt-in and matched on the device; descriptors never reach our servers (Texas CUBI covers face geometry).
- Nemotron sees signal summaries, not raw events. Safety Guard screens outbound messages.
- 30-day retention, delete button, consent screen. All data is synthetic.

## Detection quality (one frame in the video)
`evals/run.py` over the 300 labeled scenarios: precision, recall and **false-positive rate per threat**, calibration (does "high confidence" mean right?), and a layer ablation (network only vs all layers) to prove the layers add value. Optional footnote: our typing detector on the public CMU keystroke benchmark.

## NVIDIA surface
Nemotron Super (investigation + verification), Nemotron Nano (voice agent, fast triage of forwarded texts), Nemotron VL (scam text screenshots), NeMo Retriever (policy + FTC guidance), Safety Guard (outbound), Nemotron ASR + Magpie (voice), stretch TitaNet (speaker verification), optional Brev self-hosting.

## Demo inputs (frozen at T+14)
- Persona **Maya**; her phone is a teammate's iPhone (Photon iMessage). Her history is synthetic.
- **Demo console** (`/console`): buttons that inject scripted live events on cue ("incoming call from +1-800-… caller ID 'T-Mobile Support'"), so beats are repeatable. Real calls on our voice line produce the same events.
- T1: attacker laptop logs in as Maya and opens SIM swap.
- T2: "support" teammate calls Maya through our voice line; she starts a port-out PIN request while on the call.
- T3: Maya forwards "T-Mobile: your account is locked, verify at t-mobile-secure-help.co" to Tell.

## 2-minute video (replaces the beats in DEMO.md)
| Time | Beat |
|---|---|
| 0:00–0:10 | Hook: "Face ID proves it's you. It can't prove you're not being scammed." |
| 0:10–0:25 | T3: Maya forwards a scam text in iMessage → verdict + sources in seconds |
| 0:25–0:55 | T1: attacker tries a SIM swap → guardian dashboard shows the agent reading her timeline → hold → "Was this you?" → NO → locked |
| 0:55–1:30 | T2: Maya on a "support" call; it really is her, but Tell pauses it, texts and calls her → she hangs up |
| 1:30–1:45 | After: recovery plan with YES approvals, watch on the scam number |
| 1:45–1:55 | Detection numbers (incl. false-positive rate) + privacy + NVIDIA stack |
| 1:55–2:00 | End card |

## Lane mapping (prompts in LANES.md)
- **Lane 1:** contracts v0.3 (`NetworkEvent`, `Signal`, `RiskDecision`, face result), event ingest + timeline, pack loader.
- **Lane 2:** synthetic carrier generator, baselines + scoring, tools, evals.
- **Lane 3:** portal with behavior SDK + optional face check, guardian dashboard, demo console.
- **Lane 4:** Photon voice (SIP bridge) or Twilio fallback; emits live `call` events; Tell's outbound calls.
- **Lane 5:** `messaging/` (TypeScript, Photon): forwarded texts, alerts, YES/NO, `tell_message` style features; `db/`, `watcher/`.

## Open questions (decide by T+1)
- Name.
- Does the Photon 2.0 beta give us an SMS number, or iMessage only? (Lane 5 checks the dashboard.)
