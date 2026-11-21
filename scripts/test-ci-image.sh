#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
# Validate dependencies and application imports, without an accelerator.

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo 'Usage: test-ci-image.sh IMAGE amd64|arm64' >&2
    exit 2
fi

image="$1"
arch="$2"

if [[ "$arch" != amd64 && "$arch" != arm64 ]]; then
    echo "FAIL: Unsupported architecture: $arch" >&2
    exit 2
fi

platform="linux/$arch"
actual="$(docker image inspect "$image" --format '{{.Architecture}}')"

if [[ "$actual" != "$arch" ]]; then
    echo "FAIL: Expected architecture $arch; found $actual" >&2
    exit 1
fi

echo "PASS: Image architecture $actual"

docker run \
    --rm \
    --platform "$platform" \
    --network none \
    --entrypoint /bin/sh \
    "$image" -ec '
        test -x /usr/local/bin/hailortcli
        test -f /usr/local/lib/libhailort.so.4.24.0
        test -x /usr/local/nginx/sbin/nginx

        /usr/local/nginx/sbin/nginx -v 2>&1 |
            grep -F nginx/1.31.9

        /usr/local/bin/hailortcli --version 2>&1 |
            grep -F 4.24.0

        python3 -c "import hailo_platform"

        test -d /opt/frigate/frigate
        test -s /opt/frigate/frigate/version.py

        cd /opt/frigate
        python3 -c "from frigate.version import VERSION; assert VERSION; print(VERSION)"
    '

echo "PASS: Frigate/HailoRT software checks ($platform)"
