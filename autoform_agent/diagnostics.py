"""这个文件负责诊断信息、日志发现和环境快照。它帮助用户先看清当前电脑状态，再决定下一步。

This file handles diagnostics, log discovery, and environment snapshots. It helps users see the current computer state before deciding what to do next.

默认行为保持只读。需要打包日志时也先返回 dry-run 计划，让调用者确认路径后再复制。

Default behavior stays read-only. Log bundle creation starts with dry-run plans so callers can review paths before copying files.
"""

from __future__ import annotations

import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    tomllib = None

from .commands import list_command_specs
from .coverage import MODULE_COVERAGE, module_coverage_matrix
from .paths import AutoFormInstallation, discover_installations, get_default_installation
from .queue import queue_health_check
from .quicklink import list_quicklink_exports


LOG_EXTENSIONS = {".log", ".txt", ".out", ".err"}
GUI_TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
GUI_OPEN_RE = re.compile(r"#FILE_LOG#Open: (?P<path>.+)$")
GUI_FILE_VERSION_RE = re.compile(
    r"Opening file \(version: (?P<version>\d+) created with revision: (?P<created_revision>\d+) "
    r"last saved with revision: (?P<last_saved_revision>[^)]+)\)"
)
GUI_JOB_STATUS_RE = re.compile(r"JobStatus string can not be loaded from '(?P<path>.+)'\.")


def collect_recent_autoform_logs(
    search_roots: list[Path] | None = None,
    install: AutoFormInstallation | None = None,
    limit: int = 50,
    preview_bytes: int = 2048,
) -> list[dict]:
    """Return recent AutoForm-like log files without copying them."""

    roots = [path.resolve() for path in search_roots] if search_roots else _default_log_roots(install)
    seen: set[str] = set()
    logs: list[dict] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or not _looks_like_log(path):
                continue
            key = str(path.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            stat = path.stat()
            logs.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "last_modified": stat.st_mtime,
                    "preview": _read_preview(path, preview_bytes),
                }
            )
    logs.sort(key=lambda item: item["last_modified"], reverse=True)
    return logs[:limit]


