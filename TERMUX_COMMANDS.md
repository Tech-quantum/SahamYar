# SahamYar - Termux Commands

## Project path
cd ~/SahamYar/repo-check

## Git status
git status --short
git branch --show-current
git log -1 --oneline
git diff --stat
git diff --check

## Run backend tests
cd ~/SahamYar/repo-check/backend
../.venv/bin/python -m pytest -q

## Inspect changes
cd ~/SahamYar/repo-check
git diff
git diff --cached

## Create audit archive
cd ~/SahamYar/repo-check
OUT="$HOME/SahamYar-audit-$(date +%Y%m%d-%H%M%S).tar.gz"
TMP="$(mktemp -d)" || exit 1

git status --short > "$TMP/status.txt"
git diff > "$TMP/worktree.diff"
git diff --cached > "$TMP/staged.diff"
git branch --show-current > "$TMP/branch.txt"
git log -1 --oneline > "$TMP/head.txt"

tar -czf "$OUT" \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  backend app/src app.py AGENTS.md \
  "$TMP/status.txt" "$TMP/worktree.diff" \
  "$TMP/staged.diff" "$TMP/branch.txt" "$TMP/head.txt" \
  2>/dev/null

RESULT=$?
rm -rf "$TMP"

if [ "$RESULT" -eq 0 ]; then
  echo "Archive created: $OUT"
  ls -lh "$OUT"
  mkdir -p /sdcard/Download
  cp "$OUT" /sdcard/Download/
  echo "Copied to /sdcard/Download/"
else
  echo "Archive creation failed. Check project paths."
fi

## Important
# Do not run git reset --hard, git clean -fd, or destructive commands.
# Do not commit, push, or merge without explicit approval.
