#!/usr/bin/env bash
set -euo pipefail

# Install all Playwright browser engines and print versions
if ! command -v playwright >/dev/null 2>&1; then
  echo "playwright CLI not found. Activate your venv and ensure 'pip install playwright' succeeded." >&2
  exit 1
fi

playwright install webkit chromium firefox
playwright --version