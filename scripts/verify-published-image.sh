#!/usr/bin/env bash
# AI-assisted: OpenAI ChatGPT; human verification required.
# SPDX-License-Identifier: MIT
set -euo pipefail
[[ $# == 1 ]] || {
    echo 'Usage: scripts/verify-published-image.sh IMAGE:TAG' >&2
    exit 2
}
image="$1"
raw="$(mktemp)"
trap 'rm -f "$raw"' EXIT
docker buildx imagetools inspect --raw "$image" > "$raw"
python3 - "$raw" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
platforms = {
    (item.get('platform', {}).get('os'),
     item.get('platform', {}).get('architecture'))
    for item in data.get('manifests', [])
}
expected = {('linux', 'amd64'), ('linux', 'arm64')}
if not expected.issubset(platforms):
    raise SystemExit(f'FAIL: Missing platforms: {expected - platforms}')
print('PASS: Docker Hub manifest has linux/amd64 and linux/arm64')
PY
