"""这个文件把队列探测和队列命令计划包装成 MCP 工具。它帮助外部客户端了解本机或远程队列是否可用。

This file wraps queue probes and queue command plans as MCP tools. It helps external clients understand whether local or remote queue support is available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..queue import lsf_command_plan, queue_client_probe, queue_command_plan, queue_health_check


def autoform_queue_health_check() -> dict:
    """Check whether known AutoForm queue processes are running."""
    return queue_health_check()


def autoform_queue_command_plan(action: str) -> dict:
    """Return the AutoForm queue helper command for a named action."""
    return queue_command_plan(action)


def autoform_queue_client_probe(
    action: str,
    queue_name: str = "Queue1",
    status_format: str = "int",
    execute: bool = False,
    timeout: int = 20,
    working_dir: str | None = None,
) -> dict:
    """Preview or execute read oriented AFQueueClient commands."""
    return queue_client_probe(
        action,
        queue_name=queue_name,
        status_format=status_format,
        execute=execute,
        timeout=timeout,
        working_dir=Path(working_dir) if working_dir else None,
    )


def autoform_lsf_command_plan(
    action: str,
    mode: str = "share",
    commandline: str | None = None,
    username: str | None = None,
    jobname: str | None = None,
    puse: str = "0",
    lictype: str = "solver",
    nlics: str = "1",
    thermo: str = "0",
    workdir: str | None = None,
    jobid: str | None = None,
    input_files: list[str] | None = None,
    output_files: list[str] | None = None,
) -> dict:
    """Return an AutoForm LSF wrapper command without executing it."""
    return lsf_command_plan(
        action=action,
        mode=mode,
        commandline=commandline,
        username=username,
        jobname=jobname,
        puse=puse,
        lictype=lictype,
        nlics=nlics,
        thermo=thermo,
        workdir=workdir,
        jobid=jobid,
        input_files=input_files,
        output_files=output_files,
    )


def register_queue_tools(mcp: Any) -> None:
    """Register queue and LSF MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_queue_health_check)
    mcp.add_tool(autoform_queue_command_plan)
    mcp.add_tool(autoform_queue_client_probe)
    mcp.add_tool(autoform_lsf_command_plan)


__all__ = ['autoform_queue_health_check', 'autoform_queue_command_plan', 'autoform_queue_client_probe', 'autoform_lsf_command_plan', 'register_queue_tools']
