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
        return features()  # 没有配置文件：没有 MCP 要关
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError('Cannot safely read Codex configuration') from exc
    names = server_names(text)
    out: list[str] = []
    for n in names:
        out += ["-c", f"mcp_servers.{_key(n)}.enabled=false"]
    out += ["-c", "notify=[]"]
    return out + features()


# 翻译用不到的功能：插件、应用、浏览器、电脑操作、生图、多代理、记忆……每个都会往每次调用里加工具定义，
# 有的还会拉起 node_repl 之类的进程。实测（codex-cli 0.159）空调用固定上下文从约 2.5 万 token 降到约 1.7 万，
# 进程从 19 个降到 3 个，内存从约 840 MB 降到约 200 MB。只关这一次调用，不改用户的配置。
# 版本不认某个名字时 Codex 照常忽略；真报错时 run_codex 会去掉这些参数再调一次。
FEATURES_OFF = ("apps", "plugins", "browser_use", "browser_use_external", "computer_use", "image_generation", "multi_agent",
                "memories", "goals", "skill_search", "in_app_browser", "tool_suggest", "realtime_conversation", "code_mode_host",
                "sleep_tool")


def features() -> list[str]:
    out: list[str] = []
    for f in FEATURES_OFF:
        out += ["-c", f"features.{f}=false"]
    return out
