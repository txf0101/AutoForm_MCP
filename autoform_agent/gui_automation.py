"""这个文件保存 Windows 桌面 GUI 的低层工具。它可以枚举 AutoForm 窗口、恢复窗口、截图、点击、拖动和发送按键；每个动作都应留下窗口、坐标和结果证据。

This file contains low-level Windows desktop GUI helpers. It can list AutoForm windows, restore a window, take screenshots, click, drag, and send keys; each action should leave window, coordinate, and result evidence.
"""

from __future__ import annotations

import ctypes
from collections.abc import Sequence
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
import time

from PIL import ImageGrab


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_SHIFT = 0x10

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


def autoform_window_snapshot(title_contains: str | None = None, pid: int | None = None) -> dict:
    """Return visible top-level windows that belong to AutoForm Forming."""

    windows = _top_level_windows()
    autoform_windows = [item for item in windows if _looks_like_autoform_window(item)]
    autoform_windows = [item for item in autoform_windows if _target_matches(item, title_contains=title_contains, pid=pid)]
    for window in autoform_windows:
        window["interaction_ready"] = _is_interaction_ready_autoform_window(window)
    interaction_ready_windows = [item for item in autoform_windows if item["interaction_ready"]]
    return {
        "window_count": len(autoform_windows),
        "interaction_ready_window_count": len(interaction_ready_windows),
        "interaction_ready_windows": interaction_ready_windows,
        "windows": autoform_windows,
    }


def capture_desktop_screenshot(
    output_path: str | Path,
    *,
    focus_autoform: bool = True,
    wait_seconds: float = 0.5,
    restore_window: bool = False,
    title_contains: str | None = None,
    pid: int | None = None,
) -> dict:
    """Capture the current desktop so the Agent can inspect the visible UI."""

    focused = (
        focus_autoform_window(restore_window=restore_window, title_contains=title_contains, pid=pid)
        if focus_autoform
        else {"focused": False, "reason": "focus_autoform_false"}
    )
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = ImageGrab.grab()
    image.save(path)
    return {
        "path": str(path.resolve()),
        "size": image.size,
        "focused_window": focused,
    }


def focus_autoform_window(
    *,
    restore_window: bool = True,
    title_contains: str | None = None,
    pid: int | None = None,
) -> dict:
    """Restore and foreground the largest visible AutoForm window."""

    return _focus_autoform_window(restore_window=restore_window, title_contains=title_contains, pid=pid)


def restore_autoform_window(title_contains: str | None = None, *, wait_seconds: float = 0.5) -> dict:
    """Restore a visible AutoForm project window and report whether it is interaction-ready."""

    before = autoform_window_snapshot(title_contains=title_contains)
    if before.get("interaction_ready_window_count", 0) > 0:
        return {
            "status": "already_ready",
            "restored": False,
            "title_contains": title_contains,
            "before": before,
            "after": before,
            "restored_windows": [],
        }

    candidates = _restore_candidates(before, title_contains=title_contains)
    restored_windows = []
    for window in candidates:
        hwnd = int(window["handle"], 16)
        shown = bool(user32.ShowWindow(hwnd, SW_RESTORE))
        focused = bool(user32.SetForegroundWindow(hwnd))
        restored_windows.append(
            {
                "handle": window.get("handle"),
                "title": window.get("title"),
                "class_name": window.get("class_name"),
                "rect_before": window.get("rect"),
                "show_window_result": shown,
                "set_foreground_result": focused,
            }
        )
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    after = autoform_window_snapshot(title_contains=title_contains)
    if not candidates:
        status = "no_restore_candidate" if before.get("window_count", 0) else "no_autoform_window"
    elif after.get("interaction_ready_window_count", 0) > 0:
        status = "restored_to_interaction_ready"
    else:
        status = "restore_attempted_not_ready"
    return {
        "status": status,
        "restored": bool(restored_windows),
        "title_contains": title_contains,
        "before": before,
        "after": after,
        "restored_windows": restored_windows,
    }


