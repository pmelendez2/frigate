#!/usr/bin/env python3
"""Synchronize the Hailo-8 host/container installation guide in HAILO8.md."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

BEGIN = '<!-- BEGIN HAILO8 COMPONENT INSTALLATION -->'
END = '<!-- END HAILO8 COMPONENT INSTALLATION -->'
VERSION_RE = re.compile(r'^(\d+\.\d+\.\d+)-hailort-(\d+\.\d+\.\d+)$')


def make_section(release: str) -> str:
    match = VERSION_RE.fullmatch(release)
    if match is None:
        raise ValueError('release/VERSION must be X.Y.Z-hailort-X.Y.Z')
    frigate, hailort = match.groups()
    return f'''{BEGIN}
## Install the three Hailo-8 components and understand their roles

This custom build targets **Frigate {frigate}**, **HailoRT {hailort}**, and a
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
| Hailo PCIe driver {hailort} and device firmware | Raspberry Pi 5 **host** | Binds the PCIe Hailo-8, exposes the device interface, and loads firmware; a container cannot supply the host kernel module |
| HailoRT {hailort} host runtime and patched MPS service | Raspberry Pi 5 **host** | Owns/schedules the shared device, coordinates clients, and cleans up disconnected clients; **the container image does not replace the running host service** |
| Frigate {frigate} with HailoRT {hailort} userspace library/CLI | **Container image** | Runs object detection as an MPS client; connects to the host service through the mounted Unix-domain socket |

### 1. Install the PCIe driver on the host

Download the **matching {hailort} PCIe driver**, not an arbitrary newer
release:

- [Official Hailo PCIe driver {hailort} release](https://github.com/hailo-ai/hailort-drivers/releases/tag/v{hailort})
- [Hailo PCIe driver source](https://github.com/hailo-ai/hailort-drivers)
- [Hailo's Linux PCIe driver installation instructions](https://hailo.ai/developer-zone/documentation/hailort/latest-hailo8/?sp_referrer=drivers/pcie_linux.html)

For a source checkout, use:

```bash
# Execute on the Raspberry Pi 5 host, in a suitable source directory.
git clone --depth 1 --branch v{hailort} \\
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

- [Official HailoRT {hailort} release and source](https://github.com/hailo-ai/hailort/releases/tag/v{hailort})
- [Official HailoRT source compilation instructions](https://hailo.ai/developer-zone/documentation/hailort/latest-hailo8/?sp_referrer=install/install.html#compiling-from-sources)
- [Repository HailoRT/host installation guide](docs/INSTALL_HAILORT_4.24.md)

**Important patched-service requirement:** Our Raspberry Pi 5 MPS
regression testing used a locally patched HailoRT {hailort}
`hailort_service`, with fixes for container PID namespaces, network-group
lifetime and buffer-pool cleanup order. The unmodified upstream v{hailort}
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
docker pull docker.io/pmelendez2/frigate:{release}
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
{END}'''


def update(content: str, section: str, *, check: bool) -> tuple[str, bool]:
    start_count = content.count(BEGIN)
    end_count = content.count(END)
    if start_count != end_count or start_count > 1:
        raise ValueError('unbalanced or duplicate component-guide markers')
    if start_count:
        start = content.index(BEGIN)
        end = content.index(END, start) + len(END)
        new = content[:start] + section + content[end:]
    else:
        if check:
            raise ValueError('component-guide markers missing')
        headings = list(re.finditer(r'^## ', content, flags=re.MULTILINE))
        if not headings:
            raise ValueError('no level-2 heading found in HAILO8.md')
        position = headings[0].start()
        new = content[:position] + section + '\n\n' + content[position:]
    return new, new != content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--apply', action='store_true')
    group.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    version = (root / 'release/VERSION').read_text().strip()
    doc = root / 'HAILO8.md'
    previous = doc.read_text()
    updated, changed = update(previous, make_section(version), check=args.check)
    if args.check:
        if changed:
            print('FAIL: HAILO8.md component guide out of date')
            return 1
        print('PASS: HAILO8.md component guide matches release/VERSION')
        return 0
    if changed:
        doc.write_text(updated)
    print('UPDATED' if changed else 'UNCHANGED', doc.name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
