"""这个文件把作业生命周期能力包装成 MCP 工具。外部 MCP host 可以用它提交、查询、等待、取消和归档本地作业。

This file wraps job-lifecycle capabilities as MCP tools. An external MCP host can use it to submit, query, wait for, cancel, and archive local jobs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..jobs import archive_job, cancel_job, job_logs, job_status, list_jobs, submit_job, wait_for_job


def autoform_job_submit(
    command: list[str],
    job_name: str | None = None,
    working_dir: str | None = None,
    execute: bool = False,
) -> dict:
    """Plan or start one lifecycle managed AutoForm related command."""
    return submit_job(command, job_name=job_name, working_dir=working_dir, execute=execute)


def autoform_job_status(job_id: str) -> dict:
    """Return the latest known status for one lifecycle managed job."""
    return job_status(job_id)


def autoform_job_wait(job_id: str, timeout: float | None = None) -> dict:
    """Wait for one lifecycle managed job and persist its final status."""
    return wait_for_job(job_id, timeout=timeout)


def autoform_job_cancel(job_id: str, force: bool = False) -> dict:
    """Request cancellation for one lifecycle managed job."""
    return cancel_job(job_id, force=force)


def autoform_job_logs(job_id: str, preview_bytes: int = 2048) -> dict:
    """Return stdout, stderr and nearby AutoForm logs for one job."""
    return job_logs(job_id, preview_bytes=preview_bytes)


def autoform_job_archive(job_id: str, output_dir: str, dry_run: bool = True) -> dict:
    """Plan or create an archive directory for one lifecycle managed job."""
    return archive_job(job_id, Path(output_dir), dry_run=dry_run)


def autoform_list_jobs() -> list[dict]:
    """Return lifecycle managed jobs, newest first."""
    return list_jobs()


def register_job_tools(mcp: Any) -> None:
    """Register job lifecycle MCP tools on one FastMCP instance."""
    mcp.add_tool(autoform_job_submit)
    mcp.add_tool(autoform_job_status)
    mcp.add_tool(autoform_job_wait)
    mcp.add_tool(autoform_job_cancel)
    mcp.add_tool(autoform_job_logs)
    mcp.add_tool(autoform_job_archive)
    mcp.add_tool(autoform_list_jobs)


__all__ = ['autoform_job_submit', 'autoform_job_status', 'autoform_job_wait', 'autoform_job_cancel', 'autoform_job_logs', 'autoform_job_archive', 'autoform_list_jobs', 'register_job_tools']
