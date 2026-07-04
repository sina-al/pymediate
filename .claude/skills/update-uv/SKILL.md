---
name: update-uv
description: Bump the pinned uv version in this repo (pyproject.toml's [tool.uv] required-version) and update the local uv install to match. Use when asked to update/upgrade uv, or when `poe update-uv:check` reports the pin is behind latest.
---

# /update-uv — bump the pinned uv version

All the logic lives in `scripts/update_uv.py`, wired up as poe tasks — this skill just points
to them rather than re-describing what the script already does.

## Run it

```bash
uv run poe update-uv          # bump pyproject.toml + local uv install to the latest release
uv run poe update-uv:check    # report pinned vs. latest, exit 1 if behind (safe to script/CI)
```

For a specific version instead of latest, or to edit `pyproject.toml` without touching the local
install, call the script directly — see `python3 scripts/update_uv.py --help`.

## Why a pin exists at all

`pyproject.toml`'s `[tool.uv] required-version` is the single source of truth: `uv` itself
enforces it locally (hard error on mismatch), and `astral-sh/setup-uv` in CI reads it
automatically when no explicit `version:` input is given — so this one line is the only place
that ever needs updating. Don't hand-edit it; run the script so the local install stays in sync
with the pin.

## After bumping

Run `uv run poe check:all` (or at least `poe test`) to confirm nothing in the resolved
environment shifted. Commit the `pyproject.toml` change — `uv.lock` may also change if resolver
behavior shifted between uv versions; check `git diff uv.lock` and include it if so.
