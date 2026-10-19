"""Optional figure-label translation, independent of captions and source images."""
from __future__ import annotations


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
