"""AI 分析模块 - 基于活动摘要生成启发式工作分析。"""

import json
from typing import Dict, List

from workpulse.reporter import get_report_snapshot
from workpulse.tracker import get_db, POLL_INTERVAL


def _format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _build_findings(snapshot: Dict[str, object]) -> List[str]:
    findings = []
    active_total = snapshot["active_total"]
    idle_time = snapshot["idle_time"]
    categories = snapshot["categories"]
    apps = snapshot["apps"]
    context_switches = snapshot["context_switches"]

    if not active_total and not idle_time:
        return ["暂无足够数据，无法分析工作模式。"]

    if categories:
        top_category = categories[0]
        findings.append(
            f"主要时间投入在“{top_category['category']}”，约 {_format_duration(top_category['seconds'])}，"
            f"占活跃时间 {top_category['pct']:.1f}% 。"
        )

    if idle_time > active_total * 0.35 and idle_time >= 1800:
        findings.append(
            f"空闲时间达到 {_format_duration(idle_time)}，比例偏高，可能存在较多会议等待、离开工位或中断。"
        )

    if context_switches >= 20:
        findings.append(f"检测到约 {context_switches} 次上下文切换，专注度可能被频繁打断。")
    elif context_switches >= 10:
        findings.append(f"检测到约 {context_switches} 次上下文切换，处于中等偏高水平。")

    communication = next((item for item in categories if item["category"] == "沟通"), None)
    if communication and communication["pct"] >= 25:
        findings.append("沟通类活动占比较高，说明当日可能偏协同推进而非深度产出。")

    entertainment = next((item for item in categories if item["category"] == "娱乐"), None)
    if entertainment and entertainment["seconds"] >= 900:
        findings.append("娱乐类活动有明显占比，建议核查是否混入了非工作浏览。")

    multi_category_apps = [app for app in apps if str(app["category"]).startswith("多种(")]
    if multi_category_apps:
        findings.append(
            f"有 {len(multi_category_apps)} 个应用跨多个分类，说明仅按应用名看工作内容会失真。"
        )

    return findings


def _build_suggestions(snapshot: Dict[str, object]) -> List[str]:
    suggestions = []
    categories = snapshot["categories"]
    apps = snapshot["apps"]
    titles = snapshot["titles"]
    context_switches = snapshot["context_switches"]
    repeated_titles = snapshot["repeated_titles"]

    if context_switches >= 20:
        suggestions.append("将即时沟通集中到固定时段处理，减少频繁切换窗口。")

    communication = next((item for item in categories if item["category"] == "沟通"), None)
    if communication and communication["pct"] >= 25:
        suggestions.append("为沟通类任务单独设时间块，避免侵蚀深度工作时间。")

    browser = next((app for app in apps if app["app_name"] in {"Chrome", "Edge", "Firefox", "Safari"}), None)
    if browser and str(browser["category"]).startswith("多种("):
        suggestions.append("浏览器活动跨多个类别，建议后续增加标题级规则，把工作网页和娱乐网页分开。")

    if repeated_titles:
        suggestions.append("检测到重复高频窗口，可考虑把这类固定流程沉淀为模板或自动化脚本。")

    if not suggestions and titles:
        suggestions.append("当前活动结构较稳定，下一步更值得投入的是补充更细粒度的分类规则。")

    return suggestions


def _count_context_switches(period: str) -> int:
    snapshot = get_report_snapshot(period)
    start = snapshot["time_range"]["start"]
    end = snapshot["time_range"]["end"]
    conn = get_db()
    rows = conn.execute(
        """
        SELECT app_name, window_title
        FROM activities
        WHERE timestamp >= ? AND timestamp < ? AND is_idle = 0
        ORDER BY timestamp ASC
        """,
        (start, end),
    ).fetchall()
    conn.close()

    switches = 0
    last_key = None
    for row in rows:
        key = (row["app_name"], row["window_title"])
        if last_key is not None and key != last_key:
            switches += 1
        last_key = key
    return switches


def analyze_period(period: str = "today") -> Dict[str, object]:
    snapshot = get_report_snapshot(period)
    title_counts = {}
    for item in snapshot["titles"]:
        title_counts[item["window_title"]] = title_counts.get(item["window_title"], 0) + item["samples"]

    snapshot["context_switches"] = _count_context_switches(period)
    snapshot["repeated_titles"] = [
        title for title, samples in title_counts.items() if samples >= 3 and title
    ]

    findings = _build_findings(snapshot)
    suggestions = _build_suggestions(snapshot)

    return {
        "period": snapshot["period"],
        "label": snapshot["label"],
        "summary": {
            "active_time": _format_duration(snapshot["active_total"]),
            "idle_time": _format_duration(snapshot["idle_time"]),
            "context_switches": snapshot["context_switches"],
        },
        "findings": findings,
        "suggestions": suggestions,
        "snapshot": snapshot,
    }


def format_analysis(period: str = "today", fmt: str = "markdown") -> str:
    analysis = analyze_period(period)
    if fmt == "json":
        return json.dumps(analysis, ensure_ascii=False, indent=2)
    return _format_markdown(analysis)


def _format_markdown(analysis: Dict[str, object]) -> str:
    lines = [
        f"# WorkPulse {analysis['label']}分析",
        "",
        f"- **活跃时间**: {analysis['summary']['active_time']}",
        f"- **空闲时间**: {analysis['summary']['idle_time']}",
        f"- **上下文切换**: {analysis['summary']['context_switches']}",
        "",
        "## 观察",
        "",
    ]

    for item in analysis["findings"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 建议", ""])
    for item in analysis["suggestions"]:
        lines.append(f"- {item}")

    return "\n".join(lines)
