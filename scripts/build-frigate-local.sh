#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
# Build and validate Frigate locally; publish only when requested.

set -Eeuo pipefail

usage()
{
    cat <<'EOF'
Usage: scripts/build-frigate-local.sh IMAGE [amd64|arm64] [--push]

Build a Frigate image with HailoRT 4.24.0 using repository-local scripts.

  IMAGE       Fully qualified or local Docker image tag.
  amd64|arm64 Target architecture (default: current host architecture).
  --push      Push the tested image to IMAGE's registry (optional).

The build always runs security, privacy, documentation, version, and
image checks before any optional push. A Hailo accelerator is not needed.

Examples:
  ./scripts/build-frigate-local.sh frigate:dev arm64
  ./scripts/build-frigate-local.sh frigate:dev amd64
  ./scripts/build-frigate-local.sh registry.example:5000/frigate:dev \
      arm64 --push
EOF
}

if [[ $# -eq 0 || ${1:-} == -h || ${1:-} == --help ]]; then
    usage
    if [[ $# -eq 0 ]]; then
        exit 2
    fi
    exit 0
fi

if (( $# > 3 )); then
    usage >&2
    exit 2
fi

image="$1"
arch="${2:-$(uname -m)}"
publish="${3:-}"

case "$arch" in
    x86_64) arch=amd64 ;;
    aarch64) arch=arm64 ;;
    amd64|arm64) ;;
    *)
        echo "ERROR: Unsupported platform: $arch" >&2
        exit 2
        ;;
esac

if [[ -n "$publish" && "$publish" != --push ]]; then
    echo "ERROR: Unrecognized option: $publish" >&2
    exit 2
fi

# Resolve every repository file from this script, not the caller's cwd.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

scratch="$(mktemp -d)"
chmod 700 "$scratch"
trap 'rm -rf -- "$scratch"' EXIT

printf '\n=== Security and documentation preflight ===\n'
bash "$script_dir/preflight-build.sh"

printf '\n=== Generate Frigate version metadata ===\n'
bash "$script_dir/prepare-frigate-version.sh"
bash "$script_dir/check-build-context.sh"

printf '\n=== Prepare HailoRT 4.24.0 source ===\n'
bash "$script_dir/prepare-hailort-source.sh" "$scratch/hailort-src"

printf '\n=== Build Frigate for linux/%s ===\n' "$arch"
docker buildx build \
    --platform "linux/$arch" \
    --build-context "hailort-src=$scratch/hailort-src" \
    --target frigate \
    --file "$repo_root/docker/main/Dockerfile" \
    --tag "$image" \
    --load \
    "$repo_root"

printf '\n=== Validate complete Frigate image ===\n'
bash "$script_dir/test-ci-image.sh" "$image" "$arch"

if [[ "$publish" == --push ]]; then
    printf '\n=== Publish verified image ===\n'
    docker push "$image"
    echo "PASS: Published $image"
else
    echo "PASS: Built and validated $image (no registry push)"
fi
