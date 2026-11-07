"""Loads contracts/schema.json and validates requests/responses against it. Contracts are law."""
from __future__ import annotations

import json
import pathlib

import jsonschema
from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "contracts" / "schema.json").read_text())
FIXTURES = ROOT / "contracts" / "fixtures"
_validators: dict[str, jsonschema.Draft202012Validator] = {}


def _validator(name: str) -> jsonschema.Draft202012Validator:
    if name not in _validators:
        _validators[name] = jsonschema.Draft202012Validator(
            {"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]}, format_checker=jsonschema.FormatChecker())
    return _validators[name]


def errors(name: str, obj) -> list[str]:
    out = []
    for e in _validator(name).iter_errors(obj):
        path = "/".join(str(p) for p in e.absolute_path) or "(root)"
        out.append(f"{path}: {e.message}")
    return out


def require(name: str, obj) -> dict:
    """Validate an incoming request body; 422 with readable errors if it breaks the contract."""
    errs = errors(name, obj)
    if errs:
        raise HTTPException(422, {"error": f"does not match contract {name}", "detail": errs[:5]})
    return obj


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


def fixture_steps(name: str = "stream.t2.sse") -> list[dict]:
    return [json.loads(line[6:]) for line in (FIXTURES / name).read_text().splitlines() if line.startswith("data: ")]
