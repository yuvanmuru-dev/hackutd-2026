# Titan demo script (video ≈ 2:00 · live judging ≈ 2:30 + Q&A)

## Cast and screens
- **Narrator** (Yuvan): voice-over / talks to judges. Never touches the laptop.
- **Maya** (Karthik): drives the portal on his laptop and holds his phone (Maya's phone, mirrored on screen).
- **Scammer** (Ishan or Krishang): plays "T-Mobile Support" on speakerphone from a second phone. **Acted audio only:** Titan never hears or records this call; it only sees call metadata (unverified caller ID, the name "T-Mobile Support", how long the call has lasted).
- **Console** (Krishang): runs `/console` off-screen and clicks the scenario buttons.

Screens on Karthik's laptop: **Guardian** `localhost:3000/guardian` (judges' view, big) · **Portal** `localhost:3000/portal/security` · **Mirrored phone** (Messages open, sound on).

Before every take: `curl -X POST localhost:8000/demo/reset` · preflight green · guardian tab shows "Waiting for a case" · portal signed in on Privacy and security · phone on Messages.
For the video only: set `REPLY_TIMEOUT_S=15` in `agent/.env` (restart the brain) so Titan calls after 15 s instead of 60 s.

---

## 0:00–0:20 · Introduction (Narrator, over a title card or the portal)
> "Last year Americans reported losing **3.5 billion dollars to imposter scams**, people pretending to be a company or the government. It's been the most-reported fraud in America for nearly a decade, according to the FTC.
> The hardest version for a carrier is when the **victim does it themselves**: a fake 'T-Mobile Support' agent talks them into turning off their own protections. Every protection can be turned off by the customer, because to the system, it *is* the customer.
> We built **Titan**: a layer on top of T-Mobile's protections that notices when someone is being **coached**, and steps in, without ever needing your PIN."

## 0:20–0:30 · The call starts
**Console:** clicks **Call starts (unverified "T-Mobile Support")**.
**Scammer** (speakerphone, friendly and urgent):
> "Hi, is this Maya? This is Mark from T-Mobile Support. We've flagged someone trying to take over your number right now. I can lock it for you, but I need your help. Are you near your computer?"

**Maya:** "Oh no, yes, I'm at my laptop."

*On screen:* Maya's phone gets Titan's heads-up text ("The call you just answered says it's T-Mobile, but we can't verify it…"). Guardian headline: *"A caller claiming to be T-Mobile is on the line with Maya."*

**Narrator:** "The call's caller ID can't be verified. Titan sends Maya a quiet heads-up and starts watching."

## 0:30–0:45 · Coached to turn off protection
**Scammer:**
> "Okay, go to Privacy and security. To reset the lock, I need you to turn off **Port Out Protection** for a moment."

**Maya:** clicks **Port Out Protection** off.
*On screen:* the **pause screen**: *"Are you on the phone with someone who asked you to do this?"*

**Scammer:** "You'll see a security warning, that's normal. Just click that you're doing it yourself."
**Maya:** clicks **"I'm doing this on my own"**.

**Narrator:** "Titan paused her. But coached victims say yes, so Titan lets her continue and keeps watching."

## 0:45–1:05 · Titan steps in
**Scammer:**
> "Great. Now generate a **Transfer PIN** so I can verify you. Type any four digits and read the PIN back to me."

**Maya:** types the 4-digit PIN **slowly, pausing between digits** (as if being read numbers), clicks **Request Transfer PIN**.
*On screen (within about a second):* portal says the Transfer PIN is **held for 24 hours**; Port Out Protection is **back on**. Guardian: step 3 lights up, *"Coached victim · 99%"*, and the Context step shows *"typed … off her usual rhythm"*. Maya's phone gets Titan's alert.

**Narrator:**
> "That's the moment. Four NVIDIA Nemotron agents (Context, Risk, Verifier and Response) see an unverified 'T-Mobile' call, a protection turned off mid-call, a first-ever transfer PIN, and that she typed it like someone reading it off a phone call. Titan never reads what she typed and never hears the call. It re-locks her number and holds the PIN, in about a second. The fast agents run on our own Nemotron on an NVIDIA GPU."

**Scammer** (confused): "Hm, it's saying the PIN is on hold? Let me… hang on." *(Scammer drops off.)*

## 1:05–1:30 · Titan calls Maya (Photon)
Maya doesn't reply to the text. After 15 s, **Maya's phone rings** from Titan's number.
**Maya:** answers on speaker.
**Titan** (voice, roughly):
> "Hi Maya, this is Titan, your T-Mobile account security. I'll never ask for a PIN or a code. The person you were talking to isn't T-Mobile. Please hang up on them. Did you share an account PIN or a transfer PIN?"

**Maya:** "Yeah… I told him my PIN."
**Titan:** "Thanks for telling me. Would you like me to reset your account PIN?"
**Maya:** "Yeah, sure."
*On screen:* guardian shows **exactly one** step approved. **Titan:** "Done. Your account PIN reset has started."

**Narrator:** "Titan calls her itself, over Photon. Nemotron understands a natural 'yeah, sure', but a voice yes can only approve a *safer* step, one at a time."

## 1:30–1:45 · Recovery by text
Titan texts the remaining steps one at a time. **Maya** replies **YES** to each.
*On screen:* blue reply bubbles, steps check off, then **three short summary texts**. Guardian: *"Maya is safe. Titan is watching her account for 24 hours."*

*(Optional, if time: Maya texts* **LOCK** *→ "Locked. Every protection is on. Turning one off needs you signed in, never a text.")*

## 1:45–2:00 · Close (Narrator)
> "Titan covers before, during and after the scam. Every decision is checked by a Verifier agent and screened by NVIDIA Safety Guard. Titan only ever makes your account *safer* on its own, and never asks for a PIN. On a sealed test it caught **30 of 30** fake-support-call scams. That's **Titan: protection that notices when you're being talked into turning it off.**"

---

## Live judging differences
- Skip the title card; say the introduction live (about 20 s), then run the same beats.
- Keep `REPLY_TIMEOUT_S=60` (or tap **"I'm on a call: help me"** on the pause screen to make Titan call immediately; then the story is "she asked for help").
- Press **D** on the guardian screen when a judge asks how it decided (each agent, its model, reasons, data used / never used).
- If voice fails: "Titan would call her here" and continue by text. If models or Wi-Fi fail: brain with `DEMO_MODE=1` (labeled replay). Never claim a replay is live.

## Q&A one-liners
- **NVIDIA:** Nemotron 3 Ultra (risk + verifier), Nemotron 3.5 Lightning + our self-hosted Nemotron Nano on Brev (fast agents, voice), Safety Guard on every outbound line, Nemotron VL for forwarded screenshots.
- **Privacy:** no call audio, no message contents, no location history, no contacts; portal behavior is derived timing only, never keystrokes.
- **Numbers:** sealed test run once on a frozen model: hybrid caught 30/30 coached calls (rules 21/30); rules caught 28/30 scam texts (hybrid 6/30), so Titan routes texts to rules and calls to the hybrid model. Synthetic data, so no real-carrier claim.
- **Why not just block?** Real customers do port out; Titan pauses, holds and asks, and only automates *safer* changes.
