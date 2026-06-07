"""这个文件把结果证据清点和报告交付计划包装成 MCP 工具。它让外部客户端按同一套规则查看结果包和报告材料。

This file wraps result inventory and report-delivery planning as MCP tools. It lets external clients inspect result packages and report materials under the same rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..report import report_inventory, report_log_events
from ..results import copy_result_evidence, report_delivery_plan, result_inventory


def autoform_report_inventory(
    bin_dir: str | None = None,
    templates_root: str | None = None,
    help_links_file: str | None = None,
) -> dict:
    """Return report, Office and result view related local evidence."""
    return report_inventory(
        bin_dir=Path(bin_dir) if bin_dir else None,
        templates_root=Path(templates_root) if templates_root else None,
        help_links_file=Path(help_links_file) if help_links_file else None,
    )


def autoform_report_log_events(log_dir: str | None = None, limit: int = 100) -> list[dict]:
    """Parse AutoForm GUI logs for report, export and postprocessing events."""
    return report_log_events(log_dir=Path(log_dir) if log_dir else None, limit=limit)


def autoform_result_inventory(
    search_dir: str | None = None,
    workspace: str | None = None,
    limit: int = 100,
) -> dict:
    """Return result like files, log events and QuickLink evidence."""
    return result_inventory(
        search_dir=Path(search_dir) if search_dir else None,
        workspace=Path(workspace) if workspace else None,
        limit=limit,
    )


def autoform_report_delivery_plan(
    output_dir: str,
    search_dir: str | None = None,
    workspace: str | None = None,
    dry_run: bool = True,
    limit: int = 100,
) -> dict:
    """Plan or create a lightweight result evidence report package."""
    return report_delivery_plan(
        Path(output_dir),
        search_dir=Path(search_dir) if search_dir else None,
        workspace=Path(workspace) if workspace else None,
        dry_run=dry_run,
        limit=limit,
    )


def autoform_copy_result_evidence(
    output_dir: str,
    search_dir: str | None = None,
    dry_run: bool = True,
    limit: int = 100,
) -> dict:
    """Plan or copy discovered result evidence files."""
    return copy_result_evidence(
        Path(output_dir),
        search_dir=Path(search_dir) if search_dir else None,
        dry_run=dry_run,
        limit=limit,
    )


def register_reporting_tools(mcp: Any) -> None:
    """Register reports and results MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_report_inventory)
    mcp.add_tool(autoform_report_log_events)
    mcp.add_tool(autoform_result_inventory)
    mcp.add_tool(autoform_report_delivery_plan)
    mcp.add_tool(autoform_copy_result_evidence)


__all__ = ['autoform_report_inventory', 'autoform_report_log_events', 'autoform_result_inventory', 'autoform_report_delivery_plan', 'autoform_copy_result_evidence', 'register_reporting_tools']
