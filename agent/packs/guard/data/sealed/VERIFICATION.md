# Local sealed-cohort verification

The fixed design was written and reported before `generate.py` produced any
scenario data. All artifacts remain local and unpublished. No model, scorer,
prediction, evaluation, or failure material was used to author or revise them.

## Commands run from the repository root

```sh
PYTHONDONTWRITEBYTECODE=1 python3 agent/packs/guard/data/sealed/generate.py
```

Output: generated 138 records, 41 families, 33 hard negatives, six benign
forwarded texts. Labels: bot 12, coached 24, legit 42, recovery_scam 12,
scam_text 24, takeover 24.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=agent python3 - <<'PY'
import json,pathlib
from core.contracts import errors
p=pathlib.Path('agent/packs/guard/data/sealed/scenarios.jsonl')
rows=[json.loads(line) for line in p.read_text().splitlines()]
failures=[]
for index,row in enumerate(rows,1):
 issue=errors('DatasetScenario',row)
 if issue: failures.append({'line':index,'errors':issue})
print(json.dumps({'contract':'DatasetScenario','records_validated':len(rows),'failure_count':len(failures),'failures':failures},sort_keys=True))
raise SystemExit(bool(failures))
PY
```

Output: `records_validated: 138`, `failure_count: 0`, `failures: []`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 agent/packs/guard/data/sealed/generate.py --check
```

Output: deterministic check passed. Both dataset and manifest regenerated
byte-identically without writing.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 agent/packs/guard/data/sealed/check_integrity.py
```

Independent checker output: 138 records, 41 families, 511 events, 45 distinct
call IDs, 138 unique seeds, 33 hard negatives, six benign forwarded texts;
schema, fixed counts, novelty sequences, metadata/privacy invariants, source
scenario ID collisions, trigger chronology, and raw manifest digest all pass.
The independent checker also rejected eight focused in-memory negative probes:
caller-name content, unknown call references, phone-number text, a non-reserved
host, an extra line-region snapshot, cross-scenario session reuse, a raw-byte
digest mismatch, and a benign-ID manifest mismatch. These probes created no
scenario files or caches and did not alter the frozen dataset.

## Frozen raw dataset digest

`scenarios.jsonl`: 156763 bytes.

SHA-256: `c20095a240dc38423d3a3c9e90ac36c597215128d6b39ed4fb5f9e143d86b910`.
The manifest digest covers those exact raw bytes, including the final newline.

## Limits

Labels encode synthetic author-assigned intent, not verified real incidents.
No model performance or threshold claim is made. No scorer/model run, network
check, broad test suite, publication, split change, history edit, or external
registry update was performed. History inspection was restricted to timestamp
maxima. ID collision checks against source data inspect existing scenarios only;
the sealed cohort additionally uses its own fresh identifier namespace. Model
freeze and broader provenance are maintained separately by root.
