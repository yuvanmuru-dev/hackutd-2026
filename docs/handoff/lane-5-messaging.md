# Lane 5: messaging (Photon iMessage/SMS), database, watcher

**Owner:** Karthik · Codex · **Branch:** `lane/messaging` · **Issue:** #38 · **Label:** `lane:messaging`
**You own:** `messaging/` (TypeScript), `db/`, `watcher/`, `DEVPOST.md`.
**Skills / docs to read:** Photon 2.0 beta docs (photon.codes/docs/beta: API reference + WebSocket), docs/DATABASE.md, docs/SECURITY.md, and **D-024 to D-026** in docs/DECISIONS.md.

## Your piece of the story
Every word Maya reads comes through you: the **heads-up text** when the fake "T-Mobile" call connects, the **alert** ("Was this your idea? Reply YES or NO"), recovery questions, and the **incident summary** at the end. You also turn her replies (YES, NO, REPORT, UNDO, or free-form like "I told him my PIN") into actions in the brain. The Photon track judges this lane directly.

## What already exists
- Brain `MOCK=1` on :8000. When `MESSAGING_URL=http://localhost:8200` is set (dev.sh sets it), the brain POSTs every outbound text to **your** `POST /internal/send`. Before your service exists, see them at `GET /demo/outbox`.
- Examples: `contracts/fixtures/send.alert.json` (`SendRequest`), `summary.t2.json` (`IncidentSummary`), `event.t3_forwarded_text.json`, `event.customer_reply.json`, `caseevent.transcript.json`.
- Types: `contracts/generated/types.ts` (`bash scripts/gen_types.sh` copies it to `messaging/src/contract-types.ts` once `messaging/src` exists).

## Interfaces
| Direction | Endpoint | Type |
|---|---|---|
| brain → you | `POST /internal/send` (port 8200) | `SendRequest {case_id, user_id, channel, kind: heads_up\|alert\|question\|summary\|recovery_step\|info, text, expects_reply, action_id}` → 200 |
| Photon → you | **WebSocket you open to Photon** (D-024; no ngrok). Webhook only as fallback | Photon event; dedupe on message id |
| you → brain | `POST /events` | `Event` type `message.forwarded` (a scam text/screenshot she forwards) or `customer.reply` (with `case_id`) |
| you → brain | `POST /cases/{id}/events` | `CaseEventRequest {channel:"imessage", direction:"in", kind:"reply", text}` |
| you → brain | `POST /actions/{id}/approve` or `/reject` | `ApprovalRequest {via:"sms"}`; **409** = can't loosen during a suspicious call: tell her to hang up first |
| you → brain | `GET /cases/{id}` | to know pending actions (`status: awaiting_approval`) and the summary |

Phone numbers: map `user_id` → number in `messaging/.env` (`USER_PHONE_usr_maya=+1...`, teammates only, D-023).

## Build order
1. **Hello Photon (first hour):** TypeScript project in `messaging/`; send yourself an iMessage through Photon's API, open the WebSocket and receive your reply as an event (D-024). Check: you can text yourself and see the reply event logged. Demo runs on iMessage (D-026).
2. **`POST /internal/send`:** validate against `SendRequest`, map user → number, send. `summary` kind: render the summary text as-is (it's already one message). Check: `curl -X POST localhost:8200/internal/send -H 'content-type: application/json' -d @contracts/fixtures/send.alert.json` → iMessage arrives.
3. **Inbound:** reply → find the open case for that user (`GET /cases?user_id=`) → `POST /cases/{id}/events` + `POST /events` (`customer.reply`). Forwarded scam text (no open case or starts with a link/screenshot) → `message.forwarded`. Check: `/demo/play/t2`, reply YES on your phone, see it on the case.
4. **Reply understanding:** exact keywords first (YES/NO/REPORT/UNDO). Free-form → Nemotron Nano via `MESSAGING_LLM_BASE_URL` (OpenAI SDK, model from env) classifies into `{intent: yes|no|report|undo|question|info, shared: [pin, code, transfer_pin, bank]}`; act on it: approve/reject the pending action, or post the info to the case. Check: "no that wasn't me" → reject; "I told him my PIN" → shows on the case.
5. **Recovery walk-through:** when the case has several `awaiting_approval` actions, ask one at a time ("Reset your account PIN? Reply YES or NO"). Check: three YES replies → three applied actions.
6. **`db/`:** `db/migrations/001_init.sql` from docs/DATABASE.md, `db/seed.py`. Tell Lane 1 when it's ready; the brain adapter is Lane 1's job. Check: migration runs on a fresh Supabase project.
7. **`watcher/`:** every minute, for active watches, post a follow-up event to the brain if the reported number calls again (in the demo: a console button). Small.

## Decisions already made
D-012 never ask for PINs/codes, never send links · D-017 Photon `spectrum-ts`, Twilio fallback · D-023 teammates' numbers only · D-015 NVIDIA models only (Nemotron Nano for reply understanding).

## Stop and ask Lane 1 if...
- Photon can't do something we planned (no SMS number, no webhook, rate limits).
- you want the brain to send a different message kind or field.
- you're about to store message text anywhere other than the brain/case (privacy, D-005).

## Pitfalls
- Events can repeat (webhook retries, WebSocket reconnects): dedupe on the message id or you'll approve twice.
- Reconnect the WebSocket automatically with backoff; log when it drops.
- Photon can't start phone calls through its API (D-025); that's Lane 4.
- Never echo a link back, even from the scam text she forwarded (quote the domain without making it clickable).
- Keep secrets in `messaging/.env`; add names to `messaging/.env.example`.

## Definition of done
Steps 1–5 work live on a teammate's iPhone; 6–7 at least migrated/stubbed; PR `[lane 5] ...` with `Closes #38`.

## Teammate guide (Karthik)
- **Good first answer:** starts with a Photon hello-world and the `/internal/send` endpoint; knows replies become approvals.
- **Check-in:** "Send me the alert fixture as an iMessage." · "What happens if Photon delivers the same reply twice?" · "What does it do with 'I told him my PIN'?"
- **Red flags:** it writes its own risk logic; it sends links; it stores messages in its own database instead of posting to the brain; it uses a non-NVIDIA LLM.
