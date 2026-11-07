# PACK_SPEC: behavioral scam guard (pack `guard`)

Tracks: **NVIDIA + T-Mobile (Safe Signal) + Photon**. Locked 2026-11-07.
Working name: **Tell** (a "tell" is the habit that gives someone away). PROPOSAL, rename freely. Don't use "Scam Shield" (T-Mobile's real product).

## The pitch in two sentences
Face ID proves it's you. It can't prove you're not being scammed. Tell can, using only data T-Mobile already has to run your line, checked at the moment someone tries to move your number or change your account. When the pattern breaks, Nemotron investigates, explains with honest confidence, and reaches you on iMessage or a call through Photon.
**Behavior is always on. The face check is optional. Tell adds no new data collection.**

## Data rule: realistic and not invasive
Every signal must pass three tests, or it's out:
1. **T-Mobile already has it** to run the service or secure the account (account records, device/SIM records, call records = CPNI, its own app/website usage). Nothing a carrier can't see; nothing we'd have to start collecting.
2. **Used only at a trigger moment:** a sensitive account action (SIM swap, port-out PIN, add line, change email/password/PIN) or a forwarded scam text. No continuous profiling of someone's life.
3. **Minimized** to the smallest answer that works: a yes/no, a bucket or a count, never raw history. Call content is never touched (only calls with Tell itself).

Grounding: US law lets carriers use CPNI to protect customers from fraud (47 U.S.C. §222, verify the wording before quoting it). T-Mobile's own Biometric Information Privacy Notice already says it uses facial recognition, voice recordings and ID scans for identity verification and fraud prevention, and lets customers decline some of it. So an optional face check matches what T-Mobile already does.

## Data inventory (what the synthetic data contains, and nothing else)
| Signal group | Data | Already held by T-Mobile as | Minimized to | Catches |
|---|---|---|---|---|
| **Account history** | Logins (device hash, IP region, hour), account changes, SIM swaps, port-out PIN requests, care contacts (channel: app, store, phone) | Account + security logs | Per-person baseline: usual devices, usual login regions, usual hours, how often they change things, which channel they use | T1: new device + new region + rushing to SIM swap |
| **Device + SIM** | Device model/ID hash, SIM/eSIM change dates | Network registration records | "Device age on this line", "SIM changed in last 30 days" | T1, T5 |
| **Call context** (CPNI) | At trigger time only: is a call active, its duration, has this number been in contact with the line in 90 days (yes/no), caller-ID attestation (STIR/SHAKEN A/B/C), network scam label on the number | Call detail records, STIR/SHAKEN, network scam labeling | 4 values, no call log, no contact list | **T2**: active long call, never-seen number, unverified caller ID claiming "support" |
| **Requesting vs. line location** | At trigger time only: is the device making the request in the same region as the phone on the line | Network + login IP | Same region yes/no. No location history, no movement tracking | T1 attacker in another state |
| **Portal behavior** | On T-Mobile's own site/app: page path, time per step, hesitation, paste into PIN field, leaving the page mid-flow, typing rhythm summary | First-party site/app analytics | Derived numbers for that session only, no raw keystrokes or typed text | T1 unfamiliar user; T2 dictated input, app switching to the caller/texts |
| **Face check** (optional) | Selfie match + liveness | T-Mobile already uses facial recognition for ID verification | On-device match; brain gets `{match, similarity, liveness, antispoof}` | T1 wrong person |
| **Forwarded text** | Only texts the user chooses to send to Tell | User-provided | Checked, then kept on that case | T3 |

