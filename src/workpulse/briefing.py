"""日报摘要生成。"""

import json
from typing import Dict

from workpulse.ai_analyzer import analyze_period


def generate_brief(
    period: str = "today",
    fmt: str = "markdown",
    start_date: str = None,
    end_date: str = None,
    provider: str = None,
) -> str:
    analysis = analyze_period(period, start_date=start_date, end_date=end_date, provider=provider)
    if fmt == "json":
        return json.dumps(_brief_payload(analysis), ensure_ascii=False, indent=2)
    return _format_markdown(analysis)


def _brief_payload(analysis: Dict[str, object]) -> Dict[str, object]:
    findings = analysis["findings"]
    suggestions = analysis["suggestions"]
    snapshot = analysis["snapshot"]
    top_categories = [item["category"] for item in snapshot["categories"][:3]]

    return {
        "period": analysis["period"],
        "label": analysis["label"],
        "summary": {
            "active_time": analysis["summary"]["active_time"],
            "idle_time": analysis["summary"]["idle_time"],
            "top_categories": top_categories,
            "source": analysis.get("source", "heuristic"),
        },
        "paragraph": _build_paragraph(analysis),
        "highlights": findings[:3],
        "next_actions": suggestions[:3],
    }


def _build_paragraph(analysis: Dict[str, object]) -> str:
    snapshot = analysis["snapshot"]
    active_time = analysis["summary"]["active_time"]
    idle_time = analysis["summary"]["idle_time"]
    categories = snapshot["categories"]
    top_category = categories[0]["category"] if categories else "其他"
    top_pct = categories[0]["pct"] if categories else 0

    sentence = (
        f"{analysis['label']}共记录活跃时间 {active_time}，空闲时间 {idle_time}。"
        f"主要精力集中在{top_category}，占活跃时间 {top_pct:.1f}%。"
    )

    if analysis["findings"]:
        sentence += f" 观察上，{analysis['findings'][0]}"
    if analysis["suggestions"]:
        sentence += f" 下一步建议优先：{analysis['suggestions'][0]}"
    return sentence


def _format_markdown(analysis: Dict[str, object]) -> str:
    payload = _brief_payload(analysis)
    lines = [
        f"# WorkPulse {payload['label']}摘要",
        "",
        f"- 分析来源：{payload['summary']['source']}",
        "",
        payload["paragraph"],
        "",
        "## 重点",
        "",
    ]
    for item in payload["highlights"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 下一步", ""])
    for item in payload["next_actions"]:
        lines.append(f"- {item}")

    return "\n".join(lines)
