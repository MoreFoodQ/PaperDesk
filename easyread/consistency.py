"""全文譯完後的術語一致性檢查：同一個英文術語在譯文裡用了不同說法時，定一個說法，把其餘的統一過來。

合併時的統一（terms.unify）只管模型自己報進術語表的衝突；這裡看全文實際的譯文。
程式先篩出“原文有這個術語、譯文裡卻沒有術語表譯法”的段落（沒有就不調模型），連同術語表譯法在全文用了幾段，
一起發給模型（只看文字不看圖）。模型只做判斷：每個術語全文用哪個說法（use，按多數用法和領域通行說法，
不一定是先登記的那個），以及每段裡哪個說法是這個術語的另一種譯法（from）。
改文字由程式做，不讓模型重寫段落：只把 from 換成 use，而且只在這段裡 from 出現的次數和英文術語出現的次數一樣時才換
（對不上說明這個說法還有別的意思，比如“標準偏差”裡的“偏差”），公式裡不換，包含它的其他術語譯法先護住。
定下的譯法和術語表不同時，術語表改過來，全文原來用術語表譯法的段落按同樣的規則換掉。
塊 id 不變，筆記維持關聯；使用者改過的譯文不動；句子對齊跟著挪；每處改動記進 job.log。
"""
from __future__ import annotations

import difflib
import re

from . import engines, langs, prompts, sentences
from .i18n import tr
from .terms import _MATH, _mentions, _swap, mentions_count, occurrences

LIMIT = 60          # 一次最多檢查幾段
_PAREN = re.compile(r"[（(].*?[）)]")  # i18n-ok


def _fields(b: dict):
    """(鍵, 英文, 譯文)：鍵同頁面上的寫法（塊 id、id#序號、id#caption）。"""
    t = b.get("type")
    if t in ("para", "heading"):
        yield b["id"], str(b.get("en") or ""), str(b.get("zh") or "")
    elif t == "list":
        for i, it in enumerate(b.get("items") or []):
            if isinstance(it, dict):
                yield f"{b['id']}#{i}", str(it.get("en") or ""), str(it.get("zh") or "")
    elif t in ("table", "figure"):
        yield f"{b['id']}#caption", str(b.get("caption_en") or ""), str(b.get("caption_zh") or "")


def _plain(zh: str) -> str:
    return " ".join(_MATH.split(zh)[0::2])  # 公式外的文字


def _has(zh: str, want: str) -> bool:
    return want.lower() in _plain(zh).lower()


def _clean(zh) -> str:
    return _PAREN.sub("", str(zh or "")).strip()


def _rules(paper: dict) -> list[tuple[str, str]]:
    out = []
    for g in paper.get("glossary") or []:
        if isinstance(g, dict):
            en, want = str(g.get("en") or "").strip(), _clean(g.get("zh"))
            if len(en) >= 3 and len(want) >= 2 and want.lower() != en.lower():
                out.append((en, want))
    return out


def _skip(key: str, edited: set[str]) -> bool:
    return key in edited or key.partition("#")[0] in edited


def suspects(paper: dict, edited: set[str], pages: set[int] | None = None) -> tuple[list[dict], dict[str, int]]:
    """（可疑的地方 [{key, page, en, zh, terms: [{en, want}]}]，{術語: 全文用了術語表譯法的段數}）。
    pages：可疑的地方只找這些頁；用了幾段按全文算。"""
    rules = _rules(paper)
    out, agree = [], {}
    for b in paper.get("blocks") or []:
        for key, en, zh in _fields(b):
            if not zh or _skip(key, edited):
                continue
            miss = []
            for t, w in rules:
                if _mentions(en, t):
                    if _has(zh, w):
                        agree[t] = agree.get(t, 0) + 1
                    else:
                        miss.append({"en": t, "want": w})
            if miss and (pages is None or b.get("page") in pages):
                out.append({"key": key, "page": b.get("page"), "en": en, "zh": zh, "terms": miss})
    return out[:LIMIT], agree


def swap(zh: str, en_text: str, term: str, old: str, use: str, keep: list[str]) -> str | None:
    """把這段裡的 old 換成 use。old 在公式外出現的次數（去掉護住的說法後）要和英文術語出現的次數一樣，否則不換，回傳 None。"""
    if not old or old == use or len(old) > 3 * max(2, len(use)):
        return None
    guard = sorted({k for k in keep + [use] if old in k and k != old}, key=len, reverse=True)
    n = occurrences(zh, old, guard)
    if n == 0 or n != mentions_count(en_text, term):
        return None
    new = _swap(zh, [(old, use, guard)])
    if _doubled(new, use) and not _doubled(zh, use):  # “監督微調（SFT）”換成 SFT 會變成“SFT（SFT）”
        return None
    return new if new != zh else None


def _doubled(text: str, use: str) -> bool:
    return bool(re.search(re.escape(use) + r"\s*[（(]\s*" + re.escape(use) + r"\s*[)）]", text))  # i18n-ok 全角括號


def resent(obj: dict | None, old: str, new: str) -> list | None:
    """譯文只換了術語：把句子對齊（sents，UTF-16 位置）跟著挪過去。句界落在改動裡面就放棄，頁面按整段對應。"""
    if not obj or not sentences.valid(obj):
        return None
    to16 = [0]
    for c in old:
        to16.append(to16[-1] + sentences.u16(c))
    py = {v: i for i, v in enumerate(to16)}
    ops = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()

    def move(p16):
        p = py.get(p16)
        for tag, i1, i2, j1, j2 in ops if p is not None else ():
            if tag == "equal" and i1 <= p <= i2:
                return sentences.u16(new[:p - i1 + j1])
        return None

    out = []
    for en_end, zh_end in obj["sents"][:-1]:
        z = move(zh_end)
        if z is None:
            return None
        out.append([en_end, z])
    return out + [[obj["sents"][-1][0], sentences.u16(new)]]


