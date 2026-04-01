"""自动日报生成。"""

import json
from typing import Dict, List, Optional

from workpulse.ai_analyzer import analyze_period
from workpulse.briefing import _brief_payload
from workpulse.llm_client import LLMError, llm_is_configured, request_json
from workpulse.settings import load_settings


def generate_daily_report(
    period: str = "today",
    fmt: str = "markdown",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    provider: Optional[str] = None,
) -> str:
    report = build_daily_report(period, start_date=start_date, end_date=end_date, provider=provider)
    if fmt == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    return _format_markdown(report)


def build_daily_report(
    period: str = "today",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, object]:
    analysis = analyze_period(period, start_date=start_date, end_date=end_date, provider=provider)
    brief = _brief_payload(analysis)
    settings = load_settings()
    selected_provider = provider or settings.analysis_provider or "heuristic"

    heuristic_report = _heuristic_daily_report(analysis, brief)
    llm_error = None
    source = heuristic_report["source"]

    if selected_provider in {"llm", "auto", "openai_compatible"} and llm_is_configured():
        try:
            llm_report = _llm_daily_report(analysis, brief)
            heuristic_report.update(llm_report)
            source = "llm"
        except LLMError as exc:
            llm_error = str(exc)

    heuristic_report["source"] = source
    heuristic_report["llm_error"] = llm_error
    return heuristic_report


def _heuristic_daily_report(analysis: Dict[str, object], brief: Dict[str, object]) -> Dict[str, object]:
    snapshot = analysis["snapshot"]
    completed = []
    for category in snapshot["categories"][:3]:
        completed.append(
            f"{category['category']}相关工作投入约 {analysis['summary']['active_time'] if category is snapshot['categories'][0] else _fmt_pct(category['pct'])}。"
        )

    outputs = []
    for item in snapshot["titles"][:5]:
        outputs.append(f"{item['app_name']} / {item['window_title']}")

    blockers = []
    if snapshot["idle_time"] > snapshot["active_total"] * 0.35 and snapshot["idle_time"] >= 1800:
        blockers.append("空闲或等待时间较高，可能存在会议排队、环境切换或中断。")
    if analysis["summary"]["context_switches"] >= 20:
        blockers.append("上下文切换较频繁，深度工作连续性不足。")
    if not blockers:
        blockers.append("未观察到明确阻塞，但建议继续通过规则细化提升识别精度。")

    next_steps = analysis["suggestions"][:3] or ["继续补充规则配置，提升项目识别和分析质量。"]

    return {
        "period": analysis["period"],
        "label": analysis["label"],
        "source": "heuristic",
        "title": f"WorkPulse {analysis['label']}日报",
        "summary": brief["paragraph"],
        "completed": completed[:3],
        "outputs": outputs or ["暂无可归纳的标题级输出。"],
        "blockers": blockers[:3],
        "next_steps": next_steps,
    }


def _llm_daily_report(analysis: Dict[str, object], brief: Dict[str, object]) -> Dict[str, object]:
    parsed = request_json(
        (
            "你是一个日报生成助手。请基于用户给出的活动摘要输出 JSON，"
            "字段必须包含 title, summary, completed, outputs, blockers, next_steps。"
            "其中 completed, outputs, blockers, next_steps 都必须是字符串数组。"
            "summary 应该是一段简短中文工作日报总结。"
        ),
        {
            "analysis": analysis,
            "brief": brief,
        },
    )

    return {
        "title": str(parsed.get("title", f"WorkPulse {analysis['label']}日报")),
        "summary": str(parsed.get("summary", brief["paragraph"])),
        "completed": [str(item) for item in parsed.get("completed", [])] or [brief["paragraph"]],
        "outputs": [str(item) for item in parsed.get("outputs", [])] or ["暂无可归纳的标题级输出。"],
        "blockers": [str(item) for item in parsed.get("blockers", [])] or ["暂无明确阻塞。"],
        "next_steps": [str(item) for item in parsed.get("next_steps", [])] or analysis["suggestions"][:3],
    }


def _fmt_pct(value: float) -> str:
    return f"占活跃时间 {value:.1f}%"


def _format_markdown(report: Dict[str, object]) -> str:
    lines = [
        f"# {report['title']}",
        "",
        f"- 分析来源：{report['source']}",
    ]

    if report.get("llm_error"):
        lines.append(f"- LLM 回退原因：{report['llm_error']}")

    lines.extend([
        "",
        "## 今日概述",
        "",
        report["summary"],
        "",
        "## 已完成",
        "",
    ])
    for item in report["completed"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 产出与线索", ""])
    for item in report["outputs"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 阻塞与风险", ""])
    for item in report["blockers"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 下一步", ""])
    for item in report["next_steps"]:
        lines.append(f"- {item}")

    return "\n".join(lines)
