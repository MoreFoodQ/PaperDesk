"""背景翻譯：一批幾頁交給模型，驗證後並進 paper.json。每批寫入磁碟，中斷了下次接著譯。

一批失敗會重試；還是失敗就記下來跳過，接著譯後面的頁，最後在頁面上給“重試失敗的頁”。
"""
from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor

from . import config, consistency, engines, figure_translation, front_context, langs, netcheck, pdfwork, prompts, prompts_en, segments, sentences, sources, terms
from .checks import block_problems, tex_problems
from .figures import normalize_figure, prepare_figures
from .i18n import tr
from .log import log
from .paperdata import add_discussion, fill_zh, merge_blocks, set_block_text
from .store import Workspace, now_iso

_merge_lock = threading.Lock()  # 併發翻譯時，併入 paper.json 和重算原頁定位一次只做一個
# 用量到頂、餘額不足這類錯誤，後面的批次也一定失敗：直接停，剩下的頁記為沒譯，等額度恢復後一鍵重試
_QUOTA = re.compile(r"session limit|usage limit|rate limit reached|insufficient_quota|余额不足|额度|接口返回 40[12]|insufficient balance|API returned 40[12]", re.I)  # i18n-ok
_REF_LINE = re.compile(r"^\s*(\d+\.?\s*)?(references|bibliography|参考文献)\s*$", re.I | re.M)  # i18n-ok


def prepare(ws: Workspace) -> None:
    pages = pdfwork.prepare(ws.root)
    extra = {}
    try:  # 本機拖進來的 PDF：從第一頁的 arXiv 編號或 DOI 補上作者、年份、出處
        first = ws.root / "extract" / "page-001.txt"
        if first.exists() and config.load().get('metadata_lookup') is True:
            extra = sources.enrich(first.read_text(encoding="utf-8", errors="replace"), ws.load("paper").get("meta", {}))
    except Exception:  # noqa: BLE001
        log.exception("补元数据失败 %s", ws.id)

    def apply(paper):
        meta = paper.setdefault("meta", {})
        meta.update({"pages": pages, "page_count": len(pages)})
        for k, v in extra.items():
            if not meta.get(k) or (k == "title_en" and meta.get(k) == meta.get("source", "").removesuffix(".pdf")):
                meta[k] = v
    ws.update("paper", apply)


def references_page(ws: Workspace) -> int | None:
    """參考文獻從哪一頁開始（找單獨成行的 References 標題）。找不到回傳 None。"""
    n = ws.load("paper").get("meta", {}).get("page_count") or 0
    for p in range(2, n + 1):
        f = ws.root / "extract" / f"page-{p:03d}.txt"
        if f.exists() and _REF_LINE.search(f.read_text(encoding="utf-8", errors="replace")):
            return p
    return None


def scope_pages(ws: Workspace, scope: str | None) -> list[int] | None:
    """翻譯範圍：all 全文；body 到參考文獻那頁為止；range:A-B 第 A 到 B 頁；first:N 前 N 頁（舊寫法）。回傳 None 表示全文。"""
    n = ws.load("paper").get("meta", {}).get("page_count") or 0
    if scope == "body":
        ref = references_page(ws)
        return list(range(1, ref + 1)) if ref else None
    if scope and scope.startswith("range:"):
        a, _, b = scope.split(":", 1)[1].partition("-")
        start, end = sorted((int(a or 1), int(b or n)))
        lo, hi = max(1, start), min(n, end)
        if lo > hi:
            raise ValueError(tr("指定页码超出了论文范围（共 {n} 页）", n=n))
        return list(range(lo, hi + 1))
    if scope and scope.startswith("first:"):
        k = int(scope.split(":", 1)[1] or 0)
        return list(range(1, min(n, k) + 1)) if k > 0 else None
    return None


def _next_head(ws: Workspace, n: int, whole: bool = False) -> str:
    """下一頁開頭的抽取文字。whole：整頁都給（不能看圖的引擎在分段交界處，續文可能排在表格、圖注後面）。"""
    p = ws.root / "extract" / f"page-{n:03d}.txt"
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    return text if whole else text[:1500]


