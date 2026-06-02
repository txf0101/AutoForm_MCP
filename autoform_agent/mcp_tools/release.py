"""这个文件把发布检查和公开发布扫描包装成 MCP 工具。它帮助维护者判断仓库是否具备交付或公开发布条件。

This file wraps release readiness and public-release scanning as MCP tools. It helps maintainers decide whether the repository is ready for delivery or public release.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..extension import internal_extension_boundary
from ..release import install_check_plan, release_package_plan, release_readiness_check
from ..safety import public_release_scan, write_safety_plan


def autoform_release_readiness_check() -> dict:
    """Check files and package plan required for a 1.0 release candidate."""
    return release_readiness_check()


def autoform_release_package_plan(output_dir: str, dry_run: bool = True) -> dict:
    """Plan or create a source release directory."""
    return release_package_plan(Path(output_dir), dry_run=dry_run)


def autoform_install_check_plan() -> dict:
    """Return install verification commands grounded in project files."""
    return install_check_plan()


def autoform_public_release_scan() -> dict:
    """Scan source files for common blockers before making the repository public."""
    return public_release_scan()


def autoform_write_safety_plan(targets: list[str], backup_root: str = "output/rollback") -> dict:
    """Plan backup and rollback records for write targets."""
    return write_safety_plan([Path(target) for target in targets], backup_root=backup_root)


def autoform_internal_extension_boundary(workspace: str | None = None) -> dict:
    """Return confirmed AutoForm extension paths and the 1.0 automation boundary."""
    return internal_extension_boundary(workspace=workspace)


def register_release_tools(mcp: Any) -> None:
    """Register release and safety MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_release_readiness_check)
    mcp.add_tool(autoform_release_package_plan)
    mcp.add_tool(autoform_install_check_plan)
    mcp.add_tool(autoform_public_release_scan)
    mcp.add_tool(autoform_write_safety_plan)
    mcp.add_tool(autoform_internal_extension_boundary)


__all__ = ['autoform_release_readiness_check', 'autoform_release_package_plan', 'autoform_install_check_plan', 'autoform_public_release_scan', 'autoform_write_safety_plan', 'autoform_internal_extension_boundary', 'register_release_tools']
