"""项目、文件和 Git 证据采集。"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List

from workpulse.settings import Settings

IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
TEXT_OUTPUT_EXTENSIONS = {
    ".md", ".txt", ".rst", ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs",
    ".java", ".swift", ".kt", ".css", ".html", ".json", ".yaml", ".yml",
}
TERMINAL_APPS = {"terminal", "iterm", "iterm2", "warp", "kitty", "wezterm", "alacritty"}


def collect_project_context(settings: Settings) -> Dict[str, object]:
    roots = [Path(item).expanduser() for item in settings.project_roots or []]
    projects = []
    for root in roots[:10]:
        if not root.exists() or not root.is_dir():
            continue
        projects.append(_project_snapshot(root, settings.project_scan_recent_seconds))

    active_projects = [item for item in projects if item.get("recent_files") or item.get("git_dirty")]
    primary = active_projects[0] if active_projects else (projects[0] if projects else None)
    return {
        "primary_project": primary["name"] if primary else "",
        "projects": projects,
    }


def dumps_context(context: Dict[str, object]) -> str:
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))


def summarize_text_outputs(context: Dict[str, object]) -> str:
    outputs = []
    for project in context.get("projects", []):
        for filename in project.get("recent_files", []):
            suffix = Path(filename).suffix.lower()
            if suffix in TEXT_OUTPUT_EXTENSIONS:
                outputs.append(f"{project['name']}:{filename}")
            if len(outputs) >= 8:
                break
        if len(outputs) >= 8:
            break
    return "; ".join(outputs)


def terminal_evidence(app_name: str, window_title: str) -> str:
    app = (app_name or "").lower()
    if not any(name in app for name in TERMINAL_APPS):
        return ""
    title = (window_title or "").strip()
    return f"{app_name}: {title}" if title else app_name


def _project_snapshot(root: Path, recent_seconds: int) -> Dict[str, object]:
    return {
        "name": root.name,
        "path": str(root),
        "git_branch": _git(root, ["branch", "--show-current"]),
        "git_dirty": bool(_git(root, ["status", "--short"])),
        "recent_files": _recent_files(root, recent_seconds),
    }


def _git(root: Path, args: List[str]) -> str:
    if not (root / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
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


def _recent_files(root: Path, recent_seconds: int) -> List[str]:
    cutoff = time.time() - recent_seconds
    found = []
    for path in root.rglob("*"):
        if len(found) >= 20:
            break
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        try:
            if path.is_file() and path.stat().st_mtime >= cutoff:
                found.append(str(path.relative_to(root)))
        except OSError:
            continue
    return found
