#!/usr/bin/env bash
# Regenerate everything derived from contracts/schema.json. Run after any contract change.
#   python scripts/schema/build_schema.py contracts/schema.json   (only if you edited the builder)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/build_fixtures.py
npx -y json-schema-to-typescript@15.0.4 -i contracts/schema.json -o contracts/generated/types.ts \
  --unreachableDefinitions --additionalProperties false \
  --bannerComment "/* Generated from contracts/schema.json (v0.3) by scripts/gen_types.sh. Do not edit by hand. */"
# web/ and messaging/ import a copy so they build on their own
for d in web/lib/api messaging/src; do
  if [ -d "$(dirname "$d")" ]; then mkdir -p "$d" && cp contracts/generated/types.ts "$d/contract-types.ts"; fi
done
echo "types: contracts/generated/types.ts"
