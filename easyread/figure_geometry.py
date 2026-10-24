"""從 PDF 圖像和矢量路徑確定圖的範圍，題注只用於關聯，不限制圖所在的欄。"""
from __future__ import annotations

import math
from pathlib import Path

from . import figure_pixels, page_margins
from .log import log


def _bounds(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def _covered(box, regions, fraction=.6):
    area = _area(box)
    return any(_area([max(box[0], b[0]), max(box[1], b[1]),
                      min(box[2], b[2]), min(box[3], b[3])]) >= area * fraction
               for b in regions) if area else False


def _box(obj, page):
    try:
        box = [float(obj[k]) / size for k, size in
               (("x0", page.width), ("top", page.height), ("x1", page.width), ("bottom", page.height))]
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    if not all(math.isfinite(v) for v in box):
        return None
    box = [max(0, min(1, v)) for v in box]
    return box if box[0] <= box[2] and box[1] <= box[3] else None


def _distance(a, b, aspect):
    dx = max(a[0] - b[2], b[0] - a[2], 0) * aspect
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return math.hypot(dx, dy)


def _groups(boxes, aspect, gap):
    boxes = sorted(boxes, key=lambda b: b[0])
    parents = list(range(len(boxes)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for i, box in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            other = boxes[j]
            if other[0] > box[2] + gap / aspect:
                break
            if _distance(box, other, aspect) <= gap:
                parents[find(j)] = find(i)
    groups = {}
    for i, box in enumerate(boxes):
        groups.setdefault(find(i), []).append(box)
    return [_bounds(g) for g in groups.values()]


def _blank_fill(obj):
    """只填充不描邊、填的是白色（頁面底色）的路徑：PDF 常用它鋪背景，頁面上看不見。"""
    color = obj.get("non_stroking_color")
    if not obj.get("fill") or obj.get("stroke") or not isinstance(color, (tuple, list)) or not color:
        return False
    try:
        color = [float(v) for v in color]
    except (TypeError, ValueError):
        return False
    return all(v <= .04 for v in color) if len(color) == 4 else all(v >= .96 for v in color)


def _separator(box):
    width, height = box[2] - box[0], box[3] - box[1]
    return width > .65 and height < .004 or height > .75 and width < .004


def _separators(page):
    """頁眉橫線、欄間豎線這類分隔線；渲染判斷可見範圍時也要抹掉，免得圖片白邊靠它撐到頁眉。"""
    boxes = [_box(obj, page) for obj in page.lines + page.rects]
    return [b for b in boxes if b and _separator(b)]


def _clear_gap(a, b, blockers):
    """兩塊圖形之間沒有正文或別的題注隔開。"""
    if a[3] <= b[1] or b[3] <= a[1]:
        gap = [min(a[0], b[0]), min(a[3], b[3]), max(a[2], b[2]), max(a[1], b[1])]
    else:
        gap = [min(a[2], b[2]), max(a[1], b[1]), max(a[0], b[0]), min(a[3], b[3])]
    return not any(min(gap[2], c[2]) - max(gap[0], c[0]) > .002 and min(gap[3], c[3]) - max(gap[1], c[1]) > .002
                   for c in blockers)


def _graphics(page, occupied, captions, visible):
    images = []
    for obj in page.images:
        box = _box(obj, page)
        box = visible(box) if box else None  # 圖片自帶的白邊不算圖
        if box and _area(box) < .8 and box[3] > .06 and box[1] < .94 \
                and box[2] - box[0] >= .04 and box[3] - box[1] >= .025 \
                and not (box[2] - box[0] < .2 and box[3] - box[1] < .08 and _covered(box, occupied)):
            # A matched paragraph can enclose a figure when PDF text order crosses
            # columns. Only use that approximate text box to reject small inline images.
            images.append(box)

    paths = []
    for obj in page.lines + page.rects + page.curves:
        box = _box(obj, page)
        if not box or _area(box) >= .8 or box[3] < .06 or box[1] > .94 or _blank_fill(obj):
            continue
        if _separator(box):
            continue  # Page separators, not figure components.
        # Give lines a small area for the text/background exclusion tests.
        box = visible([max(0, box[0] - .001), max(0, box[1] - .001),
                       min(1, box[2] + .001), min(1, box[3] + .001)])
        if not box:
            continue  # 被裁剪路徑擋住或畫成底色，頁面上看不見
        if _covered(box, occupied + images) or _covered(box, captions, .5) \
                or any(_covered(cap, [box], .8) for cap in captions):
            continue
        paths.append(box)
    vectors = _groups(paths, page.width / page.height, .008)
    large = [b for b in vectors if b[2] - b[0] >= .045 and b[3] - b[1] >= .025]
    # 太小的組（勾叉記號、虛線分隔）不單獨當圖，但能像標籤一樣把圖裡分開的幾塊連起來。
    return images + large, [b for b in vectors if b not in large]


def _score(graphic, caption, aspect):
    box = caption["box"]
    # Side captions overlap vertically with the drawing, so either direction is valid.
    if caption.get("caption_pos", "below") == "below":
        if graphic[1] > box[3] + .02:
            return math.inf
    elif graphic[3] < box[1] - .02:
        return math.inf
    return _distance(graphic, box, aspect)


def _page_regions(page, captions, occupied, render, running=()):
    aspect = page.width / page.height
    all_words = [b for b in (_box(word, page) for word in page.extract_words()) if b]
    separators = _separators(page)
    top, bottom = page_margins.margins(separators, running)
    masks = render(all_words + separators)
    if masks is None:
        return {}  # 渲染不了就無法確認哪些圖形看得見，交給題注估算
    mask, ink = masks
    graphics, marks = _graphics(page, occupied, [c["box"] for c in captions.values()],
                                lambda box: figure_pixels.trim(mask, box))
    assigned = {bid: [] for bid in captions}
    for graphic in graphics:
        bid = min(captions, key=lambda key: _score(graphic, captions[key], aspect))
        if math.isfinite(_score(graphic, captions[bid], aspect)):
            assigned[bid].append(graphic)

    result = {}
    # 頁眉頁腳裡的字不能當圖的標籤。
    words = [b for b in all_words if b[3] > top + .002 and b[1] < bottom - .002
             and not _covered(b, occupied) and figure_pixels.inked(ink, b)]
    marks = [b for b in marks if b[3] > top + .002 and b[1] < bottom - .002]
    for bid, candidates in assigned.items():
        caption = captions[bid]
        if caption["type"] != "figure" or not candidates:
            continue
        nearest = min(_score(b, caption, aspect) for b in candidates)
        if nearest > .18:
            continue
        selected = [b for b in candidates if _score(b, caption, aspect) <= nearest + .012]
        others = [c["box"] for key, c in captions.items() if key != bid]
        # A distant top row belongs to the same figure when it connects to the
        # bottom row. Do not require every panel to be near the caption itself.
        # 隔著空白、但中間沒有正文的上一排子圖也算同一張圖。
        while True:
            near = [b for b in candidates if b not in selected and
                    any(_distance(b, chosen, aspect) <= .045 or _distance(b, chosen, aspect) <= .2
                        and _clear_gap(b, chosen, occupied + others) for chosen in selected)]
            if not near:
                break
            selected.extend(near)

        # Vector plots can put labels just outside their paths. Keep those labels,
        # while excluding body paragraphs and captions belonging to other figures.
        # 標籤可以一個挨一個連出去（圖裡的小標題、座標軸說明常是 PDF 文字）。
        labels, pending = [], [b for b in words + marks if not _covered(b, others)]
        while True:
            near = [b for b in pending if any(_distance(b, g, aspect) <= .03 for g in selected + labels)]
            if not near:
                break
            labels.extend(near)
            pending = [b for b in pending if b not in near]
        bounds = _bounds(selected + labels + [caption["box"]])
        cap, drawing = caption["box"], _bounds(selected)
        # 題注整個在圖下方（或上方）時，圖框不越過題注繼續往外擴；側邊題注和圖上下重疊，不受限。
        if caption.get("caption_pos", "below") == "below":
            if cap[1] >= drawing[3] - .01:
                bounds[3] = cap[3]
        elif cap[3] <= drawing[1] + .01:
            bounds[1] = cap[1]
        result[bid] = [round(max(0, bounds[0] - .008), 4), round(max(0, bounds[1] - .008), 4),
                       round(min(1, bounds[2] + .008), 4), round(min(1, bounds[3] + .008), 4)]
    return result


def locate_figures(root: Path, blocks: list[dict], layout: dict) -> dict[str, list[float]]:
    """沒有可靠圖形邊界時回傳空結果，讓原有題注估算規則繼續工作。"""
    by_page = {}
    caption_ids = {b.get("id") for b in blocks if b.get("type") in ("figure", "table")}
    for block in blocks:
        loc = layout.get(block.get("id"))
        if block.get("type") not in ("figure", "table") or not loc:
            continue
        by_page.setdefault(loc["page"], {})[block["id"]] = {
            "box": loc["box"], "type": block["type"], "caption_pos": block.get("caption_pos", "below")}
    if not by_page or not (root / "source.pdf").is_file():
        return {}
    import pdfplumber

    result = {}
    try:
        with pdfplumber.open(root / "source.pdf") as pdf:
            running = page_margins.running_lines(root / "extract", len(pdf.pages))
            for pn, captions in by_page.items():
                if not any(c["type"] == "figure" for c in captions.values()) or not 1 <= pn <= len(pdf.pages):
                    continue
                occupied = [box for bid, loc in layout.items() if bid not in caption_ids and loc["page"] == pn
                            for box in loc.get("boxes") or [loc["box"]]]
                def render(erase, pn=pn):
                    try:
                        return figure_pixels.visible_mask(root / "source.pdf", pn - 1, erase)
                    except Exception:  # noqa: BLE001
                        log.exception("渲染原页失败 %s 第 %s 页", root, pn)
                        return None
                try:
                    result.update(_page_regions(pdf.pages[pn - 1], captions, occupied, render, running.get(pn, ())))
                except Exception:  # noqa: BLE001
                    log.exception("读取 PDF 图形边界失败 %s 第 %s 页", root, pn)
    except Exception:  # noqa: BLE001
        log.exception("读取 PDF 图形边界失败 %s", root)
    return result
