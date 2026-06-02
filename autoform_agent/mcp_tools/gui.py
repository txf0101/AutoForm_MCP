"""这个文件把可见 AutoForm 窗口控制和 V1.1 后处理审阅能力包装成 MCP 工具。它连接低层 GUI 原语和高层结果审阅流程。

This file wraps visible AutoForm window control and V1.1 postprocessing review capabilities as MCP tools. It connects low-level GUI primitives with high-level result-review workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..gui_automation import (
    autoform_window_snapshot,
    capture_desktop_screenshot,
    click_autoform_window,
    computer_use_probe,
    drag_autoform_window,
    focus_autoform_window,
    restore_autoform_window,
    visible_window_control_demo,
)
from ..r12_demo import r12_project_view_demo
from ..result_viewer import (
    assess_result_review_readiness,
    build_result_review_plan,
    capture_result_evidence,
    find_latest_result_project,
    open_latest_result_project,
    open_result_project,
    play_forming_animation,
    result_gui_evidence,
    result_review_blockers,
    result_review_capabilities,
    route_result_task,
    select_result_variable,
    set_result_view,
    view_control_evidence_protocol,
)


def autoform_gui_window_snapshot() -> dict:
    """Return visible AutoForm GUI windows for local desktop automation."""

    return autoform_window_snapshot()


def autoform_gui_focus() -> dict:
    """Bring the best visible AutoForm GUI window to the foreground."""

    return focus_autoform_window()


def autoform_gui_restore_window(title_contains: str | None = None, wait_seconds: float = 0.5) -> dict:
    """Restore a visible AutoForm project window and verify interaction readiness."""

    return restore_autoform_window(title_contains=title_contains, wait_seconds=wait_seconds)


def autoform_gui_screenshot(
    output: str = "tmp/result_review/autoform_gui_screenshot.png",
    focus_autoform: bool = True,
    wait_seconds: float = 0.5,
) -> dict:
    """Capture the desktop after optionally focusing AutoForm."""

    return capture_desktop_screenshot(Path(output), focus_autoform=focus_autoform, wait_seconds=wait_seconds)


def autoform_gui_click(
    x: float,
    y: float,
    relative: bool = True,
    focus_first: bool = True,
    restore_window: bool = True,
    wait_seconds: float = 0.2,
) -> dict:
    """Click a coordinate in the selected AutoForm GUI window."""

    return click_autoform_window(
        x,
        y,
        relative=relative,
        focus_first=focus_first,
        restore_window=restore_window,
        wait_seconds=wait_seconds,
    )


def autoform_gui_drag(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    relative: bool = True,
    focus_first: bool = True,
    restore_window: bool = True,
    duration_seconds: float = 0.4,
    steps: int = 12,
    wait_seconds: float = 0.2,
) -> dict:
    """Drag between two coordinates in the selected AutoForm GUI window."""

    return drag_autoform_window(
        start_x,
        start_y,
        end_x,
        end_y,
        relative=relative,
        focus_first=focus_first,
        restore_window=restore_window,
        duration_seconds=duration_seconds,
        steps=steps,
        wait_seconds=wait_seconds,
    )


def autoform_computer_use_probe(
    output: str = "tmp/computer_use_probe/desktop_probe.png",
    capture: bool = False,
    focus_autoform: bool = False,
    wait_seconds: float = 0.2,
) -> dict:
    """Probe whether desktop screenshot and AutoForm window observation are available."""

    return computer_use_probe(
        Path(output),
        capture=capture,
        focus_autoform=focus_autoform,
        wait_seconds=wait_seconds,
    )


def autoform_gui_control_demo(
    output_dir: str = "tmp/r12_visible_window_control_demo",
    execute: bool = False,
    action: str = "restore_focus",
    title_contains: str | None = None,
    keystroke: str | None = None,
    click_x: float = 0.5,
    click_y: float = 0.5,
    drag_start_x: float = 0.40,
    drag_start_y: float = 0.90,
    drag_end_x: float = 0.60,
    drag_end_y: float = 0.90,
    relative: bool = True,
    wait_seconds: float = 0.2,
) -> dict:
    """Plan or run the R12 basic visible-window control demo slice."""

    return visible_window_control_demo(
        Path(output_dir),
        execute=execute,
        action=action,
        title_contains=title_contains,
        keystroke=keystroke,
        click_x=click_x,
        click_y=click_y,
        drag_start_x=drag_start_x,
        drag_start_y=drag_start_y,
        drag_end_x=drag_end_x,
        drag_end_y=drag_end_y,
        relative=relative,
        wait_seconds=wait_seconds,
    )


def autoform_r12_project_view_demo(
    example: str = "Solver_R13",
    afd_path: str | None = None,
    execute: bool = False,
    wait_seconds: float = 2.0,
    view_wait_seconds: float = 0.5,
    verify_screenshot: bool = True,
    output_dir: str = "tmp/r12_project_view_demo",
) -> dict:
    """Plan or run the R12 project-open, top-view, isometric-view demo."""

    return r12_project_view_demo(
        example_name=example,
        afd_path=afd_path,
        execute=execute,
        wait_seconds=wait_seconds,
        view_wait_seconds=view_wait_seconds,
        verify_screenshot=verify_screenshot,
        output_dir=output_dir,
    )


def autoform_result_query_capabilities(autoform_version: str | None = None) -> dict:
    """Return P0/P1 result-review variables, views, routes and evidence limits."""

    return result_review_capabilities(autoform_version=autoform_version)


def autoform_result_gui_evidence(scope: str = "all", workspace: str | None = None) -> dict:
    """Return local GUI-control evidence and known V1.1 result-review gaps."""

    return result_gui_evidence(scope=scope, workspace=workspace)


def autoform_result_blockers(scope: str = "v1_1", include_completed: bool = False) -> dict:
    """Return current V1.1 result-review blockers, countermeasures and user assistance requests."""

    return result_review_blockers(scope=scope, include_completed=include_completed)


def autoform_result_find_latest(search_dir: str | None = None, workspace: str | None = None, limit: int = 200) -> dict:
    """Find the newest candidate `.afd` result project in run outputs."""

    return find_latest_result_project(search_dir=search_dir, workspace=workspace, limit=limit)


def autoform_result_open_latest(
    search_dir: str | None = None,
    workspace: str | None = None,
    execute: bool = False,
    wait_seconds: float = 1.0,
    screenshot: bool = True,
    output_dir: str = "tmp/result_review",
) -> dict:
    """Open the latest result project candidate or return a traceable reason."""

    return open_latest_result_project(
        search_dir=search_dir,
        workspace=workspace,
        execute=execute,
        wait_seconds=wait_seconds,
        screenshot=screenshot,
        output_dir=output_dir,
    )


def autoform_result_open_project(
    project_path: str,
    execute: bool = False,
    wait_seconds: float = 1.0,
    screenshot: bool = True,
    output_dir: str = "tmp/result_review",
) -> dict:
    """Open one AutoForm result project in the visible GUI."""

    return open_result_project(
        project_path,
        execute=execute,
        wait_seconds=wait_seconds,
        screenshot=screenshot,
        output_dir=output_dir,
    )


def autoform_result_show_variable(
    result_name: str,
    operation: str | None = None,
    project_hint: str | None = "current",
    view: str | None = None,
    execute: bool = False,
    verify_screenshot: bool = True,
    output_dir: str = "tmp/result_review",
) -> dict:
    """Map and prepare a result variable switch such as draw-in or springback."""

    return select_result_variable(
        result_name,
        operation=operation,
        project_hint=project_hint,
        view=view,
        execute=execute,
        verify_screenshot=verify_screenshot,
        output_dir=output_dir,
    )


def autoform_result_set_view(
    view: str,
    execute: bool = False,
    verify_screenshot: bool = True,
    output_dir: str = "tmp/result_review",
) -> dict:
    """Map, plan, or execute a profiled result view shortcut."""

    return set_result_view(view, execute=execute, verify_screenshot=verify_screenshot, output_dir=output_dir)


def autoform_result_view_evidence(
    view: str | None = None,
    phase: str = "plan",
    execute: bool = False,
    output_dir: str = "tmp/result_review_view_controls",
) -> dict:
    """Plan, capture or compare manual evidence for AutoForm result view controls."""

    return view_control_evidence_protocol(view=view, phase=phase, output_dir=output_dir, execute=execute)


def autoform_result_play_forming_animation(
    operation: str | None = None,
    action: str = "play",
    start_frame: int | None = None,
    end_frame: int | None = None,
    speed: float | None = None,
    duration_seconds: float | None = None,
    capture_mode: str = "keyframes",
    keyframe_count: int = 3,
    execute: bool = False,
    control_profile: str = "autocomp_r13_bottom_strip",
    click_x: float | None = None,
    click_y: float | None = None,
    output_dir: str = "tmp/result_review",
) -> dict:
    """Prepare animation playback, guarded clicks, or a manual user playback observation."""

    return play_forming_animation(
        operation=operation,
        action=action,
        start_frame=start_frame,
        end_frame=end_frame,
        speed=speed,
        duration_seconds=duration_seconds,
        capture_mode=capture_mode,
        keyframe_count=keyframe_count,
        execute=execute,
        control_profile=control_profile,
        click_x=click_x,
        click_y=click_y,
        output_dir=output_dir,
    )


def autoform_result_capture_evidence(
    project_path: str | None = None,
    variable: str | None = None,
    view: str | None = None,
    operation: str | None = None,
    output_dir: str = "tmp/result_review",
    execute: bool = False,
) -> dict:
    """Capture or plan result-review evidence for the current visible window."""

    return capture_result_evidence(
        project_path=project_path,
        variable=variable,
        view=view,
        operation=operation,
        output_dir=output_dir,
        execute=execute,
    )


def autoform_result_route_task(intent: str) -> dict:
    """Map a loose user request to a P1 result-review route."""

    return route_result_task(intent)


def autoform_result_plan_review(
    intent: str,
    search_dir: str | None = None,
    workspace: str | None = None,
    operation: str | None = None,
    view: str | None = None,
) -> dict:
    """Build one P1 result-review plan with variables, view, operation and recovery guidance."""

    return build_result_review_plan(
        intent,
        search_dir=search_dir,
        workspace=workspace,
        operation=operation,
        view=view,
    )


def autoform_result_readiness(
    intent: str | None = None,
    search_dir: str | None = None,
    workspace: str | None = None,
    operation: str | None = None,
    view: str | None = None,
    require_window: bool = True,
    limit: int = 200,
) -> dict:
    """Assess whether the current machine is ready for visible result review."""

    return assess_result_review_readiness(
        intent,
        search_dir=search_dir,
        workspace=workspace,
        operation=operation,
        view=view,
        require_window=require_window,
        limit=limit,
    )


def register_gui_tools(mcp: Any) -> None:
    """Register GUI and result-review MCP tools on one FastMCP instance."""

    mcp.add_tool(autoform_gui_window_snapshot)
    mcp.add_tool(autoform_gui_focus)
    mcp.add_tool(autoform_gui_restore_window)
    mcp.add_tool(autoform_gui_screenshot)
    mcp.add_tool(autoform_gui_click)
    mcp.add_tool(autoform_gui_drag)
    mcp.add_tool(autoform_computer_use_probe)
    mcp.add_tool(autoform_gui_control_demo)
    mcp.add_tool(autoform_r12_project_view_demo)
    mcp.add_tool(autoform_result_query_capabilities)
    mcp.add_tool(autoform_result_gui_evidence)
    mcp.add_tool(autoform_result_blockers)
    mcp.add_tool(autoform_result_find_latest)
    mcp.add_tool(autoform_result_open_latest)
    mcp.add_tool(autoform_result_open_project)
    mcp.add_tool(autoform_result_show_variable)
    mcp.add_tool(autoform_result_set_view)
    mcp.add_tool(autoform_result_view_evidence)
    mcp.add_tool(autoform_result_play_forming_animation)
    mcp.add_tool(autoform_result_capture_evidence)
    mcp.add_tool(autoform_result_route_task)
    mcp.add_tool(autoform_result_plan_review)
    mcp.add_tool(autoform_result_readiness)


__all__ = [
    "autoform_gui_window_snapshot",
    "autoform_gui_focus",
    "autoform_gui_restore_window",
    "autoform_gui_screenshot",
    "autoform_gui_click",
    "autoform_gui_drag",
    "autoform_computer_use_probe",
    "autoform_gui_control_demo",
    "autoform_r12_project_view_demo",
    "autoform_result_query_capabilities",
    "autoform_result_gui_evidence",
    "autoform_result_blockers",
    "autoform_result_find_latest",
    "autoform_result_open_latest",
    "autoform_result_open_project",
    "autoform_result_show_variable",
    "autoform_result_set_view",
    "autoform_result_view_evidence",
    "autoform_result_play_forming_animation",
    "autoform_result_capture_evidence",
    "autoform_result_route_task",
    "autoform_result_plan_review",
    "autoform_result_readiness",
    "register_gui_tools",
]
