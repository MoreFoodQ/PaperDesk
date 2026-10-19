"""句子級對齊：模型在 para / list 每一項的 en 和 zh 裡，於兩邊都斷句的地方各插一個 ‖，個數相同。
並進 paper.json 前把 ‖ 去掉，記成 sents：[[英文句尾, 譯文句尾], …]，按 UTF-16 計（頁面上 JS 直接切），
最後一項就是兩邊的總長，頁面拿它核對文字沒被改過。對不上（個數不同、有空句）就不記，頁面按整段對應。

閱讀原文之後補譯時，英文已經定了：程式先按句號切好、插上 ‖ 發給模型，譯文照著插（mark_en）。"""
from __future__ import annotations

import re

MARK = "‖"
_MATH = re.compile(r"\$\$.+?\$\$|(?<!\\)\$(?:\\\$|[^$])+?(?<!\\)\$", re.S)
# 句號後面跟著這些縮寫不算斷句（Fig. 3、et al. (2020)、e.g. the …）
_ABBR = {"e.g", "i.e", "al", "fig", "figs", "eq", "eqs", "sec", "secs", "tab", "ref", "refs", "vs", "cf", "etc", "resp",
         "approx", "no", "dr", "mr", "ms", "prof", "st", "app", "ch", "thm", "lem", "def", "prop", "cor", "viz", "ca"}


def u16(s: str) -> int:
    """JS 字串長度（UTF-16 碼元）：數學斜體這類補充平面字符算 2。"""
    return len(s.encode("utf-16-le")) // 2


def _wide(c: str) -> bool:
    """中日文字和全角標點：兩句之間不加空白。韓文句間要空白，不算。"""
    o = ord(c)
    return o >= 0x2E80 and not (0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F)


# 句界 ‖ 前面通常是句末或分句標點；原文本來就有的 ‖（範數 ‖w‖ 寫在公式外）前後貼著字母，不當句界
_BEFORE = set("‖.?!:;,)]\"'”’。？！：；，、）】」』")  # i18n-ok 標點表


def _pieces(text: str) -> list[str]:
    """按句界 ‖ 切開：公式外、前面是標點或兩邊都是空白的才算；公式裡的和貼著字母的是範數符號，不動。"""
    out, last = [], 0
    spans = [m.span() for m in _MATH.finditer(text)]
    for i, c in enumerate(text):
        if c != MARK or any(a <= i < b for a, b in spans):
            continue
        before, after = text[:i].rstrip(), text[i + 1:i + 2]
        spaced = i > 0 and text[i - 1].isspace() and (not after or after.isspace())
        if (before and (before[-1] in _BEFORE or before.endswith("$"))) or spaced:
            out.append(text[last:i])
            last = i + 1
    out.append(text[last:])
    return out


def unmark(text: str) -> tuple[str, list[int] | None]:
    """去掉 ‖，回傳（乾淨的文字，除最後一句外每句的句尾位置）。沒有 ‖ 回傳 None；有空句也回傳 None（不算對齊）。"""
    if not isinstance(text, str) or MARK not in text:
        return text, None
    parts = _pieces(text)
    if len(parts) == 1:
        return text, None
    last = len(parts) - 1
    out, ends, empty = "", [], False
    for i, p in enumerate(parts):
        p = p.rstrip() if i == 0 else p.lstrip() if i == last else p.strip()
        if not p:
            empty = True
            continue
        if out:
            ends.append(u16(out))
            if not (_wide(out[-1]) or _wide(p[0])):
                out += " "  # 西文兩句之間留一個空白，空白算下一句的開頭
        out += p
    return out, None if empty or not ends else ends


def _pair(en: str, zh: str):
    """回傳（乾淨的 en、乾淨的 zh、sents 或 None）。"""
    en2, ee = unmark(en)
    zh2, ze = unmark(zh)
    if ee and ze and len(ee) == len(ze):
        return en2, zh2, [[a, b] for a, b in zip(ee, ze)] + [[u16(en2), u16(zh2)]]
    return en2, zh2, None


def _apply(obj: dict) -> None:
    en, zh, s = _pair(obj.get("en") or "", obj.get("zh") or "")
    if isinstance(obj.get("en"), str):
        obj["en"] = en
    if isinstance(obj.get("zh"), str):
        obj["zh"] = zh
    if s and obj.get("en") and obj.get("zh"):
        obj["sents"] = s
    else:
        obj.pop("sents", None)


