"""开机自启动管理。"""

import plistlib
import subprocess
import sys
from pathlib import Path

APP_NAME = "WorkPulse"
WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WIN_VALUE_NAME = "WorkPulse"
MACOS_LABEL = "com.workpulse.tracker"


def _tracker_command() -> str:
    return f'"{sys.executable}" -m workpulse.tracker'


def _launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MACOS_LABEL}.plist"


def _build_launch_agent_payload() -> dict:
    return {
        "Label": MACOS_LABEL,
        "ProgramArguments": [sys.executable, "-m", "workpulse.tracker"],
        "RunAtLoad": True,
        "KeepAlive": False,
        "ProcessType": "Background",
    }


def enable_autostart():
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, WIN_VALUE_NAME, 0, winreg.REG_SZ, _tracker_command())
        print("已启用 Windows 开机自启动")
        return

    if sys.platform == "darwin":
        path = _launch_agent_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            plistlib.dump(_build_launch_agent_payload(), f)

        subprocess.run(["launchctl", "unload", str(path)], check=False, capture_output=True)
        subprocess.run(["launchctl", "load", str(path)], check=False, capture_output=True)
        print(f"已启用 macOS 开机自启动: {path}")
        return

    raise RuntimeError(f"不支持的平台: {sys.platform}")


def disable_autostart():
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, WIN_VALUE_NAME)
        except FileNotFoundError:
            pass
        print("已关闭 Windows 开机自启动")
        return

    if sys.platform == "darwin":
        path = _launch_agent_path()
        subprocess.run(["launchctl", "unload", str(path)], check=False, capture_output=True)
        if path.exists():
            path.unlink()
        print("已关闭 macOS 开机自启动")
        return

    raise RuntimeError(f"不支持的平台: {sys.platform}")


def autostart_status() -> bool:
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, WIN_VALUE_NAME)
            return value == _tracker_command()
        except FileNotFoundError:
            return False

    if sys.platform == "darwin":
        return _launch_agent_path().exists()

    raise RuntimeError(f"不支持的平台: {sys.platform}")


def show_autostart_status():
    enabled = autostart_status()
    print("WorkPulse 开机自启动已启用" if enabled else "WorkPulse 开机自启动未启用")
