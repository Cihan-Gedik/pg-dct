#!/usr/bin/env bash
# Print Markdown release notes between two git tags (or commits).
# Usage:
#   ./scripts/release-notes.sh v0.2.0 v0.2.1
#   ./scripts/release-notes.sh v0.2.1 HEAD
set -euo pipefail

PREV="${1:-}"
TAG="${2:-}"

if [[ -z "$PREV" || -z "$TAG" ]]; then
  echo "Usage: $0 <from-ref> <to-ref>" >&2
  echo "Example: $0 v0.2.0 v0.2.1" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse "$PREV" >/dev/null 2>&1; then
  echo "Unknown ref: $PREV" >&2
  exit 1
fi
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Unknown ref: $TAG" >&2
  exit 1
fi

REPO_URL="$(git remote get-url origin 2>/dev/null | sed -E 's#git@github.com:#https://github.com/#; s#\.git$##')"
COMPARE_URL="${REPO_URL}/compare/${PREV}...${TAG}"
TAG_URL="${REPO_URL}/releases/tag/${TAG}"

echo "## Release ${TAG}"
echo ""
echo "**Compare:** [${PREV}...${TAG}](${COMPARE_URL})"
echo ""
echo "### Commits"
echo ""
git log "${PREV}..${TAG}" --pretty=format:'- %s (%h)' --reverse || true
echo ""
echo ""
echo "### Files changed"
echo ""
echo '```'
git diff "${PREV}..${TAG}" --stat | tail -20
echo '```'
echo ""
echo "See [CHANGELOG.md](CHANGELOG.md) for a curated summary."
