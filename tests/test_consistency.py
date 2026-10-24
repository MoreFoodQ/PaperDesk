"""每段第一批的前文參考、全文譯完後的術語一致性檢查、合併時術語統一的誤傷、不能看圖的引擎在段交界。不調真模型。
python -m unittest tests.test_consistency"""
import json
import shutil
import threading
import unittest
from unittest import mock

from easyread import consistency, engines, front_context, prompts, sentences, terms, translate
from tests.test_translate import make_ws


def page_of(prompt: str) -> int:
    return int(prompt.split("这次只处理第 ")[1].split(" ")[0].split(",")[0])


def run_pages(ws, cfg, pages, engine, cancel=None, plan=None):
    patches = [mock.patch.object(engines, "run", engine), mock.patch.object(translate.pdfwork, "locate", lambda r: None),
               mock.patch.object(translate, "tex_problems", lambda t: [])]
    if plan:
        patches.append(mock.patch.object(translate.segments, "plan", plan))
    for p in patches:
        p.start()
    try:
        return translate.translate_pages(ws, cfg, pages, cancel or threading.Event(), lambda *a: None)
    finally:
        for p in patches:
            p.stop()


class FrontContextTest(unittest.TestCase):
    def setUp(self):
        self.ws = make_ws(6)
        self.addCleanup(shutil.rmtree, self.ws.root, True)
        ex = self.ws.root / "extract"
        (ex / "page-001.txt").write_text("A Great Paper\nAbstract\nWe study DPO, short for direct preference optimization.", encoding="utf-8")
        (ex / "page-003.txt").write_text("2 Method\nWe define the policy as follows and then we keep", encoding="utf-8")
        (ex / "page-004.txt").write_text("writing the sentence on the next page.", encoding="utf-8")

    def test_reference_has_opening_outline_and_full_previous_page(self):
        text = front_context.build(self.ws.root, 4)
        self.assertIn("DPO, short for direct preference optimization", text)  # 前面定義的縮寫
        self.assertIn("2 Method（第 3 页）", text)
        self.assertIn("then we keep", text)  # 頁首半句話前面的那整句
        self.assertIn("不要翻译", text)
        self.assertEqual(front_context.build(self.ws.root, 1), "")
        self.assertNotIn("【论文开头】", front_context.build(self.ws.root, 2))  # 上一頁就是第 1 頁，不重複

    def test_outline_stops_at_references(self):
        (self.ws.root / "extract" / "page-005.txt").write_text("References\n1. Smith, J. and Doe, K. A paper. 2020.", encoding="utf-8")
        toc = front_context.outline(self.ws.root, 5)
        self.assertIn("2 Method（第 3 页）", toc)
        self.assertFalse(any("Smith" in t for t in toc))

    def test_only_first_batch_of_each_later_segment_gets_it(self):
        cfg = {"engine": "openai", "batch_pages": 1, "concurrency": 2, "openai": {"vision": False}}
        seen = {}

        def engine(cfg, prompt, cwd, images=None, cancel=None, meter=None):
            if "这次只处理第" not in prompt:  # 最後的一致性檢查
                return '{"fixes": []}'
            page = page_of(prompt)
            seen[page] = "前文参考" in prompt
            return json.dumps({"blocks": [{"id": f"p{page}-1", "type": "para", "page": page, "en": "x", "zh": "译"}]})

        run_pages(self.ws, cfg, [1, 2, 3, 4, 5, 6], engine)
        firsts = [p for p, has in seen.items() if has]
        self.assertEqual(len(firsts), 1)  # 兩段：只有第二段的第一批
        self.assertGreater(firsts[0], 1)
        self.assertFalse(seen[1])

    def test_prompt_places_reference_before_pages(self):
        p = prompts.translate(self.ws, [4], "text", "", front=front_context.build(self.ws.root, 4))
        self.assertLess(p.index("前文参考"), p.index("===== 第 4 页"))


def paper(blocks, glossary):
    return {"meta": {"target": "zh"}, "glossary": glossary, "blocks": blocks}


