<!-- SPDX-License-Identifier: MIT -->
<!-- AI-assisted documentation; maintainer review required. -->

# Install HailoRT 4.24.0 and build custom Frigate 0.18.3

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

This guide describes the **order of operations** for the custom Frigate
build, using a Linux ARM64 host with a Hailo-8 PCIe accelerator. It does not replace Hailo's kernel-specific install
instructions or Frigate's general deployment documentation.

**Build locations:** Steps 1–4 run on the **Hailo host**. Step 5 runs on a
**Docker build machine** (which may be different). Step 6 runs on the host
that will run Frigate.

## Official references

- [HailoRT 4.24.0 sources](https://github.com/hailo-ai/hailort/tree/v4.24.0)
- [Hailo PCIe driver 4.24.0 sources](https://github.com/hailo-ai/hailort-drivers/tree/v4.24.0)
- [Hailo PCIe driver build and install instructions](https://github.com/hailo-ai/hailort-drivers/blob/v4.24.0/linux/pcie/Readme.md)
- [HailoRT compilation and MPS documentation](https://hailo.ai/developer-zone/documentation/hailort/latest/)
- [Frigate installation documentation](https://docs.frigate.video/frigate/installation/)

**Version caution:** Hailo's `master` branches can target newer accelerator
families. **Use the explicit `v4.24.0` tag** for Hailo-8, not `master` or
`latest`. Use instructions appropriate to that release when the latest
Hailo documentation differs.

## 1. Check the host and prerequisites

Check the operating system, architecture, kernel, accelerator and build tools:

```bash
uname -m
uname -r
lspci -nn | grep -i hailo || true
docker version
docker buildx version
```

The following is a **typical Ubuntu starting point**, not a universal package
list. Consult the 4.24.0 Hailo documentation for additional build dependencies
and the exact kernel-header package for your distribution:

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake git pkg-config \
    bison flex libelf-dev dkms pciutils
```

Install the headers matching the **running** kernel using your distribution's
packages. On Raspberry Pi kernels, do not assume that the generic
`linux-headers-$(uname -r)` package exists. Verify that the directory below
exists before building the driver:

```bash
test -d "/lib/modules/$(uname -r)/build" && echo "Headers available"
```

If the headers are absent, follow your distribution's kernel/header procedure
before continuing. A driver built for a different kernel cannot be assumed
to load correctly.

## 2. Build and install the Hailo PCIe driver 4.24.0

Use an independent source checkout; do not copy these driver sources into the
Frigate repository:

```bash
mkdir -p "$HOME/src"
git clone --branch v4.24.0 --depth 1 \
    https://github.com/hailo-ai/hailort-drivers.git \
    hailort-drivers-4.24.0
cd hailort-drivers-4.24.0/linux/pcie
make all
sudo make install
sudo depmod -a
sudo modprobe hailo_pci
```

Hailo's driver README is authoritative for the build and install procedure.
If the release's module name or build steps differ for your platform, follow
that README rather than forcing the commands above.

**Firmware and udev:** Follow the matching v4.24.0 driver release instructions
for installing the Hailo-8 firmware and udev rules. These may be required for
`/dev/hailo0` to appear and function. Do not mix firmware from a different
release. Reboot if required by driver, firmware, or kernel changes.

Verify the loaded driver and device:

```bash
lsmod | grep hailo_pci
cat /sys/module/hailo_pci/version
ls -l /dev/hailo0
```

If `/dev/hailo0` is missing, **do not proceed to Frigate**. Resolve the driver,
firmware, PCIe enumeration, or kernel-header issue first.

### DKMS registration and kernel-upgrade verification

For a host expected to receive Linux kernel updates, prefer Hailo's
**v4.24.0 DKMS installation procedure** for the PCIe driver. A manual
`make all && sudo make install` builds/installs for a particular kernel;
those commands **do not by themselves establish DKMS registration**.
Use the matching driver's own documented DKMS setup rather than
assuming that a manual installation provides automatic rebuilds.

DKMS builds an **out-of-tree kernel module**, not a driver compiled into
the kernel image. Automatic rebuilding requires a valid DKMS entry, DKMS
tooling, and headers for the target kernel. Driver compilation or loading
can still fail after a kernel/API change.

Verify after DKMS installation and after each kernel upgrade/reboot:

```bash
uname -r
dkms status | grep -i hailo
modinfo -n hailo_pci
lsmod | grep hailo_pci
ls -l /dev/hailo0
hailortcli fw-control identify
systemctl is-active hailort.service
```

Check that the DKMS entry is installed for the **running kernel**. If any
check fails, review `dkms status`, the DKMS build logs and matching kernel
headers before starting Frigate. Do not rely on a successful Docker image
build as evidence that the host kernel driver is installed.

## 3. Build and install the HailoRT userspace runtime 4.24.0

The host runtime is **separate** from the kernel driver. HailoRT supplies the
library, CLI and optional Multi-Process Service (MPS) components.

```bash
git clone --branch v4.24.0 --depth 1 \
    https://github.com/hailo-ai/hailort.git \
    hailort-source
cd hailort-source
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j2
sudo cmake --install build
sudo ldconfig
hailortcli --version
```

`hailortcli --version` should report **4.24.0**. If building the versioned
source requires additional options or dependencies, use the HailoRT 4.24.0
build documentation linked above.

**MPS is required for this fork's `multi_process_service: true` setting.**
Build/install `hailort_service` with the **same 4.24.0 release**, following
Hailo's [Multi-Process Service documentation](https://hailo.ai/developer-zone/documentation/hailort/latest/).
Do not assume that installing `libhailort` alone installs or enables an MPS
systemd service. Its build options and service registration are provided by
Hailo, and can differ by packaging and platform.

After the matching MPS service has been installed, enable/start the unit if
it is named `hailort.service`:

```bash
sudo systemctl enable --now hailort.service
systemctl is-active hailort.service
ls -l /run/hailort/hailort_uds.sock
```

The expected socket pathname is shown above for this deployment; confirm the
socket and access permissions against your installed HailoRT service. A
working socket is essential for container-to-host MPS communication.

### Install and verify the host MPS service

For authoritative release-specific instructions, start with the
[HailoRT v4.24.0 source tree](https://github.com/hailo-ai/hailort/tree/v4.24.0)
and the [HailoRT Developer Zone documentation](https://hailo.ai/developer-zone/documentation/hailort/latest/).
Use the **4.24.0** service build and installation procedure rather than
instructions for newer Hailo-10/Hailo-15 runtimes. Hailo's
[parallel-applications guide](https://github.com/hailo-ai/hailo-apps/blob/main/doc/user_guide/running_parallel.md)
describes shared groups and enabling multi-process service for Hailo-8.

When building HailoRT from source, **enable its service build option**
(`HAILO_BUILD_SERVICE`) according to the matching release's CMake
instructions, then install the resulting `hailort_service` executable and
use Hailo's provided service installer/unit when available. Building only
`libhailort` or the CLI does not ensure that MPS was installed.

Verify whether the installer already provided the service:

```bash
command -v hailort_service
systemctl cat hailort.service
systemctl is-enabled hailort.service
systemctl is-active hailort.service
```

If the v4.24.0 installer provided a working `hailort.service`, **keep it**.
If a working service unit and override already exist, keep the installed
configuration rather than replacing it with an example.

**Illustrative systemd unit, only if the official installation did not
provide one:** Confirm the exact binary path and appropriate service
account first. This minimal example assumes the HailoRT 4.24.0 service
runs in the foreground and is installed at `/usr/local/bin/hailort_service`:

```ini
# /etc/systemd/system/hailort.service
[Unit]
Description=HailoRT 4.24.0 Multi-Process Service
After=systemd-udev-settle.service

[Service]
Type=simple
ExecStart=/usr/local/bin/hailort_service
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Install a custom unit only when the official v4.24.0 service installer has
not created a service and the executable's behavior has been confirmed.
If creating that unit manually, use `sudo systemctl daemon-reload` and
`sudo systemctl enable --now hailort.service`; inspect its journal if it
fails. The official vendor unit is preferred because socket directories,
logging, and runtime permissions can require additional configuration.

Verify on the **host**:

```bash
hailortcli --version
hailortcli fw-control identify
systemctl is-active hailort.service
systemctl status hailort.service --no-pager
systemctl cat hailort.service
ls -l /run/hailort/hailort_uds.sock
sudo journalctl -u hailort.service -b --no-pager -n 50
```

The MPS socket may be owned by `root:hailort` with group read/write
permissions, depending on the vendor installation. The Frigate container
must be able to use the socket through its mounted `/run/hailort` directory
and access `/dev/hailo0`. Do not make the MPS socket world-writable as a
shortcut; use the deployment's existing permissions and container access.

For example, the Compose service needs these host resources (this is a
snippet, not a complete Frigate Compose file):

```yaml
services:
  frigate:
    devices:
      - /dev/hailo0:/dev/hailo0
    volumes:
      - /run/hailort:/run/hailort
```

Frigate's detector configuration additionally needs:

```yaml
detectors:
  hailo8l:
    type: hailo8l
    device: PCIe
    multi_process_service: true
    group_id: SHARED
```

The detector type name `hailo8l` is Frigate's plugin identifier; this fork
has been targeted at **Hailo-8** hardware. It does not establish that
Hailo-8L or other accelerator types have been validated.

## 4. Validate the host before building or deploying Frigate

```bash
uname -r
cat /sys/module/hailo_pci/version
hailortcli --version
hailortcli fw-control identify
systemctl is-active hailort.service
ls -l /dev/hailo0 /run/hailort/hailort_uds.sock
```

Stop if device identification fails or hangs. Investigate kernel and service
logs, driver/runtime version mismatches, and device permissions:

```bash
sudo journalctl -k -b --no-pager | grep -i hailo | tail -n 50
sudo journalctl -u hailort.service -b --no-pager -n 50
```

Avoid running a mixed 4.23/4.24 userspace stack or assuming that a successful
`hailortcli --version` proves the driver and accelerator are operational.

## 5. Build the custom Frigate 0.18.3 image

On the Docker build machine, clone **this fork** or use an existing checkout
of its release branch. Run all commands from the
**Frigate repository root**:

```bash
git status --short --branch
docker buildx version

# Prepare release metadata and validate fork documentation.
python3 scripts/check-documentation.py
bash scripts/prepare-frigate-version.sh
bash scripts/check-build-context.sh

# HailoRT 4.24.0 is an external Docker build context.
# This directory can be removed after the build.
HAILORT_CONTEXT="$(mktemp -d)"
bash scripts/prepare-hailort-source.sh "$HAILORT_CONTEXT/hailort-src"

docker buildx build \
    --platform linux/arm64 \
    --build-context "hailort-src=$HAILORT_CONTEXT/hailort-src" \
    --target frigate \
    --file docker/main/Dockerfile \
    --tag frigate:0.18.2-hailort-4.24-mps \
    --load \
    .
```

This custom Dockerfile/build script builds the container-side HailoRT 4.24.0
components. **It does not install the host's PCIe kernel driver.** The `--load`
form requires a Buildx builder/output configuration that supports loading a
single-platform image into the local image store. Use a Buildx builder capable
of building ARM64 images (natively or with configured emulation).

Check the resulting local image:

```bash
docker image inspect frigate:0.18.2-hailort-4.24-mps \
    --format '{{.Architecture}}'
docker run --rm --entrypoint hailortcli \
    frigate:0.18.2-hailort-4.24-mps --version
```

Expect `arm64` and HailoRT CLI 4.24.0. These tests alone do **not** prove that
inference works; hardware access is verified after deployment. If building
on one machine and deploying on another, publish the image to **your own
registry** using your normal authenticated image-publishing workflow. Do not
assume a repository-specific private registry is publicly accessible.

## 6. Configure and start Frigate on the Hailo host

Follow [Frigate's official Docker/Compose deployment documentation](https://docs.frigate.video/frigate/installation/)
for volumes, ports, camera configuration, MQTT and data persistence. Select
your newly built image in the Compose service.

For this MPS-enabled deployment, verify the container has access to both the
PCIe device and the host MPS socket. The following is a **snippet**, not a
complete Frigate Compose file:

```yaml
services:
  frigate:
    image: frigate:0.18.2-hailort-4.24-mps
    devices:
      - /dev/hailo0:/dev/hailo0
    volumes:
      - /run/hailort:/run/hailort
```

Ensure the user running Frigate has the permissions required to access the
device and socket. Add Frigate's other required configuration from the
official installation guide; do not paste this snippet over an existing
complete Compose file.

In your Frigate configuration, enable the MPS options added by this fork:

```yaml
detectors:
  hailo8l:
    type: hailo8l
    device: PCIe
    multi_process_service: true
    group_id: SHARED
```

Confirm that the keys above match the detector plugin in your checked-out
commit. Start the container through your deployment's normal Compose or stack
workflow, then review its logs for successful Hailo detector initialization.

## 7. Final validation and upgrades

1. Confirm host driver, runtime, firmware and MPS service function together.
2. Confirm the container uses HailoRT 4.24.0 and can access the device/socket.
3. Confirm Frigate starts its Hailo detector and processes actual camera
   inference; a successful image build is not sufficient.
4. After a **kernel upgrade**, verify or rebuild the Hailo PCIe driver for the
   new kernel before restarting Frigate.
5. When upgrading HailoRT or Frigate, use a new feature branch and retest the
   exact host/container combination. Avoid mixing HailoRT versions.

This guide documents the prerequisites and verification path. Where Hailo's
release-specific instructions are required (firmware, MPS build options,
service installation and distribution-specific kernel headers), **follow
Hailo's documentation instead of treating this guide as a replacement**.


This installation guide targets Hailo-8. Hailo-8L has not been
validated; Hailo-10 and other Hailo devices are not supported by
this customization. See [HAILO8.md](../HAILO8.md).

## Docker Compose and HailoRT multi-process service (MPS)

This is a **partial Compose example**, not a complete Frigate deployment.
The HailoRT service must already be running on the Hailo host. For a
PCIe Hailo-8 device, configure the device mapping, MPS Unix socket mount,
and container-side service address:

```yaml
services:
  frigate:
    devices:
      - /dev/hailo0:/dev/hailo0
    volumes:
      - /run/hailort:/run/hailort
    environment:
      HAILORT_SERVICE_ADDRESS: "unix:///run/hailort/hailort_uds.sock"
```

Alternatively, a deployment manager can supply an address for Compose
substitution:

```yaml
environment:
  HAILORT_SERVICE_ADDRESS: "${HAILORT_SVC_ADDR}"
```

`HAILORT_SVC_ADDR` is an optional **deployment-side** input, not a universal
Frigate variable. Configure it outside the repository (for example, in
your deployment manager's environment). The container receives
`HAILORT_SERVICE_ADDRESS`. The socket path is an example for a host
running HailoRT's Unix-domain service; confirm it matches your host.
Ensure the socket's permissions permit the container's HailoRT client to
connect. Do not publish that socket over a network.

Enable MPS in Frigate's own `config.yml` (or `config.yaml`):

```yaml
detectors:
  hailo:
    type: hailo8l
    device: PCIe
    multi_process_service: true
    group_id: SHARED
```

The Compose environment variable alone does **not** enable detector MPS.
The `hailo8l` detector passes `multi_process_service` and `group_id` to
HailoRT `VDevice` parameters. All sharing clients must use the intended
group identifier.

For hardware acceptance, verify the running detector's effective `/api/config`
reports MPS enabled, the host service and socket are active, the real
Hailo-8 performs inference, and a second MPS client can perform inference
while Frigate remains healthy. Successful Frigate inference alone does not
prove concurrent-client support. See `docs/BUILD_ONCE_RELEASE.md` and
[issue #4](https://github.com/pmelendez2/frigate/issues/4).
