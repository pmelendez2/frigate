# SPDX-License-Identifier: MIT
# AI-assisted: OpenAI ChatGPT; maintainer review required.
"""Unit tests for public-content audit scope and detection rules."""

import importlib.util
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'check-public-content.py'


def run_git(root, *args):
    return subprocess.run(
        ['git', '-C', str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


class PublicContentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        run_git(self.root, 'init', '-q')
        run_git(self.root, 'config', 'user.email', 'test@example.invalid')
        run_git(self.root, 'config', 'user.name', 'Test')
        path = self.root / 'docs/docs/configuration/cameras.md'
        path.parent.mkdir(parents=True)
        path.write_text('Upstream example: 192.168.1.20\n')
        run_git(self.root, 'add', '.')
        run_git(self.root, 'commit', '-qm', 'Upstream baseline')
        run_git(self.root, 'tag', 'v0.18.3')

        spec = importlib.util.spec_from_file_location(
            'frigate_public_content_test', SCRIPT
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.ROOT = self.root
        self.module.FILES = ()

    def scan(self):
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return self.module.main()

    def test_unchanged_upstream_documentation_is_not_scanned(self):
        self.assertEqual(self.scan(), 0)
        self.assertEqual(self.module.documentation_files(), [])

    def test_changed_upstream_documentation_is_scanned(self):
        path = self.root / 'docs/docs/configuration/cameras.md'
        path.write_text('Changed example: 192.168.1.20\n')
        self.assertNotEqual(self.scan(), 0)

    def test_untracked_document_is_scanned(self):
        path = self.root / 'NEW.md'
        path.write_text('Do not publish ~/src/secret-project\n')
        self.assertNotEqual(self.scan(), 0)

    def test_clean_document_is_accepted(self):
        path = self.root / 'NEW.md'
        path.write_text('Use ./scripts/build-frigate-local.sh\n')
        self.assertEqual(self.scan(), 0)

    def test_committed_fork_document_is_scanned(self):
        path = self.root / 'NEW.md'
        path.write_text('Host: host.home.arpa\n')
        run_git(self.root, 'add', 'NEW.md')
        run_git(self.root, 'commit', '-qm', 'Add fork documentation')
        self.assertNotEqual(self.scan(), 0)


if __name__ == '__main__':
    unittest.main()
