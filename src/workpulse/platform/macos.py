"""macOS 平台实现 - 使用 pyobjc 获取前台窗口信息"""

import logging
from typing import Optional

from workpulse.platform.base import PlatformBase, WindowInfo

logger = logging.getLogger("workpulse.platform.macos")


class MacOSPlatform(PlatformBase):
    def __init__(self):
        self._warned_errors = set()

    def _warn_once(self, key: str, exc: Exception):
        if key in self._warned_errors:
            return
        logger.warning("macOS 平台能力不可用 (%s): %s", key, exc)
        self._warned_errors.add(key)

    def get_active_window(self) -> Optional[WindowInfo]:
        try:
            from AppKit import NSWorkspace
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGNullWindowID,
                kCGWindowListOptionOnScreenOnly,
                kCGWindowListExcludeDesktopElements,
            )

            # 获取前台应用名
            active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            app_name = active_app.localizedName() or "unknown"

            # 获取窗口标题
            pid = active_app.processIdentifier()
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
                kCGNullWindowID,
            )

            window_title = ""
            if window_list:
                for window in window_list:
                    if window.get("kCGWindowOwnerPID") == pid:
                        title = window.get("kCGWindowName", "")
                        if title:
                            window_title = title
                            break

            return WindowInfo(app_name=app_name, window_title=window_title)
        except Exception as exc:
            self._warn_once("active_window", exc)
            return None

    def get_idle_seconds(self) -> float:
        try:
            from Quartz import CGEventSourceSecondsSinceLastEventType, kCGEventSourceStateCombinedSessionState

            # kCGAnyInputEventType = 0xFFFFFFFF
            idle = CGEventSourceSecondsSinceLastEventType(
                kCGEventSourceStateCombinedSessionState, 0xFFFFFFFF
            )
            return idle
        except Exception as exc:
            self._warn_once("idle_seconds", exc)
            return 0.0
