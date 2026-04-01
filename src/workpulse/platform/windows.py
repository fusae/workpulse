"""Windows 平台实现 - 使用 pywin32 获取前台窗口信息"""

import logging
from typing import Optional

from workpulse.platform.base import PlatformBase, WindowInfo

logger = logging.getLogger("workpulse.platform.windows")


class WindowsPlatform(PlatformBase):
    def __init__(self):
        self._warned_errors = set()

    def _warn_once(self, key: str, exc: Exception):
        if key in self._warned_errors:
            return
        logger.warning("Windows 平台能力不可用 (%s): %s", key, exc)
        self._warned_errors.add(key)

    def get_active_window(self) -> Optional[WindowInfo]:
        try:
            import win32gui
            import win32process
            import psutil

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None

            window_title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            try:
                process = psutil.Process(pid)
                app_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "unknown"

            return WindowInfo(app_name=app_name, window_title=window_title or "")
        except Exception as exc:
            self._warn_once("active_window", exc)
            return None

    def get_idle_seconds(self) -> float:
        try:
            import ctypes
            import ctypes.wintypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.wintypes.UINT),
                    ("dwTime", ctypes.wintypes.DWORD),
                ]

            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0
        except Exception as exc:
            self._warn_once("idle_seconds", exc)
            return 0.0