def _rewrite(ws, changes: dict[str, tuple[str, str]], edited: set[str]) -> list[str]:
    """一次寫入裡把 {鍵: (舊譯文, 新譯文)} 改好：這段在檢查期間被改過（重譯、使用者改譯文）就跳過。回傳改成了的鍵。"""
    done = []

    def apply(paper):
        for b in paper.get("blocks") or []:
            for key, _, zh in _fields(b):
                if key not in changes or _skip(key, edited) or changes[key][0] != zh:
                    continue
                new = changes[key][1]
                field = key.partition("#")[2]
                if field == "caption":
                    b["caption_zh"] = new
                    continue
                obj = b["items"][int(field)] if field.isdigit() else b
                s = resent(obj, zh, new)
                obj["zh"] = new
                if s:
                    obj["sents"] = s
                else:
                    obj.pop("sents", None)
                done.append(key)
    ws.update("paper", apply)
    return done


def check(ws, cfg: dict, pages: list[int], cancel, meter, journal, lock) -> int:
    """跑一遍檢查並改好，回傳改了幾段。lock：翻譯用的合併鎖。pages 不是全文時只改這些頁，術語表不動。"""
    def edited_now() -> set[str]:
        reader = ws.load("reader") or {}
        return {k for k, v in (reader.get("edits") or {}).items() if isinstance(v, dict) and v.get("zh")}

    paper = ws.load("paper")
    in_job = set(pages)
    items, agree = suspects(paper, edited_now(), in_job)
    whole = in_job >= {b.get("page") for b in paper.get("blocks") or [] if b.get("page")}
    if not items:
        journal(ws, tr("术语一致性检查：没有发现不一致"))
        return 0
    name = langs.prompt_name(langs.of_paper(paper.get("meta")))
    data = engines.parse_json(engines.run(cfg, prompts.consistency(items, agree, name), ws.root, None, cancel, meter))
    data = data if isinstance(data, dict) else {}
    asked = {t["en"]: t["want"] for it in items for t in it["terms"]}
    use = {en: _clean(v) for en, v in (data.get("use") or {}).items() if en in asked and len(_clean(v)) >= 2}
    # 統一成純英文縮寫（supervised fine-tuning → SFT）不算譯法，不換；保留原詞（Transformer）的照常
    use = {en: u for en, u in use.items() if not (u.isascii() and u.lower() != en.lower() and not asked[en].isascii())}
    by_key = {it["key"]: it for it in items}
    with lock:
        paper = ws.load("paper")
        edited = edited_now()
        keep = [_clean(g.get("zh")) for g in paper.get("glossary") or [] if isinstance(g, dict)]
        changes, why = {}, {}
        texts = {key: (en, zh) for b in paper.get("blocks") or [] for key, en, zh in _fields(b)}
        # 定下的說法和術語表不同：全文（只譯了一部分時不動術語表，只改這次的頁）原來用術語表說法的段落換過來
        for en, u in use.items():
            old = asked[en]
            if u == old:
                continue
            for b in paper.get("blocks") or []:
                if not whole and b.get("page") not in in_job:
                    continue
                for key, en_text, zh in _fields(b):
                    cur = changes.get(key, (zh, zh))[1]
                    if _mentions(en_text, en) and _has(cur, old) and not _skip(key, edited):
                        new = swap(cur, en_text, en, old, u, keep)
                        if new:
                            changes[key] = (zh, new)
                            why.setdefault(key, []).append(f"{old} → {u}")
        for f in data.get("fixes") or []:
            it = by_key.get(str(f.get("key"))) if isinstance(f, dict) else None
            term = str(f.get("term") or "") if it else ""
            if not it or term not in {t["en"] for t in it["terms"]}:
                continue
            u = use.get(term, asked[term])
            src = str(f.get("from") or "").strip()
            en_text, zh = texts.get(it["key"], ("", None))
            if zh != it["zh"]:
                continue  # 檢查期間這段被重譯了
            cur = changes.get(it["key"], (zh, zh))[1]
            new = swap(cur, en_text, term, src, u, keep) if src in cur else None
            if new:
                changes[it["key"]] = (zh, new)
                why.setdefault(it["key"], []).append(f"{src} → {u}")
        done = _rewrite(ws, changes, edited) if changes else []
        if whole:
            renamed = {en: u for en, u in use.items() if u != asked[en]}

            def regloss(p):
                for g in p.get("glossary") or []:
                    if isinstance(g, dict) and str(g.get("en") or "").strip() in renamed:
                        g["zh"] = renamed[str(g["en"]).strip()]
            ws.update("paper", regloss)
    page_of = {key: b.get("page") for b in paper.get("blocks") or [] for key, _, _ in _fields(b)}
    for key in done:
        journal(ws, tr("术语一致性：第 {page} 页 {key} {what}", page=page_of.get(key), key=key, what="、".join(why[key])))  # i18n-ok 頓號
    journal(ws, tr("术语一致性检查：查了 {n} 段，改了 {m} 段", n=len(items), m=len(done)))
    return len(done)
