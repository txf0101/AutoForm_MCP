"""这个文件把求解器计划、探测和相关工作流包装成 MCP 工具。它不直接隐藏风险，执行类动作仍需要明确参数。

This file wraps solver plans, probes, and related workflows as MCP tools. It does not hide risk; execution actions still require explicit parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..solver import (
    forming_job_check_plan,
    forming_solver_full_batch_probe,
    forming_solver_full_plan,
    forming_solver_kinematic_batch_probe,
    forming_solver_kinematic_plan,
    postsolve_plan,
    rgen_plan,
    solver_capability_specs,
    solver_command_probe,
    solver_log_events,
)


def autoform_solver_capability_specs() -> list[dict]:
    """Return solver and job command specs grounded in local binary evidence."""
    return solver_capability_specs()


def autoform_solver_log_events(log_dir: str | None = None, limit: int = 100) -> list[dict]:
    """Parse solver family logs for command, request, usage, error and dump events."""
    return solver_log_events(log_dir=Path(log_dir) if log_dir else None, limit=limit)


def autoform_solver_command_probe(
    entry: str,
    args: list[str] | None = None,
    execute: bool = False,
    timeout: int = 30,
    working_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Preview or execute a bounded solver family command."""
    return solver_command_probe(
        entry,
        args=args,
        execute=execute,
        timeout=timeout,
        working_dir=Path(working_dir) if working_dir else None,
        extra_env=extra_env,
    )


def autoform_forming_job_check_plan(
    input_file: str,
    threads: int = 1,
    queue_name: str | None = None,
    queue_position: str = "Bottom",
    license_server: str | None = None,
) -> dict:
    """Plan an AFFormingJob input check command."""
    return forming_job_check_plan(
        input_file,
        threads=threads,
        queue_name=queue_name,
        queue_position=queue_position,
        license_server=license_server,
    )


def autoform_forming_solver_kinematic_plan(
    afd_path: str,
    threads: int = 1,
) -> dict:
    """Plan a direct AFFormingSolver kinematic check command."""
    return forming_solver_kinematic_plan(afd_path, threads=threads)


def autoform_forming_solver_full_plan(
    afd_path: str,
    threads: int = 1,
) -> dict:
    """Plan a direct AFFormingSolver full/default solve command."""
    return forming_solver_full_plan(afd_path, threads=threads)


def autoform_forming_solver_kinematic_batch_probe(
    afd_paths: list[str],
    threads: int = 1,
    execute: bool = False,
    timeout_per_case: int = 120,
    working_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Preview or execute direct AFFormingSolver kinematic checks for a batch of .afd projects."""
    return forming_solver_kinematic_batch_probe(
        afd_paths,
        threads=threads,
        execute=execute,
        timeout_per_case=timeout_per_case,
        working_dir=Path(working_dir) if working_dir else None,
        extra_env=extra_env,
    )


def autoform_forming_solver_full_batch_probe(
    afd_paths: list[str],
    threads: int = 1,
    execute: bool = False,
    timeout_per_case: int = 300,
    working_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Preview or execute direct AFFormingSolver full/default solves for a batch of .afd projects."""
    return forming_solver_full_batch_probe(
        afd_paths,
        threads=threads,
        execute=execute,
        timeout_per_case=timeout_per_case,
        working_dir=Path(working_dir) if working_dir else None,
        extra_env=extra_env,
    )


def autoform_postsolve_plan(
    input_file: str,
    strip_increments: list[int] | None = None,
    keep_increments: list[int] | None = None,
) -> dict:
    """Plan an AFFormingPostSolve command."""
    return postsolve_plan(input_file, strip_increments=strip_increments, keep_increments=keep_increments)


def autoform_rgen_plan(
    afd_path: str,
    parameter_pairs: list[str] | None = None,
    parameters_xml_file: str | None = None,
) -> dict:
    """Plan an AFFormingRGen command."""
    return rgen_plan(afd_path, parameter_pairs=parameter_pairs, parameters_xml_file=parameters_xml_file)


def register_solver_tools(mcp: Any) -> None:
    """Register solver MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_solver_capability_specs)
    mcp.add_tool(autoform_solver_log_events)
    mcp.add_tool(autoform_solver_command_probe)
    mcp.add_tool(autoform_forming_job_check_plan)
    mcp.add_tool(autoform_forming_solver_kinematic_plan)
    mcp.add_tool(autoform_forming_solver_full_plan)
    mcp.add_tool(autoform_forming_solver_kinematic_batch_probe)
    mcp.add_tool(autoform_forming_solver_full_batch_probe)
    mcp.add_tool(autoform_postsolve_plan)
    mcp.add_tool(autoform_rgen_plan)


__all__ = ['autoform_solver_capability_specs', 'autoform_solver_log_events', 'autoform_solver_command_probe', 'autoform_forming_job_check_plan', 'autoform_forming_solver_kinematic_plan', 'autoform_forming_solver_full_plan', 'autoform_forming_solver_kinematic_batch_probe', 'autoform_forming_solver_full_batch_probe', 'autoform_postsolve_plan', 'autoform_rgen_plan', 'register_solver_tools']
