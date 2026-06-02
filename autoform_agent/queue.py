"""这个文件规划队列和 LSF 相关命令。队列设置和正在运行的作业都和当前电脑有关。

This file plans queue and LSF commands. Queue settings and active jobs are specific to the current computer.

默认先返回状态和命令计划，只有调用者明确要求时才进入真实执行路径。

By default it returns status and command plans first, and only enters real execution paths when the caller explicitly asks for them.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from .paths import AutoFormInstallation, get_default_installation


def queue_health_check(
    process_names: list[str] | None = None,
    tasklist_output: dict[str, str] | None = None,
) -> dict:
    """Check whether known AutoForm queue and remote service processes are running."""

    names = process_names or ["AFQueueServer.exe", "AFRemoteService.exe"]
    processes = []
    for name in names:
        if tasklist_output is not None:
            rows = parse_tasklist_csv(tasklist_output.get(name, ""))
            error = None
        else:
            rows, error = _tasklist_for_process(name)
        processes.append(
            {
                "name": name,
                "running": bool(rows),
                "instances": rows,
                "error": error,
            }
        )
    return {"processes": processes}


def queue_command_plan(
    action: str,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Return the AutoForm queue maintenance command for a named action."""

    install = install or get_default_installation()
    commands = {
        "file-server": install.bin_dir / "AFFileServer.cmd",
        "remote-user": install.bin_dir / "AFRemoteUser.cmd",
        "kill-server": install.bin_dir / "killQueueServer.cmd",
    }
    if action not in commands:
        raise ValueError(f"Unsupported queue action: {action}")
    command = commands[action]
    return {
        "action": action,
        "command": [str(command)],
        "exists": command.exists(),
        "requires_confirmation": action == "kill-server",
    }


def queue_client_probe(
    action: str,
    queue_name: str = "Queue1",
    status_format: str = "int",
    execute: bool = False,
    timeout: int = 20,
    install: AutoFormInstallation | None = None,
    working_dir: Path | None = None,
) -> dict:
    """Preview or execute read-oriented AFQueueClient commands."""

    install = install or get_default_installation()
    if action == "config":
        args = ["-config"]
    elif action == "status":
        args = ["-status", queue_name, status_format]
    else:
        raise ValueError("action must be config or status")
    command = [str(install.bin_dir / "AFQueueClient.exe"), *args]
    result = {
        "action": action,
        "command": command,
        "executable_exists": Path(command[0]).exists(),
        "working_dir": str((working_dir or Path.cwd()).resolve()),
        "executed": False,
    }
    if not execute:
        return result
    completed = subprocess.run(
        command,
        cwd=result["working_dir"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    parsed = parse_queue_client_config_output(completed.stdout) if action == "config" else {}
    return {
        **result,
        "executed": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parsed": parsed,
    }


def parse_queue_client_config_output(output: str) -> dict:
    """Parse AFQueueClient -config stdout into structured rows when present."""

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return {"exit_marker": None, "queues": [], "messages": []}
    exit_marker = lines[0] if lines[0].lstrip("-").isdigit() else None
    data_lines = lines[1:] if exit_marker is not None else lines
    queues = []
    messages = []
    for line in data_lines:
        parts = line.split()
        if len(parts) >= 5 and parts[1].isdigit():
            queues.append(
                {
                    "name": parts[0],
                    "max_jobs": int(parts[1]),
                    "license_server": parts[2],
                    "restrict_to_parallel_solver": parts[3],
                    "reserved": parts[4],
                    "raw": line,
                }
            )
        else:
            messages.append(line)
    return {"exit_marker": exit_marker, "queues": queues, "messages": messages}


def lsf_command_plan(
    action: str,
    mode: str = "share",
    commandline: str | None = None,
    username: str | None = None,
    jobname: str | None = None,
    puse: str | int = "0",
    lictype: str = "solver",
    nlics: str | int = "1",
    thermo: str | int = "0",
    workdir: str | Path | None = None,
    jobid: str | None = None,
    input_files: list[str] | None = None,
    output_files: list[str] | None = None,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Return an LSF wrapper command without executing it."""

    install = install or get_default_installation()
    mode_map = {
        "share": install.bin_dir / "aflsf_share.cmd",
        "copy": install.bin_dir / "aflsf_copy.cmd",
    }
    if mode not in mode_map:
        raise ValueError("mode must be share or copy")
    script = mode_map[mode]

    if action == "submit":
        missing = [
            name
            for name, value in {
                "commandline": commandline,
                "username": username,
                "jobname": jobname,
                "workdir": workdir,
            }.items()
            if value in {None, ""}
        ]
        if missing:
            raise ValueError(f"Missing required LSF submit fields: {', '.join(missing)}")
        args = [
            str(script),
            "-bsub",
            str(commandline),
            str(username),
            str(jobname),
            str(puse),
            lictype,
            str(nlics),
            str(thermo),
            str(workdir),
        ]
        if mode == "copy":
            inputs = input_files or []
            outputs = output_files or []
            args.extend([str(len(inputs)), *inputs, str(len(outputs)), *outputs])
    elif action == "status":
        if not jobid:
            raise ValueError("jobid is required for LSF status")
        args = [str(script), "-bjobs", jobid]
    elif action == "cancel":
        if not jobid:
            raise ValueError("jobid is required for LSF cancel")
        args = [str(script), "-bkill", jobid]
    else:
        raise ValueError("action must be submit, status, or cancel")

    return {
        "action": action,
        "mode": mode,
        "command": args,
        "script_exists": script.exists(),
        "requires_confirmation": action in {"submit", "cancel"},
    }


def parse_tasklist_csv(output: str) -> list[dict]:
    """Parse Windows `tasklist /fo csv` output into dictionaries."""
    rows: list[dict] = []
    for row in csv.reader(line for line in output.splitlines() if line.strip()):
        if len(row) < 5 or row[0].upper().startswith("INFO:"):
            continue
        rows.append(
            {
                "image_name": row[0],
                "pid": row[1],
                "session_name": row[2],
                "session_number": row[3],
                "mem_usage": row[4],
            }
        )
    return rows


def _tasklist_for_process(name: str) -> tuple[list[dict], str | None]:
    """Run `tasklist` for one image name and return rows plus any error text."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return [], str(exc)
    if result.returncode != 0:
        return [], result.stderr.strip() or result.stdout.strip()
    return parse_tasklist_csv(result.stdout), None