def _normalize(data: dict, pages: list[int], taken: set[str]) -> dict:
    """補頁碼、去掉和已有塊衝突的 id、丟掉明顯無效的塊。"""
    if isinstance(data, list):
        data = {"blocks": data}
    blocks = []
    for b in data.get("blocks") or []:
        if not isinstance(b, dict) or b.get("type") not in {'heading', 'para', 'list', 'math', 'table', 'figure', 'references', 'note'}:
            continue
        b.setdefault("page", pages[0])
        try:
            b["page"] = int(b["page"])
        except (TypeError, ValueError):
            b["page"] = pages[0]
        bid = re.sub(r"[^A-Za-z0-9_\-]", "-", str(b.get("id") or f"p{b['page']}-{len(blocks) + 1}"))
        base, k = bid, 2
        while bid in taken:
            bid = f"{base}-{k}"
            k += 1
        taken.add(bid)
        b["id"] = bid
        if b['type'] == 'heading':
            b['level'] = b.get('level') if type(b.get('level')) is int and 1 <= b['level'] <= 6 else 1
        if b["type"] == "figure":
            b['src'] = ''  # Model output cannot name files; prepare_figures generates assets.
            normalize_figure(b)  # 截圖要等合併鎖裡 id 最終去重之後，見 prepare_figures
        blocks.append(b)
    data["blocks"] = blocks
    return data


def _taken(ws: Workspace, batch: list[int]) -> set[str]:
    return {b["id"] for b in ws.load("paper").get("blocks", []) if b.get("page") not in batch}


def _problems(data: dict) -> list[str]:
    problems, tex = block_problems(data["blocks"])
    return problems + tex_problems(tex)


def journal(ws: Workspace, line: str) -> None:
    """每篇論文自己的翻譯記錄 job.log，頁面上“檢視記錄”看的就是它。"""
    with open(ws.root / "job.log", "a", encoding="utf-8") as f:
        f.write(f"{now_iso()[:19].replace('T', ' ')}  {line}\n")


def _fill_batch(ws: Workspace, cfg: dict, batch: list[int], cancel, say, meter=None) -> None:
    """閱讀原文整理過的頁：不重排，只給已有的塊補譯文。漏譯的鍵拋錯，重試時只譯剩下的。"""
    blocks = [b for b in ws.load("paper").get("blocks", []) if b.get("page") in batch]
    images_enabled = figure_translation.enabled(cfg)
    items = prompts_en.todo(blocks, translate_images=images_enabled)
    figure_only = set(cfg.get("_figure_fill_pages", ()))
    # Keep metadata/check updates from ordinary fills away from completed pages.
    if set(batch) & figure_only and set(batch) - figure_only:
        _fill_batch(ws, cfg, [n for n in batch if n not in figure_only], cancel, say, meter)
        _fill_batch(ws, cfg, [n for n in batch if n in figure_only], cancel, say, meter)
        return
    by_id = {b["id"]: b for b in blocks}
    items = {key: value for key, value in items.items()
             if by_id[key.partition("#")[0]].get("page") not in figure_only or key.endswith("#image")}
    if not items:
        fill_zh(ws, {}, batch, set())
        _mark_figure_policy(ws, cfg, batch)
        return
    marked, ends = sentences.mark_items(blocks, items)  # 英文先按句插好 ‖，譯文照著插，記句子對齊
    text = engines.run(cfg, prompts_en.fill(ws, batch, marked), ws.root, None, cancel, meter)
    data = engines.parse_json(text)
    if not isinstance(data, dict) or not isinstance(data.get("zh"), dict):
        raise engines.EngineError(tr("模型输出的格式不对（缺 zh）"))
    data["zh"] = {k: v for k, v in data["zh"].items() if k in items}
    fake = [{"id": k, "type": "para", "zh": v} for k, v in data["zh"].items() if isinstance(v, str)]
    problems = _problems({"blocks": fake})
    if problems:
        say(tr("第 {page} 页起有 {n} 处公式或格式问题，正在让模型修正", page=batch[0], n=len(problems)))
        try:
            fixed = engines.parse_json(engines.run(cfg, prompts.repair(prompts.dump(data), problems), ws.root, None, cancel, meter))
            if isinstance(fixed, dict) and isinstance(fixed.get("zh"), dict) and len(fixed["zh"]) >= len(data["zh"]):
                data = fixed
        except engines.EngineError as e:
            journal(ws, tr("第 {pages} 页修正失败，保留原译：{err}", pages=batch, err=e))
    if set(batch) <= figure_only:
        data = {"zh": data["zh"]}
    with _merge_lock:
        _unify_terms(ws, data, batch, {k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in items.items()})
        missing = fill_zh(ws, data, batch, set(items), sentences.unmark_fill(data["zh"], ends))
        _mark_figure_policy(ws, cfg, batch)
        # A figure-only fill must not replace existing review/check entries.
        if not set(batch) <= figure_only:
            _save_checks(ws, data.get("checks"), batch)
    if missing:
        raise engines.EngineError(tr("漏译了 {n} 处（{ids}）", n=len(missing), ids=", ".join(missing[:5])))


