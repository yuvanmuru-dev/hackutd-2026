# Lane 3a: the guardian dashboard ("under the hood" projector view)

**Owner:** Ishan · Claude · **Branch:** `lane/web-guardian` · **Issue:** #36 · **Label:** `lane:web-guardian`
**You own:** `web/app/guardian/` and `web/components/guardian/` only. The shell, layout, theme and API client belong to Lane 3b; ask them (or Lane 1) for changes.
**Skills to read:** design-taste-frontend (app-screen rules), better-layout, better-typography, better-colors, find-animation-opportunities.

## Your piece of the story
When the agents step in, judges watch **your screen on the projector**: Maya's call, what she did during it, four agents working in order, the verdict with honest confidence, what Titan did, the iMessage and the call transcript, recovery steps checking off. It must read from the back of a room and make "multi-step agents" obvious without narration.

## What already exists
- Brain `MOCK=1` replays the full T2 run: `curl -X POST localhost:8000/demo/play/t2`, then `GET /cases` → your case id. Set `MOCK_STEP_MS=1500` when you want it slow enough to design animations.
- `contracts/fixtures/case.t2.json` (full `CaseDetail`) and `stream.t2.sse` (28 `StepEvent`s): build static first from these.
- Lane 3b's `web/lib/api/client.ts` with `subscribeCase(id, onStep, onCase)` (until it lands, read the fixture file).

## Interfaces you use
| Call | Type |
|---|---|
| `GET /cases/{id}` | `CaseDetail`: user, call, timeline, risk, signals, verification, steps, actions, messages, summary, data_used |
| `GET /cases/{id}/stream` (SSE) | `event: step` → `StepEvent`; `event: case` → `Case` head. History is replayed first; ends after `type:"done"` |

`StepEvent.agent` ∈ system, context, risk, verifier, response, messaging, voice · `stage` ∈ trigger, context, risk, verify, respond, reach, await, recover, summary, watch · `type` ∈ plan, tool_call, tool_result, signal, score, verify, action, message, call, transcript, approval_needed, approved, summary, error, done. `title` is the human line to show.

## Layout (suggested; improve it)
- **Top:** Maya + case number + status pill; **call window bar**: call start → now, caller "T-Mobile Support · unverified", with markers for events whose `call_id` = this call (protection turned off, transfer PIN requested).
- **Middle:** four agent columns or a pipeline: **Context → Risk → Verifier → Response**, each lighting up as its StepEvents arrive, with its tool calls/results listed under it.
- **Right:** verdict card: threat in words ("Coached victim"), confidence in words + percentage, top 3 `risk.top_reasons[].text`, "Checked twice" from `verification`.
- **Bottom:** conversation strip (iMessage bubbles + call transcript from `messages`) and recovery checklist (`actions`: awaiting_approval → applied).
- **Corner:** "Data used" (`data_used`) + "Never used: call audio, location history, contacts".
- Use `/guardian/[case]`; also `/guardian` that opens the latest case.

## Build order
1. Static page from `case.t2.json` (no network). Check: looks right at 1920×1080 and 1440×900.
2. Live: `GET /cases/{id}` + SSE; steps animate in; state derives from steps (don't poll). Check: `/demo/play/t2` plays end to end on screen.
3. Polish: motion (stage light-up, verdict reveal), large type, contrast; reduced-motion support. Check: screenshot with playwright-cli; run better-interface once.
4. Also handle T1/T3 cases (shorter runs, no call). Check: `/demo/play/t1`, `/demo/play/t3`.

## Decisions already made
D-003 dashboard is "under the hood" · D-044 T-Mobile "T" allowed (official asset) · D-010 steps stream from the brain · D-018 stack.

## Stop and ask Lane 1 if...
- you need data that isn't in `CaseDetail` or `StepEvent` (e.g. a new field); don't compute risk in the UI.
- you need a change in 3b's shell or client (ask 3b first).

## Definition of done
T2 plays live and readably on a projector; T1/T3 render; no console errors; PR `[lane 3a] ...` with `Closes #36`.

## Teammate guide (Ishan)
- **Good first answer:** builds static from the fixture first, then wires the stream; names the four agent stages.
- **Check-in:** "Play t2 at MOCK_STEP_MS=1500 and show me." · "Can someone at the back read the verdict?"
- **Red flags:** edits outside `guardian/` folders; invents fields; polls `/cases/{id}` in a loop instead of SSE; adds chart/state libraries without need.