**Cut on purpose** (invasive, or a carrier wouldn't use it this way): location history, commute and sleep patterns, contact-graph profiling, message content or writing style, language inferred from texts, phone motion sensors (grip, tremor), voiceprints, browsing history.

## Synthetic data: what the generator makes (Lane 2)
- **Personas (5)**, described by their account habits only:
  - Maya, 68. One laptop and one phone for 4 years, logs in monthly to pay her bill, has never changed her SIM, uses the store for help.
  - Dev, 24. New phone every year, logs in weekly from his phone, does everything in the app.
  - Priya, 41, ER nurse on nights. Logs in between 2 and 5am.
  - Marcus, 35, sales rep. Logs in from a different state most weeks.
  - Elena, 52. Account language set to Spanish, calls care often to ask about international roaming.
- **90 days of account events per persona** (sparse and realistic: bill payments, plan changes, upgrades, care contacts), plus the device/SIM registry.
- **Trigger snapshots:** at each sensitive action, the call-context and location answers above.
- **Labeled scenarios (~300):** T1 account takeover → SIM swap, T2 coached victim → port-out PIN, T3 scam text, T4 bot credential stuffing, T5 follow-up "recovery" scam.
- **Hard negatives labeled legit:** Marcus logs in from a new state, Priya changes her PIN at 3am, Dev activates his new phone at a store, Maya is on a long call with a number she *has* called before (her daughter) while updating her email.
- Seeded and reproducible. Nemotron writes scam scripts and texts for variety; Python generates the events.

## How it works (fits the existing brain + doors)
1. **Events in:** synthetic history preloaded; live events from the voice line (call context), Photon (forwarded texts, YES/NO), the portal (portal behavior, account actions), and the **demo console** that injects scripted events on cue.
2. **Baselines + scoring (deterministic):** per person: device familiarity, login-region familiarity, hour likelihood, change frequency, care-channel match, portal-path likelihood, plus the call-context answers. Output: signals with numbers and the baseline they're compared against. Nemotron never makes up numbers.
3. **Investigate (Nemotron Super agent):** a sensitive action starts a run. Tools: `account_history`, `device_sim_status`, `call_context`, `location_match`, `portal_signals`, `check_message` (lookalike domain, RDAP domain age, URLhaus), `recent_scam_reports`, `policy_lookup` (carrier security policy + FTC guidance via NeMo Retriever). It reads the sequence, picks `allow | step_up_face | hold_and_alert | block`, and explains it.
4. **Verify (second pass):** Nemotron checks each claimed signal against raw tool output; unsupported claims are downgraded. Confidence is a band with reasons.
5. **Face check (optional, off by default):** `@vladmandic/human` (MIT) in the browser, on-device descriptor (IndexedDB), blink/head-turn challenge. Step-up only, never the only factor.
6. **Reach the user (Photon):** iMessage (SMS fallback) "Was this you?" YES/NO; NO locks and opens recovery. High risk → Tell calls her. Trusted contact alerted only with her approval.
7. **After:** recovery plan as approve-before-act actions (lock, reset PIN, report to FTC + 7726, warn trusted contact) and a 24h watch for T5. A confirmed "it was me" updates her baseline.

## The threats we demo
| # | Threat | What gives it away | What Tell does |
|---|---|---|---|
| T1 | Account takeover → SIM swap | New device, login region ≠ where her phone is, goes straight to SIM swap, unfamiliar portal behavior | Hold → face check fails if enabled → iMessage "Was this you?" → NO → locked + recovery |
| T2 | **Coached victim → port-out PIN** (the novel one) | Active 22-min call from a never-contacted number, caller ID unverified (STIR/SHAKEN C) claiming "support"; dictated input, app switching; but her own device and region (so it *is* her) | Face check passes. Tell still pauses it, texts and calls her: "We never ask for your PIN on a call. Hang up, I'll wait." |
| T3 | Scam text | Lookalike domain, 3-day-old domain, known script | Verdict + sources in iMessage, raises her risk for 24h |

## Straight verdict
- **Viable:** yes. Account, device and call-context records are things a carrier really has, the synthetic data is small and realistic, the scoring is simple math, and Nemotron does the reasoning and explaining.
- **Not new as a category:** BioCatch, LexisNexis BehavioSec, NuData and TypingDNA sell behavioral biometrics to banks; BioCatch uses "active call" as a signal. **Our angle:** carrier-only call context at the moment of the request, zero new data collection, an agent that explains every decision, and reaching you in Messages within seconds.
- **Don't claim:** voice stress or lie detection, or that we use data a carrier doesn't have.
- **Judge question "would this work on real data?":** per-person baselines, hard negatives in the set, false-positive rate reported, and every field maps to a record T-Mobile already keeps (table above).

## Privacy by design (T-Mobile scores it)
- No new collection: only records T-Mobile already holds, read only at a trigger moment, minimized to yes/no or buckets.
- Never call or message content; contacts are never listed, only "seen before: yes/no".
- Face is opt-in, matched on the device; descriptors never reach our servers (Texas CUBI covers face geometry).
- Nemotron sees signal summaries, not raw records. Safety Guard screens outbound messages.
- Every decision is explained to the customer in plain words; 30-day retention on case data; all data is synthetic.

## Detection quality (one frame in the video)
`evals/run.py` over the ~300 labeled scenarios: precision, recall and **false-positive rate per threat**, calibration (does "high confidence" mean right?), and an ablation (account signals only vs + call context vs + portal behavior) to show each group earns its place.

## NVIDIA surface
Nemotron Super (investigation + verification), Nemotron Nano (voice agent, fast triage of forwarded texts), Nemotron VL (scam text screenshots), NeMo Retriever (policy + FTC guidance), Safety Guard (outbound), Nemotron ASR + Magpie (voice), optional Brev self-hosting.

## Demo inputs (frozen at T+14)
- Persona **Maya**; her phone is a teammate's iPhone (Photon iMessage). Her account history is synthetic.
- **Demo console** (`/console`): buttons that inject scripted live events on cue ("incoming call from +1-800-… caller ID 'T-Mobile Support'"), so beats are repeatable. Real calls on our voice line produce the same events.
- T1: attacker laptop logs in as Maya and opens SIM swap.
- T2: "support" teammate calls Maya through our voice line; she starts a port-out PIN request while on the call.
- T3: Maya forwards "T-Mobile: your account is locked, verify at t-mobile-secure-help.co" to Tell.

## 2-minute video (replaces the beats in DEMO.md)
| Time | Beat |
|---|---|
| 0:00–0:10 | Hook: "Face ID proves it's you. It can't prove you're not being scammed." |
| 0:10–0:25 | T3: Maya forwards a scam text in iMessage → verdict + sources in seconds |
| 0:25–0:55 | T1: attacker tries a SIM swap → guardian dashboard shows the agent checking her account history → hold → "Was this you?" → NO → locked |
| 0:55–1:30 | T2: Maya on a "support" call; it really is her, but Tell pauses it, texts and calls her → she hangs up |
| 1:30–1:45 | After: recovery plan with YES approvals, watch on the scam number |
| 1:45–1:55 | Detection numbers (incl. false-positive rate) + privacy + NVIDIA stack |
| 1:55–2:00 | End card |

## Lane mapping (prompts in LANES.md)
- **Lane 1:** contracts v0.3 (`AccountEvent`, `CallContext`, `PortalSignals`, `Signal`, `RiskDecision`, face result), event ingest + timeline, pack loader.
- **Lane 2:** synthetic account/device/call-context generator, baselines + scoring, tools, evals.
- **Lane 3:** portal with behavior SDK + optional face check, guardian dashboard, demo console.
- **Lane 4:** Photon voice (SIP bridge) or Twilio fallback; emits live call-context events; Tell's outbound calls.
- **Lane 5:** `messaging/` (TypeScript, Photon): forwarded texts, alerts, YES/NO; `db/`, `watcher/`.

## Open questions (decide by T+1)
- Name.
- Does the Photon 2.0 beta give us an SMS number, or iMessage only? (Lane 5 checks the dashboard.)
