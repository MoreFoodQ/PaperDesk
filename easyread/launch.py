"""啟動僅監聽 127.0.0.1 的服務；啟動器可指定頁面全部關閉後自動結束。"""
from __future__ import annotations

import os
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer
from urllib.parse import quote

from . import __version__, config, detect, secret_store
from .log import log, setup as setup_log
from .presence import Presence
from .server import App, Handler
from .store import now_iso, read_json, write_json_atomic


class _Server(ThreadingHTTPServer):
    # Windows 上 SO_REUSEADDR 會讓兩個行程同時佔住 8765，瀏覽器隨機連到其中一個（比如舊版本）
    allow_reuse_address = os.name != "nt"
    slots = threading.BoundedSemaphore(32)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def serve(port: int | None = None, open_browser: bool = False, path: str = "/", exit_on_close: bool = False):
    """exit_on_close 為 True 時，等待所有頁面離線且背景工作完成後結束。"""
    setup_log(config.LOG_PATH)
    started = time.monotonic()
    cfg = config.load()
    log.info("startup config-ready +%.0fms", (time.monotonic() - started) * 1000)
    app = App(cfg)
    log.info("startup library-jobs-ready +%.0fms", (time.monotonic() - started) * 1000)
    Handler.app = app
    detect.warm(cfg)
    port = cfg["port"] if port is None else port
    try:
        httpd = _Server(("127.0.0.1", port), Handler)
    except OSError:
        httpd = _Server(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    log.info("startup http-bound +%.0fms", (time.monotonic() - started) * 1000)
    app.shutdown = httpd.shutdown
    app.location.marker.start()
    app.presence = Presence(app.jobs.busy, httpd.shutdown, exit_on_close)
    if not config.temp_library():
        write_json_atomic(config.SERVER_INFO, {"url": url, "pid": os.getpid(), "started": now_iso(), 'token': secret_store.seal(app.token)})
        if os.name != 'nt':
            config.SERVER_INFO.chmod(0o600)
    log.info("EasyRead %s 已启动：%s  文献库：%s", __version__, url, app.lib.root)
    print(f"EasyRead 已启动：{url}  文献库：{app.lib.root}", flush=True)  # i18n-ok Electron 和 smoke_backend 用正則匹配這行
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url + '/auth?session=' + app.token + '&next=' + quote(path, safe=''))).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.location.marker.close()
        httpd.server_close()
        if not config.temp_library() and (read_json(config.SERVER_INFO, {}) or {}).get("pid") == os.getpid():
            config.SERVER_INFO.unlink(missing_ok=True)  # 下次 easyread 命令不會去連一個已經關掉的服務