class ConsistencyTest(unittest.TestCase):
    GL = [{"en": "standard error", "zh": "标准误差"}, {"en": "policy", "zh": "策略（policy）"}]

    def test_suspects_only_where_term_appears_but_translation_missing(self):
        blocks = [
            {"id": "a", "type": "para", "page": 2, "en": "The standard errors are large.", "zh": "标准误很大。"},
            {"id": "b", "type": "para", "page": 2, "en": "The standard error is small.", "zh": "标准误差很小。"},
            {"id": "c", "type": "para", "page": 3, "en": "No term here.", "zh": "这里没有。"},
            {"id": "d", "type": "list", "page": 3, "items": [{"en": "a policy", "zh": "一个方针"}]},
            {"id": "e", "type": "table", "page": 3, "caption_en": "Table 1: standard error", "caption_zh": "表 1：标准差"},
            {"id": "f", "type": "para", "page": 3, "en": "standard error again", "zh": "又是标准误"},
            {"id": "g", "type": "para", "page": 4, "en": "standard error", "zh": "$标准误差$ 不算"},
        ]
        items, agree = consistency.suspects(paper(blocks, self.GL), {"f"})
        got = {s["key"]: [t["want"] for t in s["terms"]] for s in items}
        # f 使用者改過，不查；g 只在公式裡有，不算用了
        self.assertEqual(got, {"a": ["标准误差"], "d#0": ["策略"], "e#caption": ["标准误差"], "g": ["标准误差"]})
        self.assertEqual(agree, {"standard error": 1})
        items2, agree2 = consistency.suspects(paper(blocks, self.GL), set(), {2})
        self.assertEqual([i["key"] for i in items2], ["a"])
        self.assertEqual(agree2, agree)  # 用了幾段按全文算

    def test_swap_only_when_counts_match(self):
        en = "The bias is small, but the standard deviation is large."
        # bias 出現一次，“偏差”出現兩次（另一次在“標準偏差”裡）：不換
        self.assertIsNone(consistency.swap("估计量的偏差很小，但标准偏差很大。", en, "bias", "偏差", "偏置", []))
        # 術語表裡有“標準偏差”就先護住，次數對上了：只換 bias 那一處
        self.assertEqual(consistency.swap("估计量的偏差很小，但标准偏差很大。", en, "bias", "偏差", "偏置", ["标准偏差"]),
                         "估计量的偏置很小，但标准偏差很大。")
        # 定下的說法包含舊說法：已經是新說法的地方不算，次數對不上就不換（不會變成“標準誤差差”）
        self.assertIsNone(consistency.swap("标准误差和标准误", "standard error and standard error", "standard error", "标准误", "标准误差", []))
        self.assertEqual(consistency.swap("一个标准误", "one standard error", "standard error", "标准误", "标准误差", []), "一个标准误差")
        self.assertIsNone(consistency.swap("$x$ 的标准误", "standard error of $x$", "standard error", "x", "y", []))
        # 換成縮寫後會變成“SFT（SFT）”：不換
        self.assertIsNone(consistency.swap("先做监督微调（SFT）。", "First, supervised fine-tuning (SFT).", "supervised fine-tuning", "监督微调", "SFT", []))

    def test_plain_footnote_is_not_previous_paragraph(self):
        # DeepSeek 把腳註寫成 “3 That is, …”（不帶上標），不能拿它當上一批最後一段
        self.assertTrue(prompts._is_note({"type": "para", "en": "3 That is, the sum of the per-timestep KL-divergences."}))
        self.assertTrue(prompts._is_note({"type": "para", "en": "7One volunteer was excluded."}))
        self.assertFalse(prompts._is_note({"type": "heading", "en": "3 Method"}))
        self.assertFalse(prompts._is_note({"type": "para", "en": "We train the model with " + "many words " * 30 + "here."}))

    def test_sentence_alignment_follows_term_swap(self):
        en = "The standard error is large. It matters."
        zh = "标准误很大。这很重要。"
        obj = {"en": en, "zh": zh, "sents": [[28, 6], [sentences.u16(en), sentences.u16(zh)]]}
        self.assertTrue(sentences.valid(obj))
        new = "标准误差很大。这很重要。"
        moved = dict(obj, zh=new, sents=consistency.resent(obj, zh, new))
        self.assertEqual(moved["sents"], [[28, 7], [sentences.u16(en), sentences.u16(new)]])
        self.assertTrue(sentences.valid(moved))
        self.assertIsNone(consistency.resent(dict(obj, sents=None), zh, new))

    def make(self, blocks, pages=3):
        ws = make_ws(pages)
        self.addCleanup(shutil.rmtree, ws.root, True)
        ws.update("paper", lambda p: p.update(glossary=[dict(g) for g in self.GL], blocks=blocks))
        return ws

    def run_check(self, ws, reply, pages):
        calls, lines = [], []

        def engine(cfg, prompt, cwd, images=None, cancel=None, meter=None):
            calls.append(prompt)
            return json.dumps(reply)

        with mock.patch.object(engines, "run", engine):
            n = consistency.check(ws, {}, list(pages), None, None, lambda w, s: lines.append(s), threading.Lock())
        return n, calls, lines

    def test_program_does_the_edit_model_only_names_it(self):
        ws = self.make([{"id": "a", "type": "para", "page": 2, "en": "The standard error is not small.", "zh": "标准误不小。"},
                        {"id": "b", "type": "para", "page": 2, "en": "A standard error.", "zh": "一个标准差。"}])
        n, calls, lines = self.run_check(ws, {"use": {"standard error": "标准误差"},
                                              "fixes": [{"key": "a", "term": "standard error", "from": "标准误"},
                                                        {"key": "b", "term": "standard error", "from": "不存在的说法"},
                                                        {"key": "zzz", "term": "standard error", "from": "x"}]}, [1, 2, 3])
        self.assertEqual(n, 1)
        self.assertEqual({b["id"]: b["zh"] for b in ws.load("paper")["blocks"]}, {"a": "标准误差不小。", "b": "一个标准差。"})  # “不”還在
        self.assertTrue(any("标准误 → 标准误差" in s for s in lines))
        self.assertEqual(len(calls), 1)

    def test_majority_rendering_replaces_glossary_when_whole_paper(self):
        blocks = [{"id": "a", "type": "para", "page": 2, "en": "The standard error and covariance.", "zh": "标准误差和协方差。"},
                  {"id": "b", "type": "para", "page": 2, "en": "Each standard error.", "zh": "每个标准误。"},
                  {"id": "c", "type": "para", "page": 3, "en": "One standard error.", "zh": "一个标准误。"}]
        ws = self.make([dict(b) for b in blocks])
        self.run_check(ws, {"use": {"standard error": "标准误"}, "fixes": []}, [1, 2, 3])
        p = ws.load("paper")
        self.assertEqual({b["id"]: b["zh"] for b in p["blocks"]}, {"a": "标准误和协方差。", "b": "每个标准误。", "c": "一个标准误。"})
        self.assertEqual(next(g["zh"] for g in p["glossary"] if g["en"] == "standard error"), "标准误")
        # 只重譯了第 3 頁：不動術語表，也不改別的頁
        ws = self.make([dict(b) for b in blocks])
        self.run_check(ws, {"use": {"standard error": "标准误"}, "fixes": []}, [3])
        p = ws.load("paper")
        self.assertEqual(p["blocks"][0]["zh"], "标准误差和协方差。")
        self.assertEqual(next(g["zh"] for g in p["glossary"] if g["en"] == "standard error"), "标准误差")

    def test_user_edit_during_check_is_not_overwritten(self):
        ws = self.make([{"id": "a", "type": "para", "page": 2, "en": "The standard error.", "zh": "标准误。"}])

        def engine(cfg, prompt, cwd, images=None, cancel=None, meter=None):
            ws.update("reader", lambda r: r.setdefault("edits", {}).__setitem__("a", {"zh": "用户的译文"}))
            return json.dumps({"use": {"standard error": "标准误差"}, "fixes": [{"key": "a", "term": "standard error", "from": "标准误"}]})

        with mock.patch.object(engines, "run", engine):
            self.assertEqual(consistency.check(ws, {}, [1, 2, 3], None, None, lambda w, s: None, threading.Lock()), 0)
        self.assertEqual(ws.load("paper")["blocks"][0]["zh"], "标准误。")

    def test_no_call_when_nothing_suspicious(self):
        ws = self.make([{"id": "a", "type": "para", "page": 1, "en": "The standard error.", "zh": "标准误差。"}])
        with mock.patch.object(engines, "run", side_effect=AssertionError("不该调模型")):
            self.assertEqual(consistency.check(ws, {}, [1], None, None, lambda w, s: None, threading.Lock()), 0)

    def test_cancel_during_check_keeps_finished_job(self):
        ws = make_ws(4)
        self.addCleanup(shutil.rmtree, ws.root, True)
        cfg = {"engine": "openai", "batch_pages": 1, "concurrency": 2, "openai": {"vision": False}}
        cancel = threading.Event()

        def engine(cfg, prompt, cwd, images=None, cancel_=None, meter=None):
            if "这次只处理第" not in prompt:
                cancel.set()
                raise engines.Cancelled()
            page = page_of(prompt)
            return json.dumps({"glossary": [{"en": "standard error", "zh": "标准误差"}],
                               "blocks": [{"id": f"p{page}-1", "type": "para", "page": page, "en": "standard error", "zh": "标准误"}]})

        self.assertEqual(run_pages(ws, cfg, [1, 2, 3, 4], engine, cancel), {})
        self.assertEqual(ws.load("paper")["translation"]["done_pages"], [1, 2, 3, 4])
        self.assertIn("术语一致性检查已取消", (ws.root / "job.log").read_text(encoding="utf-8"))


