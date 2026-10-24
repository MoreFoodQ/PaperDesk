"""Optional figure-label translation, independent of captions and source images."""
from __future__ import annotations

import json
import re


def enabled(cfg: dict) -> bool:
    # Old configurations retain their original behavior.
    return cfg.get("translate_images", True) is not False


def pending_pages(paper: dict) -> set[int]:
    # Only deliberately skipped labels are pending. Do not reinterpret old books.
    return {b["page"] for b in paper.get("blocks", [])
            if b.get("type") == "figure" and b.get("image_translation_skipped") is True
            and b.get("image_en") and not b.get("image_zh") and type(b.get("page")) is int}


def apply(blocks: list[dict], previous: list[dict], translate_images: bool) -> None:
    old = {(b.get("id"), b.get("page")): dict(b) for b in previous if b.get("type") == "figure"}
    for block in blocks:
        # State markers are owned by the application, never the model.
        block.pop("image_translation_skipped", None)
        if block.get("type") != "figure" or translate_images:
            continue
        before = old.get((block.get("id"), block.get("page")), {})
        if before.get("image_zh"):
            block["image_zh"] = before["image_zh"]
            block["image_en"] = before.get("image_en", block.get("image_en", ""))
        else:
            block.pop("image_zh", None)
            if block.get("image_en"):
                block["image_translation_skipped"] = True


SKIP_INSTRUCTION = """Figure-label translation is disabled for this task. Preserve each figure, its box,
and readable original labels in image_en, but leave image_zh empty. Continue to
translate figure captions, paragraphs, headings and tables normally. Do not omit
figures or change page images. Do not produce image_translation_skipped fields.
"""


_SERIALIZED_LABEL = re.compile(r"^\s*\{\s*['\"](?:image_zh|image_en|src|box)['\"]\s*:")


def label_text(value) -> str | None:
    """接受純譯文或明確的 image_zh 欄位；不把物件轉成顯示文字。"""
    if isinstance(value, str) and _SERIALIZED_LABEL.match(value):
        # Accept strict JSON only. Python repr and malformed objects remain missing.
        if len(value) > 65536:
            return None
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None
    if isinstance(value, dict):
        value = value.get("image_zh")
    if not isinstance(value, str) or not value.strip() or _SERIALIZED_LABEL.match(value):
        return None
    return value


def fill_values(values: dict, keys: set[str]) -> dict:
    """只保留要求的補翻鍵，並驗證圖片文字；表格表頭仍保留陣列格式。"""
    out = {}
    for key, value in values.items():
        if key not in keys:
            continue
        if key.endswith("#image"):
            value = label_text(value)
            if value is None:
                continue
        out[key] = value
    return out
