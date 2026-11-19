# Frigate — Hailo-8 / HailoRT 4.24.0 Build

This repository is a development fork of [Frigate](https://github.com/blakeblackshear/frigate), focused on building **Frigate 0.18.2** for **64-bit ARM** systems with **Hailo-8** inference and **HailoRT 4.24.0**.

Frigate is developed and maintained by its upstream project. This fork is not an official Frigate release and is not affiliated with or endorsed by the upstream maintainers or Hailo.

## Scope

The changes in this fork focus on:

- Updating Hailo-8 installation and build steps for HailoRT 4.24.0.
- Building the HailoRT components needed by the container, including support for the Hailo multi-process service (MPS).
- Exposing Hailo detector options for MPS and a shared network group.
- Updating nginx build dependencies and compatibility patches required by this Frigate build.
- Applying a small video-player compatibility change needed alongside the build updates.

This is a targeted hardware/build fork, not a separate Frigate distribution or a general-purpose replacement for upstream releases.

## Source and branch

- Upstream: <https://github.com/blakeblackshear/frigate>
- Starting version: Frigate `v0.18.2`
- Development branch: `feature/frigate-0.18.2-hailort-4.24`
- Intended target: Linux `arm64` with a supported Hailo-8 accelerator

The branch and build artifacts are development work until explicitly tested and published. Do not assume an image exists at a registry solely because a tag is mentioned in development notes.

## Build-related files

| File | Purpose |
| --- | --- |
| `docker/main/build_hailort_mps.sh` | Builds HailoRT components with MPS support. |
| `docker/main/Dockerfile` | Integrates the HailoRT build into the Frigate image. |
| `docker/main/install_hailort.sh` | Updates HailoRT installation handling. |
| `docker/hailo8l/user_installation.sh` | Updates Hailo-related installation dependencies. |
| `frigate/detectors/plugins/hailo8l.py` | Adds Hailo detector MPS configuration options. |
| `docker/main/build_nginx.sh` | Updates nginx source dependencies and build compatibility. |
| `docker/main/rootfs/usr/local/nginx/conf/nginx.conf` | Accommodates the updated nginx module configuration. |
| `web/src/components/player/GenericVideoPlayer.tsx` | Includes a related player compatibility adjustment. |

For a precise account of a release, review the relevant Git diff and its testing results; this README does not substitute for build verification.

## Prerequisites and step-by-step installation

The HailoRT 4.24.0 **host PCIe kernel driver**, host runtime, firmware and
Multi-Process Service (MPS) must be installed and verified **before running**
the custom Frigate container. The Docker image supplies the container-side
HailoRT components but **does not install the host kernel driver**.

Follow **[Install HailoRT 4.24.0 and build Frigate](docs/INSTALL_HAILORT_4.24.md)**
in this order:

1. Check the ARM64 host, kernel headers and Hailo-8 hardware.
2. Build and install the matching Hailo PCIe driver 4.24.0.
3. Build/install HailoRT userspace 4.24.0 and the MPS service, following
   Hailo's release-specific documentation.
4. Verify the device, CLI, kernel module and running MPS socket.
5. Build the custom Frigate 0.18.2 Docker image for `linux/arm64`.
6. Configure device/socket access and enable MPS in Frigate.
7. Validate real Hailo inference and recheck the driver after kernel updates.

Use Hailo's official documentation for release-specific firmware, driver,
and MPS installation details; the guide links to those authoritative sources
rather than duplicating every platform-specific instruction.

### Example detector configuration

```yaml
detectors:
  hailo8l:
    type: hailo8l
    device: PCIe
    multi_process_service: true
    group_id: SHARED
```

The example requires a correctly installed, running host MPS service. The
full installation guide covers the container's `/dev/hailo0` device and
`/run/hailort` socket mounts.

## Security and contributions

Security checks should focus on the changes being contributed, while retaining Gitleaks' default detection rules. The repository's `.gitleaks.toml` contains a narrow exception for a known public dependency revision, not a blanket exception for source files or secret types.

Do not commit build logs, downloaded archives, local environment files, passwords, API tokens, certificates, or private deployment configuration. Report suspected vulnerabilities privately to the appropriate maintainers rather than publishing exploit details in an issue.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for this fork's contributor statement.

## Upstream documentation and attribution

For official installation, configuration, and troubleshooting guidance, use the [Frigate documentation](https://docs.frigate.video/). For upstream bug reports and features unrelated to this fork's HailoRT build changes, use the upstream project after confirming the issue occurs on an official Frigate release.

Frigate and third-party components retain their respective copyright notices and licenses. Consult the repository's license and dependency notices before redistribution.
