"""WorkPulse 运行配置。"""

import importlib.resources
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

DATA_DIR = Path.home() / ".workpulse"
SETTINGS_PATH = DATA_DIR / "settings.yaml"
DEFAULT_POLL_INTERVAL = 30
DEFAULT_ARCHIVE_RETENTION_DAYS = 90
DEFAULT_SENSITIVE_APPS = ["1Password", "Keychain Access", "钥匙串访问"]
DEFAULT_SENSITIVE_TITLE_KEYWORDS = [
    "password",
    "密码",
    "验证码",
    "token",
    "secret",
    "private key",
]
DEFAULT_SENSITIVE_URL_KEYWORDS = [
    "/login",
    "password",
    "bank",
    "banking",
    "pay",
    "checkout",
]


@dataclass
class Settings:
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL
    archive_retention_days: int = DEFAULT_ARCHIVE_RETENTION_DAYS
    analysis_provider: str = "heuristic"
    llm_endpoint: str = "https://api.openai.com/v1/chat/completions"
    llm_model: str = "gpt-4o-mini"
    llm_api_key_env: str = "OPENAI_API_KEY"
    llm_timeout_seconds: int = 30
    screen_capture_enabled: bool = True
    screen_capture_interval_seconds: int = 60
    screen_ocr_enabled: bool = True
    keep_raw_screenshots: bool = False
    screenshot_retention_days: int = 7
    sensitive_apps: List[str] = None
    sensitive_title_keywords: List[str] = None
    sensitive_url_keywords: List[str] = None
    project_roots: List[str] = None
    project_scan_recent_seconds: int = 300


def ensure_settings_file():
    if SETTINGS_PATH.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    package_files = getattr(importlib.resources, "files", None)
    if package_files is not None:
        default_text = (
            package_files("workpulse.config")
            .joinpath("default_settings.yaml")
            .read_text(encoding="utf-8")
        )
    else:
        default_text = importlib.resources.read_text(
            "workpulse.config",
            "default_settings.yaml",
            encoding="utf-8",
        )
    SETTINGS_PATH.write_text(default_text, encoding="utf-8")


def load_settings() -> Settings:
    ensure_settings_file()
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    poll_interval = int(config.get("poll_interval_seconds", DEFAULT_POLL_INTERVAL))
    retention_days = int(config.get("archive_retention_days", DEFAULT_ARCHIVE_RETENTION_DAYS))
    analysis_provider = str(config.get("analysis_provider", "heuristic"))
    llm_endpoint = str(config.get("llm_endpoint", "https://api.openai.com/v1/chat/completions"))
    llm_model = str(config.get("llm_model", "gpt-4o-mini"))
    llm_api_key_env = str(config.get("llm_api_key_env", "OPENAI_API_KEY"))
    llm_timeout = int(config.get("llm_timeout_seconds", 30))
    screen_capture_enabled = bool(config.get("screen_capture_enabled", True))
    screen_capture_interval = int(config.get("screen_capture_interval_seconds", 60))
    screen_ocr_enabled = bool(config.get("screen_ocr_enabled", True))
    keep_raw_screenshots = bool(config.get("keep_raw_screenshots", False))
    screenshot_retention_days = int(config.get("screenshot_retention_days", 7))
    sensitive_apps = list(config.get("sensitive_apps", DEFAULT_SENSITIVE_APPS) or [])
    sensitive_title_keywords = list(
        config.get("sensitive_title_keywords", DEFAULT_SENSITIVE_TITLE_KEYWORDS) or []
    )
    sensitive_url_keywords = list(
        config.get("sensitive_url_keywords", DEFAULT_SENSITIVE_URL_KEYWORDS) or []
    )
    project_roots = list(config.get("project_roots", []) or [])
    project_scan_recent_seconds = int(config.get("project_scan_recent_seconds", 300))

    if poll_interval < 5:
        poll_interval = 5
    if retention_days < 1:
        retention_days = 1
    if llm_timeout < 5:
        llm_timeout = 5
    if screen_capture_interval < poll_interval:
        screen_capture_interval = poll_interval
    if screenshot_retention_days < 1:
        screenshot_retention_days = 1
    if project_scan_recent_seconds < 30:
        project_scan_recent_seconds = 30

    analysis_provider = os.environ.get("WORKPULSE_ANALYSIS_PROVIDER", analysis_provider)
    llm_endpoint = os.environ.get("WORKPULSE_LLM_ENDPOINT", llm_endpoint)
    llm_model = os.environ.get("WORKPULSE_LLM_MODEL", llm_model)
    llm_api_key_env = os.environ.get("WORKPULSE_LLM_API_KEY_ENV", llm_api_key_env)

    return Settings(
        poll_interval_seconds=poll_interval,
        archive_retention_days=retention_days,
        analysis_provider=analysis_provider,
        llm_endpoint=llm_endpoint,
        llm_model=llm_model,
        llm_api_key_env=llm_api_key_env,
        llm_timeout_seconds=llm_timeout,
        screen_capture_enabled=screen_capture_enabled,
        screen_capture_interval_seconds=screen_capture_interval,
        screen_ocr_enabled=screen_ocr_enabled,
        keep_raw_screenshots=keep_raw_screenshots,
        screenshot_retention_days=screenshot_retention_days,
        sensitive_apps=sensitive_apps,
        sensitive_title_keywords=sensitive_title_keywords,
        sensitive_url_keywords=sensitive_url_keywords,
        project_roots=project_roots,
        project_scan_recent_seconds=project_scan_recent_seconds,
    )
