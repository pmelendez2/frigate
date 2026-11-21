#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
"""Validate this fork's documentation, release versions, and local links.

Only fork-specific documents are checked. Upstream Frigate docs are not
rewritten or blocked by unrelated historical version references.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

DOCS = (
    'HAILO8.md',
    'VERSION.md',
    'AIUSAGE.md',
    'docs/INSTALL_HAILORT_4.24.md',
    'docs/CI_DOCKER_RELEASE.md',
)
REQUIRED = {
    'HAILO8.md': ('Hailo-8', 'Hailo-8L', 'Hailo-10',
                  'docs/INSTALL_HAILORT_4.24.md', 'AIUSAGE.md',
                  'scripts/build-frigate-local.sh'),
    'VERSION.md': ('release/VERSION', 'Hailo-8', 'nginx'),
    'AIUSAGE.md': ('AI', 'review'),
    'docs/INSTALL_HAILORT_4.24.md': ('hailort', 'MPS',
                                     'scripts/prepare-hailort-source.sh',
                                     'scripts/prepare-frigate-version.sh'),
    'docs/CI_DOCKER_RELEASE.md': (
        'DOCKERHUB_TOKEN',
        'release/VERSION',
        'scripts/preflight-build.sh',
        'scripts/prepare-frigate-version.sh',
    ),
}
MARKDOWN_LINK = re.compile(r'(?<!!)\[[^\]\n]*\]\((<[^>]+>|[^)\n]+)\)')
FENCED = re.compile(r'^\s*(`{3,}|~{3,})')
FRIGATE_VERSION = re.compile(r'(?<![\d.])0\.18\.\d+(?![\d.])')
HAILORT_VERSION = re.compile(r'(?<![\d.])4\.2\d\.\d+(?![\d.])')
NGINX_VERSION = re.compile(r'(?<![\d.])1\.3\d\.\d+(?![\d.])')
BANNED = re.compile(r'energy[-_]ingest|README_CUSTOM\.md|frigate-hailort:', re.I)


def unfenced_lines(contents: str):
    marker = None
    for lineno, line in enumerate(contents.splitlines(), 1):
        match = FENCED.match(line)
        if match:
            chars = match.group(1)
            if marker is None:
                marker = (chars[0], len(chars))
            elif chars[0] == marker[0] and len(chars) >= marker[1]:
                marker = None
            continue
        if marker is None:
            yield lineno, line


def check(root: Path) -> int:
    errors: list[str] = []

    def fail(file: str, message: str):
        errors.append(f'{file}: {message}')

    version_file = root / 'release/VERSION'
    if not version_file.is_file():
        fail('release/VERSION', 'missing machine-readable version')
        release = ''
    else:
        release = version_file.read_text(encoding='utf-8').strip()

    match = re.fullmatch(r'(0\.18\.\d+)-hailort-(4\.\d+\.\d+)', release)
    if not match:
        fail('release/VERSION',
             'expected format 0.18.X-hailort-4.Y.Z (one line)')
        frigate_version = hailort_version = ''
    else:
        frigate_version, hailort_version = match.groups()
    nginx_version = '1.31.9'  # Pin for this Frigate fork; update deliberately.

    for name in DOCS:
        path = root / name
        if not path.is_file():
            fail(name, 'missing required documentation')
            continue
        source = path.read_text(encoding='utf-8')
        lines = list(unfenced_lines(source))
        if not source.strip():
            fail(name, 'empty documentation')
            continue
        header = '\n'.join(source.splitlines()[:5])
        if not re.search(r'<!--\s*SPDX-License-Identifier:\s*MIT\s*-->',
                         header):
            fail(name, 'missing HTML SPDX metadata at top')
        if not re.search(r'<!--\s*AI-assisted\b.*-->', header, re.I):
            fail(name, 'missing AI-assisted provenance comment at top')
        headings = [line for _, line in lines if line.startswith('# ')]
        if len(headings) != 1:
            fail(name, f'expected one top-level Markdown title, found {len(headings)}')
        for phrase in REQUIRED.get(name, ()):
            if phrase not in source:
                fail(name, f'missing required subject/reference: {phrase}')
        for line_no, line in lines:
            forbidden = BANNED.search(line)
            if forbidden:
                fail(name, f'line {line_no}: obsolete project name: '
                           f'{forbidden.group(0)}')
            for pattern, expected, label in (
                (FRIGATE_VERSION, frigate_version, 'Frigate'),
                (HAILORT_VERSION, hailort_version, 'HailoRT'),
                (NGINX_VERSION, nginx_version, 'nginx'),
            ):
                for found in pattern.findall(line):
                    if expected and found != expected:
                        fail(name, f'line {line_no}: {label} {found} '
                                   f'differs from {expected}')
            for m in MARKDOWN_LINK.finditer(line):
                target = m.group(1).strip().strip('<>')
                # Optional markdown link title follows the URL.
                target = re.split(r'\s+["\']', target, maxsplit=1)[0]
                if not target or target.startswith('#'):
                    continue
                url = urlsplit(target)
                if url.scheme or url.netloc or target.startswith('//'):
                    continue  # External links are not network-validated.
                local = unquote(url.path)
                if not local:
                    continue
                linked = ((root / local.lstrip('/')) if local.startswith('/')
                          else path.parent / local).resolve()
                if not linked.is_relative_to(root.resolve()):
                    fail(name, f'line {line_no}: link leaves repository: {target}')
                elif not linked.exists():
                    fail(name, f'line {line_no}: broken local link: {target}')

    release_doc = root / 'VERSION.md'
    if release_doc.is_file() and release:
        text = release_doc.read_text(encoding='utf-8')
        if f'`{release}`' not in text:
            fail('VERSION.md', 'release tag does not match release/VERSION')
        for item in (frigate_version, hailort_version, nginx_version):
            if item and item not in text:
                fail('VERSION.md', f'missing component version {item}')
    install = root / 'docs/INSTALL_HAILORT_4.24.md'
    if install.is_file() and 'docker buildx build' in install.read_text():
        s = install.read_text()
        if '--build-context' not in s or 'hailort-src=' not in s:
            fail('docs/INSTALL_HAILORT_4.24.md',
                 'Docker example must supply the external hailort-src context')
    if errors:
        for error in errors:
            print('FAIL:', error, file=sys.stderr)
        print(f'Documentation checks failed: {len(errors)}', file=sys.stderr)
        return 1
    print(f'PASS: {len(DOCS)} fork documents, release versions, metadata, '
          'required content and local links')
    print(f'PASS: release/VERSION = {release}')
    print('NOTE: External URLs and upstream Frigate documentation not checked')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
                        default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    sys.exit(check(args.root.resolve()))