def attach(blocks: list) -> None:
    """就地處理一批塊：para 和 list 每一項記 sents，其他文字裡誤插的 ‖ 也去掉。並進 paper.json 前調。"""
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "para":
            _apply(b)
        elif b.get("type") == "list":
            for it in b.get("items") or []:
                if isinstance(it, dict):
                    _apply(it)
        for f in ("en", "zh", "caption_en", "caption_zh", "image_en", "image_zh"):
            if b.get("type") != "para" and isinstance(b.get(f), str):
                b[f] = unmark(b[f])[0]


def strip(text) -> str:
    return unmark(text)[0] if isinstance(text, str) else text


def valid(obj: dict) -> bool:
    """sents 還對得上這塊的文字（譯文被重譯、術語替換改過就對不上了）。"""
    s = obj.get("sents")
    if not isinstance(s, list) or len(s) < 2 or not all(isinstance(x, list) and len(x) == 2 for x in s):
        return False
    if s[-1] != [u16(obj.get("en") or ""), u16(obj.get("zh") or "")]:
        return False
    return all(s[i][0] < s[i + 1][0] and s[i][1] < s[i + 1][1] for i in range(len(s) - 1)) and s[0][0] > 0 and s[0][1] > 0


# ---------- 英文已經定了：程式切句（補譯、重譯一段時用） ----------
_END = re.compile(r"[.?!][\"'”’)\]]*(?=\s+[\"'“(\[$A-Z0-9])")


def split_en(text: str) -> list[int]:
    """英文按句切，回傳除最後一句外每句的句尾（Python 下標，不含後面的空白）。公式裡、縮寫和人名首字母后不切。"""
    if not text:
        return []
    math = [m.span() for m in _MATH.finditer(text)]
    ends = []
    for m in _END.finditer(text):
        i = m.start()
        if any(a <= i < b for a, b in math):
            continue
        word = re.search(r"([A-Za-z.]+)$", text[:i])
        w = (word.group(1) if word else "").lower().strip(".")
        if w in _ABBR or (word and len(word.group(1)) == 1 and word.group(1).isupper()):
            continue  # Fig. 3 / et al. / J. Smith
        if re.search(r"\d$", text[:i]) and re.match(r"\s*\d", text[m.end():]):
            continue  # 3. 5 這種小數被斷行拆開
        ends.append(m.end())
    return [e for e in ends if text[e:].strip()]


def mark_en(text: str, sents=None) -> tuple[str, list[int]]:
    """給英文插上 ‖ 發給模型，回傳（帶 ‖ 的英文，除最後一句外每句的 UTF-16 句尾）。有 sents 就照它切，沒有就程式切。"""
    if sents:
        cuts, pos16, i = [], {}, 0
        for k in range(len(text) + 1):  # UTF-16 位置 → Python 下標
            pos16[i] = k
            if k < len(text):
                i += u16(text[k])
        cuts = [pos16[e] for e, _ in sents[:-1] if e in pos16]
    else:
        cuts = split_en(text)
    out, last = "", 0
    for c in cuts:
        out += text[last:c].rstrip() + " " + MARK + " "
        last = c
        while last < len(text) and text[last].isspace():
            last += 1
    out += text[last:]
    return out, [u16(text[:c].rstrip()) for c in cuts]


def zh_sents(en: str, en_ends: list[int], zh_marked: str):
    """英文是程式切的，模型照著在譯文裡插 ‖：回傳（乾淨的譯文、sents 或 None）。"""
    zh, ze = unmark(zh_marked)
    if en_ends and ze and len(ze) == len(en_ends):
        return zh, [[a, b] for a, b in zip(en_ends, ze)] + [[u16(en), u16(zh)]]
    return zh, None


def mark_items(blocks: list[dict], items: dict) -> tuple[dict, dict]:
    """補譯前給段落和清單項的英文插 ‖：回傳（發給模型的 {鍵: 英文}，{鍵: (英文, 句尾)}）。只有一句的不插。"""
    by_id = {b.get("id"): b for b in blocks}
    out, ends = dict(items), {}
    for key, en in items.items():
        bid, _, field = key.partition("#")
        t = (by_id.get(bid) or {}).get("type")
        if isinstance(en, str) and ((t == "para" and not field) or (t == "list" and field.isdigit())):
            marked, e = mark_en(en)
            if e:
                out[key], ends[key] = marked, (en, e)
    return out, ends


def unmark_fill(zh: dict, ends: dict) -> dict:
    """補譯的輸出：就地去掉 ‖，回傳 {鍵: sents}（個數對不上的鍵不在裡面）。"""
    got = {}
    for key, v in list(zh.items()):
        if not isinstance(v, str):
            continue
        if key in ends:
            zh[key], s = zh_sents(ends[key][0], ends[key][1], v)
            if s:
                got[key] = s
        else:
            zh[key] = strip(v)
    return got
