"""Validate every fixture in contracts/fixtures against contracts/schema.json (v0.3, Titan).

Run: python scripts/validate_contracts.py   (needs: pip install jsonschema)
CI runs this on every PR. The part of the file name before the first dot picks the schema:
  case -> CaseDetail, event -> Event, check -> CheckResponse, checkreq -> CheckRequest, ...
  *.sse -> StepEvent per `data:` line.
"""
import json
import pathlib
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
schema = json.loads((ROOT / "contracts/schema.json").read_text())
defs = schema["$defs"]

PREFIX = {
    "case": "CaseDetail", "event": "Event", "check": "CheckResponse", "checkreq": "CheckRequest",
    "protections": "ProtectionState", "risk": "RiskScore", "scenario": "DatasetScenario", "send": "SendRequest",
    "callreq": "CallRequest", "summary": "IncidentSummary", "timeline": "Timeline", "user": "User", "caseevent": "CaseEventRequest",
}


def check(name, obj, where):
    validator = jsonschema.Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": defs},
                                                format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
    if errors:
        e = errors[0]
        path = "/".join(str(p) for p in e.absolute_path)
        sys.exit(f"FAIL {where} ({name}) at '{path}': {e.message}")


jsonschema.Draft202012Validator.check_schema(schema)
count = 0
for f in sorted((ROOT / "contracts/fixtures").iterdir()):
    if f.suffix == ".json":
        kind = PREFIX.get(f.name.split(".")[0])
        if not kind:
            sys.exit(f"FAIL {f.name}: unknown prefix; add it to PREFIX in scripts/validate_contracts.py")
        check(kind, json.loads(f.read_text()), f.name)
        count += 1
    elif f.suffix == ".sse":
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if line.startswith("data: "):
                check("StepEvent", json.loads(line[6:]), f"{f.name}:{i}")
                count += 1
print(f"PASS {count} fixtures/events valid")
