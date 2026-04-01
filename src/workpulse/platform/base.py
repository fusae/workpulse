"""平台抽象接口 - 定义获取前台窗口信息和空闲时间的接口"""

import abc
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowInfo:
    """前台窗口信息"""
    app_name: str
    window_title: str


class PlatformBase(abc.ABC):
    """平台抽象基类"""

    @abc.abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]:
        """获取当前前台窗口的应用名和窗口标题"""
        ...

    @abc.abstractmethod
    def get_idle_seconds(self) -> float:
        """获取用户空闲时间（秒）"""
        ...


def get_platform() -> PlatformBase:
    """根据当前系统返回对应的平台实现"""
    if sys.platform == "win32":
        from workpulse.platform.windows import WindowsPlatform
        return WindowsPlatform()
    elif sys.platform == "darwin":
        from workpulse.platform.macos import MacOSPlatform
        return MacOSPlatform()
    else:
        raise RuntimeError(f"不支持的平台: {sys.platform}")