def _mark_figure_policy(ws: Workspace, cfg: dict, batch: list[int]) -> None:
    def apply(paper):
        blocks = [b for b in paper.get("blocks", []) if b.get("page") in batch]
        if not figure_translation.enabled(cfg):
            figure_translation.apply(blocks, blocks, False)
        else:
            for block in blocks:
                if block.get("image_zh"):
                    block.pop("image_translation_skipped", None)
    ws.update("paper", apply)


def _one_batch(ws: Workspace, cfg: dict, batch: list[int], total_pages: int, cancel, say, meter=None, read=False,
               skip_head=False, peek=(), front=False) -> None:
    """read：閱讀原文，整理成塊但不翻譯。skip_head：上一頁由另一段同時在譯，頁首續文歸它。
    peek：分段交界處順便看一眼的相鄰頁（見 prompts.peek_note）。front：帶上前文參考（每段第一批，見 front_context）。"""
    mode = engines.image_mode(cfg)
    images = [pdfwork.engine_image(ws.root, n) for n in sorted({*batch, *peek})] if mode != "text" else []
    nxt = batch[-1] + 1
    # 分段交界、引擎不能看圖：前一段最後一批拿下一頁全文補完跨頁那段（後一段第一批會跳過頁首續文，這裡補不全就丟了）
    head = _next_head(ws, nxt, whole=mode == "text" and nxt in peek) if nxt <= total_pages else ""
    if read:
        prompt = prompts_en.structure(ws, batch, mode, head, skip_head, peek)
    else:
        prompt = prompts.translate(ws, batch, mode, head, skip_head, peek, front_context.build(ws.root, batch[0]) if front else "")
    meta = ws.load('paper').get('meta', {})
    if meta.get('format') == 'epub':
        # EPUB pages are locally generated. Keep the existing schema and page IDs.
        language = str(meta.get('source_language', ''))[:40]
        prompt = (f"Source format: EPUB, declared language: {language}. "
                  "These pages are repaginated reading pages, not original book page numbers. "
                  "The en fields store the original text in its actual language; never convert it to English. "
                  "In original-only mode preserve the original language. In translation mode use the configured target.\n\n") + prompt
    if not read and not figure_translation.enabled(cfg):
        prompt += "\n\n" + figure_translation.SKIP_INSTRUCTION
    text = engines.run(cfg, prompt, ws.root, images, cancel, meter)
    try:
        data = engines.parse_json(text)
    except engines.EngineError:
        (ws.root / "extract" / f"failed-{batch[0]:03d}.txt").write_text(text, encoding="utf-8")
        raise
    data = _normalize(data, batch, _taken(ws, batch))
    figure_translation.apply(data["blocks"], ws.load("paper").get("blocks", []),
                             read or figure_translation.enabled(cfg))
    problems = _problems(data)
    if problems:  # 給一次修的機會
        say(tr("第 {page} 页起有 {n} 处公式或格式问题，正在让模型修正", page=batch[0], n=len(problems)))
        try:
            fixed = engines.parse_json(engines.run(cfg, prompts.repair(prompts.dump(data), problems), ws.root, None, cancel, meter))
            fixed = _normalize(fixed, batch, _taken(ws, batch))
            figure_translation.apply(fixed["blocks"], ws.load("paper").get("blocks", []),
                                     read or figure_translation.enabled(cfg))
            if fixed["blocks"] and len(_problems(fixed)) < len(problems):
                data = fixed
        except engines.EngineError as e:
            journal(ws, tr("第 {pages} 页修正失败，保留原译：{err}", pages=batch, err=e))
    if not data["blocks"] and not data.get("references"):  # 整頁都是參考文獻時只有 references，沒有新塊，也算譯完
        raise engines.EngineError(tr("模型没有整理出任何内容") if read else tr("模型没有译出任何内容"))
    with _merge_lock:
        data = _normalize(data, batch, _taken(ws, batch))  # 併發時別的批可能剛佔用了同名 id
        figure_translation.apply(data["blocks"], ws.load("paper").get("blocks", []),
                                 read or figure_translation.enabled(cfg))
        prepare_figures(ws.root, data["blocks"], total_pages)
        _unify_terms(ws, data, batch)
        drop = _one_references(ws, data, batch)
        merge_blocks(ws, data, done=batch, replace_pages=batch, en_only=read, drop_ids=drop)
        _save_checks(ws, data.get("checks"), batch)
        try:
            pdfwork.locate(ws.root)
        except Exception:  # noqa: BLE001 —— 定位失敗不影響閱讀
            log.exception("locate 失败 %s", ws.id)


