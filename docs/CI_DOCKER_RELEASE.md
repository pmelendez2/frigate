<!-- SPDX-License-Identifier: MIT -->
<!-- AI-assisted documentation; maintainer review required. -->

# CI, validation, and Docker Hub releases

<!-- BEGIN GENERATED RELEASE METADATA -->
| Release metadata | Value |
| --- | --- |
| Release | `0.18.3-hailort-4.24.0` |
| Frigate | `0.18.3` |
| HailoRT | `4.24.0` |
| Docker Hub image | `docker.io/pmelendez2/frigate:0.18.3-hailort-4.24.0` |
| Hailo-8 hardware validation | Raspberry Pi 5 ARM64 only |
| AMD64 Hailo-8 hardware validation | Not performed |
<!-- END GENERATED RELEASE METADATA -->

This fork maintains Frigate's upstream source while adding Hailo-8 and
HailoRT 4.24.0 support. The GitHub repository and Docker Hub image use the
name `pmelendez2/frigate`. The project-specific overview is in
[HAILO8.md](../HAILO8.md); upstream `README.md` is retained.

## Release responsibilities

- **Developer builds:** Use the scripts in this repository to prepare the
  source tree, scan fork changes with Gitleaks, check documentation, build an
  image, and run hardware-free software validation.
- **Pull requests:** Run the required `isolated`, `image-build-amd64`, and
  `image-build-arm64` checks before merging into a protected branch.
- **Signed release tags:** Re-run security and image validation; publish both
  architectures to Docker Hub only after the checks succeed.
- **Hardware tests:** Deploy the ARM64 image on a compatible Hailo-8 system
  and verify PCIe driver, MPS service, API health, and real inference.
  AMD64 CI does not establish AMD64 hardware inference compatibility.

## First-time repository setup

1. Enable GitHub Actions for the fork and configure branch protection for
   the intended integration branch. The workflows currently target `main`;
   establish that branch deliberately if the fork uses another default.
2. Require the `isolated`, `image-build-amd64`, and `image-build-arm64`
   checks after their first successful execution. Do not bypass failed jobs.
3. Create the Docker Hub repository `pmelendez2/frigate` and configure the
   `DOCKERHUB_TOKEN` GitHub Actions repository secret with limited write
   permissions. Do not commit credentials or print token values.
4. Configure a `dockerhub-release` environment if approval is required.
5. Enable the repository's Git hooks from the **repository root**:

   ```bash
   git config --local core.hooksPath .githooks
   chmod +x .githooks/pre-commit .githooks/pre-push
   ```

## Required pre-build security and documentation checks

Run from the **repository root**:

```bash
bash scripts/preflight-build.sh
bash scripts/prepare-frigate-version.sh
bash scripts/check-build-context.sh
```

`prepare-frigate-version.sh` executes the same security and documentation
preflight, so a local Docker build cannot skip it. The security checks use
Gitleaks' default rules plus the narrow exceptions in `.gitleaks.toml`.
They scan fork changes since the upstream `v0.18.3` base as well as staged,
unstaged, and untracked nonignored files; unrelated upstream history is not
re-scanned. Failures stop the build. Missing Gitleaks tooling also fails
closed. CI runners must fetch sufficient Git history for the base comparison.

The public-content preflight examines all tracked and nonignored untracked
Markdown and reStructuredText documents for personal checkout paths,
local file URLs, private registry identifiers, internal network
addresses, and host-specific examples. It reports only file names,
line numbers, and issue categories, not the matched private text.
This applies to upstream documentation too, without modifying it.
Legitimate host device paths such as `/dev/hailo0` and the MPS
socket `/run/hailort/hailort_uds.sock` remain documented.

The version-generation target produces the ignored `frigate/version.py` and
`web/.env`; a complete image test must import `frigate.version`. Software
validation verifies HailoRT 4.24.0 and nginx 1.31.9 without an attached
accelerator. Hardware validation is always separate.

## Build and validate a development image

The repository includes a hardware-free build command for either supported
architecture. It runs the required documentation, privacy, and Gitleaks
checks **before** invoking Docker Buildx, then tests the finished image.

```bash
bash scripts/build-frigate-local.sh frigate:development-arm64 arm64
```

For AMD64, specify `amd64` and a distinct development tag. Docker Buildx
must support the selected target architecture. Local builds are not
published automatically; release publication is handled by GitHub Actions
only after the signed release and multi-platform checks succeed.

## Feature branches and pull requests

Stage only intended changes. Confirm the security and documentation checks
pass, create a signed commit, and push the feature branch. Open a pull
request against the protected integration branch. The required CI checks
must pass before merging. The `isolated` check compares changes against the
upstream base, not against thousands of unrelated historical commits.

## Signed-tag release

After merging and verifying the integration branch, use the version in
[`release/VERSION`](../release/VERSION) to create and verify a signed tag.
The release workflow requires a signed tag, matching version, and a commit
reachable from the configured integration branch.

```bash
git switch main
git pull --ff-only origin main
git status --short --branch
git tag -s "frigate-hailort-v$(cat release/VERSION)" \
    -m "Frigate HailoRT $(cat release/VERSION)"
git verify-tag "frigate-hailort-v$(cat release/VERSION)"
git push origin "frigate-hailort-v$(cat release/VERSION)"
```

The release publishes `docker.io/pmelendez2/frigate` for `linux/amd64` and
`linux/arm64` under one version tag plus a source-commit tag. It does not
publish `latest`. Both architecture builds, tests, and the final manifest
verification must pass; do not publish a partially tested architecture.
The release version and target hardware are described in
[VERSION.md](../VERSION.md).

## Deployment and rollback

Follow [Frigate's official installation guide](https://docs.frigate.video/frigate/installation/)
for persistent storage, cameras, and networking. Verify the target host's
Hailo PCIe driver, firmware, and MPS socket as described in
[INSTALL_HAILORT_4.24.md](INSTALL_HAILORT_4.24.md). Deploy the immutable image
tag and run `scripts/test-frigate-deployment.sh` from the repository root.
Verify actual camera inference separately. Retain the prior working image
tag and Compose configuration for rollback.

## AI-assisted contributions

See [AIUSAGE.md](../AIUSAGE.md). Human maintainers review generated
changes and remain responsible for signing and publishing releases.

## Current hardware-gated Docker Hub publication process

For the HailoRT 4.24.0 fork, the authoritative release procedure is
`docs/BUILD_ONCE_RELEASE.md`: successful `main` CI exports AMD64/ARM64
images, the ARM64 image is checked on physical Hailo hardware, then
`docker-publish.yml` is dispatched for RC publication. Stable promotion
uses a verified signed annotated tag and reuses the RC manifest without
rebuilding. Do **not** rely on older tag-triggered publication instructions
for this release. Hardware-aware automation remains tracked in
[issue #5](https://github.com/pmelendez2/frigate/issues/5).
