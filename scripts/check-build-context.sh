#!/usr/bin/env bash
# AI-assisted: OpenAI ChatGPT; human verification required.
# Fail before an expensive build if required source-generated files are absent.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

[[ -s frigate/version.py ]] || {
    echo 'FAIL: Missing frigate/version.py; run prepare-frigate-version.sh' >&2
    exit 1
}
[[ -s web/.env ]] || {
    echo 'FAIL: Missing web/.env; run prepare-frigate-version.sh' >&2
    exit 1
}
[[ -f docker/main/Dockerfile ]] || exit 1
[[ -f docker/main/build_hailort_mps.sh ]] || exit 1
[[ -f .dockerignore ]] || exit 1
if grep -Eq '^[[:space:]]*frigate/version\.py[[:space:]]*$' .dockerignore; then
    echo 'FAIL: .dockerignore excludes frigate/version.py' >&2
    exit 1
fi

python3 -m py_compile frigate/version.py
printf 'PASS: Frigate version module and Docker build context verified\n'
