#!/usr/bin/env bash
# Start every Titan service that exists in this checkout. Ctrl-C stops them all.
#   bash scripts/dev.sh            brain in MOCK mode (default) + any doors present
#   MOCK=0 bash scripts/dev.sh     real brain (once the workflow lands)
#   TUNNEL=1 bash scripts/dev.sh   also start ngrok for messaging (8200) and voice (8100) webhooks
set -uo pipefail
cd "$(dirname "$0")/.."
export MOCK="${MOCK:-1}"
export BRAIN_URL="${BRAIN_URL:-http://localhost:8000}"
export NEXT_PUBLIC_BRAIN_URL="${NEXT_PUBLIC_BRAIN_URL:-$BRAIN_URL}"
export MESSAGING_URL="${MESSAGING_URL:-http://localhost:8200}"
export VOICE_URL="${VOICE_URL:-http://localhost:8100}"
pids=()
start() { echo "▶ $1"; (cd "$2" && eval "$3") 2>&1 | sed -u "s/^/[$1] /" & pids+=($!); }
trap 'echo; echo "stopping"; kill ${pids[*]} 2>/dev/null; exit 0' INT TERM

start brain agent "uv run --no-project --with-requirements requirements.txt uvicorn server:app --reload --port 8000"
[ -f web/package.json ]       && start web web "npm run dev -- --port 3000"
[ -f messaging/package.json ] && start messaging messaging "npm run dev"
[ -f voice/requirements.txt ] && start voice voice "uv run --no-project --with-requirements requirements.txt python bot.py"
[ -f watcher/requirements.txt ] && start watcher watcher "uv run --no-project --with-requirements requirements.txt python watcher.py"
if [ "${TUNNEL:-0}" = "1" ]; then
  command -v ngrok >/dev/null && start ngrok . "ngrok start --all" || echo "ngrok not installed"
fi
echo "brain: $BRAIN_URL/docs   web: http://localhost:3000   mock=$MOCK"
echo "try:   curl -X POST $BRAIN_URL/demo/play/t2   then open /cases"
wait
