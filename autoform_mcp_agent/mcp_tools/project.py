"""这个文件把工程解析、官方样例基准和工程运行流程包装成 MCP 工具。它是 MCP host 运行 AutoForm 示例或用户工程的主要入口。

This file wraps project resolution, official example baselines, and project-run workflows as MCP tools. It is the main MCP entry point for running AutoForm examples or user projects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..inventory import (
    get_afd_project_summary,
    get_afd_readable_index,
    inspect_afd,
    list_example_projects,
    list_executables,
)
from ..paths import discover_installations
from ..process import collect_forming_job_logs, forming_job_plan, open_afd, run_forming_job, start_forming_ui
from ..project_workflow import example_project_baseline, official_sample_run_summary, project_run_workflow, resolve_project_input


def autoform_discover_installation() -> list[dict]:
    """Return discovered AutoForm Forming installations and key paths."""
    return [install.as_dict() for install in discover_installations()]


def autoform_start_ui(graphics: str = "directx11", dry_run: bool = True) -> list[str]:
    """Start AutoForm Forming, returning the command that was used."""
    return start_forming_ui(graphics=graphics, dry_run=dry_run)


def autoform_open_afd(afd_path: str, dry_run: bool = True) -> list[str]:
    """Open an AutoForm .afd project, returning the command that was used."""
    return open_afd(Path(afd_path), dry_run=dry_run)


def autoform_resolve_project(afd_path: str | None = None, example_name: str | None = "Solver_R13") -> dict:
    """Resolve an explicit .afd path or official example project name."""
    return resolve_project_input(afd_path=afd_path, example_name=example_name)


def autoform_project_run(
    afd_path: str | None = None,
    example_name: str | None = "Solver_R13",
    mode: str = "kinematic",
    threads: int = 1,
    output_root: str = "output/project_runs",
    execute: bool = False,
    timeout: int | None = None,
    open_gui: bool = False,
    gui_wait_seconds: float = 3.0,
    workspace: str | None = None,
) -> dict:
    """Plan or execute one reproducible AutoForm project run workflow.

    Set `open_gui` to true when the user wants an AutoForm Forming window to
    open on the copied run project before the solver starts.  The returned
    `gui_observation` field records the launch command, process id when known,
    and the best-effort visibility boundary.
    """
    return project_run_workflow(
        afd_path=afd_path,
        example_name=example_name,
        mode=mode,
        threads=threads,
        output_root=output_root,
        execute=execute,
        timeout=timeout,
        open_gui=open_gui,
        gui_wait_seconds=gui_wait_seconds,
        workspace=workspace,
    )


def autoform_example_project_baseline(output_path: str | None = None, execute: bool = False, threads: int = 1) -> dict:
    """Build the official example project baseline table for 1.0 validation."""
    return example_project_baseline(output_path=output_path, execute=execute, threads=threads)


def autoform_official_sample_run_summary(
    search_dir: str = "output/project_runs",
    mode: str = "kinematic",
    expected_examples: list[str] | None = None,
    limit: int = 500,
) -> dict:
    """Summarize latest local run evidence for official AutoForm examples."""
    return official_sample_run_summary(
        search_dir=search_dir,
        mode=mode,
        expected_examples=expected_examples,
        limit=limit,
    )


def autoform_run_forming_job(
    args: list[str],
    dry_run: bool = True,
    timeout: int | None = None,
    working_dir: str | None = None,
) -> dict:
    """Run AFFormingJob with explicit command line arguments."""
    # `run_forming_job` returns a command list for dry runs and a
    # `subprocess.CompletedProcess` for real executions.  Normalize both shapes
    # to one JSON ready response for MCP clients.
    result = run_forming_job(
        args,
        dry_run=dry_run,
        timeout=timeout,
        working_dir=Path(working_dir) if working_dir else None,
    )
    if isinstance(result, list):
        return {"dry_run": True, "command": result}
    return {
        "dry_run": False,
        "command": result.args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def autoform_forming_job_plan(args: list[str], working_dir: str | None = None) -> dict:
    """Return a structured AFFormingJob command preview."""
    return forming_job_plan(args, working_dir=Path(working_dir) if working_dir else None)


def autoform_collect_forming_job_logs(search_dir: str, limit: int = 20) -> list[dict]:
    """Return local AFFormingJob log files and short previews."""
    return collect_forming_job_logs(Path(search_dir), limit=limit)


def autoform_list_example_projects() -> list[dict]:
    """Return official .afd examples from AutoForm ProgramData."""
    return list_example_projects()


def autoform_inspect_afd(afd_path: str) -> dict:
    """Return file level metadata for an .afd project."""
    return inspect_afd(Path(afd_path))


def autoform_get_afd_readable_index(
    afd_path: str,
    query: str | None = None,
    min_length: int = 4,
    limit: int = 200,
) -> dict:
    """Extract printable fragments from an .afd file for evidence discovery."""
    return get_afd_readable_index(Path(afd_path), query=query, min_length=min_length, limit=limit)


def autoform_get_afd_project_summary(afd_path: str) -> dict:
    """Return a compact candidate summary extracted from readable .afd fragments."""
    return get_afd_project_summary(Path(afd_path))


def autoform_list_executables() -> list[dict]:
    """Return AutoForm bin executable and command entries."""
    return list_executables()


def register_project_tools(mcp: Any) -> None:
    """Register project and installation MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_discover_installation)
    mcp.add_tool(autoform_start_ui)
    mcp.add_tool(autoform_open_afd)
    mcp.add_tool(autoform_resolve_project)
    mcp.add_tool(autoform_project_run)
    mcp.add_tool(autoform_example_project_baseline)
    mcp.add_tool(autoform_official_sample_run_summary)
    mcp.add_tool(autoform_run_forming_job)
    mcp.add_tool(autoform_forming_job_plan)
    mcp.add_tool(autoform_collect_forming_job_logs)
    mcp.add_tool(autoform_list_example_projects)
    mcp.add_tool(autoform_inspect_afd)
    mcp.add_tool(autoform_get_afd_readable_index)
    mcp.add_tool(autoform_get_afd_project_summary)
    mcp.add_tool(autoform_list_executables)


__all__ = ['autoform_discover_installation', 'autoform_start_ui', 'autoform_open_afd', 'autoform_resolve_project', 'autoform_project_run', 'autoform_example_project_baseline', 'autoform_official_sample_run_summary', 'autoform_run_forming_job', 'autoform_forming_job_plan', 'autoform_collect_forming_job_logs', 'autoform_list_example_projects', 'autoform_inspect_afd', 'autoform_get_afd_readable_index', 'autoform_get_afd_project_summary', 'autoform_list_executables', 'register_project_tools']
