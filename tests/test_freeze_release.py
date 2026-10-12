import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from easyread import config, translate, server
from easyread import engines, security
import os
from easyread.store import Workspace, write_json_atomic
from scripts import prepare_source_release as release


class FreezeReleaseTest(unittest.TestCase):
    def test_downloads_require_public_unicast_including_embedded_ipv4(self):
        for address in ('127.0.0.1', '224.0.0.1', '192.0.0.8', '64:ff9b::7f00:1', '2002:c0a8:0001::1', '::ffff:127.0.0.1'):
            self.assertFalse(security.public_ip(address), address)
        for address in ('8.8.8.8', '2606:4700:4700::1111', '64:ff9b::808:808'):
            self.assertTrue(security.public_ip(address), address)
    @unittest.skipUnless(os.name == 'nt', 'Windows frozen runtime')
    def test_incomplete_local_cli_cannot_fall_back_to_unverified_global_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root/'.tools/codex/node_modules/@openai/codex/package.json'
            package.parent.mkdir(parents=True); package.write_text('{}')
            with patch.object(engines, '__file__', str(root/'easyread/engines.py')), patch.object(engines.shutil, 'which', return_value='unverified-global.exe'):
                with self.assertRaises(engines.EngineError): engines.codex_path({})
    def test_default_local_pdf_preparation_makes_no_metadata_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'extract').mkdir(); (root/'extract/page-001.txt').write_text('arXiv:2411.00640')
            write_json_atomic(root/'paper.json', {'meta': {}})
            ws = Workspace(root)
            with patch.object(translate.pdfwork, 'prepare', return_value=[]), patch.object(translate.sources, 'enrich') as enrich, patch.object(config, 'load', return_value={'metadata_lookup': False}):
                translate.prepare(ws); enrich.assert_not_called()

    def test_metadata_lookup_remains_available_when_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'extract').mkdir(); (root/'extract/page-001.txt').write_text('arXiv:2411.00640')
            write_json_atomic(root/'paper.json', {'meta': {}})
            ws = Workspace(root)
            with patch.object(translate.pdfwork, 'prepare', return_value=[]), patch.object(translate.sources, 'enrich', return_value={'authors': 'Synthetic author'}) as enrich, patch.object(config, 'load', return_value={'metadata_lookup': True}):
                translate.prepare(ws); enrich.assert_called_once()
            self.assertEqual(ws.load('paper')['meta']['authors'], 'Synthetic author')

    def test_error_access_log_does_not_leak_query_capability(self):
        fake = type('Probe', (), {'command': 'GET', 'path': '/auth?session=SYNTHETIC_SECRET', 'address_string': lambda _: '127.0.0.1'})()
        with patch.object(server.sys, 'stderr', io.StringIO()) as output:
            server.Handler.log_message(fake, '%s %s', 'request', '401')
            self.assertNotIn('SYNTHETIC_SECRET', output.getvalue())
            self.assertIn('/auth', output.getvalue())

    def test_release_has_no_private_directories_and_has_required_runtime(self):
        files = release.check()
        names = {p.relative_to(release.ROOT).as_posix() for p in files}
        self.assertIn('easyread/pdf_worker.py', names)
        self.assertIn('scripts/codex/package-lock.json', names)
        self.assertIn('scripts/verify_source.py', names)
        self.assertFalse(any(set(Path(n).parts) & release.PRIVATE for n in names))
