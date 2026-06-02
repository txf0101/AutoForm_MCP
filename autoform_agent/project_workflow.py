"""这个文件把工程解析、复制、可选 GUI 打开、求解器执行和结果证据打包成一个可复现流程。它是官方样例和用户工程运行的主业务层。

This file turns project resolution, copying, optional GUI opening, solver execution, and result evidence packaging into one reproducible workflow. It is the main business layer for official examples and user projects.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
from typing import Iterable

from .inventory import get_afd_project_summary, list_example_projects
from .paths import AutoFormInstallation, get_default_installation
from .process import open_afd, open_afd_observer
from .results import report_delivery_plan, result_inventory
from .solver import forming_solver_full_batch_probe, forming_solver_kinematic_batch_probe


PROJECT_WORKFLOW_SCHEMA_VERSION = "1.0"
DEFAULT_RUN_ROOT = Path("output") / "project_runs"
DEFAULT_BASELINE_PATH = Path("docs") / "example_project_baselines.json"
DEFAULT_GUI_OBSERVATION_WAIT_SECONDS = 3.0


def resolve_project_input(
    *,
    afd_path: str | Path | None = None,
    example_name: str | None = None,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Resolve either an explicit `.afd` path or an official example name."""

    if afd_path is not None:
        path = Path(afd_path).resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return {"source": "explicit_path", "path": str(path), "name": path.name}

    requested = (example_name or "Solver_R13").casefold().replace(".afd", "")
    examples = list_example_projects(install=install or get_default_installation())
    for item in examples:
        stem = Path(item["path"]).stem.casefold()
        if requested == stem or requested in stem:
            return {"source": "official_example", "path": item["path"], "name": item["name"]}
    raise FileNotFoundError(f"No official example matched {example_name!r}.")


