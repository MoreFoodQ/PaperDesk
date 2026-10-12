"""Functional regression tests for the fork's security and integration boundaries."""
import copy
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from easyread import config, engines, i18n, langs, secret_store, server, settings_api, updates


class HostBoundaryTest(unittest.TestCase):
    def setUp(self):
        class Probe(server.Handler):
            app = type('ProbeApp', (), {'token': 'test-session'})()
            def do_GET(self):
                if self._trusted_request():
                    self._json(200, {"token": "private-token"})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Probe)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def request(self, host, origin=None, token='test-session'):
        headers = {"Host": host}
        if token:
            headers['X-Token'] = token
        if origin:
            headers["Origin"] = origin
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request("GET", "/api/library", headers=headers)
        response = connection.getresponse()
        result = response.status, response.read().decode()
        connection.close()
        return result

    def test_rebinding_host_cannot_read_token(self):
        status, body = self.request(f"attacker.example:{self.httpd.server_port}")
        self.assertEqual(status, 403)
        self.assertNotIn("private-token", body)

    def test_foreign_origin_is_rejected(self):
        status, _ = self.request(f"127.0.0.1:{self.httpd.server_port}", "https://attacker.example")
        self.assertEqual(status, 403)

    def test_local_client_works(self):
        host = f"127.0.0.1:{self.httpd.server_port}"
        self.assertEqual(self.request(host, "http://" + host)[0], 200)

    def test_native_client_without_session_cannot_read_token(self):
        status, body = self.request(f'127.0.0.1:{self.httpd.server_port}', token=None)
        self.assertEqual(status, 401)
        self.assertNotIn('private-token', body)

    def test_wrong_session_is_rejected(self):
        self.assertEqual(self.request(f'127.0.0.1:{self.httpd.server_port}', token='wrong')[0], 401)


class PaperDeskTest(unittest.TestCase):
    def test_defaults_and_language(self):
        self.assertEqual(config.DEFAULTS["engine"], "codex")
        self.assertEqual(config.DEFAULTS["chat"]["default"], "gpt")
        self.assertEqual(config.DEFAULTS["target"], "zh-TW")
        self.assertIn("繁體中文", langs.prompt_name("zh-TW"))
        with patch.object(i18n, "lang", return_value="zh-TW"):
            self.assertEqual(i18n.tr("设置"), "設定")
            self.assertIn("繁體中文", langs.reply_lang({}))
        self.assertEqual(i18n._system_language("zh-Hant-TW"), "zh-TW")

    def test_upstream_feed_is_disabled_even_when_forced(self):
        with patch.object(updates, "_fetch") as fetch:
            self.assertFalse(updates.check(force=True)["supported"])
            fetch.assert_not_called()

    def test_browser_cannot_replace_executable(self):
        for key, value in (("command", "malware.exe"), ("extra_args", ["--dangerously-bypass-approvals-and-sandbox"])):
            with self.assertRaises(ValueError):
                settings_api.save_config({"codex": {key: value}})

    def test_unsafe_arguments_rejected_at_execution(self):
        with patch.object(engines, "_popen") as popen:
            with self.assertRaises(engines.EngineError):
                engines._codex_once("codex", {"extra_args": ["--sandbox", "danger-full-access"]}, "hi", Path.cwd(), [], None, [])
            popen.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI")
    def test_secret_disk_storage_round_trip(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(config, "CONFIG_PATH", Path(folder) / "config.json"):
            sample = "test-only-not-a-real-api-key"
            config.save({"openai": {"api_key": sample, "keys": {"test": sample}}})
            disk = config.CONFIG_PATH.read_text(encoding="utf-8")
            self.assertNotIn(sample, disk)
            self.assertIn(secret_store.PREFIX, disk)
            self.assertEqual(config.load()["openai"]["api_key"], sample)
            self.assertEqual(config.load()["openai"]["keys"]["test"], sample)
            self.assertNotIn(sample, json.dumps(config.public(config.load())))

    def test_tw_dictionary_preserves_placeholders(self):
        import re
        for key, value in i18n.tw_dict().items():
            self.assertEqual(re.findall(r"\{\w+\}", key), re.findall(r"\{\w+\}", value), key)


if __name__ == "__main__":
    unittest.main()