def _focus_autoform_window(
    *,
    restore_window: bool,
    title_contains: str | None = None,
    pid: int | None = None,
) -> dict:
    """Foreground the largest visible AutoForm window, optionally restoring it first."""

    window = _best_autoform_window(title_contains=title_contains, pid=pid)
    if window is None:
        snapshot = autoform_window_snapshot(title_contains=title_contains, pid=pid)
        reason = "no_interaction_ready_autoform_window" if snapshot.get("window_count", 0) else "no_visible_autoform_window"
        return {"focused": False, "reason": reason, "title_contains": title_contains, "pid": pid, "window_snapshot": snapshot}
    hwnd = int(window["handle"], 16)
    if restore_window:
        user32.ShowWindow(hwnd, SW_RESTORE)
    focused = bool(user32.SetForegroundWindow(hwnd))
    return {"focused": focused, "restore_window": restore_window, "title_contains": title_contains, "pid": pid, "window": window}


def click_autoform_window(
    x: float,
    y: float,
    *,
    relative: bool = True,
    focus_first: bool = True,
    restore_window: bool = True,
    wait_seconds: float = 0.2,
) -> dict:
    """Click either a relative or absolute coordinate in the AutoForm window."""

    focused = (
        focus_autoform_window(restore_window=restore_window)
        if focus_first
        else {"focused": False, "reason": "focus_first_false"}
    )
    window = focused.get("window") or _best_autoform_window()
    if window is None:
        return {"clicked": False, "reason": "no_visible_autoform_window", "focused_window": focused}
    rect = window["rect"]
    if relative:
        screen_x = int(rect["left"] + rect["width"] * x)
        screen_y = int(rect["top"] + rect["height"] * y)
    else:
        screen_x = int(x)
        screen_y = int(y)
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    user32.SetCursorPos(screen_x, screen_y)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
    return {
        "clicked": True,
        "screen_x": screen_x,
        "screen_y": screen_y,
        "relative": relative,
        "window": window,
        "focused_window": focused,
        "restore_window": restore_window,
    }


def drag_autoform_window(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    *,
    relative: bool = True,
    focus_first: bool = True,
    restore_window: bool = True,
    duration_seconds: float = 0.4,
    steps: int = 12,
    wait_seconds: float = 0.2,
) -> dict:
    """Drag between two coordinates in the selected AutoForm window."""

    focused = (
        focus_autoform_window(restore_window=restore_window)
        if focus_first
        else {"focused": False, "reason": "focus_first_false"}
    )
    window = focused.get("window") or _best_autoform_window()
    if window is None:
        return {"dragged": False, "reason": "no_visible_autoform_window", "focused_window": focused}
    start_screen = _screen_point(window, start_x, start_y, relative=relative)
    end_screen = _screen_point(window, end_x, end_y, relative=relative)
    step_count = max(int(steps), 1)
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    user32.SetCursorPos(*start_screen)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
    for index in range(1, step_count + 1):
        fraction = index / step_count
        point_x = int(start_screen[0] + (end_screen[0] - start_screen[0]) * fraction)
        point_y = int(start_screen[1] + (end_screen[1] - start_screen[1]) * fraction)
        user32.SetCursorPos(point_x, point_y)
        if duration_seconds > 0:
            time.sleep(duration_seconds / step_count)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
    return {
        "dragged": True,
        "start_screen_x": start_screen[0],
        "start_screen_y": start_screen[1],
        "end_screen_x": end_screen[0],
        "end_screen_y": end_screen[1],
        "relative": relative,
        "steps": step_count,
        "duration_seconds": duration_seconds,
        "window": window,
        "focused_window": focused,
        "restore_window": restore_window,
    }


def send_autoform_keystroke(
    keys: str | Sequence[str],
    *,
    focus_first: bool = True,
    restore_window: bool = False,
    title_contains: str | None = None,
    pid: int | None = None,
    wait_seconds: float = 0.2,
) -> dict:
    """Send a small audited keystroke to the visible AutoForm window."""

    key_sequence = _normalize_keystroke(keys)
    if not key_sequence:
        return {"sent": False, "reason": "empty_keystroke"}
    unsupported = [key for key in key_sequence if _virtual_key(key) is None]
    if unsupported:
        return {"sent": False, "reason": "unsupported_key", "unsupported_keys": unsupported}
    focused = (
        focus_autoform_window(restore_window=restore_window, title_contains=title_contains, pid=pid)
        if focus_first
        else {"focused": False, "reason": "focus_first_false"}
    )
    window = focused.get("window") or _best_autoform_window(title_contains=title_contains, pid=pid)
    if window is None:
        return {"sent": False, "reason": "no_interaction_ready_autoform_window", "focused_window": focused}
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    modifiers = [key for key in key_sequence[:-1] if key in {"shift"}]
    primary_key = key_sequence[-1]
    for modifier in modifiers:
        _key_event(_virtual_key(modifier), key_up=False)
    _key_event(_virtual_key(primary_key), key_up=False)
    _key_event(_virtual_key(primary_key), key_up=True)
    for modifier in reversed(modifiers):
        _key_event(_virtual_key(modifier), key_up=True)
    return {
        "sent": True,
        "keys": key_sequence,
        "window": window,
        "focused_window": focused,
        "restore_window": restore_window,
        "title_contains": title_contains,
        "pid": pid,
    }


