"""环境与依赖自检。"""

import importlib
import json
import sys
from pathlib import Path
from typing import Dict, List

from workpulse.classifier import RULES_PATH, _ensure_rules_file
from workpulse.settings import SETTINGS_PATH, ensure_settings_file
from workpulse.tracker import DATA_DIR, DB_PATH, get_db


def run_doctor(fmt: str = "markdown") -> str:
    report = collect_diagnostics()
    if fmt == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    return _format_markdown(report)


def collect_diagnostics() -> Dict[str, object]:
    checks: List[Dict[str, str]] = []

    checks.append(_check_python())
    checks.append(_check_platform())
    checks.extend(_check_dependencies())
    checks.append(_check_data_dir())
    checks.append(_check_settings())
    checks.append(_check_rules())
    checks.append(_check_database())

    overall = "ok" if all(item["status"] == "ok" for item in checks) else "warn"
    return {
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "overall": overall,
        "checks": checks,
    }


def _check_python() -> Dict[str, str]:
    major, minor = sys.version_info[:2]
    status = "ok" if (major, minor) >= (3, 8) else "warn"
    message = f"Python {major}.{minor}"
    return {"name": "python", "status": status, "message": message}


def _check_platform() -> Dict[str, str]:
    if sys.platform in {"win32", "darwin"}:
        return {"name": "platform", "status": "ok", "message": f"支持的平台: {sys.platform}"}
    return {"name": "platform", "status": "warn", "message": f"当前平台暂不支持: {sys.platform}"}


def _check_dependencies() -> List[Dict[str, str]]:
    if sys.platform == "win32":
        modules = ["psutil", "win32gui", "win32process"]
    elif sys.platform == "darwin":
        modules = ["AppKit", "Quartz"]
    else:
        modules = []

    checks = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            checks.append({"name": f"dep:{module_name}", "status": "ok", "message": "已安装"})
        except Exception as exc:
            checks.append({"name": f"dep:{module_name}", "status": "warn", "message": f"不可用: {exc}"})
    return checks


def _check_data_dir() -> Dict[str, str]:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        writable = DATA_DIR.is_dir()
        status = "ok" if writable else "warn"
        return {"name": "data_dir", "status": status, "message": str(DATA_DIR)}
    except Exception as exc:
        return {"name": "data_dir", "status": "warn", "message": str(exc)}


def _check_settings() -> Dict[str, str]:
    try:
        ensure_settings_file()
        return {"name": "settings", "status": "ok", "message": str(SETTINGS_PATH)}
    except Exception as exc:
        return {"name": "settings", "status": "warn", "message": str(exc)}


def _check_rules() -> Dict[str, str]:
    try:
        _ensure_rules_file()
        return {"name": "rules", "status": "ok", "message": str(RULES_PATH)}
    except Exception as exc:
        return {"name": "rules", "status": "warn", "message": str(exc)}


def _check_database() -> Dict[str, str]:
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"name": "database", "status": "ok", "message": str(DB_PATH)}
    except Exception as exc:
        return {"name": "database", "status": "warn", "message": str(exc)}


def _format_markdown(report: Dict[str, object]) -> str:
    lines = [
        "# WorkPulse Doctor",
        "",
        f"- **平台**: {report['platform']}",
        f"- **Python**: {report['python_version']}",
        f"- **整体状态**: {report['overall']}",
        "",
        "| 检查项 | 状态 | 说明 |",
        "|------|------|------|",
    ]
    for item in report["checks"]:
        lines.append(f"| {item['name']} | {item['status']} | {item['message']} |")
    return "\n".join(lines)
