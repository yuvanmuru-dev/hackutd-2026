# Titan

**Tagline:** Your protections know it's you. Titan asks whether you're being coached.

Hackathon prototype built for the T-Mobile track; not affiliated with or endorsed by T-Mobile.

## Inspiration

An account takeover does not always begin with someone stealing a password. Sometimes a scammer convinces the account owner to help.

Our main scenario follows Maya, a synthetic customer on a call with someone claiming to be T-Mobile support. The caller pressures her to turn off Port Out Protection and request a transfer PIN. She is on her own device and can pass the account's identity checks. The dangerous signal is the sequence: an unverified call, a protection being disabled, and a request to move the number.

We built Titan to connect those events and reach the customer while she can still stop the scam.

## What it does

Titan is a proposed coordination layer on top of existing carrier protections, including Scam Shield, SIM Protection, Port Out Protection, and transfer-PIN controls. In our prototype, those carrier controls and network signals are simulated. Titan does not access or change a real T-Mobile account.

Before a sensitive action, a fast gate can return a pause or hold without waiting for an LLM. A longer investigation then gathers the relevant context, assesses the risk, checks the evidence, and decides how to respond. Automatic actions make the simulated account safer, such as restoring a protection or holding a transfer PIN. The brain blocks attempts to loosen protection while a suspicious call is active.

The customer sees plain-language iMessages, rather than an unexplained risk score. Recovery is conversational: one action, one question, one answer. A YES for resetting the demo account PIN does not approve the next recovery step. An incident summary explains what happened, what Titan did, and which actions the customer approved.

The guardian dashboard is the view under the hood: it streams the workflow, evidence, tool results, and approvals. The customer's phone is the primary experience.

## Four agents, one shared case

| Agent | Responsibility |
| --- | --- |
| **Context** | Select tools and gather the minimum relevant account, protection, device, call, and session signals. |
| **Risk** | Combine the available model/rules score with the sequence of events and propose a response. Rules provide a protective floor. |
| **Verifier** | Check claims against tool results and remove or downgrade unsupported conclusions before the response reaches the customer. |
| **Response** | Coordinate safer account actions, customer outreach, recovery approvals, and the incident summary. |

Messaging and voice are interfaces to the same brain, not separate owners of account decisions. Customer replies return to the brain with a case ID. The brain interprets them and advances the appropriate recovery action. The watcher is an event producer for follow-up calls, not another reasoning agent.

## How we built it

Seven coding agents worked across defined lanes: the brain, synthetic data and carrier tools, ML and evaluation, the guardian dashboard, the customer portal and web shell, voice, and messaging plus follow-up monitoring. We used separate branches and folder ownership so parallel work could meet at explicit interfaces.

We built contracts first. JSON Schema, generated TypeScript types, and fixtures define the events and requests each lane sends. A FastAPI brain exposes HTTP endpoints and streams workflow steps over Server-Sent Events. The Next.js interface and TypeScript messaging service use those contracts rather than sharing the brain's internal state.

Photon 2.0 carries the live iMessage conversation. The messaging service sends through the Photon API and opens an authenticated WebSocket connection for incoming events. It deduplicates provider message IDs, saves replay checkpoints, and forwards replies as idempotent customer.reply events. Outbound recipients are restricted to teammates' allowlisted numbers.

The current demo uses an in-memory case store. It must stay running to preserve its cases; persistent storage is deferred. Voice belongs to the same case architecture, with a Twilio-first path and a Photon SIP integration path. We do not claim that a local text demonstration verifies the voice bridge.

### NVIDIA models and tools

All LLM reasoning uses NVIDIA-hosted models. Current model choices follow the team's verified D-035 configuration:

| Component | Model / technology | Role |
| --- | --- | --- |
| Risk and Verifier | `nvidia/nemotron-3-ultra-550b-a55b` | Risk assessment and evidence checking, with fallback behavior recorded in the workflow. |
| Context, response writing, and reply reading | `nvidia/nemotron-3.5-lightning-30b-a3b` | Fast interaction; thinking is disabled with `chat_template_kwargs.enable_thinking=false`. |
| Model-written outbound text | `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` | Safety screening alongside deterministic rules. Fixed recovery questions retain their action-specific wording. |
| Policy retrieval | NeMo Retriever | Retrieve relevant policy passages; unavailable retrieval is disclosed and has a local policy fallback. |
| Screenshot understanding | Nemotron VL integration | Planned brain-side reading of images the customer deliberately forwards; not claimed as live-verified in this draft. |
| Voice | Nemotron ASR and Lightning | Speech recognition and conversation. ElevenLabs Flash is the default TTS; Magpie is the NVIDIA TTS fallback. Voice integration needs its own end-to-end verification. |

## Synthetic data and privacy by design

