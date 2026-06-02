"""这个文件把材料文件和材料库能力包装成 MCP 工具。它让 MCP host 可以先预演材料操作，再在明确允许时执行。

This file wraps material-file and material-library capabilities as MCP tools. It lets an MCP host preview material operations before executing them with clear permission.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..materials import (
    find_duplicate_material_files,
    inspect_material_file,
    install_material_library,
    list_material_libraries,
    material_library_backup_plan,
)


def autoform_install_materials(
    source: str,
    library_name: str | None = None,
    include_docs: bool = False,
    dry_run: bool = True,
) -> dict:
    """Install AutoForm material files into the configured materials directory."""
    result = install_material_library(
        Path(source),
        library_name=library_name,
        include_docs=include_docs,
        dry_run=dry_run,
    )
    return result.as_dict()


def autoform_list_material_libraries(materials_dir: str | None = None) -> list[dict]:
    """Return top level AutoForm material libraries and file counts."""
    return list_material_libraries(materials_dir=Path(materials_dir) if materials_dir else None)


def autoform_find_duplicate_material_files(
    materials_dir: str | None = None,
    match_mode: str = "name_size",
    limit: int | None = 50,
) -> list[dict]:
    """Return likely duplicate .mat and .mtb files from a materials tree."""
    return find_duplicate_material_files(
        materials_dir=Path(materials_dir) if materials_dir else None,
        match_mode=match_mode,
        limit=limit,
    )


def autoform_material_library_backup_plan(
    library_name: str,
    backup_root: str,
    materials_dir: str | None = None,
    dry_run: bool = True,
    timestamp: str | None = None,
) -> dict:
    """Plan or create a backup copy of one top level material library."""
    return material_library_backup_plan(
        library_name,
        Path(backup_root),
        materials_dir=Path(materials_dir) if materials_dir else None,
        dry_run=dry_run,
        timestamp=timestamp,
    )


def autoform_inspect_material_file(path: str, preview_lines: int = 20, hash_contents: bool = False) -> dict:
    """Inspect one AutoForm .mat or .mtb material file."""
    return inspect_material_file(Path(path), preview_lines=preview_lines, hash_contents=hash_contents)


def register_material_tools(mcp: Any) -> None:
    """Register material library MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_install_materials)
    mcp.add_tool(autoform_list_material_libraries)
    mcp.add_tool(autoform_find_duplicate_material_files)
    mcp.add_tool(autoform_material_library_backup_plan)
    mcp.add_tool(autoform_inspect_material_file)


__all__ = ['autoform_install_materials', 'autoform_list_material_libraries', 'autoform_find_duplicate_material_files', 'autoform_material_library_backup_plan', 'autoform_inspect_material_file', 'register_material_tools']
