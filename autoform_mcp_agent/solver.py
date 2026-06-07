"""这个文件处理求解器相关命令：规划、受控执行和日志解析。求解器可能消耗许可证并修改 `.afd` 作业。

This file handles solver-family commands: planning, bounded execution, and log parsing. Solver tools can consume licenses and modify `.afd` jobs.

公开函数把规划和执行分开，记录证据文本，并返回比原始 stdout 更容易排查的结构化摘要。

Public functions separate planning from execution, record evidence strings, and return structured summaries that are easier to debug than raw stdout.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .paths import AutoFormInstallation, get_default_installation


SOLVER_ENTRY_SPECS = {
    "forming-job": {
        "executable": "AFFormingJob_R13.cmd",
        "evidence_files": ["Application_AFJobCommon.dll", "Business_JobRunner.dll", "AFFormingJob_R13.cmd"],
        "confirmed_options": [
            "-h",
            "--help",
            "-v",
            "--version",
            "-jn",
            "-puse",
            "-ls",
            "-queue",
            "-check",
            "-getLogs",
            "-getLogsAndData",
            "-precomputation",
            "-assemblyExport",
        ],
        "purpose": "Job-layer command entry for AutoForm forming jobs.",
    },
    "forming-solver": {
        "executable": "AFFormingSolver.exe",
        "evidence_files": ["AFFormingSolver.exe"],
        "confirmed_options": [
            "-jn",
            "-a",
            "-p",
            "-pg",
            "-i",
            "-bg",
            "-puse",
            "-k",
            "-wafi",
            "-ujn",
            "-ppo",
            "-th",
            "-thInc",
            "-addThermoLics",
            "-mail",
            "-EvaluationData",
            "-cp",
            "-map",
            "-cut",
            "-ls",
            "-v",
        ],
        "purpose": "Direct forming solver entry with confirmed internal usage strings.",
    },
    "postsolve": {
        "executable": "AFFormingPostSolve.exe",
        "evidence_files": ["AFFormingPostSolve.exe"],
        "confirmed_options": ["-jn", "-int", "-str", "-nstr", "-h", "--help", "-v", "--version"],
        "purpose": "Post-solve processing entry; real data input should follow a completed job.",
    },
    "rgen": {
        "executable": "AFFormingRGen.exe",
        "evidence_files": ["Business_CommonAFRGen.dll", "AFFormingRGen.exe"],
        "confirmed_options": ["--version", "<input.afd> {<parameterId> <parameterValue>}", "<input.afd> <parameters_xml_file>"],
        "purpose": "Variant or result generation entry with confirmed input forms in Business_CommonAFRGen.dll.",
    },
    "os-solver": {
        "executable": "AFOSSolver.exe",
        "evidence_files": ["AFOSSolver.exe"],
        "confirmed_options": [],
        "purpose": "One-step solver executable; direct public command syntax is still not confirmed.",
    },
}
PROGRAM_END_RE = re.compile(r"\+{6}\s+Program END(?P<with_errors>\s+with ERRORS)?\s+\[(?P<pid>\d+)\s+(?P<code>-?\d+)\]\.")
OPEN_POSTFILE_RE = re.compile(r'post:\s+Postfile\s+"(?P<path>[^"]+)"\s+opened\.', re.IGNORECASE)
CLOSE_POSTFILE_RE = re.compile(r'post:\s+Postfile\s+"(?P<path>[^"]+)"\s+closed\.', re.IGNORECASE)
VERSION_RE = re.compile(r"^[|\s]*Version:\s+(?P<version>.*?)(?:\s*\|)?$", re.MULTILINE)
BUILD_RE = re.compile(r"^[|\s]*Build:\s+(?P<build>.*?)(?:\s*\|)?$", re.MULTILINE)
LOG_TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
SOLVER_LOG_PATTERNS = ["log_AFFormingRGen_*.txt", "log_AFFormingPostSolve_*.txt", "log_AFFormingJob_*.txt", "log_AFFormingSolver_*.txt"]


def solver_capability_specs(
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> list[dict]:
    """Return solver and job command specs grounded in local binary evidence."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    specs = []
    for key, spec in SOLVER_ENTRY_SPECS.items():
        executable = root / spec["executable"]
        evidence_files = [_evidence_file_fact(root / name, spec["confirmed_options"]) for name in spec["evidence_files"]]
        specs.append(
            {
                "key": key,
                "purpose": spec["purpose"],
                "executable": str(executable),
                "executable_exists": executable.exists(),
                "confirmed_options": spec["confirmed_options"],
                "evidence_files": evidence_files,
                "syntax_status": "confirmed_markers_present" if any(item["matched_markers"] for item in evidence_files) else "entry_present_without_marker_match",
            }
        )
    return specs


