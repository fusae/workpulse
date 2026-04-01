"""活动数据导出。"""

import csv
import io
import json
from typing import List, Optional

from workpulse.reporter import _get_time_range
from workpulse.tracker import POLL_INTERVAL, get_db


def export_activities(
    fmt: str = "csv",
    source: str = "active",
    period: str = "today",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    start, end, _ = _get_time_range(period, start_date=start_date, end_date=end_date)
    rows = _load_rows(source, start, end)
    if fmt == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2)
    return _to_csv(rows)


def _load_rows(source: str, start: str, end: str) -> List[dict]:
    conn = get_db()
    table_map = {
        "active": "activities",
        "archive": "activity_archive",
    }

    if source == "all":
        rows = []
        for table in ("activities", "activity_archive"):
            rows.extend(_query_table(conn, table, start, end))
        conn.close()
        rows.sort(key=lambda item: item["timestamp"])
        return rows

    table = table_map[source]
    rows = _query_table(conn, table, start, end)
    conn.close()
    return rows


def _query_table(conn, table: str, start: str, end: str) -> List[dict]:
    rows = conn.execute(
        f"""
        SELECT timestamp, app_name, window_title, category, is_idle, platform,
               COALESCE(sample_seconds, ?) AS sample_seconds
        FROM {table}
        WHERE timestamp >= ? AND timestamp < ?
        ORDER BY timestamp ASC
        """,
        (POLL_INTERVAL, start, end),
    ).fetchall()
    return [dict(row) for row in rows]


def _to_csv(rows: List[dict]) -> str:
    if not rows:
        return "timestamp,app_name,window_title,category,is_idle,platform,sample_seconds\n"

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["timestamp", "app_name", "window_title", "category", "is_idle", "platform", "sample_seconds"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
