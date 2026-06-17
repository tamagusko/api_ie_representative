#!/usr/bin/env bash
# Deploy this API to a Hugging Face Docker Space.
#
# The runtime data (data/processed/boundaries.parquet, data/representatives.db)
# is gitignored, so it never reaches GitHub. The Space image bakes it in, so this
# script force-adds those files onto a throwaway `hf-deploy` branch and pushes
# that branch to the Space's `main`. Your normal history stays data-free.
#
# Usage:
#   ./deploy-hf.sh https://huggingface.co/spaces/<user>/<space>
#
# Auth: when git prompts, use your HF username and a WRITE access token as the
# password (huggingface.co > Settings > Access Tokens). Or run `huggingface-cli
# login` first so the credential is cached.
#
# Refresh the data before deploying with: uv run refresh-reps
set -euo pipefail

SPACE_URL="${1:-}"
if [ -z "$SPACE_URL" ]; then
  echo "usage: ./deploy-hf.sh https://huggingface.co/spaces/<user>/<space>" >&2
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

ORIGINAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
cleanup() { git checkout -q "$ORIGINAL_BRANCH" 2>/dev/null || true; }
trap cleanup EXIT

git remote remove space 2>/dev/null || true
git remote add space "$SPACE_URL"

# Build a deploy commit = current branch + the baked data artifacts.
git checkout -q -B hf-deploy

# Hugging Face rejects plain binaries; .gitattributes routes *.parquet/*.db
# through Git LFS, so it must be installed and active for this push.
if ! git lfs version >/dev/null 2>&1; then
  echo "git-lfs is required (HF stores binaries via LFS). Install it, then re-run:" >&2
  echo "  macOS:  brew install git-lfs" >&2
  echo "  Debian: sudo apt-get install git-lfs" >&2
  exit 1
fi
git lfs install --local >/dev/null

git add -f "${DATA_FILES[@]}"
git commit -q -m "deploy: bake TD data $(date +%Y-%m-%d)" || echo "(no data changes to commit)"

echo "Pushing hf-deploy -> space/main ..."
git push -f space hf-deploy:main

echo
echo "Done. Watch the build at: ${SPACE_URL%/}"
echo "Live endpoint once built: <user>-<space>.hf.space/lookup?lat=53.322&lon=-6.29"
