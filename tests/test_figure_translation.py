"""Figure policy regressions exercise real scheduling, state writes and retries."""
import copy
import json
import re
import shutil
import threading
import unittest
from unittest.mock import patch

from easyread import config, engines, figure_translation, prompts_en, settings_api, translate, translate_api
from easyread.jobs import Jobs
from easyread.library import Library
from easyread.store import write_json_atomic
from tests.test_translate import make_ws
from tests.test_jobs import StopWorker


def blocks(n=1):
    return [
        {"id": f"p{n}", "type": "para", "page": n, "en": "Body", "zh": "正文"},
        {"id": f"t{n}", "type": "table", "page": n, "caption_en": "Table 1", "caption_zh": "表一",
         "head": [["組別", "數值"]], "rows": [["A", "42"]]},
        {"id": f"f{n}", "type": "figure", "page": n, "num": str(n), "caption_en": "Figure caption",
         "caption_zh": "圖片說明", "image_en": "Time (days)", "image_zh": "時間（天）"}]


class FigureTranslationTest(unittest.TestCase):
    def setUp(self):
        self.ws = make_ws(3)
        self.addCleanup(lambda: shutil.rmtree(self.ws.root, ignore_errors=True))
        self.cfg = {"engine": "openai", "openai": {"vision": False}, "target": "zh-TW",
                    "batch_pages": 1, "concurrency": 1, "page_cap": 0, "translate_images": False}
        self.calls = []
        self.real_config_load = config.load
        for p in [patch('easyread.jobs.config.load', side_effect=lambda: self.cfg),
                  patch.object(translate.netcheck, 'problem', return_value=None),
                  patch.object(translate.pdfwork, 'locate'),
                  patch.object(translate, 'tex_problems', return_value=[]),
                  patch.object(engines, 'run', side_effect=self.engine)]:
            p.start()
            self.addCleanup(p.stop)
        with patch('easyread.jobs.threading.Thread.start'):
            self.jobs = Jobs(Library(self.ws.root.parent))

    def engine(self, cfg, prompt, cwd, images=None, cancel=None, meter=None):
        self.calls.append((copy.deepcopy(cfg), prompt, images))
        marker = "要翻译的内容（键 → 英文）：\n"
        if marker in prompt:
            items = json.loads(prompt.split(marker, 1)[1])
            # Unrequested body/metadata/check changes must never leak into image-only fills.
            return json.dumps({"zh": {**{k: "補翻文字" for k in items}, "p1": "DO NOT APPLY"},
                               "meta": {"title_zh": "DO NOT APPLY"},
                               "checks": [], "glossary": [{"en": "x", "zh": "y"}]})
        pages = [int(n) for n in re.search(r"这次只处理第 ([\d, ]+) 页", prompt)[1].split(',')]
        return json.dumps({"blocks": [b for n in pages for b in blocks(n)]})

    def drain(self):
        get = self.jobs.bulk.get
        def next_job():
            if self.jobs.bulk.empty():
                raise StopWorker()
            return get()
        with patch.object(self.jobs.bulk, 'get', side_effect=next_job), self.assertRaises(StopWorker):
            self.jobs._bulk_loop()

    def run_pages(self, cfg=None, pages=None, read=False):
        return translate.translate_pages(self.ws, cfg or self.cfg, pages or [1], threading.Event(), lambda *a: None, read=read)

    def seed_skipped(self, pages=(1,)):
        data = [b for n in (1, 2, 3) for b in blocks(n)]
        for b in data:
            if b['type'] == 'figure' and b['page'] in pages:
                b.pop('image_zh')
                b['image_translation_skipped'] = True
        self.ws.update('paper', lambda p: p.update(blocks=data, translation={'done_pages': [1, 2, 3], 'en_pages': []}))

    def test_default_and_old_config_preserve_translation(self):
        cfg = dict(self.cfg)
        cfg.pop('translate_images')
        self.assertTrue(config.DEFAULTS['translate_images'])
        self.assertEqual(self.run_pages(cfg), {})
        figure = self.ws.load('paper')['blocks'][2]
        self.assertTrue(figure['image_zh'])
        self.assertNotIn('image_translation_skipped', figure)
        self.assertNotIn('Figure-label translation is disabled', self.calls[0][1])

    def test_off_ignores_model_translation_keeps_body_table_caption(self):
        self.assertEqual(self.run_pages(), {})
        paper = self.ws.load('paper')
        paragraph, table, figure = paper['blocks']
        self.assertEqual(paragraph['zh'], '正文')
        self.assertEqual(table['rows'], [['A', '42']])
        self.assertEqual(figure['caption_zh'], '圖片說明')
        self.assertEqual(figure['image_en'], 'Time (days)')
        self.assertNotIn('image_zh', figure)
        self.assertEqual(figure_translation.pending_pages(paper), {1})
        self.assertEqual(paper['translation']['en_pages'], [])
        self.assertIn('Figure-label translation is disabled', self.calls[0][1])

    def test_off_does_not_disable_page_images(self):
        cfg = dict(self.cfg, openai={'vision': True})
        with patch.object(translate.pdfwork, 'engine_image', return_value=self.ws.root/'page.jpg') as image:
            self.assertEqual(self.run_pages(cfg), {})
        self.assertTrue(image.called)
        self.assertTrue(self.calls[0][2])

    def test_model_cannot_forge_skip_marker_when_enabled(self):
        data = blocks()
        data[2]['image_translation_skipped'] = True
        figure_translation.apply(data, [], True)
        self.assertNotIn('image_translation_skipped', data[2])

    def test_explicit_retranslation_off_keeps_existing_figure_translation(self):
        self.ws.update('paper', lambda p: p.update(blocks=blocks()))
        self.ws.update('paper', lambda p: p['blocks'][2].update(image_zh='Previously translated labels'))
        self.assertEqual(self.run_pages(), {})
        self.assertEqual(self.ws.load('paper')['blocks'][2]['image_zh'], 'Previously translated labels')

    def test_original_fill_skips_images_without_false_missing_error(self):
        self.ws.update('paper', lambda p: p.update(blocks=[
            {'id': 'p1', 'type': 'para', 'page': 1, 'en': 'Body'},
            {'id': 'f1', 'type': 'figure', 'page': 1, 'image_en': 'Time', 'caption_en': 'Figure caption'}],
            translation={'done_pages': [1], 'en_pages': [1]}))
        self.assertEqual(self.run_pages(), {})
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('f1#image', self.calls[0][1].split('要翻译的内容')[1])
        figure = self.ws.load('paper')['blocks'][1]
        self.assertEqual(figure['caption_zh'], '補翻文字')
        self.assertTrue(figure['image_translation_skipped'])
        self.assertEqual(self.ws.load('paper')['translation']['en_pages'], [])

    def test_image_only_original_fill_needs_no_model_when_disabled(self):
        self.ws.update('paper', lambda p: p.update(blocks=[{'id': 'f1', 'type': 'figure', 'page': 1, 'image_en': 'Time'}],
                     translation={'done_pages': [1], 'en_pages': [1]}))
        self.assertEqual(self.run_pages(), {})
        self.assertEqual(self.calls, [])
        self.assertEqual(figure_translation.pending_pages(self.ws.load('paper')), {1})

    def test_read_only_does_not_mark_figures_as_skipped_translation(self):
        self.assertEqual(self.run_pages(read=True), {})
        self.assertEqual(figure_translation.pending_pages(self.ws.load('paper')), set())
        self.assertNotIn('Figure-label translation is disabled', self.calls[0][1])

    def test_queue_snapshot_survives_global_change(self):
        self.jobs.enqueue(self.ws, pages=[1, 2])
        self.cfg['translate_images'] = True
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertTrue(all(c[0]['translate_images'] is False for c in self.calls))
        self.assertEqual(figure_translation.pending_pages(self.ws.load('paper')), {1, 2})

    def test_confirm_and_failed_retry_keep_snapshot(self):
        self.cfg['page_cap'] = 1
        self.jobs.enqueue(self.ws)
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'confirm')
        self.cfg['translate_images'] = True
        translate_api.enqueue(self.jobs, self.ws, {'confirmed': True})
        self.assertFalse(self.ws.load('job')['translate_images'])
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.jobs._write(self.ws, state='partial', failed={'1': 'test'})
        translate_api.enqueue(self.jobs, self.ws, {'failed': True})
        self.assertFalse(self.ws.load('job')['translate_images'])

    def test_restart_retains_setting_and_legacy_job_defaults_on(self):
        self.jobs.enqueue(self.ws, pages=[1])
        self.cfg['translate_images'] = True
        with patch('easyread.jobs.threading.Thread.start'):
            resumed = Jobs(self.jobs.lib)
        self.assertFalse(self.ws.load('job')['translate_images'])
        original = self.jobs
        self.jobs = resumed
        self.drain()
        self.jobs = original
        self.assertFalse(self.calls[0][0]['translate_images'])
        self.calls.clear()
        self.ws.update('paper', lambda p: p.update(blocks=[], translation={}))
        self.jobs._run_bulk(self.ws, {'pages': [1], 'translate': True}, threading.Event())
        self.assertTrue(self.calls[0][0]['translate_images'])

    def test_continue_fills_only_skipped_labels_preserving_other_data(self):
        self.seed_skipped((1, 2))
        self.cfg['translate_images'] = True
        self.ws.apply_reader_ops([{'op': 'paper_note', 'body': 'Retain my note'}])
        write_json_atomic(self.ws.root/'discussion.json', {'entries': [{'id': 'check1', 'kind': 'check', 'by': 'translator', 'anchor': 'p1', 'body': 'Retain review'}]})
        before = self.ws.load('paper')
        reader, discussion = self.ws.load('reader'), self.ws.load('discussion')
        self.jobs.enqueue(self.ws)
        with patch.object(translate.consistency, 'check') as consistency:
            self.drain()
        consistency.assert_not_called()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertEqual(figure_translation.pending_pages(self.ws.load('paper')), set())
        after = self.ws.load('paper')
        for old, new in zip(before['blocks'], after['blocks']):
            if old['type'] != 'figure':
                self.assertEqual(old, new)
            else:
                self.assertEqual(new['image_zh'], '補翻文字' if old.get('image_translation_skipped') else old['image_zh'])
                self.assertEqual(old['id'], new['id'])
                self.assertEqual(old['caption_zh'], new['caption_zh'])
        self.assertEqual(before['glossary'], after['glossary'])
        self.assertEqual(self.ws.load('reader'), reader)
        self.assertEqual(self.ws.load('discussion'), discussion)

    def test_explicit_image_fill_works_when_global_off_and_only_fills_images(self):
        self.seed_skipped()
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        self.assertTrue(self.ws.load('job')['translate_images'])
        self.assertTrue(self.ws.load('job')['images_only'])
        self.drain()
        self.assertFalse(self.cfg['translate_images'])
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertEqual(len(self.calls), 1)
        items = json.loads(self.calls[0][1].split('要翻译的内容（键 → 英文）：\n')[1])
        self.assertEqual(items, {'f1#image': 'Time (days)'})

    def test_no_pending_images_and_off_continue_do_not_call_model(self):
        self.seed_skipped()
        self.jobs.enqueue(self.ws)
        self.drain()
        self.assertEqual(self.calls, [])
        self.ws.update('paper', lambda p: p['blocks'][2].pop('image_translation_skipped'))
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        self.drain()
        self.assertEqual(self.calls, [])

    def test_missing_image_fill_stays_pending_and_retry_preserves_body(self):
        self.seed_skipped()
        before = self.ws.load('paper')['blocks'][:2]
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        with patch.object(engines, 'run', return_value='{"zh": {}}') as model:
            self.drain()
        self.assertEqual(model.call_count, 2)
        self.assertEqual(self.ws.load('job')['state'], 'partial')
        self.assertEqual(figure_translation.pending_pages(self.ws.load('paper')), {1})
        translate_api.enqueue(self.jobs, self.ws, {'failed': True})
        self.assertTrue(self.ws.load('job')['images_only'])
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertEqual(self.ws.load('paper')['blocks'][:2], before)

    def test_cancelled_image_fill_preserves_existing_blocks(self):
        self.seed_skipped()
        before = self.ws.load('paper')['blocks']
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        with patch.object(engines, 'run', side_effect=engines.Cancelled):
            self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'cancelled')
        self.assertEqual(self.ws.load('paper')['blocks'], before)
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')

    def test_boolean_api_validation(self):
        with patch.object(config, 'save', return_value={}) as save, patch.object(config, 'public', return_value={}):
            for invalid in ['false', 0, 1, None, [], {}]:
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    settings_api.save_config({'translate_images': invalid})
            save.assert_not_called()
            settings_api.save_config({'translate_images': False})
            save.assert_called_once_with({'translate_images': False})

    def test_legacy_missing_labels_are_not_silently_scheduled(self):
        self.seed_skipped()
        self.ws.update('paper', lambda p: p['blocks'][2].pop('image_translation_skipped'))
        self.cfg['translate_images'] = True
        self.jobs.enqueue(self.ws)
        self.drain()
        self.assertEqual(self.calls, [])


    def test_mixed_original_and_image_fill_keep_completed_page_checks(self):
        self.seed_skipped()
        self.cfg.update(translate_images=True, batch_pages=3)
        self.ws.update('paper', lambda p: p['translation'].update(en_pages=[2]))
        self.ws.update('paper', lambda p: p['blocks'][3].pop('zh'))
        write_json_atomic(self.ws.root/'discussion.json', {'entries': [{'id': 'check1', 'kind': 'check', 'by': 'translator', 'anchor': 'p1', 'body': 'Retain review'}]})
        self.jobs.enqueue(self.ws)
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertEqual(self.ws.load('paper')['blocks'][3]['zh'], '補翻文字')
        self.assertEqual(self.ws.load('discussion')['entries'][0]['id'], 'check1')
        self.assertEqual(figure_translation.pending_pages(self.ws.load('paper')), set())
        self.assertEqual(len(self.calls), 2)

    def test_real_pdf_and_epub_images_notes_and_exports_survive_skip_and_fill(self):
        import hashlib
        from easyread import build
        from scripts.smoke_backend import probe_pdf
        from tests.test_epub import epub_bytes
        lib = Library(self.ws.root/'formats')
        for suffix, document in [('pdf', probe_pdf()), ('epub', epub_bytes())]:
            with self.subTest(format=suffix):
                ws, _ = lib.create_from_document(document, 'synthetic.' + suffix)
                translate.prepare(ws)
                source = ws.root/('source.' + suffix)
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                ws.apply_reader_ops([{'op': 'paper_note', 'body': 'Synthetic retained note'}])
                reader = ws.load('reader')
                def model(cfg, prompt, cwd, images=None, cancel=None, meter=None):
                    if '要翻译的内容（键 → 英文）：\n' in prompt:
                        return self.engine(cfg, prompt, cwd, images, cancel, meter)
                    response = blocks()
                    response[2]['box'] = [0.1, 0.1, 0.9, 0.7]
                    return json.dumps({'blocks': response})
                with patch.object(engines, 'run', side_effect=model):
                    self.assertEqual(translate.translate_pages(ws, self.cfg, [1], threading.Event(), lambda *a: None), {})
                    figure = ws.load('paper')['blocks'][2]
                    self.assertTrue((ws.root/figure['src']).is_file())
                    image_digest = hashlib.sha256((ws.root/figure['src']).read_bytes()).hexdigest()
                    self.assertTrue(figure['image_translation_skipped'])
                    before = ws.load('paper')['blocks'][:2]
                    cfg = dict(self.cfg, translate_images=True, _figure_fill_pages={1})
                    self.assertEqual(translate.translate_pages(ws, cfg, [1], threading.Event(), lambda *a: None), {})
                self.assertEqual(ws.load('paper')['blocks'][:2], before)
                self.assertEqual(ws.load('reader'), reader)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
                self.assertEqual(hashlib.sha256((ws.root/figure['src']).read_bytes()).hexdigest(), image_digest)
                exported = build.build(ws, ws.root/'synthetic-export.html', lang='zh-TW').read_text(encoding='utf-8')
                self.assertIn('data:image/webp;base64,', exported)
                self.assertIn('Synthetic retained note', exported)
                self.assertIn('補翻文字', exported)



    def test_explicit_pages_still_retranslate_body_instead_of_image_only_fill(self):
        self.seed_skipped()
        self.cfg['translate_images'] = True
        self.ws.update('paper', lambda p: p['blocks'][0].update(zh='OLD BODY TRANSLATION'))
        translate_api.enqueue(self.jobs, self.ws, {'pages': [1]})
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertIn('这次只处理第 1 页', self.calls[0][1])
        self.assertEqual(self.ws.load('paper')['blocks'][0]['zh'], '正文')

    def test_automatic_image_fill_retry_does_not_turn_into_page_retranslation(self):
        self.seed_skipped()
        self.cfg['translate_images'] = True
        self.jobs.enqueue(self.ws)
        with patch.object(engines, 'run', return_value='{"zh": {}}'):
            self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'partial')
        translate_api.enqueue(self.jobs, self.ws, {'failed': True})
        self.assertTrue(self.ws.load('job')['fill_skipped_images'])
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertIn('要翻译的内容', self.calls[0][1])

    def test_explicit_image_fill_still_requires_page_cap_confirmation(self):
        self.seed_skipped((1, 2))
        self.cfg['page_cap'] = 1
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'confirm')
        self.assertEqual(self.calls, [])
        translate_api.enqueue(self.jobs, self.ws, {'confirmed': True})
        self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertEqual(len(self.calls), 2)

    def test_config_default_and_false_persist_across_reload(self):
        with patch.object(config, 'CONFIG_PATH', self.ws.root/'synthetic-config.json'):
            self.assertTrue(self.real_config_load()['translate_images'])
            config.save({'translate_images': False})
            self.assertFalse(self.real_config_load()['translate_images'])
            stored = json.loads((self.ws.root/'synthetic-config.json').read_text(encoding='utf-8'))
            self.assertFalse(stored['translate_images'])



    def test_structured_image_fill_extracts_only_translation(self):
        self.seed_skipped()
        before = self.ws.load('paper')
        original = before['blocks'][2].copy()
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        value = {'image_zh': '分數\n時間（天）\n群組 A', 'image_en': 'DO NOT REPLACE SOURCE',
                 'src': '../../untrusted', 'box': [0, 0, 1, 1]}
        with patch.object(engines, 'run', return_value=json.dumps({'zh': {'f1#image': value}})) as model:
            self.drain()
        self.assertEqual(model.call_count, 1)
        after = self.ws.load('paper')
        figure = after['blocks'][2]
        self.assertEqual(figure['image_zh'], value['image_zh'])
        self.assertEqual(figure['image_en'], original['image_en'])
        self.assertEqual(figure.get('src'), original.get('src'))
        self.assertEqual(figure.get('box'), original.get('box'))
        self.assertEqual(after['blocks'][:2], before['blocks'][:2])
        self.assertNotIn('image_translation_skipped', figure)
        self.assertEqual(self.ws.load('job')['state'], 'done')

    def test_malformed_image_values_stay_pending_instead_of_becoming_text(self):
        for value in [True, 80, ['translated'], {'image_en': 'no translation'},
                      {'image_zh': {'nested': 'not text'}}, "{'image_zh': 'Python repr'}"]:
            with self.subTest(value=value):
                self.seed_skipped()
                original = self.ws.load('paper')['blocks']
                translate_api.enqueue(self.jobs, self.ws, {'images': True})
                with patch.object(engines, 'run', return_value=json.dumps({'zh': {'f1#image': value}})) as model:
                    self.drain()
                self.assertEqual(model.call_count, 2)
                self.assertEqual(self.ws.load('job')['state'], 'partial')
                self.assertEqual(self.ws.load('paper')['blocks'], original)
                self.assertEqual(figure_translation.pending_pages(self.ws.load('paper')), {1})

    def test_repair_reply_is_subject_to_image_type_validation(self):
        self.seed_skipped()
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        replies = [json.dumps({'zh': {'f1#image': 'bad math'}}),
                   json.dumps({'zh': {'f1#image': {'image_zh': '修正譯文', 'src': 'ignored'}}})]
        with patch.object(engines, 'run', side_effect=replies), patch.object(translate, '_problems', return_value=['repair']):
            self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertEqual(self.ws.load('paper')['blocks'][2]['image_zh'], '修正譯文')

    def test_low_level_image_fill_never_stringifies_objects_and_keeps_table_arrays(self):
        from easyread import paperdata
        self.seed_skipped()
        missing = paperdata.fill_zh(self.ws, {'zh': {'f1#image': {'image_zh': ['invalid']}}}, [1], {'f1#image'})
        self.assertEqual(missing, ['f1#image'])
        self.assertNotIn('image_zh', self.ws.load('paper')['blocks'][2])
        missing = paperdata.fill_zh(self.ws, {'zh': {'f1#image': {'image_zh': '純譯文'},
                                                    't1#head': [['組別', '數值']]}},
                                    [1], {'f1#image', 't1#head'})
        self.assertEqual(missing, [])
        self.assertEqual(self.ws.load('paper')['blocks'][2]['image_zh'], '純譯文')
        self.assertEqual(self.ws.load('paper')['blocks'][1]['head'], [['組別', '數值']])

    def test_serialized_json_image_object_and_prompt_schema(self):
        self.seed_skipped()
        translate_api.enqueue(self.jobs, self.ws, {'images': True})
        seen=[]
        def model(cfg, prompt, *args):
            seen.append(prompt)
            return json.dumps({'zh': {'f1#image': json.dumps({'image_zh': '分數\n時間'})}})
        with patch.object(engines, 'run', side_effect=model):
            self.drain()
        self.assertEqual(self.ws.load('job')['state'], 'done')
        self.assertEqual(self.ws.load('paper')['blocks'][2]['image_zh'], '分數\n時間')
        self.assertIn('#image 鍵的值必須是純譯文字串', seen[0])


if __name__ == '__main__':
    unittest.main()
