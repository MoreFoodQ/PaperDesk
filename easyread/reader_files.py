"""閱讀頁面預熱：預先載入定位資料與縮圖，並記錄文獻庫移轉期間的進行中操作。"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from . import foreground, pdfwork
from .log import log

_warming: set[str] = set()


def refresh_layout(ws) -> None:
    if (ws.load("job") or {}).get("state") in ("queued", "running"):
        return
    try:
        pdfwork.refresh_layout(ws.root)
    except Exception:  # noqa: BLE001
        log.exception("重算原页定位失败 %s", ws.root)


def warm(root: Path, gate=None) -> None:
    if str(root) in _warming or (root / "pages" / f"w{pdfwork.PANEL_WIDTH}").exists() and \
            len(list((root / "pages" / f"w{pdfwork.PANEL_WIDTH}").glob("*.webp"))) >= len(list((root / "pages").glob("page-*.webp"))):
        return
    if gate:
        gate.begin()  # 在執行緒啟動前登記，避免請求結束到背景啟動之間的移轉空檔。
    _warming.add(str(root))

    def run():
        try:
            pdfwork.warm_variants(root)
        except Exception:  # noqa: BLE001
            log.exception("生成面板图失败 %s", root)
        finally:
            _warming.discard(str(root))
            if gate:
                gate.end()
    try:
        threading.Thread(target=run, daemon=True).start()
    except Exception:
        _warming.discard(str(root))
        if gate:
            gate.end()
        raise


def reveal(path: Path):
    import subprocess
    if sys.platform.startswith("win"):
        foreground.open_folder(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
