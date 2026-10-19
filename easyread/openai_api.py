"""OpenAI 相容 API 的請求與串流處理。

- chat：使用 {base}/chat/completions。
- responses：使用 {base}/responses。
實際可用模型、影像能力與驗證方式由設定的服務商決定。
"""
from __future__ import annotations

import base64
import json
import math
import threading
import time
import urllib.error
import urllib.request
import uuid
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterator

from . import __version__, http, usage
from .engines import Cancelled, EngineError
from .i18n import tr

def api_kinds() -> list[tuple[str, str]]:
    return [("chat", tr("Chat Completions（通用）")), ("responses", tr("Responses（OpenAI 新接口）"))]


def _hint(code: int) -> str:
    return {401: tr("（Key 不对或过期了）"), 402: tr("（余额不足）"), 403: tr("（没有权限用这个模型）"),
            404: tr("（地址、模型名或接口格式不对）"), 429: tr("（被限流了，稍后重试或换个模型）")}.get(code, "")


_SESSION = f"easyread-{uuid.uuid4()}"  # 每次啟動一個，整個行程內不變


def kind(o: dict) -> str:
    return "responses" if o.get("api") == "responses" else "chat"


def _base(o: dict) -> str:
    base = (o.get("base_url") or "").strip().rstrip("/")
    if not base or not o.get("model"):
        raise EngineError(tr("API 没填地址或模型（设置 → 模型）"))
    return base


def _headers(o: dict, stream: bool = False) -> dict:
    # 要帶 User-Agent：Python 預設的 "Python-urllib/x" 會被 Cloudflare 後面的介面（比如 OpenCode）直接攔掉，報 403 error code: 1010
    # x-opencode-session：OpenCode Go 要求帶一個穩定的會話 ID，不帶報 400 MissingSessionID；別的服務商會忽略這個頭
    h = {"Content-Type": "application/json", "User-Agent": f"EasyRead/{__version__}", "x-opencode-session": _SESSION}
    if stream:
        h["Accept"] = "text/event-stream"
    if o.get("api_key"):
        h["Authorization"] = "Bearer " + o["api_key"]
    return h


