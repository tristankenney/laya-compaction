#!/usr/bin/env bash
# Renders the plist (launchd cannot expand variables in string values, so the
# substitution happens at install time) and loads the agent.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.laya.decisions"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -x "$REPO/.venv/bin/python" ] || {
  echo "no venv at $REPO/.venv — run: python3 -m venv .venv && .venv/bin/pip install laya-mlx" >&2
  exit 1
}

mkdir -p "$HOME/.laya/logs" "$HOME/Library/LaunchAgents"
sed -e "s|@REPO@|$REPO|g" -e "s|@HOME@|$HOME|g" \
  "$REPO/launchd/$LABEL.plist.in" > "$TARGET"

launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$TARGET"
launchctl enable "gui/$UID/$LABEL"
echo "loaded $LABEL — logs in $HOME/.laya/logs"
