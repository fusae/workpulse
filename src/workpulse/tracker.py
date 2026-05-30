"""核心追踪器 - 轮询前台窗口并记录到 SQLite"""

import json
import logging
import os
import signal
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from workpulse.classifier import Classifier
from workpulse.context import collect_project_context, dumps_context, summarize_text_outputs, terminal_evidence
from workpulse.intent import infer_intent
from workpulse.platform.base import get_platform
from workpulse.screen import ScreenSample, capture_screen_sample
from workpulse.settings import DEFAULT_POLL_INTERVAL, load_settings

logger = logging.getLogger("workpulse")

DATA_DIR = Path.home() / ".workpulse"
DB_PATH = DATA_DIR / "activity.db"
PID_PATH = DATA_DIR / "workpulse.pid"
LOG_PATH = DATA_DIR / "workpulse.log"
PAUSE_PATH = DATA_DIR / "pause.json"

POLL_INTERVAL = DEFAULT_POLL_INTERVAL  # 历史兼容默认值


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str):
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            app_name TEXT NOT NULL,
            window_title TEXT,
            category TEXT,
            is_idle BOOLEAN DEFAULT FALSE,
            platform TEXT NOT NULL,
            sample_seconds INTEGER NOT NULL DEFAULT 30,
            browser_url TEXT,
            screenshot_path TEXT,
            screenshot_hash TEXT,
            ocr_text TEXT,
            ocr_status TEXT,
            screen_summary TEXT,
            screen_skipped_reason TEXT,
            project_name TEXT,
            project_evidence TEXT,
            intent TEXT,
            intent_evidence TEXT,
            text_evidence TEXT,
            terminal_evidence TEXT
        )
    """)
    _ensure_column(conn, "activities", "sample_seconds", "sample_seconds INTEGER NOT NULL DEFAULT 30")
    _ensure_column(conn, "activities", "browser_url", "browser_url TEXT")
    _ensure_column(conn, "activities", "screenshot_path", "screenshot_path TEXT")
    _ensure_column(conn, "activities", "screenshot_hash", "screenshot_hash TEXT")
    _ensure_column(conn, "activities", "ocr_text", "ocr_text TEXT")
    _ensure_column(conn, "activities", "ocr_status", "ocr_status TEXT")
    _ensure_column(conn, "activities", "screen_summary", "screen_summary TEXT")
    _ensure_column(conn, "activities", "screen_skipped_reason", "screen_skipped_reason TEXT")
    _ensure_column(conn, "activities", "project_name", "project_name TEXT")
    _ensure_column(conn, "activities", "project_evidence", "project_evidence TEXT")
    _ensure_column(conn, "activities", "intent", "intent TEXT")
    _ensure_column(conn, "activities", "intent_evidence", "intent_evidence TEXT")
    _ensure_column(conn, "activities", "text_evidence", "text_evidence TEXT")
    _ensure_column(conn, "activities", "terminal_evidence", "terminal_evidence TEXT")
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activities_timestamp
        ON activities(timestamp)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_archive (
            id INTEGER PRIMARY KEY,
            archived_at TEXT NOT NULL,
            original_id INTEGER,
            timestamp TEXT NOT NULL,
            app_name TEXT NOT NULL,
            window_title TEXT,
            category TEXT,
            is_idle BOOLEAN DEFAULT FALSE,
            platform TEXT NOT NULL,
            sample_seconds INTEGER NOT NULL DEFAULT 30,
            browser_url TEXT,
            screenshot_path TEXT,
            screenshot_hash TEXT,
            ocr_text TEXT,
            ocr_status TEXT,
            screen_summary TEXT,
            screen_skipped_reason TEXT,
            project_name TEXT,
            project_evidence TEXT,
            intent TEXT,
            intent_evidence TEXT,
            text_evidence TEXT,
            terminal_evidence TEXT
        )
    """)
    _ensure_column(conn, "activity_archive", "sample_seconds", "sample_seconds INTEGER NOT NULL DEFAULT 30")
    _ensure_column(conn, "activity_archive", "browser_url", "browser_url TEXT")
    _ensure_column(conn, "activity_archive", "screenshot_path", "screenshot_path TEXT")
    _ensure_column(conn, "activity_archive", "screenshot_hash", "screenshot_hash TEXT")
    _ensure_column(conn, "activity_archive", "ocr_text", "ocr_text TEXT")
    _ensure_column(conn, "activity_archive", "ocr_status", "ocr_status TEXT")
    _ensure_column(conn, "activity_archive", "screen_summary", "screen_summary TEXT")
    _ensure_column(conn, "activity_archive", "screen_skipped_reason", "screen_skipped_reason TEXT")
    _ensure_column(conn, "activity_archive", "project_name", "project_name TEXT")
    _ensure_column(conn, "activity_archive", "project_evidence", "project_evidence TEXT")
    _ensure_column(conn, "activity_archive", "intent", "intent TEXT")
    _ensure_column(conn, "activity_archive", "intent_evidence", "intent_evidence TEXT")
    _ensure_column(conn, "activity_archive", "text_evidence", "text_evidence TEXT")
    _ensure_column(conn, "activity_archive", "terminal_evidence", "terminal_evidence TEXT")
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_archive_timestamp
        ON activity_archive(timestamp)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracker_events (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT,
            platform TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tracker_events_timestamp
        ON tracker_events(timestamp)
    """)
    conn.commit()


def _setup_logging():
    from logging.handlers import RotatingFileHandler

    _ensure_data_dir()
    if logger.handlers:
        return

    handler = RotatingFileHandler(
        LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def get_db() -> sqlite3.Connection:
    _ensure_data_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_platform_name() -> str:
    return "macos" if sys.platform == "darwin" else "windows"


def record_event(event_type: str, details: Optional[dict] = None, conn: Optional[sqlite3.Connection] = None):
    """记录追踪器事件。"""
    owns_conn = conn is None
    if conn is None:
        conn = get_db()

    payload = json.dumps(details, ensure_ascii=False) if details else None
    conn.execute(
        "INSERT INTO tracker_events (timestamp, event_type, details, platform) VALUES (?, ?, ?, ?)",
        (_utc_now(), event_type, payload, _get_platform_name()),
    )
    conn.commit()

    if owns_conn:
        conn.close()


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_pause_status(now: Optional[datetime] = None) -> dict:
    """Return pause status and clear expired pause state."""
    if now is None:
        now = datetime.now(timezone.utc)
    if not PAUSE_PATH.exists():
        return {"paused": False, "until": None}

    try:
        status = json.loads(PAUSE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        PAUSE_PATH.unlink(missing_ok=True)
        return {"paused": False, "until": None}

    until = _parse_iso_datetime(status.get("until"))
    if until is not None and until <= now:
        PAUSE_PATH.unlink(missing_ok=True)
        return {"paused": False, "until": None}

    return {
        "paused": bool(status.get("paused", True)),
        "until": until.isoformat() if until else None,
        "reason": status.get("reason", "manual"),
    }


def pause_tracking(minutes: Optional[int] = None):
    _ensure_data_dir()
    until = None
    if minutes is not None:
        if minutes < 1:
            minutes = 1
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    payload = {
        "paused": True,
        "until": until.isoformat() if until else None,
        "reason": "manual",
    }
    PAUSE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    record_event("paused", {"minutes": minutes, "until": payload["until"]})
    if until:
        print(f"WorkPulse 已暂停至 {until.isoformat()}")
    else:
        print("WorkPulse 已暂停")


def resume_tracking():
    existed = PAUSE_PATH.exists()
    PAUSE_PATH.unlink(missing_ok=True)
    record_event("resumed", {"was_paused": existed})
    print("WorkPulse 已恢复")


def archive_old_activities(retention_days: Optional[int] = None, conn: Optional[sqlite3.Connection] = None) -> int:
    """将保留期之外的数据转移到归档表。"""
    if retention_days is None:
        retention_days = load_settings().archive_retention_days
    owns_conn = conn is None
    if conn is None:
        conn = get_db()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    rows = conn.execute(
        """
        SELECT id, timestamp, app_name, window_title, category, is_idle, platform, sample_seconds,
               browser_url, screenshot_path, screenshot_hash, ocr_text, ocr_status, screen_summary, screen_skipped_reason,
               project_name, project_evidence, intent, intent_evidence, text_evidence, terminal_evidence
        FROM activities
        WHERE timestamp < ?
        ORDER BY timestamp
        """,
        (cutoff,),
    ).fetchall()

    if not rows:
        if owns_conn:
            conn.close()
        return 0

    archived_at = _utc_now()
    conn.executemany(
        """
        INSERT INTO activity_archive (
            archived_at, original_id, timestamp, app_name, window_title, category, is_idle, platform, sample_seconds,
            browser_url, screenshot_path, screenshot_hash, ocr_text, ocr_status, screen_summary, screen_skipped_reason,
            project_name, project_evidence, intent, intent_evidence, text_evidence, terminal_evidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                archived_at,
                row["id"],
                row["timestamp"],
                row["app_name"],
                row["window_title"],
                row["category"],
                row["is_idle"],
                row["platform"],
                row["sample_seconds"],
                row["browser_url"],
                row["screenshot_path"],
                row["screenshot_hash"],
                row["ocr_text"],
                row["ocr_status"],
                row["screen_summary"],
                row["screen_skipped_reason"],
                row["project_name"],
                row["project_evidence"],
                row["intent"],
                row["intent_evidence"],
                row["text_evidence"],
                row["terminal_evidence"],
            )
            for row in rows
        ],
    )
    conn.executemany(
        "DELETE FROM activities WHERE id = ?",
        [(row["id"],) for row in rows],
    )
    conn.commit()

    logger.info("已归档 %d 条活动记录（保留 %d 天）", len(rows), retention_days)
    record_event(
        "archive_completed",
        {"archived_rows": len(rows), "retention_days": retention_days, "cutoff": cutoff},
        conn=conn,
    )

    if owns_conn:
        conn.close()
    return len(rows)


