#!/usr/bin/env python3
# AI-assisted: OpenAI ChatGPT; human verification required.
"""Update the separate local buildit.sh launcher without replacing it.

Uses exact anchors, creates a timestamped backup, and refuses unexpected
script versions. Does not modify the git checkout or start Docker.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python3 tools/update-local-buildit.py PATH_TO_BUILDIT')
        return 2
    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.is_file():
        print(f'ERROR: Script not found: {path}')
        return 1
    original = path.read_text()
    marker = 'bash "$BUILD_DIR/scripts/prepare-frigate-version.sh"'
    if marker in original:
        print('Already updated; no change necessary')
        return 0

    tag_line = 'readonly IMAGE_TAG="0.18.2-hailort-4.24-mps-source"'
    build_anchor = (
        '        echo "Building ARM64 image: $LOCAL_IMAGE"\n'
        '        docker buildx build \\\n'
    )
    runtime_anchor = (
        'printf \'\\n=== Verify image HailoRT runtime ===\\n\'\n'
        'check_image_runtime\n'
    )
    frigate_case = original.rfind("    frigate)\n")
    if frigate_case < 0:
        print("ERROR: Frigate build case missing; file unchanged")
        return 1
    for needle, label in (
        (tag_line, 'Frigate tag'),
        (runtime_anchor, 'runtime check'),
    ):
        if original.count(needle) != 1:
            print(f'ERROR: Unexpected {label} section; file unchanged')
            return 1

    if original[frigate_case:].count(build_anchor) != 1:
        print("ERROR: Frigate build anchor missing; file unchanged")
        return 1

    revised = original.replace(
        tag_line,
        'readonly IMAGE_TAG="${FRIGATE_IMAGE_TAG:-'
        '0.18.2-hailort-4.24-mps-source}"',
    )
    index = revised.rfind("    frigate)\n")
    prefix, fragment = revised[:index], revised[index:]
    fragment = fragment.replace(
        build_anchor,
        '        bash "$BUILD_DIR/scripts/prepare-frigate-version.sh"\n'
        '        bash "$BUILD_DIR/scripts/check-build-context.sh"\n'
        + build_anchor,
        1,
    )
    revised = prefix + fragment
    revised = revised.replace(
        runtime_anchor,
        runtime_anchor +
        'if [[ "$TARGET" == frigate ]]; then\n'
        '    bash "$BUILD_DIR/scripts/test-ci-image.sh" '
        '"$LOCAL_IMAGE" arm64\n'
        'fi\n',
    )

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = path.with_name(f'{path.name}.bak.{stamp}')
    if backup.exists():
        print(f'ERROR: Backup already exists: {backup}')
        return 1
    backup.write_bytes(path.read_bytes())
    os.chmod(backup, path.stat().st_mode & 0o777)
    path.write_text(revised)
    print(f'PASS: Updated {path}')
    print(f'Backup: {backup}')
    print('Rebuild with a NEW FRIGATE_IMAGE_TAG (registry tags are immutable).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
