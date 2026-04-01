"""WorkPulse 运行配置。"""

import importlib.resources
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DATA_DIR = Path.home() / ".workpulse"
SETTINGS_PATH = DATA_DIR / "settings.yaml"
DEFAULT_POLL_INTERVAL = 30
DEFAULT_ARCHIVE_RETENTION_DAYS = 90


@dataclass
class Settings:
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL
    archive_retention_days: int = DEFAULT_ARCHIVE_RETENTION_DAYS
    analysis_provider: str = "heuristic"
    llm_endpoint: str = "https://api.openai.com/v1/chat/completions"
    llm_model: str = "gpt-4o-mini"
    llm_api_key_env: str = "OPENAI_API_KEY"
    llm_timeout_seconds: int = 30


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

    if poll_interval < 5:
        poll_interval = 5
    if retention_days < 1:
        retention_days = 1
    if llm_timeout < 5:
        llm_timeout = 5

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
    )
