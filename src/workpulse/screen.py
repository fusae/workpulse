"""屏幕与浏览器上下文采样。"""

import hashlib
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from workpulse.settings import Settings

logger = logging.getLogger("workpulse.screen")

DATA_DIR = Path.home() / ".workpulse"
SCREENSHOT_DIR = DATA_DIR / "screenshots"


@dataclass
class ScreenSample:
    url: str = ""
    screenshot_path: str = ""
    screenshot_hash: str = ""
    ocr_text: str = ""
    ocr_status: str = "not_run"
    screen_summary: str = ""
    skipped_reason: str = ""


def browser_url(app_name: str) -> str:
    app = app_name.lower()
    if "chrome" in app:
        return _osascript('tell application "Google Chrome" to return URL of active tab of front window')
    if "edge" in app:
        return _osascript('tell application "Microsoft Edge" to return URL of active tab of front window')
    if "safari" in app:
        return _osascript('tell application "Safari" to return URL of front document')
    return ""


def capture_screen_sample(
    app_name: str,
    window_title: str,
    settings: Settings,
    force: bool = False,
) -> ScreenSample:
    sample = ScreenSample(url=browser_url(app_name))
    if not settings.screen_capture_enabled:
        sample.skipped_reason = "screen_capture_disabled"
        return sample
    if not force:
        sample.skipped_reason = "screen_capture_not_due"
        sample.screen_summary = _summarize(app_name, window_title, sample.url, "")
        return sample

    skipped = _sensitive_reason(app_name, window_title, sample.url, settings)
    if skipped:
        sample.skipped_reason = skipped
        return sample

    if shutil.which("screencapture") is None:
        sample.skipped_reason = "screencapture_unavailable"
        return sample

    target = _screenshot_target(settings)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["screencapture", "-x", str(target)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("截图失败: %s", exc)
        sample.skipped_reason = "screencapture_failed"
        _safe_unlink(target)
        return sample

    sample.screenshot_hash = _sha256_file(target)
    if settings.screen_ocr_enabled:
        sample.ocr_text, sample.ocr_status = _ocr_text(target)

    sample.screen_summary = _summarize(app_name, window_title, sample.url, sample.ocr_text)
    if settings.keep_raw_screenshots:
        sample.screenshot_path = str(target)
    else:
        _safe_unlink(target)

    prune_screenshots(settings.screenshot_retention_days)
    return sample


def prune_screenshots(retention_days: int) -> int:
    if not SCREENSHOT_DIR.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0
    for path in SCREENSHOT_DIR.rglob("*.png"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            _safe_unlink(path)
            removed += 1
    return removed


def _osascript(script: str) -> str:
    if shutil.which("osascript") is None:
        return ""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _sensitive_reason(app_name: str, title: str, url: str, settings: Settings) -> str:
    app_lower = app_name.lower()
    title_lower = title.lower()
    url_lower = url.lower()
    if any(item.lower() in app_lower for item in settings.sensitive_apps):
        return "sensitive_app"
    if any(item.lower() in title_lower for item in settings.sensitive_title_keywords):
        return "sensitive_title"
    if any(item.lower() in url_lower for item in settings.sensitive_url_keywords):
        return "sensitive_url"
    return ""


def _screenshot_target(settings: Settings) -> Path:
    if settings.keep_raw_screenshots:
        day = datetime.now().strftime("%Y%m%d")
        name = datetime.now().strftime("%H%M%S_%f.png")
        return SCREENSHOT_DIR / day / name
    fd, raw_path = tempfile.mkstemp(prefix="workpulse-screen-", suffix=".png")
    Path(raw_path).unlink(missing_ok=True)
    return Path(raw_path)


def _ocr_text(path: Path) -> tuple[str, str]:
    if shutil.which("tesseract") is None:
        return "", "tesseract_unavailable"
    try:
        result = subprocess.run(
            ["tesseract", str(path), "stdout", "-l", "eng+chi_sim"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        logger.warning("OCR 失败: %s", exc)
        return "", "ocr_failed"
    if result.returncode != 0:
        return "", "ocr_failed"
    return _compact_text(result.stdout), "ok"


def _summarize(app_name: str, window_title: str, url: str, ocr_text: str) -> str:
    parts = [f"app={app_name}"]
    if window_title:
        parts.append(f"title={window_title}")
    if url:
        parts.append(f"url={url}")
    if ocr_text:
        parts.append(f"screen_text={ocr_text[:300]}")
    return " | ".join(parts)


def _compact_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_unlink(path: Path):
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
