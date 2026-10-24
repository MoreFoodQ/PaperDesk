"""Disable configured MCP servers and unused features on every Codex call.
Configuration errors fail closed; provider/model/auth settings are preserved.
"""
from __future__ import annotations

import os
import re
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path

_BARE = re.compile(r"[A-Za-z0-9_-]+")


def config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"


def server_names(text: str) -> list[str]:
    servers = tomllib.loads(text).get('mcp_servers', {})
    if not isinstance(servers, dict):
        raise ValueError('Invalid MCP configuration')
    return list(servers)


def _key(name: str) -> str:
    return name if _BARE.fullmatch(name) else '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def args(path: Path | None = None) -> list[str]:
    """Disable every parsed MCP server; unreadable/invalid configs fail closed."""
    try:
        text = (path or config_path()).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return features()  # 沒有設定檔：沒有 MCP 要關
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError('Cannot safely read Codex configuration') from exc
    names = server_names(text)
    out: list[str] = []
    for n in names:
        out += ["-c", f"mcp_servers.{_key(n)}.enabled=false"]
    out += ["-c", "notify=[]"]
    return out + features()


# 翻譯用不到的功能：插件、應用、瀏覽器、電腦操作、生圖、多代理、記憶……每個都會往每次呼叫里加工具定義，
# 有的還會拉起 node_repl 之類的行程。實測（codex-cli 0.159）空呼叫固定上下文從約 2.5 萬 token 降到約 1.7 萬，
# 行程從 19 個降到 3 個，記憶體從約 840 MB 降到約 200 MB。只關這一次呼叫，不改使用者的設定。
# 版本不認某個名字時 Codex 照常忽略；真回報錯誤時 run_codex 會去掉這些參數再調一次。
FEATURES_OFF = ("apps", "plugins", "browser_use", "browser_use_external", "computer_use", "image_generation", "multi_agent",
                "memories", "goals", "skill_search", "in_app_browser", "tool_suggest", "realtime_conversation", "code_mode_host",
                "sleep_tool")


def features() -> list[str]:
    out: list[str] = []
    for f in FEATURES_OFF:
        out += ["-c", f"features.{f}=false"]
    return out
