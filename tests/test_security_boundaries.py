import io
import os
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from easyread import build, codex_lean, config, http, security, sources, translate, wsock, store
from easyread.store import Workspace, write_json_atomic


class SecurityBoundaries(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows sharing violations')
    def test_transient_read_sharing_violation_is_retried(self):
        with patch('builtins.open', side_effect=[PermissionError('sharing violation'), io.StringIO('{"ok": true}')]), patch.object(store.time, 'sleep'):
            self.assertEqual(store.read_json(Path('fake.json')), {'ok': True})
    def test_model_cannot_choose_file_or_html_level(self):
        data = translate._normalize({'blocks': [
            {'type': 'figure', 'src': '../sentinel.txt', 'id': 'figure'},
            {'type': 'heading', 'level': '1" onclick="alert(1)', 'id': 'heading'},
            {'type': 'bad" onclick="alert(1)', 'id': 'bad'},
        ]}, [1], set())
        self.assertEqual(len(data['blocks']), 2)
        self.assertEqual(data['blocks'][0]['src'], '')
        self.assertEqual(data['blocks'][1]['level'], 1)

    def test_export_rejects_outside_file_and_fake_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'paper'; root.mkdir()
            outside = Path(folder) / 'sentinel.txt'; outside.write_text('SYNTHETIC_SECRET')
            ws = Workspace(root)
            write_json_atomic(ws.paper_path, {'meta': {'pages': []}, 'blocks': [{'type': 'figure', 'src': '../sentinel.txt'}]})
            result = build.build(ws).read_text(encoding='utf-8')
            self.assertNotIn('U1lOVEhFVElDX1NFQ1JFVA==', result)
            (root/'figures').mkdir(); (root/'figures/fake.webp').write_text('SYNTHETIC_SECRET')
            self.assertIsNone(security.asset_path(root, 'figures/fake.webp'))
            from PIL import Image
            Image.new('RGB', (2, 2)).save(root/'figures/good.png')
            self.assertIsNotNone(security.asset_path(root, 'figures/good.png'))
            self.assertIsNone(security.asset_path(root, str(outside)))
            self.assertIsNone(security.asset_path(root, 'figures/../../sentinel.txt'))

    def test_public_download_rejects_file_and_private_dns(self):
        with self.assertRaises(sources.SourceError):
            sources._get('file:///never-read.pdf')
        addresses = [(2, 1, 6, '', ('127.0.0.1', 80))]
        with patch('socket.getaddrinfo', return_value=addresses), self.assertRaises(ValueError):
            http._public_connect(('public-looking.example', 80), 1)
        with self.assertRaises(ValueError):
            security.origin('http://user:password@example.com')

    def test_saved_key_cannot_follow_endpoint_change(self):
        cfg = {'preset': 'custom', 'base_url': 'https://trusted.example/v1', 'keys': {'custom': 'SYNTHETIC'}}
        self.assertEqual(config.saved_key(cfg, 'custom', 'https://trusted.example/v2'), 'SYNTHETIC')
        with self.assertRaises(ValueError):
            config.saved_key(cfg, 'custom', 'https://collector.example/v1')
        with self.assertRaises(ValueError):
            security.validate_api('http://remote.example', 'SYNTHETIC')
        security.validate_api('http://127.0.0.1:11434/v1', 'LOCAL_ONLY')

    def test_mcp_inline_toml_and_invalid_configuration(self):
        self.assertEqual(codex_lean.server_names('[mcp_servers]\nworker={command="fake"}'), ['worker'])
        with self.assertRaises(ValueError):
            codex_lean.server_names('[invalid')

    def test_authorization_never_reaches_redirect_receiver(self):
        seen = []
        class Receiver(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.headers.get('Authorization')); self.send_response(200); self.end_headers()
            def log_message(self, *args): pass
        destination = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302); self.send_header('Location', f'http://127.0.0.1:{destination.server_port}/'); self.end_headers()
            def log_message(self, *args): pass
        sender = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        for srv in (sender, destination):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{sender.server_port}/', headers={'Authorization': 'Bearer SYNTHETIC'})
            with self.assertRaises(ValueError):
                http.urlopen(req, timeout=3)
            self.assertEqual(seen, [])
        finally:
            for srv in (sender, destination): srv.shutdown(); srv.server_close()

    def test_websocket_rejects_giant_frame_before_payload_read(self):
        class Probe:
            rfile = io.BytesIO(b'\x82\xff' + (2**40).to_bytes(8, 'big'))
            wfile = io.BytesIO()
        probe = Probe(); wsock.hold(probe)
        self.assertEqual(probe.rfile.tell(), 10)
