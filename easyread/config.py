"""配置和数据位置。

从源码目录运行时，数据就放在源码目录（library/、config.json）；pip 安装后放在 ~/EasyRead。
环境变量 EASYREAD_HOME 改数据目录，EASYREAD_LIBRARY 临时指定文献库（测试、多库）。
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

from .chat_models import DEFAULT_CHAT
from .presets import PRESET_GROUPS, PRESETS  # noqa: F401
from .store import read_json, write_json_atomic
from . import secret_store
from .security import origin, validate_api
from .i18n import tr


def server_token() -> str:
    return secret_store.unseal((read_json(SERVER_INFO, {}) or {}).get('token', ''))


def saved_key(o: dict, preset: str, url: str) -> str:
    key = (o.get('keys') or {}).get(preset, '')
    if not key and preset == (o.get('preset') or ''):
        key = o.get('api_key') or ''
    if not key:
        return ''
    bound = (o.get('key_origins') or {}).get(preset)
    if not bound:
        bound = o.get('base_url') if preset == (o.get('preset') or '') else next((p['base_url'] for p in PRESETS if p['id'] == preset), '')
    if not bound or origin(bound) != origin(url):
        raise ValueError(tr('服務網址已變更，請為此網址重新輸入金鑰。'))
    return key

PACKAGE = Path(__file__).resolve().parent
WEB = PACKAGE / "web"
_SOURCE = PACKAGE.parent
HOME = Path(os.environ.get("EASYREAD_HOME") or (_SOURCE / "data" if (_SOURCE / "pyproject.toml").exists() else Path.home() / "PaperDesk"))
PROJECT = HOME  # 旧名，cli 里还在用
CONFIG_PATH = HOME / "config.json"
LOG_PATH = HOME / "easyread.log"
SERVER_INFO = HOME / ".server.json"

DEFAULTS = {
    'metadata_lookup': False,
    'budget': {'daily_calls': 0, 'daily_tokens': 0},
    "library_dir": str(HOME / "library"),
    "port": 8876,
    "engine": "codex",          # Use the locally authenticated Codex CLI by default.
    "auto_translate": True,      # 导入后自动开始翻译
    "target": "zh-TW",
    "check_updates": False,      # This fork has no release feed yet.
    "batch_pages": 2,            # 每次交给模型的页数
    "page_cap": 60,              # 全文超过多少页先确认；0 表示不限
    "concurrency": 0,            # 同时译几段（分段并行，见 segments.py）；0 是自动，每段约 2 批、最多 4 段；手动最多 8 段
    "concurrency_v": 2,          # 1.3.1 起 concurrency 的意思变了，旧配置的 1 当成自动，见 load
    "claude": {"command": "claude", "model": "", "reasoning_effort": "", "extra_args": [], "timeout": 1200},
    "codex": {"command": "codex", "model": "", "reasoning_effort": "", "service_tier": "", "extra_args": [], "timeout": 1200},
    # api：chat（/chat/completions）| responses（/responses），见 openai_api.py
    "openai": {"preset": "", "base_url": "", "api": "chat", "api_key": "", "model": "", "vision": False, "timeout": 600},
    # 阅读页右侧“问 AI”的模型名单和默认模型，见 chat_models.py
    "chat": copy.deepcopy(DEFAULT_CHAT),
}

def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def is_first_run() -> bool:
    return not CONFIG_PATH.exists()


def _saved() -> dict:
    raw = secret_store.transform(read_json(CONFIG_PATH, {}) or {}, decrypt=True)
    if raw.get("concurrency_v") != 2 and raw.get("concurrency") == 1:
        # 以前默认 1，而且切到本机 CLI 时设置页会强制改回 1，旧配置里的 1 多半不是自己选的：当成自动。
        # 存过一次之后带上 concurrency_v，再选 1 就是真的要一段一段译
        raw["concurrency"] = 0
    elif raw.get("concurrency_v") != 2 and isinstance(raw.get("concurrency"), int) and raw["concurrency"] > 4:
        raw["concurrency"] = 4  # 以前的 6 是“同时 6 批”，现在是“同时 6 段”：升级时不替老用户开到 4 段以上
    raw["concurrency_v"] = 2
    return raw


def load() -> dict:
    cfg = _merge(DEFAULTS, _saved())
    lib = os.environ.get("EASYREAD_LIBRARY") or os.environ.get("COREAD_LIBRARY")
    if lib:  # 测试或多库时临时指定文献库
        cfg["library_dir"] = lib
    return cfg


def temp_library() -> bool:
    return bool(os.environ.get("EASYREAD_LIBRARY") or os.environ.get("COREAD_LIBRARY"))


def save(patch: dict) -> dict:
    cfg = _merge(_merge(DEFAULTS, _saved()), patch)
    write_json_atomic(CONFIG_PATH, secret_store.transform(cfg))
    return load()


def with_key(o: dict) -> dict:
    """页面提交的 openai 设置 → 要存的样子。每家服务商的 Key 分开存（keys[预设]），换来换去不用重填；
    页面发回来的打码 Key 或空 Key 表示不改。"""
    cur = load()["openai"]
    o = dict(o)
    key = o.pop("api_key", None)
    preset = o.get("preset", cur.get("preset")) or ""
    keys = dict(cur.get("keys") or {})
    bindings = dict(cur.get('key_origins') or {})
    url = o.get('base_url', cur.get('base_url', ''))
    if cur.get("api_key") and not keys:  # 旧配置只有一个 Key
        keys[cur.get("preset") or ""] = cur["api_key"]
    if key and not key.startswith("••••"):
        validate_api(url, key)
        keys[preset] = key.strip()
        bindings[preset] = url
    elif keys.get(preset):
        saved_key({**cur, 'keys': keys}, preset, url)
    o["keys"] = keys
    o['key_origins'] = bindings
    o["api_key"] = keys.get(preset, "")
    return o


def public(cfg: dict) -> dict:
    """给页面看的配置：密钥只露后四位。"""
    out = copy.deepcopy(cfg)
    key = out["openai"].get("api_key") or ""
    out["openai"]["api_key"] = ("••••" + key[-4:]) if key else ""
    out["openai"]["has_key"] = bool(key)
    out["openai"]["saved_keys"] = [k for k, v in (out["openai"].pop("keys", None) or {}).items() if v]
    out['openai'].pop('key_origins', None)
    return out


def library_dir(cfg: dict | None = None) -> Path:
    p = Path((cfg or load())["library_dir"])
    p.mkdir(parents=True, exist_ok=True)
    return p
