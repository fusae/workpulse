"""Intent inference for activity samples."""

from __future__ import annotations

import json
from typing import Dict, Optional, Tuple


INTENT_LABELS = {
    "coding": "编码开发",
    "research": "资料研究",
    "communication": "沟通协作",
    "writing": "写作产出",
    "planning": "计划管理",
    "terminal": "终端操作",
    "entertainment": "娱乐分心",
    "unknown": "未知意图",
}


def infer_intent(
    app_name: str,
    window_title: str,
    browser_url: str = "",
    ocr_text: str = "",
    project_name: Optional[str] = None,
) -> Tuple[str, str]:
    haystack = " ".join(
        part.lower()
        for part in [app_name or "", window_title or "", browser_url or "", ocr_text or ""]
        if part
    )
    evidence: Dict[str, object] = {
        "app": app_name,
        "title": window_title,
    }
    if browser_url:
        evidence["url"] = browser_url
    if project_name:
        evidence["project"] = project_name

    rules = [
        ("entertainment", ["youtube", "netflix", "bilibili", "抖音", "tiktok", "reddit"]),
        ("communication", ["slack", "discord", "teams", "wechat", "微信", "mail", "gmail", "飞书", "lark"]),
        ("terminal", ["terminal", "iterm", "warp", "zsh", "bash", "fish", "powershell"]),
        ("coding", ["code", "cursor", "xcode", "pycharm", "webstorm", "github", "gitlab", ".py", ".ts", ".js", ".go", ".rs"]),
        ("research", ["google", "search", "arxiv", "wikipedia", "docs", "文档", "stackoverflow", "medium"]),
        ("writing", ["notion", "obsidian", "pages", "word", "docs.google", "markdown", ".md", "写作"]),
        ("planning", ["calendar", "linear", "jira", "trello", "things", "todo", "日历", "任务"]),
    ]

    for intent, keywords in rules:
        matched = [keyword for keyword in keywords if keyword in haystack]
        if matched:
            evidence["matched_keywords"] = matched[:5]
            return intent, json.dumps(evidence, ensure_ascii=False)

    if project_name:
        evidence["matched_keywords"] = ["project_context"]
        return "coding", json.dumps(evidence, ensure_ascii=False)

    return "unknown", json.dumps(evidence, ensure_ascii=False)


def intent_label(intent: str) -> str:
    return INTENT_LABELS.get(intent, intent or INTENT_LABELS["unknown"])
