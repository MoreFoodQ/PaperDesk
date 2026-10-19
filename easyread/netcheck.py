"""在模型請求前檢查連線，並提供具體的錯誤說明。

- problem(cfg)：依模型設定取得實際連線位址，檢查是否能收到 HTTP 回應。
- explain(cfg, msg)：補充連線、憑證或服務限制相關的錯誤資訊。
- proxy_env()：將系統代理設定轉為 CLI 可讀取的 HTTPS_PROXY 環境變數。
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .i18n import tr
from . import http
from .log import log
from .presets import NEEDS_VPN, PRESETS



_OK_TTL = 120  # 透過一次後兩分鐘內不再測，一篇論文幾十批不用每批都測
_ok: dict[str, float] = {}
_LOCAL = {"localhost", "127.0.0.1", "::1"}
_NET = re.compile(r"ECONNREFUSED|ETIMEDOUT|ENOTFOUND|ECONNRESET|EAI_AGAIN|fetch failed|connection error|unable to connect"
                  r"|error sending request|stream disconnected|timed out|getaddrinfo|连不上|can't connect", re.I)  # i18n-ok 匹配回報錯誤
_REGION = re.compile(r"unsupported_country|not available in your (country|region)|request not allowed", re.I)
# 自己給出的連不上 / 證書提示裡一定帶的詞（中英文各一套），見到就不再追加建議
_MARKS = ("先把它打开", "請檢查網路", "check your network", "start it first")  # i18n-ok
_CERT_MARKS = ("证书校验失败", "certificate verification failed")  # i18n-ok
_CERT = re.compile(r"CERTIFICATE_VERIFY_FAILED|certificate verify failed|self.signed certificate|unknown issuer", re.I)


def _claude_base() -> str:
    """讀取 Claude Code 自訂的 ANTHROPIC_BASE_URL；未設定時使用官方位址。"""
    base = os.environ.get("ANTHROPIC_BASE_URL")
    if not base:
        try:
            env = json.loads((Path.home() / ".claude" / "settings.json").read_text(encoding="utf-8")).get("env") or {}
            base = env.get("ANTHROPIC_BASE_URL")
        except (OSError, ValueError, AttributeError):
            pass
    return base or "https://api.anthropic.com"


def _codex_base() -> str:
    try:
        text = (Path.home() / ".codex" / "config.toml").read_text(encoding="utf-8")
    except OSError:
        text = ""
    m = re.search(r'^\s*model_provider\s*=\s*"([^"]+)"', re.split(r"(?m)^\s*\[", text, maxsplit=1)[0], re.M)
    if m and m.group(1) != "openai":
        sec = re.search(r"^\[model_providers\.%s\]([\s\S]*?)(?=^\[|\Z)" % re.escape(m.group(1)), text, re.M)
        b = sec and re.search(r'^\s*base_url\s*=\s*"([^"]+)"', sec.group(1), re.M)
        if b:
            return b.group(1)
    return "https://chatgpt.com"


def target(cfg: dict) -> dict | None:
    """回傳服務名稱、連線位址與舊版相容旗標 vpn；旗標不代表必須使用代理。"""
    e = cfg.get("engine")
    if e == "claude":
        url = _claude_base()
        official = "anthropic.com" in url
        return {"name": "Claude" if official else tr("Claude Code 配置的中转地址"), "url": url, "vpn": official}
    if e == "codex":
        url = _codex_base()
        official = "chatgpt.com" in url or "openai.com" in url
        return {"name": tr("OpenAI（Codex）") if official else tr("Codex 配置的中转地址"), "url": url, "vpn": official}
    if e == "openai":
        o = cfg.get("openai") or {}
        url = (o.get("base_url") or "").strip().rstrip("/")
        if not url:
            return None
        p = next((x for x in PRESETS if x["id"] == o.get("preset")), None) \
            or next((x for x in PRESETS if x["base_url"].rstrip("/") == url), None)
        return {"name": p["name"] if p else tr("接口"), "url": url, "vpn": bool(p and p["id"] in NEEDS_VPN)}
    return None


def _advice(t: dict) -> str:
    host = urlparse(t["url"]).hostname or t["url"]
    if host in _LOCAL:
        return tr("连不上 {name}（{host}）：先把它打开，再点重试。", name=t["name"], host=urlparse(t["url"]).netloc)
    return tr('無法連線至 {name}（{host}）：請檢查網路、API 位址與服務狀態；若使用代理伺服器，也請確認代理設定。', name=t['name'], host=host)


def _region(t: dict) -> str:
    return tr('{name} 不支援目前的連線地區，請確認帳號與所在地符合服務商的使用條件。', name=t['name'])


def _certificate(t: dict) -> str:
    host = urlparse(t["url"]).hostname or t["url"]
    return tr("{name}（{host}）证书校验失败：请检查系统信任的根证书；使用代理时，也检查代理证书是否已获系统信任。", name=t["name"], host=host)


def problem(cfg: dict, timeout: float = 6) -> str | None:
    """連得上回傳 None，連不上回傳給使用者看的一句話。"""
    t = target(cfg)
    u = urlparse(t["url"]) if t else None
    if not u or not u.hostname:
        return None
    origin = f"{u.scheme}://{u.netloc}/"
    if time.time() - _ok.get(origin, 0) < _OK_TTL:
        return None
    for attempt in range(2):  # 避免短暫連線不穩造成誤判，最多嘗試兩次
        try:
            http.urlopen(origin, timeout=timeout).close()
        except urllib.error.HTTPError as e:  # 有 HTTP 回應就說明網路是通的
            if _REGION.search(e.read(2000).decode("utf-8", "replace")):
                return _region(t)
        except Exception as e:  # noqa: BLE001  DNS 失敗、拒絕連接、超時、證書被劫持……
            if _CERT.search(str(e)):
                log.info("证书校验失败 %s：%s", origin, e)
                return _certificate(t)
            if attempt == 0:
                continue
            log.info("连通性检查失败 %s：%s", origin, e)
            return _advice(t)
        _ok[origin] = time.time()
        return None


def explain(cfg: dict, msg: str) -> str:
    t = target(cfg)
    if not t or any(k in msg for k in _MARKS):
        return msg
    if _REGION.search(msg):
        return msg + "\n" + _region(t)
    if _CERT.search(msg):
        _ok.clear()
        return msg + "\n" + _certificate(t)
    if _NET.search(msg):
        _ok.clear()
        return msg + "\n" + _advice(t)
    return msg


def offline(msg: str) -> bool:
    """這條回報錯誤是不是網路 / 地區問題（是的話剩下的頁不用再試了）。"""
    return any(k in msg for k in _MARKS + _CERT_MARKS)


def proxy_env() -> dict | None:
    """Windows / macOS 的系統代理 Python 讀得到，Node 寫的 Claude Code 讀不到；沒設 HTTPS_PROXY 時替它補上。"""
    if any(os.environ.get(k) for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")):
        return None
    p = urllib.request.getproxies()
    proxy = p.get("https") or p.get("http")
    if not proxy or not proxy.startswith("http"):
        return None
    return dict(os.environ, HTTPS_PROXY=proxy, HTTP_PROXY=p.get("http") or proxy,
                NO_PROXY=os.environ.get("NO_PROXY") or "localhost,127.0.0.1,::1")
