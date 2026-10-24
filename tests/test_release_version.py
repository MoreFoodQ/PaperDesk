import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from easyread import __version__
from scripts import prepare_source_release as release


class ReleaseVersionTest(unittest.TestCase):
    def test_python_electron_and_lock_versions_agree(self):
        root=Path(__file__).resolve().parents[1]
        package=json.loads((root/'package.json').read_text(encoding='utf-8'))
        lock=json.loads((root/'package-lock.json').read_text(encoding='utf-8'))
        python=re.search(r'^version = "([^"\n]+)"', (root/'pyproject.toml').read_text(encoding='utf-8'), re.M)[1]
        self.assertEqual({__version__, package['version'], lock['version'], lock['packages']['']['version'], python}, {__version__})

    def test_source_archive_and_embedded_manifest_use_declared_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            package=root/'package.json'
            package.write_text(json.dumps({'version':'9.8.7'}), encoding='utf-8')
            with patch.object(release,'check',return_value=[package]):
                archive, count=release.build(root)
            self.assertEqual(archive.name,'paperdesk-9.8.7-source.zip')
            self.assertEqual(count,1)
            with zipfile.ZipFile(archive) as source:
                manifest=json.loads(source.read('paperdesk/RELEASE-MANIFEST.json'))
                self.assertEqual(manifest['version'],'9.8.7')
                self.assertEqual(manifest['files']['package.json'], hashlib.sha256(package.read_bytes()).hexdigest())
            self.assertEqual((root/'outputs/SHA256SUMS.txt').read_text().split()[0],hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_invalid_version_cannot_escape_the_output_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            package=root/'package.json'
            package.write_text(json.dumps({'version':'../../escape'}),encoding='utf-8')
            with patch.object(release,'check',return_value=[package]), self.assertRaises(ValueError):
                release.build(root)
            self.assertFalse((root/'outputs').exists())
