#!/usr/bin/env bash
# AI-assisted: OpenAI ChatGPT; human verification required.
# SPDX-License-Identifier: MIT
# Create clean HailoRT v4.24.0 external Docker build context.
set -euo pipefail
[[ $# == 1 ]] || {
    echo 'Usage: scripts/prepare-hailort-source.sh OUTPUT_DIRECTORY' >&2
    exit 2
}
dest="$1"
[[ ! -e "$dest" ]] || {
    echo "ERROR: Destination already exists: $dest" >&2
    exit 1
}
command -v git >/dev/null
command -v tar >/dev/null
scratch="$(mktemp -d)"
trap 'rm -rf -- "$scratch"' EXIT

hailort_repo="https://github.com/pmelendez2/hailort.git"
hailort_commit="12ca1995d83db8432f037300349c331267f4abb0"

git init -q "$scratch/hailort"
git -C "$scratch/hailort" remote add origin "$hailort_repo"
git -C "$scratch/hailort" fetch -q --depth=1 origin "$hailort_commit"

actual="$(git -C "$scratch/hailort" rev-parse FETCH_HEAD)"
[[ "$actual" == "$hailort_commit" ]] || {
    echo "ERROR: HailoRT source commit mismatch: $actual" >&2
    exit 1
}
mkdir -p "$dest"
git -C "$scratch/hailort" archive --format=tar "$actual" | tar -xf - -C "$dest"
[[ -f "$dest/CMakeLists.txt" ]] || {
    echo 'ERROR: HailoRT source export incomplete' >&2
    exit 1
}
echo "PASS: Exported HailoRT $actual into $dest"
