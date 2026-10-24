"""讓後端打開的窗口（資源管理器、選資料夾）彈到最前面，而不是只在任務欄閃。

Windows 只允許“剛收到使用者輸入的行程”把窗口提到前景；後端是背景行程，打開的窗口會被攔下來只閃任務欄。
模擬按一下 Alt 讓本行程拿到前景權限，再用 AllowSetForegroundWindow 把權限交給別的行程（PowerShell 選資料夾）；
資源管理器的窗口由已在執行的 explorer 打開，權限交不過去，只能等窗口出現後由本行程親手提到前面。
"""
from __future__ import annotations

import os
import sys
import time


def _user32():
    import ctypes
    return ctypes.windll.user32


def allow() -> None:
    if sys.platform != "win32":
        return
    try:
        u = _user32()
        u.keybd_event(0x12, 0, 0, 0)  # VK_MENU 按下
        u.keybd_event(0x12, 0, 2, 0)  # KEYEVENTF_KEYUP
        u.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception:  # noqa: BLE001  拿不到權限就退回老樣子，窗口照樣會打開
        pass


def _explorer_windows() -> dict[int, str]:
    import ctypes
    from ctypes import wintypes
    u, found = _user32(), {}

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hwnd, cls, 64)
        if cls.value == "CabinetWClass" and u.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(512)
            u.GetWindowTextW(hwnd, title, 512)
            found[hwnd] = title.value
        return True

    u.EnumWindows(each, 0)
    return found


def open_folder(path: str) -> None:
    """用資源管理器打開資料夾，並把那個窗口提到最前面。"""
    try:
        before = _explorer_windows()
    except Exception:  # noqa: BLE001
        before = {}
    allow()
    os.startfile(path)  # noqa: S606
    name = os.path.basename(path.rstrip("\\/")) or path
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        time.sleep(0.15)
        try:
            now = _explorer_windows()
        except Exception:  # noqa: BLE001
            return
        hwnd = next((h for h in now if h not in before), None)
        if not hwnd and time.monotonic() > deadline - 2:  # 沒有新窗口：資源管理器可能複用了已開著的同名窗口
            hwnd = next((h for h, t in now.items() if t == name), None)
        if hwnd:
            u = _user32()
            allow()
            if u.IsIconic(hwnd):
                u.ShowWindow(hwnd, 9)  # SW_RESTORE
            u.SetForegroundWindow(hwnd)
            return
