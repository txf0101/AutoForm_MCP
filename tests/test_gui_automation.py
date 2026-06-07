"""这个测试文件检查AutoForm 可见窗口、截图、恢复和 GUI 原语。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks visible AutoForm windows, screenshots, window restore, and GUI primitives. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

import autoform_mcp_agent.gui_automation as gui_automation


def test_top_level_windows_keeps_results_when_enumwindows_has_no_error(monkeypatch) -> None:
    def fake_enum_windows(callback, _lparam):
        callback(100, 0)
        return 0

    monkeypatch.setattr(gui_automation.user32, "EnumWindows", fake_enum_windows)
    monkeypatch.setattr(gui_automation.ctypes, "get_last_error", lambda: 0)
    monkeypatch.setattr(gui_automation, "_window_rect", lambda _hwnd: {"width": 10, "height": 20})
    monkeypatch.setattr(gui_automation, "_process_name", lambda _pid: "AFFormingUI.exe")
    monkeypatch.setattr(gui_automation, "_window_text", lambda _hwnd: "AutoForm Forming R13")
    monkeypatch.setattr(gui_automation, "_class_name", lambda _hwnd: "AutoForm")
    monkeypatch.setattr(gui_automation.user32, "GetWindowThreadProcessId", lambda _hwnd, pid: None)
    monkeypatch.setattr(gui_automation.user32, "IsWindowVisible", lambda _hwnd: True)

    windows = gui_automation._top_level_windows()

    assert windows[0]["title"] == "AutoForm Forming R13"
    assert windows[0]["area"] == 200


def test_computer_use_probe_reports_no_window_without_capture(monkeypatch) -> None:
    monkeypatch.setattr(gui_automation, "autoform_window_snapshot", lambda: {"window_count": 0, "windows": []})

    result = gui_automation.computer_use_probe(capture=False)

    assert result["status"] == "blocked_for_computer_use"
    assert "visible_autoform_window" in result["blocking_reasons"]
    assert result["screenshot"]["status"] == "skipped"


def test_best_autoform_window_rejects_small_offscreen_placeholder(monkeypatch) -> None:
    windows = [
        {
            "visible": True,
            "process_name": "AFFormingUI.exe",
            "title": "AutoForm Forming R13 - part.afd",
            "class_name": "Qt5QWindowIcon",
            "rect": {"left": -21333, "top": -21333, "width": 158, "height": 26},
            "area": 4108,
        },
        {
            "visible": True,
            "process_name": "AFFormingUI.exe",
            "title": "AutoForm Forming R13 - part.afd",
            "class_name": "Qt5QWindowIcon",
            "rect": {"left": -7, "top": -7, "width": 1721, "height": 1033},
            "area": 1777793,
        },
    ]
    monkeypatch.setattr(gui_automation, "_top_level_windows", lambda: windows)

    snapshot = gui_automation.autoform_window_snapshot()

    assert snapshot["window_count"] == 2
    assert snapshot["interaction_ready_window_count"] == 1
    assert gui_automation._best_autoform_window()["rect"]["width"] == 1721


def test_autoform_window_snapshot_can_filter_by_project_title(monkeypatch) -> None:
    windows = [
        {
            "visible": True,
            "process_name": "AFFormingUI.exe",
            "title": "AutoForm Forming R13 - AutoComp_R13.afd",
            "class_name": "Qt5QWindowIcon",
            "rect": {"left": 0, "top": 0, "width": 800, "height": 600},
            "area": 480000,
        },
        {
            "visible": True,
            "process_name": "AFFormingUI.exe",
            "title": "AutoForm Forming R13 - Solver_R13.afd",
            "class_name": "Qt5QWindowIcon",
            "rect": {"left": 0, "top": 0, "width": 700, "height": 600},
            "area": 420000,
        },
    ]
    monkeypatch.setattr(gui_automation, "_top_level_windows", lambda: windows)

    snapshot = gui_automation.autoform_window_snapshot(title_contains="Solver_R13.afd")

    assert snapshot["window_count"] == 1
    assert snapshot["interaction_ready_window_count"] == 1
    assert snapshot["windows"][0]["title"].endswith("Solver_R13.afd")


def test_restore_autoform_window_restores_offscreen_project_placeholder(monkeypatch) -> None:
    offscreen = {
        "handle": "0x9013a",
        "visible": True,
        "process_name": "AFFormingUI.exe",
        "title": "AutoForm Forming R13 - part.afd",
        "class_name": "Qt5QWindowIcon",
        "rect": {"left": -21333, "top": -21333, "width": 158, "height": 26},
        "area": 4108,
    }
    restored = {
        **offscreen,
        "rect": {"left": -7, "top": -7, "width": 1721, "height": 1033},
        "area": 1777793,
    }
    calls = []
    snapshots = iter([[offscreen], [restored]])
    monkeypatch.setattr(gui_automation, "_top_level_windows", lambda: next(snapshots))
    monkeypatch.setattr(gui_automation.user32, "ShowWindow", lambda hwnd, mode: calls.append(("show", hwnd, mode)) or True)
    monkeypatch.setattr(gui_automation.user32, "SetForegroundWindow", lambda hwnd: calls.append(("focus", hwnd)) or True)

    result = gui_automation.restore_autoform_window(wait_seconds=0)

    assert result["status"] == "restored_to_interaction_ready"
    assert result["restored"] is True
    assert result["before"]["interaction_ready_window_count"] == 0
    assert result["after"]["interaction_ready_window_count"] == 1
    assert calls == [
        ("show", int("0x9013a", 16), gui_automation.SW_RESTORE),
        ("focus", int("0x9013a", 16)),
    ]


def test_restore_autoform_window_returns_already_ready(monkeypatch) -> None:
    ready = {
        "handle": "0x9013a",
        "visible": True,
        "process_name": "AFFormingUI.exe",
        "title": "AutoForm Forming R13 - part.afd",
        "class_name": "Qt5QWindowIcon",
        "rect": {"left": -7, "top": -7, "width": 1721, "height": 1033},
        "area": 1777793,
    }
    monkeypatch.setattr(gui_automation, "_top_level_windows", lambda: [ready])

    result = gui_automation.restore_autoform_window(wait_seconds=0)

    assert result["status"] == "already_ready"
    assert result["restored"] is False
    assert result["after"]["interaction_ready_window_count"] == 1


def test_computer_use_probe_reports_screenshot_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        gui_automation,
        "autoform_window_snapshot",
        lambda: {
            "window_count": 1,
            "interaction_ready_window_count": 1,
            "interaction_ready_windows": [{"title": "AutoForm Forming R13"}],
            "windows": [{"title": "AutoForm Forming R13"}],
        },
    )

    def fail_capture(*_args, **_kwargs):
        raise OSError("The handle is invalid")

    monkeypatch.setattr(gui_automation, "capture_desktop_screenshot", fail_capture)

    result = gui_automation.computer_use_probe(tmp_path / "screen.png", capture=True)

    assert result["status"] == "blocked_for_computer_use"
    assert result["screenshot"]["status"] == "fail"
    assert result["screenshot"]["error_type"] == "OSError"
    assert "desktop_screenshot_capture" in result["blocking_reasons"]


def test_drag_autoform_window_uses_relative_window_coordinates(monkeypatch) -> None:
    window = {"rect": {"left": 10, "top": 20, "width": 200, "height": 100}, "title": "AutoForm Forming R13"}
    positions = []
    mouse_events = []

    monkeypatch.setattr(
        gui_automation,
        "focus_autoform_window",
        lambda restore_window=True: {"focused": True, "restore_window": restore_window, "window": window},
    )
    monkeypatch.setattr(gui_automation.user32, "SetCursorPos", lambda x, y: positions.append((x, y)) or True)
    monkeypatch.setattr(
        gui_automation.user32,
        "mouse_event",
        lambda event, _dx, _dy, _data, _extra: mouse_events.append(event),
    )

    result = gui_automation.drag_autoform_window(
        0.1,
        0.2,
        0.9,
        0.8,
        duration_seconds=0,
        steps=2,
        wait_seconds=0,
    )

    assert result["dragged"] is True
    assert result["start_screen_x"] == 30
    assert result["start_screen_y"] == 40
    assert result["end_screen_x"] == 190
    assert result["end_screen_y"] == 100
    assert positions[0] == (30, 40)
    assert positions[-1] == (190, 100)
    assert mouse_events == [gui_automation.MOUSEEVENTF_LEFTDOWN, gui_automation.MOUSEEVENTF_LEFTUP]


def test_send_autoform_keystroke_sends_modifier_sequence(monkeypatch) -> None:
    window = {"rect": {"left": 10, "top": 20, "width": 200, "height": 100}, "title": "AutoForm Forming R13"}
    key_events = []

    monkeypatch.setattr(
        gui_automation,
        "focus_autoform_window",
        lambda restore_window=False, title_contains=None, pid=None: {
            "focused": True,
            "restore_window": restore_window,
            "title_contains": title_contains,
            "pid": pid,
            "window": window,
        },
    )
    monkeypatch.setattr(
        gui_automation.user32,
        "keybd_event",
        lambda vk, _scan, flags, _extra: key_events.append((vk, flags)),
    )

    result = gui_automation.send_autoform_keystroke("Shift+Y", wait_seconds=0)

    assert result["sent"] is True
    assert result["keys"] == ["shift", "y"]
    assert key_events == [
        (gui_automation.VK_SHIFT, 0),
        (ord("Y"), 0),
        (ord("Y"), gui_automation.KEYEVENTF_KEYUP),
        (gui_automation.VK_SHIFT, gui_automation.KEYEVENTF_KEYUP),
    ]


def test_visible_window_control_demo_dry_run_only_plans(monkeypatch, tmp_path) -> None:
    ready_snapshot = {
        "window_count": 1,
        "interaction_ready_window_count": 1,
        "interaction_ready_windows": [{"title": "AutoForm Forming R13 - part.afd"}],
        "windows": [{"title": "AutoForm Forming R13 - part.afd"}],
    }
    monkeypatch.setattr(gui_automation, "autoform_window_snapshot", lambda: ready_snapshot)
    monkeypatch.setattr(
        gui_automation,
        "restore_autoform_window",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("dry run should not restore")),
    )

    result = gui_automation.visible_window_control_demo(tmp_path, execute=False, action="click")

    assert result["schema_version"] == "autoform.r12.visible_window_control_demo.v1"
    assert result["status"] == "planned_not_executed"
    assert result["approval_required"] is True
    assert result["stages"][-1] == {"stage": "click", "status": "planned_requires_execute"}


def test_visible_window_control_demo_executes_restore_focus(monkeypatch, tmp_path) -> None:
    ready_snapshot = {
        "window_count": 1,
        "interaction_ready_window_count": 1,
        "interaction_ready_windows": [{"title": "AutoForm Forming R13 - part.afd"}],
        "windows": [{"title": "AutoForm Forming R13 - part.afd"}],
    }
    monkeypatch.setattr(gui_automation, "autoform_window_snapshot", lambda: ready_snapshot)
    monkeypatch.setattr(
        gui_automation,
        "restore_autoform_window",
        lambda **_kwargs: {"status": "already_ready", "restored": False},
    )
    monkeypatch.setattr(
        gui_automation,
        "focus_autoform_window",
        lambda restore_window=False: {"focused": True, "restore_window": restore_window, "window": ready_snapshot["windows"][0]},
    )

    result = gui_automation.visible_window_control_demo(tmp_path, execute=True, action="restore_focus", wait_seconds=0)

    assert result["status"] == "restored_and_focused"
    assert result["approval_required"] is False
    assert [stage["stage"] for stage in result["stages"]] == ["restore_window", "focus_window"]


def test_visible_window_control_demo_reports_invalid_action(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gui_automation, "autoform_window_snapshot", lambda: {"window_count": 0, "windows": []})

    result = gui_automation.visible_window_control_demo(tmp_path, action="close_window")

    assert result["status"] == "invalid_action"
    assert result["blocking_reasons"] == ["invalid_action"]