def computer_use_probe(
    output_path: str | Path = Path("tmp") / "computer_use_probe" / "desktop_probe.png",
    *,
    capture: bool = False,
    focus_autoform: bool = False,
    wait_seconds: float = 0.2,
) -> dict:
    """Probe whether this session can observe the desktop and AutoForm GUI."""

    window_snapshot = _safe_window_snapshot()
    screenshot = {
        "status": "skipped",
        "reason": "capture_false",
        "output_path": str(Path(output_path)),
    }
    if capture:
        try:
            captured = capture_desktop_screenshot(
                output_path,
                focus_autoform=focus_autoform,
                wait_seconds=wait_seconds,
            )
            screenshot = {"status": "pass", **captured}
        except Exception as exc:
            screenshot = {
                "status": "fail",
                "output_path": str(Path(output_path)),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

    checks = [
        {
            "id": "visible_autoform_window",
            "status": "pass" if window_snapshot.get("window_count", 0) > 0 else "fail",
            "severity": "blocker",
            "evidence": f"window_count={window_snapshot.get('window_count', 0)}",
        },
        {
            "id": "interaction_ready_autoform_window",
            "status": "pass" if window_snapshot.get("interaction_ready_window_count", 0) > 0 else "fail",
            "severity": "blocker",
            "evidence": f"interaction_ready_window_count={window_snapshot.get('interaction_ready_window_count', 0)}",
        },
        {
            "id": "desktop_screenshot_capture",
            "status": screenshot["status"],
            "severity": "blocker" if capture else "warning",
            "evidence": screenshot.get("path") or screenshot.get("error") or screenshot.get("reason"),
        },
    ]
    blockers = [item["id"] for item in checks if item["severity"] == "blocker" and item["status"] != "pass"]
    if blockers:
        status = "blocked_for_computer_use"
    elif capture:
        status = "ready_for_desktop_observation"
    else:
        status = "probe_ready_capture_not_requested"
    return {
        "schema_version": "1.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "window_snapshot": window_snapshot,
        "screenshot": screenshot,
        "checks": checks,
        "blocking_reasons": blockers,
        "recommended_next_actions": _computer_use_next_actions(blockers, capture),
        "evidence_boundary": (
            "This probe checks local desktop visibility and screenshot capability. "
            "It does not verify AutoForm result-variable, view, or animation controls."
        ),
    }


def visible_window_control_demo(
    output_dir: str | Path = Path("tmp") / "r12_visible_window_control_demo",
    *,
    execute: bool = False,
    action: str = "restore_focus",
    title_contains: str | None = None,
    keystroke: str | Sequence[str] | None = None,
    click_x: float = 0.5,
    click_y: float = 0.5,
    drag_start_x: float = 0.40,
    drag_start_y: float = 0.90,
    drag_end_x: float = 0.60,
    drag_end_y: float = 0.90,
    relative: bool = True,
    wait_seconds: float = 0.2,
) -> dict:
    """Run or plan the R12 basic visible-window control demo slice.

    The default call is a dry run.  Real desktop side effects stay behind
    ``execute=True`` and one explicit action value.
    """

    requested_action = (action or "restore_focus").strip().lower().replace("-", "_")
    aliases = {
        "probe": "restore_focus",
        "focus": "restore_focus",
        "restore": "restore_focus",
        "capture": "screenshot",
    }
    selected_action = aliases.get(requested_action, requested_action)
    valid_actions = {"restore_focus", "screenshot", "keystroke", "click", "drag"}
    output_root = Path(output_dir)
    before = _safe_window_snapshot()
    base = {
        "schema_version": "autoform.r12.visible_window_control_demo.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "r_stage": "R12",
        "demo_slice": "basic_visible_window_control",
        "execute": bool(execute),
        "requested_action": requested_action,
        "action": selected_action,
        "title_contains": title_contains,
        "output_dir": str(output_root),
        "source_basis": [
            {
                "path": "VC开发文档/Auto_Autoform思路整理/AutoForm多Agent系统整体任务规划矛盾检查与Vibecoding开发计划.docx",
                "fact": "R12 keeps AutoForm adapter actions reserved behind approval, dry-run and simulated-event boundaries.",
            },
            {
                "path": "docs/gui_result_review_scope.md",
                "fact": "Visible GUI primitives are used for explicit user-visible AutoForm result-review actions.",
            },
            {
                "path": "autoform_agent/gui_automation.py",
                "fact": "Win32 window snapshot, restore, focus, screenshot, click, drag and keystroke primitives share one implementation layer.",
            },
        ],
        "execution_boundary": {
            "target_process": "AFFormingUI.exe",
            "target_window": "visible AutoForm Forming top-level window",
            "requires_execute_for_desktop_side_effects": True,
            "allowed_actions": sorted(valid_actions),
        },
        "before": before,
        "stages": [],
    }
    if selected_action not in valid_actions:
        return {
            **base,
            "status": "invalid_action",
            "blocking_reasons": ["invalid_action"],
            "recommended_next_actions": [f"Use one of: {', '.join(sorted(valid_actions))}."],
        }

    if not execute:
        blockers = []
        if before.get("window_count", 0) == 0:
            blockers.append("visible_autoform_window")
        elif before.get("interaction_ready_window_count", 0) == 0:
            blockers.append("interaction_ready_autoform_window")
        return {
            **base,
            "status": "planned_not_executed" if not blockers else "blocked_for_visible_window_demo",
            "approval_required": True,
            "blocking_reasons": blockers,
            "stages": _planned_demo_stages(selected_action),
            "recommended_next_actions": _visible_window_demo_next_actions(blockers, execute=False),
        }

    stages: list[dict] = []
    blockers: list[str] = []
    restore_result = restore_autoform_window(title_contains=title_contains, wait_seconds=wait_seconds)
    stages.append({"stage": "restore_window", "status": restore_result.get("status"), "result": restore_result})

    focus_result = focus_autoform_window(restore_window=False)
    focus_status = "completed" if focus_result.get("focused") else "blocked"
    stages.append({"stage": "focus_window", "status": focus_status, "result": focus_result})

    after_focus = _safe_window_snapshot()
    if after_focus.get("window_count", 0) == 0:
        blockers.append("visible_autoform_window")
    elif after_focus.get("interaction_ready_window_count", 0) == 0:
        blockers.append("interaction_ready_autoform_window")

    action_result: dict | None = None
    if not blockers and selected_action == "screenshot":
        try:
            action_result = capture_desktop_screenshot(
                output_root / "r12_visible_window_control_demo.png",
                focus_autoform=True,
                restore_window=False,
                wait_seconds=wait_seconds,
            )
            stages.append({"stage": "screenshot", "status": "completed", "result": action_result})
        except Exception as exc:
            blockers.append("desktop_screenshot_capture")
            stages.append(
                {
                    "stage": "screenshot",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    elif not blockers and selected_action == "keystroke":
        action_result = send_autoform_keystroke(
            keystroke or "E",
            focus_first=True,
            restore_window=False,
            wait_seconds=wait_seconds,
        )
        stages.append(
            {
                "stage": "keystroke",
                "status": "completed" if action_result.get("sent") else "blocked",
                "result": action_result,
            }
        )
        if not action_result.get("sent"):
            blockers.append(str(action_result.get("reason") or "keystroke_not_sent"))
    elif not blockers and selected_action == "click":
        action_result = click_autoform_window(
            click_x,
            click_y,
            relative=relative,
            focus_first=True,
            restore_window=False,
            wait_seconds=wait_seconds,
        )
        stages.append(
            {
                "stage": "click",
                "status": "completed" if action_result.get("clicked") else "blocked",
                "result": action_result,
            }
        )
        if not action_result.get("clicked"):
            blockers.append(str(action_result.get("reason") or "click_not_sent"))
    elif not blockers and selected_action == "drag":
        action_result = drag_autoform_window(
            drag_start_x,
            drag_start_y,
            drag_end_x,
            drag_end_y,
            relative=relative,
            focus_first=True,
            restore_window=False,
            wait_seconds=wait_seconds,
        )
        stages.append(
            {
                "stage": "drag",
                "status": "completed" if action_result.get("dragged") else "blocked",
                "result": action_result,
            }
        )
        if not action_result.get("dragged"):
            blockers.append(str(action_result.get("reason") or "drag_not_sent"))

    after = _safe_window_snapshot()
    if blockers:
        status = "blocked_for_visible_window_demo"
    elif selected_action == "restore_focus":
        status = "restored_and_focused"
    else:
        status = f"{selected_action}_completed"
    return {
        **base,
        "status": status,
        "approval_required": False,
        "blocking_reasons": blockers,
        "after_focus": after_focus,
        "after": after,
        "stages": stages,
        "action_result": action_result,
        "recommended_next_actions": _visible_window_demo_next_actions(blockers, execute=True),
    }


# 下面这些内部函数给真实桌面动作加保护垫。
# 外层流程先通过这里拿到安全快照、规范按键名称和生成下一步建议，再进入 Windows API 动作。
# The internal helpers below add padding around real desktop actions.
# Outer workflows do not call Windows APIs blindly; they use these helpers to get safe snapshots, normalize key names, and build next-step guidance.
def _safe_window_snapshot() -> dict:
    try:
        return autoform_window_snapshot()
    except Exception as exc:
        return {
            "window_count": 0,
            "windows": [],
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _normalize_keystroke(keys: str | Sequence[str]) -> list[str]:
    if isinstance(keys, str):
        raw_items = keys.replace("+", " ").split()
    else:
        raw_items = [str(item) for item in keys]
    normalized = []
    for item in raw_items:
        key = item.strip().lower()
        if key in {"", "变换"}:
            continue
        if key in {"shift", "shiftkey"}:
            normalized.append("shift")
        elif len(key) == 1 and key.isascii() and key.isalnum():
            normalized.append(key)
        else:
            normalized.append(key)
    return normalized


def _virtual_key(key: str) -> int | None:
    if key == "shift":
        return VK_SHIFT
    if len(key) == 1 and key.isascii() and key.isalnum():
        return ord(key.upper())
    return None


def _key_event(vk_code: int | None, *, key_up: bool) -> None:
    if vk_code is None:
        return
    flags = KEYEVENTF_KEYUP if key_up else 0
    user32.keybd_event(vk_code, 0, flags, None)


def _computer_use_next_actions(blockers: list[str], capture: bool) -> list[str]:
    actions = []
    if "desktop_screenshot_capture" in blockers:
        actions.append("Run the probe from an interactive desktop session or grant screenshot execution approval.")
    if "visible_autoform_window" in blockers:
        actions.append("Open an AutoForm result project, then rerun computer-use-probe and result-readiness.")
    if "interaction_ready_autoform_window" in blockers:
        actions.append("Restore or maximize the target AutoForm result window on screen before shortcut, click, drag, or screenshot automation.")
    if not capture:
        actions.append("Rerun with capture=true or CLI --capture when desktop screenshot evidence is needed.")
    if not actions:
        actions.append("Use result-readiness before any result-variable, view, animation, or click action.")
    return actions


def _planned_demo_stages(action: str) -> list[dict]:
    stages = [
        {"stage": "snapshot", "status": "observed"},
        {"stage": "restore_window", "status": "planned_requires_execute"},
        {"stage": "focus_window", "status": "planned_requires_execute"},
    ]
    if action != "restore_focus":
        stages.append({"stage": action, "status": "planned_requires_execute"})
    return stages


def _visible_window_demo_next_actions(blockers: list[str], *, execute: bool) -> list[str]:
    actions: list[str] = []
    if "visible_autoform_window" in blockers:
        actions.append("Open an AutoForm Forming result window before running the R12 visible-window demo.")
    if "interaction_ready_autoform_window" in blockers:
        actions.append("Restore or maximize the AutoForm project window, then rerun the demo.")
    if "desktop_screenshot_capture" in blockers:
        actions.append("Run the screenshot stage from an interactive desktop session with screenshot access.")
    if not execute:
        actions.append("Add execute=true or CLI --execute only after confirming the target AutoForm window.")
    if not actions:
        actions.append("Use result-readiness before any result-variable, view or animation workflow.")
    return actions


def _top_level_windows() -> list[dict]:
    """Enumerate top-level Windows windows with process and rectangle facts."""

    results: list[dict] = []

    def collect(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rect = _window_rect(hwnd)
        results.append(
            {
                "handle": hex(hwnd),
                "pid": int(pid.value),
                "process_name": _process_name(pid.value),
                "title": _window_text(hwnd),
                "class_name": _class_name(hwnd),
                "visible": bool(user32.IsWindowVisible(hwnd)),
                "rect": rect,
                "area": rect["width"] * rect["height"],
            }
        )
        return True

    if not user32.EnumWindows(EnumWindowsProc(collect), 0):
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
    return results


def _best_autoform_window(title_contains: str | None = None, pid: int | None = None) -> dict | None:
    """Choose the largest visible AutoForm window as the interaction target."""

    candidates = [
        item
        for item in _top_level_windows()
        if item["visible"]
        and _looks_like_autoform_window(item)
        and _is_interaction_ready_autoform_window(item)
        and _target_matches(item, title_contains=title_contains, pid=pid)
    ]
    if not candidates:
        return None
    return max(candidates, key=_autoform_window_score)


def _restore_candidates(snapshot: dict, *, title_contains: str | None = None) -> list[dict]:
    """Select visible AutoForm windows that are plausible restore targets."""

    title_term = (title_contains or "").casefold().strip()
    candidates = []
    for window in snapshot.get("windows", []):
        if window.get("interaction_ready"):
            continue
        if not window.get("visible"):
            continue
        title = (window.get("title") or "").casefold()
        if title_term and title_term not in title:
            continue
        if not title_term and ".afd" not in title:
            continue
        candidates.append(window)
    candidates.sort(key=_autoform_window_score, reverse=True)
    return candidates[:1]


def _title_matches(window: dict, title_contains: str | None) -> bool:
    title_term = (title_contains or "").casefold().strip()
    if not title_term:
        return True
    return title_term in (window.get("title") or "").casefold()


def _target_matches(window: dict, *, title_contains: str | None = None, pid: int | None = None) -> bool:
    if pid is not None and int(window.get("pid") or -1) != int(pid):
        return False
    return _title_matches(window, title_contains)


def _is_interaction_ready_autoform_window(window: dict) -> bool:
    """Return whether a window is large enough for audited GUI actions."""

    rect = window.get("rect") or {}
    width = int(rect.get("width") or 0)
    height = int(rect.get("height") or 0)
    if not window.get("visible"):
        return False
    if width < 400 or height < 300:
        return False
    left = int(rect.get("left") or 0)
    top = int(rect.get("top") or 0)
    if left < -5000 or top < -5000:
        return False
    return True


def _autoform_window_score(window: dict) -> tuple[int, int, int]:
    """Prefer real project windows over startup or untitled AutoForm windows."""

    title = (window.get("title") or "").casefold()
    has_project_title = ".afd" in title
    is_untitled = "untitled" in title
    return (
        1 if has_project_title else 0,
        0 if is_untitled else 1,
        int(window.get("area") or 0),
    )


def _looks_like_autoform_window(window: dict) -> bool:
    """Return whether a window belongs to AutoForm Forming by stable facts."""

    process_name = (window.get("process_name") or "").casefold()
    title = (window.get("title") or "").casefold()
    class_name = (window.get("class_name") or "").casefold()
    if process_name == "afformingui.exe":
        return True
    if title.startswith("autoform forming"):
        return True
    return (
        "autoform" in class_name
        or "afforming" in class_name
    )


def _window_text(hwnd: wintypes.HWND) -> str:
    """Read a window title safely, preserving empty titles."""

    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_name(hwnd: wintypes.HWND) -> str:
    """Read the Win32 class name used by the top-level window."""

    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _window_rect(hwnd: wintypes.HWND) -> dict:
    """Read the screen rectangle and derived size for one window handle."""

    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return {"left": 0, "top": 0, "right": 0, "bottom": 0, "width": 0, "height": 0}
    return {
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
        "width": max(rect.right - rect.left, 0),
        "height": max(rect.bottom - rect.top, 0),
    }


def _screen_point(window: dict, x: float, y: float, *, relative: bool) -> tuple[int, int]:
    if not relative:
        return int(x), int(y)
    rect = window["rect"]
    return int(rect["left"] + rect["width"] * x), int(rect["top"] + rect["height"] * y)


def _process_name(pid: int) -> str | None:
    """Resolve a Windows process image name from a PID using kernel32 only."""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return Path(buffer.value).name
    finally:
        kernel32.CloseHandle(handle)
