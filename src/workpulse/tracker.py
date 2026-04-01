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
from workpulse.platform.base import get_platform

logger = logging.getLogger("workpulse")

DATA_DIR = Path.home() / ".workpulse"
DB_PATH = DATA_DIR / "activity.db"
PID_PATH = DATA_DIR / "workpulse.pid"
LOG_PATH = DATA_DIR / "workpulse.log"

POLL_INTERVAL = 30  # 秒
ARCHIVE_RETENTION_DAYS = 90


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
            sample_seconds INTEGER NOT NULL DEFAULT 30
        )
    """)
    _ensure_column(conn, "activities", "sample_seconds", "sample_seconds INTEGER NOT NULL DEFAULT 30")
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
            sample_seconds INTEGER NOT NULL DEFAULT 30
        )
    """)
    _ensure_column(conn, "activity_archive", "sample_seconds", "sample_seconds INTEGER NOT NULL DEFAULT 30")
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


def archive_old_activities(retention_days: int = ARCHIVE_RETENTION_DAYS, conn: Optional[sqlite3.Connection] = None) -> int:
    """将保留期之外的数据转移到归档表。"""
    owns_conn = conn is None
    if conn is None:
        conn = get_db()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    rows = conn.execute(
        """
        SELECT id, timestamp, app_name, window_title, category, is_idle, platform, sample_seconds
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
            archived_at, original_id, timestamp, app_name, window_title, category, is_idle, platform, sample_seconds
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        self.running = False
        self._conn: Optional[sqlite3.Connection] = None
        self._buffer: list = []  # 写入失败时的缓冲队列

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_db()
        return self._conn

    def _record(self):
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

        row = (timestamp, app_name, window_title, category, is_idle, platform_name, POLL_INTERVAL)

        try:
            conn = self._get_conn()
            # 先写入缓冲区中的数据
            if self._buffer:
                conn.executemany(
                    "INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform, sample_seconds) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    self._buffer,
                )
                logger.info("缓冲区 %d 条记录已写入", len(self._buffer))
                self._buffer.clear()

            conn.execute(
                "INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform, sample_seconds) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            conn.commit()
            logger.debug("记录: %s | %s | %s | idle=%s", app_name, window_title[:50], category, is_idle)
        except sqlite3.Error as e:
            logger.warning("SQLite 写入失败，缓存到内存: %s", e)
            self._buffer.append(row)

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
            time.sleep(POLL_INTERVAL)

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
    else:
        print("WorkPulse 未在运行")


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