def _body(o: dict, prompt: str, images: list[Path], stream: bool, temperature: float | None) -> dict:
    urls = ["data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode() for p in images] if o.get("vision") else []
    if kind(o) == "responses":
        content = [{"type": "input_text", "text": prompt}] + [{"type": "input_image", "image_url": u} for u in urls]
        body = {"model": o["model"], "input": [{"role": "user", "content": content}], "store": False}
    else:
        content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": u}} for u in urls] if urls else prompt
        body = {"model": o["model"], "messages": [{"role": "user", "content": content}]}
    if o.get("reasoning_effort"):
        if kind(o) == "responses":
            body["reasoning"] = {"effort": o["reasoning_effort"]}
        else:
            body["reasoning_effort"] = o["reasoning_effort"]
    if o.get("service_tier"):
        body["service_tier"] = o["service_tier"]
    if temperature is not None and not o.get("reasoning_effort"):
        body["temperature"] = temperature
    if stream:
        body["stream"] = True
        if kind(o) == "chat":
            body["stream_options"] = {"include_usage": True}  # 最後一塊帶上 token 用量；不認這個參數的介面會去掉再發
    return body


def _open(o: dict, body: dict, stream: bool):
    """發請求。有的模型（推理模型、Kimi K2 系列）不讓改 temperature、有的介面不認 stream_options，報 400 時去掉再發。"""
    path = "/responses" if kind(o) == "responses" else "/chat/completions"
    for _ in range(3):
        req = urllib.request.Request(_base(o) + path, data=json.dumps(body).encode(), headers=_headers(o, stream))
        try:
            return http.urlopen(req, timeout=int(o.get("timeout") or 600))
        except urllib.error.HTTPError as e:
            detail = e.read(300).decode("utf-8", "replace")
            e.close()
            drop = next((k for k in ("temperature", "stream_options") if k in detail and k in body), None)
            if e.code == 400 and drop:
                body = {k: v for k, v in body.items() if k != drop}
                continue
            e.detail = detail
            raise


def _http_error(e: urllib.error.HTTPError) -> EngineError:
    return EngineError(tr("接口返回 {code}{hint}：{detail}", code=e.code, hint=_hint(e.code), detail=getattr(e, "detail", "")))


# ---------- 一次拿到整段（翻譯用） ----------
def complete(o: dict, prompt: str, images: list[Path], cancel=None, meter=None) -> str:
    body = _body(o, prompt, images, False, None if kind(o) == "responses" else 0.2)
    res = None
    for attempt in range(4):  # 限流、服務端錯誤、網路抖動：等一會兒再試
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        try:
            res = _fetch(o, body, cancel)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                _sleep(_retry_after(e.headers.get("Retry-After"), 5 * 2 ** attempt), cancel)
                continue
            raise _http_error(e)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if attempt < 2:
                _sleep(5, cancel)
                continue
            raise EngineError(tr("连不上接口：{err}", err=e))
    if meter is not None and isinstance(res, dict):
        meter.add(**usage.from_openai(res))
    return _responses_text(res) if kind(o) == "responses" else _chat_text(res)


def _fetch(o: dict, body: dict, cancel) -> dict:
    """發請求、讀完整個回答。請求放在執行緒裡，點取消就不再等它（這次呼叫的回答丟掉），不然要等介面回傳，常常一兩分鐘。"""
    if cancel is None:
        with _open(o, body, False) as r:
            return json.loads(r.read())
    box: dict = {}

    def run():
        try:
            with _open(o, body, False) as r:
                box["res"] = json.loads(r.read())
        except BaseException as e:  # 原樣交回主執行緒，限流重試、連不上這些分支照舊
            box["err"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    while t.is_alive():
        t.join(0.3)
        if cancel.is_set() and t.is_alive():
            raise Cancelled()
    if "err" in box:
        raise box["err"]
    return box["res"]


def _chat_text(res) -> str:
    try:
        choice = res["choices"][0]
        text = choice["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise EngineError(tr("接口返回格式不对：{res}", res=str(res)[:300]))
    _check_finish(choice.get("finish_reason"))
    return text


def _responses_text(res) -> str:
    if not isinstance(res, dict):
        raise EngineError(tr("接口返回格式不对：{res}", res=str(res)[:300]))
    _check_response_status(res)
    if "output" not in res:
        raise EngineError(tr("接口返回格式不对：{res}", res=str(res)[:300]))
    return "".join(c.get("text") or "" for item in res["output"] if item.get("type") == "message"
                   for c in item.get("content") or [] if c.get("type") == "output_text")


def _truncated() -> EngineError:
    return EngineError(tr("模型输出被截断了（超过它的输出长度上限）。在设置里把“每次交给模型的页数”调成 1 页再试。"))


def _check_finish(reason) -> None:
    if reason == "length":
        raise _truncated()
    if reason == "content_filter":
        raise EngineError(tr("模型输出被服务商的内容过滤器中断了。"))


def _check_response_status(res: dict) -> None:
    if res.get("status") == "incomplete":
        reason = (res.get("incomplete_details") or {}).get("reason")
        if reason == "max_output_tokens":
            raise _truncated()
        raise EngineError(tr("模型未完成回答：{reason}", reason=reason or tr("接口没有提供原因")))
    if res.get("status") == "failed":
        raise EngineError(tr("接口返回出错：{err}", err=res.get("error")))


def _retry_after(value: str | None, default: float) -> float:
    """Retry-After 可以是秒數或 HTTP 日期；不合法時使用正常退避。"""
    if not value:
        return default
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return default
    return max(0, seconds) if math.isfinite(seconds) else default


def _sleep(seconds: float, cancel) -> None:
    end = time.time() + min(seconds, 90)
    while time.time() < end:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        time.sleep(0.5)


# ---------- 逐字輸出（問 AI 用） ----------
def stream(o: dict, text: str, cancel, meter=None) -> Iterator[str]:
    if cancel.is_set():
        raise Cancelled()
    body = _body(o, text, [], True, None if kind(o) == "responses" else 0.4)
    try:
        r = _open(o, body, True)
    except urllib.error.HTTPError as e:
        raise _http_error(e)
    except Exception as e:  # noqa: BLE001
        raise EngineError(tr("连不上接口：{err}", err=e))
    with r:
        if cancel.is_set():
            raise Cancelled()
        pieces = _responses_pieces(r, cancel, meter) if kind(o) == "responses" else _chat_pieces(r, cancel, meter)
        yield from _strip_think(pieces)


_DONE, _EMPTY, _PARTIAL = object(), object(), object()


def _payload(data: list[str]):
    """一條事件的 data 行合起來：[DONE]、空事件、還沒收完整的 JSON 分別給標記，否則給解析結果。"""
    payload = "\n".join(data).strip()
    if payload == "[DONE]":
        return _DONE
    if not payload:
        return _EMPTY
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return _PARTIAL


def _events(r, cancel) -> Iterator[dict | None]:
    """按空行分隔 SSE 事件，同一事件的多個 data 行要合起來解析；[DONE] 給 None。
    有的中轉介面事件之間只隔一個換行，或者最後一條後面沒有空行就斷開：
    已攢下的 data 本身就是完整 JSON 時，碰到下一行 data 或連接結束也照樣交出去。"""
    data = []
    for raw in r:
        if cancel.is_set():
            raise Cancelled()
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        is_data = line.startswith("data:") or line == "data"
        if data and (not line or is_data):
            ev = _payload(data)
            if not (ev is _PARTIAL and is_data):  # 還不完整又來了 data 行：一條事件拆成了多行，接著攢
                data.clear()
                if ev is _DONE:
                    yield None
                    return
                if ev is not _EMPTY:
                    yield _check_event(ev)
        if is_data:
            data.append(line.partition(":")[2].removeprefix(" "))
    if data:
        ev = _payload(data)
        if ev is _DONE:
            yield None
        elif ev is not _EMPTY:
            yield _check_event(ev)


def _check_event(ev) -> dict:
    if ev is _PARTIAL:
        raise EngineError(tr("接口返回的流数据不是有效 JSON"))
    if not isinstance(ev, dict):
        raise EngineError(tr("接口返回的流数据格式不对"))
    return ev


def _chat_pieces(r, cancel, meter=None) -> Iterator[str]:
    finished = False
    for ev in _events(r, cancel):
        if ev is None:
            return
        if ev.get("error"):
            raise EngineError(tr("接口返回出错：{err}", err=ev["error"]))
        if ev.get("usage") and meter is not None:
            meter.add(**usage.from_openai(ev))
        choice = (ev.get("choices") or [{}])[0]
        _check_finish(choice.get("finish_reason"))
        finished = finished or bool(choice.get("finish_reason"))
        yield (choice.get("delta") or {}).get("content") or ""
    if not finished:
        raise EngineError(tr("接口连接提前结束，回答未完成，请重试。"))


def _responses_pieces(r, cancel, meter=None) -> Iterator[str]:
    for ev in _events(r, cancel):
        t = (ev or {}).get("type", "")
        if ev is None:
            return
        if t in ("response.completed", "response.incomplete", "response.failed"):
            res = ev.get("response") or {}
            _check_response_status({**res, "status": res.get("status") or t.split(".")[1]})
            if meter is not None:
                meter.add(**usage.from_openai(res))
            return
        if t == "response.output_text.delta":
            yield ev.get("delta") or ""
        elif t == "error":
            err = (ev.get("response") or {}).get("error") or ev.get("error") or ev.get("message")
            raise EngineError(tr("接口返回出错：{err}", err=err))
    raise EngineError(tr("接口连接提前结束，回答未完成，请重试。"))


def _strip_think(pieces: Iterator[str]) -> Iterator[str]:
    """推理模型把思考過程包在 <think> 裡，讀者不需要看。"""
    thinking = False
    pending = ""
    for piece in pieces:
        pending += piece
        while pending:
            tag = "</think>" if thinking else "<think>"
            index = pending.find(tag)
            if index >= 0:
                if not thinking and index:
                    yield pending[:index]
                pending = pending[index + len(tag):]
                thinking = not thinking
                continue
            # 留下可能是下一個標籤開頭的後綴，下一片到來後再判斷。
            keep = next((n for n in range(len(tag) - 1, 0, -1) if pending.endswith(tag[:n])), 0)
            visible = pending[:-keep] if keep else pending
            if not thinking and visible:
                yield visible
            pending = pending[-keep:] if keep else ""
            break
    if pending and not thinking:
        yield pending


# ---------- 模型清單 ----------
def models(o: dict) -> list[str]:
    """GET {base}/models，回傳模型名（排好序）。"""
    base = (o.get("base_url") or "").strip().rstrip("/")
    if not base:
        raise EngineError(tr("先填接口地址"))
    req = urllib.request.Request(base + "/models", headers=_headers(o))
    try:
        with http.urlopen(req, timeout=20) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        e.detail = e.read(300).decode("utf-8", "replace")
        e.close()
        raise _http_error(e)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise EngineError(tr("连不上接口：{err}", err=e))
    except json.JSONDecodeError:
        raise EngineError(tr("这个地址不提供模型列表，手填模型名"))
    items = res.get("data") if isinstance(res, dict) else res
    if not isinstance(items, list):  # Gemini 的舊格式是 {"models": [...]}
        items = (res or {}).get("models") or []
    ids = [str(m.get("id") or m.get("name") or "").removeprefix("models/") if isinstance(m, dict) else str(m) for m in items]
    return sorted({i for i in ids if i})