def forming_job_check_plan(
    input_file: str | Path,
    threads: int = 1,
    queue_name: str | None = None,
    queue_position: str = "Bottom",
    license_server: str | None = None,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Plan an AFFormingJob input check command."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    command = [str(root / "AFFormingJob_R13.cmd"), "-jn", str(Path(input_file)), "-puse", str(threads), "-check"]
    if license_server:
        command.extend(["-ls", license_server])
    if queue_name:
        command.extend(["-queue", queue_name, queue_position])
    return _command_plan("forming-job-check", command, "Uses confirmed -jn, -puse and -check options from AFJobCommon/JobRunner evidence.")


def forming_solver_kinematic_plan(
    afd_path: str | Path,
    threads: int = 1,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Plan a direct AFFormingSolver kinematic check command."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    command = _forming_solver_base_command(root, afd_path, threads)
    command.append("-k")
    plan = _command_plan(
        "forming-solver-kinematic-check",
        command,
        "Uses confirmed -jn, -a, -puse and -k options. Runtime evidence shows -a is a flag and -jn receives the path stem because AutoForm appends .afd.",
    )
    plan["recommended_env"] = _solver_environment_recommendations(root)
    return plan


def forming_solver_full_plan(
    afd_path: str | Path,
    threads: int = 1,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Plan a direct AFFormingSolver full/default solve command."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    command = _forming_solver_base_command(root, afd_path, threads)
    plan = _command_plan(
        "forming-solver-full-solve",
        command,
        "Uses confirmed -jn, -a and -puse options. Runtime evidence on copied official examples shows the default no -k form performs a full solve and returns Program END 0.",
    )
    plan["recommended_env"] = _solver_environment_recommendations(root)
    return plan


def postsolve_plan(
    input_file: str | Path,
    strip_increments: list[int] | None = None,
    keep_increments: list[int] | None = None,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Plan an AFFormingPostSolve command."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    command = [str(root / "AFFormingPostSolve.exe"), "-jn", str(Path(input_file))]
    if strip_increments:
        command.extend(["-str", *[str(item) for item in strip_increments]])
    if keep_increments:
        command.extend(["-nstr", *[str(item) for item in keep_increments]])
    return _command_plan("postsolve", command, "Uses confirmed -jn, -str and -nstr options from AFFormingPostSolve usage strings.")


def rgen_plan(
    afd_path: str | Path,
    parameter_pairs: list[str] | None = None,
    parameters_xml_file: str | Path | None = None,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Plan an AFFormingRGen command using one of the confirmed input forms."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    command = [str(root / "AFFormingRGen.exe"), "-debug", str(Path(afd_path))]
    if parameters_xml_file is not None:
        command.append(str(Path(parameters_xml_file)))
    else:
        command.extend(parameter_pairs or [])
    return _command_plan("rgen-debug", command, "Uses confirmed -debug <input.afd> plus parameter pairs or parameters XML forms from AFFormingRGen usage output.")


def solver_command_probe(
    entry: str,
    args: list[str] | None = None,
    execute: bool = False,
    timeout: int = 30,
    working_dir: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Preview or execute a bounded solver-family command."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    spec = SOLVER_ENTRY_SPECS.get(entry)
    if spec is None:
        raise ValueError(f"Unknown solver entry: {entry}")
    command = [str(root / spec["executable"]), *list(args or [])]
    result = _command_plan(entry, command, "Bounded solver-family command probe.")
    result.update(
        {
            "executed": False,
            "timeout_seconds": timeout,
            "working_dir": str(Path(working_dir).resolve()) if working_dir is not None else None,
            "extra_env_keys": sorted(extra_env) if extra_env else [],
        }
    )
    if not execute:
        return result
    env = None
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=Path(working_dir).resolve() if working_dir is not None else None,
        env=env,
    )
    executed_result = {
        **result,
        "executed": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if entry == "forming-solver":
        executed_result["stdout_summary"] = parse_forming_solver_stdout(completed.stdout)
    return executed_result


def forming_solver_kinematic_batch_probe(
    afd_paths: list[str | Path],
    threads: int = 1,
    execute: bool = False,
    timeout_per_case: int = 120,
    working_dir: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Preview or execute direct kinematic checks for a batch of .afd projects."""

    cases = []
    for afd_path in afd_paths:
        plan = forming_solver_kinematic_plan(
            afd_path,
            threads=threads,
            install=install,
            bin_dir=bin_dir,
        )
        case = {
            "afd_path": str(Path(afd_path)),
            "plan": plan,
            "executed": False,
        }
        if execute:
            try:
                result = solver_command_probe(
                    "forming-solver",
                    args=plan["command"][1:],
                    execute=True,
                    timeout=timeout_per_case,
                    working_dir=working_dir,
                    extra_env=extra_env or plan.get("recommended_env"),
                    install=install,
                    bin_dir=bin_dir,
                )
                case.update(
                    {
                        "executed": True,
                        "returncode": result["returncode"],
                        "stdout_summary": result.get("stdout_summary"),
                        "stdout_tail": _tail_lines(result.get("stdout", "")),
                        "stderr_tail": _tail_lines(result.get("stderr", "")),
                    }
                )
            except subprocess.TimeoutExpired as exc:
                case.update(
                    {
                        "executed": True,
                        "timed_out": True,
                        "timeout_seconds": timeout_per_case,
                        "stdout_tail": _tail_lines(_coerce_timeout_text(exc.stdout)),
                        "stderr_tail": _tail_lines(_coerce_timeout_text(exc.stderr)),
                    }
                )
        cases.append(case)
    return {
        "case_count": len(cases),
        "threads": threads,
        "executed": execute,
        "timeout_per_case": timeout_per_case,
        "working_dir": str(Path(working_dir).resolve()) if working_dir is not None else None,
        "extra_env_keys": _batch_env_keys(cases, extra_env),
        "cases": cases,
    }


def forming_solver_full_batch_probe(
    afd_paths: list[str | Path],
    threads: int = 1,
    execute: bool = False,
    timeout_per_case: int = 300,
    working_dir: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Preview or execute full/default solves for a batch of .afd projects."""

    cases = []
    for afd_path in afd_paths:
        plan = forming_solver_full_plan(
            afd_path,
            threads=threads,
            install=install,
            bin_dir=bin_dir,
        )
        case = {
            "afd_path": str(Path(afd_path)),
            "plan": plan,
            "executed": False,
        }
        if execute:
            try:
                result = solver_command_probe(
                    "forming-solver",
                    args=plan["command"][1:],
                    execute=True,
                    timeout=timeout_per_case,
                    working_dir=working_dir,
                    extra_env=extra_env or plan.get("recommended_env"),
                    install=install,
                    bin_dir=bin_dir,
                )
                case.update(
                    {
                        "executed": True,
                        "returncode": result["returncode"],
                        "stdout_summary": result.get("stdout_summary"),
                        "stdout_tail": _tail_lines(result.get("stdout", "")),
                        "stderr_tail": _tail_lines(result.get("stderr", "")),
                    }
                )
            except subprocess.TimeoutExpired as exc:
                case.update(
                    {
                        "executed": True,
                        "timed_out": True,
                        "timeout_seconds": timeout_per_case,
                        "stdout_tail": _tail_lines(_coerce_timeout_text(exc.stdout)),
                        "stderr_tail": _tail_lines(_coerce_timeout_text(exc.stderr)),
                    }
                )
        cases.append(case)
    return {
        "case_count": len(cases),
        "threads": threads,
        "executed": execute,
        "timeout_per_case": timeout_per_case,
        "working_dir": str(Path(working_dir).resolve()) if working_dir is not None else None,
        "extra_env_keys": _batch_env_keys(cases, extra_env),
        "cases": cases,
    }


def solver_log_events(log_dir: str | Path | None = None, limit: int = 100) -> list[dict]:
    """Parse solver-family log files for command arguments, requests, errors and dump records."""

    root = Path(log_dir).resolve() if log_dir is not None else Path.cwd().resolve()
    if not root.exists():
        return []
    events = []
    for pattern in SOLVER_LOG_PATTERNS:
        for path in sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True):
            events.extend(_parse_solver_log(path))
    return events[:limit]


def parse_forming_solver_stdout(stdout: str) -> dict:
    """Extract stable facts from AFFormingSolver console output."""

    program_end = None
    program_end_match = PROGRAM_END_RE.search(stdout)
    if program_end_match:
        program_end = {
            "pid": int(program_end_match.group("pid")),
            "code": int(program_end_match.group("code")),
            "with_errors": bool(program_end_match.group("with_errors")),
        }
    opened_postfiles = [match.group("path") for match in OPEN_POSTFILE_RE.finditer(stdout)]
    closed_postfiles = [match.group("path") for match in CLOSE_POSTFILE_RE.finditer(stdout)]
    version_match = VERSION_RE.search(stdout)
    build_match = BUILD_RE.search(stdout)
    return {
        "simulation_successful": "Simulation successfully finished" in stdout,
        "program_end": program_end,
        "opened_postfiles": opened_postfiles,
        "closed_postfiles": closed_postfiles,
        "version": version_match.group("version").strip() if version_match else None,
        "build": build_match.group("build").strip() if build_match else None,
        "cannot_open_file": "Cannot open file" in stdout,
        "usage_printed": "Usage:" in stdout,
        "error_lines": _extract_error_lines(stdout),
    }


def _command_plan(kind: str, command: list[str], evidence: str) -> dict:
    """Return a common command-plan dictionary for solver-family tools."""
    executable = Path(command[0])
    return {
        "kind": kind,
        "command": command,
        "executable": command[0],
        "executable_exists": executable.exists(),
        "evidence": evidence,
        "requires_confirmation": True,
    }


def _forming_solver_job_name(afd_path: str | Path) -> Path:
    """Return the stem path required by `AFFormingSolver -jn`."""
    path = Path(afd_path)
    if path.suffix.casefold() == ".afd":
        path = path.with_suffix("")
    return path.resolve()


def _forming_solver_base_command(root: Path, afd_path: str | Path, threads: int) -> list[str]:
    """Build the shared arguments for direct `AFFormingSolver` calls."""
    return [
        str(root / "AFFormingSolver.exe"),
        "-jn",
        str(_forming_solver_job_name(afd_path)),
        "-a",
        "-puse",
        str(threads),
    ]


def _solver_environment_recommendations(bin_dir: Path) -> dict[str, str]:
    """Suggest environment variables observed to improve local solver runs."""
    recommendations = {}
    if (bin_dir / "MBA_Trans.dll").exists():
        recommendations["AF_HOME_LIB"] = str(bin_dir)
    return recommendations


def _tail_lines(text: str, limit: int = 12) -> list[str]:
    """Return the last non-empty output lines for compact summaries."""
    lines = text.splitlines()
    return lines[-limit:]


def _batch_env_keys(cases: list[dict], extra_env: dict[str, str] | None) -> list[str]:
    """Return environment variable names used across batch probe cases."""
    if extra_env:
        return sorted(extra_env)
    if not cases:
        return []
    return sorted(cases[0].get("plan", {}).get("recommended_env", {}))


def _coerce_timeout_text(value) -> str:
    """Convert timeout output from bytes or text into a safe string."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _extract_error_lines(text: str, limit: int = 20) -> list[str]:
    """Extract likely error or warning lines from solver stdout/log text."""
    lines = []
    for line in text.splitlines():
        lower = line.casefold()
        if "program end" in lower:
            continue
        if "geerror" in lower or "error:" in lower or "cannot open" in lower or "cannot define" in lower:
            lines.append(line.strip())
    return lines[-limit:]


def _parse_solver_log(path: Path) -> list[dict]:
    """Parse command, request, usage, error and dump events from one log file."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    current_timestamp = None
    events = []
    for line_no, line in enumerate(lines, 1):
        timestamp_match = LOG_TIMESTAMP_RE.search(line)
        if timestamp_match:
            current_timestamp = timestamp_match.group("timestamp")
        categories = []
        lower = line.casefold()
        if "argv[" in line:
            categories.append("command_argument")
        if "message: request:" in lower or "createrealizationrequest" in lower:
            categories.append("request")
        if "error" in lower or "geerror" in lower or "exerror" in lower:
            categories.append("error")
        if "dumpfile written" in lower or "application crashed" in lower:
            categories.append("dump")
        if "usage:" in line:
            categories.append("usage")
        if not categories:
            continue
        events.append(
            {
                "timestamp": current_timestamp,
                "entry": _solver_log_entry(path),
                "categories": categories,
                "line": line_no,
                "log_path": str(path),
                "message": line.strip()[:500],
            }
        )
    return events


def _solver_log_entry(path: Path) -> str:
    """Classify a solver-family log filename into a stable source label."""
    name = path.name
    if name.startswith("log_AFFormingRGen"):
        return "rgen"
    if name.startswith("log_AFFormingPostSolve"):
        return "postsolve"
    if name.startswith("log_AFFormingJob"):
        return "forming-job"
    if name.startswith("log_AFFormingSolver"):
        return "forming-solver"
    return "unknown"


def _evidence_file_fact(path: Path, markers: list[str]) -> dict:
    """Read binary evidence markers from an AutoForm DLL or executable."""
    fact = {
        "name": path.name,
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "matched_markers": [],
    }
    if not path.exists():
        return fact
    data = path.read_bytes()
    fact["matched_markers"] = [marker for marker in markers if marker.encode("utf-8", errors="ignore") in data]
    return fact
