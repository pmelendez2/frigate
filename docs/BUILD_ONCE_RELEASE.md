<!-- SPDX-License-Identifier: MIT -->
<!-- AI-assisted documentation; maintainer review required. -->
# Build once, test hardware, publish RC, promote stable

The required Frigate HailoRT CI checks build both native AMD64 and ARM64
images. On a **push to `main` only**, the CI job saves each smoke-tested
Docker image, its SHA-256 checksum, and a build record as a downloadable
GitHub Actions artifact (`frigate-image-amd64` and `frigate-image-arm64`).
Pull requests still run builds and tests, but do not retain deployable image
artifacts. The artifacts expire after **14 days**; publish or save them
before expiry. Large container artifacts consume GitHub Actions storage.

The completed CI run from before this change cannot supply an image artifact.
A new successful `main` CI run is required after this change is merged.

## 1. Find the successful main CI run

From the repository root:

```bash
REPO=pmelendez2/frigate
gh run list --repo "$REPO" --workflow ci.yml --branch main --limit 10
```

Record the successful `push` run ID at the desired `main` commit.

## 2. Load the exact ARM64 CI image on the hardware test host

The GitHub CLI must be authenticated with permission to read run artifacts.
Use a temporary working directory; do not mount production configuration
into a second concurrently running Frigate container.

```bash
REPO=pmelendez2/frigate
RUN_ID=REPLACE_WITH_SUCCESSFUL_MAIN_CI_RUN_ID
mkdir -p "$HOME/frigate-ci-arm64"
gh run download "$RUN_ID" --repo "$REPO" \
    --name frigate-image-arm64 --dir "$HOME/frigate-ci-arm64"
cd "$HOME/frigate-ci-arm64" || exit 1
sha256sum -c image.tar.zst.sha256 || exit 1
zstd -dc image.tar.zst | docker load || exit 1
docker image inspect frigate:ci-arm64 \
    --format 'Architecture={{.Architecture}} ID={{.Id}}'
cat build.txt
```

Confirm that `build.txt` matches the approved commit SHA, image ID,
architecture, and version. Keep production running until a consistent
configuration/database backup and a tested rollback are available.

For live hardware testing, deploy the loaded image using the existing host's
container-management procedure. The container must have its expected Hailo
device and `/run/hailort` socket access. Verify application health and real
Hailo-8 inference; hardware-free image smoke tests alone do not suffice.
Record the tested CI run ID and image ID. Do not publish an unverified RC.

## 3. Publish the tested artifacts as a Docker Hub RC

The `docker-publish.yml` workflow uses `workflow_dispatch` on `main`.
It requires the successful `main` CI run ID, the desired RC number,
`stage=rc`, and explicit `hardware_verified=true` confirmation.
The `dockerhub-release` GitHub environment can require maintainer approval.
This workflow downloads and validates both CI artifacts, then pushes each
architecture and assembles the multiarchitecture RC manifest. It does not
rebuild the images.

```bash
gh workflow run docker-publish.yml \
    --repo pmelendez2/frigate --ref main \
    -f ci_run_id=REPLACE_WITH_SUCCESSFUL_MAIN_CI_RUN_ID \
    -f stage=rc -f rc_number=1 -f hardware_verified=true
```

After publication, verify the RC manifest and architecture entries:

```bash
docker buildx imagetools inspect \
    docker.io/pmelendez2/frigate:0.18.3-hailort-4.24.0-rc.1
```

## 4. Promote the approved RC to stable

First create a signed annotated release tag at the **same main commit**
as the successful CI run. The release workflow verifies the signed Git tag
through GitHub before stable promotion. Pushing this tag alone does not
publish or rebuild Docker images.

```bash
git switch main || exit 1
git pull --ff-only origin main || exit 1
git status --short --branch
git tag -s "frigate-hailort-v$(cat release/VERSION)" \
    -m "Frigate HailoRT $(cat release/VERSION)"
git verify-tag "frigate-hailort-v$(cat release/VERSION)" || exit 1
git push origin "frigate-hailort-v$(cat release/VERSION)"
```

Then dispatch promotion of the **same RC number and CI run**:

```bash
gh workflow run docker-publish.yml \
    --repo pmelendez2/frigate --ref main \
    -f ci_run_id=REPLACE_WITH_SUCCESSFUL_MAIN_CI_RUN_ID \
    -f stage=stable -f rc_number=1 -f hardware_verified=true
```

The stable action remotely re-tags the existing RC manifest with
`0.18.3-hailort-4.24.0` without compiling or repackaging application
layers. It checks both architectures again. Keep the RC and per-architecture
tags available for audit and rollback. A stable release should remain
immutable once clients use it.

**Important:** Any change merged into `main` after the tested CI run
requires a new CI build and hardware test; the publication gate refuses
artifacts from an older commit. Hardware verification is a maintainer
attestation, not something the GitHub runner can independently prove.