The account histories, personas, carrier signals, and threat scenarios are synthetic. A teammate's phone stands in for Maya's phone for live message delivery. We do not use real customer records or real carrier access.

Our design asks for small answers at the moment of a sensitive action: whether a call is active, whether caller ID is verified, whether a device is new, and whether protections changed during that call. It does not require listening to the suspected scam call. Derived session measurements replace typed text and raw keystrokes.

We deliberately exclude location history, contact lists, browsing history, motion sensors, and voiceprints. Only messages or screenshots the customer chooses to forward enter the scam-content check. Forwarded content is untrusted data, never instructions for the agent.

Titan never asks the customer to disclose a PIN, code, or password, and never sends links in customer texts. Phone identifiers are minimized and hashed where used as signals. Raw teammate numbers and credentials stay in local configuration. Message bodies belong on their case, not in transport logs or the messaging checkpoint store.

The hackathon prototype has no production authentication or tenant isolation. Its privacy choices are design constraints and implementation safeguards, not a claim of production security certification or legal compliance. Production deployment would require carrier authorization, access controls, retention/deletion enforcement, and independent security and privacy review.

## Challenges we ran into

- **A real owner can still be a coached victim.** We needed to evaluate the timing and relationship between events, rather than treat successful authentication as proof that an action is safe.
- **A generated explanation can outrun its evidence.** We added a distinct verification pass and source-bearing tool results, and preserve uncertainty when checks are unavailable.
- **Retries must not become extra approvals.** At-least-once message delivery requires deduplication. We made the brain the sole approval owner and kept messaging to event forwarding.
- **A safety fallback can remove the question the customer needs to answer.** Recovery prompts now preserve the action and action ID. Model-written text receives model safety screening; deterministic recovery questions still receive the no-links/no-secret-request rules.
- **Offline tests must stay offline.** We found and fixed an environment-loading path that restored live delivery URLs during a test. The isolated regression harness blocks external HTTP and checks that no live message or call is dispatched.

## What we have verified

On an allowlisted teammate iPhone, we verified a real Photon alert, an incoming reply, and the sequential recovery loop with the brain in real-model mode: NO led to Step 1 of 4; one YES applied only the synthetic PIN-reset action; Step 2 of 4 then arrived. The other recovery actions remained pending. We also verified a complete incident-summary dispatch after correcting a transport guard that confused a scam description with a request for a secret.

Contract validation, TypeScript checks, messaging regression tests, lane-boundary checks, secret scanning, and isolated brain workflow tests support this work. These establish tested behaviors, not fraud-detection accuracy on real customers.

We have not measured or included a final precision, recall, false-positive rate, or latency claim in this draft. Any submission numbers must come from the final recorded evaluation run, with the dataset and operating mode identified. A replayed fixture run must be labeled as a replay; it must not be presented as live model inference.

## What we learned

Customer trust depends on the whole interaction: the explanation must match the evidence, the question must match the action, and a repeated event must not cause a second approval. A multi-agent workflow becomes useful when those boundaries are enforced by code and visible in the case record.

We also learned that the most useful intervention may be a small one at the right moment: put the action on hold, explain why, and give the customer a clear next step without asking for another secret.

## What's next

The immediate integration priorities are follow-up monitoring for a reported number that calls again and forwarding customer-selected screenshots to the brain's Nemotron VL reader. The next demo pass must verify those paths and the remaining recovery steps and summary together. Supabase and the SMS fallback are deferred so the team can focus on the verified iMessage experience.

Beyond the hackathon, we would evaluate on independently designed scenarios and hard negatives, measure calibrated risk and false-positive rates, strengthen identity and authorization controls, add durable case storage, and test accessibility and recovery wording with customers. Any real carrier integration would require a separate authorized deployment.

## Starter-kit disclosure

We began with a pre-event starter kit containing a generic agent loop and four public-data tools under `agent/`, development scripts under `scripts/`, and agent skill files under `.claude/skills/`. We reused that scaffolding. It was not created from scratch during HackUTD.

The Titan-specific scenario, synthetic carrier workflow, protection orchestration, agent roles, contracts, customer interfaces, and integrations are the hackathon project's work built on that base. The repository history and final submission should distinguish reused scaffolding from work completed during the event.

## Draft source and submission notes

This draft follows `docs/PLAN.md`, `docs/PACK_SPEC.md`, and `docs/SECURITY.md`, with later decisions in `docs/DECISIONS.md` taking precedence: D-024/D-040 for Photon 2.0, D-035 for model names, D-039/D-042 for reply and approval ownership, and D-045 for current scope. The pre-event disclosure comes from `AGENTS.md`.

Before publishing, the team should update the verification paragraph from the final demo, insert only recorded evaluation results, and confirm the final voice, watcher, and screenshot integration status. This is a submission draft, not a published Devpost entry.
