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

git clone --depth=1 --branch v4.24.0 \
    https://github.com/hailo-ai/hailort.git "$scratch/hailort"
actual="$(git -C "$scratch/hailort" describe --tags --exact-match)"
[[ "$actual" == v4.24.0 ]] || {
    echo "ERROR: Unexpected HailoRT tag: $actual" >&2
    exit 1
}
mkdir -p "$dest"
git -C "$scratch/hailort" archive --format=tar HEAD | tar -xf - -C "$dest"
[[ -f "$dest/CMakeLists.txt" ]] || {
    echo 'ERROR: HailoRT source export incomplete' >&2
    exit 1
}
echo "PASS: Exported HailoRT $actual into $dest"
