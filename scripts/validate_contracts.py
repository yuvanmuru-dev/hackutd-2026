"""Validate every fixture in contracts/fixtures against contracts/schema.json.

Run: python scripts/validate_contracts.py   (needs: pip install jsonschema)
CI runs this on every PR. Fixture name -> schema:
  report*.json -> Report, case*.json -> CaseDetail, *.sse -> StepEvent per data line.
"""
import json
import pathlib
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
schema = json.loads((ROOT / "contracts/schema.json").read_text())
defs = schema["$defs"]


def check(name, obj, where):
    try:
        jsonschema.validate(obj, {"$ref": f"#/$defs/{name}", "$defs": defs})
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.absolute_path)
        sys.exit(f"FAIL {where} ({name}) at '{path}': {e.message}")


jsonschema.Draft202012Validator.check_schema(schema)
count = 0
for f in sorted((ROOT / "contracts/fixtures").iterdir()):
    if f.suffix == ".json":
        kind = "Report" if f.name.startswith("report") else "CaseDetail" if f.name.startswith("case") else None
        if not kind:
            sys.exit(f"FAIL {f.name}: name must start with report or case")
        check(kind, json.loads(f.read_text()), f.name)
        count += 1
    elif f.suffix == ".sse":
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if line.startswith("data: "):
                check("StepEvent", json.loads(line[6:]), f"{f.name}:{i}")
                count += 1
print(f"PASS {count} fixtures/events valid")
