#!/usr/bin/env python3
"""Synchronize fenced Markdown release metadata from release/VERSION.

Run from any working directory; this script anchors paths at the repository root.
It never changes free-form prose or historical release notes.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_PATH = ROOT / "release" / "VERSION"
DOCS = (
    "HAILO8.md",
    "VERSION.md",
    "docs/CI_DOCKER_RELEASE.md",
    "docs/INSTALL_HAILORT_4.24.md",
)
START = "<!-- BEGIN GENERATED RELEASE METADATA -->"
END = "<!-- END GENERATED RELEASE METADATA -->"
VERSION_RE = re.compile(
    r"^v?(?P<frigate>\d+\.\d+\.\d+)-hailort-"
    r"(?P<hailort>\d+\.\d+\.\d+)$"
)
HEADER_RE = re.compile(r"(?m)^# .+\n")
PUBLIC_IMAGE = "docker.io/pmelendez2/frigate"


def read_version():
    if not VERSION_PATH.is_file():
        raise ValueError(
            "release/VERSION is missing; create it with a single line "
            "such as 0.18.2-hailort-4.24.0"
        )
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError(
            "release/VERSION must contain one release identifier in "
            "the form 0.18.2-hailort-4.24.0"
        )
    return f"{match['frigate']}-hailort-{match['hailort']}", match


def make_block(version, match):
    return (
        f"{START}\n"
        "| Release metadata | Value |\n"
        "| --- | --- |\n"
        f"| Release | `{version}` |\n"
        f"| Frigate | `{match['frigate']}` |\n"
        f"| HailoRT | `{match['hailort']}` |\n"
        f"| Docker Hub image | `{PUBLIC_IMAGE}:{version}` |\n"
        "| Hailo-8 hardware validation | Raspberry Pi 5 ARM64 only |\n"
        "| AMD64 Hailo-8 hardware validation | Not performed |\n"
        f"{END}"
    )


def update_content(path, content, block, initialize):
    start_count, end_count = content.count(START), content.count(END)
    if start_count == end_count == 1:
        left = content.index(START)
        right = content.index(END) + len(END)
        if right < left:
            raise ValueError(f"{path}: reversed markers")
        return content[:left] + block + content[right:]
    if start_count or end_count:
        raise ValueError(f"{path}: inconsistent or duplicate markers")
    if not initialize:
        raise ValueError(
            f"{path}: missing generated block; run --init once"
        )
    match = HEADER_RE.search(content)
    if not match:
        raise ValueError(f"{path}: missing top-level Markdown title")
    # Insert the generated block immediately after the Markdown title.
    return content[:match.end()] + "\n" + block + "\n" + content[match.end():]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--init", action="store_true", help="insert missing blocks")
    action.add_argument("--sync", action="store_true", help="refresh existing blocks")
    action.add_argument("--check", action="store_true", help="fail if blocks differ")
    args = parser.parse_args()
    try:
        version, match = read_version()
        block = make_block(version, match)
        changes = []
        for relative_path in DOCS:
            path = ROOT / relative_path
            if not path.is_file():
                raise ValueError(f"{relative_path}: required document missing")
            original = path.read_text(encoding="utf-8")
            updated = update_content(
                relative_path, original, block, args.init
            )
            if original != updated:
                changes.append((path, original, updated))
        if args.check:
            if changes:
                for path, _, _ in changes:
                    print(f"STALE: {path.relative_to(ROOT)}")
                return 1
            print(f"PASS: release metadata matches {version} in {len(DOCS)} docs")
            return 0
        for path, _, updated in changes:
            path.write_text(updated, encoding="utf-8")
            print(f"UPDATED: {path.relative_to(ROOT)}")
        print(f"PASS: {len(changes)} document(s) updated for {version}")
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
