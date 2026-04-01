"""智能分类引擎 - 根据规则对应用和窗口标题进行分类"""

import importlib.resources
from pathlib import Path
from typing import List

import yaml

RULES_PATH = Path.home() / ".workpulse" / "rules.yaml"


def _ensure_rules_file():
    """确保用户规则文件存在，不存在则从默认配置复制"""
    if RULES_PATH.exists():
        return
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)

    default_text = None
    try:
        package_files = getattr(importlib.resources, "files", None)
        if package_files is not None:
            default_text = (
                package_files("workpulse.config")
                .joinpath("default_rules.yaml")
                .read_text(encoding="utf-8")
            )
        else:
            default_text = importlib.resources.read_text(
                "workpulse.config",
                "default_rules.yaml",
                encoding="utf-8",
            )
    except (FileNotFoundError, ModuleNotFoundError):
        default_text = None

    if default_text is not None:
        RULES_PATH.write_text(default_text, encoding="utf-8")
        return

    # fallback: 写一个最小配置
    RULES_PATH.write_text(
        "idle_threshold_minutes: 5\ndefault_category: \"其他\"\nrules: []\n",
        encoding="utf-8",
    )


class Classifier:
    def __init__(self):
        _ensure_rules_file()
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        self.idle_threshold_minutes: int = config.get("idle_threshold_minutes", 5)
        self.default_category: str = config.get("default_category", "其他")
        self.rules: List[dict] = config.get("rules", [])

    def classify(self, app_name: str, window_title: str) -> str:
        """根据规则匹配分类，大小写不敏感"""
        app_lower = app_name.lower()
        title_lower = window_title.lower()

        for rule in self.rules:
            if "app_contains" in rule:
                if rule["app_contains"].lower() in app_lower:
                    return rule["category"]
            if "title_contains" in rule:
                if rule["title_contains"].lower() in title_lower:
                    return rule["category"]

        return self.default_category
