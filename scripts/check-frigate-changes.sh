#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
# Scan only fork-owned revisions and changed/untracked working-tree files.

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

usage() {
    echo 'Usage: check-frigate-changes.sh --staged|--worktree|--range BASE' >&2
    exit 2
}

case "${1:-}" in
    --staged|--worktree)
        [[ $# -eq 1 ]] || usage
        mode="$1"
        ;;
    --range)
        [[ $# -eq 2 ]] || usage
        mode="$1"
        base="$2"
        git rev-parse --verify "${base}^{commit}" >/dev/null
        ;;
    *)
        usage
        ;;
esac

command -v git >/dev/null
command -v python3 >/dev/null

test -f .gitleaks.toml || {
    echo 'ERROR: Missing .gitleaks.toml' >&2
    exit 1
}

scratch="$(mktemp -d)"
chmod 700 "$scratch"
trap 'rm -rf -- "$scratch"' EXIT

files="$scratch/files.z"

case "$mode" in
    --staged)
        git diff --cached --check
        git diff --cached --name-only --diff-filter=ACMR -z > "$files"
        ;;
    --range)
        git diff --check "${base}..HEAD"
        git diff --name-only --diff-filter=ACMR -z \
            "${base}..HEAD" > "$files"
        ;;
    --worktree)
        git diff --check HEAD
        git diff --name-only --diff-filter=ACMR -z HEAD > "$files"
        git ls-files --others --exclude-standard -z >> "$files"
        ;;
esac

# NUL-delimited paths correctly handle whitespace and unusual filenames.
# Never export files that traverse outside the scan directory.
python3 - "$files" "$scratch/source" "$mode" <<'PYTHON'
from pathlib import Path, PurePosixPath
import subprocess
import sys

names = Path(sys.argv[1]).read_bytes().split(b'\0')
root = Path(sys.argv[2])
mode = sys.argv[3]
count = 0

for raw in sorted(set(filter(None, names))):
    name = raw.decode('utf-8', 'surrogateescape')
    relative = PurePosixPath(name)

    if relative.is_absolute() or '..' in relative.parts:
        raise SystemExit(f'Unsafe file path: {name!r}')

    if mode == '--worktree':
        source = Path(name)
        if not source.is_file() or source.is_symlink():
            continue
        content = source.read_bytes()
    else:
        revision = f':{name}' if mode == '--staged' else f'HEAD:{name}'
        content = subprocess.check_output(['git', 'show', revision])

    target = root.joinpath(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    count += 1

print(f'Scanning {count} {mode} file(s)')
PYTHON

if [[ ! -d "$scratch/source" ]]; then
    echo 'PASS: No changed files to scan'
    exit 0
fi

if command -v gitleaks >/dev/null 2>&1; then
    gitleaks dir \
        --redact \
        --config "$PWD/.gitleaks.toml" \
        "$scratch/source"
elif command -v docker >/dev/null 2>&1; then
    docker run --rm \
        --mount "type=bind,src=$scratch/source,dst=/src,readonly" \
        --mount "type=bind,src=$PWD/.gitleaks.toml,dst=/config.toml,readonly" \
        ghcr.io/gitleaks/gitleaks:v8.30.1 \
        dir --redact --config /config.toml /src
else
    echo 'FAIL: Gitleaks or Docker is required' >&2
    exit 1
fi

echo "PASS: Gitleaks ($mode) and Git whitespace checks"
