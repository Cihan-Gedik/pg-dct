# Releases and version history

How to see **what changed** in a tag, commit, or release — locally and on GitHub.

---

## Quick reference

| Goal | Command / link |
|------|----------------|
| All tags | `git fetch --tags && git tag --list --sort=-v:refname` |
| Human-readable history | [CHANGELOG.md](../CHANGELOG.md) |
| Changes between two versions | `git log v0.2.0..v0.2.1 --oneline` |
| Files changed | `git diff v0.2.0..v0.2.1 --stat` |
| One tag detail | `git show v0.2.1 --stat` |
| GitHub compare | https://github.com/Cihan-Gedik/pg-dct/compare/v0.2.0...v0.2.1 |
| GitHub tags | https://github.com/Cihan-Gedik/pg-dct/tags |

---

## Generate release notes (script)

From repo root:

```bash
chmod +x scripts/release-notes.sh
./scripts/release-notes.sh v0.2.0 v0.2.1
```

Or via Make:

```bash
make release-notes PREV=v0.2.0 TAG=v0.2.1
```

Output is Markdown you can paste into a [GitHub Release](https://github.com/Cihan-Gedik/pg-dct/releases/new).

---

## Cut a new release (maintainer)

1. Update [CHANGELOG.md](../CHANGELOG.md): move items from `[Unreleased]` into a new `## [x.y.z] - YYYY-MM-DD` section.
2. Bump versions in `ui/package.json` and `backend/pyproject.toml`.
3. Build UI: `make ui-build`
4. Commit, tag, push:

```bash
git add CHANGELOG.md ui/package.json backend/pyproject.toml backend/app/static
git commit -m "Release v0.2.2: short summary of why."
git tag -a v0.2.2 -m "Release v0.2.2"
git push origin main
git push origin v0.2.2
```

5. Create GitHub Release (optional but professional):

```bash
gh release create v0.2.2 \
  --title "v0.2.2" \
  --notes-file <(./scripts/release-notes.sh v0.2.1 v0.2.2)
```

Or copy the **CHANGELOG** section for that version into the release description on the web UI.

---

## Semantic versioning (this repo)

| Bump | When |
|------|------|
| **PATCH** (0.2.1 → 0.2.2) | Bug fixes, small UI tweaks |
| **MINOR** (0.2.x → 0.3.0) | New features (new API, dashboard panel) |
| **MAJOR** (1.0.0) | Breaking API or config changes |

---

## API version

The running API reports its package version from `backend/pyproject.toml`. After deploy/restart, check:

```bash
curl -s http://127.0.0.1:8080/openapi.json | python3 -c "import json,sys; print(json.load(sys.stdin).get('info',{}).get('version'))"
```

(UI build is tied to `ui/package.json`; keep both in sync on release.)
