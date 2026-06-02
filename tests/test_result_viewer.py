"""这个测试文件检查V1.1 结果审阅、视角、动画和 readiness。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks V1.1 result review, views, animation, and readiness. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from PIL import Image, ImageDraw

import autoform_agent.result_viewer as result_viewer
from autoform_agent.result_viewer import (
    assess_result_review_readiness,
    build_result_review_plan,
    classify_autoform_dialogs,
    extract_operation_request,
    find_latest_result_project,
    open_result_project,
    play_forming_animation,
    result_gui_evidence,
    result_review_blockers,
    resolve_result_view,
    resolve_result_variable,
    route_result_task,
    select_result_variable,
    set_result_view,
    view_control_evidence_protocol,
)


def _ready_autoform_window(title: str = "AutoForm Forming R13 - AutoComp_R13.afd") -> dict:
    return {
        "handle": "0x1",
        "pid": 1234,
        "process_name": "AFFormingUI.exe",
        "title": title,
        "class_name": "Qt5QWindow",
        "visible": True,
        "interaction_ready": True,
        "rect": {"left": 0, "top": 0, "right": 200, "bottom": 100, "width": 200, "height": 100},
    }


def _ready_autoform_snapshot(title: str = "AutoForm Forming R13 - AutoComp_R13.afd") -> dict:
    window = _ready_autoform_window(title)
    return {
        "window_count": 1,
        "interaction_ready_window_count": 1,
        "interaction_ready_windows": [window],
        "windows": [window],
    }


def _capture_for(path: Path, *, window: dict | None = None) -> dict:
    return {
        "path": str(path),
        "focused_window": {"focused": True, "window": window or _ready_autoform_window()},
    }


def test_resolve_result_variable_maps_draw_in_synonyms() -> None:
    resolved = resolve_result_variable("进料量")

    assert resolved["matched"] is True
    assert resolved["variable"]["key"] == "draw_in"
    assert "DrawInPresenter" in resolved["variable"]["presenters"]


def test_route_result_task_maps_formability_sentence() -> None:
    routed = route_result_task("看一下有没有开裂和起皱")

    assert routed["matched"] is True
    assert routed["selected"]["route"]["key"] == "formability_check"
    keys = [item["key"] for item in routed["selected"]["variables"]]
    assert "formability" in keys
    assert "wrinkles" in keys


def test_find_latest_result_project_prefers_manifest_project(tmp_path: Path) -> None:
    run_dir = tmp_path / "output" / "project_runs" / "latest"
    run_dir.mkdir(parents=True)
    project = run_dir / "latest.afd"
    project.write_text("afd", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        '{"working_project": "' + str(project).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )

    result = find_latest_result_project(tmp_path)

    assert result["status"] == "found"
    assert result["selected"]["path"] == str(project.resolve())
    assert result["selected"]["source"] == "run_manifest"


def test_open_result_project_dry_run_uses_observer_and_evidence(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "demo.afd"
    project.write_text("afd", encoding="utf-8")

    def fake_open_afd_observer(path, dry_run=True):
        return {"project_path": str(path), "dry_run": dry_run, "launched": False, "command": ["AFFormingUI.exe", "-file", str(path)]}

    monkeypatch.setattr(result_viewer, "open_afd_observer", fake_open_afd_observer)

    result = open_result_project(project, execute=False, screenshot=True, output_dir=tmp_path / "evidence")

    assert result["status"] == "planned"
    assert result["executed"] is False
    assert result["gui_observation"]["dry_run"] is True
    assert result["evidence"]["status"] == "planned"


def test_select_result_variable_execute_reports_unverified_control_path(tmp_path: Path) -> None:
    result = select_result_variable("回弹", view="等轴测", execute=False, output_dir=tmp_path)

    assert result["status"] == "planned"
    assert result["variable_resolution"]["variable"]["key"] == "springback"
    assert result["view_resolution"]["view"]["key"] == "isometric"
    assert result["failure_reason"] is None


def test_set_result_view_unknown_returns_traceable_reason() -> None:
    result = set_result_view("未知视角", execute=False)

    assert result["status"] == "failed"
    assert result["failure_reason"] == "unknown_result_view"


def test_resolve_result_view_accepts_live_r13_menu_labels() -> None:
    assert resolve_result_view("+Z向视图")["view"]["key"] == "top"
    assert resolve_result_view("+X向视图")["view"]["key"] == "front"
    assert resolve_result_view("-Y向视图")["view"]["key"] == "side"
    assert resolve_result_view("等轴测视图")["view"]["key"] == "isometric"


def test_set_result_view_execute_uses_shortcut_profile(monkeypatch, tmp_path: Path) -> None:
    captures = []

    def fake_capture_result_evidence(**kwargs):
        evidence = {
            "status": "captured",
            "screenshot_path": str(tmp_path / f"{kwargs['context']['action']}.png"),
            "capture": {"path": str(tmp_path / f"{kwargs['context']['action']}.png")},
        }
        captures.append(kwargs["context"])
        return evidence

    monkeypatch.setattr(result_viewer, "capture_result_evidence", fake_capture_result_evidence)
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: {"window_count": 1, "interaction_ready_window_count": 1, "interaction_ready_windows": [{}]},
    )
    monkeypatch.setattr(
        result_viewer,
        "send_autoform_keystroke",
        lambda shortcut, **_kwargs: {"sent": True, "keys": [shortcut.lower()]},
    )
    monkeypatch.setattr(result_viewer.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        result_viewer,
        "_animation_visual_change_check",
        lambda _before, _after, _profile: {"status": "pass", "failure_reason": None},
    )

    result = set_result_view("+Z向视图", execute=True, output_dir=tmp_path)

    assert result["status"] == "view_change_confirmed"
    assert result["executed"] is True
    assert result["control_profile"]["shortcut"] == "Z"
    assert captures[0]["action"] == "set_result_view_before"
    assert captures[1]["action"] == "set_result_view_after"


def test_set_result_view_execute_blocks_without_interaction_ready_window(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: {"window_count": 1, "interaction_ready_window_count": 0, "windows": []},
    )

    result = set_result_view("+Z向视图", execute=True, output_dir=tmp_path)

    assert result["status"] == "blocked_no_interaction_ready_autoform_window"
    assert result["failure_reason"] == "no_interaction_ready_autoform_window"


def test_view_control_evidence_protocol_plans_manual_capture_sequence() -> None:
    result = view_control_evidence_protocol(phase="plan")

    assert result["status"] == "operator_assistance_required"
    assert result["user_assistance_required"] is True
    assert [item["key"] for item in result["target_views"]] == [
        "isometric",
        "top",
        "front",
        "side",
        "fit",
        "reset",
    ]
    assert result["capture_sequence"][0]["view"] == "isometric"
    assert "result-view-evidence --view isometric --phase before" in result["capture_sequence"][0]["before_command"]
    assert "view_control_evidence_records.jsonl" in result["record_path"]
    assert result["target_views"][1]["r13_control_label"] == "+Z向视图"
    assert "AutoForm R13 菜单名或控件名：等轴测视图" in result["capture_sequence"][0]["operator_instruction"]


def test_view_control_evidence_protocol_captures_and_compares_manual_pair(monkeypatch, tmp_path: Path) -> None:
    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    Image.new("RGB", (240, 160), "white").save(before_path)
    after_image = Image.new("RGB", (240, 160), "white")
    ImageDraw.Draw(after_image).rectangle((70, 50, 170, 120), fill="black")
    after_image.save(after_path)

    def fake_capture(**kwargs):
        phase = kwargs["context"]["phase"]
        path = before_path if phase == "before" else after_path
        return {
            "status": "captured",
            "created_at": f"2026-06-01T00:00:0{0 if phase == 'before' else 1}Z",
            "screenshot_path": str(path),
            "context": kwargs["context"],
            "capture": _capture_for(path),
        }

    monkeypatch.setattr(result_viewer, "capture_result_evidence", fake_capture)

    before = view_control_evidence_protocol(view="isometric", phase="before", execute=True, output_dir=tmp_path)
    after = view_control_evidence_protocol(view="isometric", phase="after", execute=True, output_dir=tmp_path)
    compared = view_control_evidence_protocol(view="isometric", phase="compare", output_dir=tmp_path)

    assert before["status"] == "captured"
    assert before["user_assistance_required"] is True
    assert after["status"] == "captured"
    assert compared["status"] == "view_change_confirmed"
    assert compared["visual_validation"]["status"] == "pass"
    assert (tmp_path / "view_control_evidence_records.jsonl").exists()


def test_play_forming_animation_plans_keyframe_capture() -> None:
    result = play_forming_animation(operation="D-20", execute=False, keyframe_count=3)

    assert result["status"] == "planned"
    assert result["failure_reason"] is None
    assert result["captures"][0]["status"] == "planned"
    assert (
        result["gui_evidence"]["summary"]["animation"]
        == "guarded_autocomp_r13_profile_confirmed_manual_fallback_ready"
    )
    assert result["control_profile"]["key"] == "autocomp_r13_bottom_strip"


def test_play_forming_animation_manual_profile_observes_user_playback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: _ready_autoform_snapshot("AutoForm Forming R13 - Solver_R13.afd"),
    )
    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    Image.new("RGB", (200, 100), "white").save(before_path)
    after_image = Image.new("RGB", (200, 100), "white")
    ImageDraw.Draw(after_image).rectangle((50, 25, 120, 70), fill="black")
    after_image.save(after_path)

    def fake_capture(**kwargs):
        phase = kwargs["context"]["phase"]
        path = before_path if phase == "before_manual_playback" else after_path
        return {
            "status": "captured",
            "context": kwargs["context"],
            "capture": _capture_for(path, window=_ready_autoform_window("AutoForm Forming R13 - Solver_R13.afd")),
        }

    monkeypatch.setattr(result_viewer, "capture_result_evidence", fake_capture)

    result = play_forming_animation(
        operation="D-20",
        action="observe",
        execute=True,
        duration_seconds=0,
        control_profile="manual_user_playback",
        output_dir=tmp_path,
    )

    assert result["status"] == "manual_playback_observed_with_result_view_change"
    assert result["manual_operator_required"] is True
    assert result["execution"]["backend"] == "manual_user_operated_autoform_with_mcp_screenshot_validation"
    assert result["execution"]["before_evidence"]["context"]["operator"] == "user"
    assert result["execution"]["visual_validation"]["status"] == "pass"


def test_play_forming_animation_manual_profile_blocks_without_interaction_ready_window(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: {
            "window_count": 1,
            "interaction_ready_window_count": 0,
            "interaction_ready_windows": [],
            "windows": [
                {
                    "title": "AutoForm Forming R13 - Solver_R13.afd",
                    "process_name": "AFFormingUI.exe",
                    "visible": True,
                    "interaction_ready": False,
                    "rect": {"left": -21334, "top": -21333, "right": -21176, "bottom": -21307, "width": 158, "height": 26},
                }
            ],
        },
    )

    result = play_forming_animation(
        operation="D-20",
        action="observe",
        execute=True,
        duration_seconds=0,
        control_profile="manual_user_playback",
        output_dir=tmp_path,
    )

    assert result["status"] == "blocked_for_gui_execution"
    assert result["failure_reason"] == "no_interaction_ready_autoform_window"
    assert result["executed"] is False


def test_play_forming_animation_execute_uses_guarded_mcp_click(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: _ready_autoform_snapshot("AutoForm Forming R13 - AutoComp_R13.afd"),
    )
    clicked = {}

    def fake_click(x, y, **kwargs):
        clicked["x"] = x
        clicked["y"] = y
        clicked["kwargs"] = kwargs
        return {"clicked": True, "screen_x": 662, "screen_y": 572}

    monkeypatch.setattr(result_viewer, "click_autoform_window", fake_click)
    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    Image.new("RGB", (200, 100), "white").save(before_path)
    after_image = Image.new("RGB", (200, 100), "white")
    ImageDraw.Draw(after_image).rectangle((50, 25, 120, 70), fill="black")
    after_image.save(after_path)

    def fake_capture(**kwargs):
        phase = kwargs["context"]["phase"]
        path = before_path if phase == "before_click" else after_path
        return {
            "status": "captured",
            "context": kwargs["context"],
            "capture": _capture_for(path, window=_ready_autoform_window("AutoForm Forming R13 - AutoComp_R13.afd")),
        }

    monkeypatch.setattr(result_viewer, "capture_result_evidence", fake_capture)

    result = play_forming_animation(operation="D-20 Drawing", execute=True, output_dir=tmp_path)

    assert result["status"] == "played_with_guarded_mcp_click_profile"
    assert result["executed"] is True
    assert result["execution"]["backend"] == "mcp_win32_gui_primitives"
    assert clicked["x"] == 0.815
    assert clicked["y"] == 0.92
    assert clicked["kwargs"]["restore_window"] is False
    assert result["execution"]["before_evidence"]["context"]["phase"] == "before_click"
    assert result["execution"]["after_evidence"]["context"]["phase"] == "after_click"
    assert result["execution"]["visual_validation"]["status"] == "pass"


def test_play_forming_animation_execute_reports_click_without_visual_change(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: _ready_autoform_snapshot("AutoForm Forming R13 - AutoComp_R13.afd"),
    )
    monkeypatch.setattr(
        result_viewer,
        "click_autoform_window",
        lambda *_args, **_kwargs: {"clicked": True, "screen_x": 662, "screen_y": 572},
    )

    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    Image.new("RGB", (200, 100), "white").save(before_path)
    Image.new("RGB", (200, 100), "white").save(after_path)

    def fake_capture(**kwargs):
        phase = kwargs["context"]["phase"]
        path = before_path if phase == "before_click" else after_path
        return {
            "status": "captured",
            "context": kwargs["context"],
            "capture": _capture_for(path, window=_ready_autoform_window("AutoForm Forming R13 - AutoComp_R13.afd")),
        }

    monkeypatch.setattr(result_viewer, "capture_result_evidence", fake_capture)

    result = play_forming_animation(operation="D-20 Drawing", execute=True, output_dir=tmp_path)

    assert result["status"] == "clicked_without_result_view_change_detected"
    assert result["executed"] is True
    assert result["failure_reason"] == "animation_visual_change_not_detected"
    assert result["execution"]["visual_validation"]["status"] == "fail"


def test_play_forming_animation_execute_rejects_window_geometry_change(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: _ready_autoform_snapshot("AutoForm Forming R13 - AutoComp_R13.afd"),
    )
    monkeypatch.setattr(
        result_viewer,
        "click_autoform_window",
        lambda *_args, **_kwargs: {"clicked": True, "screen_x": 662, "screen_y": 572},
    )

    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    Image.new("RGB", (260, 180), "white").save(before_path)
    after_image = Image.new("RGB", (260, 180), "white")
    ImageDraw.Draw(after_image).rectangle((80, 50, 180, 120), fill="black")
    after_image.save(after_path)
    after_window = _ready_autoform_window("AutoForm Forming R13 - AutoComp_R13.afd")
    after_window["rect"] = {"left": 40, "top": 30, "right": 240, "bottom": 130, "width": 200, "height": 100}

    def fake_capture(**kwargs):
        phase = kwargs["context"]["phase"]
        path = before_path if phase == "before_click" else after_path
        window = _ready_autoform_window("AutoForm Forming R13 - AutoComp_R13.afd") if phase == "before_click" else after_window
        return {
            "status": "captured",
            "context": kwargs["context"],
            "capture": _capture_for(path, window=window),
        }

    monkeypatch.setattr(result_viewer, "capture_result_evidence", fake_capture)

    result = play_forming_animation(operation="D-20 Drawing", execute=True, output_dir=tmp_path)

    assert result["status"] == "clicked_without_visual_validation"
    assert result["failure_reason"] == "animation_visual_validation_target_window_changed"
    assert result["execution"]["visual_validation"]["status"] == "inconclusive"


def test_play_forming_animation_execute_blocks_unmatched_window(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: {
            "window_count": 1,
            "interaction_ready_window_count": 1,
            "interaction_ready_windows": [_ready_autoform_window("AutoForm Forming R13 - Other.afd")],
            "windows": [_ready_autoform_window("AutoForm Forming R13 - Other.afd")],
        },
    )

    result = play_forming_animation(operation="D-20", execute=True, output_dir=tmp_path)

    assert result["status"] == "blocked_for_gui_execution"
    assert result["failure_reason"] == "animation_profile_window_title_not_matched"


def test_result_gui_evidence_reports_observed_animation_and_deferred_frame_reader() -> None:
    result = result_gui_evidence(scope="animation")
    keys = {record["key"] for record in result["records"]}

    assert result["status"] == "observed"
    assert "result_bottom_time_step_playback_controls" in keys
    assert "result_frame_count_reader" in keys
    assert result["summary"]["observed_count"] == 1
    assert result["summary"]["gap_count"] == 0
    assert result["summary"]["deferred_count"] == 1
    assert result["execution_profiles"][0]["key"] == "autocomp_r13_bottom_strip"


def test_classify_autoform_dialogs_detects_visible_blockers_and_hidden_candidates() -> None:
    hidden_welcome = _ready_autoform_window("欢迎使用 AutoForm Forming")
    hidden_welcome["visible"] = False
    hidden_welcome["interaction_ready"] = False
    license_dialog = _ready_autoform_window("AutoForm License Activation")
    license_dialog["class_name"] = "QDialog"
    warning_dialog = _ready_autoform_window("AutoForm Warning")
    warning_dialog["class_name"] = "Qt5QWindowPopupDropShadowSaveBits"
    snapshot = {
        "window_count": 3,
        "interaction_ready_window_count": 0,
        "interaction_ready_windows": [],
        "windows": [hidden_welcome, license_dialog, warning_dialog],
    }

    result = classify_autoform_dialogs(snapshot)
    keys = {item["key"] for item in result["dialogs"]}

    assert result["status"] == "blocking_dialogs_detected"
    assert result["dialog_count"] == 3
    assert result["visible_dialog_count"] == 2
    assert result["blocking_dialog_count"] == 2
    assert {"welcome_dialog", "license_dialog", "warning_dialog"} <= keys
    assert all(item["window"]["class_name"] for item in result["blocking_dialogs"])


def test_result_gui_evidence_dialog_scope_reports_classifier(monkeypatch) -> None:
    monkeypatch.setattr(result_viewer, "autoform_window_snapshot", lambda: {"window_count": 0, "windows": []})

    result = result_gui_evidence(scope="dialog")
    keys = {record["key"] for record in result["records"]}

    assert result["summary"]["dialog_detection"] == "title_class_classifier_ready"
    assert "title_class_dialog_classifier" in keys
    assert result["dialog_classifier"]["status"] == "no_dialog_candidates"


def test_result_review_blockers_report_user_assistance_requests() -> None:
    result = result_review_blockers()
    keys = {item["key"] for item in result["blockers"]}
    deferred_keys = {item["key"] for item in result["deferred_items"]}

    assert result["progress_estimate"]["overall_near_term_demo"] == 0.93
    assert result["progress_estimate"]["v1_1_core_status"] == "delivery_candidate_no_open_blockers"
    assert result["status_summary"]["blocker_count"] == 0
    assert result["status_summary"]["user_assistance_required"] is False
    assert result["status_summary"]["high_severity_count"] == 0
    assert "manual_playback_demo_capture_pending" not in keys
    assert "dialog_and_blocker_detection_pending" not in keys
    assert "view_shortcut_profiles_verified" not in keys
    assert result["user_assistance_requests"] == []
    assert "engineering_report_rules_optional" in deferred_keys
    assert "automatic_animation_play_or_scrub_locator" in deferred_keys


def test_result_review_blockers_include_completed_dialog_classifier() -> None:
    result = result_review_blockers(include_completed=True)
    dialog_item = next(item for item in result["blockers"] if item["key"] == "dialog_and_blocker_detection_pending")

    assert dialog_item["status"] == "completed"
    assert dialog_item["user_assistance_required"] is False


def test_extract_operation_request_detects_d_operation() -> None:
    result = extract_operation_request("切到 D-20 最终状态")

    assert result["matched"] is True
    assert result["kind"] == "operation"
    assert result["value"] == "D-20"


def test_build_result_review_plan_returns_route_evidence_and_recovery(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "latest"
    run_dir.mkdir(parents=True)
    project = run_dir / "latest.afd"
    project.write_text("afd", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        '{"working_project": "' + str(project).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )

    result = build_result_review_plan("看一下 D-20 有没有开裂和起皱，等轴测截图", search_dir=tmp_path)

    assert result["status"] == "planned"
    assert result["route"]["selected"]["route"]["key"] == "formability_check"
    assert result["operation_request"]["value"] == "D-20"
    assert result["view_resolution"]["view"]["key"] == "isometric"
    assert result["latest_project"]["status"] == "found"
    assert result["screenshot_caption_plan"]["automation_status"] == "planned_until_gui_execution"
    assert any(item["id"] == "control_path_unverified" for item in result["recovery_guides"])


def test_assess_result_review_readiness_blocks_without_window(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "latest"
    run_dir.mkdir(parents=True)
    project = run_dir / "latest.afd"
    project.write_text("afd", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        '{"working_project": "' + str(project).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(result_viewer, "autoform_window_snapshot", lambda: {"window_count": 0, "windows": []})

    result = assess_result_review_readiness("看一下有没有回弹", search_dir=tmp_path)

    assert result["status"] == "blocked_for_gui_execution"
    assert result["planning_status"] == "ready"
    assert "visible_autoform_window" in result["blocking_reasons"]
    assert result["latest_project"]["status"] == "found"


def test_assess_result_review_readiness_blocks_without_interaction_ready_window(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "latest"
    run_dir.mkdir(parents=True)
    project = run_dir / "latest.afd"
    project.write_text("afd", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        '{"working_project": "' + str(project).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: {
            "window_count": 1,
            "interaction_ready_window_count": 0,
            "interaction_ready_windows": [],
            "windows": [
                {
                    "title": "AutoForm Forming R13 - latest.afd",
                    "process_name": "AFFormingUI.exe",
                    "visible": True,
                    "interaction_ready": False,
                    "rect": {"left": -21334, "top": -21333, "right": -21176, "bottom": -21307, "width": 158, "height": 26},
                }
            ],
        },
    )

    result = assess_result_review_readiness("springback", search_dir=tmp_path)

    assert result["status"] == "blocked_for_gui_execution"
    assert "interaction_ready_autoform_window" in result["blocking_reasons"]
    assert result["checks"][2]["id"] == "visible_autoform_window"
    assert result["checks"][3]["id"] == "interaction_ready_autoform_window"


def test_assess_result_review_readiness_blocks_visible_dialog_candidate(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "latest"
    run_dir.mkdir(parents=True)
    project = run_dir / "latest.afd"
    project.write_text("afd", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        '{"working_project": "' + str(project).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    result_window = _ready_autoform_window("AutoForm Forming R13 - latest.afd")
    warning_dialog = _ready_autoform_window("AutoForm Warning")
    warning_dialog["handle"] = "0x2"
    warning_dialog["class_name"] = "QDialog"
    warning_dialog["interaction_ready"] = False
    monkeypatch.setattr(
        result_viewer,
        "autoform_window_snapshot",
        lambda: {
            "window_count": 2,
            "interaction_ready_window_count": 1,
            "interaction_ready_windows": [result_window],
            "windows": [result_window, warning_dialog],
        },
    )

    result = assess_result_review_readiness("springback", search_dir=tmp_path)

    assert result["status"] == "blocked_for_gui_execution"
    assert "autoform_dialog_blockers" in result["blocking_reasons"]
    assert result["dialog_evidence"]["blocking_dialog_count"] == 1
    assert result["dialog_evidence"]["blocking_dialogs"][0]["key"] == "warning_dialog"
