import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from easyread import engines


@unittest.skipUnless(os.name == 'nt', 'Windows native runtime')
class PackagedRuntimeTest(unittest.TestCase):
    def test_frozen_default_uses_installed_native_cli_without_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            native=root/'resources/codex/bin/codex.exe'
            native.parent.mkdir(parents=True);native.write_bytes(b'synthetic')
            with patch.object(sys,'frozen',True,create=True), patch.object(sys,'executable',str(root/'resources/backend/easyread-backend.exe')), patch.object(engines.shutil,'which') as which:
                self.assertEqual(Path(engines.codex_path({})),native)
                which.assert_not_called()

    def test_incomplete_installer_does_not_use_unverified_global_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sys,'frozen',True,create=True), patch.object(sys,'executable',str(Path(folder)/'resources/backend/easyread-backend.exe')), patch.object(engines.shutil,'which',return_value='foreign.exe') as which:
                with self.assertRaises(engines.EngineError):engines.codex_path({})
                which.assert_not_called()

    def test_explicit_command_remains_a_user_choice(self):
        with patch.object(sys,'frozen',True,create=True),patch.object(engines.shutil,'which',return_value='chosen.exe'):
            self.assertEqual(engines.codex_path({'command':'chosen.exe'}),'chosen.exe')
