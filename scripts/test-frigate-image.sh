#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
# Single-platform, hardware-free image verification.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo 'Usage: test-frigate-image.sh IMAGE' >&2
    exit 2
fi

image="$1"
arch="$(docker image inspect "$image" --format '{{.Architecture}}')"

case "$arch" in
    arm64|amd64)
        ;;
    *)
        echo "FAIL: Unsupported image architecture: $arch" >&2
        exit 1
        ;;
esac

echo "=== Image validation ($arch) ==="

bash "$(dirname "$0")/test-ci-image.sh" "$image" "$arch"

echo 'PASS: Image validated without Hailo hardware'