def _one_references(ws: Workspace, data: dict, batch: list[int]) -> list[str]:
    """全文只留一個“參考文獻”塊（頁面上它會把整張參考文獻表畫出來，兩個就畫兩遍）。
    參考文獻跨了幾批（分段並行時可能兩段各起一個）時留頁碼最早的那個；這批的更早，就接過已有那塊的 id
    （掛在上面的筆記還維持關聯），回傳要在合併時一併刪掉的舊塊 id。在合併鎖裡調。"""
    mine = [b for b in data["blocks"] if b.get("type") == "references"]
    if not mine:
        return []
    others = [b for b in ws.load("paper").get("blocks", []) if b.get("type") == "references" and b.get("page") not in batch]
    keep = min(mine, key=lambda b: b.get("page") or 0)
    data["blocks"] = [b for b in data["blocks"] if b.get("type") != "references" or b is keep]
    if not others:
        return []
    if min(b.get("page") or 0 for b in others) <= (keep.get("page") or 0):
        data["blocks"].remove(keep)
        return []
    keep["id"] = others[0]["id"]
    return [b["id"] for b in others]


def _unify_terms(ws: Workspace, data: dict, batch: list[int], en_of: dict | None = None) -> None:
    """這批新報的術語和術語表裡已有的譯法不同（分段並行時幾段各自先定了譯法）：譯文改成已有的說法。在合併鎖裡調。"""
    for en, mine, old in terms.unify(ws.load("paper").get("glossary", []), data, en_of):
        journal(ws, tr("第 {page} 页起术语统一：{en} 的“{mine}”改成已有的“{old}”", page=batch[0], en=en, mine=mine, old=old))


def _save_checks(ws: Workspace, checks, batch: list[int]) -> None:
    """模型發現的原文問題 → 頁邊的“原文核對提示”。重譯這幾頁時，先去掉上次翻譯留下的那幾條。"""
    pages = {b["id"]: b.get("page") for b in ws.load("paper").get("blocks", [])}
    old = [e["id"] for e in ws.load("discussion").get("entries", [])
           if e.get("kind") == "check" and e.get("by") == "translator" and pages.get(e.get("anchor")) in batch]
    if old:
        ws.update("discussion", lambda d: d.__setitem__("entries", [e for e in d["entries"] if e.get("id") not in old]))
    items = [{"kind": "check", "by": "translator", "anchor": c["anchor"], "quote": sentences.strip(str(c.get("quote") or ""))[:200],
              "title": str(c.get("title") or "")[:80], "body": str(c["body"])}
             for c in (checks or []) if isinstance(c, dict) and c.get("anchor") in pages and str(c.get("body") or "").strip()]
    if items:
        try:
            add_discussion(ws, items)
        except ValueError as e:
            journal(ws, tr("核对提示没存上：{err}", err=e))


