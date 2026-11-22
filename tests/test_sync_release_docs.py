#!/usr/bin/env python3
"""Small dependency-free tests for Markdown release synchronization."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync-release-docs.py"
spec = importlib.util.spec_from_file_location("release_docs", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseDocsTest(unittest.TestCase):
    def setUp(self):
        self.version = "0.18.2-hailort-4.24.0"
        self.match = module.VERSION_RE.fullmatch(self.version)
        self.block = module.make_block(self.version, self.match)

    def test_version_pattern(self):
        self.assertIsNotNone(self.match)
        self.assertIsNone(module.VERSION_RE.fullmatch("0.18.2-fix1"))

    def test_initialization_and_repeat_sync(self):
        original = "# Documentation\n\nOriginal text.\n"
        inserted = module.update_content("test.md", original, self.block, True)
        self.assertEqual(inserted.count(module.START), 1)
        self.assertIn("Original text.", inserted)
        self.assertEqual(
            module.update_content("test.md", inserted, self.block, False),
            inserted,
        )

    def test_stale_block_is_replaced(self):
        old = self.block.replace(self.version, "0.18.1-hailort-4.23.0")
        result = module.update_content("test.md", old, self.block, False)
        self.assertEqual(result, self.block)

    def test_reject_duplicate_markers(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            module.update_content(
                "test.md", self.block + "\n" + self.block, self.block, True
            )

    def test_missing_markers_fail_without_init(self):
        with self.assertRaisesRegex(ValueError, "missing generated"):
            module.update_content("test.md", "# Title\n", self.block, False)

    def test_marker_only_touch(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.md"
            original = "# Title\n\nHistorical version 0.17.0.\n"
            sample.write_text(original)
            replaced = module.update_content(
                sample, sample.read_text(), self.block, True
            )
            self.assertIn("Historical version 0.17.0.", replaced)


if __name__ == "__main__":
    unittest.main()
