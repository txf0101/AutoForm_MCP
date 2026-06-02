"""这个文件把命令辅助能力包装成 MCP 工具。包装层只负责参数适配，真实规则仍留在业务模块中。

This file wraps command-helper capabilities as MCP tools. The wrapper adapts arguments only; the real rules remain in the business modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..commands import (
    executable_command_plan,
    executable_help_probe,
    list_command_specs,
    material_conversion_execute,
    material_conversion_plan,
    report_ms_office_plan,
)


def autoform_list_command_specs() -> list[dict]:
    """Return known AutoForm command entries with path status."""
    return list_command_specs()


def autoform_executable_command_plan(entry: str, args: list[str] | None = None) -> dict:
    """Return an AutoForm executable command preview."""
    return executable_command_plan(entry, args=args)


def autoform_executable_help_probe(
    entry: str,
    help_arg: str | None = None,
    execute: bool = False,
    timeout: int = 10,
) -> dict:
    """Preview or run a bounded executable help probe."""
    return executable_help_probe(entry, help_arg=help_arg, execute=execute, timeout=timeout)


def autoform_mat_to_mtb_plan(args: list[str] | None = None) -> dict:
    """Return an AFMat2Mtb command preview with caller supplied arguments."""
    return material_conversion_plan(args=args)


def autoform_mat_to_mtb_convert(
    source: str,
    working_dir: str | None = None,
    execute: bool = False,
    timeout: int = 30,
) -> dict:
    """Preview or execute AFMat2Mtb conversion for one .mat file."""
    return material_conversion_execute(
        Path(source),
        working_dir=Path(working_dir) if working_dir else None,
        execute=execute,
        timeout=timeout,
    )


def autoform_report_ms_office_plan(args: list[str] | None = None) -> dict:
    """Return an AFReportMSOffice command preview with caller supplied arguments."""
    return report_ms_office_plan(args=args)


def register_command_tools(mcp: Any) -> None:
    """Register command helpers MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_list_command_specs)
    mcp.add_tool(autoform_executable_command_plan)
    mcp.add_tool(autoform_executable_help_probe)
    mcp.add_tool(autoform_mat_to_mtb_plan)
    mcp.add_tool(autoform_mat_to_mtb_convert)
    mcp.add_tool(autoform_report_ms_office_plan)


__all__ = ['autoform_list_command_specs', 'autoform_executable_command_plan', 'autoform_executable_help_probe', 'autoform_mat_to_mtb_plan', 'autoform_mat_to_mtb_convert', 'autoform_report_ms_office_plan', 'register_command_tools']
