# Titan: demo video script (3:00) with every interaction

## Cast
- **Scammer (Yuvan):** calls Karthik's phone from your phone. Voice only, off-camera.
- **Maya (Karthik):** clicks the portal on his laptop; answers his phone on speaker (phone mirrored on the laptop).
- **Console operator:** clicks two buttons in `localhost:3000/console` (Reset, Call starts; later Play T3).
- **Narrator:** recorded as a **voice-over afterwards** over the screen recording.

## Phone contacts (Karthik's phone)
- Yuvan's number saved as **T-Mobile Support** (the fake caller ID).
- Titan's Photon number saved as **Titan** (the rescue texts and call).

## Screen layout (Karthik's laptop, one screen recording)
- **Guardian** `localhost:3000/guardian` (large): the judges' view.
- **Portal** `localhost:3000/portal/security`: where Maya clicks.
- **Phone mirror** (Messages open): texts and the incoming call.
- Console in another window, off-screen. Record system audio + mic (to catch the speakerphone).

## Before recording
1. `agent/.env`: `REPLY_TIMEOUT_S=15` → restart `MOCK=0 bash scripts/dev.sh`.
2. Brev running (`docker start nano` if restarted). Preflight green (ignore the stale "voice tunnel" line).
3. Console **Reset demo data** → reload portal → SIM + Port Out **on**, no Transfer PIN; guardian "Waiting for a case".
4. No `git pull` / file edits during a take.

---

## Main take: T2 (one continuous recording)

| Time | Cue / line | Action | Must appear before next cue |
|---|---|---|---|
| 0:00–0:25 | *(title card; voice-over added later: Problem)* | n/a | n/a |
| 0:25–0:40 | *(voice-over: Meet Maya, over the portal)* | n/a | Portal on Privacy and security |
| 0:40 | "Action" | **Yuvan calls Karthik** (shows **T-Mobile Support**); Karthik answers on speaker. **Same moment:** console **Call starts** | Heads-up text from **Titan**; guardian call headline |
| | **Scammer:** "Hi, is this Maya? This is Mark from T-Mobile Support. Someone's trying to take over your number right now. I can lock it, but I need your help. Are you at your computer?" | | |
| | **Maya:** "Oh no, yes, I'm at my laptop." | | |
| 1:00 | **Scammer:** "Go to Privacy and security and turn off Port Out Protection for a moment." | Karthik clicks **Port Out off** | **Pause screen** |
| | **Scammer:** "That warning's normal, just say you're doing it yourself." | Karthik clicks **I'm doing this on my own** | Pause closes, switch off |
| 1:15 | **Scammer:** "Now generate a Transfer PIN and read it back to me." | Karthik types 4 digits **slowly**, clicks **Request Transfer PIN** | PIN **held 24 h**, Port Out **back on**, guardian **Coached victim** + "typed … off her usual rhythm", alert text arrives |
| | **Scammer:** "Hm, it says the PIN's on hold? Hang on…" | **Yuvan hangs up.** Karthik does **not** reply to the text | ~15 s pause |
| 1:40 | *(voice-over: How it decided)* | Karthik presses **D** on guardian, ~5 s, **D** again | Drawer opens/closes |
| 1:55 | Phone rings: **Titan** | Karthik answers on speaker | Titan speaks |
| | **Titan:** "Hi Maya, this is Titan, your T-Mobile account security. I'll never ask for a PIN or a code. The person you were talking to isn't T-Mobile… Did you share an account PIN or a transfer PIN?" | | |
| | **Maya:** "Yeah… I told him my PIN." | | Titan asks the first recovery question |
| | **Titan:** "Would you like me to start an account PIN reset?" | **Maya:** "Yeah, sure." Wait for Titan's acknowledgement, then hang up | Guardian: **one** step approved |
| 2:20 | Recovery texts arrive one at a time | Karthik replies **YES** to each, waiting for the next | 3 summary texts; guardian **Maya is safe** |
| 2:35 | Stop recording | n/a | n/a |

**If Titan's call doesn't ring within ~30 s:** keep going. Karthik replies **NO** to the alert text; recovery continues by text. Use the text-only voice-over line.

## Extra clips (record separately; Reset + reload between)
- **T3 (2:35–2:45):** console **Play T3: scam text** → Titan's "This text is a scam…" (link broken) arrives.
- **LOCK (2:45–2:52):** Karthik texts **LOCK** to Titan → "Locked. Every protection is on…"; reload portal to show all switches on.

---

## Voice-over (Narrator, recorded afterwards)

**0:00 Problem**
"Last year Americans reported losing three and a half billion dollars to imposter scams, people pretending to be a company or the government. The hardest version for a carrier is when the victim does it themselves: a fake 'T-Mobile Support' agent talks them into turning off their own protections. To the system, it *is* the customer. We built Titan, a layer on top of T-Mobile's protections that notices when someone is being coached."

**0:25 Meet Maya**
"Maya has T-Mobile's protections on. Titan sits on top, watching only account signals: call metadata, account changes, and how she uses the page. Never call audio."

**0:40 The call**
"An unverified call that claims to be T-Mobile. Titan quietly warns her and starts watching."

**1:00 Pause**
"The scammer tells her to turn off a protection. Titan pauses her. Coached victims say yes, so Titan lets her continue and keeps watching."

**1:15 Titan steps in**
"That's the moment. Four NVIDIA Nemotron agents (Context, Risk, Verifier and Response) see an unverified 'T-Mobile' call, a protection turned off mid-call, a first-ever transfer PIN, and that she typed it like someone reading digits. Titan never hears the call and never reads what she typed. It re-locks her number and holds the PIN in about a second."

**1:40 How it decided**
"Each agent shows its work. Context gathered the facts, Risk scored them with our ML model and Nemotron Ultra, the Verifier checked every claim against the data, and Response acted. The fast agents run on our own Nemotron on an NVIDIA GPU. And here's what Titan never used: call audio, location, contacts."

**1:55 Titan calls**
"Titan calls her itself, over Photon. Nemotron understands a natural 'yeah, sure', but a voice yes can only approve a safer step, one at a time."

**2:20 Recovery**
"She finishes recovery by text, one question at a time, and gets a plain summary. Titan keeps watching for twenty-four hours."

**2:35 Scam text (clip)**
"She can forward any suspicious text, and Titan checks it."

**2:45 LOCK (clip)**
"She can lock everything with one text, but no text can ever unlock it."

**2:52 Close**
"Titan covers before, during and after the scam. It also stops SIM-swap takeovers and warns her when a reported scammer calls back. On a sealed test it caught thirty of thirty fake-support-call scams. Titan: protection that notices when you're being talked into turning it off."

*(Text-only fallback line for 1:55 if the call fails: "Titan reaches her by text, and can call her over Photon too.")*

## After recording
Set `REPLY_TIMEOUT_S` back to 60 for live judging (or use "I'm on a call: help me" for an instant call).
