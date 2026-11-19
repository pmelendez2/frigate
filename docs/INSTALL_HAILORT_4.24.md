# Install HailoRT 4.24.0 and build custom Frigate 0.18.2

This guide describes the **order of operations** for the custom Frigate
`feature/frigate-0.18.2-hailort-4.24` build, using a Linux ARM64 host with a
Hailo-8 PCIe accelerator. It does not replace Hailo's kernel-specific install
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
cd "$HOME/src"
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

## 3. Build and install the HailoRT userspace runtime 4.24.0

The host runtime is **separate** from the kernel driver. HailoRT supplies the
library, CLI and optional Multi-Process Service (MPS) components.

```bash
cd "$HOME/src"
git clone --branch v4.24.0 --depth 1 \
    https://github.com/hailo-ai/hailort.git \
    hailort-4.24.0
cd hailort-4.24.0
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

## 5. Build the custom Frigate 0.18.2 image

On the Docker build machine, clone **this fork** or use an existing checkout
of its `feature/frigate-0.18.2-hailort-4.24` branch. Run all commands from the
**Frigate repository root**:

```bash
git status --short --branch
docker buildx version

docker buildx build \
    --platform linux/arm64 \
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
