# Titan: the merged plan (read this first)

Tracks: **NVIDIA + T-Mobile (Safe Signal) + Photon**. Details: docs/PACK_SPEC.md. Who builds what: docs/LANES.md.

## The problem (specific)
Scammers call T-Mobile customers pretending to be **T-Mobile support**. They talk the customer into opening their own locks: turning off SIM Protection or Port Out Protection, reading out the account PIN, a one-time login code, or a transfer PIN. With those, the scammer moves the phone number to their own SIM or carrier and takes over every bank and email account that sends codes by text.

**Why T-Mobile's protections fail here:** every one of them trusts the account owner. When the owner is the one being manipulated, she passes every check: right password, right PIN, right code, her own phone. Scam Shield can label a call, but nothing connects "she's on a call with an unverified number right now" to "she just turned off her protection."

## The solution in one line
Titan sits on top of T-Mobile's existing protections. When a sensitive account action happens **while the customer is on a suspicious call**, a team of Nemotron agents checks what's going on, re-locks the account through T-Mobile's own protections, and reaches the customer on iMessage and a phone call through Photon before the scammer gets anything usable.

## Yes, T-Mobile can see the call (and what she does during it)
- **Network side (carrier only):** T-Mobile's network knows in real time that a line is on a call, when it started, the other number, and the caller-ID verification result (STIR/SHAKEN A/B/C). That's how calls get routed, billed and labeled by Scam ID today.
- **Account side:** every action in T-Life / the website / care is logged with a timestamp (protection turned off, transfer PIN generated, code sent, PIN entered).
- **Join the two:** "actions taken while on the call" = account actions whose timestamp falls inside the active call window. No call content, no recording.
- **App side (optional):** the T-Life app can also tell "on a call right now" on the device (iOS CallKit call observer, Android call state), without the number.
- **Industry precedent:** carriers already expose fraud signals like this to banks through GSMA Open Gateway / CAMARA network APIs (SIM Swap is live in several countries; call-forwarding and device-swap signals are being standardized). Titan uses the same kind of signal inside the carrier.
- **Legal footing:** US rules on carrier customer data (CPNI, 47 U.S.C. §222) allow use to protect customers from fraud. Verify wording before quoting.
- **In our demo:** our Photon/Twilio number sits in front of the demo phone, so we see each call exactly the way a carrier would (start, duration, number, verified or not). Say this is simulated.

## The agents (multi-step workflow)
```
Trigger: sensitive action during a call (protection off, transfer PIN, code relay, SIM swap)
  → Agent 1 Context   → Agent 2 Risk   → Verifier   → Agent 3 Response
                                                        ├→ Messaging agent (iMessage via Photon)
                                                        └→ Voice agent (call via Photon)
  → pause until she replies → YES: release + learn  |  NO: recovery plan → report → 24h watch
```
| Agent | Model | What it does |
|---|---|---|
| **1. Context agent** | Nemotron Super + tools | Gathers only what's needed, in parallel: her account baseline (usual devices, hours, how often she changes things), protection status and recent changes, **call context** (on a call? how long? number seen before? caller ID verified? Scam ID label?), actions taken during the call, portal behavior (hesitation, leaving the page mid-flow) |
| **2. Risk agent** | Our ML models + Nemotron Super | Personal anomaly model (is this unlike *her*?) + calibrated risk classifier → "coached victim, 87%, top reasons: protection turned off during an unverified 19-min call, first transfer PIN ever, left the page 3 times". Hard rules as a floor ("protection off during an unverified call" always escalates) |
| **3. Verifier** | Nemotron Super (second pass) | Checks every claim from agents 1–2 against the raw data. Anything unsupported is removed or downgraded before anything reaches the customer. This is T-Mobile's "honest confidence" |
| **4. Response agent** | Nemotron Super | Acts **through T-Mobile's protections**: turns the protection back on, holds the transfer PIN for 24h, asks for the face check if identity is in doubt. Decides how to reach her. After her answer, builds the recovery plan |
| **Messaging agent** | Nemotron Nano + Nemotron VL | iMessage through Photon: the alert, understands free-form replies, walks her through recovery one approval at a time, checks scam texts/screenshots she forwards |
| **Voice agent** | Nemotron Nano + Nemotron ASR + Magpie TTS | Calls her through Photon **as a second incoming call** while the scam call is live: "This is Titan. The person you're talking to isn't T-Mobile. Please hang up, I'll stay on the line." Takes spoken YES/NO and approvals |

