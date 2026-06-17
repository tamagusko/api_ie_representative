#!/usr/bin/env bash
# Deploy this API to a Hugging Face Docker Space.
#
# The runtime data (data/processed/boundaries.parquet, data/representatives.db)
# is gitignored, so it is not in normal history. This script publishes a one-off
# deploy commit that bundles those files, built inside a throwaway git worktree
# so your main working tree and branch are never modified. HF requires binaries
# via Git LFS; .gitattributes routes *.parquet/*.db through it.
#
# Usage:
#   ./deploy-hf.sh https://huggingface.co/spaces/<user>/<space>
#
# Auth: when git prompts, username = your HF username, password = a WRITE access
# token (huggingface.co > Settings > Access Tokens).
#
# Refresh the data before deploying with: uv run refresh-reps
set -euo pipefail

SPACE_URL="${1:-}"
if [ -z "$SPACE_URL" ]; then
  echo "usage: ./deploy-hf.sh https://huggingface.co/spaces/<user>/<space>" >&2
  exit 1
fi

if ! git lfs version >/dev/null 2>&1; then
  echo "git-lfs is required (HF stores binaries via LFS). Install it, then re-run:" >&2
  echo "  macOS:  brew install git-lfs" >&2
  echo "  Debian: sudo apt-get install git-lfs" >&2
  exit 1
fi

DATA_FILES=(
  data/processed/boundaries.parquet
  data/representatives.db
  data/overrides.yaml
)
for f in "${DATA_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Missing $f — run 'uv run refresh-reps' first." >&2
    exit 1
  fi
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE="$(mktemp -d)"
cleanup() {
  git -C "$REPO_ROOT" worktree remove --force "$WORKTREE" 2>/dev/null || true
  rm -rf "$WORKTREE"
}
trap cleanup EXIT

# Isolated detached worktree at the current commit — the main tree is untouched.
git worktree add -q --detach "$WORKTREE" HEAD
git -C "$WORKTREE" remote add space "$SPACE_URL" 2>/dev/null \
  || git -C "$WORKTREE" remote set-url space "$SPACE_URL"
git -C "$WORKTREE" lfs install --local >/dev/null

# Copy the live data artifacts in and commit them (LFS-tracked via .gitattributes).
for f in "${DATA_FILES[@]}"; do
  mkdir -p "$WORKTREE/$(dirname "$f")"
  cp "$REPO_ROOT/$f" "$WORKTREE/$f"
done
git -C "$WORKTREE" add -f "${DATA_FILES[@]}"
git -C "$WORKTREE" commit -q -m "deploy: bake TD data $(date +%Y-%m-%d)" \
  || echo "(no changes to commit)"

echo "Pushing -> space/main ..."
git -C "$WORKTREE" push -f space HEAD:main

echo
echo "Done. Watch the build at: ${SPACE_URL%/}"
echo "Live once built: <user>-<space>.hf.space/lookup?lat=53.322&lon=-6.29"
