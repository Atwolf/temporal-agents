#!/bin/bash
set -euo pipefail

# Only run in remote (web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Install project with dev dependencies
pip install -e ".[dev]"

# Seed agent definitions DB (idempotent)
python -m temporal_agents.db.seed
