#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# 1. Conform the installed uv to pyproject.toml's pin. Use pip, not `uv self update` or the
#    astral.sh installer: both fetch from github.com, which this environment's outbound proxy
#    blocks; PyPI is allowlisted and reliable here.
required_uv="$(grep -oP 'required-version\s*=\s*"==\K[^"]+' pyproject.toml || true)"
if [ -n "$required_uv" ]; then
  current_uv="$(uv --version 2>/dev/null | awk '{print $2}' || echo none)"
  if [ "$current_uv" != "$required_uv" ]; then
    pip install --user --quiet --upgrade "uv==$required_uv"
  fi
fi
export PATH="$HOME/.local/bin:$PATH"
echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"

# 2. gh CLI — Ubuntu's default universe archive already carries it, no extra apt repo needed.
if ! command -v gh >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq gh
fi

# 3. Python deps, per this repo's documented sync command.
uv sync --all-extras --group test
