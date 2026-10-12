import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from easyread import pdfwork


class PageVariantAtomicTest(unittest.TestCase):
    def test_concurrent_request_cannot_read_a_partially_written_variant(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'pages').mkdir()
            with Image.new('RGB', (1200, 600), 'white') as im:
                im.save(root / 'pages/page-001.webp', 'WEBP')
            published = root / 'pages/w400/page-001.webp'
            started, release = threading.Event(), threading.Event()
            original = Image.Image.save

            def delayed_save(im, filename, *args, **kwargs):
                Path(filename).write_bytes(b'')
                started.set()
                if not release.wait(5):
                    raise TimeoutError('test writer was not released')
                return original(im, filename, *args, **kwargs)

            with ThreadPoolExecutor(max_workers=2) as pool, patch.object(Image.Image, 'save', delayed_save):
                first = pool.submit(pdfwork.page_variant, root, 'pages/page-001.webp', 400)
                try:
                    self.assertTrue(started.wait(3))
                    self.assertFalse(published.exists(), 'cache was published before its bytes were complete')
                    second = pool.submit(pdfwork.page_variant, root, 'pages/page-001.webp', 400)
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=5), second.result(timeout=5))
            with Image.open(published) as im:
                self.assertEqual(im.size, (400, 200))
            self.assertFalse(list(published.parent.glob('.variant-*')))

    def test_existing_empty_cache_is_regenerated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'pages/w400').mkdir(parents=True)
            with Image.new('RGB', (1200, 600), 'white') as im:
                im.save(root / 'pages/page-001.webp', 'WEBP')
            published = root / 'pages/w400/page-001.webp'
            published.write_bytes(b'')
            result = pdfwork.page_variant(root, 'pages/page-001.webp', 400)
            with Image.open(result) as im:
                self.assertEqual(im.size, (400, 200))
