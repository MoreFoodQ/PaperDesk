"""術語統一：一批譯完並進 paper.json 前，它新報的術語如果和術語表裡已有的譯法不同，就把這批譯文裡的說法換成已有的。

分段並行時幾段同時開譯，各段第一批看不到別段的術語表，同一個詞可能各譯各的；
術語表按“先並進去的為準”，後並進來的那批在這裡改成同一個說法，讀起來全文一致。
只換這批自己報出來的衝突術語，只在原文確實出現這個英文術語的塊裡換，不動原文和 $公式$；
這個說法在這段出現的次數要和英文術語出現的次數一樣才換（“標準偏差”裡的“偏差”不是 bias）；表格單元格只換整格就是這個說法的。
"""
from __future__ import annotations

import re

_MATH = re.compile(r"(\$[^$]*\$)")
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")  # i18n-ok


def _key(en) -> str:
    return " ".join(str(en or "").lower().split())


def conflicts(glossary: list[dict], new: list[dict]) -> list[tuple[str, str, str]]:
    """[(英文, 這批的譯法, 已有譯法)]。太短的譯法不換，免得誤傷別的詞：一個字的不換；
    是已有譯法一部分的（“標準誤”和“標準誤差”），三個字以上才換；帶括號註釋的不換。"""
    have = {_key(g.get("en")): str(g.get("zh") or "").strip() for g in glossary or [] if isinstance(g, dict)}
    out = []
    for g in new or []:
        if not isinstance(g, dict):
            continue
        old, mine = have.get(_key(g.get("en"))), str(g.get("zh") or "").strip()
        if any(c in s for s in (old or "", mine) for c in "（()）"):  # i18n-ok
            continue  # “Unlikelihood（非似然訓練）”這種帶註釋的寫法拿來替換正文會到處重複註釋，不換
        if old and mine and old != mine and len(mine) >= (3 if mine in old else 2):
            out.append((str(g.get("en")), mine, old))
    return out


def _swap_plain(text: str, mine: str, old: str, keep: list[str]) -> str:
    """keep：包含 mine 的其他已知譯法（“協方差”裡的“方差”、“標準誤差”裡的“標準誤”），先護住再換。"""
    marks = {}
    for i, k in enumerate(sorted(keep, key=len, reverse=True)):
        if k in text:
            m = f"\x00{i}\x01"
            marks[m] = k
            text = text.replace(k, m)
    if _CJK.search(mine):
        text = text.replace(mine, old)
    else:  # 拉丁字母的譯法只換整詞，不換詞的一部分
        text = re.sub(r"(?<!\w)" + re.escape(mine) + r"(?!\w)", lambda _: old, text)
    for m, k in marks.items():
        text = text.replace(m, k)
    return text


def occurrences(text: str, word: str, keep=()) -> int:
    """word 在公式外出現幾次；keep 裡包含它的說法（“標準偏差”裡的“偏差”）不算。拉丁文字按整詞數。"""
    rest = " ".join(_MATH.split(text)[0::2])
    for k in sorted({k for k in keep if word in k and k != word}, key=len, reverse=True):
        rest = rest.replace(k, "")
    if _CJK.search(word):
        return rest.count(word)
    return len(re.findall(r"(?<!\w)" + re.escape(word) + r"(?!\w)", rest))


def mentions_count(en_text: str, en: str) -> int:
    return len(re.findall(r"(?<!\w)" + re.escape(en) + r"(s|es)?(?!\w)", en_text or "", re.I))


def _fit(text: str, swaps, en_text: str):
    """只留這段裡能安全替換的：說法出現的次數和英文術語出現的次數一樣。
    對不上說明這個說法在這段還有別的意思（“偏差”也出現在 standard deviation 的“標準偏差”裡），不換。"""
    return [(mine, old, keep) for en, mine, old, keep in swaps
            if occurrences(text, mine, keep) == mentions_count(en_text, en) > 0]


def _swap(text: str, swaps) -> str:
    parts = _MATH.split(text)  # 奇數位是 $公式$，不碰
    for i in range(0, len(parts), 2):
        for mine, old, keep in swaps:
            parts[i] = _swap_plain(parts[i], mine, old, keep)
    return "".join(parts)




def _mentions(en_text: str, en: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(en) + r"(s|es)?(?!\w)", en_text or "", re.I))


def _block_en(b: dict) -> str:
    items = " ".join(str(it.get("en") or "") for it in b.get("items") or [] if isinstance(it, dict))
    return " ".join([*(str(b.get(k) or "") for k in ("en", "caption_en", "image_en")), items, str(b.get("head") or ""), str(b.get("rows") or "")])


def unify(glossary: list[dict], data: dict, en_of: dict | None = None) -> list[tuple[str, str, str]]:
    """就地改 data（模型的一批輸出：blocks，或閱讀原文補譯時的 zh 字典），回傳換了哪些。
    en_of：補譯時 {鍵: 英文}，用來判斷這個鍵的原文裡有沒有這個術語。"""
    found = conflicts(glossary, data.get("glossary") or [])
    if not found:
        return []
    known = {str(g.get("zh") or "") for g in list(glossary or []) + list(data.get("glossary") or []) if isinstance(g, dict)}

    def swaps_for(en_text: str):
        # 已有譯法包含 mine 時（“標準誤差”含“標準誤”）old 本身也要護住，免得換成“標準誤差差”
        return [(en, mine, old, [k for k in known | {old} if mine in k and k != mine])
                for en, mine, old in found if _mentions(en_text, en)]

    def fix(value, swaps, en_text):
        if isinstance(value, str):
            ok = _fit(value, swaps, en_text)
            return _swap(value, ok) if ok else value
        return value

    def cells(value, swaps):
        """表格單元格對不上英文：只換整格就是這個說法的（表頭裡的“誤差棒”）。"""
        if isinstance(value, list):
            return [cells(v, swaps) for v in value]
        if isinstance(value, str):
            return next((old for _, mine, old, _ in swaps if value.strip() == mine), value)
        return value

    for b in data.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        swaps = swaps_for(_block_en(b))
        if not swaps:
            continue
        # 每個欄位按自己的英文數次數：段落看 en，題注看 caption_en，清單項看各自的 en
        for f, src in (("zh", "en"), ("caption_zh", "caption_en"), ("image_zh", "image_en")):
            if isinstance(b.get(f), str):
                b[f] = fix(b[f], swaps, str(b.get(src) or ""))
        for it in b.get("items") or []:
            if isinstance(it, dict) and isinstance(it.get("zh"), str):
                it["zh"] = fix(it["zh"], swaps, str(it.get("en") or ""))
        if b.get("type") == "table":
            for f in ("head", "rows"):
                if isinstance(b.get(f), list):
                    b[f] = cells(b[f], swaps)
    if isinstance(data.get("zh"), dict):
        for k, v in data["zh"].items():
            en_text = str((en_of or {}).get(k) or "")
            swaps = swaps_for(en_text)
            if swaps:
                data["zh"][k] = fix(v, swaps, en_text) if isinstance(v, str) else cells(v, swaps)
    # 術語表裡只留已有的那條，這批的衝突條目丟掉（merge 本來也會丟，這裡顯式一點）
    bad = {_key(en) for en, _, _ in found}
    data["glossary"] = [g for g in data.get("glossary") or [] if not (isinstance(g, dict) and _key(g.get("en")) in bad)]
    return found
