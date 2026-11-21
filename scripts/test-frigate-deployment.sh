#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
# Read-only checks for a Hailo-8 host running Frigate.
set -uo pipefail

CONTAINER="${1:-frigate}"
# Override EXPECTED_TAG to validate a development image.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_version="$(cat "$repo_root/release/VERSION")"
EXPECTED_TAG="${EXPECTED_TAG:-$release_version}"
failed=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; failed=$((failed + 1)); }
warn() { printf 'WARN: %s\n' "$1"; }

printf 'Container: %s\n' "$CONTAINER"
if ! docker inspect --type container "$CONTAINER" >/dev/null 2>&1; then
    fail "Container not found: $CONTAINER"
    exit 1
fi

state=$(docker inspect --type container "$CONTAINER" \
    --format '{{.State.Running}}' 2>/dev/null) || state='unknown'
if [[ "$state" == true ]]; then
    pass 'Frigate container is running'
else
    fail "Frigate container not running (state=$state)"
fi

image=$(docker inspect --type container "$CONTAINER" \
    --format '{{.Config.Image}}' 2>/dev/null) || image=''
if [[ "$image" == *"$EXPECTED_TAG" ]]; then
    pass "Expected Frigate image is deployed: $image"
else
    fail "Unexpected deployed image: ${image:-unknown}"
fi

arch=$(uname -m)
if [[ "$arch" == aarch64 ]]; then
    pass 'Host architecture is aarch64'
else
    fail "Host architecture is $arch, expected aarch64"
fi

if [[ -c /dev/hailo0 ]]; then
    pass 'Host Hailo device exists'
else
    fail '/dev/hailo0 is not a character device'
fi

if [[ -S /run/hailort/hailort_uds.sock ]]; then
    pass 'Host HailoRT MPS socket exists'
else
    fail 'Host MPS socket is absent'
fi

if systemctl is-active --quiet hailort.service; then
    pass 'Host HailoRT MPS service is active'
else
    fail 'Host HailoRT MPS service is not active'
fi

if command -v hailortcli >/dev/null 2>&1 && \
    hailortcli --version 2>&1 | grep -Fq '4.24.0'; then
    pass 'Host HailoRT CLI version is 4.24.0'
else
    fail 'Host HailoRT CLI is absent or not 4.24.0'
fi

if [[ -r /sys/module/hailo_pci/version ]]; then
    driver=$(cat /sys/module/hailo_pci/version)
    if [[ "$driver" == *'4.24.0'* ]]; then
        pass 'Host Hailo PCIe driver reports 4.24.0'
    else
        warn "Driver version is $driver (check compatibility manually)"
    fi
else
    fail 'Hailo PCIe driver version cannot be read'
fi

mounts=$(docker inspect --type container "$CONTAINER" \
    --format '{{range .Mounts}}{{.Source}}:{{.Destination}}{{"\n"}}{{end}}' \
    2>/dev/null) || mounts=''
if grep -Fq '/run/hailort:/run/hailort' <<< "$mounts"; then
    pass 'Host MPS directory is mounted into Frigate'
else
    fail 'Frigate MPS directory bind mount missing'
fi

if [[ "$state" == true ]]; then
    if docker exec "$CONTAINER" test -c /dev/hailo0; then
        pass 'Frigate container can see Hailo device'
    else
        fail 'Frigate container cannot see Hailo device'
    fi
    if docker exec "$CONTAINER" test -S \
        /run/hailort/hailort_uds.sock; then
        pass 'Frigate container can see MPS socket'
    else
        fail 'Frigate container cannot see MPS socket'
    fi
    if docker exec "$CONTAINER" /bin/sh -ec \
        'hailortcli --version 2>&1 | grep -F "4.24.0" >/dev/null'; then
        pass 'Container HailoRT CLI version is 4.24.0'
    else
        fail 'Container HailoRT CLI is not 4.24.0'
    fi
    if docker exec "$CONTAINER" /bin/sh -ec \
        'curl -fsS --max-time 10 http://localhost:5000/api/version' \
        >/dev/null; then
        pass 'Frigate internal version API responds'
    else
        fail 'Frigate internal version API does not respond'
    fi
fi

health=$(docker inspect --type container "$CONTAINER" \
    --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
    2>/dev/null) || health='unknown'
case "$health" in
    healthy) pass 'Docker health status is healthy' ;;
    starting) fail 'Docker health status is still starting' ;;
    *) fail "Docker health status is $health" ;;
esac

printf '\nDeployment checks failed: %d\n' "$failed"
if (( failed > 0 )); then
    exit 1
fi
printf 'PASS: Deployment prerequisites and API checks complete\n'
printf 'NOTE: Confirm real camera detections separately; this test does not\n'
printf '      prove successful inference or video stream processing.\n'