def diagnostic_bundle_plan(
    output_dir: Path,
    search_roots: list[Path] | None = None,
    limit: int = 50,
    dry_run: bool = True,
) -> dict:
    """Plan a diagnostic bundle made from recent log files."""

    logs = collect_recent_autoform_logs(search_roots=search_roots, limit=limit)
    destination = output_dir.resolve()
    planned_files = []
    for index, item in enumerate(logs, 1):
        source = Path(item["path"])
        planned_files.append(
            {
                "source": str(source),
                "destination": str(destination / f"{index:03d}_{source.name}"),
                "size_bytes": item["size_bytes"],
            }
        )
    manifest = {
        "destination": str(destination),
        "dry_run": dry_run,
        "log_count": len(planned_files),
        "planned_files": planned_files,
    }
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
        for item in planned_files:
            source = Path(item["source"])
            target = Path(item["destination"])
            target.write_bytes(source.read_bytes())
        (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def collect_gui_project_events(
    log_dir: Path | None = None,
    limit: int = 50,
) -> list[dict]:
    """Parse AutoForm GUI logs for project open events and file facts."""

    root = log_dir.resolve() if log_dir is not None else _default_gui_log_dir()
    if not root.exists():
        return []
    events: list[dict] = []
    for log_path in sorted(root.glob("log_AFFormingUI_*.txt"), key=lambda item: item.stat().st_mtime, reverse=True):
        events.extend(_parse_gui_log(log_path))
    events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    return events[:limit]


def environment_snapshot(
    output_path: Path | None = None,
    write: bool = False,
) -> dict:
    """Return or write a compact AutoForm Agent environment snapshot."""

    installs = [install.as_dict() for install in discover_installations()]
    snapshot = {
        "python": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "installations": installs,
        "command_specs": list_command_specs() if installs else [],
        "module_coverage": module_coverage_matrix() if installs else [],
    }
    if write:
        if output_path is None:
            raise ValueError("output_path is required when write=True")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        snapshot["written_to"] = str(output_path.resolve())
    return snapshot


def autoform_status_snapshot(
    project_root: Path | None = None,
    log_limit: int = 5,
    preview_bytes: int = 0,
) -> dict:
    """Return the read-only status document behind the `autoform://status` MCP resource.

    The status payload is intentionally broader than `environment_snapshot`.
    `environment_snapshot` is a support dump, while this function is the small
    live contract that a client can poll before choosing tools.  Every probe is
    isolated so one unavailable local dependency becomes a structured error
    instead of preventing the whole status resource from being read.
    """

    resolved_root = (project_root or Path.cwd()).resolve()
    errors: list[dict[str, str]] = []

    installations = _status_probe(
        "installations",
        lambda: [install.as_dict() for install in discover_installations()],
        fallback=[],
        errors=errors,
    )
    queue_status = _status_probe("queue_health", queue_health_check, fallback={"processes": []}, errors=errors)
    quicklink_exports = _status_probe(
        "quicklink_exports",
        lambda: list_quicklink_exports(resolved_root),
        fallback=[],
        errors=errors,
    )
    coverage_rows = _status_probe(
        "module_coverage",
        module_coverage_matrix,
        fallback=[dict(row) for row in MODULE_COVERAGE],
        errors=errors,
    )
    recent_logs = _status_probe(
        "recent_logs",
        lambda: collect_recent_autoform_logs(
            search_roots=None if installations else [_workspace_log_root(resolved_root)],
            limit=log_limit,
            preview_bytes=preview_bytes,
        ),
        fallback=[],
        errors=errors,
    )

    return {
        "schema_version": "1.0",
        "resource_uri": "autoform://status",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_ok": not errors,
        "project": _project_status(resolved_root),
        "runtime": {
            "python": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "services": _service_defaults(),
        "installations": {
            "count": len(installations),
            "items": installations,
        },
        "queue": _queue_status_summary(queue_status),
        "quicklink": {
            "export_count": len(quicklink_exports),
            "latest_export": quicklink_exports[0] if quicklink_exports else None,
        },
        "logs": {
            "count": len(recent_logs),
            "latest_log": _compact_log_record(recent_logs[0]) if recent_logs else None,
            "items": [_compact_log_record(item) for item in recent_logs],
        },
        "coverage": _coverage_status(coverage_rows),
        "errors": errors,
        "evidence": {
            "project_metadata": str(resolved_root / "pyproject.toml"),
            "installation_probe": "autoform_agent.paths.discover_installations",
            "queue_probe": "autoform_agent.queue.queue_health_check",
            "quicklink_probe": "autoform_agent.quicklink.list_quicklink_exports",
            "log_probe": "autoform_agent.diagnostics.collect_recent_autoform_logs",
            "coverage_probe": "autoform_agent.coverage.module_coverage_matrix",
        },
    }


def _default_log_roots(install: AutoFormInstallation | None = None) -> list[Path]:
    """Return likely log locations for the selected AutoForm installation."""
    selected = install or get_default_installation()
    return [
        selected.autoform_program_data,
        Path.cwd(),
    ]


def _looks_like_log(path: Path) -> bool:
    """Identify AutoForm logs by filename prefix and text suffix."""
    suffix = path.suffix.lower()
    if suffix not in LOG_EXTENSIONS:
        return False
    name = path.name.casefold()
    return suffix in {".log", ".out", ".err"} or "log" in name


def _read_preview(path: Path, preview_bytes: int) -> str:
    """Read a bounded log preview for diagnostics output."""
    if preview_bytes <= 0:
        return ""
    data = path.read_bytes()[:preview_bytes]
    return data.decode("utf-8", errors="replace")


def _default_gui_log_dir() -> Path:
    """Return the default GUI log folder for AutoForm R13 on Windows."""
    return Path.home() / "AppData" / "Local" / "AutoForm" / "AFplus" / "R13F" / "log"


def _parse_gui_log(log_path: Path) -> list[dict]:
    """Extract project-open records and related file facts from one GUI log."""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    events: list[dict] = []
    current: dict | None = None
    current_timestamp: str | None = None
    for line in lines:
        timestamp_match = GUI_TIMESTAMP_RE.search(line)
        if timestamp_match:
            current_timestamp = timestamp_match.group("timestamp")
        open_match = GUI_OPEN_RE.search(line)
        if open_match:
            current = {
                "timestamp": current_timestamp,
                "event": "open_project",
                "path": open_match.group("path"),
                "log_path": str(log_path),
                "file_version": None,
                "created_revision": None,
                "last_saved_revision": None,
                "job_status_available": None,
            }
            events.append(current)
            continue
        version_match = GUI_FILE_VERSION_RE.search(line)
        if version_match and current is not None:
            current["file_version"] = version_match.group("version")
            current["created_revision"] = version_match.group("created_revision")
            current["last_saved_revision"] = version_match.group("last_saved_revision")
            continue
        job_status_match = GUI_JOB_STATUS_RE.search(line)
        if job_status_match and current is not None:
            current["job_status_available"] = False
            current["job_status_path"] = job_status_match.group("path")
    return events


def _status_probe(
    name: str,
    func: Callable[[], Any],
    fallback: Any,
    errors: list[dict[str, str]],
) -> Any:
    """Run one status probe and capture its failure as structured data."""
    try:
        return func()
    except Exception as exc:  # pragma: no cover - depends on local AutoForm state
        errors.append({"probe": name, "error": str(exc)})
        return fallback


def _workspace_log_root(project_root: Path) -> Path:
    """Return the bounded workspace log root used when AutoForm is not found."""
    output_root = project_root / "output"
    return output_root if output_root.exists() else project_root


def _project_status(project_root: Path) -> dict:
    """Read project identity from `pyproject.toml` with a text fallback."""
    pyproject = project_root / "pyproject.toml"
    status = {"root": str(project_root), "pyproject": str(pyproject), "pyproject_exists": pyproject.exists()}
    if not pyproject.exists():
        return {**status, "name": None, "version": None}

    try:
        if tomllib is not None:
            parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = parsed.get("project", {})
            return {**status, "name": project.get("name"), "version": project.get("version")}
        return {**status, **_read_pyproject_text_metadata(pyproject)}
    except Exception as exc:  # pragma: no cover - malformed local metadata
        return {**status, "name": None, "version": None, "metadata_error": str(exc)}


def _read_pyproject_text_metadata(pyproject: Path) -> dict:
    """Extract package name and version on Python versions without `tomllib`."""
    metadata = {"name": None, "version": None}
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        for key in ["name", "version"]:
            if stripped.startswith(f"{key} ="):
                metadata[key] = stripped.split("=", 1)[1].strip().strip('"')
    return metadata


def _service_defaults() -> dict:
    """Return the stable stdio MCP entry details shown in status output."""
    return {
        "mcp_stdio_server": {
            "command": "python",
            "args": ["-m", "autoform_agent.mcp_server"],
            "resource": "autoform://status",
            "config_template": "codex_mcp_config.autoform-mcp.toml",
            "evidence": "autoform_agent/mcp_server.py and autoform_agent/mcp_tools/",
        },
    }


def _queue_status_summary(queue_status: dict) -> dict:
    """Summarize queue and remote-service process state for status polling."""
    processes = queue_status.get("processes", []) if isinstance(queue_status, dict) else []
    running = [item for item in processes if item.get("running")]
    return {
        "process_count": len(processes),
        "running_process_count": len(running),
        "processes": processes,
    }


def _compact_log_record(log_record: dict) -> dict:
    """Drop bulky previews from log records before putting them in status."""
    return {
        key: value
        for key, value in log_record.items()
        if key in {"name", "path", "size_bytes", "last_modified"}
    }


def _coverage_status(coverage_rows: list[dict]) -> dict:
    """Summarize Agent capability coverage plus the status resource itself."""
    tools = sorted(
        {
            tool
            for row in coverage_rows
            for tool in row.get("tools", [])
        }
    )
    return {
        "module_count": len(coverage_rows),
        "tool_reference_count": len(tools),
        "tool_references": tools,
        "resource_count": 1,
        "resources": ["autoform://status"],
    }