def project_run_workflow(
    *,
    afd_path: str | Path | None = None,
    example_name: str | None = "Solver_R13",
    mode: str = "kinematic",
    threads: int = 1,
    output_root: str | Path | None = None,
    execute: bool = False,
    timeout: int | None = None,
    open_gui: bool = False,
    gui_wait_seconds: float = DEFAULT_GUI_OBSERVATION_WAIT_SECONDS,
    workspace: str | Path | None = None,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Plan or execute a reproducible open-and-run workflow for one project.

    `open_gui=True` starts AutoForm Forming with the copied run project before
    the direct solver command runs.  This gives the user an interactive window
    for observing the project while preserving the solver stdout summary as the
    authoritative automation result.
    """

    normalized_mode = _normalize_mode(mode)
    install = install or get_default_installation()
    resolved = resolve_project_input(afd_path=afd_path, example_name=example_name, install=install)
    source_path = Path(resolved["path"]).resolve()
    run_dir = _run_dir(Path(output_root or DEFAULT_RUN_ROOT), source_path, normalized_mode)
    working_project = run_dir / source_path.name
    timeout_seconds = timeout or (120 if normalized_mode == "kinematic" else 300)

    # Executed runs work from a copied `.afd` so official examples and user
    # source projects stay unchanged.  `open_afd()` validates that the target
    # project exists even in dry-run mode, so the copy has to happen before the
    # GUI command is calculated for an executed workflow.
    if execute:
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, working_project)
        command_input = working_project
    else:
        command_input = source_path

    gui_command = open_afd(command_input, install=install, dry_run=True)
    gui_observation = open_afd_observer(command_input, install=install, dry_run=True)
    result = {
        "schema_version": PROJECT_WORKFLOW_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "mode": normalized_mode,
        "threads": threads,
        "execute": execute,
        "timeout_seconds": timeout_seconds,
        "project": resolved,
        "run_dir": str(run_dir.resolve()),
        "working_project": str(working_project.resolve()),
        "copy_project": execute,
        "gui_command": gui_command,
        "gui_observation": gui_observation,
        "summary": _safe_project_summary(source_path),
    }
    if not execute:
        result["solver"] = _solver_probe(command_input, normalized_mode, threads, False, timeout_seconds, run_dir)
        result["status"] = "planned"
        return result

    if open_gui:
        result["gui_observation"] = open_afd_observer(working_project, install=install, dry_run=False)
        result["gui_command"] = result["gui_observation"]["command"]
        result["gui_open_requested"] = True
        if gui_wait_seconds > 0:
            # Give AutoForm Forming a short chance to create its window before
            # the solver begins writing into the same copied project file.
            time.sleep(gui_wait_seconds)
        result["gui_observation"]["startup_wait_seconds"] = max(gui_wait_seconds, 0)
    result["solver"] = _solver_probe(working_project, normalized_mode, threads, True, timeout_seconds, run_dir)
    result["inventory"] = result_inventory(search_dir=run_dir, workspace=workspace or Path.cwd(), limit=100)
    result["report_package"] = report_delivery_plan(
        run_dir / "result_package",
        search_dir=run_dir,
        workspace=workspace or Path.cwd(),
        dry_run=False,
        limit=100,
    )
    result["status"] = _workflow_status(result["solver"])
    _write_json(run_dir / "run_manifest.json", result)
    return result


def example_project_baseline(
    output_path: str | Path | None = None,
    *,
    execute: bool = False,
    threads: int = 1,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Build the 1.0 official-example baseline table used by docs and tests."""

    install = install or get_default_installation()
    examples = list_example_projects(install=install)
    rows = []
    for item in examples:
        path = Path(item["path"])
        rows.append(
            {
                "name": item["name"],
                "path": item["path"],
                "summary": _safe_project_summary(path),
                "kinematic": project_run_workflow(
                    afd_path=path,
                    example_name=None,
                    mode="kinematic",
                    threads=threads,
                    execute=execute,
                    install=install,
                )["solver"],
                "full": project_run_workflow(
                    afd_path=path,
                    example_name=None,
                    mode="full",
                    threads=threads,
                    execute=False,
                    install=install,
                )["solver"],
            }
        )
    baseline = {
        "schema_version": PROJECT_WORKFLOW_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "execute": execute,
        "example_count": len(rows),
        "examples": rows,
    }
    if output_path is not None:
        _write_json(Path(output_path), baseline)
    return baseline


def official_sample_run_summary(
    search_dir: str | Path | None = None,
    *,
    mode: str | None = "kinematic",
    expected_examples: Iterable[str] | None = None,
    install: AutoFormInstallation | None = None,
    limit: int = 500,
) -> dict:
    """Summarize latest run evidence for official AutoForm examples."""

    root = Path(search_dir or DEFAULT_RUN_ROOT).resolve()
    normalized_mode = None if mode in {None, "", "all"} else _normalize_mode(str(mode))
    expected, expected_source, expected_error = _expected_example_names(expected_examples, install)
    expected_keys = {_example_key(name) for name in expected}
    manifests = _load_run_manifests(root, limit=limit)
    latest_by_example: dict[str, dict] = {}
    extra_runs = []
    for record in manifests:
        payload = record["payload"]
        if normalized_mode is not None and payload.get("mode") != normalized_mode:
            continue
        summary = _manifest_run_summary(record)
        key = _example_key(summary["example_name"])
        if expected_keys and key not in expected_keys:
            extra_runs.append(summary)
            continue
        existing = latest_by_example.get(key)
        if existing is None or summary["sort_time"] > existing["sort_time"]:
            latest_by_example[key] = summary

    rows = []
    missing = []
    failed = []
    expected_order = expected or sorted({summary["example_name"] for summary in latest_by_example.values()})
    for name in expected_order:
        key = _example_key(name)
        summary = latest_by_example.get(key)
        if summary is None:
            missing.append(_display_example_name(name))
            rows.append(
                {
                    "name": _display_example_name(name),
                    "status": "missing",
                    "latest_manifest": None,
                    "solver_returncode": None,
                    "simulation_successful": False,
                    "program_end_code": None,
                    "stdout_evidence": [],
                }
            )
            continue
        public_summary = _public_run_summary(summary)
        rows.append(public_summary)
        if public_summary["status"] != "passed":
            failed.append(public_summary["name"])

    covered_count = len([item for item in rows if item["status"] != "missing"])
    passing_count = len([item for item in rows if item["status"] == "passed"])
    if expected_order and not missing and not failed:
        status = "all_expected_examples_passed"
    elif rows:
        status = "incomplete_or_failed"
    else:
        status = "no_run_manifests_found"

    return {
        "schema_version": "1.1",
        "created_at": _utc_now(),
        "root": str(root),
        "mode": normalized_mode or "all",
        "expected_example_source": expected_source,
        "expected_example_error": expected_error,
        "expected_example_count": len(expected_order),
        "run_manifest_count": len(manifests),
        "covered_example_count": covered_count,
        "passing_example_count": passing_count,
        "missing_examples": missing,
        "failed_examples": failed,
        "status": status,
        "examples": rows,
        "extra_runs": [_public_run_summary(item) for item in extra_runs[:limit]],
        "evidence_boundary": (
            "This summary reads local run_manifest.json files and solver stdout summaries. "
            "It verifies batch solver completion evidence; visible GUI post-processing remains a separate gate."
        ),
    }


def _solver_probe(
    afd_path: Path,
    mode: str,
    threads: int,
    execute: bool,
    timeout: int,
    working_dir: Path,
) -> dict:
    """Call the correct solver batch helper for one project."""

    if mode == "kinematic":
        return forming_solver_kinematic_batch_probe(
            [afd_path],
            threads=threads,
            execute=execute,
            timeout_per_case=timeout,
            working_dir=working_dir,
        )
    return forming_solver_full_batch_probe(
        [afd_path],
        threads=threads,
        execute=execute,
        timeout_per_case=timeout,
        working_dir=working_dir,
    )


def _workflow_status(solver: dict) -> str:
    """Classify one workflow from the first solver case."""

    cases = solver.get("cases") or []
    if not cases:
        return "no_case"
    case = cases[0]
    if case.get("timed_out"):
        return "timeout"
    if not case.get("executed"):
        return "planned"
    return "completed" if case.get("returncode") == 0 else "failed"


def _expected_example_names(
    expected_examples: Iterable[str] | None,
    install: AutoFormInstallation | None,
) -> tuple[list[str], str, str | None]:
    if expected_examples is not None:
        return [_display_example_name(name) for name in expected_examples], "explicit_parameter", None
    try:
        examples = list_example_projects(install=install or get_default_installation())
    except Exception as exc:
        return [], "local_install_discovery_failed", str(exc)
    return [_display_example_name(item["name"]) for item in examples], "local_installation_examples", None


def _load_run_manifests(root: Path, limit: int) -> list[dict]:
    if not root.exists():
        return []
    records = []
    for manifest_path in root.rglob("run_manifest.json"):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            payload = {"manifest_read_error": str(exc)}
        records.append(
            {
                "path": manifest_path.resolve(),
                "payload": payload,
                "last_modified": manifest_path.stat().st_mtime,
            }
        )
    records.sort(key=lambda item: item["last_modified"], reverse=True)
    return records[:limit]


def _manifest_run_summary(record: dict) -> dict:
    payload = record["payload"]
    case = _first_solver_case(payload)
    stdout_summary = case.get("stdout_summary") if isinstance(case, dict) else {}
    program_end = stdout_summary.get("program_end") if isinstance(stdout_summary, dict) else {}
    returncode = case.get("returncode") if isinstance(case, dict) else None
    simulation_successful = bool(stdout_summary.get("simulation_successful")) if isinstance(stdout_summary, dict) else False
    program_end_code = program_end.get("code") if isinstance(program_end, dict) else None
    passed = returncode == 0 and simulation_successful and program_end_code in {0, None}
    return {
        "name": _display_example_name(_manifest_example_name(payload)),
        "example_name": _display_example_name(_manifest_example_name(payload)),
        "status": "passed" if passed else "failed",
        "latest_manifest": str(record["path"]),
        "run_dir": payload.get("run_dir"),
        "working_project": payload.get("working_project"),
        "created_at": payload.get("created_at"),
        "mode": payload.get("mode"),
        "execute": payload.get("execute"),
        "solver_returncode": returncode,
        "simulation_successful": simulation_successful,
        "program_end_code": program_end_code,
        "stdout_evidence": _stdout_evidence(case),
        "sort_time": _manifest_sort_time(payload, record["last_modified"]),
    }


def _public_run_summary(summary: dict) -> dict:
    return {key: value for key, value in summary.items() if key != "sort_time"}


def _first_solver_case(payload: dict) -> dict:
    solver = payload.get("solver") if isinstance(payload, dict) else {}
    cases = solver.get("cases") if isinstance(solver, dict) else []
    if cases and isinstance(cases[0], dict):
        return cases[0]
    return {}


def _manifest_example_name(payload: dict) -> str:
    project = payload.get("project") if isinstance(payload, dict) else {}
    if isinstance(project, dict) and project.get("name"):
        return str(project["name"])
    working_project = payload.get("working_project") if isinstance(payload, dict) else None
    if working_project:
        return Path(str(working_project)).name
    return "unknown.afd"


def _stdout_evidence(case: dict) -> list[str]:
    tail = case.get("stdout_tail") if isinstance(case, dict) else []
    if not isinstance(tail, list):
        return []
    return [
        str(line)
        for line in tail
        if "Simulation successfully finished" in str(line) or "Program END" in str(line)
    ]


def _manifest_sort_time(payload: dict, fallback: float) -> float:
    created_at = payload.get("created_at") if isinstance(payload, dict) else None
    if isinstance(created_at, str):
        try:
            return datetime.fromisoformat(created_at).timestamp()
        except ValueError:
            pass
    return float(fallback)


def _display_example_name(name: str) -> str:
    path_name = Path(str(name)).name
    return path_name if path_name.casefold().endswith(".afd") else f"{path_name}.afd"


def _example_key(name: str) -> str:
    return _display_example_name(name).casefold()


def _run_dir(output_root: Path, source_path: Path, mode: str) -> Path:
    """Return a timestamped directory for one project run."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_stem = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in source_path.stem)
    return output_root / f"{timestamp}_{safe_stem}_{mode}"


def _safe_project_summary(path: Path) -> dict:
    """Return a project summary while preserving error details in JSON."""

    try:
        return get_afd_project_summary(path)
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}


def _normalize_mode(mode: str) -> str:
    """Accept friendly mode names while keeping the public contract small."""

    normalized = mode.strip().casefold()
    if normalized in {"kinematic", "check", "k"}:
        return "kinematic"
    if normalized in {"full", "solve", "run"}:
        return "full"
    raise ValueError("mode must be kinematic or full")


def _write_json(path: Path, payload: dict) -> None:
    """Write UTF-8 JSON with parent creation for workflow artifacts."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()
