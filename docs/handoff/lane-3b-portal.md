# Lane 3b: web shell + Maya's portal + console

**Owner:** Ishan · Codex #1 · **Branch:** `lane/web-portal` · **Issue:** #37 · **Label:** `lane:web-portal`
**You own:** everything in `web/` **except** `web/app/guardian/` and `web/components/guardian/` (Lane 3a).
**Skills to read:** design-taste-frontend, better-layout, better-typography, better-writing, better-accessibility.

## Your piece of the story
You build what **Maya touches**: the carrier account portal where the scammer talks her into turning off Port Out Protection and requesting a transfer PIN, and the **pause screen** that stops her in the moment. You also build the customer incident page and the backstage console. In the 2-minute video, your screens are on the portal laptop and the pause screen is the first time judges see Titan help.

## What already exists (use it; don't rebuild)
- Brain on :8000 with `MOCK=1` (`bash scripts/dev.sh`). Real gate rules, real protection state, replayed agent runs.
- `contracts/generated/types.ts`: all request/response types. Copy into `web/lib/api/contract-types.ts` with `bash scripts/gen_types.sh` (it does this once `web/lib` exists).
- Examples of every payload: `contracts/fixtures/` (`check.pause.json`, `protections.maya.json`, `case.t2.json`, ...).

## Interfaces you use (exact)
| You call | When | Types |
|---|---|---|
| `GET /protections/usr_maya` | Security page load | → `ProtectionState` |
| `POST /check` | **before** turning any protection off, SIM swap, email/password change | `CheckRequest` → `CheckResponse` |
| `POST /protections/usr_maya/{name}` | apply a toggle | `ProtectionChangeRequest {enabled, via:"portal", check_id?}` → `ProtectionState`; **409** = you skipped the pause |
| `POST /transfer-pin/usr_maya` | "Generate transfer PIN" | → `{check: CheckResponse, protections}`; `hold` → show "ready in 24 hours" |
| `POST /events` | behavior summary at end of each flow; login | `Event` type `portal.signals` / `login` |
| `GET /cases/{id}` | customer `/case/[id]` page | → `CaseDetail` (use `summary`, `actions`, `case_number`) |
| `POST /demo/play/{t1,t2,t3}`, `POST /demo/reset`, `POST /events` | console buttons | |

## Build order (each milestone ends with a check)
1. **Scaffold, push within 45 min** (unblocks 3a): `npx create-next-app@latest web --ts --tailwind --app --eslint --no-src-dir --import-alias "@/*"`; layout + theme tokens (neutral, magenta-like accent, the T-Mobile "T" for Titan (D-044)); `web/lib/api/client.ts` (fetch wrapper with `NEXT_PUBLIC_BRAIN_URL`, typed with contract types; SSE helper `subscribeCase(id, onStep, onCase)` for 3a). Check: `cd web && npm run build` passes; push; tell 3a.
2. **Portal + Security page:** login (fake, pick Maya), Security page with SIM Protection, Port Out Protection, Scam Block toggles, "Generate transfer PIN", account PIN field. Check: toggles reflect `GET /protections`.
3. **Pause screen flow (the most important screen):** toggle off → `POST /check {action:"protection_off", protection, portal_signals}` → if `pause`, show `pause_screen.title/body` with two buttons. "I'm on a call: help me" → `POST /check` with `customer_choice:"on_call_help"` → show "Titan is calling you now" + link to `/case/{case_id}`. "I'm doing this on my own" → `POST /check` with `customer_choice:"doing_it_myself"` → `POST /protections/...` with that `check_id`. Check: run `curl -X POST localhost:8000/events -H 'content-type: application/json' -d @contracts/fixtures/event.call_started.json`, then try to turn Port Out Protection off → pause screen appears; without the call → no pause.
4. **Transfer PIN hold:** show "Your PIN will be ready in 24 hours" on `hold`. Check: same as above.
5. **Behavior script** `web/lib/behavior/`: per flow compute `page_path`, `ms_per_step`, `hesitation_ms` (longest idle), `paste_into_pin`, `tab_switches` (`visibilitychange`), `pointer_speed`, `typing_rhythm_distance` (optional, null is fine) → `POST /events` type `portal.signals`; include as `portal_signals` in `/check`. Consent screen on first visit. Check: event appears in `GET /users/usr_maya/timeline`.
6. **Customer `/case/[id]`** ("the T-Life app view"): incident summary in plain words, what Titan did, what she approved, next steps, case number. Mobile-first. Check: open with the case id from `/demo/play/t2`.
7. **`/console`** (backstage): buttons for play t1/t2/t3, reset, and single events (call starts, call ends, login from new device). Check: each button changes `GET /cases`.
8. **Optional, last:** face check toggle with `@vladmandic/human` (descriptor in IndexedDB only; blink challenge) → `face.result` event + `face` in `/check`. Cut if behind.

## Decisions already made (DECISIONS.md)
D-003 customer is the star · D-044 T-Mobile "T" allowed (official asset) · D-006 derived numbers only · D-007 face optional · D-012 no links · D-018 Next.js + Tailwind v4.

## Stop and ask Lane 1 if...
- you need a field or endpoint that isn't in CONTRACTS.md (don't invent one; don't call Nemotron from the web).
- the brain returns something that doesn't match the types.
- you're about to add a UI framework/state library beyond what Next.js + Tailwind give you (shadcn/ui components are OK).

## Pitfalls
- Calling `POST /protections/...` off without a `check_id` from an `allow` check during a call → 409 by design.
- Don't compute risk or decide anything in the browser; show what the brain returns.
- Keep copy short and calm; Maya is 68. Big tap targets.

## Definition of done
Steps 1–7 work against `MOCK=1`; `npm run build` passes; screenshots at 1440 px and 390 px look right; PR `[lane 3b] ...` with `Closes #37`.

## Teammate guide (Ishan)
- **Good first answer from the agent:** goal = "Maya's portal with the pause screen, the customer case page and the console, plus the web shell 3a needs"; first milestone = scaffold + API client, pushed fast.
- **Check-in questions:** "Show me the pause screen with an active call and without one." · "What does the portal send in `portal_signals`?" · "Did you run `npm run build`?"
- **Red flags:** it adds Redux/Prisma/auth libraries; it hardcodes the pause decision in the UI; it uses the T-Mobile logo; it edits `web/app/guardian/`.
