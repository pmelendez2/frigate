#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; human verification required.
"""Check fork-owned and changed public files for local or private details.

Unchanged upstream documentation may contain legitimate private-IP examples.
Gitleaks independently scans fork changes for credential patterns.
"""

from pathlib import Path
import ipaddress
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    'HAILO8.md',
    'VERSION.md',
    'AIUSAGE.md',
    'docs/CI_DOCKER_RELEASE.md',
    'docs/INSTALL_HAILORT_4.24.md',
    'scripts/preflight-build.sh',
    'scripts/build-frigate-local.sh',
    'scripts/check-frigate-changes.sh',
    'scripts/prepare-frigate-version.sh',
    'scripts/check-documentation.py',
    'scripts/test-ci-image.sh',
    'scripts/test-frigate-image.sh',
    'scripts/test-frigate-deployment.sh',
    'scripts/prepare-hailort-source.sh',
    'scripts/check-build-context.sh',
    'scripts/verify-published-image.sh',
    '.github/workflows/ci.yml',
    '.github/workflows/docker-publish.yml',
    '.githooks/pre-commit',
    '.githooks/pre-push',
)

# Use separate string literals so the checker does not match its own source.
PATTERNS = (
    (re.compile(r'/home/' + r'[^/\s]+/'), 'personal home directory'),
    (re.compile(r'~/src/' + r'[^\s`]+'), 'developer checkout path'),
    (re.compile(r'home\.' + r'arpa', re.I), 'private DNS domain'),
    (re.compile('teco' + 'reg', re.I), 'private registry name'),
    (re.compile(r'energy[-_]' + r'ingest', re.I), 'unrelated project'),
    (re.compile(r'README_' + r'CUSTOM\.md', re.I), 'obsolete filename'),
    (re.compile(r'buildit' + r'\.sh'), 'external local build launcher'),
)

EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')

IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')


def check_file(name: str) -> list[str]:
    path = ROOT / name
    if not path.is_file():
        return [f'{name}: required public file missing']

    issues = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        for expression, label in PATTERNS:
            if expression.search(line):
                issues.append(f'{name}:{line_number}: {label}')

        if EMAIL.search(line):
            issues.append(f'{name}:{line_number}: email address in public file')

        for match in IPV4.finditer(line):
            address = ipaddress.ip_address(match.group(0))
            if not address.is_global:
                issues.append(f'{name}:{line_number}: nonpublic IP address')

    return issues



# Review fork-owned documentation and any documentation added or modified
# relative to the upstream release. Do not flag unchanged upstream examples.
DOC_EXTENSIONS = {'.md', '.mdx', '.rst', '.markdown'}

DOC_PATH_RULES = (
    (re.compile(r'~/src/' + r'[^\s`]+', re.I),
     'personal source-tree path'),
    (re.compile(r'/home/' + r'[^/\s`]+(?:/[^\s`]+)?'),
     'personal home-directory path'),
    (re.compile(r'/Users/' + r'[^/\s`]+(?:/[^\s`]+)?'),
     'personal macOS directory path'),
    (re.compile(r'\\\\[^\\\s]+\\Users\\[^\\\s]+', re.I),
     'personal Windows directory path'),
    (re.compile(r'file://' + r'/[^\s)`]+', re.I),
     'local file URI'),
    (re.compile(r'\bfrigate-0\.18\.2(?=/|\\)', re.I),
     'obsolete local checkout path'),
    (re.compile(r'buildit' + r'\.sh', re.I),
     'external build launcher reference'),
    (re.compile(r'teco' + r'reg', re.I),
     'private registry reference'),
    (re.compile(r'home\.' + r'arpa', re.I),
     'internal DNS reference'),
    (re.compile(r'\b(?:sp' + r'arta|pi' + r'cam)(?:-w)?\b', re.I),
     'development/deployment host reference'),
)


def git_paths(*arguments: str) -> set[Path]:
    result = subprocess.run(
        ['git', '-C', str(ROOT), *arguments, '-z'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            'Cannot enumerate changed Git files: ' + ' '.join(arguments)
        )
    return {
        Path(raw.decode('utf-8', errors='surrogateescape'))
        for raw in result.stdout.split(b'\0') if raw
    }


def documentation_files() -> list[Path]:
    # These checks cover commits on the fork, staged/unstaged changes, and
    # untracked documents. The tag is the upstream Frigate release baseline.
    names = {
        Path(name) for name in FILES
        if Path(name).suffix.lower() in DOC_EXTENSIONS
    }
    # Compare the complete working tree with the current upstream release.
    # This includes staged and unstaged fork changes, but not upstream-only
    # documentation introduced by the release merge.
    names.update(git_paths('diff', '--name-only', 'v0.18.3'))
    names.update(git_paths('ls-files', '--others', '--exclude-standard'))

    docs = []
    for name in sorted(names):
        if name.is_absolute() or '..' in name.parts:
            raise RuntimeError('Unexpected Git path outside repository')
        if name.suffix.lower() not in DOC_EXTENSIONS:
            continue
        path = ROOT / name
        if path.is_file() and not path.is_symlink():
            docs.append(path)
    return docs


def check_documentation_paths() -> tuple[list[str], int]:
    issues = []
    docs = documentation_files()

    for path in docs:
        name = path.relative_to(ROOT).as_posix()
        # Ignore lines already present in the upstream release.
        # Fork-owned documents absent from upstream are checked in full.
        upstream = subprocess.run(
            ['git', '-C', str(ROOT), 'show',
             f'v0.18.3:{name}'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
        upstream_lines = (
            set(upstream.stdout.splitlines())
            if upstream.returncode == 0 else set()
        )

        for number, line in enumerate(
            path.read_text(encoding='utf-8', errors='replace').splitlines(),
            1,
        ):
            if line in upstream_lines:
                continue
            for expression, label in DOC_PATH_RULES:
                if expression.search(line):
                    issues.append(f'{name}:{number}: {label}')

            for match in IPV4.finditer(line):
                try:
                    address = ipaddress.ip_address(match.group(0))
                except ValueError:
                    continue
                # Loopback addresses are often legitimate service examples.
                if address in ipaddress.ip_network('10.0.0.0/8') or (
                    address in ipaddress.ip_network('172.16.0.0/12')
                ) or address in ipaddress.ip_network('192.168.0.0/16'):
                    issues.append(f'{name}:{number}: private IPv4 address')

    return issues, len(docs)

def main() -> int:
    issues = []
    for name in FILES:
        issues.extend(check_file(name))

    try:
        documentation_issues, count = check_documentation_paths()
    except RuntimeError as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1
    issues.extend(documentation_issues)

    if issues:
        for issue in issues:
            print(f'FAIL: {issue}', file=sys.stderr)
        return 1

    print(f'PASS: {len(FILES)} custom files checked for local details')
    print(f'PASS: {count} fork/changed docs checked for private paths')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
