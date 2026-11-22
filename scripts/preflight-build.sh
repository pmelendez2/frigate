#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
# Required by local builds and both CI architecture jobs.

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

echo '=== Public-content and documentation checks ==='
python3 scripts/check-documentation.py
python3 scripts/sync-release-docs.py --check
python3 tools/update-hailo8-component-guide.py --check
python3 -m unittest discover \
    -s tests -p 'test_hailo8_component_guide.py' -v
python3 scripts/check-public-content.py

echo '=== Gitleaks: changes since upstream base ==='
bash scripts/check-frigate-changes.sh --range v0.18.2

echo '=== Gitleaks: staged changes ==='
bash scripts/check-frigate-changes.sh --staged

echo '=== Gitleaks: tracked edits and untracked files ==='
bash scripts/check-frigate-changes.sh --worktree

echo 'PASS: Build preflight complete'
