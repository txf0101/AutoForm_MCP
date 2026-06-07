"""这个测试文件检查 R12 打开工程和切换视角演示。每个断言都在确认默认先规划、真实 GUI 动作必须显式开启。

This test file checks the R12 project-open and view-switch demo. Each assertion confirms that planning is the default and real GUI actions require explicit execution.
"""

from pathlib import Path

import autoform_mcp_agent.r12_demo as r12_demo


def _resolved_project(path: Path) -> dict:
    return {"source": "official_example", "path": str(path), "name": path.name}


def test_r12_project_view_demo_dry_run_plans_without_gui_side_effects(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "Solver_R13.afd"
    monkeypatch.setattr(r12_demo, "resolve_project_input", lambda **_kwargs: _resolved_project(project))

    def fake_open_afd_observer(path, dry_run=True):
        assert Path(path) == project
        assert dry_run is True
        return {"mode": "gui_project_observer", "dry_run": True, "command": ["AFFormingUI.exe", "-file", str(path)]}

    monkeypatch.setattr(r12_demo, "open_afd_observer", fake_open_afd_observer)

    result = r12_demo.r12_project_view_demo(execute=False, output_dir=tmp_path)

    assert result["schema_version"] == "autoform.r12.project_view_demo.v1"
    assert result["status"] == "planned_not_executed"
    assert result["approval_required"] is True
    assert result["view_sequence"] == []
    assert [stage["stage"] for stage in result["stages"]] == ["open_project"]


def test_r12_project_view_demo_execute_without_view_sequence_only_opens_project(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "Solver_R13.afd"
    monkeypatch.setattr(r12_demo, "resolve_project_input", lambda **_kwargs: _resolved_project(project))
    monkeypatch.setattr(
        r12_demo,
        "open_afd_observer",
        lambda path, dry_run=True: {
            "mode": "gui_project_observer",
            "dry_run": dry_run,
            "launched": not dry_run,
            "pid": 1234,
            "project_path": str(path),
        },
    )
    ready_snapshot = {
        "window_count": 1,
        "interaction_ready_window_count": 1,
        "interaction_ready_windows": [{"title": "AutoForm Forming R13 - Solver_R13.afd"}],
        "windows": [{"title": "AutoForm Forming R13 - Solver_R13.afd"}],
    }
    monkeypatch.setattr(r12_demo, "autoform_window_snapshot", lambda **_kwargs: ready_snapshot)
    calls = []
    monkeypatch.setattr(r12_demo, "set_result_view", lambda view, **kwargs: calls.append((view, kwargs)))

    result = r12_demo.r12_project_view_demo(
        execute=True,
        wait_seconds=0,
        view_wait_seconds=0,
        verify_screenshot=False,
        output_dir=tmp_path,
    )

    assert result["status"] == "completed"
    assert result["view_sequence"] == []
    assert result["view_results"] == []
    assert calls == []
    assert [stage["stage"] for stage in result["stages"]] == ["open_project", "window_ready_check"]


def test_r12_project_view_demo_execute_opens_project_then_switches_views(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "Solver_R13.afd"
    monkeypatch.setattr(r12_demo, "resolve_project_input", lambda **_kwargs: _resolved_project(project))
    monkeypatch.setattr(
        r12_demo,
        "open_afd_observer",
        lambda path, dry_run=True: {
            "mode": "gui_project_observer",
            "dry_run": dry_run,
            "launched": not dry_run,
            "pid": 1234,
            "project_path": str(path),
        },
    )
    ready_snapshot = {
        "window_count": 1,
        "interaction_ready_window_count": 1,
        "interaction_ready_windows": [{"title": "AutoForm Forming R13 - Solver_R13.afd"}],
        "windows": [{"title": "AutoForm Forming R13 - Solver_R13.afd"}],
    }
    snapshot_filters = []

    def fake_autoform_window_snapshot(**kwargs):
        snapshot_filters.append((kwargs.get("title_contains"), kwargs.get("pid")))
        return ready_snapshot

    monkeypatch.setattr(r12_demo, "autoform_window_snapshot", fake_autoform_window_snapshot)
    calls = []

    def fake_set_result_view(view, **kwargs):
        calls.append((view, kwargs))
        return {
            "status": f"{view}_view_confirmed",
            "executed": True,
            "view_resolution": {"view": {"key": view}},
            "keystroke": {"sent": True},
        }

    monkeypatch.setattr(r12_demo, "set_result_view", fake_set_result_view)

    result = r12_demo.r12_project_view_demo(
        execute=True,
        wait_seconds=0,
        view_wait_seconds=0,
        verify_screenshot=False,
        view_sequence=["top", "isometric"],
        output_dir=tmp_path,
    )

    assert result["status"] == "completed"
    assert result["approval_required"] is False
    assert result["blocking_reasons"] == []
    assert [item[0] for item in calls] == ["top", "isometric"]
    assert calls[0][1]["execute"] is True
    assert calls[0][1]["verify_screenshot"] is False
    assert calls[0][1]["title_contains"] == "Solver_R13.afd"
    assert calls[1][1]["title_contains"] == "Solver_R13.afd"
    assert calls[0][1]["target_pid"] == 1234
    assert calls[1][1]["target_pid"] == 1234
    assert snapshot_filters == [("Solver_R13.afd", 1234), ("Solver_R13.afd", 1234)]
    assert [stage["stage"] for stage in result["stages"]] == [
        "open_project",
        "window_ready_check",
        "set_top_view",
        "set_isometric_view",
    ]


def test_r12_project_view_demo_accepts_single_view_sequence(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "Solver_R13.afd"
    monkeypatch.setattr(r12_demo, "resolve_project_input", lambda **_kwargs: _resolved_project(project))
    monkeypatch.setattr(
        r12_demo,
        "open_afd_observer",
        lambda path, dry_run=True: {
            "mode": "gui_project_observer",
            "dry_run": dry_run,
            "launched": not dry_run,
            "pid": 4321,
            "project_path": str(path),
        },
    )
    ready_snapshot = {
        "window_count": 1,
        "interaction_ready_window_count": 1,
        "interaction_ready_windows": [{"title": "AutoForm Forming R13 - Solver_R13.afd"}],
        "windows": [{"title": "AutoForm Forming R13 - Solver_R13.afd"}],
    }
    monkeypatch.setattr(r12_demo, "autoform_window_snapshot", lambda **_kwargs: ready_snapshot)
    calls = []

    def fake_set_result_view(view, **kwargs):
        calls.append((view, kwargs))
        return {"status": "view_change_confirmed", "executed": True}

    monkeypatch.setattr(r12_demo, "set_result_view", fake_set_result_view)

    result = r12_demo.r12_project_view_demo(
        execute=True,
        wait_seconds=0,
        view_wait_seconds=0,
        verify_screenshot=False,
        view_sequence=["top"],
        output_dir=tmp_path,
    )

    assert result["status"] == "completed"
    assert result["view_sequence"] == ["top"]
    assert [item[0] for item in calls] == ["top"]
    assert [stage["stage"] for stage in result["stages"]] == ["open_project", "window_ready_check", "set_top_view"]
