"""翻譯與問答共用的模型後端。

- claude：呼叫已安裝的 Claude Code，沿用其登入與唯讀工具權限。
- codex：呼叫官方 Codex CLI，沿用既有登入，並可附上原始頁面影像。
- openai：連接設定中的 API 服務或本機模型服務，支援 Chat Completions
  與 Responses 格式；實作位於 openai_api.py。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .i18n import tr
from . import codex_lean, netcheck, usage
from .log import log




class EngineError(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


ENGINE_NAMES = {"claude": "Claude Code", "codex": "Codex CLI", "openai": "API", "none": "不翻译"}  # i18n-ok 顯示時用 engine_name()


def engine_name(engine: str | None) -> str:
    return tr("不翻译") if engine == "none" else ENGINE_NAMES.get(engine, engine or "")


def run(cfg: dict, prompt: str, cwd: Path, images: list[Path] | None = None, cancel: threading.Event | None = None,
        meter: usage.Meter | None = None) -> str:
    """meter：傳了就把這次呼叫的 token 用量記進去（整篇翻譯時用）。"""
    bad = netcheck.problem(cfg)
    if bad:
        raise EngineError(bad)
    try:
        from . import budget
        local = usage.Meter(cfg.get('engine', ''))
        try:
            with budget.call(local):
                return _run(cfg, prompt, cwd, images, cancel, local)
        finally:
            budget.forward(local, meter)
    except EngineError as e:
        raise EngineError(netcheck.explain(cfg, str(e))) from None


def _run(cfg: dict, prompt: str, cwd: Path, images: list[Path] | None, cancel: threading.Event | None, meter) -> str:
    engine = cfg.get("engine")
    if engine == "claude":
        return run_claude(cfg["claude"], prompt, cwd, cancel, meter)
    if engine == "codex":
        return run_codex(cfg["codex"], prompt, cwd, images or [], cancel, meter)
    if engine == "openai":
        return run_openai(cfg["openai"], prompt, images or [], cancel, meter)
    raise EngineError(tr("没有配置翻译引擎（设置 → 模型）"))


def image_mode(cfg: dict) -> str:
    """提示詞裡怎麼說原頁圖：claude 自己用 Read 讀；codex 和能看圖的介面作為附件；其餘沒有圖。"""
    engine = cfg.get("engine")
    if engine == "claude":
        return "claude"
    if engine == "codex" or (engine == "openai" and cfg["openai"].get("vision")):
        return "attached"
    return "text"


def who(cfg: dict) -> str:
    engine = cfg.get("engine")
    if engine == "openai":
        return cfg["openai"].get("model") or "API"
    return {"claude": "claude", "codex": "codex"}.get(engine, "")


# ---------- 本機 CLI ----------
_NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
# stream-json 比 json 多一條 rate_limit_event（訂閱額度用了百分之幾）；-p 下用它必須加 --verbose
_CLAUDE_ARGS = ["--output-format", "stream-json", "--verbose", "--allowedTools", "Read", "--strict-mcp-config",
                "--disable-slash-commands", "--no-session-persistence"]


def claude_path(c: dict) -> str | None:
    return shutil.which(c.get("command") or "claude")


def codex_path(c: dict) -> str | None:
    if not c.get("command") or c.get("command") == "codex":
        if getattr(sys, 'frozen', False) and os.name == 'nt':
            native = Path(sys.executable).resolve().parent.parent / 'codex/bin/codex.exe'
            if native.is_file():
                return str(native)
            raise EngineError('安裝包內的 Codex CLI 不完整，請重新安裝 PaperDesk。')  # i18n-ok
        root = Path(__file__).resolve().parents[1] / ".tools" / "codex" / "node_modules" / "@openai"
        for package in (root / "codex", root / "codex" / "node_modules" / "@openai" / "codex-win32-x64", root / "codex-win32-x64"):
            for folder in ("bin", "codex"):
                native = package / "vendor" / "x86_64-pc-windows-msvc" / folder / "codex.exe"
                if os.name == "nt" and native.is_file():
                    return str(native)
        if os.name == 'nt' and (root/'codex'/'package.json').is_file():
            raise EngineError('專案內 Codex 未完整安裝，請重新執行 Setup-PaperDesk.cmd。')  # i18n-ok
    exe = shutil.which(c.get("command") or "codex")
    if exe and os.name == "nt" and Path(exe).suffix.lower() in (".cmd", ".bat", ".ps1"):
        # Use the native npm binary, avoiding cmd.exe argument interpretation.
        root = Path(exe).parent / "node_modules" / "@openai"
        for package in (root / "codex", root / "codex" / "node_modules" / "@openai" / "codex-win32-x64", root / "codex-win32-x64"):
            for folder in ("bin", "codex"):
                native = package / "vendor" / "x86_64-pc-windows-msvc" / folder / "codex.exe"
                if native.is_file():
                    return str(native)
        raise EngineError("找不到 Codex 原生執行檔，請重新安裝官方 Codex CLI。")  # i18n-ok
    return exe


def _popen(args: list[str], cwd: Path):
    inherited = netcheck.proxy_env() or dict(os.environ)
    allowed = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'APPDATA', 'LOCALAPPDATA',
               'USERPROFILE', 'HOME', 'LANG', 'LC_ALL', 'LC_CTYPE', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'NODE_EXTRA_CA_CERTS',
               'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY', 'CODEX_HOME', 'PYTHONUTF8'}
    executable = Path(args[0]).name.lower()
    if 'claude' in executable:
        allowed.update({'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'CLAUDE_CONFIG_DIR'})
    else:
        allowed.update({'CODEX_API_KEY', 'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_ORG_ID'})
        path = codex_lean.config_path()
        if path.exists():
            parsed = codex_lean.tomllib.loads(path.read_text(encoding='utf-8-sig'))
            selected = parsed.get('model_providers', {}).get(parsed.get('model_provider'), {})
            if isinstance(selected.get('env_key'), str): allowed.add(selected['env_key'].upper())
    env = {k: v for k, v in inherited.items() if k.upper() in allowed}
    return subprocess.Popen(args, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", creationflags=_NO_WINDOW,
                            env=env)


def run_claude(c: dict, prompt: str, cwd: Path, cancel=None, meter=None) -> str:
    exe = claude_path(c)
    if not exe:
        raise EngineError(tr("找不到 Claude Code 命令：{cmd}（先装好并登录 Claude Code）", cmd=c.get("command") or "claude"))
    args = [exe, "-p", *_CLAUDE_ARGS]
    if c.get("model"):
        args += ["--model", c["model"]]
    if c.get("extra_args"):
        raise EngineError("PaperDesk 不允許附加 CLI 參數。")  # i18n-ok
    if c.get("reasoning_effort"):
        args += ["--effort", c["reasoning_effort"]]
    # lean（翻譯時）：只給 Read 一個工具。--allowedTools 只是免確認，別的內置工具的定義照樣每次都發，
    # 實測空呼叫固定上下文從約 3.2 萬 token 降到約 5 千。使用者設定（代理、預設模型、登入）照舊讀。
    out = _communicate(_popen(args + CLAUDE_LEAN, cwd), prompt, int(c.get("timeout") or 1200), cancel)
    events = _json_lines(out)
    res = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if res is None:
        raise EngineError(tr("Claude Code 输出不是 JSON：{out}", out=out[:300]))
    if meter is not None:
        meter.add(**usage.from_claude(res, next((e for e in reversed(events) if e.get("type") == "rate_limit_event"), None)))
    if res.get("is_error") or res.get("subtype", "success") != "success":
        msg = str(res.get("result") or res.get("terminal_reason") or res.get("subtype"))
        if "limit" in msg.lower():
            msg += tr("（用量到上限了，等额度恢复后点“重试”，或在设置里换个引擎）")
        raise EngineError(tr("Claude Code 出错：{msg}", msg=msg))
    return res.get("result") or ""


def run_codex(c: dict, prompt: str, cwd: Path, images: list[Path], cancel=None, meter=None) -> str:
    """c["lean"]：不拉起使用者 Codex 設定裡的 MCP 服務（翻譯時用，見 codex_lean）。
    這些覆蓋參數讓 Codex 報設定錯誤時，去掉它們照舊再調一次。"""
    exe = codex_path(c)
    if not exe:
        raise EngineError(tr("找不到 Codex 命令：{cmd}（先装好并登录 Codex CLI）", cmd=c.get("command") or "codex"))
    try:
        lean = codex_lean.args()
    except ValueError as exc:
        raise EngineError(tr('Codex 設定無法安全解析，已停止呼叫。')) from exc
    text, out = _codex_once(exe, c, prompt, cwd, images, cancel, lean)
    if not text and lean and _CONFIG_ERR.search(out or ""):
        raise EngineError("Codex 不支援所需的安全設定，請更新 CLI；PaperDesk 不會降低保護重試。")  # i18n-ok
    events = _json_lines(out)
    if meter is not None:
        for e in events:
            if e.get("type") == "turn.completed":
                meter.add(**usage.from_codex(e))
    if not text:
        errs = [str(e.get("message") or (e.get("error") or {}).get("message") or "") for e in events if e.get("type") in ("error", "turn.failed")]
        raise EngineError(tr("Codex 没有给出结果：{msg}", msg=(next((m for m in reversed(errs) if m), "") or (out or "")[-300:])))
    return text


_CONFIG_ERR = re.compile(r"error (loading|parsing).*config|mcp_servers|unknown (field|key)|invalid config", re.I)
_OPTION_ERR = re.compile(r"unknown option|--tools", re.I)
CLAUDE_LEAN = ["--tools", "Read"]  # 只給 Read 一個工具（見 run_claude）


def option_unknown(err) -> bool:
    """Claude Code 版本太舊、不認 --tools 時的回報錯誤。"""
    return bool(_OPTION_ERR.search(str(err)))


def for_translation(cfg: dict) -> dict:
    """本機 CLI 只帶用得到的東西（見 run_claude、run_codex）：整篇翻譯、問 AI、回答筆記、重譯一段都走這裡。"""
    out = dict(cfg)
    for e in ("claude", "codex"):
        if isinstance(cfg.get(e), dict):
            out[e] = {**cfg[e], "lean": True}
    return out


def _codex_once(exe: str, c: dict, prompt: str, cwd: Path, images: list[Path], cancel, extra: list[str]) -> tuple[str, str]:
    if c.get("extra_args"):
        raise EngineError("PaperDesk 不允許附加 CLI 參數。")  # i18n-ok
    fd, last = tempfile.mkstemp(suffix=".txt", prefix="easyread-codex-")
    os.close(fd)
    args = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--ephemeral", "--color", "never", "--json", "-o", last]
    if c.get("model"):
        args += ["--model", c["model"]]
    for img in images:
        args += ["-i", str(img)]
    for field, key in (("reasoning_effort", "model_reasoning_effort"), ("service_tier", "service_tier")):
        if c.get(field):
            args += ["-c", key + "=" + json.dumps(c[field])]
    args += extra + ["-c", "features.shell_tool=false", "-c", "features.hooks=false", "-c", 'web_search="disabled"',
                     '-c', 'tools.view_image=false', '-c', 'project_doc_max_bytes=0', "-"]
    try:
        out = _communicate(_popen(args, cwd), prompt, int(c.get("timeout") or 1200), cancel)
        text = Path(last).read_text(encoding="utf-8", errors="replace").strip()
    finally:
        Path(last).unlink(missing_ok=True)
    return text, out


def _json_lines(out: str) -> list[dict]:
    """CLI 一行一個 JSON 事件；夾雜的非 JSON 行跳過。"""
    events = []
    for line in (out or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def _communicate(proc, stdin_text: str, timeout: int, cancel) -> str:
    result = {}

    def talk():
        result["out"], result["err"] = proc.communicate(stdin_text)

    t = threading.Thread(target=talk, daemon=True)
    t.start()
    waited = 0.0
    while t.is_alive():
        t.join(0.5)
        waited += 0.5
        if cancel is not None and cancel.is_set():
            proc.kill()
            raise Cancelled()
        if waited > timeout:
            proc.kill()
            raise EngineError(tr("超过 {n} 秒没有结果", n=timeout))
    if proc.returncode not in (0, None) and not result.get("out"):
        raise EngineError((result.get("err") or "")[-500:] or tr("退出码 {code}", code=proc.returncode))
    return result.get("out", "")


# ---------- OpenAI 相容介面 ----------
def run_openai(c: dict, prompt: str, images: list[Path], cancel=None, meter=None) -> str:
    from . import openai_api  # 它要用本檔案的 EngineError，放這裡免得循環匯入
    return openai_api.complete(c, prompt, images, cancel, meter)


def parse_json(text: str):
    """從模型輸出裡取出 JSON（容忍 ```json 圍欄和前後廢話）。"""
    t = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()  # 推理模型（deepseek-r1、qwen3）先輸出的思考過程
    # 先取最外層的 { … }：譯文裡可能本身帶程式碼塊（論文附錄的 PyTorch 程式碼），按 ``` 圍欄切會切到半截
    bodies = []
    for s in (t, *(m.group(1).strip() for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", t))):
        start = min([i for i in (s.find("{"), s.find("[")) if i >= 0], default=-1)
        if start >= 0:
            bodies.append(s[start:max(s.rfind("}"), s.rfind("]")) + 1])
    if not bodies:
        raise EngineError(tr("模型输出里没有 JSON：{text}", text=text[:200]))
    first = None
    for body in bodies:
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            first = first or e
    body = bodies[0]
    # 常見毛病：TeX 反斜槓沒寫成兩個（\alpha、\sum）、字串裡有原樣換行
    fixed = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", body)
    try:
        return json.loads(fixed, strict=False)
    except json.JSONDecodeError:
        raise EngineError(tr("模型输出的 JSON 格式有错（{err}），会自动重试", err=first))


def _version(exe: str) -> str:
    try:
        return subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30,
                              creationflags=_NO_WINDOW).stdout.strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return ""


def test(cfg: dict) -> dict:
    """設定頁“測試”按鈕：真的讓模型回一句，確認引擎能用。"""
    engine = cfg.get("engine")
    if engine in ("claude", "codex"):
        exe = (claude_path if engine == "claude" else codex_path)(cfg[engine])
        if not exe:
            return {"ok": False, "message": tr("找不到 {engine} 命令，先安装并登录", engine=engine)}
    if engine == "none":
        return {"ok": True, "message": tr("未启用自动翻译")}
    try:
        out = run(cfg, '只回复 JSON，不要别的文字：{"ok": true}', Path(tempfile.gettempdir()), None, None)  # i18n-ok
        parse_json(out)
        return {"ok": True, "message": tr("可以用：{out}", out=out.strip()[:40])}
    except (EngineError, Cancelled) as e:
        return {"ok": False, "message": str(e)[:300]}
