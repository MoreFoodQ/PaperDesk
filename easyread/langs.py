"""譯文語言：論文翻成哪種語言。預設中文；設定裡可以改，每篇論文第一次翻譯時記下當時的語言。

資料格式不變：譯文仍然存在 zh / caption_zh / title_zh 這些欄位裡，欄位名只是歷史叫法。
"""
from __future__ import annotations

# 程式碼 → (介面上顯示的名字, 提示詞裡怎麼稱呼, 英文名)
TARGETS = {
    "zh-TW": ("繁體中文", "繁體中文（台灣用語；使用資訊、資料、程式、網路、預設、儲存等用詞；專業術語依學科語境，保留原文縮寫與公式；不得使用簡體字）", "Traditional Chinese"),  # i18n-ok
    "zh": ("中文", "中文", "Chinese"),  # i18n-ok 語言名
    "ja": ("日本語", "日语（日本語）", "Japanese"),  # i18n-ok
    "ko": ("한국어", "韩语（한국어）", "Korean"),  # i18n-ok
    "es": ("Español", "西班牙语（Español）", "Spanish"),  # i18n-ok
    "fr": ("Français", "法语（Français）", "French"),  # i18n-ok
    "de": ("Deutsch", "德语（Deutsch）", "German"),  # i18n-ok
}
DEFAULT = "zh"


def valid(code: str | None) -> str:
    return code if code in TARGETS else DEFAULT


def of_paper(meta: dict | None, cfg: dict | None = None) -> str:
    """這篇論文的譯文語言：翻過的用當時記下的，沒翻過的用設定裡的。"""
    meta = meta or {}
    if meta.get("target") in TARGETS:
        return meta["target"]
    if meta.get("title_zh"):  # 1.3 以前譯的論文沒記語言，都是中文
        return DEFAULT
    if cfg is None:
        from . import config
        cfg = config.load()
    return valid(cfg.get("target"))


def remember(ws, code: str | None) -> None:
    """匯入時選了譯文語言：記到這篇論文上。已經有譯文的論文不改，免得一篇裡混兩種語言。"""
    if code not in TARGETS:
        return

    def apply(paper):
        meta = paper.setdefault("meta", {})
        if not meta.get("target") and not any(b.get("zh") or b.get("caption_zh") for b in paper.get("blocks", [])):
            meta["target"] = code
    ws.update("paper", apply)


def prompt_name(code: str) -> str:
    return TARGETS[valid(code)][1]


def listing() -> list[dict]:
    return [{"id": k, "name": v[0]} for k, v in TARGETS.items()]


def reply_lang(meta: dict | None) -> str:
    """問 AI、整理筆記用什麼語言回答：論文翻過就用譯文語言，沒翻過跟介面語言。提示詞裡的稱呼。"""
    meta = meta or {}
    if meta.get("target") in TARGETS:
        return prompt_name(meta["target"])
    if meta.get("title_zh"):  # 1.3 以前譯的論文沒記語言，都是中文
        return "中文"  # i18n-ok 提示詞
    from . import i18n
    return prompt_name("zh-TW") if i18n.lang() == "zh-TW" else "中文" if i18n.lang() == "zh" else "英文（English）"  # i18n-ok
