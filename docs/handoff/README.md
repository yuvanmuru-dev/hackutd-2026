# Hand-off: how each lane works with its agent (read this first, teammates)

Each lane has one file here with everything its agent needs. Your agent reads it; **you** read it too, so you can steer.

| Lane | File | Person · agent | Issue |
|---|---|---|---|
| 2a Data + tools | [lane-2a-data.md](lane-2a-data.md) | Yuvan · Codex | #34 |
| 2b ML + evals | [lane-2b-ml.md](lane-2b-ml.md) | Ishan · Codex #2 | #35 |
| 3a Guardian dashboard | [lane-3a-guardian.md](lane-3a-guardian.md) | Ishan · Claude | #36 |
| 3b Portal + web shell | [lane-3b-portal.md](lane-3b-portal.md) | Ishan · Codex #1 | #37 |
| 4 Voice | [lane-4-voice.md](lane-4-voice.md) | Krishang · Codex | #32 |
| 5 Messaging + db + watcher | [lane-5-messaging.md](lane-5-messaging.md) | Karthik · Codex | #38 |

## Start (10 minutes)
1. Accept the GitHub invite → `git clone https://github.com/yuvanmuru-dev/hackutd-2026 && cd hackutd-2026`
2. `brew install gitleaks && bash scripts/install-hooks.sh`
3. `cp agent/.env.example agent/.env` → fill in **your own** `NVIDIA_API_KEY` (+ your lane's keys). Never commit it, never paste it in chat.
4. `bash scripts/dev.sh` → open http://localhost:8000/docs → `curl -X POST localhost:8000/demo/play/t2` → `curl localhost:8000/cases`. You should see one case. If not, ask in the team chat before going further.
5. `git checkout -b <your branch>` (see your lane file).
6. Open your agent in the repo root and paste **exactly**:
   > You are working on Titan for HackUTD 2026. Read, in order: AGENTS.md (especially "Stop rules"), docs/PLAN.md, docs/DECISIONS.md, docs/CONTRACTS.md, docs/ARCHITECTURE.md, and **docs/handoff/<your lane file>**. Then reply with: (1) your lane's goal in one sentence, (2) the 5-bullet plan for your first milestone, (3) any question that blocks you, written in the QUESTION FOR LANE 1 format. Don't write code until I say go.
7. Check its answer against your lane file (the "Teammate guide" section tells you what a good answer looks like). Then say "go".

## The question loop (when anything is unclear)
Agents must **stop and ask** instead of guessing (rules in AGENTS.md). They write the question in this block:

```
QUESTION FOR LANE 1
Lane / issue / branch: <e.g. 3b portal / #37 / lane/web-portal>
Blocked on: <one line>
Context: <what I was doing; files involved>
What the docs say: <file + section, or "nothing">
Options: A) ...  B) ...
My recommendation: <A or B, and why>
Can I keep working meanwhile? <yes: on X / no>
```

**You** (the teammate) paste that block to Yuvan (team chat or a GitHub issue with the `question` label, template provided). Yuvan pastes it to his Claude (Lane 1). Lane 1 answers with:

```
ANSWER FROM LANE 1 (D-0xx)
Decision: <what to do>
Why: <one line>
Changes for you: <files / endpoints / types>
Also applies to: <other lanes or "only you">
```

Every answer that affects more than one lane is added to **docs/DECISIONS.md** with its D-number, so every agent sees it on its next `git pull`. Tell your agent: "Pull main and re-read docs/DECISIONS.md."

## Teammate rules of thumb
- **Every 30–45 min:** ask your agent "What did you finish, what did you run to check it, what's next, anything blocked?" If it can't name a command it ran, it hasn't verified anything.
- **Before every PR:** run your lane's checks (in your lane file), `git pull --rebase origin main`, then PR into `main` titled `[lane N] ...` with `Closes #<issue>`. Yuvan merges.
- **Red flags, stop the agent:** it edits files outside your folders · it changes a request/response shape · it adds a new framework, database, LLM provider or paid API · it "simplifies" by faking data the brain should provide · it disables a test or the CI check · it says "done" without running anything · it starts a big refactor.
- **If CI fails the lane-boundary check:** your branch touched another lane's folder. Move that change out or ask Lane 1.
- **When in doubt, ask.** A 2-minute question beats a 2-hour detour.
