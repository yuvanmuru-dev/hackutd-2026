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
