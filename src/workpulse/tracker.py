"""核心追踪器 - 轮询前台窗口并记录到 SQLite"""

import logging
import os
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
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


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            app_name TEXT NOT NULL,
            window_title TEXT,
            category TEXT,
            is_idle BOOLEAN DEFAULT FALSE,
            platform TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activities_timestamp
        ON activities(timestamp)
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
        timestamp = datetime.now(timezone.utc).isoformat()
        platform_name = "macos" if sys.platform == "darwin" else "windows"

        row = (timestamp, app_name, window_title, category, is_idle, platform_name)

        try:
            conn = self._get_conn()
            # 先写入缓冲区中的数据
            if self._buffer:
                conn.executemany(
                    "INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    self._buffer,
                )
                logger.info("缓冲区 %d 条记录已写入", len(self._buffer))
                self._buffer.clear()

            conn.execute(
                "INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform) "
                "VALUES (?, ?, ?, ?, ?, ?)",
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


def run_tracker():
    """运行追踪循环。"""
    _setup_logging()
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
        os.kill(pid, signal.SIGTERM)
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
    pid = int(PID_PATH.read_text().strip())
    try:
        os.kill(pid, 0)  # 检查进程是否存在
        return True
    except (ProcessLookupError, PermissionError):
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
    cursor = conn.execute(
        "DELETE FROM activities WHERE timestamp < ?", (before_date,)
    )
    conn.commit()
    print(f"已删除 {cursor.rowcount} 条记录（{before_date} 之前）")
    conn.close()


if __name__ == "__main__":
    run_tracker()
