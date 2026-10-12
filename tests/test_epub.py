"""Synthetic EPUB/PDF integration and hostile archive regressions; no model calls."""
import hashlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PIL import Image

from easyread import build, chat, cloudlib, engines, epub, pdfwork, translate
from easyread.library import Library
from easyread.store import read_json
from scripts.smoke_backend import probe_pdf


def epub_bytes(extra=None, body=None, version='3.0', metadata='', spine='b a', manifest=None):
    image = io.BytesIO()
    Image.new('RGB', (80, 50), '#1a647a').save(image, 'PNG')
    items = manifest or '<item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/>'
    refs = ''.join('<itemref idref="' + i + '"/>' for i in spine.split())
    files = {'mimetype': b'application/epub+zip',
        'META-INF/container.xml': b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>',
        'OPS/book.opf': f'<package xmlns="http://www.idpf.org/2007/opf" version="{version}"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>EPUB Synthetic Test</dc:title><dc:creator>Test Author</dc:creator><dc:language>zh-TW</dc:language>{metadata}</metadata><manifest>{items}</manifest><spine>{refs}</spine></package>'.encode(),
        'OPS/a.xhtml': b'<html><head><title>Hidden title</title></head><body><h1>Second chapter</h1><p>Final result and conclusion.</p></body></html>',
        'OPS/b.xhtml': (body or '<html><body><h1>第一章 Chapter One</h1><p>繁體中文內容，read in spine order.</p><ul><li>List item</li></ul><table><tr><td>Control</td><td>42</td></tr></table><img src="figure.png" alt="Synthetic diagram"/><script>DO_NOT_RUN_THIS</script><p><img src="https://example.invalid/image.png" alt="remote"/></p></body></html>').encode(),
        'OPS/figure.png': image.getvalue()}
    files.update(extra or {})
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, value in files.items():
            z.writestr(name, value)
    return out.getvalue()


class EPUBTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='paperdesk-epub-test-')
        self.root = Path(self.temp.name)
        self.lib = Library(self.root / 'library')

    def tearDown(self):
        self.temp.cleanup()

    def parse(self, data):
        (self.root / 'source.epub').write_bytes(data)
        return epub._read(self.root)

    def test_spine_metadata_unicode_table_images_and_no_active_content(self):
        meta, chapters = self.parse(epub_bytes())
        self.assertEqual(meta['title_en'], 'EPUB Synthetic Test')
        self.assertEqual(meta['authors'], 'Test Author')
        text = ' '.join(b[1] for ch in chapters for b in ch if b[0] != 'image')
        self.assertIn('繁體中文內容', text)
        self.assertLess(text.index('Chapter One'), text.index('Second chapter'))
        self.assertIn('Control | 42', text)
        self.assertNotIn('DO_NOT_RUN_THIS', text)
        self.assertNotIn('Hidden title', text)
        self.assertIn('remote', text)
        self.assertEqual(sum(b[0] == 'image' for ch in chapters for b in ch), 1)

    def test_epub2(self):
        self.assertEqual(self.parse(epub_bytes(version='2.0'))[0]['format'], 'epub')

    def test_traversal_absolute_windows_paths_duplicates_and_symlinks(self):
        for name in ('../outside', '/absolute', 'OPS/../escape', 'C:/escape'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.parse(epub_bytes(extra={name: b'x'}))
        with self.assertRaises(ValueError):
            self.parse(epub_bytes(extra={'OPS/escape': b'x'}).replace(b'OPS/escape', b'OPS\\escape'))
        import warnings
        duplicate = io.BytesIO(epub_bytes())
        with warnings.catch_warnings(), zipfile.ZipFile(duplicate, 'a') as z:
            warnings.simplefilter('ignore')
            z.writestr('mimetype', b'application/epub+zip')
        with self.assertRaises(ValueError):
            self.parse(duplicate.getvalue())
        out = io.BytesIO(epub_bytes())
        with zipfile.ZipFile(out, 'a') as z:
            info = zipfile.ZipInfo('OPS/link')
            info.external_attr = 0o120777 << 16
            z.writestr(info, 'outside')
        with self.assertRaises(ValueError):
            self.parse(out.getvalue())

    def test_zip_bomb_declared_size_and_expanded_size_limits(self):
        with self.assertRaises(ValueError):
            self.parse(epub_bytes(extra={'OPS/bomb': b'x' * (2 * 1024 * 1024)}))
        with mock.patch.object(epub, 'MAX_TOTAL', 20), self.assertRaises(ValueError):
            self.parse(epub_bytes())

    def test_encryption_fixed_layout_math_and_svg_fail_explicitly(self):
        variants = [epub_bytes(extra={'META-INF/encryption.xml': b'<encryption/>'}),
                    epub_bytes(metadata='<meta property="rendition:layout">pre-paginated</meta>'),
                    epub_bytes(body='<html><body><math><mi>x</mi></math></body></html>'),
                    epub_bytes(body='<html><body><svg/></body></html>')]
        for data in variants:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.parse(data)

    def test_entities_utf16_xml_missing_members_remote_spine_rejected(self):
        variants = [epub_bytes(extra={'META-INF/container.xml': b'<!DOCTYPE a [<!ENTITY x "bad">]><a>&x;</a>'}),
                    epub_bytes(extra={'META-INF/container.xml': '<container/>'.encode('utf-16')}),
                    epub_bytes(manifest='<item id="a" href="missing.xhtml" media-type="application/xhtml+xml"/>', spine='a'),
                    epub_bytes(manifest='<item id="a" href="https://example.invalid/ch.xhtml" media-type="application/xhtml+xml"/>', spine='a')]
        for data in variants:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.parse(data)

    def test_invalid_import_not_published_and_worker_error_is_readable(self):
        with self.assertRaisesRegex(ValueError, 'DRM'):
            self.lib.create_from_document(epub_bytes(extra={'META-INF/encryption.xml': b'<encryption/>'}), 'test.epub')
        self.assertEqual(self.lib.list(), [])
        self.assertEqual(list(self.lib.root.iterdir()), [])
        with self.assertRaises(ValueError):
            self.lib.create_from_document(b'not an epub', 'fake.epub')

    def test_pdf_dispatch_keeps_original_bytes_identity_and_metadata(self):
        data = probe_pdf()
        ws, fresh = self.lib.create_from_document(data, 'test.pdf')
        self.assertTrue(fresh)
        self.assertEqual(ws.id, hashlib.sha256(data).hexdigest()[:12])
        self.assertEqual((ws.root / 'source.pdf').read_bytes(), data)
        self.assertEqual(self.lib.summary(ws)['format'], 'pdf')
        self.assertFalse((ws.root / 'source.epub').exists())
        self.assertGreater(len(pdfwork.prepare(ws.root)), 0)

    def test_epub_prepare_notes_translation_chat_export_and_cloud_identity(self):
        data = epub_bytes()
        ws, fresh = self.lib.create_from_document(data, 'book.epub')
        self.assertTrue(fresh)
        self.assertEqual((ws.root / 'source.epub').read_bytes(), data)
        with mock.patch.object(translate.config, 'load', return_value={'metadata_lookup': False}):
            translate.prepare(ws)
        paper = ws.load('paper')
        self.assertEqual(paper['meta']['page_count'], 2)
        self.assertIn('繁體中文內容', (ws.root / 'extract/page-001.txt').read_text(encoding='utf-8'))
        self.assertIn('Second chapter', (ws.root / 'extract/page-002.txt').read_text(encoding='utf-8'))
        self.assertGreater(len(read_json(ws.root / 'extract/page-001.chars.json', [])), 20)
        self.assertTrue((ws.root / 'source.pdf').read_bytes().startswith(b'%PDF'))
        self.assertEqual(cloudlib._sha(ws.root), hashlib.sha256(data).hexdigest())
        ws.apply_reader_ops([{'op': 'paper_note', 'body': 'Retain my note', 'at': '2026-10-12T00:00:00Z'}])
        before = ws.load('reader')
        prompts = []
        def fake_run(cfg, prompt, cwd, images=None, cancel=None, meter=None):
            prompts.append(prompt)
            return json.dumps({'blocks': [{'id': 'p1-1', 'type': 'para', 'page': 1, 'en': 'read in spine order.', 'zh': '依章節順序閱讀。'}]})
        cfg = {'engine': 'openai', 'openai': {'vision': False}, 'batch_pages': 1, 'concurrency': 1}
        with mock.patch.object(engines, 'run', fake_run), mock.patch.object(translate.netcheck, 'problem', return_value=None):
            failed = translate.translate_pages(ws, cfg, [1], threading.Event(), lambda *args: None)
        self.assertEqual(failed, {})
        self.assertIn('繁體中文內容', prompts[0])
        self.assertIn('declared language: zh-TW', prompts[0])
        self.assertIn('never convert it to English', prompts[0])
        self.assertIn('read in spine order', chat._paper_context(ws))
        self.assertEqual(ws.load('reader'), before)
        exported = build.build(ws, self.root / 'offline.html', lang='zh-TW').read_text(encoding='utf-8')
        self.assertIn('data:image/webp;base64,', exported)
        self.assertIn('Retain my note', exported)
        self.assertIn('依章節順序閱讀', exported)
        same, fresh = self.lib.create_from_document(data, 'renamed.EPUB')
        self.assertFalse(fresh)
        self.assertEqual(same.load('reader'), before)

    def test_original_only_vision_and_cancel_preserve_notes(self):
        ws, _ = self.lib.create_from_document(epub_bytes(), 'book.epub')
        with mock.patch.object(translate.config, 'load', return_value={'metadata_lookup': False}):
            translate.prepare(ws)
        ws.apply_reader_ops([{'op': 'paper_note', 'body': 'Original-mode note'}])
        before = ws.load('reader')
        images_seen = []
        def fake_run(cfg, prompt, cwd, images=None, cancel=None, meter=None):
            images_seen.extend(images or [])
            self.assertIn('In original-only mode preserve the original language', prompt)
            return json.dumps({'blocks': [{'id': 'p1-original', 'type': 'para', 'page': 1,
                                          'en': '繁體中文原文', 'zh': ''}]}, ensure_ascii=False)
        cfg = {'engine': 'openai', 'openai': {'vision': True}, 'batch_pages': 1, 'concurrency': 1}
        with mock.patch.object(engines, 'run', fake_run), mock.patch.object(translate.netcheck, 'problem', return_value=None):
            self.assertEqual(translate.translate_pages(ws, cfg, [1], threading.Event(), lambda *args: None, read=True), {})
        self.assertTrue(images_seen)
        self.assertTrue(all(Path(p).is_file() for p in images_seen))
        self.assertEqual(ws.load('paper')['translation']['en_pages'], [1])
        self.assertEqual(ws.load('reader'), before)
        cancel = threading.Event()
        cancel.set()
        with mock.patch.object(engines, 'run') as engine, mock.patch.object(translate.netcheck, 'problem', return_value=None):
            with self.assertRaises(engines.Cancelled):
                translate.translate_pages(ws, cfg, [2], cancel, lambda *args: None)
            engine.assert_not_called()
        self.assertEqual(ws.load('reader'), before)

    def test_page_limit_is_enforced(self):
        ws, _ = self.lib.create_from_document(epub_bytes(), 'book.epub')
        with mock.patch.object(epub, 'MAX_PAGES', 1), self.assertRaises(ValueError):
            epub.prepare(ws.root)
        self.assertFalse((ws.root / 'source.pdf').exists())


if __name__ == '__main__':
    unittest.main()
