# Reported-number watcher (Lane 5, D-045)

The watcher posts synthetic repeat-call metadata to the brain. The brain owns
reported-number labeling, risk decisions, and the “same scam coming back” text.
The watcher never calls a data API, texts a customer, or changes a protection.

## Run

```sh
cd watcher
uv run --no-project --with-requirements requirements.txt python watcher.py
```

`scripts/dev.sh` also starts this process when watcher/requirements.txt exists.
Configuration is read from the process environment; defaults are listed in
.env.example. The normal interval is 60 seconds. Ctrl-C/SIGTERM stops the loop.
The worker does not restart the brain or write its in-memory store.

## Active watches

No new brain endpoint or contract is introduced. The worker reads GET /cases
and GET /cases/{id}. A usable number watch requires all of:

- Case status `watching`.
- An applied `report_number` action, not a proposed or rejected one.
- A `watch` / `plan` StepEvent whose `data.until` is still in the future.
- The matching original `call.started` event in the case timeline, including
  `data.other_number_hash`.

The watch begins at that plan's timestamp. Missing metadata fails closed rather
than inventing a watch or treating an unapproved report as confirmed.

## One deliberate demo call

After the teammate has approved reporting the caller and the case enters its
watch period, run:

```sh
cd watcher
uv run --no-project --with-requirements requirements.txt python watcher.py \
  --repeat-case case_REPLACE_WITH_REAL_CASE_ID --event-id evt_repeat_demo_1
```

This sends one synthetic incoming call from the **same number hash** as that
case. It does not dial a real number. Reuse the event ID when retrying the same
call; choose a new ID only to simulate another distinct call. The brain's
POST /events is idempotent on that ID. `scam_label` starts false: the brain, not
this worker, resolves the report and labels the call.

The intended brain-side label and follow-up heads-up are being integrated by
Lane 1. A successful event POST alone does not verify that customer message.

## Metadata queue for a scripted call source

The polling worker reads complete contract-valid Event JSON objects, one per
line, from WATCHER_CALLS_FILE (default .state/incoming.jsonl). A script or future
console integration can append a synthetic `call.started` event there before
it is ingested by the brain. Use current UTC timestamps and stable evt_ IDs.
Only incoming calls for the same user/hash inside an active watch are posted.
This is a pre-ingest queue; do not scrape and re-post events already in the
brain's timeline.

```sh
cd watcher
uv run --no-project --with-requirements requirements.txt python watcher.py --once
```

The checkpoint stores hashes of completed event IDs, not number hashes, caller
names, or message content. On failure the same queued event is retried; even a
lost response after acceptance is safe because its event ID is unchanged.
Run one worker per queue/checkpoint. Keep the small demo queue under 4 MB.

No Supabase dependency or new watcher HTTP API is needed. A dashboard button
can continue using the existing brain POST /events; web changes belong to its
owner, so this lane supplies the CLI and queue instead.

## Isolated checks

```sh
cd watcher
python3 -m unittest -v
```

Tests use the real contract fixture and fake HTTP/brain clients. They cover
report approval and expiry, call/user/hash matching, restart deduplication,
ambiguous delivery retries, and the exact POST /events payload. They send no
real messages or calls.
