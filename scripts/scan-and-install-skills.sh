#!/usr/bin/env bash
# Scan each skill with NVIDIA SkillSpector, show the verdict, and only copy it into
# this project's .claude/skills/ if you type "y". What gets scanned is exactly what gets installed.
#
# Run from the project root:   bash scripts/scan-and-install-skills.sh
# Mac/Linux: Terminal.  Windows: Git Bash (comes with Git for Windows) or WSL.
#
# Needs: git, uv (https://docs.astral.sh/uv), skillspector:
#   uv tool install git+https://github.com/NVIDIA/skillspector.git
# Optional deeper scan (uses an LLM to judge intent, not just patterns):
#   export SKILLSPECTOR_PROVIDER=nv_build NVIDIA_INFERENCE_KEY=nvapi-...   (same key as Nemotron)
#   or SKILLSPECTOR_PROVIDER=claude_cli (uses your Claude Code login), then set DEEP=1

set -euo pipefail

DEST=".claude/skills"
WORK="$(mktemp -d)"
REPORTS="skill-scan-reports"
mkdir -p "$DEST" "$REPORTS"
LLM_FLAG="--no-llm"; [[ "${DEEP:-0}" == "1" ]] && LLM_FLAG=""

command -v skillspector >/dev/null || { echo "skillspector not found. Run: uv tool install git+https://github.com/NVIDIA/skillspector.git"; exit 1; }

# name | repo | path to the skill folder inside the repo
SKILLS=(
  "design-taste-frontend|https://github.com/Leonxlnx/taste-skill|skills/taste-skill"
  "web-design-guidelines|https://github.com/vercel-labs/agent-skills|skills/web-design-guidelines"
  "playwright-cli|https://github.com/microsoft/playwright-cli|skills/playwright-cli"
  # Figma community "Find Animation Opportunities" = Emil Kowalski's skill
  "find-animation-opportunities|https://github.com/emilkowalski/skills|skills/find-animation-opportunities"
  # "Better Interface" (also on Figma community) = Jakub Krehel's pack. better-interface routes to the better-* skills, so install them together.
  "better-interface|https://github.com/jakubkrehel/skills|skills/better-interface"
  "better-accessibility|https://github.com/jakubkrehel/skills|skills/better-accessibility"
  "better-colors|https://github.com/jakubkrehel/skills|skills/better-colors"
  "better-layout|https://github.com/jakubkrehel/skills|skills/better-layout"
  "better-typography|https://github.com/jakubkrehel/skills|skills/better-typography"
  "better-ui|https://github.com/jakubkrehel/skills|skills/better-ui"
  "better-writing|https://github.com/jakubkrehel/skills|skills/better-writing"
  "interface-review|https://github.com/jakubkrehel/skills|skills/interface-review"
)

for entry in "${SKILLS[@]}"; do
  IFS='|' read -r NAME REPO SUB <<< "$entry"
  echo
  echo "=============================================="
  echo " $NAME"
  echo "=============================================="
  CLONE="$WORK/$NAME"
  git clone -q --depth 1 "$REPO" "$CLONE"
  COMMIT="$(git -C "$CLONE" rev-parse --short HEAD)"
  echo "repo $REPO @ $COMMIT"

  set +e
  skillspector scan "$CLONE/$SUB" $LLM_FLAG --format json --output "$REPORTS/$NAME.json" >/dev/null
  set -e
  skillspector scan "$CLONE/$SUB" $LLM_FLAG --format markdown --output "$REPORTS/$NAME.md" >/dev/null 2>&1 || true

  python3 - "$REPORTS/$NAME.json" <<'PY'
import json, sys, collections
d = json.load(open(sys.argv[1]))
ra = d["risk_assessment"]
print(f"score {ra['score']}/100  severity {ra['severity']}  recommendation {ra['recommendation']}")
c = collections.Counter((i["id"], i["pattern"], i["severity"]) for i in d.get("issues", []))
for (rid, pat, sev), n in c.most_common():
    print(f"  {sev:<8} {rid:<5} x{n}  {pat}")
print(f"coverage {d['analysis_completeness'].get('coverage_percent')}%")
PY
  echo "full report: $REPORTS/$NAME.md"
  read -r -p "Install $NAME into $DEST? Read the findings first. [y/N] " ok
  if [[ "$ok" == "y" || "$ok" == "Y" ]]; then
    rm -rf "${DEST:?}/$NAME"
    cp -R "$CLONE/$SUB" "$DEST/$NAME"
    echo "$NAME $REPO @ $COMMIT" >> "$DEST/INSTALLED.txt"
    echo "installed -> $DEST/$NAME"
  else
    echo "skipped $NAME"
  fi
done

# Local skills (e.g. copied from Figma community pages): one folder per skill in figma-skills/
for DIR in figma-skills/*/; do
  [[ -f "$DIR/SKILL.md" ]] || continue
  NAME="$(basename "$DIR")"
  echo
  echo "=============================================="
  echo " $NAME (local: $DIR)"
  echo "=============================================="
  head -1 "$DIR/SKILL.md" | grep -q '^---$' || echo "WARNING: no frontmatter. Claude Code needs a name/description header to load it."
  skillspector scan "$DIR" $LLM_FLAG --format json --output "$REPORTS/$NAME.json" >/dev/null 2>&1 || true
  skillspector scan "$DIR" $LLM_FLAG --format markdown --output "$REPORTS/$NAME.md" >/dev/null 2>&1 || true
  python3 - "$REPORTS/$NAME.json" <<'PY2'
import json, sys, collections
d = json.load(open(sys.argv[1]))
ra = d["risk_assessment"]
print(f"score {ra['score']}/100  severity {ra['severity']}  recommendation {ra['recommendation']}")
for i in d.get("issues") or []:
    print(f"  {i.get('severity'):<8} {i.get('id'):<5} {(i.get('pattern') or '')[:60]}")
print(f"coverage {d['analysis_completeness'].get('coverage_percent')}%  (partial coverage = read the file yourself)")
PY2
  read -r -p "Install $NAME into $DEST? [y/N] " ok
  if [[ "$ok" == "y" || "$ok" == "Y" ]]; then
    rm -rf "${DEST:?}/$NAME"; cp -R "$DIR" "$DEST/$NAME"
    echo "$NAME local figma-skills copy, $(date +%F)" >> "$DEST/INSTALLED.txt"
    echo "installed -> $DEST/$NAME"
  else
    echo "skipped $NAME"
  fi
done

rm -rf "$WORK"
echo
echo "Done. Restart Claude Code (or open a new session) so it picks up the skills."
echo "Playwright skill also needs the CLI itself:  npm install -g @playwright/cli@latest"
