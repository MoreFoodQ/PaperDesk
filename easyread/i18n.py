"""介面語言：預設繁體中文，可切換英文或跟隨系統。

PR.t() 與 tr() 的中文來源字串同時是語系索引鍵。舊索引鍵保留原文，
避免既有字典、測試與儲存資料失去對應；新增的註解與文件使用繁體中文。
繁體與英文對照分別位於 web/i18n/zh-TW.json 與 en.json，完整性由測試檢查。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

# 不匯入 config：config 間接匯入了很多用 tr 的模組，這裡保持沒有套件內相依性
EN_PATH = Path(__file__).resolve().parent / "web" / "i18n" / "en.json"
TW_PATH = EN_PATH.with_name("zh-TW.json")
CHOICES = ("auto", "zh-TW", "en")


@lru_cache(maxsize=1)
def tw_dict() -> dict:
    return json.loads(TW_PATH.read_text(encoding="utf-8"))


def _system_language(tag: str) -> str:
    tag = tag.lower().replace("_", "-")
    if _is_zh(tag):
        return "zh-TW"
    return "en"


@lru_cache(maxsize=1)
def _dict_cached(mtime: float) -> dict:
    return json.loads(EN_PATH.read_text(encoding="utf-8"))


def en_dict() -> dict:
    try:
        return _dict_cached(EN_PATH.stat().st_mtime)
    except (OSError, ValueError):
        return {}


def _is_zh(tag: str | None) -> bool:
    tag = (tag or "").strip().lower().replace("_", "-")
    return tag.startswith("zh") or tag.startswith("chinese")


@lru_cache(maxsize=1)
def system_lang() -> str:
    # 桌面版由 Electron 傳進來（macOS 從啟動臺打開時拿不到 LANG）
    tag = os.environ.get("EASYREAD_SYSTEM_LANG")
    if tag:
        return _system_language(tag)
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var)
        if value and value not in ("C", "POSIX", "C.UTF-8"):
            return _system_language(value)
    if sys.platform == "win32":
        try:
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "zh-TW" if lid & 0x3FF == 0x04 else "en"
        except (AttributeError, OSError):
            pass
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3).stdout
            first = next((line.strip(' ",()') for line in out.splitlines() if line.strip(' ",()')), "")
            return _system_language(first)
        except (OSError, subprocess.SubprocessError):
            pass
    return "zh-TW"


def choice() -> str:
    forced = os.environ.get("EASYREAD_LANG")  # 測試、排查問題時臨時指定，優先於設定
    if forced in ("zh-TW", "zh", "en"):
        return forced  # Explicit developer/test override; not a UI choice.
    from . import prefs
    value = (prefs.load().get("ui") or {}).get("lang", "zh-TW")
    if value == "zh":  # Legacy Simplified Chinese UI preference.
        return "zh-TW"
    return value if value in CHOICES else "auto"


def lang() -> str:
    value = choice()
    return value if value in ("zh-TW", "zh", "en") else system_lang()


def tr(text: str, **kw) -> str:
    """中文原文 → 當前語言；{name} 佔位符用 kw 填。"""
    if lang() == "en":
        text = en_dict().get(text) or text
    elif lang() == "zh-TW":
        text = tw_dict().get(text) or text
    return text.format(**kw) if kw else text


def inject(page: str, language: str | None = None) -> str:
    """回傳頁面時寫上語言，英文時把詞典也放入，前端同步就能用。"""
    picked = choice() if language is None else language  # 設定裡的“介面語言”要顯示當前選的是哪項
    language = language or lang()
    from . import config, langs  # 用到時再匯入，見檔案開頭
    target = langs.valid(config.load().get("target"))  # 設定裡的譯文語言：按鈕文字、沒譯過的論文用它
    page = page.replace('<html lang="zh-CN">', f'<html lang="{"zh-CN" if language == "zh" else language}" data-lang-choice="{picked}" data-target="{target}">', 1)
    if language in ("en", "zh-TW"):
        payload = json.dumps(en_dict() if language == "en" else tw_dict(), ensure_ascii=False).replace("<", "\\u003c")
        page = page.replace("</title>", f'</title>\n<script id="pr-i18n" type="application/json">{payload}</script>', 1)
    return page