def _recover_previous_session():
    """识别未清理的旧 PID，并记录恢复事件。"""
    if not PID_PATH.exists():
        return

    try:
        pid = int(PID_PATH.read_text().strip())
    except ValueError:
        PID_PATH.unlink()
        return

    if _process_exists(pid):
        return

    logger.warning("检测到上次运行未正常清理的 PID 文件: %s", pid)
    record_event("recovered_stale_pid", {"stale_pid": pid})
    PID_PATH.unlink()


class Tracker:
    def __init__(self):
        self.platform = get_platform()
        self.classifier = Classifier()
        self.settings = load_settings()
        self.running = False
        self._conn: Optional[sqlite3.Connection] = None
        self._buffer: list = []  # 写入失败时的缓冲队列
        self._last_screen_capture_at = 0.0

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_db()
        return self._conn

    def _record(self):
        if get_pause_status()["paused"]:
            return

        window = self.platform.get_active_window()
        idle_seconds = self.platform.get_idle_seconds()
        idle_threshold = self.classifier.idle_threshold_minutes * 60
        is_idle = idle_seconds >= idle_threshold

        if window is None:
            app_name = "unknown"
            window_title = ""
        else:
            app_name = window.app_name
            window_title = window.window_title

        category = self.classifier.classify(app_name, window_title)
        timestamp = _utc_now()
        platform_name = _get_platform_name()
        screen_sample = self._screen_sample(app_name, window_title)
        project_context = collect_project_context(self.settings)
        text_evidence = summarize_text_outputs(project_context)
        terminal_summary = terminal_evidence(app_name, window_title)
        intent, intent_evidence = infer_intent(
            app_name,
            window_title,
            screen_sample.url,
            screen_sample.ocr_text,
            project_context["primary_project"],
        )

        row = (
            timestamp,
            app_name,
            window_title,
            category,
            is_idle,
            platform_name,
            self.settings.poll_interval_seconds,
            screen_sample.url,
            screen_sample.screenshot_path,
            screen_sample.screenshot_hash,
            screen_sample.ocr_text,
            screen_sample.ocr_status,
            screen_sample.screen_summary,
            screen_sample.skipped_reason,
            project_context["primary_project"],
            dumps_context(project_context),
            intent,
            intent_evidence,
            text_evidence,
            terminal_summary,
        )

        try:
            conn = self._get_conn()
            # 先写入缓冲区中的数据
            if self._buffer:
                conn.executemany(
                    """
                    INSERT INTO activities (
                        timestamp, app_name, window_title, category, is_idle, platform, sample_seconds,
                        browser_url, screenshot_path, screenshot_hash, ocr_text, ocr_status, screen_summary, screen_skipped_reason,
                        project_name, project_evidence, intent, intent_evidence, text_evidence, terminal_evidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._buffer,
                )
                logger.info("缓冲区 %d 条记录已写入", len(self._buffer))
                self._buffer.clear()

            conn.execute(
                """
                INSERT INTO activities (
                    timestamp, app_name, window_title, category, is_idle, platform, sample_seconds,
                    browser_url, screenshot_path, screenshot_hash, ocr_text, ocr_status, screen_summary, screen_skipped_reason,
                    project_name, project_evidence, intent, intent_evidence, text_evidence, terminal_evidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            conn.commit()
            logger.debug("记录: %s | %s | %s | idle=%s", app_name, window_title[:50], category, is_idle)
        except sqlite3.Error as e:
            logger.warning("SQLite 写入失败，缓存到内存: %s", e)
            self._buffer.append(row)

    def _screen_sample(self, app_name: str, window_title: str) -> ScreenSample:
        now = time.time()
        due = (
            now - self._last_screen_capture_at
            >= self.settings.screen_capture_interval_seconds
        )
        sample = capture_screen_sample(app_name, window_title, self.settings, force=due)
        if sample.screenshot_hash or sample.skipped_reason:
            self._last_screen_capture_at = now
        return sample

    def run(self):
        _setup_logging()
        logger.info("WorkPulse 追踪器启动")
        self.running = True

        def _stop(signum, frame):
            logger.info("收到停止信号 (%s)", signum)
            self.running = False

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        while self.running:
            try:
                self._record()
            except Exception as e:
                logger.error("记录异常: %s", e, exc_info=True)
            time.sleep(self.settings.poll_interval_seconds)

        if self._conn:
            self._conn.close()
        logger.info("WorkPulse 追踪器已停止")


def _wait_for_daemon_pid(timeout_seconds: float = 5.0) -> Optional[int]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if PID_PATH.exists():
            try:
                return int(PID_PATH.read_text().strip())
            except ValueError:
                pass
        time.sleep(0.1)
    return None


def _process_exists(pid: int) -> bool:
    """检查进程是否存在。"""
    if sys.platform == "win32":
        try:
            import psutil
        except ImportError:
            logger.warning("Windows 环境缺少 psutil，无法可靠检查进程状态")
            return False
        return psutil.pid_exists(pid)

    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _terminate_process(pid: int):
    """终止指定进程。"""
    if sys.platform == "win32":
        try:
            import psutil
        except ImportError as exc:
            raise RuntimeError("Windows 环境缺少 psutil，无法停止追踪器") from exc

        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess as exc:
            raise ProcessLookupError(pid) from exc

        process.terminate()
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            process.kill()
        return

    os.kill(pid, signal.SIGTERM)


def run_tracker():
    """运行追踪循环。"""
    _setup_logging()
    _recover_previous_session()
    archive_old_activities()
    tracker = Tracker()
    tracker.run()


def start_daemon():
    """启动后台追踪守护进程"""
    _ensure_data_dir()

    if is_running():
        print("WorkPulse 已在运行中")
        return

    if sys.platform == "win32":
        # Windows: 使用 subprocess 启动后台进程
        import subprocess

        # 启动一个新的 Python 进程运行追踪器
        creation_flags = 0
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            creation_flags |= subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, 'DETACHED_PROCESS'):
            creation_flags |= subprocess.DETACHED_PROCESS

        process = subprocess.Popen(
            [sys.executable, "-m", "workpulse.tracker"],
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        PID_PATH.write_text(str(process.pid))
        print(f"WorkPulse 已启动 (PID: {process.pid})")
    else:
        # Unix/macOS: 使用 fork
        pid = os.fork()
        if pid > 0:
            daemon_pid = _wait_for_daemon_pid() or pid
            print(f"WorkPulse 已启动 (PID: {daemon_pid})")
            return

        # 子进程 - 成为守护进程
        os.setsid()
        pid2 = os.fork()
        if pid2 > 0:
            os._exit(0)

        # 写入 PID 文件
        PID_PATH.write_text(str(os.getpid()))

        # 重定向标准输出
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

        try:
            run_tracker()
        finally:
            if PID_PATH.exists():
                PID_PATH.unlink()


def stop_daemon():
    """停止后台追踪"""
    if not PID_PATH.exists():
        print("WorkPulse 未在运行")
        return

    pid = int(PID_PATH.read_text().strip())
    try:
        _terminate_process(pid)
        print(f"WorkPulse 已停止 (PID: {pid})")
    except ProcessLookupError:
        print("进程已不存在，清理 PID 文件")
    finally:
        if PID_PATH.exists():
            PID_PATH.unlink()


def is_running() -> bool:
    """检查追踪器是否在运行"""
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text().strip())
    except ValueError:
        PID_PATH.unlink()
        return False

    if _process_exists(pid):
        return True

    if PID_PATH.exists():
        PID_PATH.unlink()
    return False


def show_status():
    """显示运行状态"""
    if is_running():
        pid = int(PID_PATH.read_text().strip())
        print(f"WorkPulse 运行中 (PID: {pid})")

        conn = get_db()
        row = conn.execute(
            "SELECT COUNT(*) as cnt, MIN(timestamp) as first, MAX(timestamp) as last FROM activities"
        ).fetchone()
        conn.close()
        if row["cnt"] > 0:
            print(f"  记录数: {row['cnt']}")
            print(f"  首条记录: {row['first']}")
            print(f"  最新记录: {row['last']}")
        pause = get_pause_status()
        if pause["paused"]:
            print(f"  暂停中: {pause['until'] or '手动恢复前'}")
    else:
        print("WorkPulse 未在运行")
        pause = get_pause_status()
        if pause["paused"]:
            print(f"  暂停中: {pause['until'] or '手动恢复前'}")


def prune_data(before_date: str):
    """清理指定日期之前的数据"""
    conn = get_db()
    active_cursor = conn.execute(
        "DELETE FROM activities WHERE timestamp < ?", (before_date,)
    )
    archive_cursor = conn.execute(
        "DELETE FROM activity_archive WHERE timestamp < ?", (before_date,)
    )
    events_cursor = conn.execute(
        "DELETE FROM tracker_events WHERE timestamp < ?", (before_date,)
    )
    deleted = (
        active_cursor.rowcount
        + archive_cursor.rowcount
        + events_cursor.rowcount
    )
    record_event(
        "manual_prune",
        {"before_date": before_date, "deleted_rows": deleted},
        conn=conn,
    )
    conn.commit()
    print(f"已删除 {deleted} 条记录（{before_date} 之前）")
    conn.close()


if __name__ == "__main__":
    run_tracker()
