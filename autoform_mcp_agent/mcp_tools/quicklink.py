"""这个文件把 QuickLink 解析、段落读取和导出比较能力包装成 MCP 工具。它让外部客户端用结构化方式读取 QuickLink 资料。

This file wraps QuickLink parsing, section reading, and export comparison as MCP tools. It lets external clients read QuickLink materials in a structured way.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..quicklink import (
    compare_quicklink_exports,
    get_blank_info,
    get_die_face,
    get_evaluation,
    get_process_plan,
    get_project_data,
    get_quicklink_section,
    install_quicklink_bridge,
    list_exported_geometry,
    list_quicklink_exports,
    list_quicklink_standards,
    parse_quicklink_xml,
    quicklink_archive_inventory,
    quicklink_bridge_status,
    quicklink_schema,
    validate_quicklink_standard,
)


def autoform_install_quicklink_bridge(
    workspace: str,
    script_name: str = "CodexAgentBridge.cmd",
    dry_run: bool = True,
) -> str:
    """Install the QuickLink script bridge into AutoForm's scripts directory."""
    return str(
        install_quicklink_bridge(
            Path(workspace),
            script_name=script_name,
            dry_run=dry_run,
        )
    )


def autoform_get_quicklink_bridge_status(
    workspace: str,
    script_name: str = "CodexAgentBridge.cmd",
) -> dict:
    """Check the installed QuickLink bridge script without modifying files."""
    return quicklink_bridge_status(Path(workspace), script_name=script_name)


def autoform_list_quicklink_exports(workspace: str) -> list[dict]:
    """List QuickLink exports collected by the AutoForm bridge script."""
    return list_quicklink_exports(Path(workspace))


def autoform_parse_quicklink_xml(source: str) -> dict:
    """Parse a QuickLink XML file, zip archive, manifest, or export directory."""
    return parse_quicklink_xml(Path(source))


def autoform_quicklink_schema(source: str) -> dict:
    """Return the normalized AutoForm Agent 1.0 schema for a QuickLink export."""
    return quicklink_schema(Path(source))


def autoform_get_project_data(source: str) -> list[dict]:
    """Return ProjectData values from a QuickLink export."""
    return get_project_data(Path(source))


def autoform_get_blank_info(source: str) -> dict | None:
    """Return Blank information from a QuickLink export."""
    return get_blank_info(Path(source))


def autoform_list_exported_geometry(source: str) -> list[str]:
    """Return geometry files referenced by a QuickLink export."""
    return list_exported_geometry(Path(source))


def autoform_quicklink_archive_inventory(source: str) -> dict:
    """Return member level facts for a QuickLink archive or XML source."""
    return quicklink_archive_inventory(Path(source))


def autoform_compare_quicklink_exports(left: str, right: str) -> dict:
    """Compare two QuickLink exports at a stable summary level."""
    return compare_quicklink_exports(Path(left), Path(right))


def autoform_get_quicklink_section(source: str, section_name: str, value_limit: int = 100) -> dict:
    """Return a deeper summary for one named QuickLink XML section."""
    return get_quicklink_section(Path(source), section_name, value_limit=value_limit)


def autoform_get_quicklink_process_plan(source: str, value_limit: int = 100) -> dict:
    """Return detailed ProcessPlan data from a QuickLink export."""
    return get_process_plan(Path(source), value_limit=value_limit)


def autoform_get_quicklink_evaluation(source: str, value_limit: int = 100) -> dict:
    """Return detailed Evaluation data from a QuickLink export."""
    return get_evaluation(Path(source), value_limit=value_limit)


def autoform_get_quicklink_die_face(source: str, value_limit: int = 100) -> dict:
    """Return detailed DieFace data from a QuickLink export."""
    return get_die_face(Path(source), value_limit=value_limit)


def autoform_list_quicklink_standards(templates_dir: str | None = None) -> list[dict]:
    """Return QuickLink standards and templates shipped with AutoForm."""
    return list_quicklink_standards(templates_dir=Path(templates_dir) if templates_dir else None)


def autoform_validate_quicklink_standard(path: str) -> dict:
    """Validate one QuickLink XML or XSD standard file."""
    return validate_quicklink_standard(Path(path))


def register_quicklink_tools(mcp: Any) -> None:
    """Register QuickLink MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_install_quicklink_bridge)
    mcp.add_tool(autoform_get_quicklink_bridge_status)
    mcp.add_tool(autoform_list_quicklink_exports)
    mcp.add_tool(autoform_parse_quicklink_xml)
    mcp.add_tool(autoform_quicklink_schema)
    mcp.add_tool(autoform_get_project_data)
    mcp.add_tool(autoform_get_blank_info)
    mcp.add_tool(autoform_list_exported_geometry)
    mcp.add_tool(autoform_quicklink_archive_inventory)
    mcp.add_tool(autoform_compare_quicklink_exports)
    mcp.add_tool(autoform_get_quicklink_section)
    mcp.add_tool(autoform_get_quicklink_process_plan)
    mcp.add_tool(autoform_get_quicklink_evaluation)
    mcp.add_tool(autoform_get_quicklink_die_face)
    mcp.add_tool(autoform_list_quicklink_standards)
    mcp.add_tool(autoform_validate_quicklink_standard)


__all__ = ['autoform_install_quicklink_bridge', 'autoform_get_quicklink_bridge_status', 'autoform_list_quicklink_exports', 'autoform_parse_quicklink_xml', 'autoform_quicklink_schema', 'autoform_get_project_data', 'autoform_get_blank_info', 'autoform_list_exported_geometry', 'autoform_quicklink_archive_inventory', 'autoform_compare_quicklink_exports', 'autoform_get_quicklink_section', 'autoform_get_quicklink_process_plan', 'autoform_get_quicklink_evaluation', 'autoform_get_quicklink_die_face', 'autoform_list_quicklink_standards', 'autoform_validate_quicklink_standard', 'register_quicklink_tools']
