"""报告生成 - 按时间范围生成工作时间分配报告"""

import html
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from workpulse.tracker import get_db, POLL_INTERVAL


def _format_duration(seconds: float) -> str:
    """将秒数格式化为 Xh Xm 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _get_time_range(period: str, now: Optional[datetime] = None) -> Tuple[str, str]:
    """根据 period 返回 UTC 时间范围 (start, end)。"""
    local_now = now.astimezone() if now is not None else datetime.now().astimezone()
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        start = today_start
    elif period == "yesterday":
        start = today_start - timedelta(days=1)
        local_now = today_start  # 到今天 0 点
    elif period == "week":
        # 本周一开始
        weekday = local_now.weekday()
        start = today_start - timedelta(days=weekday)
    else:
        start = today_start

    return (
        start.astimezone(timezone.utc).isoformat(),
        local_now.astimezone(timezone.utc).isoformat(),
    )


def _get_app_rows(conn, start: str, end: str) -> List[Dict[str, object]]:
    rows = conn.execute("""
        SELECT app_name, COALESCE(category, '其他') as category, COUNT(*) as samples
        FROM activities
        WHERE timestamp >= ? AND timestamp < ? AND is_idle = 0
        GROUP BY app_name, category
        ORDER BY samples DESC
    """, (start, end)).fetchall()

    apps: Dict[str, Dict[str, object]] = {}
    for row in rows:
        app = apps.setdefault(
            row["app_name"],
            {"app_name": row["app_name"], "samples": 0, "categories": []},
        )
        app["samples"] += row["samples"]
        app["categories"].append((row["category"], row["samples"]))

    app_rows = []
    for app in apps.values():
        categories = app["categories"]
        dominant_category = max(categories, key=lambda item: item[1])[0]
        if len(categories) == 1:
            category_label = dominant_category
        else:
            category_label = f"多种({dominant_category})"

        app_rows.append(
            {
                "app_name": app["app_name"],
                "samples": app["samples"],
                "category": category_label,
            }
        )

    app_rows.sort(key=lambda item: item["samples"], reverse=True)
    return app_rows[:15]


def get_report_snapshot(period: str = "today") -> Dict[str, object]:
    start, end = _get_time_range(period)
    conn = get_db()

    category_rows = conn.execute("""
        SELECT category, COUNT(*) as samples, is_idle
        FROM activities
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY category, is_idle
        ORDER BY samples DESC
    """, (start, end)).fetchall()

    app_rows = _get_app_rows(conn, start, end)

    title_rows = conn.execute("""
        SELECT app_name, window_title, COUNT(*) as samples
        FROM activities
        WHERE timestamp >= ? AND timestamp < ? AND is_idle = 0
          AND window_title != ''
        GROUP BY app_name, window_title
        ORDER BY samples DESC
        LIMIT 10
    """, (start, end)).fetchall()

    total = conn.execute("""
        SELECT COUNT(*) as cnt FROM activities
        WHERE timestamp >= ? AND timestamp < ?
    """, (start, end)).fetchone()["cnt"]
    conn.close()

    period_labels = {"today": "今日", "yesterday": "昨日", "week": "本周"}
    label = period_labels.get(period, period)
    if total == 0:
        return {
            "period": period,
            "label": label,
            "time_range": {"start": start, "end": end},
            "total_samples": 0,
            "active_total": 0,
            "idle_time": 0,
            "categories": [],
            "apps": [],
            "titles": [],
        }

    categories = {}
    idle_time = 0
    for row in category_rows:
        seconds = row["samples"] * POLL_INTERVAL
        if row["is_idle"]:
            idle_time += seconds
        else:
            cat = row["category"] or "其他"
            categories[cat] = categories.get(cat, 0) + seconds

    active_total = sum(categories.values())
    return {
        "period": period,
        "label": label,
        "time_range": {"start": start, "end": end},
        "total_samples": total,
        "active_total": active_total,
        "idle_time": idle_time,
        "categories": [
            {
                "category": cat,
                "seconds": seconds,
                "pct": (seconds / active_total * 100) if active_total > 0 else 0,
            }
            for cat, seconds in sorted(categories.items(), key=lambda x: -x[1])
        ],
        "apps": app_rows,
        "titles": [dict(row) for row in title_rows],
    }


def generate_report(period: str = "today", fmt: str = "table", include_analysis: bool = False) -> str:
    """生成报告

    Args:
        period: today / yesterday / week
        fmt: table / markdown
    """
    snapshot = get_report_snapshot(period)
    if snapshot["total_samples"] == 0:
        return f"[{period}] 暂无数据"
    categories = {item["category"]: item["seconds"] for item in snapshot["categories"]}
    active_total = snapshot["active_total"]
    idle_time = snapshot["idle_time"]
    app_rows = snapshot["apps"]
    title_rows = snapshot["titles"]
    analysis = None
    if include_analysis:
        from workpulse.ai_analyzer import analyze_period
        analysis = analyze_period(period)

    if fmt == "html":
        return _format_html(period, categories, active_total, idle_time, app_rows, title_rows, analysis)
    if fmt == "markdown":
        return _format_markdown(period, categories, active_total, idle_time, app_rows, title_rows, analysis)
    else:
        return _format_table(period, categories, active_total, idle_time, app_rows, title_rows, analysis)


def _format_table(period, categories, active_total, idle_time, app_rows, title_rows, analysis=None) -> str:
    lines = []
    period_labels = {"today": "今日", "yesterday": "昨日", "week": "本周"}
    label = period_labels.get(period, period)

    lines.append(f"{'=' * 50}")
    lines.append(f"  WorkPulse {label}报告")
    lines.append(f"{'=' * 50}")
    lines.append("")

    # 总览
    lines.append(f"  活跃时间: {_format_duration(active_total)}")
    lines.append(f"  空闲时间: {_format_duration(idle_time)}")
    lines.append("")

    # 分类汇总
    lines.append("  [分类统计]")
    lines.append(f"  {'分类':<10} {'时长':<10} {'占比':<8}")
    lines.append(f"  {'-' * 30}")
    for cat, seconds in sorted(categories.items(), key=lambda x: -x[1]):
        pct = (seconds / active_total * 100) if active_total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {cat:<10} {_format_duration(seconds):<10} {pct:5.1f}% {bar}")
    lines.append("")

    # 应用汇总
    lines.append("  [应用统计]")
    lines.append(f"  {'应用':<20} {'时长':<10} {'分类':<8}")
    lines.append(f"  {'-' * 40}")
    for row in app_rows:
        seconds = row["samples"] * POLL_INTERVAL
        lines.append(f"  {row['app_name']:<20} {_format_duration(seconds):<10} {row['category']}")
    lines.append("")

    # 窗口标题 Top 10
    if title_rows:
        lines.append("  [活动详情 Top 10]")
        lines.append(f"  {'应用':<15} {'窗口标题':<35} {'时长':<8}")
        lines.append(f"  {'-' * 60}")
        for row in title_rows:
            title = row["window_title"]
            if len(title) > 32:
                title = title[:32] + "..."
            seconds = row["samples"] * POLL_INTERVAL
            lines.append(f"  {row['app_name']:<15} {title:<35} {_format_duration(seconds)}")

    if analysis:
        lines.append("")
        lines.append("  [分析摘要]")
        for item in analysis["findings"]:
            lines.append(f"  - {item}")
        for item in analysis["suggestions"]:
            lines.append(f"  - 建议：{item}")

    lines.append("")
    lines.append(f"{'=' * 50}")
    return "\n".join(lines)


def _format_markdown(period, categories, active_total, idle_time, app_rows, title_rows, analysis=None) -> str:
    lines = []
    period_labels = {"today": "今日", "yesterday": "昨日", "week": "本周"}
    label = period_labels.get(period, period)

    lines.append(f"# WorkPulse {label}报告")
    lines.append("")
    lines.append(f"- **活跃时间**: {_format_duration(active_total)}")
    lines.append(f"- **空闲时间**: {_format_duration(idle_time)}")
    lines.append("")

    # 分类汇总
    lines.append("## 分类统计")
    lines.append("")
    lines.append("| 分类 | 时长 | 占比 |")
    lines.append("|------|------|------|")
    for cat, seconds in sorted(categories.items(), key=lambda x: -x[1]):
        pct = (seconds / active_total * 100) if active_total > 0 else 0
        lines.append(f"| {cat} | {_format_duration(seconds)} | {pct:.1f}% |")
    lines.append("")

    # 应用汇总
    lines.append("## 应用统计")
    lines.append("")
    lines.append("| 应用 | 时长 | 分类 |")
    lines.append("|------|------|------|")
    for row in app_rows:
        seconds = row["samples"] * POLL_INTERVAL
        lines.append(f"| {row['app_name']} | {_format_duration(seconds)} | {row['category']} |")
    lines.append("")

    # 窗口标题 Top 10
    if title_rows:
        lines.append("## 活动详情 Top 10")
        lines.append("")
        lines.append("| 应用 | 窗口标题 | 时长 |")
        lines.append("|------|----------|------|")
        for row in title_rows:
            title = row["window_title"]
            if len(title) > 50:
                title = title[:50] + "..."
            seconds = row["samples"] * POLL_INTERVAL
            lines.append(f"| {row['app_name']} | {title} | {_format_duration(seconds)} |")

    if analysis:
        lines.extend(["", "## 分析摘要", ""])
        for item in analysis["findings"]:
            lines.append(f"- {item}")
        for item in analysis["suggestions"]:
            lines.append(f"- 建议：{item}")

    return "\n".join(lines)


def _format_html(period, categories, active_total, idle_time, app_rows, title_rows, analysis=None) -> str:
    period_labels = {"today": "今日", "yesterday": "昨日", "week": "本周"}
    label = period_labels.get(period, period)

    category_rows = "".join(
        f"<tr><td>{html.escape(cat)}</td><td>{_format_duration(seconds)}</td><td>{(seconds / active_total * 100) if active_total else 0:.1f}%</td></tr>"
        for cat, seconds in sorted(categories.items(), key=lambda x: -x[1])
    )
    app_table_rows = "".join(
        f"<tr><td>{html.escape(str(row['app_name']))}</td><td>{_format_duration(row['samples'] * POLL_INTERVAL)}</td><td>{html.escape(str(row['category']))}</td></tr>"
        for row in app_rows
    )
    title_table_rows = "".join(
        f"<tr><td>{html.escape(str(row['app_name']))}</td><td>{html.escape(str(row['window_title']))}</td><td>{_format_duration(row['samples'] * POLL_INTERVAL)}</td></tr>"
        for row in title_rows
    )

    analysis_block = ""
    if analysis:
        findings = "".join(f"<li>{html.escape(item)}</li>" for item in analysis["findings"])
        suggestions = "".join(f"<li>{html.escape(item)}</li>" for item in analysis["suggestions"])
        analysis_block = f"""
        <section>
          <h2>分析摘要</h2>
          <h3>观察</h3>
          <ul>{findings}</ul>
          <h3>建议</h3>
          <ul>{suggestions}</ul>
        </section>
        """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WorkPulse {label}报告</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --card: #fffdf8;
      --ink: #1f1b16;
      --muted: #6f6254;
      --accent: #b65c2d;
      --line: #e3d8c8;
    }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #efe7da 0%, var(--bg) 100%);
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    .hero, section {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 18px;
      box-shadow: 0 12px 30px rgba(79, 58, 38, 0.08);
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .metric {{
      padding: 14px;
      border-radius: 14px;
      background: #fbf7ef;
      border: 1px solid var(--line);
    }}
    .metric .label {{
      display: block;
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 6px;
    }}
    .metric .value {{
      font-size: 28px;
      color: var(--accent);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
    }}
    th {{
      color: var(--muted);
      font-weight: normal;
    }}
    h1, h2, h3 {{
      margin-top: 0;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>WorkPulse {label}报告</h1>
      <div class="metrics">
        <div class="metric"><span class="label">活跃时间</span><span class="value">{_format_duration(active_total)}</span></div>
        <div class="metric"><span class="label">空闲时间</span><span class="value">{_format_duration(idle_time)}</span></div>
      </div>
    </section>
    <section>
      <h2>分类统计</h2>
      <table>
        <thead><tr><th>分类</th><th>时长</th><th>占比</th></tr></thead>
        <tbody>{category_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>应用统计</h2>
      <table>
        <thead><tr><th>应用</th><th>时长</th><th>分类</th></tr></thead>
        <tbody>{app_table_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>活动详情 Top 10</h2>
      <table>
        <thead><tr><th>应用</th><th>窗口标题</th><th>时长</th></tr></thead>
        <tbody>{title_table_rows}</tbody>
      </table>
    </section>
    {analysis_block}
  </main>
</body>
</html>
"""
