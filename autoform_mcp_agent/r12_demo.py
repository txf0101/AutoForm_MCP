"""这个文件把打开工程和切换视角串成一个可审计演示。它用于确认可见 AutoForm 窗口能按计划被观察和控制。

This file combines project opening and view switching into one auditable demo. It confirms that a visible AutoForm window can be observed and controlled as planned.

演示目标是打开官方样例工程，并在调用方明确传入视角序列时切换视角。默认先规划，真实动作需要显式执行。

The demo opens an official example project and switches views only when the caller provides a view sequence. It plans first by default; real desktop actions require explicit execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import time

from .gui_automation import autoform_window_snapshot
from .process import open_afd_observer
from .project_workflow import resolve_project_input
from .result_viewer import resolve_result_view, set_result_view


DEFAULT_R12_PROJECT_VIEW_OUTPUT_DIR = Path("tmp") / "r12_project_view_demo"
DEFAULT_R12_VIEW_SEQUENCE: tuple[str, ...] = ()


def r12_project_view_demo(
    *,
    example_name: str = "Solver_R13",
    afd_path: str | Path | None = None,
    execute: bool = False,
    wait_seconds: float = 2.0,
    view_wait_seconds: float = 0.5,
    verify_screenshot: bool = True,
    view_sequence: str | list[str] | tuple[str, ...] | None = None,
    output_dir: str | Path = DEFAULT_R12_PROJECT_VIEW_OUTPUT_DIR,
) -> dict:
    """Plan or execute the R12 project-open and view-switch acceptance slice."""

    output_root = Path(output_dir)
    requested_views = _normalize_view_sequence(view_sequence)
    resolved = resolve_project_input(afd_path=afd_path, example_name=example_name)
    project_path = Path(resolved["path"])
    target_title = project_path.name
    base = {
        "schema_version": "autoform.r12.project_view_demo.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "r_stage": "R12",
        "demo_slice": "open_project_optional_view_sequence",
        "execute": bool(execute),
        "project": resolved,
        "target_title_contains": target_title,
        "view_sequence": requested_views,
        "output_dir": str(output_root),
        "approval_boundary": {
            "requires_execute_for_desktop_side_effects": True,
            "desktop_actions_when_executed": [
                "open AutoForm Forming project window",
                "focus visible AutoForm window",
                "send requested view shortcuts when view_sequence is provided",
                "capture screenshots when verify_screenshot is enabled",
            ],
        },
        "source_basis": [
            {
                "path": "autoform_mcp_agent/process.py",
                "fact": "open_afd_observer launches AFFormingUI.exe -file for a selected .afd project.",
            },
            {
                "path": "autoform_mcp_agent/result_viewer.py",
                "fact": "RESULT_VIEWS maps top view to shortcut Z and isometric view to shortcut E.",
            },
            {
                "path": "README.md",
                "fact": "R12 visible-window controls and result-set-view shortcuts are documented as guarded GUI actions.",
            },
        ],
        "stages": [],
    }

    if not execute:
        open_plan = open_afd_observer(project_path, dry_run=True)
        stages = [{"stage": "open_project", "status": "planned_requires_execute", "result": open_plan}]
        for view_key in requested_views:
            stages.append(
                {
                    "stage": _view_stage_name(view_key),
                    "status": "planned_requires_execute",
                    "shortcut": _view_shortcut(view_key),
                }
            )
        return {
            **base,
            "status": "planned_not_executed",
            "approval_required": True,
            "stages": stages,
            "blocking_reasons": [],
            "recommended_next_actions": [
                "Run again with --execute after confirming the target AutoForm desktop session is safe to control.",
            ],
        }

    stages: list[dict] = []
    blockers: list[str] = []
    open_result = open_afd_observer(project_path, dry_run=False)
    target_pid = open_result.get("pid")
    stages.append({"stage": "open_project", "status": "launched" if open_result.get("launched") else "blocked", "result": open_result})
    if not open_result.get("launched"):
        blockers.append("project_window_launch_failed")

    window_after_open, effective_pid = _wait_for_target_window(
        target_title=target_title,
        preferred_pid=target_pid,
        timeout_seconds=wait_seconds,
    )
    stages.append({"stage": "window_ready_check", "status": _window_ready_status(window_after_open), "result": window_after_open})
    if window_after_open.get("interaction_ready_window_count", 0) < 1:
        blockers.append("interaction_ready_autoform_window")

    view_results: list[dict] = []
    if not blockers:
        for view_key in requested_views:
            view_result = set_result_view(
                view_key,
                execute=True,
                verify_screenshot=verify_screenshot,
                output_dir=output_root / view_key,
                title_contains=target_title,
                target_pid=effective_pid,
            )
            stage_name = f"set_{view_key}_view"
            view_results.append(view_result)
            stages.append({"stage": stage_name, "status": view_result["status"], "result": view_result})
            if not view_result.get("executed"):
                blockers.append(f"{view_key}_view_not_executed")
                break
            if view_wait_seconds > 0:
                time.sleep(view_wait_seconds)

    final_window_snapshot = autoform_window_snapshot(title_contains=target_title, pid=effective_pid)
    status = "completed" if not blockers and len(view_results) == len(requested_views) else "blocked_for_r12_project_view_demo"
    return {
        **base,
        "status": status,
        "approval_required": False,
        "blocking_reasons": blockers,
        "stages": stages,
        "view_results": view_results,
        "effective_target_pid": effective_pid,
        "window_after_open": window_after_open,
        "final_window_snapshot": final_window_snapshot,
        "recommended_next_actions": _next_actions(blockers),
    }


def _window_ready_status(snapshot: dict) -> str:
    if snapshot.get("interaction_ready_window_count", 0) > 0:
        return "interaction_ready"
    if snapshot.get("window_count", 0) > 0:
        return "visible_but_not_interaction_ready"
    return "no_visible_autoform_window"


def _normalize_view_sequence(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        raw_items = []
    elif isinstance(value, str):
        raw_items = [item.strip() for item in re.split(r"[,;，；\s]+", value) if item.strip()]
    else:
        raw_items = [str(item).strip() for item in value if str(item).strip()]
    normalized: list[str] = []
    for item in raw_items:
        resolution = resolve_result_view(item)
        if resolution.get("matched") and isinstance(resolution.get("view"), dict):
            normalized.append(str(resolution["view"]["key"]))
        else:
            normalized.append(item)
    return normalized


def _view_stage_name(view_key: str) -> str:
    return f"set_{view_key}_view"


def _view_shortcut(view_key: str) -> str | None:
    resolution = resolve_result_view(view_key)
    view = resolution.get("view") if isinstance(resolution.get("view"), dict) else {}
    shortcut = view.get("r13_shortcut") if isinstance(view, dict) else None
    return str(shortcut) if shortcut else None


def _wait_for_target_window(*, target_title: str, preferred_pid: int | None, timeout_seconds: float) -> tuple[dict, int | None]:
    deadline = time.monotonic() + max(timeout_seconds, 0)
    last_snapshot = {"window_count": 0, "interaction_ready_window_count": 0, "interaction_ready_windows": [], "windows": []}
    while True:
        if preferred_pid is not None:
            preferred_snapshot = autoform_window_snapshot(title_contains=target_title, pid=preferred_pid)
            if preferred_snapshot.get("interaction_ready_window_count", 0) > 0:
                return preferred_snapshot, preferred_pid
            last_snapshot = preferred_snapshot
        fallback_snapshot = autoform_window_snapshot(title_contains=target_title)
        if fallback_snapshot.get("interaction_ready_window_count", 0) > 0:
            window = fallback_snapshot["interaction_ready_windows"][0]
            return fallback_snapshot, int(window["pid"])
        last_snapshot = fallback_snapshot
        if time.monotonic() >= deadline:
            return last_snapshot, preferred_pid
        time.sleep(0.5)


def _next_actions(blockers: list[str]) -> list[str]:
    if not blockers:
        return [
            "Use the captured screenshots and view result records as R12 evidence.",
            "Continue only after human review if a later step needs real solving or result interpretation.",
        ]
    actions = []
    if "interaction_ready_autoform_window" in blockers:
        actions.append("Bring the AutoForm project window onto the visible desktop, then rerun the demo.")
    if "project_window_launch_failed" in blockers:
        actions.append("Check the resolved .afd path and AFFormingUI.exe path before rerunning.")
    if any(item.endswith("_view_not_executed") for item in blockers):
        actions.append("Confirm the AutoForm window is focused and that R13 shortcuts Z and E are available.")
    return actions or ["Inspect the stage results and rerun after clearing the blocking condition."]
