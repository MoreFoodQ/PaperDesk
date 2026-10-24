"""整篇翻譯入口：繼續確認中的任務、重試失敗頁、給已整理的原文補譯文。"""
from __future__ import annotations

from . import figure_translation, paperdata, translate


def enqueue(jobs, ws, body: dict) -> dict:
    last = ws.load("job") or {}
    pending = last.get("state") == "confirm"
    explicit = body.get("pages") is not None
    pages = paperdata.parse_pages(body["pages"]) if explicit else None
    cap_check = False
    scope = body.get("scope") or (last.get("scope") if pending else None)
    read = bool(last.get("read")) if pending else bool(body.get("read"))
    model = (last.get("model") or "") if pending else str(body.get("model") or "")
    target = (last.get("target") or "") if pending else ""
    translate_images = last.get("translate_images", True) if pending or body.get("failed") else None
    images_only = bool(last.get("images_only")) if pending or body.get("failed") else body.get("images") is True
    if body.get("images") is True and not pending and not body.get("failed"):
        pages = sorted(figure_translation.pending_pages(ws.load("paper")))
        translate_images, read, cap_check = True, False, True
    if pending and not explicit:
        # 確認的是等待時已算好的頁，不能因為後來又整理了原文而擴大範圍。
        pages = last.get("pages")
        cap_check = last.get("cap_check") is True
        if pages is not None and body.get("scope") and scope != last.get("scope"):
            selected = translate.scope_pages(ws, scope)
            if selected is not None:
                pages = [n for n in pages if n in selected]
                cap_check = False  # 使用者已選擇更小的明確範圍。
    if body.get("failed"):
        pages = sorted(int(k) for k in (last.get("failed") or {})) or None
        read, model, target = bool(last.get("read")), last.get("model") or "", last.get("target") or ""
    elif body.get("en"):
        read = False
        if not explicit and not pending:
            pages = sorted(set((ws.load("paper").get("translation") or {}).get("en_pages", [])))
            cap_check = True  # 系統生成的頁計劃仍需確認；使用者親自填 pages 才豁免。
    jobs.enqueue(ws, pages=pages, translate_after=True, scope=scope, read=read, model=model,
                 confirmed=body.get("confirmed") is True, target=target, cap_check=cap_check,
                 translate_images=translate_images, images_only=images_only,
                 fill_skipped_images=last.get("fill_skipped_images") if pending or body.get("failed") else None)
    return {"ok": True}
