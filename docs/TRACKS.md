# Tracks (announced at kickoff, 2026-11-07)

Rule this year: a project can enter **up to 3 company tracks**. NVIDIA is one of ours.

## All tracks (transcribed from the slides)
| Track | Prompt (short) | Judges / requirements | Prizes |
|---|---|---|---|
| **NVIDIA**: Use Nemotron beyond a chatbot | Must use Nemotron. Beyond a chatbot (not just answering prompts), multi-step workflows (agents that plan and execute), tool integration (external APIs used intelligently), real-world applicability | The 4 bullets are the requirements | 1st: 2× RTX 5080 + $200 Brev. 2nd: 1× RTX 5080 + $200 Brev + swag |
| **T-Mobile**: Safe Signal | Protect customers from scams and fraud in ways no one has thought of yet. Prevention, real-time protection, education, new security features. Detection is a core piece, not the whole product. Go beyond classification: safeguards + customer-facing experiences. Clear next steps, honest confidence, privacy by design. **You create the data** (synthetic scam messages/scenarios, no real customer data) | Creativity, impact, usability, security and privacy, detection quality. "Customers feel protected before, during and after a threat" | Not shown |
| **Photon**: Photon 2.0 | Must integrate Photon 2.0 / API (photon.codes/beta). Texting: iMessage, SMS, RCS, WhatsApp, Telegram, Email. Voice: calls on an SMS number and iMessage | Must use Photon | Winner $400 cash + $300 credits + interview fast-track. Runner-up $200 + $100. **Voice Call Winner $300 + $100** |
| **Capital One**: Best use of Nessie | Reimagine banking with the Nessie API | Best use of Nessie | $300 gift card **per team member** |
| **State Farm**: The Worst Day, at Scale | Catastrophe response: identify those with the most urgent needs, coordinate assistance, ensure no one is overlooked | | Beats Studio Pro / RC drone / portable monitor |
| **PNC**: 360° Financial Health Navigator | Whole financial picture across checking, savings, CDs/IRAs, loans, cards, mortgages. Coach, 3+ health indicators, forecasts, what-if simulator | | PS5 Slim / Ninja CREAMi / AirPods Pro 3 |
| **Toyota Financial Services**: What's Your Next Move? | "Given my situation today, what's the smartest next move for me and my Toyota?" Personalize (simulated profile, vehicle, loan/lease), simplify, guide to a next step, show business value | Working prototype, synthetic data, responsible AI | $500 / $350 / $150 Amazon |
| **Goldman Sachs**: DealPilot | Automate and secure commercial loan processing; detect hidden cross-deal fraud patterns | | AirPods Max 2 / HomePod mini 2 / $50 Grubhub |
| **EOG**: Beat the Shutdown | Night-shift operator console for saltwater handling: what's failing, time before it worsens, lowest-cost path | | Bambu P1S / Ninja CREAMi |
| **NMC²**: Keep the World Running | Help data center teams stay ahead: missed warnings, unclear handoffs | | AirPods Max 2 / Apple Watch 12 / Echo Show 11 |
| **CBRE** | Connect fragmented real-estate data to predict operational failures, quantify impact, act before disruptions spread | | Sony headphones / Kindle / camera |
| Spacetime (sponsor tool) | SpacetimeDB reactive backend, ~$38 credit per hacker (code HACKUTD2026) | No track prize shown | Credits |

## Photon fit check (verified in Photon's docs, 2026-11-07)
- Messaging SDK is **TypeScript only** (`spectrum-ts`), with webhooks (HMAC-signed, at-least-once: dedupe on `message.id`). iMessage, WhatsApp, Telegram documented; SMS/RCS/Email are the 2.0 beta additions on the slide.
- **Voice is SIP only** (TLS 5061 / TCP 5060, G.711). No SDK audio streaming yet. Our Pipecat bot needs a SIP bridge: Photon line → SIP → **Twilio SIP Domain → `<Connect><Stream>`** (keeps the Twilio Media Streams code we planned) or LiveKit SIP → Pipecat. Prove this in the first 2 hours or fall back to Twilio for voice and Photon for texting.
- Quota 5,000 msgs/server/day. Free/Pro use a shared line pool.

## Scoring (GAMEPLAN rubric: track fit ×2, real data ×2, demo wow ×2, features fit ×1, domain ×1; max 40)
| Combo (NVIDIA + 2) | Product | Fit | Data | Wow | Features | Domain | Total |
|---|---|---|---|---|---|---|---|
| **T-Mobile + Photon** | Scam defense agent that lives in your Messages and answers suspicious calls | 5 | 4 | 5 | 5 | 3 | **37** |
| State Farm + Photon | Disaster outreach agent: texts/calls every affected customer, triages, re-pings non-responders | 5 | 5 | 4 | 4 | 2 | 35 |
| T-Mobile + Capital One | Scam defense + Nessie money hold (pause a transfer a scammer pushed you into) | 4 | 4 | 4 | 5 | 3 | 33 |
| Toyota/PNC + Photon | Finance coach over iMessage | 3 | 3 | 3 | 4 | 3 | 27 (crowded: every finance team builds this) |
| EOG/NMC² + Photon | Night-shift ops console that pages the operator by call | 4 | 3 | 4 | 3 | 1 | 28 |

## Recommendation: NVIDIA + T-Mobile + Photon (idea G, scam defense)
Why it wins: T-Mobile's criteria are our core features almost one to one, and Photon is literally our "doors" layer.
| T-Mobile asks for | We already planned |
|---|---|
| Before, during, after a threat | Web/text check (before), live call (during), recovery + watch (after) |
| Go beyond classification; clear next steps | Approve-before-act actions: report, warn family, call the real bank |
| Honest confidence | Second-pass verification, "checked twice", downgrade to unverifiable |
| Detection quality | `evals/` accuracy number on our synthetic scam set (precision, recall, false-positive rate) |
| Privacy by design | Only processes what the user forwards, PII redaction, approvals, synthetic data |
| You create the data | Nemotron-generated + hand-written synthetic scam corpus is our eval set |

Product sketch (name TBD; don't use "Scam Shield", that's T-Mobile's existing product):
- **Before:** forward any text, email, link or screenshot to our iMessage/SMS number (Photon). The agent checks it against evidence: domain age (RDAP), malware/phish lists (URLhaus, PhishTank), the brand's real contact info (our directory), known scam scripts (FTC alerts via NeMo Retriever), screenshot reading (Nemotron VL). Replies with a verdict, honest confidence and sources in seconds.
- **During:** forward unknown callers to the agent. It answers, questions the caller, and checks their claims live; the case page shows the transcript and tool calls; you get a text: "IRS impersonation, 93% confident, here's why. I didn't give them anything."
- **After:** if you already clicked or paid: a recovery plan with actions that wait for your YES (warn a trusted family member, draft the FTC report, email your bank's fraud team), plus a watch for follow-up "recovery scams" from the same number or domain.
- **Trusted circle:** grandma's case can alert her grandson, only with her approval.
- Photon Voice Call prize: the call screener is the entry.

Confirmed: Photon is a company track, so NVIDIA + T-Mobile + Photon uses all 3 slots. Capital One is out (no Nessie work).
