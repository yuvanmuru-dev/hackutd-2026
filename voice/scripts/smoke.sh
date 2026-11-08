#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --locked python smoke.py "${@}"
