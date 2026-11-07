# Database: Titan

## Storage model
- **Provider:** Supabase Postgres (Lane 5 writes the migration in `db/`). The brain also has an in-memory store with the same interface, used by `MOCK=1`, tests, and as the fallback.
- **Ownership:** single demo tenant; rows belong to a synthetic customer (`user_id`). No auth in the hackathon.
- **Classification:** everything is synthetic. We still treat phone numbers and message text as personal: numbers stored as salted hashes, message bodies only on the case that needs them.

## Entities
| Entity | Purpose | Retention |
|---|---|---|
| users | Synthetic customers (Maya, Dev, Priya, Marcus, Elena) + baselines | Seed data |
| devices | Devices seen on the account | Seed + events |
| protections | Current state of each protection per user | Live |
| calls | Call windows (metadata only) | 30 days |
| events | Append-only account timeline (the source of truth) | 30 days |
| cases | One incident | 30 days, delete on request |
| runs, steps | Workflow runs and every streamed step | With the case |
| actions | Things Titan did or proposes; approvals | With the case |
| messages | iMessage/SMS in and out on a case | With the case |
| watches | 24 h watch after an incident | Until expiry |
| scam_numbers | Numbers reported to Scam ID (hashed) | Demo lifetime |

## Schema (proposal; Lane 5 implements, Lane 1 approves)
- **users**(id text pk, name text, persona jsonb, baseline jsonb, phone_hash text, trusted_contact jsonb null, face_enabled bool default false, created_at timestamptz)
- **devices**(id text pk, user_id fk→users, device_hash text, first_seen timestamptz, last_seen timestamptz, unique(user_id, device_hash))
- **protections**(user_id fk→users, name text check in ('sim_protection','port_out_protection','scam_block'), enabled bool, hold_until timestamptz null, updated_at timestamptz, pk(user_id, name))
- **calls**(id text pk, user_id fk, other_number_hash text, caller_name text null, attestation text check in ('A','B','C','none'), seen_before bool, scam_label bool, started_at timestamptz, ended_at timestamptz null)
- **events**(id text pk = client event_id (idempotency), user_id fk, type text, ts timestamptz, source text check in ('portal','voice','messaging','console','watcher','generator','brain'), call_id fk→calls null (set if inside a call window), payload jsonb, created_at)
  - types: `call.started`, `call.ended`, `login`, `otp.sent`, `otp.entered`, `pin.attempt`, `protection.changed`, `transfer_pin.requested`, `sim_swap.requested`, `portal.signals`, `message.forwarded`, `customer.reply`
- **cases**(id text pk, user_id fk, status text check in ('open','awaiting_reply','recovering','watching','closed'), threat text null check in ('takeover','coached','scam_text','legit'), risk real null, confidence text null check in ('low','medium','high'), reasons jsonb, summary jsonb null, created_at, updated_at)
- **runs**(id text pk, case_id fk, stage text, status text check in ('running','paused','done','error'), started_at, finished_at null)
- **steps**(run_id fk, seq int, type text, payload jsonb, ts timestamptz, pk(run_id, seq))
- **actions**(id text pk, case_id fk, kind text (e.g. `relock`, `hold_transfer_pin`, `reset_pin`, `revoke_transfer_pin`, `sign_out_sessions`, `report_number`, `notify_trusted_contact`, `release_hold`), direction text check in ('safer','looser'), status text check in ('proposed','awaiting_approval','approved','rejected','applied','failed'), approved_via text null check in ('web','sms','voice'), created_at, applied_at null)
- **messages**(id text pk, case_id fk, channel text check in ('imessage','sms','voice'), direction text check in ('in','out'), body text, provider_message_id text unique null (Photon dedupe), ts timestamptz)
- **watches**(id text pk, case_id fk, target_hash text, kind text check in ('number','domain'), until timestamptz)
- **scam_numbers**(number_hash text pk, first_reported timestamptz, report_count int default 1)

## Relationships
users 1–n devices, calls, events, cases · cases 1–n runs, actions, messages, watches · runs 1–n steps · events n–1 calls (optional).
Delete a user → cascade everything (demo "delete my data" button).

## Access rules
No auth in the hackathon: only the brain's service key writes; the web reads through the brain's API, never directly from Supabase. RLS off; noted in SECURITY.md as a known gap.

## Queries and indexes
- Timeline: events by (user_id, ts desc) → index (user_id, ts).
- "Actions during this call": events where call_id = ? → index (call_id).
- Active call for a user: calls where user_id = ? and ended_at is null → index (user_id, ended_at).
- Case stream: steps by (run_id, seq).
- Dedupe: unique events.id, unique messages.provider_message_id.

## Migrations and seed data
- One SQL migration in `db/migrations/001_init.sql`; Lane 1 reviews.
- Seed: `agent/packs/guard/data/` from the generator (synthetic only), loaded by `db/seed.py`. Reset = drop + migrate + seed, under 10 s.

## Data validation
The brain validates every request against `contracts/schema.json` before writing. Unknown event types → 422. Events for unknown users → 404. Duplicate event_id → 200, no-op.