def _batches(pages: list[int], size: int, en_pages: set[int]) -> list[list[int]]:
    """分批：只把連續的頁放一批（續傳時中間隔著已譯的頁，跨頁續文對不上）；閱讀原文整理過的頁（補譯文）和要從頭譯的頁不混在一批裡。"""
    out: list[list[int]] = []
    for n in pages:
        if out and n == out[-1][-1] + 1 and len(out[-1]) < size and (out[-1][0] in en_pages) == (n in en_pages):
            out[-1].append(n)
        else:
            out.append([n])
    return out


def translate_pages(ws: Workspace, cfg: dict, pages: list[int], cancel, report, meter=None, read=False) -> dict[int, str]:
    """翻譯給定的頁（已完成的頁會重譯並替換；閱讀原文整理過的頁就地補譯文）。report(done, total, message)；
    meter 收集 token 用量。read：閱讀原文，把頁整理成塊但不翻譯。回傳沒做成的頁 {頁碼: 原因}。"""
    cfg = engines.for_translation(cfg)  # 本機 CLI 不載入使用者的 MCP、多餘的工具定義（問 AI 不走這裡）
    paper = ws.load("paper")
    total_pages = paper.get("meta", {}).get("page_count") or 0
    en_pages = set() if read else set(paper.get("translation", {}).get("en_pages", []))
    en_pages |= set(cfg.get("_figure_fill_pages", ())) if not read else set()
    size = max(1, int(cfg.get("batch_pages") or 2))
    # 分段並行：切成幾段連續的頁同時譯，段內一批接一批（見 segments.py）
    k = segments.workers(cfg.get("concurrency"), len(_batches(pages, size, en_pages)))
    lanes = [_batches(seg, size, en_pages) for seg in segments.plan(pages, size, k, ws.root)]
    batches = [b for lane in lanes for b in lane]
    verb = tr("正在整理原文") if read else tr("正在翻译")
    workers = max(1, len(lanes))
    job_pages = set(pages)
    had = set(paper.get("translation", {}).get("done_pages", [])) - en_pages  # 開譯前已經有譯文的頁
    lane_of = {n: i for i, lane in enumerate(lanes) for b in lane for n in b}
    state = {"done": 0, "active": set(), "quota": "", "ok": set()}  # ok：這次已經做成的頁
    failed: dict[int, str] = {}
    lock = threading.Lock()
    bad = netcheck.problem(cfg)
    if bad:
        raise engines.EngineError(bad)
    if not read and not paper.get("meta", {}).get("target"):  # 第一次翻譯時記下譯文語言，之後改設定不影響這篇
        old_zh = any(b.get("zh") or b.get("caption_zh") for b in paper.get("blocks", []))  # 1.3 以前譯的都是中文
        target = "zh" if old_zh else langs.of_paper(paper.get("meta"), cfg)
        ws.update("paper", lambda p: p.setdefault("meta", {}).setdefault("target", target))
    journal(ws, (tr("只读原文（不翻译）") if read else "") + tr("开始：{pages} 页，{batches} 批，引擎 {engine}，并发 {workers}", pages=len(pages), batches=len(batches), engine=engines.engine_name(cfg.get("engine")), workers=workers))

    def label(batch):
        return tr("第 {a}–{b} 页", a=batch[0], b=batch[-1]) if len(batch) > 1 else tr("第 {page} 页", page=batch[0])

    if workers > 1:
        journal(ws, tr("分 {n} 段同时译：{ranges}", n=workers, ranges=tr("、").join(label(sorted({lane[0][0], lane[-1][-1]})) for lane in lanes)))

    def say(msg=None):
        with lock:
            active = sorted(state["active"])
            text = msg or (verb + tr("、").join(label(b) for b in active) if active else verb)
            report(state["done"], len(pages), text)

    def work(batch):
        if cancel.is_set():
            return
        if state["quota"]:  # 額度用完了，不再白跑
            with lock:
                state["done"] += len(batch)
                for n in batch:
                    failed[n] = state["quota"]
            return
        with lock:
            state["active"].add(tuple(batch))
            p = batch[0] - 1  # 上一頁這次也要譯、還沒譯好（在別的段裡同時譯）：跨頁那段歸它，這批跳過頁首續文
            skip_head = p in job_pages and p not in state["ok"] and p not in en_pages
            # 交界兩邊都看一眼相鄰頁的原頁圖：後一段第一批看上一頁末尾，前一段最後一批看下一頁開頭
            q = batch[-1] + 1
            # 下一頁存在、不在本段（別的段在譯，或者斷點續傳時已經譯過、跳過了頁首續文）：本批負責把跨頁那段補完整
            owner = q <= total_pages and lane_of.get(q) != lane_of[batch[-1]] and q not in en_pages
            peek = ([p] if skip_head else []) + ([q] if owner else [])
            # 每段第一批、上一頁還沒有譯文（同時在別的段裡譯，或從沒譯過）：給原文的前文參考
            front = batch is lanes[lane_of[batch[0]]][0] and batch[0] > 1 and (p not in had or skip_head)
        say()
        err = None
        for attempt in range(2):
            try:
                if batch[0] in en_pages:
                    _fill_batch(ws, cfg, batch, cancel, say, meter)
                else:
                    _one_batch(ws, cfg, batch, total_pages, cancel, say, meter, read, skip_head, peek, front)
                with lock:
                    state["ok"].update(batch)
                journal(ws, tr("{pages} 完成", pages=label(batch)))
                err = None
                break
            except engines.Cancelled:
                raise
            except Exception as e:  # noqa: BLE001
                err = str(e) if isinstance(e, engines.EngineError) else f"{type(e).__name__}: {e}"
                journal(ws, tr("{pages} 第 {n} 次失败：{err}", pages=label(batch), n=attempt + 1, err=err[:500]))
                log.warning("翻译失败 %s %s: %s", ws.id, batch, err[:300])
                if cancel.is_set():
                    raise engines.Cancelled()
                if _QUOTA.search(err) or netcheck.offline(err):
                    state["quota"] = err[:300]
                    journal(ws, tr("额度用完或连不上，停止翻译剩下的页"))
                    break
        with lock:
            state["active"].discard(tuple(batch))
            state["done"] += len(batch)
            if err:
                for n in batch:
                    failed[n] = err[:300]
        say()

    def run_lane(lane):
        for batch in lane:
            if cancel.is_set():
                return
            work(batch)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_lane, lane) for lane in lanes]
        for f in futures:
            f.result()  # Cancelled 在這裡拋出去
    if cancel.is_set():
        raise engines.Cancelled()
    if not read and len(batches) > 1 and not state["quota"] and state["ok"] - set(cfg.get("_figure_fill_pages", ())):
        try:  # 檢查失敗或這時取消，都不影響已經譯好的內容：照常結束，不算取消
            report(state["done"], len(pages), tr("正在检查术语一致性"))
            consistency.check(ws, cfg, sorted(state["ok"] - set(cfg.get("_figure_fill_pages", ()))), cancel, meter, journal, _merge_lock)
        except engines.Cancelled:
            journal(ws, tr("术语一致性检查已取消，译文保留"))
        except Exception as e:  # noqa: BLE001
            journal(ws, tr("术语一致性检查没做成：{err}", err=str(e)[:300]))
            log.warning("术语一致性检查失败 %s: %s", ws.id, e)
    journal(ws, tr("结束，{n} 页失败：{pages}", n=len(failed), pages=sorted(failed)) if failed else tr("结束，全部成功"))
    return failed


def answer(ws: Workspace, cfg: dict, note_id: str, cancel) -> None:
    note = ws.load("reader").get("notes", {}).get(note_id)
    if not note:
        raise KeyError(note_id)
    text = engines.run(engines.for_translation(cfg), prompts.answer(ws, note), ws.root, None, cancel).strip()
    if not text:
        raise engines.EngineError(tr("模型没有给出回答"))
    add_discussion(ws, [{"reply_to": note_id, "kind": "reply", "body": text, "by": engines.who(cfg)}])


def retranslate(ws: Workspace, cfg: dict, key: str, hint: str, cancel) -> None:
    prompt, en_ends = prompts.retranslate(ws, key, hint)
    data = engines.parse_json(engines.run(engines.for_translation(cfg), prompt, ws.root, None, cancel))
    zh = (data or {}).get("zh", "").strip() if isinstance(data, dict) else ""
    if not zh:
        raise engines.EngineError(tr("模型没有给出新译文"))
    zh, sents = sentences.zh_sents(*en_ends, zh) if en_ends else (sentences.strip(zh), None)
    set_block_text(ws, key, zh, sents)
