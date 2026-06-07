"""这个文件把 AutoForm 参考资料生成和查询能力包装成 MCP 工具。它帮助 MCP host 查找本机已整理的 AutoForm 资料依据。

This file wraps AutoForm reference generation and lookup capabilities as MCP tools. It helps an MCP host find locally prepared AutoForm evidence and reference material.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..af_api import (
    af_api_build_preview,
    af_api_template_plan,
    check_af_api_build_env,
    list_af_api_modules,
)
from ..coverage import help_topic_agent_mapping, module_coverage_matrix
from ..inventory import list_help_topics


def autoform_list_help_topics(query: str | None = None) -> list[dict]:
    """Return AutoForm help topic anchors, optionally filtered by query."""
    return list_help_topics(query=query)


def autoform_help_topic_agent_mapping(query: str | None = None) -> dict:
    """Map helpLinks.cfg topics to current Agent domains and tools."""
    return help_topic_agent_mapping(query=query)


def autoform_list_af_api_modules() -> list[dict]:
    """Return AF_API sample modules and exported function names."""
    return list_af_api_modules()


def autoform_check_af_api_build_env() -> dict:
    """Return available C compiler commands and AF_HOME_LIB state."""
    return check_af_api_build_env()


def autoform_af_api_template_plan(module: str, output_dir: str, dry_run: bool = True) -> dict:
    """Plan or create AF_API starter files by copying installed samples."""
    return af_api_template_plan(module, Path(output_dir), dry_run=dry_run)


def autoform_af_api_build_preview(
    module: str,
    compiler: str = "cl",
    source_file: str | None = None,
) -> dict:
    """Return AF_API compiler commands without executing them."""
    return af_api_build_preview(module, compiler=compiler, source_file=source_file)


def autoform_module_coverage_matrix() -> list[dict]:
    """Return a high level AutoForm Agent module coverage matrix."""
    return module_coverage_matrix()


def register_reference_tools(mcp: Any) -> None:
    """Register reference and AF_API MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_list_help_topics)
    mcp.add_tool(autoform_help_topic_agent_mapping)
    mcp.add_tool(autoform_list_af_api_modules)
    mcp.add_tool(autoform_check_af_api_build_env)
    mcp.add_tool(autoform_af_api_template_plan)
    mcp.add_tool(autoform_af_api_build_preview)
    mcp.add_tool(autoform_module_coverage_matrix)


__all__ = ['autoform_list_help_topics', 'autoform_help_topic_agent_mapping', 'autoform_list_af_api_modules', 'autoform_check_af_api_build_env', 'autoform_af_api_template_plan', 'autoform_af_api_build_preview', 'autoform_module_coverage_matrix', 'register_reference_tools']
