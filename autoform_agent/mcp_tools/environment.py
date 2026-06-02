"""这个文件把环境诊断能力包装成 MCP 工具。MCP host 可以通过它查看本机安装、日志和诊断状态。

This file wraps environment diagnostics as MCP tools. An MCP host can use it to inspect local installation, log, and diagnostic status.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import get_logging_config, get_queue_config, get_remote_hosts
from ..diagnostics import (
    collect_gui_project_events,
    collect_recent_autoform_logs,
    diagnostic_bundle_plan,
    environment_snapshot,
)


def autoform_get_queue_config(config_path: str | None = None) -> dict:
    """Return queue settings from AutoForm's systemConfigFile.xml."""
    return get_queue_config(config_path=Path(config_path) if config_path else None)


def autoform_get_remote_hosts(config_path: str | None = None) -> dict:
    """Return AutoForm remote computing hosts and supported modules."""
    return get_remote_hosts(config_path=Path(config_path) if config_path else None)


def autoform_get_logging_config(config_path: str | None = None) -> dict:
    """Return logging settings from AutoForm's systemConfigFile.xml."""
    return get_logging_config(config_path=Path(config_path) if config_path else None)


def autoform_collect_recent_logs(
    search_roots: list[str] | None = None,
    limit: int = 50,
    preview_bytes: int = 2048,
) -> list[dict]:
    """Return recent AutoForm like log files without copying them."""
    # MCP clients pass strings.  Implementation code receives `Path` instances so
    # path normalization and validation stay consistent with the CLI.
    roots = [Path(item) for item in search_roots] if search_roots else None
    return collect_recent_autoform_logs(search_roots=roots, limit=limit, preview_bytes=preview_bytes)


def autoform_collect_gui_project_events(log_dir: str | None = None, limit: int = 50) -> list[dict]:
    """Parse AutoForm GUI logs for project open events and file facts."""
    return collect_gui_project_events(log_dir=Path(log_dir) if log_dir else None, limit=limit)


def autoform_diagnostic_bundle_plan(
    output_dir: str,
    search_roots: list[str] | None = None,
    limit: int = 50,
    dry_run: bool = True,
) -> dict:
    """Plan or create a diagnostic bundle from recent log files."""
    roots = [Path(item) for item in search_roots] if search_roots else None
    return diagnostic_bundle_plan(Path(output_dir), search_roots=roots, limit=limit, dry_run=dry_run)


def autoform_environment_snapshot(output_path: str | None = None, write: bool = False) -> dict:
    """Return or write a compact AutoForm Agent environment snapshot."""
    return environment_snapshot(output_path=Path(output_path) if output_path else None, write=write)


def register_environment_tools(mcp: Any) -> None:
    """Register environment and diagnostics MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_get_queue_config)
    mcp.add_tool(autoform_get_remote_hosts)
    mcp.add_tool(autoform_get_logging_config)
    mcp.add_tool(autoform_collect_recent_logs)
    mcp.add_tool(autoform_collect_gui_project_events)
    mcp.add_tool(autoform_diagnostic_bundle_plan)
    mcp.add_tool(autoform_environment_snapshot)


__all__ = ['autoform_get_queue_config', 'autoform_get_remote_hosts', 'autoform_get_logging_config', 'autoform_collect_recent_logs', 'autoform_collect_gui_project_events', 'autoform_diagnostic_bundle_plan', 'autoform_environment_snapshot', 'register_environment_tools']
