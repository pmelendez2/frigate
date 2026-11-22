#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
# Generate Frigate's ignored runtime version module before Docker builds.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

[[ -f Makefile && -d frigate && -d web ]] || {
    echo 'FAIL: Run from the Frigate source checkout' >&2
    exit 1
}
command -v make >/dev/null

# These checks are required for both local and automated builds.
bash scripts/preflight-build.sh

# Frigate requires the generated version module at application startup.
make version

[[ -s frigate/version.py ]] || {
    echo 'FAIL: make version did not generate frigate/version.py' >&2
    exit 1
}
[[ -s web/.env ]] || {
    echo 'FAIL: make version did not generate web/.env' >&2
    exit 1
}
python3 -m py_compile frigate/version.py
python3 - <<'PY'
import importlib.util
from pathlib import Path

path = Path('frigate/version.py')
spec = importlib.util.spec_from_file_location('frigate_build_version', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert isinstance(module.VERSION, str) and module.VERSION.startswith('0.18.3-')
print(f'PASS: Generated Frigate version {module.VERSION}')
PY

echo 'PASS: Frigate build context contains generated version module'
