"""瀏覽器頁面全部離線後，依啟動選項自動結束本機服務。

文獻庫與閱讀頁透過 WebSocket 回報連線狀態。最後一個頁面離線後，
先保留緩衝時間，避免重新整理或頁面切換造成誤判。
仍有翻譯或問答任務時繼續執行，待工作完成且無頁面連線後再結束。

此機制由 --exit-on-close 啟用；一般常駐服務與 Electron 桌面版不使用它。
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .log import log

GRACE = 15        # 最後一個頁面斷開後再等多久
FIRST_WAIT = 120  # 啟動後一直沒有頁面連上來（瀏覽器沒打開之類），等多久


class Presence:
    def __init__(self, busy: Callable[[], bool], stop: Callable[[], None], enabled: bool,
                 grace: float = GRACE, first_wait: float = FIRST_WAIT, tick: float = 1.0):
        self.busy, self.stop, self.enabled = busy, stop, enabled
        self.grace, self.first_wait, self.tick = grace, first_wait, tick
        self.pages = 0
        self.seen = False  # 有沒有頁面連上來過
        self.lock = threading.Lock()
        self.idle_since: float | None = time.monotonic()
        if enabled:
            threading.Thread(target=self._watch, daemon=True).start()

    def enter(self) -> None:
        with self.lock:
            self.pages += 1
            self.seen = True

    def leave(self) -> None:
        with self.lock:
            self.pages = max(0, self.pages - 1)

    def keep(self) -> None:
        """有人用 `easyread serve` 要一個常駐的服務、卻複用了這個會自動退出的：從此不再自動退出。"""
        if self.enabled:
            log.info("改为常驻，不再在页面关掉后自动退出")
        self.enabled = False

    def should_stop(self, now: float) -> bool:
        with self.lock:
            idle = self.pages == 0
            wait = self.grace if self.seen else self.first_wait
        if not idle or self.busy():
            self.idle_since = None
            return False
        if self.idle_since is None:
            self.idle_since = now
        return now - self.idle_since >= wait

    def _watch(self) -> None:
        while self.enabled:
            time.sleep(self.tick)
            if self.enabled and self.should_stop(time.monotonic()):
                log.info("页面都关了，后台没有任务在跑，退出服务")
                self.stop()
                return
