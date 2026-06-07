"""这个文件记录已经识别过的 AutoForm 可执行程序，并为它们生成受控命令计划。默认先告诉用户会运行什么命令。

This file records known AutoForm executables and builds bounded command plans for them. By default it first shows the user exactly what command would run.

AutoForm 有很多 `.exe` 和 `.cmd`。这里只登记本项目有证据的入口，并把“计划命令”和“真实执行”分开，避免误动许可证、队列、材料库或输出文件。

AutoForm exposes many `.exe` and `.cmd` entries. This module only registers entries backed by local evidence and separates planning from real execution to avoid accidental license, queue, material-library, or output changes.
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .paths import AutoFormInstallation, get_default_installation


@dataclass(frozen=True)
class CommandSpec:
    """Maintainer-owned description of one AutoForm command-line entry.

    `safe_help_args` is a small allow list for bounded help probes.  Real
    business execution remains gated by the caller through `execute=True` or
    higher-level dry-run flags.
    """

    key: str
    executable: str
    category: str
    purpose: str
    evidence: str
    safe_help_args: tuple[str, ...] = ("-help",)
    requires_confirmation: bool = True

    def as_dict(self) -> dict:
        """Return a JSON-ready representation shared by CLI, MCP and tests."""
        return {
            "key": self.key,
            "executable": self.executable,
            "category": self.category,
            "purpose": self.purpose,
            "evidence": self.evidence,
            "safe_help_args": list(self.safe_help_args),
            "requires_confirmation": self.requires_confirmation,
        }


COMMAND_SPECS = {
    # Each entry below should be backed by a local file, command output, log, or
    # official sample.  Add the evidence string first when expanding this list so
    # future maintainers can trace why the entry is considered known.
    "forming-job": CommandSpec(
        key="forming-job",
        executable="AFFormingJob.exe",
        category="simulation_job",
        purpose="Run AutoForm forming jobs through the installed command line entry.",
        evidence="AFFormingJob_R13.cmd forwards arguments to AFFormingJob.exe.",
        safe_help_args=("-help",),
        requires_confirmation=True,
    ),
    "material-converter": CommandSpec(
        key="material-converter",
        executable="AFMat2Mtb.exe",
        category="material",
        purpose="Material conversion entry found in the installed AutoForm bin directory.",
        evidence="AFMat2Mtb.exe is present under the AutoForm bin directory; a demo .mat converted successfully when invoked with the material basename.",
        safe_help_args=("-help", "/?"),
        requires_confirmation=True,
    ),
    "report-office": CommandSpec(
        key="report-office",
        executable="AFReportMSOffice.exe",
        category="report",
        purpose="Microsoft Office report entry found in the installed AutoForm bin directory.",
        evidence="AFReportMSOffice.exe is present under the AutoForm bin directory.",
        safe_help_args=("-help", "/?"),
        requires_confirmation=True,
    ),
    "queue-client": CommandSpec(
        key="queue-client",
        executable="AFQueueClient.exe",
        category="queue",
        purpose="Queue client used by AutoForm queue helper scripts.",
        evidence="AFFileServer.cmd and AFRemoteUser.cmd call AFQueueClient.exe.",
        safe_help_args=("-help", "/?"),
        requires_confirmation=True,
    ),
}


def list_command_specs(
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> list[dict]:
    """Return known command entries with local path status."""

    install = install or get_default_installation()
    # A caller-supplied `bin_dir` is useful in tests and future multi-version
    # diagnostics; production callers normally rely on the discovered install.
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    specs: list[dict] = []
    for spec in COMMAND_SPECS.values():
        path = root / spec.executable
        specs.append(
            {
                **spec.as_dict(),
                "path": str(path),
                "exists": path.exists(),
            }
        )
    return specs


def executable_command_plan(
    entry: str,
    args: list[str] | None = None,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Return a structured AutoForm executable command without running it."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    spec = _resolve_spec(entry)
    # Unknown entries are still allowed as previews so inventory work can inspect
    # newly found executables.  They remain confirmation-required by default.
    executable = spec.executable if spec else entry
    path = Path(executable)
    if not path.is_absolute():
        path = root / executable
    path = path.resolve()
    raw_args = list(args or [])
    return {
        "entry": entry,
        "known_spec": spec.as_dict() if spec else None,
        "executable": str(path),
        "executable_exists": path.exists(),
        "args": raw_args,
        "command": [str(path), *raw_args],
        "requires_confirmation": spec.requires_confirmation if spec else True,
        "parameter_status": "preview_only_until_help_or_official_sample_confirms_syntax",
    }


def executable_help_probe(
    entry: str,
    help_arg: str | None = None,
    execute: bool = False,
    timeout: int = 10,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Preview or run a bounded help probe for a known AutoForm executable."""

    spec = _resolve_spec(entry)
    # Use the first known safe help argument unless the caller explicitly asks
    # for another allow-listed form such as `/?`.
    selected_help_arg = help_arg or (spec.safe_help_args[0] if spec else "-help")
    plan = executable_command_plan(entry, [selected_help_arg], install=install, bin_dir=bin_dir)
    allowed_help_args = list(spec.safe_help_args) if spec else [selected_help_arg]
    result = {
        **plan,
        "help_arg": selected_help_arg,
        "allowed_help_args": allowed_help_args,
        "timeout_seconds": timeout,
        "executed": False,
    }
    if not execute:
        return result
    if selected_help_arg not in allowed_help_args:
        raise ValueError(f"Help argument {selected_help_arg!r} is not in the allow list for {entry}.")
    # Keep probes short and captured.  Some AutoForm commands write logs instead
    # of stdout, so callers should inspect both the returned streams and recent
    # log files.
    completed = subprocess.run(
        result["command"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return {
        **result,
        "executed": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def material_conversion_plan(args: list[str] | None = None) -> dict:
    """Return an AFMat2Mtb command preview with caller supplied arguments."""

    return {
        **executable_command_plan("material-converter", args=args),
        "observed_syntax": "Run from the directory containing the .mat file and pass the material basename without the .mat extension.",
        "parameter_status": "observed_for_demo_mat_to_mtb_conversion",
    }


def material_conversion_execute(
    source: str | Path,
    working_dir: str | Path | None = None,
    execute: bool = False,
    timeout: int = 30,
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> dict:
    """Preview or execute AFMat2Mtb conversion for one .mat file."""

    install = install or get_default_installation()
    root = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    executable = (root / "AFMat2Mtb.exe").resolve()
    requested_source = Path(source)
    # AFMat2Mtb was observed to require the current working directory to contain
    # the input `.mat`, while the command argument is the material basename.
    work = Path(working_dir).resolve() if working_dir is not None else requested_source.parent.resolve()
    source_mat = _resolve_material_source(requested_source, work)
    if source_mat.suffix.casefold() != ".mat":
        raise ValueError("AFMat2Mtb conversion expects a .mat source file or a basename resolving to .mat.")

    staged_input = work / source_mat.name
    output_mtb = work / f"{source_mat.stem}.mtb"
    command = [str(executable), source_mat.stem]
    result = {
        "source": str(source_mat),
        "source_exists": source_mat.exists(),
        "working_dir": str(work),
        "staged_input": str(staged_input),
        "output_mtb": str(output_mtb),
        "executable": str(executable),
        "executable_exists": executable.exists(),
        "command": command,
        "observed_syntax": "Run from the directory containing the .mat file and pass the material basename without the .mat extension.",
        "timeout_seconds": timeout,
        "executed": False,
        "output_exists_before": output_mtb.exists(),
    }
    if not execute:
        return result
    if not source_mat.exists():
        raise FileNotFoundError(source_mat)
    work.mkdir(parents=True, exist_ok=True)
    if source_mat.resolve() != staged_input.resolve():
        # Refuse to overwrite a different staged material.  Material conversion
        # is often used with production library files, so silent replacement
        # would make troubleshooting difficult.
        if staged_input.exists() and not filecmp.cmp(source_mat, staged_input, shallow=False):
            raise FileExistsError(f"Refusing to overwrite existing staged material: {staged_input}")
        if not staged_input.exists():
            shutil.copy2(source_mat, staged_input)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=work,
    )
    return {
        **result,
        "executed": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "staged_input_exists_after": staged_input.exists(),
        "output_exists_after": output_mtb.exists(),
        "output_size": output_mtb.stat().st_size if output_mtb.exists() else None,
    }


def report_ms_office_plan(args: list[str] | None = None) -> dict:
    """Return an AFReportMSOffice command preview with caller supplied arguments."""

    return executable_command_plan("report-office", args=args)


def _resolve_spec(entry: str) -> CommandSpec | None:
    """Resolve a command by stable key or executable filename."""
    if entry in COMMAND_SPECS:
        return COMMAND_SPECS[entry]
    lowered = entry.casefold()
    for spec in COMMAND_SPECS.values():
        if spec.executable.casefold() == lowered:
            return spec
    return None


def _resolve_material_source(source: Path, working_dir: Path) -> Path:
    """Find the `.mat` source from absolute paths, relative paths or basenames."""
    candidates = [source]
    if source.suffix == "":
        candidates.append(source.with_suffix(".mat"))
    if not source.is_absolute():
        candidates.append(working_dir / source)
        if source.suffix == "":
            candidates.append(working_dir / source.with_suffix(".mat"))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    if source.suffix == "":
        return (working_dir / source.with_suffix(".mat")).resolve() if not source.is_absolute() else source.with_suffix(".mat").resolve()
    return source.resolve()
