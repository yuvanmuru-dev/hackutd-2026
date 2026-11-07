# Lane 2a: synthetic data + agent tools (then QA)

**Owner:** Yuvan · Codex · **Branch:** `lane/data` · **Issue:** #34 (and #39 Brev, later) · **Label:** `lane:data`
**You own:** `agent/packs/guard/` **except** `agent/packs/guard/ml/` (Lane 2b).
**Read:** docs/PACK_SPEC.md (data rule, data inventory, synthetic data), the `Event` and `DatasetScenario` types in `contracts/schema.json`, `agent/core/store.py` (the brain's store you read from).

## Your piece of the story
You build Titan's **world**: five realistic customers with 90 days of account history, ~300 labeled scenarios (including tricky legit ones), and the **tools** the Context agent calls ("is she on a call? was it verified? did she ever request a transfer PIN?"). Lane 2b trains on your data; Lane 1's agents call your tools.

## What already exists
- `contracts/fixtures/scenario.t2.json` and `scenario.hard_negative_daughter.json`: the exact format.
- `agent/core/store.py`: users (Maya, Dev, Priya, Marcus, Elena), protections, events, calls, cases. **The brain owns protection state**; your tools read it.
- Personas: docs/PACK_SPEC.md.

## Interfaces
1. **Data files** in `agent/packs/guard/data/`: `personas.json`, `history/<user_id>.jsonl` (`Event` per line), `scenarios/*.json` (`DatasetScenario`), `policy/*.md` (short carrier security policy + FTC guidance you write).
2. **Tools** in `agent/packs/guard/tools.py`, exact names, each `def tool(store, **args) -> {"result": ..., "source": Source}`:
   `account_history(user_id, days)`, `device_sim_status(user_id)`, `protection_status(user_id)`, `call_context(user_id)`, `location_match(user_id, event_id)`, `portal_signals(user_id, session_id?)`, `check_message(text)` (lookalike domain, RDAP domain age, URLhaus), `recent_scam_reports(number_hash|domain)`, `policy_lookup(question)` (NeMo Retriever over `data/policy/`).
   Plus `TOOL_SCHEMAS` (OpenAI function-calling format) so the agents can call them.

## Build order
1. **Seed set within the first hour:** 20 scenarios (4 per threat + 4 hard negatives) for Maya, valid against `DatasetScenario`. Check: a quick script validates them with `core.contracts.errors("DatasetScenario", s)`. Push; tell Ishan's ML agent.
2. **Generator** `generator.py` (seeded): 5 personas × 90 days of sparse account history; scenarios T1 takeover, T1b code relay, T2 coached, T3 scam text, T4 bot, T5 recovery scam; hard negatives (Marcus logs in from a new state, Priya at 3am, Dev activates a new phone at a store, Maya on a long call with her daughter); `generator.variant` so ML can hold out variants. ~300 scenarios. Check: all validate; label counts printed.
3. **Tools** reading from the store (+ data files for history). Each returns a `Source`. Check: `python -c` calls on the T2 fixture data give sensible answers.
4. **`check_message`** with real RDAP + URLhaus (cache results in `agent/cache/`), and **`policy_lookup`** with NeMo Retriever. Check: the T3 text returns lookalike + young domain.
5. **From T+10: QA.** Every hour: pull main, `bash scripts/dev.sh`, run the T2 demo end to end (portal + phone), time each beat, file issues labeled with the owning lane + `demo-blocker`/`polish`.
6. **Later: #39 Brev** (GPU training with 2b, self-hosted Nemotron Nano). Off the critical path.

## Decisions already made
D-005/D-006 data rule (nothing from the "cut on purpose" list) · D-013 the brain owns state · D-015 NVIDIA only (NeMo Retriever) · D-021 Brev optional.

## Stop and ask Lane 1 if...
- the schema can't express something you need in the data.
- a tool needs data the store doesn't have.
- you're tempted to include data from the "cut on purpose" list (location history, contacts, message content...).

## Definition of done
Seed + full dataset validate; 9 tools with sources; RDAP/URLhaus/Retriever working with cache; PR `[lane 2a] ...` with `Closes #34`.

## Teammate guide (Yuvan)
- **Check-in:** "How many scenarios per label, and which are hard negatives?" · "Show me `call_context` for Maya during the T2 call."
- **Red flags:** invasive fields; tools that change protection state; data that only works for Maya.
