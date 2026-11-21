<!-- SPDX-License-Identifier: MIT -->
<!-- AI-assisted documentation; maintainer review required. -->

# Versions and hardware scope

<!-- BEGIN GENERATED RELEASE METADATA -->
| Release metadata | Value |
| --- | --- |
| Release | `0.18.2-hailort-4.24.0` |
| Frigate | `0.18.2` |
| HailoRT | `4.24.0` |
| Docker Hub image | `docker.io/pmelendez2/frigate:0.18.2-hailort-4.24.0` |
| Hailo-8 hardware validation | Raspberry Pi 5 ARM64 only |
| AMD64 Hailo-8 hardware validation | Not performed |
<!-- END GENERATED RELEASE METADATA -->

| Component | Version or status |
| --- | --- |
| Upstream Frigate baseline | 0.18.2 |
| HailoRT library, CLI and MPS | 4.24.0 |
| nginx | 1.31.9 |
| Docker image platforms | `linux/amd64`, `linux/arm64` |
| Intended accelerator | Hailo-8 PCIe |
| Hailo-8L | Not validated |
| Hailo-10 / Hailo-10H | Not supported by this customization |
| Docker Hub image name | `docker.io/pmelendez2/frigate` |
| Release tag | `0.18.2-hailort-4.24.0` |

The version tag is sourced from [`release/VERSION`](release/VERSION).
Frigate's runtime Python version module is generated with `make version`.
Neither this file nor the Docker Hub tag replaces `frigate/version.py`.

Successful CI without accelerator hardware does not establish working
Hailo-8 inference. Record hardware-validation results for each tested device separately.
