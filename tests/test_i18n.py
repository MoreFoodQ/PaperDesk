"""介面語言：系統語言判斷、tr 填佔位符、頁面注入詞典，以及所有介面文字都有英文。  python -m unittest tests.test_i18n"""
import os
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from easyread import i18n

ROOT = Path(__file__).resolve().parents[1]


class I18nTest(unittest.TestCase):
    def setUp(self):
        i18n.system_lang.cache_clear()

    def tearDown(self):
        i18n.system_lang.cache_clear()

    def test_system_lang_from_electron(self):
        for tag, want in (("zh-CN", "zh-TW"), ("zh-TW", "zh-TW"), ("en-US", "en"), ("de", "en"), ("ja", "en")):
            i18n.system_lang.cache_clear()
            with mock.patch.dict(os.environ, {"EASYREAD_SYSTEM_LANG": tag}):
                self.assertEqual(i18n.system_lang(), want, tag)

    def test_system_lang_from_env(self):
        env = {k: v for k, v in os.environ.items() if k not in ("EASYREAD_SYSTEM_LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE")}
        env["LANG"] = "de_DE.UTF-8"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(i18n.system_lang(), "en")

    def test_choice_overrides_system(self):
        with mock.patch.object(i18n, "system_lang", lambda: "zh"), mock.patch.object(i18n, "choice", lambda: "en"):
            self.assertEqual(i18n.lang(), "en")
        with mock.patch.object(i18n, "system_lang", lambda: "en"), mock.patch.object(i18n, "choice", lambda: "auto"):
            self.assertEqual(i18n.lang(), "en")

    def test_tr(self):
        fake = {"已导入 {n} 篇": "Imported {n} papers"}
        with mock.patch.object(i18n, "en_dict", lambda: fake):
            with mock.patch.object(i18n, "lang", lambda: "en"):
                self.assertEqual(i18n.tr("已导入 {n} 篇", n=3), "Imported 3 papers")
                self.assertEqual(i18n.tr("词典里没有"), "词典里没有")
            with mock.patch.object(i18n, "lang", lambda: "zh"):
                self.assertEqual(i18n.tr("已导入 {n} 篇", n=3), "已导入 3 篇")

    def test_inject(self):
        page = '<html lang="zh-CN">\n<head><title>EasyRead</title></head>'
        self.assertNotIn("pr-i18n", i18n.inject(page, "zh"))
        with mock.patch.object(i18n, "en_dict", lambda: {"设置": "Settings</script>"}):
            out = i18n.inject(page, "en")
        self.assertIn('<html lang="en"', out)
        self.assertIn('id="pr-i18n"', out)
        self.assertNotIn("Settings</script>", out)  # 詞典裡的 < 要轉義，不能提前結束 script

    def test_every_ui_string_has_english(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "i18n_check.py")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout[-3000:])

    def test_traditional_dictionary_covers_ui_and_preserves_placeholders(self):
        from scripts.i18n_check import collect
        keys, _ = collect()
        dictionary = i18n.tw_dict()
        self.assertFalse(keys - dictionary.keys())
        for key in keys:
            self.assertEqual(set(re.findall(r'\{\w+\}', key)),
                             set(re.findall(r'\{\w+\}', dictionary[key])), key)
        with mock.patch.object(i18n, 'lang', return_value='zh-TW'):
            self.assertEqual(i18n.tr('万'), '萬')
            self.assertEqual(i18n.tr('自定义地址'), '自訂位址')

    def test_legacy_simplified_ui_preference_uses_traditional(self):
        from easyread import prefs
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(prefs, 'load', return_value={'ui': {'lang': 'zh'}}):
            self.assertEqual(i18n.choice(), 'zh-TW')
            self.assertEqual(i18n.lang(), 'zh-TW')


if __name__ == "__main__":
    unittest.main()