class TermsUnifyTest(unittest.TestCase):
    def test_merge_time_unify_skips_other_meanings(self):
        data = {"glossary": [{"en": "bias", "zh": "偏差"}],
                "blocks": [{"id": "x", "type": "para", "page": 3, "en": "The bias is small, but the standard deviation is large.",
                            "zh": "偏差很小，但标准偏差很大。"},
                           {"id": "y", "type": "para", "page": 3, "en": "The bias is small.", "zh": "偏差很小。"}]}
        terms.unify([{"en": "bias", "zh": "偏置"}], data)
        self.assertEqual([b["zh"] for b in data["blocks"]], ["偏差很小，但标准偏差很大。", "偏置很小。"])


class SeamTest(unittest.TestCase):
    def engine(self, seen):
        def run(cfg, prompt, cwd, images=None, cancel=None, meter=None):
            if "这次只处理第" not in prompt:
                return '{"fixes": []}'
            page = page_of(prompt)
            seen[page] = (prompt, list(images or []))
            return json.dumps({"blocks": [{"id": f"p{page}-1", "type": "para", "page": page, "en": "x", "zh": "译"}]})
        return run

    def test_text_engine_seam_owner_gets_whole_next_page(self):
        ws = make_ws(8)
        self.addCleanup(shutil.rmtree, ws.root, True)
        (ws.root / "extract" / "page-005.txt").write_text("Table 3 header row " * 120 + "THE-CONTINUATION ends here.", encoding="utf-8")
        cfg = {"engine": "openai", "batch_pages": 2, "concurrency": 2, "openai": {"vision": False}}
        seen = {}
        run_pages(ws, cfg, list(range(1, 9)), self.engine(seen), plan=lambda pages, size, k, root: [pages[:4], pages[4:]])
        self.assertIn("THE-CONTINUATION", seen[3][0])  # 第 3–4 頁是前一段最後一批：拿到第 5 頁全文
        self.assertNotIn("THE-CONTINUATION", seen[1][0])

    def test_resume_batches_only_join_consecutive_pages(self):
        self.assertEqual(translate._batches([3, 6, 7, 10, 11, 14], 2, set()), [[3], [6, 7], [10, 11], [14]])

    def test_resume_seam_owner_still_peeks_next_page(self):
        ws = make_ws(6)
        self.addCleanup(shutil.rmtree, ws.root, True)
        # 第 5 頁上次已經譯完（跳過了頁首續文），這次只續傳第 3–4 頁
        ws.update("paper", lambda p: p["translation"].update(done_pages=[1, 2, 5, 6]))
        cfg = {"engine": "claude", "batch_pages": 2, "concurrency": 1, "claude": {}}
        seen = {}
        with mock.patch.object(translate.pdfwork, "engine_image", lambda root, n: root / f"extract/page-{n:03d}.jpg"):
            run_pages(ws, cfg, [3, 4], self.engine(seen))
        self.assertIn("extract/page-005.jpg", seen[3][0])


if __name__ == "__main__":
    unittest.main()