Not agents: the **watcher** (24h watch for follow-up "recovery" scams, wakes the Context agent), **Safety Guard** (screens every outbound message and script), the **ML models** (tools the Risk agent calls).

## The demo scenario (2 minutes)
1. Maya (68) gets a call: caller ID "T-Mobile Support", unverified, number never seen before.
2. 19 minutes in, he tells her to turn off Port Out Protection and generate a transfer PIN. She does. **She passes every existing check.**
3. Agents 1 → 2 → Verifier → 3 run live on the `/guardian` screen: "coached victim, 87%".
4. Port Out Protection goes back on; the PIN is held 24h. iMessage arrives. No reply in 60s → Titan calls her. She hangs up on the scammer.
5. She says "I told him my PIN" → recovery plan with YES approvals (reset PIN, cancel transfer PIN, sign out sessions, report the number to Scam ID).
6. Next day the "fraud recovery department" calls → now labeled Scam Likely for everyone.

## What changed from the first draft (and why)
| First draft | Merged plan | Why |
|---|---|---|
| Agent 1 knows the **entire call history** | Only answers at the trigger moment: on a call? how long? seen before (yes/no)? verified? labeled? | Reading all calls is surveillance; T-Mobile judges score privacy. Minimal data is enough |
| "Unknown caller + protections off = suspicious" | Personal baseline + sequence during the call + ML risk score with calibrated confidence | Many legit calls are unknown numbers; we need honest confidence and a low false-positive rate |
| Agent 3 **interrupts the call** | Second incoming call + iMessage at the same time | We can't cut into a call between two other people. (Inside T-Mobile's network an in-call warning tone is possible: pitch it as the production version) |
| Alert only | Acts through T-Mobile's protections (re-lock, 24h hold, face step-up) | "Build on existing protections" |
| No checking | **Verifier** step | Honest confidence; catches agent mistakes before the customer sees them |
| Stops at the alert | Recovery plan, report to Scam ID, 24h watch | T-Mobile's "before, during and after" |
| No proof | Synthetic dataset (~300 labeled scenarios incl. tricky normal ones) + evals: precision, recall, false-positive rate | T-Mobile scores "detection quality" |

## Requirements checklist
- **Nemotron:** Super (Context, Risk, Verifier, Response), Nano (Messaging, Voice), VL (screenshots), ASR + Magpie (voice), Safety Guard, NeMo Retriever (policy lookup).
- **Multi-step agent workflow:** trigger → context → risk → verify → act → reach → wait for reply → branch → recover → watch. Long-running, human in the loop, every step streamed live.
- **External LLMs/APIs:** NVIDIA build.nvidia.com (Nemotron), Photon (iMessage, SMS, voice), NeMo Retriever, RDAP + URLhaus (scam links), ElevenLabs TTS (optional), Twilio (voice fallback), Supabase.
- **Photon:** every customer touchpoint: alerts, replies, recovery walk-through, the voice call.
- **T-Mobile criteria:** creativity (catching the coached owner, not just impostors), impact, usability (one text or one call, plain words), security and privacy (no call content, minimal data, no new collection), detection quality (eval numbers), honest confidence (Verifier + calibration), before/during/after.

## Data rules (short)
Only data T-Mobile already holds, read only at the trigger moment, reduced to yes/no or buckets. Never call or message content, never location history, never contact lists. All data is synthetic. Face check is optional and runs on the device.

## Name: Titan
The first "T" is styled after the T-Mobile T. **Branding caution:** T-Mobile's T logo and its magenta are trademarks. Inside a T-Mobile-sponsored track, showing it as "Titan, built for T-Mobile" in the pitch is reasonable, but in the app UI use our own T glyph in a magenta-like color, not the official logo file, so nothing looks like we're impersonating T-Mobile.
