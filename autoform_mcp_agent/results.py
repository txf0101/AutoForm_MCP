"""这个文件清点结果证据，并可生成轻量证据包。它适合先回答“有哪些结果文件和日志可以看”。

This file inventories result evidence and can build a lightweight evidence package. It first answers what result files and logs are available.

AutoForm 结果格式仍在逐步验证，所以这里采用保守路径：收集已确认文件、解析 QuickLink、汇总求解器和报告日志，再按需写出小型证据包。

AutoForm result formats are still being verified, so this module takes a conservative path: collect confirmed files, parse QuickLink data, summarize solver and report logs, and optionally write a small evidence package.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from .quicklink import list_quicklink_exports, parse_quicklink_xml
from .report import report_inventory, report_log_events
from .solver import solver_log_events


RESULT_SUFFIXES = {".afd", ".zip", ".xml", ".xlsx", ".xlsm", ".pptx", ".pdf", ".png", ".jpg", ".jpeg"}
TEXT_SUFFIXES = {".txt", ".log", ".xml", ".json", ".csv"}
EXCLUDED_TOP_LEVEL_DIRS = {"tmp", ".git", ".pytest_cache", "__pycache__"}
EXCLUDED_OUTPUT_DIRS = {"release", "result_package"}


def result_inventory(
    search_dir: str | Path | None = None,
    *,
    workspace: str | Path | None = None,
    limit: int = 100,
) -> dict:
    """Return result, report and QuickLink evidence from a workspace or directory."""

    root = Path(search_dir or workspace or Path.cwd()).resolve()
    workspace_root = Path(workspace or root).resolve()
    files = _collect_result_files(root, limit=limit)
    quicklinks = list_quicklink_exports(workspace_root)
    latest_quicklink = _safe_parse_latest_quicklink(quicklinks)
    return {
        "root": str(root),
        "workspace": str(workspace_root),
        "file_count": len(files),
        "files": files,
        "quicklink_export_count": len(quicklinks),
        "latest_quicklink": latest_quicklink,
        "solver_log_events": solver_log_events(log_dir=root, limit=limit),
        "report_log_events": report_log_events(log_dir=root, limit=limit),
    }


def report_delivery_plan(
    output_dir: str | Path,
    *,
    search_dir: str | Path | None = None,
    workspace: str | Path | None = None,
    dry_run: bool = True,
    limit: int = 100,
) -> dict:
    """Plan or create a small evidence report package for current AutoForm results."""

    destination = Path(output_dir).resolve()
    inventory = result_inventory(search_dir=search_dir, workspace=workspace, limit=limit)
    office_inventory = _safe_report_inventory()
    planned_files = [
        {
            "name": "result_inventory.json",
            "destination": str(destination / "result_inventory.json"),
            "kind": "json",
        },
        {
            "name": "summary.md",
            "destination": str(destination / "summary.md"),
            "kind": "markdown",
        },
    ]
    package = {
        "schema_version": "1.0",
        "created_at": _utc_now(),
        "destination": str(destination),
        "dry_run": dry_run,
        "inventory": inventory,
        "office_report_inventory": office_inventory,
        "planned_files": planned_files,
        "status": "planned" if dry_run else "written",
    }
    if dry_run:
        return package

    destination.mkdir(parents=True, exist_ok=True)
    (destination / "result_inventory.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (destination / "summary.md").write_text(_summary_markdown(package), encoding="utf-8")
    return package


def copy_result_evidence(
    output_dir: str | Path,
    *,
    search_dir: str | Path | None = None,
    dry_run: bool = True,
    limit: int = 100,
) -> dict:
    """Plan or copy discovered result files into an evidence directory."""

    inventory = result_inventory(search_dir=search_dir, limit=limit)
    destination = Path(output_dir).resolve()
    planned_files = [
        {
            "source": item["path"],
            "destination": str(destination / Path(item["path"]).name),
            "exists": Path(item["path"]).exists(),
        }
        for item in inventory["files"]
    ]
    plan = {"destination": str(destination), "dry_run": dry_run, "planned_files": planned_files}
    if dry_run:
        return plan
    destination.mkdir(parents=True, exist_ok=True)
    for item in planned_files:
        source = Path(item["source"])
        if source.exists():
            shutil.copy2(source, item["destination"])
    return plan


def _collect_result_files(root: Path, limit: int) -> list[dict]:
    """Collect known result-like files with bounded recursion."""
    if not root.exists():
        return []
    files = []
    for path in root.rglob("*"):
        if _is_excluded_result_path(path, root):
            continue
        if not path.is_file() or path.suffix.lower() not in RESULT_SUFFIXES:
            continue
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "path": str(path.resolve()),
                "relative_path": str(path.relative_to(root)),
                "suffix": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "preview": _preview(path),
            }
        )
    files.sort(key=lambda item: item["last_modified"], reverse=True)
    return files[:limit]


def _is_excluded_result_path(path: Path, root: Path) -> bool:
    """Skip generated test and package folders that would pollute delivery evidence."""

    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    if not parts:
        return False
    if parts[0] in EXCLUDED_TOP_LEVEL_DIRS:
        return True
    # `output` may contain real AutoForm solver outputs, so only known package
    # staging folders are skipped here.
    return len(parts) > 1 and parts[0] == "output" and parts[1] in EXCLUDED_OUTPUT_DIRS


def _safe_parse_latest_quicklink(exports: list[dict]) -> dict | None:
    """Parse the newest QuickLink export when it has a readable target."""
    if not exports:
        return None
    candidate = exports[0].get("target_path") or exports[0].get("archive_path") or exports[0].get("directory")
    if not candidate:
        return {"export": exports[0], "parse_status": "no_target"}
    try:
        return {"export": exports[0], "parse_status": "parsed", "parsed": parse_quicklink_xml(Path(candidate))}
    except Exception as exc:
        return {"export": exports[0], "parse_status": "failed", "error": str(exc)}


def _safe_report_inventory() -> dict:
    """Return report inventory or capture why it is unavailable."""
    try:
        return report_inventory()
    except Exception as exc:
        return {"error": str(exc)}


def _summary_markdown(package: dict) -> str:
    """Build a compact human-readable report summary."""
    inventory = package["inventory"]
    lines = [
        "# AutoForm Result Evidence Summary",
        "",
        f"Created at: {package['created_at']}",
        f"Source root: {inventory['root']}",
        f"Result-like files: {inventory['file_count']}",
        f"QuickLink exports: {inventory['quicklink_export_count']}",
        f"Solver log events: {len(inventory['solver_log_events'])}",
        f"Report log events: {len(inventory['report_log_events'])}",
        "",
        "## Files",
    ]
    for item in inventory["files"][:20]:
        lines.append(f"- {item['relative_path']} ({item['size_bytes']} bytes)")
    return "\n".join(lines) + "\n"


def _preview(path: Path, limit: int = 500) -> str:
    """Read a bounded preview for text-like result files."""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    return path.read_bytes()[:limit].decode("utf-8", errors="replace")


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()
