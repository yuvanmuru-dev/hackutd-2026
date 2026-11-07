#!/usr/bin/env bash
# Local pre-commit secret scan. Run once per clone: bash scripts/install-hooks.sh
# Needs gitleaks: brew install gitleaks (Mac) / see github.com/gitleaks/gitleaks for others.
set -euo pipefail
HOOK="$(git rev-parse --git-dir)/hooks/pre-commit"
cat > "$HOOK" <<'HOOKEOF'
#!/usr/bin/env bash
if command -v gitleaks >/dev/null; then
  gitleaks protect --staged --redact -v || { echo "gitleaks found a secret in staged changes. Remove it, then commit."; exit 1; }
else
  echo "warning: gitleaks not installed, skipping secret scan (brew install gitleaks)"
fi
HOOKEOF
chmod +x "$HOOK"
echo "pre-commit secret scan installed at $HOOK"
