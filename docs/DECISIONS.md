# Decisions (settled: don't re-open without asking Lane 1)

Agents: read this before planning and after every `git pull`. New answers from Lane 1 are appended at the bottom with a D-number.

## Product
- **D-001** Product is **Titan**. Tracks: NVIDIA + T-Mobile (Safe Signal) + Photon. The main scenario is **T2: coached victim** (Maya on a fake "T-Mobile support" call turns off Port Out Protection and asks for a transfer PIN).
- **D-002** Titan is a layer **on top of T-Mobile's existing protections** (Scam Shield, SIM Protection, Port Out Protection, account PIN, login codes). It acts through them; it doesn't replace them.
- **D-003** The customer is the star: heads-up text → pause screen → agents step in → Titan calls → incident summary. The guardian dashboard is the "under the hood" view.
- **D-004** In the UI use our own "T" glyph in a magenta-like color. **Never** the official T-Mobile logo file or brand assets. Feature names (Scam Shield, Port Out Protection) are fine in text.

## Data and privacy
- **D-005** All data is synthetic. Only data T-Mobile already holds, read at the trigger moment, reduced to yes/no or buckets (PACK_SPEC "Data rule"). **Never:** call audio/content (except Titan's own calls), location history, contact lists, message content beyond what the customer forwards, motion sensors, voiceprints, browsing.
- **D-006** Portal behavior = derived numbers only (hesitation, tab switches, paste into PIN, page path, typing-rhythm distance). Never keystrokes or typed text.
- **D-007** Face check is optional, off by default, on-device (`@vladmandic/human`), sends only `{match, similarity, liveness, antispoof}`. First feature to cut.

## Architecture
- **D-008** One brain (`agent/`, FastAPI). Doors (web, messaging, voice, watcher) talk to it **only** over the HTTP API in docs/CONTRACTS.md. Only the brain calls Nemotron for the four agents and the data/ML tools.
- **D-009** Contracts are law: `contracts/schema.json` v0.3. Shape changes only via a `contract:` PR merged by Lane 1.
- **D-010** Two paths: `/check` is rules + ML only, < 300 ms (pause screen must be instant); the Nemotron agents run asynchronously and stream StepEvents.
- **D-011** Agents may only make the account **safer** on their own. Anything **looser** needs the customer's approval **and** no suspicious call active. Enforced in the brain (409).
- **D-012** Titan never asks for a PIN, code or password and never sends a link in a text.
- **D-013** Storage: Supabase Postgres (docs/DATABASE.md); the brain's in-memory store is the fallback and the MOCK store.
- **D-014** No auth: hardcoded synthetic personas. Main persona `usr_maya`.

## Stack and providers
- **D-015** LLMs: NVIDIA only (build.nvidia.com via the OpenAI SDK client). Nemotron Super for Context/Risk/Verifier/Response, Nano for Messaging/Voice conversation, VL for screenshots, Safety Guard, NeMo Retriever. **No OpenAI/Anthropic/Gemini models.**
- **D-016** Voice: Pipecat, Nemotron ASR, **ElevenLabs TTS (Flash) by default**, Magpie fallback via `TTS_PROVIDER`.
- **D-017** Messaging: Photon `spectrum-ts` (TypeScript), webhooks, dedupe on `message.id`. Twilio is the fallback for SMS/voice.
- **D-018** Web: Next.js App Router + TypeScript + Tailwind v4, one app (`web/`). Types from `contracts/generated/types.ts`.
- **D-019** ML: scikit-learn, XGBoost, SHAP; runs in-process in the brain. No deep learning frameworks needed.
- **D-020** No new frameworks (LangChain, LlamaIndex, Prisma, Redux, etc.), databases, or paid APIs without asking Lane 1.
- **D-021** Brev ($60 for the team) is optional and off the critical path (#39). Everything must work on hosted endpoints.

## Process
- **D-022** One branch per agent, PR into `main`, Lane 1 merges. CI: contracts, gitleaks, brain tests, lane-boundary check.
- **D-023** Outbound texts/calls only to teammates' numbers (`OUTBOUND_ALLOWLIST`).

## Answers log (appended by Lane 1)
<!-- D-024 onward -->
- **D-024 (Lane 5, asked by Karthik)** Messaging uses Photon's **outbound API to send** and a **WebSocket opened by us to receive** events (Photon 2.0: "connect, start a session, receive events"). No ngrok or public webhook for messaging. Keep the webhook handler only as a fallback. Still dedupe on the message id (events can repeat on reconnect). Authenticate per the WebSocket docs; keys in `messaging/.env` only.
- **D-025 (Lanes 4 + 5)** Photon does **not** start phone calls through its API. Voice is SIP only (inbound and outbound to `sip.spectrum.photon.codes`, TLS 5061); SDK call control is on Photon's roadmap. Titan's outbound call stays in Lane 4 (Pipecat + SIP bridge, Twilio fallback at T+2). Messaging must not try to place calls.
- **D-026 (Lane 5)** Demo texting runs on **iMessage**. Photon 2.0 lists SMS, but US A2P SMS needs 10DLC registration that may not clear in time. SMS is a stretch only if the dashboard shows it ready.
- **D-027 (Lanes 3a + 3b, asked by Ishan)** Ishan's Claude session builds **both** web lanes (3b portal + shell, 3a guardian) on the two separate branches `lane/web-portal` and `lane/web-guardian`. Lane 1 merges the scaffold PR early so the guardian branch diffs cleanly. Ishan's Codex #1 is free for other work (his call).
- **D-028 (Lane 3a)** The guardian derives state from StepEvents and re-fetches `GET /cases/{id}` once on steps of type `action`, `approval_needed`, `approved`, `summary` and `done` (no polling loop). Declined recovery steps emit a `type: action` step with `data.approved: false` (PR #41). Render `type: error` steps too (model fallbacks, blocked messages). Rely on `title`/`type`/`agent`/`stage`; `data` contents differ between MOCK and the real workflow beyond the contract.
- **D-029 (Windows teammates)** Run the repo's bash scripts (`dev.sh`, `gen_types.sh`, `install-hooks.sh`) in **Git Bash** (or WSL), not PowerShell. gitleaks via `winget install gitleaks` or `scoop install gitleaks`.

- **D-030 (Lane 4, asked by Krishang)** Voice order: (1) guaranteed path first: Twilio number → Media Streams → Pipecat bot (Nemotron ASR → Nano → ElevenLabs Flash); (2) then a timeboxed Photon SIP → Twilio SIP Domain attempt into the same bot. Go/no-go 90 min after he starts, posted in the team chat. Outbound Titan call via Twilio API (or SIP through Photon if it works). Scam call forwarded with plain `<Dial>`, never recorded or streamed; only `call.started`/`call.ended` events. Voice needs ngrok. Allowlist enforced in code. Twilio trial preamble: Yuvan decides on upgrading.
- **D-031 (Lanes 2a + 2b, asked by Yuvan's Codex)** Code relay (T1b) is labeled `coached` with `generator.variant: "code_relay"` (no new label): the real customer reads her login code to a scammer during an unverified call; the brain already routes `otp.sent` during a suspicious call to the coached run. Seed: call.started (unverified) → otp.sent (same call_id) → optional new-device login from another region; trigger = otp.sent. ML reports code relay separately by variant.
