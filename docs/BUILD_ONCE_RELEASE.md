<!-- SPDX-License-Identifier: MIT -->
<!-- AI-assisted documentation; maintainer review required. -->
# Build once, publish RC, validate hardware, promote stable

The required Frigate HailoRT CI checks build both native AMD64 and ARM64
images. On a **push to `main` only**, the CI job saves each smoke-tested
Docker image, its SHA-256 checksum, and a build record as a downloadable
GitHub Actions artifact (`frigate-image-amd64` and `frigate-image-arm64`).
Pull requests still run builds and tests, but do not retain deployable image
artifacts. The artifacts expire after **14 days**; publish or save them
before expiry. Large container artifacts consume GitHub Actions storage.

For this release, the previously successful `main` CI run
`45061766119` retained both tested architecture artifacts. They are
eligible for publication only when the workflow verifies that no
intervening change affects image content, dependencies, or testing.
Future releases must use their own successful `main` CI artifacts.

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

## 4. Test the published RC on physical hardware

Deploy the **published RC tag**, not a private-registry image or a
locally retagged development image. Resolve its multi-architecture
manifest and ARM64 digest and record both. On the Hailo-8 PCIe host,
verify the matching host driver/runtime, active MPS service and
socket, healthy Frigate camera inference, and successful inference
from a second client using the same MPS group. Record the test date,
device/OS/kernel, image digest, result, and limitations in
[`docs/releases/0.18.3-hailort-4.24.0.md`](releases/0.18.3-hailort-4.24.0.md).

Do not promote on a skipped or failed hardware test.

## 5. Finalize release notes and documentation

After RC acceptance, correct every current-release version example,
record fixed issues and known limitations, and update `CHANGELOG.md`
and the versioned release notes. Keep documentation changes on a
signed feature branch, submit a PR, and wait for required CI.
The release workflow restricts reuse of prior image artifacts to
a narrow list of release documentation/workflow files. Any other
change requires rebuilding and repeating hardware validation.

## 6. Promote the approved RC to stable

Create a signed annotated release tag at the **current `main` commit**
after the release-documentation PR merges. The verified CI artifact
commit may be an earlier ancestor only when all intervening changes
are expressly allowed by the release workflow. The tag must match
the current `main` commit. Pushing a tag alone does not publish an
image or cause a rebuild.

```bash
git switch main || exit 1
git pull --ff-only origin main || exit 1
git status --short --branch
git tag -s "frigate-hailort-v$(cat release/VERSION)" \
    -m "Frigate HailoRT $(cat release/VERSION)"
git verify-tag "frigate-hailort-v$(cat release/VERSION)" || exit 1
git push origin "frigate-hailort-v$(cat release/VERSION)"
```

Then dispatch promotion of the **same RC number and CI run**.
The workflow checks release-note completeness and explicit hardware
verification before copying the RC manifest to stable:

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

**Important:** Application, dependency, build, or test changes merged
after the tested CI run require a new build and hardware test. Only
the narrowly scoped release-only exception documented below permits
reuse of earlier artifacts. Hardware verification is a maintainer
attestation, not something the GitHub runner can independently prove.

## Release recovery after a publication-workflow-only fix

A CI run records the application image build commit and the exact image ID
for each architecture. The publication workflow normally requires the run
commit to equal the current `main` commit. A narrowly scoped exception is
allowed when the selected CI commit is an ancestor of current `main` and
**every** intervening changed file is restricted to release tooling or
documentation. An application, build recipe, dependency, release-version,
or image-smoke-test change invalidates the old run and requires a new CI
artifact and hardware test. The workflow fails closed on any other path.

On the RC job, enable ARM64 QEMU userspace emulation before attempting the
ARM64 software smoke test on the AMD64 publication runner. This does not
rebuild either retained image. The previously verified physical ARM64
hardware test remains the release gate; emulation is only a software check.

**Hardware validation:** Build hosts without a physical Hailo-8 can complete
software CI. RC publication requires an explicit hardware verification
attestation. A skipped test is not a PASS. Run a concurrent MPS test on a
physical Hailo-8 host using a second client with `--multi-process-service`
and the same group ID while Frigate remains active. Verify image identity,
service and Frigate health, camera activity and inference, and successful
second-client output. Never hard-code private hostnames or registry URLs
into repository validation scripts. Portable automatic detection, remote
selection, and PASS/SKIPPED/FAIL modes remain tracked in
[issue #5](https://github.com/pmelendez2/frigate/issues/5);
this release workflow does **not** claim to implement that automation.

## 7. Publish GitHub Release notes

After the stable workflow passes, create a GitHub Release from
`frigate-hailort-v0.18.3-hailort-4.24.0` using `docs/releases/0.18.3-hailort-4.24.0.md` as its notes.
Confirm the release and manifest point to the intended tested
build. Do not mark the GitHub Release as a prerelease.
