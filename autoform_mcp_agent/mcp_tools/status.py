"""这个文件暴露 MCP 状态工具和 `autoform://status` 资源。它让 MCP host 在调用其他工具前先读取本机健康状态。

This file exposes the MCP status tool and the `autoform://status` resource. It lets an MCP host read local health status before calling other tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..diagnostics import autoform_status_snapshot as build_autoform_status_snapshot


def autoform_status_resource() -> dict:
    """Return the current read only status document for MCP resource clients."""
    return build_autoform_status_snapshot()


def autoform_status_snapshot(workspace: str | None = None) -> dict:
    """Return the same read only status document exposed as `autoform://status`."""
    return build_autoform_status_snapshot(project_root=Path(workspace) if workspace else None)


def register_status_tools(mcp: Any) -> None:
    """Register status and resource MCP tools on one FastMCP instance."""
    mcp.resource(
        "autoform://status",
        name="autoform-status",
        description="Read only AutoForm Agent status, including installation, queue, QuickLink and log probes.",
        mime_type="application/json",
    )(autoform_status_resource)
    mcp.add_tool(autoform_status_snapshot)


__all__ = ['autoform_status_resource', 'autoform_status_snapshot', 'register_status_tools']
