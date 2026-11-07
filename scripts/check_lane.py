"""Guardrail: fail a PR whose branch edits files outside its lane, or adds forbidden patterns.

Run locally: python scripts/check_lane.py lane/web-portal          (compares against origin/main)
CI runs it on every PR with the PR's head branch. Branches not listed below pass with a warning.
"""
import fnmatch
import re
import subprocess
import sys

LANES = {
    "lane/spine": ["agent/server.py", "agent/core/*", "agent/test_*", "agent/requirements.txt", "agent/.env.example",
                   "contracts/*", "docs/*", "scripts/*", ".github/*", "*.md", ".gitignore"],
    "lane/data": ["agent/packs/guard/*", "agent/cache/*"],
    "lane/ml": ["agent/packs/guard/ml/*", "evals/*"],
    "lane/web-guardian": ["web/app/guardian/*", "web/components/guardian/*"],
    "lane/web-portal": ["web/*"],
    "lane/voice": ["voice/*"],
    "lane/messaging": ["messaging/*", "db/*", "watcher/*", "DEVPOST.md"],
}
EXCLUDE = {
    "lane/data": ["agent/packs/guard/ml/*"],
    "lane/web-portal": ["web/app/guardian/*", "web/components/guardian/*"],
}
# branches named contract/* may only touch contracts + the contract docs/scripts
LANES["contract"] = ["contracts/*", "docs/CONTRACTS.md", "scripts/schema/*", "scripts/build_fixtures.py",
                     "scripts/validate_contracts.py", "agent/core/contracts.py"]

FORBIDDEN = [  # (regex on added lines, message). Docs are exempt.
    (r"api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com", "non-NVIDIA LLM endpoint (D-015)"),
    (r"[\"'](gpt-[0-9o]|o[1-4]-|claude-|gemini-)", "non-NVIDIA model name (D-015)"),
    (r"(?i)t-?mobile[-_ ]?logo\.(png|svg|jpg)|magenta-t\.svg", "official T-Mobile logo asset (D-004)"),
    (r"(?i)(enter|tell me|read (me|out)|what is) (your|the) (pin|passcode|password|one[- ]time code)", "Titan must never ask for a PIN/code/password (D-012)"),
]


def changed_files(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    return [f for f in out.stdout.splitlines() if f]


def added_lines(base: str) -> list[tuple[str, str]]:
    out = subprocess.run(["git", "diff", "-U0", f"{base}...HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
    current, lines = None, []
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and current:
            lines.append((current, line[1:]))
    return lines


def lane_for(branch: str) -> str | None:
    if branch.startswith("contract/"):
        return "contract"
    return branch if branch in LANES else None


def main():
    branch = sys.argv[1] if len(sys.argv) > 1 else ""
    base = sys.argv[2] if len(sys.argv) > 2 else "origin/main"
    problems = []
    lane = lane_for(branch)
    files = changed_files(base)
    if lane is None:
        print(f"WARN branch '{branch}' is not a lane branch; lane-boundary check skipped")
    else:
        allowed, excluded = LANES[lane], EXCLUDE.get(lane, [])
        for f in files:
            ok = any(fnmatch.fnmatch(f, p) for p in allowed) and not any(fnmatch.fnmatch(f, p) for p in excluded)
            # every lane may add env var names to its own .env.example
            if not ok and f.endswith(".env.example") and any(fnmatch.fnmatch(f, p) for p in allowed):
                ok = True
            if not ok:
                problems.append(f"{f}: outside {lane}'s folders (ask the owner or Lane 1; see docs/LANES.md)")
    for path, text in added_lines(base):
        if path.startswith("docs/") or path.endswith(".md") or path == "scripts/check_lane.py":
            continue
        for rx, msg in FORBIDDEN:
            if re.search(rx, text):
                problems.append(f"{path}: {msg}: {text.strip()[:100]}")
    if problems:
        print("FAIL lane guardrails:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"PASS lane guardrails ({len(files)} files, branch '{branch}')")


if __name__ == "__main__":
    main()
