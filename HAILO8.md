<!-- SPDX-License-Identifier: MIT -->
<!-- AI-assisted documentation; maintainer review required. -->

# Frigate — Hailo-8 / HailoRT 4.24.0 Build

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

This repository is a development fork of [Frigate](https://github.com/blakeblackshear/frigate), focused on building **Frigate 0.18.3** for **ARM64 and AMD64** Linux systems with **Hailo-8** inference and **HailoRT 4.24.0**.

Frigate is developed and maintained by its upstream project. This fork is not an official Frigate release and is not affiliated with or endorsed by the upstream maintainers or Hailo.

<!-- BEGIN HAILO8 COMPONENT INSTALLATION -->
## Install the three Hailo-8 components and understand their roles

This custom build targets **Frigate 0.18.3**, **HailoRT 4.24.0**, and a
**full Hailo-8 accelerator on Raspberry Pi 5 (Linux ARM64)**. This is the only
hardware configuration validated for this fork. AMD64 image builds are
software checks, **not** evidence of AMD64 Hailo-8 inference compatibility.
Hailo-8L and Hailo-10 hardware have not been validated with this fork.

**The image does not contain everything needed to operate a PCIe Hailo-8.**
A container shares the host's Linux kernel, so a kernel PCIe device driver
cannot be installed as part of an ordinary Frigate image. The host-side
MPS service must also run separately so multiple containers/processes can
share the device. Here is the actual division of responsibilities:

| Component | Where installed | Why it is needed |
| --- | --- | --- |
| Hailo PCIe driver 4.24.0 and device firmware | Raspberry Pi 5 **host** | Binds the PCIe Hailo-8, exposes the device interface, and loads firmware; a container cannot supply the host kernel module |
| HailoRT 4.24.0 host runtime and patched MPS service | Raspberry Pi 5 **host** | Owns/schedules the shared device, coordinates clients, and cleans up disconnected clients; **the container image does not replace the running host service** |
| Frigate 0.18.3 with HailoRT 4.24.0 userspace library/CLI | **Container image** | Runs object detection as an MPS client; connects to the host service through the mounted Unix-domain socket |

### 1. Install the PCIe driver on the host

Download the **matching 4.24.0 PCIe driver**, not an arbitrary newer
release:

- [Official Hailo PCIe driver 4.24.0 release](https://github.com/hailo-ai/hailort-drivers/releases/tag/v4.24.0)
- [Hailo PCIe driver source](https://github.com/hailo-ai/hailort-drivers)
- [Hailo's Linux PCIe driver installation instructions](https://hailo.ai/developer-zone/documentation/hailort/latest-hailo8/?sp_referrer=drivers/pcie_linux.html)

For a source checkout, use:

```bash
# Execute on the Raspberry Pi 5 host, in a suitable source directory.
git clone --depth 1 --branch v4.24.0 \
    https://github.com/hailo-ai/hailort-drivers.git
```

Install the driver on the **host**, following Hailo's instructions for the
installed Ubuntu kernel and DKMS/kernel headers. The package or module
installation steps are kernel-dependent; do not blindly copy Raspberry Pi OS
package instructions onto Ubuntu. The matching driver is responsible for
loading the device firmware. Verify the resulting device and driver:

```bash
uname -m
uname -r
lsmod | grep '^hailo_pci' || true
ls -l /dev/hailo0
```

The device path may differ on systems with multiple accelerators. Successful
module loading does **not** by itself demonstrate working inference.

### 2. Install the host HailoRT runtime and MPS service

- [Official HailoRT 4.24.0 release and source](https://github.com/hailo-ai/hailort/releases/tag/v4.24.0)
- [Official HailoRT source compilation instructions](https://hailo.ai/developer-zone/documentation/hailort/latest-hailo8/?sp_referrer=install/install.html#compiling-from-sources)
- [Repository HailoRT/host installation guide](docs/INSTALL_HAILORT_4.24.md)

**Important patched-service requirement:** Our Raspberry Pi 5 MPS
regression testing used a locally patched HailoRT 4.24.0
`hailort_service`, with fixes for container PID namespaces, network-group
lifetime and buffer-pool cleanup order. The unmodified upstream v4.24.0
source **does not include those local fixes**. The patched source is
available at [pmelendez2/hailort](https://github.com/pmelendez2/hailort).
Build the patched service from a reviewed, pinned commit of that fork.
Publication of the source does not establish that a release binary has
passed hardware validation. Do not substitute an unverified prebuilt
service or claim that the upstream service contains our MPS fixes.

On the host, verify both the userspace version and the running service:

```bash
hailortcli --version
systemctl is-active hailort.service
systemctl show hailort.service -p MainPID -p NRestarts
ls -l /run/hailort/hailort_uds.sock
```

The host service must be started **before** MPS-enabled Frigate connects.
The socket path above is the one used in our tested deployment; verify the
actual socket location for other installations. Firmware, PCIe driver, host
runtime and container client must be mutually compatible.

### 3. Install and configure the Frigate container

- [Public Frigate fork source](https://github.com/pmelendez2/frigate)
- [Docker Hub repository](https://hub.docker.com/r/pmelendez2/frigate)
- [Repository build and release instructions](docs/CI_DOCKER_RELEASE.md)

**After the release is published**, pull the explicit versioned image:

```bash
docker pull docker.io/pmelendez2/frigate:0.18.3-hailort-4.24.0
```

This image contains the Frigate application and HailoRT **client** runtime.
It does **not** install the host kernel driver, device firmware, or a running
host `hailort_service`. Configure your Compose deployment to expose the
HailoRT Unix socket (commonly through a bind mount of `/run/hailort`), use
the service endpoint required by that deployment, and enable the detector's
`multi_process_service` option and matching `group_id` (for example,
`SHARED`). See the [Hailo detector configuration and installation guide](docs/INSTALL_HAILORT_4.24.md)
for the complete deployment configuration. Keep credentials in deployment
secrets/environment variables, not in the public Compose example.

After deploying, verify Frigate reports a healthy container and that
actual Hailo inference succeeds. Confirm the host MPS PID and restart count
remain stable after a client connects and disconnects. Docker CI builds for
`linux/amd64` and `linux/arm64` do not replace the Raspberry Pi 5/Hailo-8
hardware validation.

### Why the installation must be split

```text
Frigate container (HailoRT client library)
       |
       | mounted HailoRT Unix-domain socket
       v
Host hailort_service (patched MPS scheduling/cleanup)
       |
       | host HailoRT runtime + kernel PCIe driver
       v
Hailo-8 PCIe accelerator (firmware loaded by driver)
```

The container supplies the application and client library; the Raspberry Pi
5 host supplies device access, firmware loading, and the shared-device
service. A standalone container image cannot replace those host pieces.

### Future enhancement: Cross-host HailoRT MPS access

**Status: Proposed — community contributions welcome.**

A future enhancement could investigate connecting a Frigate instance on one
computer to a HailoRT MPS service on another computer, potentially across
AMD64 and ARM64 hosts.

The existing MPS design uses host-local IPC. Forwarding its Unix-domain
socket over a network is not sufficient to establish remote compatibility.
Research would need to address shared-memory and file-descriptor semantics,
secure authentication, cross-architecture interoperability, latency,
client disconnection, resource cleanup, and service recovery.

**Cross-host MPS is not currently supported or validated.** It is outside
the scope of this Frigate release. Contributors are welcome to investigate
a safe, maintainable implementation and propose a design for review.
<!-- END HAILO8 COMPONENT INSTALLATION -->

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
- Starting version: Frigate `v0.18.3`
- Docker image platforms: `linux/arm64` and `linux/amd64`
- Hardware validation target: Hailo-8 on Raspberry Pi 5 ARM64

Use versioned release images and verify their platform manifests and
published checks before deployment.

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

See [release validation](docs/CI_DOCKER_RELEASE.md) for the supported
build and test sequence.

## Hardware compatibility

The custom integration targets **Hailo-8** PCIe hardware with HailoRT 4.24.0.
Its primary hardware validation target is a Raspberry Pi 5 with a
Hailo-8 PCIe accelerator.

| Accelerator | Status |
| --- | --- |
| Hailo-8 | Validated on Raspberry Pi 5 ARM64 only |
| Hailo-8L | Not verified; no compatibility guarantee |
| Hailo-10 / Hailo-10H | Not supported by this customization |
| Other Hailo accelerators | Not tested or supported |

An AMD64 image build or software-only CI result does not establish AMD64
Hailo-8 inference support. Hailo-8L and Hailo-10 must not be implied
compatible without separate driver, model and inference testing.

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
5. Build the custom Frigate 0.18.3 Docker image for `linux/arm64` (or `linux/amd64` for software validation).
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

## HailoRT Multi-Process Service (MPS) on the host

HailoRT 4.24.0 MPS is a **host operating-system service**, separate from the
Frigate container. It lets multiple clients share the Hailo-8 through a
shared virtual-device group. The host must provide a running `hailort.service`
and a socket accessible to the container; enabling `multi_process_service`
in Frigate alone does not create that service.

On a Hailo-8 host, verify the service with:

```bash
systemctl is-active hailort.service
systemctl cat hailort.service
ls -l /run/hailort/hailort_uds.sock
```

See [host MPS setup and systemd example](docs/INSTALL_HAILORT_4.24.md#install-and-verify-the-host-mps-service)
for the release-specific official references, example unit, socket permissions,
and Frigate container mounts. For shared Hailo-8 applications, Hailo's
[parallel-applications guide](https://github.com/hailo-ai/hailo-apps/blob/main/doc/user_guide/running_parallel.md)
documents the shared group approach. Our Frigate detector uses
`multi_process_service: true` and `group_id: SHARED`.

## DKMS and Linux kernel updates

The Hailo-8 PCIe driver is an **out-of-tree Linux kernel module**. For hosts that receive kernel updates, use **Dynamic Kernel Module Support (DKMS)** to
manage the Hailo PCIe driver across kernel updates. DKMS can automatically
**rebuild and install** the module for a new kernel when the driver is
registered with DKMS and matching kernel headers are available. This is
not the same as compiling the driver *into* the Linux kernel.

DKMS protects against an important operational failure: a kernel upgrade
may leave Frigate unable to access `/dev/hailo0` if the Hailo driver is
missing for the newly booted kernel. DKMS does **not** guarantee that a
new kernel is compatible with the driver; a rebuild may fail and must be
checked before restarting Frigate.

After installing the driver with Hailo's **v4.24.0 DKMS procedure**, and
after each kernel upgrade and reboot, verify the registration, loaded
module, and accelerator:

```bash
uname -r
dkms status | grep -i hailo
modinfo -n hailo_pci
lsmod | grep hailo_pci
ls -l /dev/hailo0
hailortcli fw-control identify
systemctl is-active hailort.service
```

If `dkms status` has no Hailo entry, **do not assume** that a manual
`make install` registered the module with DKMS. Follow the driver's
version-specific DKMS instructions before relying on automatic rebuilds.
See [the HailoRT installation guide](docs/INSTALL_HAILORT_4.24.md)
for prerequisites and post-upgrade checks.

## Security and contributions

Security checks should focus on the changes being contributed, while retaining Gitleaks' default detection rules. The repository's `.gitleaks.toml` contains a narrow exception for a known public dependency revision, not a blanket exception for source files or secret types.

Do not commit build logs, downloaded archives, local environment files, passwords, API tokens, certificates, or private deployment configuration. Report suspected vulnerabilities privately to the appropriate maintainers rather than publishing exploit details in an issue.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for this fork's contributor statement.

## Upstream documentation and attribution

For official installation, configuration, and troubleshooting guidance, use the [Frigate documentation](https://docs.frigate.video/). For upstream bug reports and features unrelated to this fork's HailoRT build changes, use the upstream project after confirming the issue occurs on an official Frigate release.

Frigate and third-party components retain their respective copyright notices and licenses. Consult the repository's license and dependency notices before redistribution.

## Builds, validation, and releases

This fork provides reproducible Docker builds for `linux/arm64` and
`linux/amd64`. The repository's `scripts/build-frigate-local.sh` provides a
portable local build entry point. Each build runs documentation checks, source-security
scanning with Gitleaks, build-context validation, and application-import
smoke tests. A physical accelerator is not required for software builds.

Docker Hub release images are published only after the required checks
pass for both architectures and the release is authorized through a
verified signed Git tag. Hardware inference is validated separately on
supported Hailo-8 systems; automated builds do not imply accelerator
compatibility on every platform.

See the [installation guide](docs/INSTALL_HAILORT_4.24.md) for host
prerequisites, [release documentation](docs/CI_DOCKER_RELEASE.md) for
publishing and verification, and [version information](VERSION.md) for
component compatibility. The [AI usage statement](AIUSAGE.md) and
[contributor code of conduct](CODE_OF_CONDUCT.md) also apply.

## HailoRT 4.24.0 shared-service setup

To use the HailoRT multi-process service, the Frigate container needs the
host's `/run/hailort` socket mount and the `HAILORT_SERVICE_ADDRESS`
container environment variable. Its `hailo8l` detector also needs
`multi_process_service: true` and an agreed `group_id`. The service address
alone is not sufficient. See `docs/INSTALL_HAILORT_4.24.md` for a complete
MPS-specific Compose and detector example. See
[issue #4](https://github.com/pmelendez2/frigate/issues/4).
