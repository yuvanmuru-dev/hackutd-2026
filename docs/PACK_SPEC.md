# PACK_SPEC: behavioral scam guard (pack `guard`)

Tracks: **NVIDIA + T-Mobile (Safe Signal) + Photon**. Locked 2026-11-07.
Working name: **Tell** (a "tell" is the habit that gives someone away). PROPOSAL, rename freely. Don't use "Scam Shield" (T-Mobile's real product).

## The pitch in two sentences
Face ID proves it's you. It can't prove you're not being scammed, and our behavior layer can.
Tell learns how you normally use your carrier account (typing rhythm, devices, places, hours, the flow you take). When someone acts differently, Nemotron investigates, explains with honest confidence, and reaches you on iMessage or a phone call through Photon before your number or money is gone.

## The three threats we demo (all synthetic)
| # | Threat | Who's acting | What gives it away | What Tell does |
|---|---|---|---|---|
| T1 | **Account takeover → SIM swap** | Attacker with a stolen password | New device, impossible travel, typing rhythm far from baseline, goes straight to the SIM page | Holds the SIM swap. Face ID step-up fails (attacker doesn't have the phone). iMessage: "Was this you?" → user replies NO → lock + recovery plan |
| T2 | **Coached victim → port-out PIN** (the novel one) | The real user, on the phone with a fake "support agent" | Line is on an active call with an unknown number (carrier signal), typing looks dictated (long pauses, then bursts), unusual hesitation, rushed flow, new destination | Face ID **passes** (it's really her). Behavior still flags coercion → pauses the action, iMessage + agent calls her: "We never ask for your PIN on a call. Hang up, I'll wait." |
| T3 | **Scam text before the attack** | Scammer | Forwarded text checked: lookalike domain, new domain age, known scam script | Verdict with sources, links it to her case, raises her risk level for 24h (watch) |

T2 is what judges haven't seen: catching coercion, not just impostors. Only a carrier knows the line is on a call right now; that's the T-Mobile-specific edge.

## How it works (fits the existing brain + doors)
1. **Capture (web, on-device):** a small behavior SDK in the demo carrier portal computes features in the browser: key hold/flight times, paste events, pause lengths, pointer/touch speed, navigation path, time on page. **Only derived numbers leave the device. No raw keystrokes, no text typed.**
2. **Score (brain, deterministic):** per-feature z-scores against the user's baseline plus device/geo checks → `anomaly` signals with numbers. This is plain math, fast and explainable. Nemotron does not guess numbers.
3. **Investigate (Nemotron Super agent):** a sensitive action (SIM swap, port-out PIN, add line, change email/password) starts a run. Tools: `get_baseline`, `score_session`, `device_history`, `geo_velocity`, `line_status` (active call? who with?), `recent_scam_reports` (T3 cases), `policy_lookup` (carrier security policy via NeMo Retriever). It weighs the signals, picks a decision: `allow | step_up_face | hold_and_alert | block`, and writes the explanation.
4. **Verify (second pass):** Nemotron checks each claimed signal against raw tool output; anything unsupported is downgraded. Confidence shown as a band with reasons, never a fake 99%.
5. **Step-up Face ID:** WebAuthn passkey with the platform authenticator = **real Face ID on iPhone / Touch ID on Mac. The face never leaves the device**; we only get a signed yes/no. Needs HTTPS (ngrok URL as the relying-party ID).
6. **Reach the user (Photon):** iMessage (SMS fallback) "Was this you?" with YES/NO; NO locks the account and opens recovery. High risk → agent phone call via Photon voice. Optional trusted contact gets alerted, only with the user's approval.
7. **After:** recovery plan as approve-before-act actions (lock account, reset PIN, report to FTC + 7726, warn trusted contact) and a 24h watch for follow-up attempts. Every confirmed "it was me" updates the baseline.

## Privacy by design (say this in the pitch, T-Mobile scores it)
- Face data never touches our servers (WebAuthn). Texas's biometric law (CUBI) covers face geometry; we sidestep it by design.
- Behavior: derived features only, per-user baseline, 30-day retention, delete button, consent screen on first use.
- Nemotron sees feature summaries and signals, never raw input. Safety Guard screens outbound messages.
- All users, sessions, calls and texts are synthetic. No real customer data.

## NVIDIA surface
Nemotron Super (investigation agent + verification), Nemotron Nano (voice agent + fast triage of forwarded texts), Nemotron VL (screenshots of scam texts), NeMo Retriever (carrier security policy + FTC scam guidance), Safety Guard (outbound messages), Nemotron ASR + Magpie (voice), optional Brev self-hosting.

## Synthetic data (we create it; also the eval set)
- `agent/packs/guard/data/users.json`: 3 personas with 30 days of baseline sessions (Maya 68 retired teacher, Dev 24 student, Priya 41 nurse on night shifts so "3am" is normal for her).
- Generator script: legit sessions, impostor sessions (T1), coached sessions (T2), bot sessions. Labeled. 200+ sessions.
- 40 scam/legit texts for T3, written + Nemotron-generated, labeled.
- `evals/run.py` prints precision, recall and **false-positive rate** per threat type, plus calibration (does "high confidence" mean right?). That's T-Mobile's "detection quality".

## Demo inputs (frozen at T+14)
- Persona: **Maya**, phone = a teammate's iPhone (Photon iMessage + Face ID).
- Beat T1: attacker laptop logs in as Maya from "Lagos" and opens SIM swap.
- Beat T2: Maya on her phone, on a call with "support" (teammate), types the port-out PIN request while being dictated to.
- Beat T3: Maya forwards "T-Mobile: your account is locked, verify at t-mobile-secure-help.co" to the Tell number.

## 2-minute video (replaces the beats in DEMO.md)
| Time | Beat |
|---|---|
| 0:00–0:10 | Hook: "Face ID proves it's you. It can't prove you're not being scammed." |
| 0:10–0:25 | T3: Maya forwards a scam text in iMessage → verdict + sources in seconds |
| 0:25–0:55 | T1: attacker tries a SIM swap → guardian dashboard shows the agent investigating live → hold → Maya's phone: "Was this you?" → NO → locked |
| 0:55–1:30 | T2: Maya on a "support" call, Face ID passes, but Tell pauses it → iMessage + Tell calls her → she hangs up on the scammer |
| 1:30–1:45 | After: recovery plan with YES approvals, watch on the scam number |
| 1:45–1:55 | Detection quality numbers + privacy (face never leaves the phone) + NVIDIA stack |
| 1:55–2:00 | End card |

## Lane mapping (changes from LANES.md)
- **Lane 2 (packs):** `agent/packs/guard/`: synthetic data generator, scoring math, all tools, evals.
- **Lane 3 (web):** two surfaces in `web/`: (a) the demo carrier portal with the behavior SDK + WebAuthn Face ID step-up, (b) the guardian dashboard (live case view, risk timeline, signals, decisions).
- **Lane 4 (voice):** Photon voice line via SIP bridge → Pipecat (Nemotron). Outbound "is this you?" call and inbound call screening. Twilio is the fallback if the bridge fails by T+2.
- **Lane 5 (messaging + memory):** `messaging/` in TypeScript with Photon `spectrum-ts`: inbound forwarded texts → brain, outbound alerts, YES/NO replies → approve/reject. Plus `db/` and `watcher/`. Email via Photon too if the 2.0 beta has it; otherwise AgentMail stays.

## Open questions (decide by T+1)
- Name.
- Does the Photon 2.0 beta give us an SMS number, or iMessage only? (Lane 5 checks the dashboard.)
- Line status (active call) is a **simulated carrier signal** from our own voice line. Say so in the demo.
