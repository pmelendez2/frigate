import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/update-hailo8-component-guide.py'
SPEC = importlib.util.spec_from_file_location('guide', SCRIPT)
GUIDE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUIDE)


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.source = '# Title\n\n## Scope\n\nOriginal details.\n'
        self.section = GUIDE.make_section('0.18.2-hailort-4.24.0')

    def test_versions(self):
        self.assertIn('Frigate 0.18.2', self.section)
        self.assertIn('HailoRT 4.24.0', self.section)
        self.assertIn('Raspberry Pi 5', self.section)

    def test_installation_sources(self):
        self.assertIn('hailort-drivers/releases/tag/v4.24.0', self.section)
        self.assertIn('hailort/releases/tag/v4.24.0', self.section)
        self.assertIn('docker.io/pmelendez2/frigate:0.18.2-hailort-4.24.0', self.section)

    def test_cross_host_mps_future_work(self):
        self.assertIn(
            'Future enhancement: Cross-host HailoRT MPS',
            self.section,
        )
        self.assertIn(
            'not currently supported or validated',
            self.section,
        )

    def test_patched_hailort_source(self):
        self.assertIn(
            'https://github.com/pmelendez2/hailort',
            self.section,
        )

    def test_idempotence(self):
        a, changed = GUIDE.update(self.source, self.section, check=False)
        self.assertTrue(changed)
        b, changed = GUIDE.update(a, self.section, check=False)
        self.assertFalse(changed)
        self.assertEqual(a, b)
        self.assertIn('Original details.', b)

    def test_check_requires_section(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            GUIDE.update(self.source, self.section, check=True)

    def test_stale_section_detected(self):
        a, _ = GUIDE.update(self.source, self.section, check=False)
        b, changed = GUIDE.update(a, GUIDE.make_section('0.18.3-hailort-4.24.0'), check=True)
        self.assertTrue(changed)
        self.assertIn('0.18.3', b)

    def test_duplicate_markers_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            GUIDE.update(self.source + GUIDE.BEGIN + GUIDE.END + GUIDE.BEGIN + GUIDE.END,
                         self.section, check=False)


if __name__ == '__main__':
    unittest.main()
