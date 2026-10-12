import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from easyread import account_usage, budget, config, engines, netcheck, usage
from easyread import pdfwork
from easyread import library, store


class PhaseTwo(unittest.TestCase):
    def test_pdf_title_survives_worker_dispatch(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.pdf'
            writer = PdfWriter(); writer.add_blank_page(width=60, height=80)
            writer.add_metadata({'/Title': 'Synthetic title retained'})
            writer.write(path)
            self.assertEqual(library._pdf_title(path), 'Synthetic title retained')

    def test_pdf_lock_is_not_stolen_after_generic_30_second_age(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'.pdf-worker.lock'; path.write_text('synthetic')
            os.utime(path, (time.time()-31, time.time()-31))
            with self.assertRaises(TimeoutError):
                with store.dir_lock(Path(folder), '.pdf-worker.lock', timeout=0.01, stale_after=150):
                    self.fail('Must not steal a live PDF operation lock')
            self.assertTrue(path.exists())
    def test_parallel_pdf_workers_preserve_one_complete_cached_image(self):
        from pypdf import PdfWriter
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writer = PdfWriter(); writer.add_blank_page(width=60, height=80)
            writer.write(root/'source.pdf')
            with ThreadPoolExecutor(max_workers=4) as pool:
                images = list(pool.map(lambda _: pdfwork.engine_image(root, 1), range(4)))
            self.assertEqual(len(set(images)), 1)
            with Image.open(images[0]) as image: image.verify()
            self.assertFalse((root/'.pdf-worker.lock').exists())
    def test_quota_prefers_buckets_and_unknown_is_not_zero(self):
        result = account_usage.normalize({'rateLimits': {'limitId': 'legacy', 'primary': {'usedPercent': 20}},
          'rateLimitsByLimitId': {'test': {'primary': {'usedPercent': 15, 'windowDurationMins': 300},
                                        'secondary': {'usedPercent': None}}}})
        self.assertEqual(result[0]['id'], 'test')
        self.assertEqual(len(result[0]['windows']), 1)
        self.assertEqual(result[0]['windows'][0]['remaining_percent'], 85)
        self.assertEqual(account_usage.normalize({'rateLimits': None}), [])

    def test_quota_cache_and_error_are_safe(self):
        with patch.object(account_usage, '_cached', None), patch.object(account_usage, '_read', side_effect=RuntimeError('SYNTHETIC_SECRET')):
            first = account_usage.snapshot()
            self.assertEqual(first['status'], 'unavailable')
            self.assertNotIn('SYNTHETIC_SECRET', json.dumps(first))
            self.assertEqual(account_usage.snapshot(), first)

    def test_cli_environment_without_system_proxy_and_no_secret_inheritance(self):
        with patch.object(netcheck, 'proxy_env', return_value=None), patch.dict(os.environ, {'PAPERDESK_SESSION': 'SYNTHETIC', 'UNRELATED_SECRET': 'SYNTHETIC', 'OPENAI_API_KEY': 'PROVIDER_KEY'}), patch.object(engines.subprocess, 'Popen') as popen:
            engines._popen(['codex', '--version'], Path('.'))
            env = popen.call_args.kwargs['env']
            self.assertEqual(env['OPENAI_API_KEY'], 'PROVIDER_KEY')
            self.assertNotIn('UNRELATED_SECRET', env)
            self.assertNotIn('PAPERDESK_SESSION', env)

    def test_daily_call_limit_is_shared_under_concurrency(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'HOME', Path(folder)), patch.object(config, 'load', return_value={'budget': {'daily_calls': 3, 'daily_tokens': 0}}):
            def invoke(_):
                m = usage.Meter('fake')
                try:
                    with budget.call(m): m.add(input=10, output=2)
                    return True
                except engines.EngineError: return False
            with ThreadPoolExecutor(max_workers=5) as pool:
                self.assertEqual(sum(pool.map(invoke, range(10))), 3)
            data = budget.snapshot()
            self.assertEqual((data['calls'], data['reported_tokens']), (3, 36))

    def test_reported_token_limit_blocks_next_call(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'HOME', Path(folder)), patch.object(config, 'load', return_value={'budget': {'daily_calls': 0, 'daily_tokens': 20}}):
            m = usage.Meter('fake')
            with budget.call(m): m.add(input=15, output=10)
            with self.assertRaises(engines.EngineError):
                with budget.call(usage.Meter('fake')): self.fail('Must not invoke model')
            self.assertEqual(budget.snapshot()['reported_tokens'], 25)

    def test_call_crossing_midnight_stays_in_start_day(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'HOME', Path(folder)), patch.object(config, 'load', return_value={'budget': {'daily_calls': 0, 'daily_tokens': 0}}), patch.object(budget, '_today', return_value='2026-10-11') as today:
            m = usage.Meter('fake')
            with budget.call(m):
                m.add(input=10, output=5)
                today.return_value = '2026-10-12'
            self.assertEqual(budget.snapshot()['reported_tokens'], 0)
            self.assertEqual(budget._load('2026-10-11')['reported_tokens'], 15)
