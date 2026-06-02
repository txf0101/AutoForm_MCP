"""这个文件是 V1.1 GUI 后处理审阅的核心业务层。它把用户的自然语言请求映射到结果变量、视角、工序、截图证据、动画播放和 readiness 检查，并把未验证的 GUI 自动化保留为后续项。

This file is the core business layer for V1.1 GUI postprocessing review. It maps a user's plain request to result variables, views, operations, screenshot evidence, animation playback, and readiness checks while keeping unverified GUI automation as later work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Iterable

from PIL import Image, ImageChops, ImageStat

from .gui_automation import (
    autoform_window_snapshot,
    capture_desktop_screenshot,
    click_autoform_window,
    focus_autoform_window,
    send_autoform_keystroke,
)
from .process import open_afd_observer


DEFAULT_RESULT_REVIEW_OUTPUT_DIR = Path("tmp") / "result_review"
DEFAULT_VIEW_CONTROL_EVIDENCE_DIR = Path("tmp") / "result_review_view_controls"
VIEW_CONTROL_TARGET_ORDER = ("isometric", "top", "front", "side", "fit", "reset")
VIEW_CONTROL_VALIDATION = {
    "crop_fraction": (0.15, 0.12, 0.82, 0.70),
    "min_result_view_changed_pixel_ratio": 0.005,
    "min_result_view_mean_delta": 0.10,
}


ANIMATION_CONTROL_PROFILES: dict[str, dict] = {
    "autocomp_r13_bottom_strip": {
        "status": "guarded_profile_confirmed_for_autocomp_r13_20260602",
        "backend": "mcp_win32_gui_primitives",
        "evidence_record_key": "result_bottom_time_step_playback_controls",
        "title_terms": ("AutoComp_R13",),
        "operation_terms": ("D-20", "D-20 Drawing"),
        "supported_actions": ("play", "toggle", "start"),
        "default_click": {
            "label": "bottom time-step strip profiled control",
            "x": 0.815,
            "y": 0.92,
            "source": "tmp/autoform_animation_attempt/autoform_result_evidence_20260531_171641_174969.png",
        },
        "visual_validation": {
            "crop_fraction": (0.15, 0.12, 0.82, 0.70),
            "min_result_view_changed_pixel_ratio": 0.005,
            "min_result_view_mean_delta": 0.10,
            "source": "tmp/result_review_auto_play_v1_1_geometry_guard_probe before and after capture",
        },
        "evidence_boundary": (
            "This profile is limited to the locally observed AutoComp_R13 result window. "
            "It uses relative Win32 clicks exposed through MCP, captures before and after screenshots, "
            "and treats result-view pixel change as the playback confirmation. On 2026-06-02 "
            "the profile produced a confirmed result-view change after the window-geometry guard "
            "was added. Cross-project automatic playback remains a later UI-layout validation task."
        ),
    },
    "manual_user_playback": {
        "status": "manual_operator_observation_ready",
        "backend": "manual_user_operated_autoform_with_mcp_screenshot_validation",
        "manual_operator_required": True,
        "evidence_record_key": "manual_user_playback_observation_protocol",
        "title_terms": (),
        "operation_terms": (),
        "supported_actions": ("play", "observe", "manual_play", "manual_observe"),
        "visual_validation": {
            "crop_fraction": (0.15, 0.12, 0.82, 0.70),
            "min_result_view_changed_pixel_ratio": 0.005,
            "min_result_view_mean_delta": 0.10,
        },
        "operator_steps": (
            "Open the target result project in AutoForm Forming.",
            "Select the intended operation and result view in AutoForm.",
            "During the MCP observation window, manually press Play or scrub the time-step strip.",
            "Let MCP capture before and after screenshots and validate the result-view change.",
        ),
        "evidence_boundary": (
            "This profile does not click AutoForm controls. The user operates playback in the visible "
            "AutoForm window, while MCP captures before and after screenshots and confirms whether the "
            "central result-view crop changed."
        ),
    },
}


RECOVERY_GUIDES: tuple[dict, ...] = (
    {
        "id": "window_not_found",
        "condition": "No visible AutoForm result window is found.",
        "check": "Run autoform_gui_window_snapshot before any click or screenshot action.",
        "next_step": "Open the latest result project, then repeat the window snapshot.",
    },
    {
        "id": "project_not_loaded",
        "condition": "A window exists but the requested result project is not confirmed.",
        "check": "Compare the selected .afd path with the window title and the latest run_manifest.json.",
        "next_step": "Reopen the selected project with autoform_result_open_project and capture evidence.",
    },
    {
        "id": "dialog_blocks_view",
        "condition": "A license, warning, or modal dialog blocks the result area.",
        "check": "Capture a screenshot and record the dialog title before continuing.",
        "next_step": "Return the dialog evidence to the user and wait for explicit instruction.",
    },
    {
        "id": "control_path_unverified",
        "condition": "The requested result variable, view, or animation button has no verified R13 control path.",
        "check": "Return the semantic route, presenter evidence, and screenshot plan without clicking unknown controls.",
        "next_step": "Collect GUI screenshots and stable control coordinates before enabling automatic execution.",
    },
    {
        "id": "display_geometry_changed",
        "condition": "DPI, resolution, or monitor layout changes the relative click target.",
        "check": "Record window rectangle, monitor origin, and screenshot size with every evidence capture.",
        "next_step": "Use a fresh window snapshot and avoid replaying stale coordinates.",
    },
)


DIALOG_CLASSIFIERS: tuple[dict, ...] = (
    {
        "key": "license_dialog",
        "category": "license",
        "terms": ("license", "licence", "licensing", "activation", "许可证", "许可", "激活"),
        "confidence": "high",
        "blocks_result_view_when_visible": True,
        "next_action": "Capture the dialog title and ask the user before dismissing license or activation prompts.",
    },
    {
        "key": "warning_dialog",
        "category": "warning",
        "terms": ("warning", "error", "failed", "failure", "exception", "警告", "错误", "异常", "失败"),
        "confidence": "high",
        "blocks_result_view_when_visible": True,
        "next_action": "Capture the warning title and message area before any continuation click.",
    },
    {
        "key": "quicklink_dialog",
        "category": "quicklink",
        "terms": ("quicklink", "export script", "script selection", "导出脚本", "脚本选择"),
        "confidence": "medium",
        "blocks_result_view_when_visible": True,
        "next_action": "Record the QuickLink dialog title and wait for the intended export action.",
    },
    {
        "key": "welcome_dialog",
        "category": "welcome",
        "terms": ("welcome", "start center", "getting started", "欢迎", "开始中心"),
        "confidence": "medium",
        "blocks_result_view_when_visible": True,
        "next_action": "Open the selected result project if only the welcome window is present.",
    },
)

GENERIC_DIALOG_CLASS_TERMS = ("dialog", "popup", "dropshadow", "modal")


@dataclass(frozen=True)
class ResultVariableSpec:
    """One user-facing result variable family with its local evidence."""

    key: str
    label: str
    synonyms: tuple[str, ...]
    presenters: tuple[str, ...]
    task_categories: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    execution_status: str = "semantic_mapping_ready_coordinate_switching_deferred_to_v1_2"

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "synonyms": list(self.synonyms),
            "presenters": list(self.presenters),
            "task_categories": list(self.task_categories),
            "evidence_ids": list(self.evidence_ids),
            "execution_status": self.execution_status,
        }


@dataclass(frozen=True)
class ResultViewSpec:
    """One user-facing result view request."""

    key: str
    label: str
    synonyms: tuple[str, ...]
    target_behavior: str
    execution_status: str = "control_path_unverified"
    r13_control_label: str | None = None
    r13_shortcut: str | None = None
    evidence_status: str = "manual_evidence_pending"
    profile_note: str | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "synonyms": list(self.synonyms),
            "target_behavior": self.target_behavior,
            "execution_status": self.execution_status,
            "r13_control_label": self.r13_control_label,
            "r13_shortcut": self.r13_shortcut,
            "evidence_status": self.evidence_status,
            "profile_note": self.profile_note,
        }


@dataclass(frozen=True)
class ResultTaskRoute:
    """A P1 route from a loose user intent to result variables."""

    key: str
    label: str
    triggers: tuple[str, ...]
    variables: tuple[str, ...]
    default_view: str
    evidence_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "triggers": list(self.triggers),
            "variables": list(self.variables),
            "default_view": self.default_view,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class GuiEvidenceRecord:
    """One locally observed GUI fact or one explicit remaining gap."""

    key: str
    scopes: tuple[str, ...]
    status: str
    observed_on: str
    summary: str
    source_claims: tuple[str, ...]
    evidence_paths: tuple[str, ...]
    observed_controls: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()

    def as_dict(self, *, workspace: str | Path | None = None) -> dict:
        return {
            "key": self.key,
            "scopes": list(self.scopes),
            "status": self.status,
            "observed_on": self.observed_on,
            "summary": self.summary,
            "source_claims": list(self.source_claims),
            "evidence_paths": [_evidence_path_status(path, workspace=workspace) for path in self.evidence_paths],
            "observed_controls": list(self.observed_controls),
            "limitations": list(self.limitations),
            "next_actions": list(self.next_actions),
        }


GUI_EVIDENCE_RECORDS: tuple[GuiEvidenceRecord, ...] = (
    GuiEvidenceRecord(
        key="simulation_control_output_each_time_step",
        scopes=("simulation_control_output", "frame_density", "preprocessing"),
        status="locally_observed_and_applied",
        observed_on="2026-05-31",
        summary=(
            "A copied AutoComp_R13 project was opened at Simulation > Control > Output, "
            "the nominal output strategy was set to Each Time Step, Apply was used, and "
            "the project was saved before recalculation."
        ),
        source_claims=(
            "run_recap.md records the GUI path, Each Time Step setting, Apply, save, and recalculation.",
            "20260531_180914_real_sim_output_frames.md records helpLinks.cfg, F_Std_CtrPar, and "
            "Business_FormingStandard.dll evidence for the Output nominal option.",
        ),
        evidence_paths=(
            "output/project_runs/frame_rate_experiment/AutoComp_R13_every_time_step_20260531_185003/run_recap.md",
            "output/session_reviews/20260531_180914_real_sim_output_frames.md",
            r"D:\Program Files\AutoForm\AFplus\R13F\bin\F_Std_CtrPar",
            r"D:\Program Files\AutoForm\AFplus\R13F\bin\Business_FormingStandard.dll",
        ),
        observed_controls=(
            "Simulation > Control > Output",
            "Nominal output strategy",
            "Each Time Step / mei yi shi jian bu",
            "Apply",
            "Save",
        ),
        limitations=(
            "This output setting increases saved result states only when the solved model actually produces those states.",
            "Changing viewer playback speed alone does not create additional solver result frames.",
        ),
        next_actions=(
            "Expose a guarded execution path that can apply this setting on a copied project.",
            "Locate Custom Time Steps interval input if a smaller evidence package is required.",
        ),
    ),
    GuiEvidenceRecord(
        key="result_bottom_time_step_playback_controls",
        scopes=("animation", "postprocessing", "time_step_strip"),
        status="locally_observed_guarded_click_profile_confirmed_for_autocomp_r13",
        observed_on="2026-06-02",
        summary=(
            "The recalculated AutoComp_R13 final result opened in the evaluation view. "
            "The bottom time-step strip could play D-20 Drawing intermediate deformation "
            "and switch to the D-20 Springback end state. A guarded MCP click profile has "
            "now confirmed a result-view crop change on the local AutoComp_R13 window."
        ),
        source_claims=(
            "run_recap.md records successful four-iteration recalculation and bottom time-step playback behavior.",
            "Local screenshots in tmp/autoform_animation_attempt capture bottom playback controls from the result window.",
            "tmp/result_review_validation and tmp/result_review_validation_right_icon record live MCP click trials where the result-view crop did not change.",
            "tmp/result_review_drag_probe records a live MCP drag trial that did not change the result-view crop.",
            "tmp/result_review_auto_play_v1_1_geometry_guard_probe records the 2026-06-02 guarded click success after geometry-change false positives were blocked.",
        ),
        evidence_paths=(
            "output/project_runs/frame_rate_experiment/AutoComp_R13_every_time_step_20260531_185003/run_recap.md",
            "tmp/autoform_animation_attempt/bottom_controls_crop.png",
            "tmp/autoform_animation_attempt/bottom_play_controls_crop.png",
            "tmp/autoform_animation_attempt/bottom_strip_crop.png",
            "tmp/autoform_probe_after_high_frame.png",
            "tmp/result_review_validation/autoform_result_evidence_20260531_212323_601088.png",
            "tmp/result_review_validation/autoform_result_evidence_20260531_212327_757889.png",
            "tmp/result_review_validation_right_icon/autoform_result_evidence_20260531_212346_000976.png",
            "tmp/result_review_validation_right_icon/autoform_result_evidence_20260531_212349_879347.png",
            "tmp/result_review_drag_probe/before_drag.png",
            "tmp/result_review_drag_probe/after_drag.png",
            "tmp/result_review_auto_play_v1_1_geometry_guard_probe/autoform_result_evidence_20260602_160536_313451.png",
            "tmp/result_review_auto_play_v1_1_geometry_guard_probe/autoform_result_evidence_20260602_160540_465427.png",
        ),
        observed_controls=(
            "bottom time-step strip",
            "profiled control candidates on the bottom strip",
            "D-20 Drawing operation entry",
            "D-20 Springback operation entry",
        ),
        limitations=(
            "The guarded MCP click profile is confirmed only for the locally observed AutoComp_R13 window shape.",
            "Earlier live MCP click and drag trials on 2026-05-31 did not confirm result-view movement and remain useful as negative locator evidence.",
            "The exact visible frame count is deferred to V1.2 or later.",
        ),
        next_actions=(
            "Use autocomp_r13_bottom_strip for the local AutoComp_R13 V1.1 demonstration when the readiness checks pass.",
            "Use manual_user_playback as the fallback when the project or window layout does not match the confirmed profile.",
        ),
    ),
    GuiEvidenceRecord(
        key="result_frame_count_reader",
        scopes=("animation", "frame_count", "postprocessing"),
        status="deferred_to_v1_2_exact_frame_count_reader",
        observed_on="2026-05-31",
        summary=(
            "The project has an observed playback path. Exact frame-count reading is outside the "
            "V1.1 stable-demo scope and remains a V1.2 or later task."
        ),
        source_claims=(
            "20260531_180914_real_sim_output_frames.md lists result frame count reading as a follow-up requirement.",
            "run_recap.md confirms playback availability but does not report a numeric frame count.",
        ),
        evidence_paths=(
            "output/session_reviews/20260531_180914_real_sim_output_frames.md",
            "output/project_runs/frame_rate_experiment/AutoComp_R13_every_time_step_20260531_185003/run_recap.md",
        ),
        limitations=("No stable API, export, or log parser has been confirmed for exact result frame counts.",),
        next_actions=(
            "Inspect readable AFD fragments, result exports, and GUI logs for operation increment counts.",
            "Keep V1.1 animation evidence on screenshot observation and report frame count as unknown.",
        ),
    ),
    GuiEvidenceRecord(
        key="manual_user_playback_observation_protocol",
        scopes=("animation", "manual_demo", "postprocessing"),
        status="manual_observation_protocol_ready",
        observed_on="2026-05-31",
        summary=(
            "For fallback demonstrations, the user can operate playback directly in AutoForm while MCP captures "
            "before and after screenshots and validates the result-view crop."
        ),
        source_claims=(
            "result_viewer.py exposes the manual_user_playback animation profile without sending GUI clicks.",
            "The same visual validation used by the guarded click profile checks the central result-view crop.",
        ),
        evidence_paths=(
            "autoform_agent/result_viewer.py",
            "tests/test_result_viewer.py",
        ),
        observed_controls=("user-operated AutoForm playback control", "MCP before and after screenshot capture"),
        limitations=(
            "Playback itself is performed by the user, so this protocol confirms visible result change rather than control automation.",
            "The exact frame count remains unknown in V1.1.",
        ),
        next_actions=(
            "Use this protocol for the next V1.1 demo and save the before and after evidence package.",
            "Keep automatic locator promotion in the V1.2 UI-layout-sensitive work package.",
        ),
    ),
    GuiEvidenceRecord(
        key="title_class_dialog_classifier",
        scopes=("dialog", "blocker", "recovery", "readiness", "postprocessing"),
        status="locally_observed_logic_ready",
        observed_on="2026-06-02",
        summary=(
            "Result readiness can classify AutoForm license, warning, QuickLink, welcome, "
            "and generic popup candidates from window title and class evidence before GUI clicks."
        ),
        source_claims=(
            "gui_automation.autoform_window_snapshot returns AutoForm window title, class name, visibility, rectangle, and interaction readiness.",
            "result_viewer.py runs classify_autoform_dialogs inside assess_result_review_readiness.",
            "tests/test_result_viewer.py covers dialog classification and readiness blocking.",
        ),
        evidence_paths=(
            "autoform_agent/gui_automation.py",
            "autoform_agent/result_viewer.py",
            "tests/test_result_viewer.py",
        ),
        observed_controls=("AutoForm top-level window title", "Win32 class name", "window visibility", "window rectangle"),
        limitations=(
            "The classifier records title and class candidates; it does not read dialog body text.",
            "Visible warning, license, QuickLink, or generic popup candidates still need screenshot evidence before user action.",
        ),
        next_actions=(
            "Keep dialog evidence in result-readiness before GUI execution.",
            "Add body-text extraction later only after a stable OCR or accessibility source is confirmed.",
        ),
    ),
    GuiEvidenceRecord(
        key="result_view_toolbar_controls",
        scopes=("view", "postprocessing", "toolbar"),
        status="locally_observed_shortcut_profiles_verified_fit_deferred_to_v1_2",
        observed_on="2026-06-01",
        summary=(
            "Result view semantics are mapped. AutoForm R13 shortcut profiles are verified for "
            "isometric, top, front, and side views; fit-window toolbar automation and a direct "
            "reset button remain V1.2 or later work."
        ),
        source_claims=(
            "2026-06-01 live AutoComp_R13 validation confirmed result-set-view --execute for E, Z, X, and Shift+Y.",
            "docs/v1_1_gui_result_review_goals.md now keeps fit-window toolbar automation and direct reset discovery outside V1.1 stable-demo scope.",
        ),
        evidence_paths=(
            "docs/v1_1_gui_result_review_goals.md",
            "autoform_agent/result_viewer.py",
            "output/session_reviews/20260601_mcp_v1_1_view_control_live_evidence_recap.md",
        ),
        limitations=(
            "Toolbar-only fit-window automation is sensitive to ribbon layout and is deferred.",
            "The current reset surrogate is the verified isometric shortcut E.",
        ),
        next_actions=(
            "Use shortcut profiles for V1.1 view switching.",
            "Revisit toolbar fit-window and direct reset discovery in V1.2 with a controlled UI profile.",
        ),
    ),
    GuiEvidenceRecord(
        key="direct_parameter_write_for_output_density",
        scopes=("simulation_control_output", "automation", "rgen"),
        status="deferred_to_v1_2_direct_output_density_writer",
        observed_on="2026-05-31",
        summary=(
            "The GUI path for output density is locally observed. A direct RGen or "
            "parameter-write path is deferred until a copied-project round trip is proven."
        ),
        source_claims=(
            "20260531_180914_real_sim_output_frames.md records that direct step-length writing was not yet reliable.",
        ),
        evidence_paths=("output/session_reviews/20260531_180914_real_sim_output_frames.md",),
        limitations=("Use the GUI-observed path or return a plan until the direct writer is verified.",),
        next_actions=("Keep direct parameter writes behind dry-run planning and handle the writer in the V1.2 evidence package.",),
    ),
)


RESULT_VARIABLES: tuple[ResultVariableSpec, ...] = (
    ResultVariableSpec(
        key="formability",
        label="成形性",
        synonyms=("成形性", "成形极限", "fld", "flc", "开裂", "破裂", "失效", "缩颈", "裂"),
        presenters=("SplitsPresenter", "ResultVariablePropertiesPresenter"),
        task_categories=("formability_check",),
        evidence_ids=("S1", "S5", "S6", "S8"),
    ),
    ResultVariableSpec(
        key="wrinkles",
        label="起皱",
        synonyms=("起皱", "皱", "wrinkle", "wrinkles"),
        presenters=("SplitsPresenter",),
        task_categories=("formability_check",),
        evidence_ids=("S5", "S8"),
    ),
    ResultVariableSpec(
        key="thinning",
        label="减薄与厚度",
        synonyms=("减薄", "厚度", "最小厚度", "thinning", "thickness"),
        presenters=("ResultVariablePropertiesPresenter",),
        task_categories=("formability_check",),
        evidence_ids=("S1", "S5", "S6"),
    ),
    ResultVariableSpec(
        key="draw_in",
        label="流入量",
        synonyms=("流入量", "拉入量", "进料量", "draw-in", "draw in", "drawin", "进料"),
        presenters=("DrawInPresenter",),
        task_categories=("material_flow_check",),
        evidence_ids=("S1", "S5"),
    ),
    ResultVariableSpec(
        key="material_flow",
        label="材料流动",
        synonyms=("材料流动", "流动", "滑移线", "skid lines", "material flow", "走料"),
        presenters=("MaterialFlowSkidLinesPresenter",),
        task_categories=("material_flow_check",),
        evidence_ids=("S1", "S5"),
    ),
    ResultVariableSpec(
        key="springback",
        label="回弹",
        synonyms=("回弹", "形状偏差", "springback", "spring back", "尺寸偏差"),
        presenters=("EvalSpringbackPresenter", "EvalSpringbackOperationPresenter[m_resultsPage]"),
        task_categories=("springback_check",),
        evidence_ids=("S1", "S2", "S7"),
    ),
    ResultVariableSpec(
        key="surface_quality",
        label="表面质量",
        synonyms=("表面", "表面质量", "外板质量", "凹凸", "surface", "surface quality"),
        presenters=("SurfacePresenter",),
        task_categories=("surface_quality_check",),
        evidence_ids=("S1", "S3", "S4"),
    ),
    ResultVariableSpec(
        key="forces",
        label="工艺载荷",
        synonyms=("力", "总力", "工具力", "载荷", "吨位", "tool force", "total force", "forces"),
        presenters=("ProcessDataGeneralPresenter", "ProcessTotalForcesPresenter", "ProcessDataToolPresenter"),
        task_categories=("force_curve_check",),
        evidence_ids=("S1", "S5"),
    ),
    ResultVariableSpec(
        key="forming_animation",
        label="成形过程动画",
        synonyms=("动画", "播放", "冲压过程", "成形过程", "关键帧", "animation", "movie", "frame"),
        presenters=("SolverResultsPagePresenter", "PostProcessingPagePresenter"),
        task_categories=("forming_animation",),
        evidence_ids=("S2", "S3", "S9"),
        execution_status="evidence_discovery_required",
    ),
)


RESULT_VIEWS: tuple[ResultViewSpec, ...] = (
    ResultViewSpec(
        "isometric",
        "等轴测",
        ("等轴测", "等轴测视图", "三维", "3d", "isometric", "iso", "E"),
        "Switch to the 3D isometric result view.",
        execution_status="shortcut_profile_verified_20260601",
        r13_control_label="等轴测视图",
        r13_shortcut="E",
        evidence_status="stable_manual_pair_and_shortcut_profile_captured_20260601",
    ),
    ResultViewSpec(
        "top",
        "俯视",
        ("俯视", "上视", "+Z向视图", "+Z", "Z", "top"),
        "Switch to the top result view.",
        execution_status="shortcut_profile_verified_20260601",
        r13_control_label="+Z向视图",
        r13_shortcut="Z",
        evidence_status="stable_manual_pair_and_shortcut_profile_captured_20260601",
    ),
    ResultViewSpec(
        "front",
        "正视",
        ("正视", "前视", "+X向视图", "+X", "X", "front"),
        "Switch to the front result view.",
        execution_status="shortcut_profile_verified_20260601",
        r13_control_label="+X向视图",
        r13_shortcut="X",
        evidence_status="stable_manual_pair_and_shortcut_profile_captured_20260601",
    ),
    ResultViewSpec(
        "side",
        "侧视",
        ("侧视", "左视", "右视", "-Y向视图", "-Y", "Shift+Y", "变换+Y", "side", "left", "right"),
        "Switch to a side result view.",
        execution_status="shortcut_profile_verified_20260601",
        r13_control_label="-Y向视图",
        r13_shortcut="Shift+Y",
        evidence_status="stable_manual_pair_and_shortcut_profile_captured_20260601",
    ),
    ResultViewSpec(
        "fit",
        "适合窗口",
        ("局部放大", "适合窗口", "放大", "fit", "zoom"),
        "Fit the result model to the visible window.",
        execution_status="manual_toolbar_path_verified_automation_deferred_to_v1_2",
        r13_control_label="适合窗口",
        evidence_status="stable_manual_pair_captured_20260601",
    ),
    ResultViewSpec(
        "reset",
        "复位视角",
        ("复位", "重置视角", "reset"),
        "Reset result view orientation and zoom.",
        execution_status="manual_surrogate_path_verified_direct_reset_deferred_to_v1_2",
        r13_control_label="等轴测视图",
        r13_shortcut="E",
        evidence_status="stable_manual_surrogate_pair_captured_20260601",
        profile_note="Live AutoForm R13 inspection found no separate reset item; 等轴测视图 is the current reset surrogate.",
    ),
)


TASK_ROUTES: tuple[ResultTaskRoute, ...] = (
    ResultTaskRoute(
        key="formability_check",
        label="成形性检查",
        triggers=("成形性", "开裂", "破裂", "起皱", "减薄", "有没有裂", "有没有皱", "formability"),
        variables=("formability", "wrinkles", "thinning"),
        default_view="isometric",
        evidence_ids=("S1", "S5", "S6", "S8"),
    ),
    ResultTaskRoute(
        key="springback_check",
        label="回弹检查",
        triggers=("回弹", "形状偏差", "尺寸偏差", "springback"),
        variables=("springback",),
        default_view="isometric",
        evidence_ids=("S1", "S2", "S7"),
    ),
    ResultTaskRoute(
        key="surface_quality_check",
        label="表面质量检查",
        triggers=("表面", "外板", "凹凸", "surface"),
        variables=("surface_quality",),
        default_view="isometric",
        evidence_ids=("S1", "S3", "S4"),
    ),
    ResultTaskRoute(
        key="material_flow_check",
        label="材料流动检查",
        triggers=("流入量", "进料", "材料流动", "走料", "draw", "material flow"),
        variables=("draw_in", "material_flow"),
        default_view="isometric",
        evidence_ids=("S1", "S5"),
    ),
    ResultTaskRoute(
        key="force_curve_check",
        label="力曲线检查",
        triggers=("力", "载荷", "吨位", "tool force", "total force"),
        variables=("forces",),
        default_view="front",
        evidence_ids=("S1", "S5"),
    ),
    ResultTaskRoute(
        key="forming_animation",
        label="成形过程动画",
        triggers=("动画", "播放", "过程", "关键帧", "animation", "movie"),
        variables=("forming_animation",),
        default_view="isometric",
        evidence_ids=("S2", "S3", "S9"),
    ),
)


def result_review_capabilities(autoform_version: str | None = None) -> dict:
    """Return the current P0/P1 result-review capability contract."""

    gui_evidence = result_gui_evidence(scope="all")
    return {
        "schema_version": "1.1",
        "autoform_version": autoform_version,
        "p0": {
            "gui_primitives": ("window_snapshot", "focus", "screenshot", "click", "drag"),
            "result_open": "ready_with_explicit_execute",
            "result_variable_mapping": "ready",
            "view_mapping": "shortcut_profiles_verified_fit_and_direct_reset_deferred_to_v1_2",
            "animation": "guarded_autocomp_r13_profile_confirmed_manual_fallback_ready",
            "evidence_capture": "ready_with_explicit_execute",
        },
        "p1": {
            "synonym_dictionary": "ready",
            "task_routes": "ready",
            "review_plan": "ready",
            "readiness_diagnostic": "ready",
            "operation_or_frame_selection": "operation_selection_observed_exact_frame_reader_deferred_to_v1_2",
            "exception_recovery": "structured_recovery_guides_ready_title_class_dialog_classifier_ready",
        },
        "gui_evidence_summary": gui_evidence["summary"],
        "variables": [item.as_dict() for item in RESULT_VARIABLES],
        "views": [item.as_dict() for item in RESULT_VIEWS],
        "task_routes": [item.as_dict() for item in TASK_ROUTES],
        "recovery_guides": list(RECOVERY_GUIDES),
        "evidence_boundary": (
            "Variable and task mappings are grounded in the plan document evidence IDs. "
            "AutoForm R13 bottom animation playback controls now have local AutoComp_R13 evidence; "
            "V1.1 stable demos use verified view shortcuts plus the confirmed guarded AutoComp_R13 playback profile. "
            "Toolbar fit-window automation, direct reset discovery, exact frame-count reading, and generalized automatic click "
            "execution are V1.2 or later tasks because they depend on UI layout details."
        ),
    }


def result_review_blockers(scope: str = "v1_1", *, include_completed: bool = False) -> dict:
    """Return current V1.1 blockers, countermeasures, and user assistance needs."""

    blockers = [
        {
            "key": "view_shortcut_profiles_verified",
            "phase": "P0",
            "severity": "low",
            "status": "completed",
            "summary": "AutoForm R13 shortcut profiles are verified for isometric, top, front, and side result views.",
            "evidence": [
                "2026-06-01 live AutoComp_R13 validation confirmed result-set-view --execute for E, Z, X, and Shift+Y.",
                "RESULT_VIEWS marks isometric, top, front, and side as shortcut_profile_verified_20260601.",
                "output/session_reviews/20260601_mcp_v1_1_view_control_live_evidence_recap.md records the live evidence path.",
            ],
            "recommended_countermeasure": (
                "Use shortcut view profiles in the V1.1 demo. Keep toolbar fit-window automation and direct reset discovery in V1.2."
            ),
            "user_assistance_required": False,
            "requested_user_assistance": "",
            "next_tooling_step": "No V1.1 action needed unless a demo requires fit-window toolbar automation.",
        },
        {
            "key": "manual_playback_demo_capture_pending",
            "phase": "P0",
            "severity": "low",
            "status": "completed",
            "summary": "The animation demo capture is complete for the local AutoComp_R13 window through the guarded bottom-strip profile; manual playback remains a fallback.",
            "evidence": [
                "manual_user_playback captures before and after screenshots without sending AutoForm clicks.",
                "tests/test_result_viewer.py covers the manual playback observation success path.",
                "output/session_reviews/20260531_mcp_v1_1_manual_playback_observation_recap.md records why this profile is the V1.1 stable demo path.",
                "tmp/result_review_auto_play_v1_1_geometry_guard_probe records a 2026-06-02 guarded click with stable window geometry and result-view visual change.",
            ],
            "recommended_countermeasure": (
                "Use autocomp_r13_bottom_strip for the local AutoComp_R13 V1.1 demo after readiness passes; use manual_user_playback when the project or layout differs."
            ),
            "user_assistance_required": False,
            "requested_user_assistance": "",
            "next_tooling_step": "No P0 action remains for the local AutoComp_R13 demonstration.",
        },
        {
            "key": "dialog_and_blocker_detection_pending",
            "phase": "P1",
            "severity": "low",
            "status": "completed",
            "summary": "Readiness checks now classify AutoForm license, warning, QuickLink, welcome, and generic popup candidates from window title and class evidence.",
            "evidence": [
                "RECOVERY_GUIDES includes dialog_blocks_view with screenshot-first recovery.",
                "computer-use-probe can expose window and screenshot capability before GUI actions.",
                "classify_autoform_dialogs records dialog category, title, class name, visibility, rectangle, and blocking status.",
                "tests/test_result_viewer.py covers dialog classification and readiness blocking.",
            ],
            "recommended_countermeasure": (
                "Use result-readiness before GUI actions. If a visible blocking dialog is detected, capture screenshot evidence and ask the user before continuing."
            ),
            "user_assistance_required": False,
            "requested_user_assistance": "",
            "next_tooling_step": "No V1.1 software action remains unless a new dialog title appears in live rehearsal.",
        },
    ]
    if not include_completed:
        blockers = [item for item in blockers if item["status"] == "open"]

    user_assistance_items = [item for item in blockers if item["user_assistance_required"]]
    deferred_items = [
        {
            "key": "engineering_report_rules_optional",
            "phase": "V1.2+",
            "reason": "The user confirmed on 2026-06-02 that V1.1 does not need engineering pass/fail report generation.",
            "current_v1_1_handling": (
                "Keep the report-rule schema and template as optional future inputs; V1.1 returns evidence and review boundaries "
                "without engineering pass/fail conclusions."
            ),
        },
        {
            "key": "fit_window_toolbar_automation",
            "phase": "V1.2+",
            "reason": "Toolbar-only execution depends on ribbon layout and visible window geometry.",
            "current_v1_1_handling": "Use verified shortcut views and manual fit-window evidence only when needed.",
        },
        {
            "key": "direct_reset_button_discovery",
            "phase": "V1.2+",
            "reason": "Live R13 inspection did not reveal a separate reset item; current demo uses the verified isometric shortcut E as a reset surrogate.",
            "current_v1_1_handling": "Return the reset surrogate explicitly in view plans.",
        },
        {
            "key": "automatic_animation_play_or_scrub_locator",
            "phase": "V1.2+",
            "reason": "The local AutoComp_R13 bottom-strip profile is confirmed, while cross-project play and scrub locators still depend on UI layout.",
            "current_v1_1_handling": "Use the confirmed autocomp_r13_bottom_strip profile for the local demo and manual_user_playback as fallback.",
        },
        {
            "key": "coordinate_based_result_variable_switching",
            "phase": "V1.2+",
            "reason": "Result-column UI targets depend on the current left panel layout and selected operation.",
            "current_v1_1_handling": "Keep semantic mapping, result routes, and screenshot evidence plans in V1.1.",
        },
        {
            "key": "exact_frame_count_reader",
            "phase": "V1.2+",
            "reason": "No source-backed export, log, or API reader has been confirmed for numeric frame counts.",
            "current_v1_1_handling": "Report frame count as unknown and validate animation by result-view screenshot changes.",
        },
    ]
    return {
        "schema_version": "1.1",
        "scope": scope,
        "scope_decision": (
        "V1.1 is scoped to stable demonstration: shortcut-based view changes, semantic result-review planning, "
        "guarded local AutoComp_R13 animation playback, manual playback fallback, screenshot evidence, and readiness checks. "
            "Engineering pass/fail report generation is outside the current V1.1 scope. "
            "UI-layout-sensitive precise automation is deferred to V1.2 or later."
        ),
        "generated_at": _utc_now(),
        "progress_estimate": {
            "p0_demo_closure": 0.96,
            "p1_experience_layer": 0.88,
            "p2_report_layer": 0.45,
            "p2_report_scope": "optional_future_input_not_in_current_v1_1_scope",
            "overall_near_term_demo": 0.93,
            "overall_strict_no_touch_goal": 0.63,
            "strict_no_touch_goal_status": "deferred_to_v1_2_or_later",
            "v1_1_core_status": "delivery_candidate_no_open_blockers",
        },
        "status_summary": {
            "blocker_count": len(blockers),
            "high_severity_count": sum(1 for item in blockers if item["severity"] == "high"),
            "user_assistance_required": bool(user_assistance_items),
            "user_assistance_count": len(user_assistance_items),
            "deferred_item_count": len(deferred_items),
        },
        "blockers": blockers,
        "deferred_items": deferred_items,
        "recommended_sequence": [
            "Use verified result-set-view shortcuts for isometric, top, front, and side views.",
            "Use the confirmed autocomp_r13_bottom_strip profile for the local AutoComp_R13 playback demo when readiness passes.",
            "Keep result-variable work at semantic mapping and evidence-plan level for V1.1.",
            "Use result-readiness dialog evidence when unexpected AutoForm windows appear during demo rehearsal.",
            "Treat report-rule thresholds as optional future input because current V1.1 does not include engineering pass/fail reports.",
        ],
        "user_assistance_requests": [
            {
                "key": item["key"],
                "phase": item["phase"],
                "requested_user_assistance": item["requested_user_assistance"],
            }
            for item in user_assistance_items
        ],
        "evidence_policy": (
            "Each blocker is tied to current source files, test coverage, local screenshots, or recap records. "
            "Items without a confirmed source stay in recommended actions rather than completed capability."
        ),
    }


def result_gui_evidence(scope: str = "all", *, workspace: str | Path | None = None) -> dict:
    """Return local V1.1 GUI control evidence and remaining gaps."""

    normalized_scope = _normalize_text(scope or "all")
    matched_records = [
        record.as_dict(workspace=workspace)
        for record in GUI_EVIDENCE_RECORDS
        if _gui_record_matches_scope(record, normalized_scope)
    ]
    status_counts: dict[str, int] = {}
    for record in matched_records:
        status = record["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    gaps = [
        record
        for record in matched_records
        if record["status"].startswith("gap_") or "missing" in record["status"] or "pending" in record["status"]
    ]
    deferred = [record for record in matched_records if "deferred" in record["status"]]
    observed = [
        record
        for record in matched_records
        if _gui_status_is_observed(record["status"])
    ]
    dialog_classification = _dialog_classification_for_scope(normalized_scope)
    return {
        "schema_version": "1.1",
        "scope": scope,
        "generated_at": _utc_now(),
        "status": _gui_evidence_status(matched_records, gaps, observed),
        "summary": {
            "record_count": len(matched_records),
            "observed_count": len(observed),
            "gap_count": len(gaps),
            "deferred_count": len(deferred),
            "statuses": status_counts,
            "simulation_output": "each_time_step_observed_and_applied",
            "animation": "guarded_autocomp_r13_profile_confirmed_manual_fallback_ready",
            "view_controls": "shortcut_profiles_verified_fit_and_direct_reset_deferred_to_v1_2",
            "dialog_detection": "title_class_classifier_ready",
            "v1_1_scope": "stable_demo_shortcut_views_guarded_playback_manual_fallback_screenshot_evidence",
            "query_tool": "autoform_result_gui_evidence",
        },
        "records": matched_records,
        "dialog_classifier": dialog_classification,
        "execution_profiles": _animation_profiles_for_scope(normalized_scope),
        "gaps": [{"key": item["key"], "status": item["status"], "next_actions": item["next_actions"]} for item in gaps],
        "deferred_items": [
            {"key": item["key"], "status": item["status"], "next_actions": item["next_actions"]} for item in deferred
        ],
        "recommended_next_actions": _dedupe_texts(
            action for record in matched_records for action in record.get("next_actions", [])
        ),
        "evidence_policy": (
            "Each claim is backed by local recap, source, screenshot, or installed-file paths. "
            "Path existence is reported per evidence item so stale or moved files remain visible."
        ),
    }


def classify_autoform_dialogs(window_snapshot: dict | None = None) -> dict:
    """Classify visible AutoForm dialog candidates from title and class facts."""

    snapshot = window_snapshot if window_snapshot is not None else autoform_window_snapshot()
    dialogs = []
    for window in snapshot.get("windows", []):
        dialog = _classify_autoform_dialog_window(window)
        if dialog is not None:
            dialogs.append(dialog)
    blocking = [item for item in dialogs if item["blocks_result_view"]]
    visible = [item for item in dialogs if item["visible"]]
    if blocking:
        status = "blocking_dialogs_detected"
    elif dialogs:
        status = "dialog_candidates_detected"
    else:
        status = "no_dialog_candidates"
    return {
        "schema_version": "1.1",
        "status": status,
        "classifier": "title_class_window_classifier",
        "window_count": snapshot.get("window_count", 0),
        "dialog_count": len(dialogs),
        "visible_dialog_count": len(visible),
        "blocking_dialog_count": len(blocking),
        "dialogs": dialogs,
        "blocking_dialogs": blocking,
        "recommended_next_actions": _dialog_next_actions(dialogs, blocking),
        "evidence_policy": (
            "Dialog classification uses AutoForm window titles, Win32 class names, visibility, "
            "rectangles, and interaction readiness from autoform_gui_window_snapshot."
        ),
    }


def extract_operation_request(intent: str, operation: str | None = None) -> dict:
    """Extract operation, increment, or frame hints from a user request."""

    source = "explicit_parameter" if operation else "intent"
    text = str(operation or intent or "")
    normalized = _normalize_text(text)
    d_operation = re.search(r"\bD\s*[-_ ]\s*(\d+)\b", text, flags=re.IGNORECASE)
    if d_operation:
        value = f"D-{d_operation.group(1)}"
        return {
            "matched": True,
            "kind": "operation",
            "value": value,
            "source": source,
            "confidence": "high",
            "candidates": [value],
            "fallback": None,
        }

    op_match = re.search(r"\b(?:op|operation|工序|步号)\s*[-_:： ]?\s*(\d+)\b", text, flags=re.IGNORECASE)
    if op_match:
        value = op_match.group(1)
        return {
            "matched": True,
            "kind": "operation_number",
            "value": value,
            "source": source,
            "confidence": "medium",
            "candidates": [value, f"D-{value}"],
            "fallback": "Confirm the exact operation name from the AutoForm result tree.",
        }

    increment_match = re.search(r"\b(?:inc|increment|frame|帧|增量)\s*[-_:： ]?\s*(\d+)\b", text, flags=re.IGNORECASE)
    if increment_match:
        value = increment_match.group(1)
        return {
            "matched": True,
            "kind": "frame_or_increment",
            "value": value,
            "source": source,
            "confidence": "medium",
            "candidates": [value],
            "fallback": "Confirm frame numbering after the result window is visible.",
        }

    final_terms = ("最后", "最终", "末态", "成形结束", "last", "final", "end state")
    if any(term in normalized for term in final_terms):
        return {
            "matched": True,
            "kind": "final_state",
            "value": "final",
            "source": source,
            "confidence": "medium",
            "candidates": ["latest_finished_operation", "last_available_increment"],
            "fallback": "Read the visible operation list or solver stdout tail to confirm the final operation.",
        }

    return {
        "matched": False,
        "kind": None,
        "value": None,
        "source": source,
        "confidence": "none",
        "candidates": ["latest_finished_operation", "visible_operation_candidates"],
        "fallback": "Return operation candidates after the result project is opened.",
    }


def build_result_review_plan(
    intent: str,
    *,
    search_dir: str | Path | None = None,
    workspace: str | Path | None = None,
    operation: str | None = None,
    view: str | None = None,
) -> dict:
    """Build one P1 review plan from a user sentence."""

    route = route_result_task(intent)
    direct_variables = _variables_from_intent(intent)
    selected_variables = []
    if route["matched"]:
        selected_variables = route["selected"]["variables"]
    elif direct_variables:
        selected_variables = direct_variables

    operation_request = extract_operation_request(intent, operation=operation)
    view_resolution = resolve_result_view(view) if view else _view_from_intent_or_route(intent, route)
    latest_project = None
    if search_dir or workspace:
        latest_project = find_latest_result_project(search_dir=search_dir, workspace=workspace)

    planned_tools = ["autoform_result_query_capabilities"]
    if latest_project is not None:
        planned_tools.extend(["autoform_result_find_latest", "autoform_result_open_latest"])
    else:
        planned_tools.append("autoform_result_open_latest")
    for variable in selected_variables:
        planned_tools.append(f"autoform_result_show_variable:{variable['key']}")
    if view_resolution and view_resolution.get("matched"):
        planned_tools.append(f"autoform_result_set_view:{view_resolution['view']['key']}")
    if route["matched"] and route["selected"]["route"]["key"] == "forming_animation":
        planned_tools.append("autoform_result_play_forming_animation")
    planned_tools.append("autoform_result_capture_evidence")

    status = "planned" if selected_variables or route["matched"] else "needs_clarification"
    return {
        "schema_version": "1.1",
        "status": status,
        "intent": intent,
        "route": route,
        "direct_variables": direct_variables,
        "selected_variables": selected_variables,
        "operation_request": operation_request,
        "view_resolution": view_resolution,
        "latest_project": latest_project,
        "planned_tools": planned_tools,
        "evidence_checklist": _evidence_checklist(selected_variables, view_resolution, operation_request),
        "screenshot_caption_plan": _screenshot_caption_plan(selected_variables, view_resolution, operation_request),
        "recovery_guides": list(RECOVERY_GUIDES),
        "failure_reason": None if status == "planned" else "no_task_route_or_variable_matched",
        "execution_boundary": (
            "This is a review plan. Opening windows, clicking controls, and capturing real screenshots "
            "still require explicit execution and local GUI evidence."
        ),
    }


def assess_result_review_readiness(
    intent: str | None = None,
    *,
    search_dir: str | Path | None = None,
    workspace: str | Path | None = None,
    operation: str | None = None,
    view: str | None = None,
    require_window: bool = True,
    limit: int = 200,
) -> dict:
    """Assess whether the current machine is ready for visible result review."""

    latest_project = find_latest_result_project(search_dir=search_dir, workspace=workspace, limit=limit)
    window_snapshot = autoform_window_snapshot()
    review_plan = (
        build_result_review_plan(
            intent,
            search_dir=search_dir,
            workspace=workspace,
            operation=operation,
            view=view,
        )
        if intent
        else None
    )
    selected_project = latest_project.get("selected")
    matching_windows = _matching_project_windows(window_snapshot.get("windows", []), selected_project)
    dialog_evidence = classify_autoform_dialogs(window_snapshot)
    checks = _readiness_checks(
        latest_project=latest_project,
        window_snapshot=window_snapshot,
        matching_windows=matching_windows,
        dialog_evidence=dialog_evidence,
        review_plan=review_plan,
        require_window=require_window,
    )
    blocking = [item for item in checks if item["severity"] == "blocker" and item["status"] != "pass"]
    warnings = [item for item in checks if item["severity"] == "warning" and item["status"] != "pass"]
    return {
        "schema_version": "1.1",
        "status": "ready_for_gui_execution" if not blocking else "blocked_for_gui_execution",
        "planning_status": "ready" if latest_project["status"] == "found" else "blocked_no_project",
        "latest_project": latest_project,
        "window_snapshot": window_snapshot,
        "matching_windows": matching_windows,
        "dialog_evidence": dialog_evidence,
        "review_plan": review_plan,
        "checks": checks,
        "blocking_reasons": [item["id"] for item in blocking],
        "warnings": [item["id"] for item in warnings],
        "recommended_next_actions": _readiness_next_actions(checks, latest_project, window_snapshot),
        "recovery_guides": list(RECOVERY_GUIDES),
    }


def find_latest_result_project(
    search_dir: str | Path | None = None,
    *,
    workspace: str | Path | None = None,
    limit: int = 200,
) -> dict:
    """Find the newest candidate `.afd` result project in run outputs."""

    root = Path(search_dir or workspace or Path.cwd()).resolve()
    candidates = _candidate_projects_from_manifests(root, limit=limit)
    candidates.extend(_candidate_projects_from_scan(root, limit=limit))
    candidates = _dedupe_candidates(candidates)
    candidates.sort(key=lambda item: item["last_modified"], reverse=True)
    selected = candidates[0] if candidates else None
    return {
        "root": str(root),
        "candidate_count": len(candidates),
        "selected": selected,
        "candidates": candidates[:limit],
        "status": "found" if selected else "not_found",
        "failure_reason": None if selected else "no_afd_project_found_in_search_root",
    }


def open_latest_result_project(
    search_dir: str | Path | None = None,
    *,
    workspace: str | Path | None = None,
    execute: bool = False,
    wait_seconds: float = 1.0,
    screenshot: bool = True,
    output_dir: str | Path = DEFAULT_RESULT_REVIEW_OUTPUT_DIR,
) -> dict:
    """Open the newest `.afd` candidate or return a traceable failure."""

    latest = find_latest_result_project(search_dir=search_dir, workspace=workspace)
    selected = latest["selected"]
    if not selected:
        return {
            "status": "not_found",
            "latest_project": latest,
            "executed": False,
            "failure_reason": latest["failure_reason"],
            "next_step": "Run autoform_project_run or pass project_path to autoform_result_open_project.",
        }
    result = open_result_project(
        selected["path"],
        execute=execute,
        wait_seconds=wait_seconds,
        screenshot=screenshot,
        output_dir=output_dir,
    )
    result["latest_project"] = latest
    return result


def open_result_project(
    project_path: str | Path,
    *,
    execute: bool = False,
    wait_seconds: float = 1.0,
    screenshot: bool = True,
    output_dir: str | Path = DEFAULT_RESULT_REVIEW_OUTPUT_DIR,
) -> dict:
    """Plan or execute opening one AutoForm result project in the visible GUI."""

    path = Path(project_path).resolve()
    result = {
        "status": "planned",
        "executed": False,
        "project_path": str(path),
        "project_exists": path.exists(),
        "requested_at": _utc_now(),
        "wait_seconds": max(wait_seconds, 0),
    }
    if not path.exists():
        return {**result, "status": "failed", "failure_reason": "project_path_not_found"}

    observation = open_afd_observer(path, dry_run=not execute)
    result["gui_observation"] = observation
    result["executed"] = bool(execute and observation.get("launched"))
    result["status"] = "opened" if result["executed"] else "planned"

    if execute and wait_seconds > 0:
        time.sleep(wait_seconds)

    if screenshot:
        result["evidence"] = capture_result_evidence(
            project_path=path,
            output_dir=output_dir,
            execute=execute,
            context={"action": "open_result_project"},
        )
    return result


def resolve_result_variable(name: str) -> dict:
    """Resolve a user term to the closest result variable family."""

    normalized = _normalize_text(name)
    for spec in RESULT_VARIABLES:
        if normalized == _normalize_text(spec.key) or normalized == _normalize_text(spec.label):
            return {"matched": True, "match_type": "exact", "variable": spec.as_dict()}
    for spec in RESULT_VARIABLES:
        for synonym in spec.synonyms:
            if normalized == _normalize_text(synonym):
                return {"matched": True, "match_type": "synonym", "matched_synonym": synonym, "variable": spec.as_dict()}
    for spec in RESULT_VARIABLES:
        for synonym in spec.synonyms:
            if _normalize_text(synonym) in normalized or normalized in _normalize_text(synonym):
                return {"matched": True, "match_type": "partial", "matched_synonym": synonym, "variable": spec.as_dict()}
    return {
        "matched": False,
        "input": name,
        "failure_reason": "unknown_result_variable",
        "known_variables": [item.key for item in RESULT_VARIABLES],
    }


def resolve_result_view(name: str) -> dict:
    """Resolve a user view term to a supported view family."""

    normalized = _normalize_text(name)
    for spec in RESULT_VIEWS:
        if normalized == _normalize_text(spec.key) or normalized == _normalize_text(spec.label):
            return {"matched": True, "match_type": "exact", "view": spec.as_dict()}
    for spec in RESULT_VIEWS:
        for synonym in spec.synonyms:
            if normalized == _normalize_text(synonym):
                return {"matched": True, "match_type": "synonym", "matched_synonym": synonym, "view": spec.as_dict()}
    return {
        "matched": False,
        "input": name,
        "failure_reason": "unknown_result_view",
        "known_views": [item.key for item in RESULT_VIEWS],
    }


def route_result_task(intent: str) -> dict:
    """Map a loose user intent to a P1 result-review route."""

    normalized = _normalize_text(intent)
    matches: list[dict] = []
    for route in TASK_ROUTES:
        score = 0
        matched_triggers = []
        for trigger in route.triggers:
            if _normalize_text(trigger) in normalized:
                score += 1
                matched_triggers.append(trigger)
        if score:
            matches.append(
                {
                    "score": score,
                    "matched_triggers": matched_triggers,
                    "route": route.as_dict(),
                    "variables": [resolve_result_variable(key)["variable"] for key in route.variables],
                }
            )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "matched": bool(matches),
        "intent": intent,
        "selected": matches[0] if matches else None,
        "candidates": matches,
        "failure_reason": None if matches else "no_task_route_matched",
    }


def select_result_variable(
    result_name: str,
    *,
    operation: str | None = None,
    project_hint: str | None = "current",
    view: str | None = None,
    execute: bool = False,
    verify_screenshot: bool = True,
    output_dir: str | Path = DEFAULT_RESULT_REVIEW_OUTPUT_DIR,
) -> dict:
    """Prepare a variable switch and capture evidence when explicitly requested."""

    variable = resolve_result_variable(result_name)
    if not variable["matched"]:
        return {
            "status": "failed",
            "executed": False,
            "variable_resolution": variable,
            "failure_reason": variable["failure_reason"],
        }
    view_resolution = resolve_result_view(view) if view else None
    result = {
        "status": "planned" if not execute else "control_path_unverified",
        "executed": False,
        "project_hint": project_hint,
        "operation": operation,
        "variable_resolution": variable,
        "view_resolution": view_resolution,
        "planned_sequence": [
            "focus AutoForm Forming result window",
            f"open presenter route: {', '.join(variable['variable']['presenters'])}",
            "select requested operation or report candidates",
            "capture screenshot and operation log",
        ],
        "failure_reason": None if not execute else "result_variable_gui_control_path_unverified",
        "evidence_boundary": "Semantic mapping is ready; automatic GUI clicks require local R13 control-path evidence.",
    }
    if verify_screenshot:
        result["evidence"] = capture_result_evidence(
            output_dir=output_dir,
            execute=execute,
            context={
                "action": "select_result_variable",
                "variable": variable["variable"]["key"],
                "operation": operation,
                "view": view_resolution["view"]["key"] if view_resolution and view_resolution["matched"] else None,
            },
        )
    return result


def set_result_view(
    view: str,
    *,
    execute: bool = False,
    verify_screenshot: bool = True,
    output_dir: str | Path = DEFAULT_RESULT_REVIEW_OUTPUT_DIR,
    title_contains: str | None = None,
    target_pid: int | None = None,
) -> dict:
    """Prepare a view change and capture evidence when requested."""

    resolution = resolve_result_view(view)
    if not resolution["matched"]:
        return {
            "status": "failed",
            "executed": False,
            "view_resolution": resolution,
            "failure_reason": resolution["failure_reason"],
        }
    selected_view = resolution["view"]
    shortcut = selected_view.get("r13_shortcut")
    result = {
        "status": "planned" if not execute else "shortcut_profile_pending",
        "executed": False,
        "view_resolution": resolution,
        "planned_sequence": [
            "focus AutoForm Forming result window",
            selected_view["target_behavior"],
            "capture screenshot after view request",
        ],
        "control_profile": {
            "type": "keyboard_shortcut" if shortcut else "manual_or_toolbar",
            "shortcut": shortcut,
            "r13_control_label": selected_view.get("r13_control_label"),
            "profile_note": selected_view.get("profile_note"),
            "title_contains": title_contains,
            "target_pid": target_pid,
        },
        "failure_reason": None if not execute else None if shortcut else "result_view_shortcut_profile_missing",
        "evidence_boundary": (
            "View semantics and selected R13 shortcuts are ready. Toolbar-only paths still require button evidence."
        ),
    }
    if execute and shortcut:
        window_snapshot = (
            autoform_window_snapshot(title_contains=title_contains, pid=target_pid)
            if title_contains or target_pid is not None
            else autoform_window_snapshot()
        )
        result["window_snapshot"] = window_snapshot
        if window_snapshot.get("interaction_ready_window_count", 0) < 1:
            result["status"] = "blocked_no_interaction_ready_autoform_window"
            result["failure_reason"] = "no_interaction_ready_autoform_window"
            result["evidence_boundary"] = (
                "A usable AutoForm result window must be visible and large enough before shortcut automation runs."
            )
            return result
        before = None
        after = None
        if verify_screenshot:
            before = capture_result_evidence(
                view=selected_view["key"],
                output_dir=output_dir,
                execute=True,
                context={
                    "action": "set_result_view_before",
                    "view": selected_view["key"],
                    "shortcut": shortcut,
                    "title_contains": title_contains,
                    "target_pid": target_pid,
                },
                title_contains=title_contains,
                target_pid=target_pid,
            )
        keystroke = send_autoform_keystroke(
            shortcut,
            focus_first=True,
            restore_window=False,
            title_contains=title_contains,
            pid=target_pid,
        )
        result["executed"] = bool(keystroke.get("sent"))
        result["keystroke"] = keystroke
        if verify_screenshot:
            time.sleep(0.5)
            after = capture_result_evidence(
                view=selected_view["key"],
                output_dir=output_dir,
                execute=True,
                context={
                    "action": "set_result_view_after",
                    "view": selected_view["key"],
                    "shortcut": shortcut,
                    "title_contains": title_contains,
                    "target_pid": target_pid,
                },
                title_contains=title_contains,
                target_pid=target_pid,
            )
            result["evidence"] = {"before": before, "after": after}
            visual_validation = _animation_visual_change_check(before, after, {"visual_validation": VIEW_CONTROL_VALIDATION})
            result["visual_validation"] = visual_validation
            if result["executed"] and visual_validation["status"] == "pass":
                result["status"] = "view_change_confirmed"
                result["failure_reason"] = None
            elif result["executed"] and visual_validation["status"] == "fail":
                result["status"] = "shortcut_sent_without_view_change_detected"
                result["failure_reason"] = visual_validation["failure_reason"]
            else:
                result["status"] = "view_change_validation_inconclusive"
                result["failure_reason"] = visual_validation.get("failure_reason")
        elif result["executed"]:
            result["status"] = "shortcut_sent_without_visual_validation"
        else:
            result["status"] = "shortcut_send_failed"
            result["failure_reason"] = keystroke.get("reason", "shortcut_send_failed")
        return result
    if execute and not shortcut:
        result["status"] = "control_path_unverified"
    if verify_screenshot:
        result["evidence"] = capture_result_evidence(
            output_dir=output_dir,
            execute=execute,
            context={"action": "set_result_view", "view": selected_view["key"]},
        )
    return result


def view_control_evidence_protocol(
    *,
    view: str | None = None,
    phase: str = "plan",
    output_dir: str | Path = DEFAULT_VIEW_CONTROL_EVIDENCE_DIR,
    execute: bool = False,
) -> dict:
    """Prepare, capture, or compare manual evidence for AutoForm view controls."""

    output_root = Path(output_dir)
    phase_key = _normalize_text(phase or "plan")
    if phase_key in {"", "plan", "prepare"}:
        return _view_control_evidence_plan(output_root)

    if not view:
        return {
            "schema_version": "1.1",
            "status": "failed",
            "failure_reason": "view_required",
            "supported_phases": ["plan", "before", "after", "compare"],
            "target_views": _view_control_target_views(),
        }
    resolution = resolve_result_view(view)
    if not resolution["matched"]:
        return {
            "schema_version": "1.1",
            "status": "failed",
            "failure_reason": resolution["failure_reason"],
            "view_resolution": resolution,
            "target_views": _view_control_target_views(),
        }
    selected_view = resolution["view"]
    if phase_key in {"before", "pre", "capture before", "before capture"}:
        return _capture_view_control_phase(
            selected_view=selected_view,
            phase="before",
            output_dir=output_root,
            execute=execute,
        )
    if phase_key in {"after", "post", "capture after", "after capture"}:
        return _capture_view_control_phase(
            selected_view=selected_view,
            phase="after",
            output_dir=output_root,
            execute=execute,
        )
    if phase_key in {"compare", "validate", "check"}:
        return _compare_view_control_evidence(selected_view=selected_view, output_dir=output_root)
    return {
        "schema_version": "1.1",
        "status": "failed",
        "failure_reason": "unknown_view_evidence_phase",
        "phase": phase,
        "supported_phases": ["plan", "before", "after", "compare"],
    }


def play_forming_animation(
    *,
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
    output_dir: str | Path = DEFAULT_RESULT_REVIEW_OUTPUT_DIR,
) -> dict:
    """Prepare or evidence an animation request with explicit capability limits."""

    profile = _animation_control_profile(control_profile)
    result = {
        "status": "planned",
        "executed": False,
        "operation": operation,
        "action": action,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "speed": speed,
        "duration_seconds": duration_seconds,
        "capture_mode": capture_mode,
        "keyframe_count": keyframe_count,
        "control_profile": profile,
        "execution_backend": profile.get("backend") if profile else "unknown_profile",
        "manual_operator_required": bool(profile and profile.get("manual_operator_required")),
        "planned_sequence": [
            "focus AutoForm Forming result window",
            "select forming process or solver-result view",
            "use the locally observed bottom time-step playback strip when the project matches the evidence scope",
            "capture start, middle, and end evidence",
        ],
        "failure_reason": None if not execute else None,
        "evidence_boundary": (
            "AutoForm R13 bottom playback controls were observed on AutoComp_R13 D-20 Drawing and "
            "D-20 Springback. This function can use a guarded MCP Win32 click profile for that "
            "observed path. Exact frame-count reading and generalized cross-project execution still need "
            "additional local proof."
        ),
        "gui_evidence": result_gui_evidence(scope="animation"),
    }
    if profile and profile.get("manual_operator_required"):
        result["planned_sequence"] = list(profile.get("operator_steps", ()))
        result["manual_operator_steps"] = list(profile.get("operator_steps", ()))
        result["evidence_boundary"] = profile["evidence_boundary"]
    if execute:
        if profile and profile.get("manual_operator_required"):
            execution = _execute_manual_animation_observation(
                operation=operation,
                action=action,
                duration_seconds=duration_seconds,
                control_profile=control_profile,
                output_dir=output_dir,
            )
        else:
            execution = _execute_animation_control_profile(
                operation=operation,
                action=action,
                duration_seconds=duration_seconds,
                control_profile=control_profile,
                click_x=click_x,
                click_y=click_y,
                output_dir=output_dir,
            )
        result["execution"] = execution
        result["status"] = execution["status"]
        result["executed"] = execution["executed"]
        result["failure_reason"] = execution.get("failure_reason")
        return result

    if capture_mode in {"screenshot", "screenshots", "keyframes"}:
        captures = []
        count = 1
        for index in range(count):
            captures.append(
                capture_result_evidence(
                    output_dir=output_dir,
                    execute=False,
                    context={"action": "play_forming_animation", "capture_index": index, "operation": operation},
                )
            )
        result["captures"] = captures
    return result


def capture_result_evidence(
    *,
    project_path: str | Path | None = None,
    variable: str | None = None,
    view: str | None = None,
    operation: str | None = None,
    output_dir: str | Path = DEFAULT_RESULT_REVIEW_OUTPUT_DIR,
    execute: bool = False,
    context: dict | None = None,
    title_contains: str | None = None,
    target_pid: int | None = None,
) -> dict:
    """Return a screenshot plan or capture a desktop screenshot as evidence."""

    output_root = Path(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    screenshot_path = output_root / f"autoform_result_evidence_{timestamp}.png"
    evidence = {
        "schema_version": "1.1",
        "created_at": _utc_now(),
        "project_path": str(Path(project_path).resolve()) if project_path else None,
        "variable": variable,
        "view": view,
        "operation": operation,
        "context": context or {},
        "title_contains": title_contains,
        "target_pid": target_pid,
        "execute": execute,
        "screenshot_path": str(screenshot_path),
        "window_snapshot": None,
        "capture": None,
        "caption_plan": _screenshot_caption_plan(
            [resolve_result_variable(variable)["variable"]] if variable and resolve_result_variable(variable).get("matched") else [],
            resolve_result_view(view) if view else None,
            extract_operation_request(operation or ""),
        ),
    }
    if not execute:
        evidence["status"] = "planned"
        return evidence
    evidence["window_snapshot"] = (
        autoform_window_snapshot(title_contains=title_contains, pid=target_pid)
        if title_contains or target_pid is not None
        else autoform_window_snapshot()
    )
    capture_kwargs = {"focus_autoform": True}
    if title_contains:
        capture_kwargs["title_contains"] = title_contains
    if target_pid is not None:
        capture_kwargs["pid"] = target_pid
    evidence["capture"] = capture_desktop_screenshot(screenshot_path, **capture_kwargs)
    evidence["status"] = "captured"
    return evidence


def focus_result_window() -> dict:
    """Focus the best visible AutoForm Forming window."""

    return focus_autoform_window()


# 下面这一组函数只负责寻找“哪个结果工程最可能是用户要看的工程”。
# 它们会先看运行清单，再扫工作区里的 .afd 文件，最后去重和过滤临时文件。
# The helpers below only decide which result project is most likely the one the user wants.
# They check run manifests first, then scan workspace .afd files, then deduplicate and filter temporary files.
def _candidate_projects_from_manifests(root: Path, *, limit: int) -> list[dict]:
    manifests = sorted(root.rglob("run_manifest.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    candidates: list[dict] = []
    for manifest in manifests[:limit]:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("working_project", "project_path", "source_project"):
            value = data.get(key)
            if not value:
                continue
            path = Path(value)
            if path.exists() and path.suffix.casefold() == ".afd":
                candidates.append(_candidate_from_path(path, source="run_manifest", manifest=manifest))
                break
    return candidates


def _candidate_projects_from_scan(root: Path, *, limit: int) -> list[dict]:
    if not root.exists():
        return []
    candidates = []
    for path in root.rglob("*.afd"):
        if _is_excluded_candidate_path(path, root):
            continue
        candidates.append(_candidate_from_path(path, source="workspace_scan"))
    candidates.sort(key=lambda item: item["last_modified"], reverse=True)
    return candidates[:limit]


def _candidate_from_path(path: Path, *, source: str, manifest: Path | None = None) -> dict:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "source": source,
        "manifest": str(manifest.resolve()) if manifest else None,
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
    }


def _dedupe_candidates(candidates: Iterable[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for candidate in candidates:
        key = candidate["path"].casefold()
        existing = deduped.get(key)
        if existing is None or candidate["last_modified"] > existing["last_modified"]:
            deduped[key] = candidate
    return list(deduped.values())


def _is_excluded_candidate_path(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    if not parts:
        return False
    if parts[0] in {".git", ".pytest_cache", "__pycache__", "tmp"}:
        return True
    return len(parts) > 1 and parts[0] == "output" and parts[1] in {"release", "result_package"}


def _variables_from_intent(intent: str) -> list[dict]:
    normalized = _normalize_text(intent)
    variables = []
    seen = set()
    for spec in RESULT_VARIABLES:
        terms = (spec.key, spec.label, *spec.synonyms)
        if any(_normalize_text(term) in normalized for term in terms):
            if spec.key not in seen:
                variables.append(spec.as_dict())
                seen.add(spec.key)
    return variables


def _view_from_intent_or_route(intent: str, route: dict) -> dict | None:
    for spec in RESULT_VIEWS:
        terms = (spec.key, spec.label, *spec.synonyms)
        if any(_normalize_text(term) in _normalize_text(intent) for term in terms):
            return {"matched": True, "match_type": "intent", "view": spec.as_dict()}
    if route["matched"]:
        return resolve_result_view(route["selected"]["route"]["default_view"])
    return None


def _evidence_checklist(variables: list[dict], view_resolution: dict | None, operation_request: dict) -> list[dict]:
    checklist = [
        {
            "id": "project",
            "item": "Confirm selected .afd result project and run_manifest.json.",
            "source": "result-find-latest or explicit project path",
            "status": "required",
        },
        {
            "id": "window",
            "item": "Confirm visible AutoForm Forming window title, rectangle, and process id.",
            "source": "autoform_gui_window_snapshot",
            "status": "required_for_gui_execution",
        },
    ]
    for variable in variables:
        checklist.append(
            {
                "id": f"variable:{variable['key']}",
                "item": f"Show result variable {variable['label']}.",
                "source": ", ".join(variable["presenters"]),
                "status": variable["execution_status"],
            }
        )
    if view_resolution and view_resolution.get("matched"):
        checklist.append(
            {
                "id": f"view:{view_resolution['view']['key']}",
                "item": f"Set view to {view_resolution['view']['label']}.",
                "source": view_resolution["view"]["target_behavior"],
                "status": view_resolution["view"]["execution_status"],
            }
        )
    checklist.append(
        {
            "id": "operation",
            "item": "Confirm requested operation, frame, or final state.",
            "source": operation_request["source"],
            "status": "matched" if operation_request["matched"] else "candidate_required",
            "candidates": operation_request["candidates"],
        }
    )
    checklist.append(
        {
            "id": "screenshot",
            "item": "Capture screenshot with project, variable, view, operation, timestamp, and window metadata.",
            "source": "autoform_result_capture_evidence",
            "status": "required",
        }
    )
    return checklist


def _screenshot_caption_plan(
    variables: list[dict],
    view_resolution: dict | None,
    operation_request: dict,
) -> dict:
    return {
        "fields": [
            "project_path",
            "result_variable",
            "view",
            "operation_or_frame",
            "timestamp",
            "window_title",
            "automation_status",
        ],
        "variable_labels": [item["label"] for item in variables],
        "view_label": view_resolution["view"]["label"] if view_resolution and view_resolution.get("matched") else None,
        "operation_label": operation_request["value"],
        "automation_status": "planned_until_gui_execution",
    }


def _matching_project_windows(windows: list[dict], selected_project: dict | None) -> list[dict]:
    if not selected_project:
        return []
    project_name = _normalize_text(Path(selected_project["path"]).name)
    matches = []
    for window in windows:
        title = _normalize_text(window.get("title") or "")
        if project_name and project_name in title:
            matches.append(window)
    return matches


def _readiness_checks(
    *,
    latest_project: dict,
    window_snapshot: dict,
    matching_windows: list[dict],
    dialog_evidence: dict,
    review_plan: dict | None,
    require_window: bool,
) -> list[dict]:
    gui_evidence = result_gui_evidence(scope="all")
    checks = [
        {
            "id": "latest_project_found",
            "label": "Latest result project candidate is available.",
            "status": "pass" if latest_project["status"] == "found" else "fail",
            "severity": "blocker",
            "evidence": latest_project.get("selected", {}).get("path") if latest_project.get("selected") else latest_project["failure_reason"],
        },
        {
            "id": "semantic_review_plan",
            "label": "User request can be mapped to a result review route.",
            "status": "pass" if not review_plan or review_plan["status"] == "planned" else "fail",
            "severity": "blocker" if review_plan else "info",
            "evidence": review_plan.get("route", {}).get("selected", {}).get("route", {}).get("key") if review_plan else "not_requested",
        },
        {
            "id": "visible_autoform_window",
            "label": "A visible AutoForm window is available for GUI actions.",
            "status": "pass" if window_snapshot.get("window_count", 0) > 0 else ("fail" if require_window else "pending"),
            "severity": "blocker" if require_window else "warning",
            "evidence": f"window_count={window_snapshot.get('window_count', 0)}",
        },
        {
            "id": "interaction_ready_autoform_window",
            "label": "A visible AutoForm window is large enough and on screen for audited GUI actions.",
            "status": (
                "pass"
                if window_snapshot.get("interaction_ready_window_count", 0) > 0
                else ("fail" if require_window else "pending")
            ),
            "severity": "blocker" if require_window else "warning",
            "evidence": f"interaction_ready_window_count={window_snapshot.get('interaction_ready_window_count', 0)}",
        },
        {
            "id": "project_window_match",
            "label": "A visible AutoForm window title matches the selected result project.",
            "status": "pass" if matching_windows else ("fail" if require_window and window_snapshot.get("window_count", 0) > 0 else "pending"),
            "severity": "warning",
            "evidence": [item.get("title") for item in matching_windows] if matching_windows else "no_matching_project_window",
        },
        {
            "id": "autoform_dialog_blockers",
            "label": "No visible AutoForm dialog is blocking the result area.",
            "status": "pass" if dialog_evidence.get("blocking_dialog_count", 0) == 0 else "fail",
            "severity": "blocker" if require_window else "warning",
            "evidence": {
                "blocking_dialog_count": dialog_evidence.get("blocking_dialog_count", 0),
                "dialog_titles": [item.get("title") for item in dialog_evidence.get("blocking_dialogs", [])],
            },
        },
        {
            "id": "view_and_animation_control_evidence",
            "label": "GUI control evidence has observed animation playback and known remaining gaps.",
            "status": "pending",
            "severity": "warning",
            "evidence": gui_evidence["summary"],
        },
    ]
    return checks


def _readiness_next_actions(checks: list[dict], latest_project: dict, window_snapshot: dict) -> list[str]:
    failed = {item["id"] for item in checks if item["status"] == "fail"}
    pending = {item["id"] for item in checks if item["status"] == "pending"}
    actions = []
    if "latest_project_found" in failed:
        actions.append("Run an official example or pass an explicit .afd project path.")
    if "visible_autoform_window" in failed or "visible_autoform_window" in pending:
        selected = latest_project.get("selected")
        if selected:
            actions.append(f"Open the selected project with autoform_result_open_project: {selected['path']}")
        else:
            actions.append("Open AutoForm Forming and repeat autoform_gui_window_snapshot.")
    if "interaction_ready_autoform_window" in failed or "interaction_ready_autoform_window" in pending:
        actions.append(
            "Run autoform_gui_restore_window or CLI gui-restore-window, then repeat autoform_gui_window_snapshot."
        )
    if "project_window_match" in failed or "project_window_match" in pending:
        actions.append("After the GUI opens, capture a fresh window snapshot and compare the title with the selected .afd name.")
    if "autoform_dialog_blockers" in failed:
        actions.append("Capture the AutoForm dialog screenshot and return its title and class evidence before continuing.")
    if "view_and_animation_control_evidence" in pending:
        actions.append("Collect stable R13 view-control evidence and a frame-count reader before enabling generalized automatic clicks.")
    if window_snapshot.get("window_count", 0) > 0:
        actions.append("Capture a screenshot before any click so dialog or license blockers can be recorded.")
    return actions


def _view_control_target_views() -> list[dict]:
    by_key = {item.key: item for item in RESULT_VIEWS}
    return [by_key[key].as_dict() for key in VIEW_CONTROL_TARGET_ORDER if key in by_key]


def _view_control_evidence_plan(output_dir: Path) -> dict:
    target_views = _view_control_target_views()
    capture_sequence = []
    for item in target_views:
        view_key = item["key"]
        capture_sequence.append(
            {
                "view": view_key,
                "label": item["label"],
                "before_command": (
                    "python -m autoform_agent.cli result-view-evidence "
                    f"--view {view_key} --phase before --execute --output-dir {output_dir}"
                ),
                "after_command": (
                    "python -m autoform_agent.cli result-view-evidence "
                    f"--view {view_key} --phase after --execute --output-dir {output_dir}"
                ),
                "compare_command": (
                    "python -m autoform_agent.cli result-view-evidence "
                    f"--view {view_key} --phase compare --output-dir {output_dir}"
                ),
                "operator_instruction": _view_control_operator_instruction(item),
            }
        )
    return {
        "schema_version": "1.1",
        "status": "operator_assistance_required",
        "output_dir": str(output_dir),
        "record_path": str(_view_control_record_path(output_dir)),
        "target_views": target_views,
        "capture_sequence": capture_sequence,
        "operator_steps": [
            "在 AutoForm Forming 中打开目标结果工程，并保持窗口尺寸稳定。",
            "每个视角先由 MCP 抓取 before 截图。",
            "before 截图完成后，用户手动把 AutoForm 切换到指定视角。",
            "切换后由 MCP 抓取 after 截图，并对该视角运行 compare。",
        ],
        "user_assistance_required": True,
        "evidence_boundary": (
            "This protocol records manual view-control evidence. It prepares guarded automation profiles "
            "only after before and after screenshots confirm a result-view change."
        ),
    }


def _view_control_operator_instruction(view: dict) -> str:
    label = view["label"]
    control_label = view.get("r13_control_label")
    shortcut = view.get("r13_shortcut")
    parts = [f"before 截图完成后，请手动把 AutoForm 切换到{label}"]
    if control_label:
        parts.append(f"AutoForm R13 菜单名或控件名：{control_label}")
    if shortcut:
        parts.append(f"快捷键：{shortcut}")
    parts.append("随后保持窗口尺寸和位置不变。")
    return "；".join(parts)


def _capture_view_control_phase(*, selected_view: dict, phase: str, output_dir: Path, execute: bool) -> dict:
    context = {
        "action": "view_control_evidence",
        "phase": phase,
        "view": selected_view["key"],
        "view_label": selected_view["label"],
        "operator_instruction": _view_control_operator_instruction(selected_view),
    }
    evidence = capture_result_evidence(
        view=selected_view["key"],
        output_dir=output_dir,
        execute=execute,
        context=context,
    )
    result = {
        "schema_version": "1.1",
        "status": "captured" if execute and evidence.get("status") == "captured" else "planned",
        "execute": execute,
        "phase": phase,
        "view": selected_view,
        "output_dir": str(output_dir),
        "record_path": str(_view_control_record_path(output_dir)),
        "evidence": evidence,
        "next_step": (
            selected_view["target_behavior"]
            if phase == "before"
            else f"Run compare for {selected_view['key']} after the after screenshot."
        ),
        "user_assistance_required": phase == "before",
        "operator_instruction": _view_control_operator_instruction(selected_view),
    }
    if execute and evidence.get("status") == "captured":
        record = _view_control_record_from_evidence(selected_view=selected_view, phase=phase, evidence=evidence)
        _append_view_control_record(output_dir, record)
        result["record"] = record
    return result


def _compare_view_control_evidence(*, selected_view: dict, output_dir: Path) -> dict:
    records = _read_view_control_records(output_dir)
    view_records = [item for item in records if item.get("view_key") == selected_view["key"]]
    before = _latest_view_record(view_records, "before")
    after = _latest_view_record(view_records, "after")
    if before is None or after is None:
        return {
            "schema_version": "1.1",
            "status": "missing_evidence_pair",
            "view": selected_view,
            "record_path": str(_view_control_record_path(output_dir)),
            "before_found": before is not None,
            "after_found": after is not None,
            "next_step": "Capture both before and after screenshots for the same view, then rerun compare.",
        }
    profile = {"visual_validation": VIEW_CONTROL_VALIDATION}
    visual_validation = _animation_visual_change_check(
        _record_as_evidence(before),
        _record_as_evidence(after),
        profile,
    )
    if visual_validation["status"] == "pass":
        status = "view_change_confirmed"
        failure_reason = None
    elif visual_validation["status"] == "fail":
        status = "view_change_not_confirmed"
        failure_reason = visual_validation["failure_reason"]
    else:
        status = "view_change_validation_inconclusive"
        failure_reason = visual_validation.get("failure_reason")
    return {
        "schema_version": "1.1",
        "status": status,
        "failure_reason": failure_reason,
        "view": selected_view,
        "before_record": before,
        "after_record": after,
        "visual_validation": visual_validation,
        "next_step": (
            "Promote this view to a guarded control profile after repeated confirmation."
            if status == "view_change_confirmed"
            else "Repeat the before and after capture with the AutoForm result viewport clearly visible."
        ),
    }


def _view_control_record_path(output_dir: Path) -> Path:
    return output_dir / "view_control_evidence_records.jsonl"


def _view_control_record_from_evidence(*, selected_view: dict, phase: str, evidence: dict) -> dict:
    capture = evidence.get("capture") or {}
    focused = capture.get("focused_window") or {}
    window = focused.get("window") or {}
    return {
        "schema_version": "1.1",
        "created_at": evidence.get("created_at") or _utc_now(),
        "view_key": selected_view["key"],
        "view_label": selected_view["label"],
        "phase": phase,
        "screenshot_path": evidence.get("screenshot_path"),
        "capture_path": capture.get("path"),
        "window_handle": window.get("handle"),
        "window_pid": window.get("pid"),
        "window_process_name": window.get("process_name"),
        "window_title": window.get("title"),
        "window_rect": window.get("rect"),
        "window_interaction_ready": window.get("interaction_ready"),
        "evidence_status": evidence.get("status"),
        "context": evidence.get("context") or {},
    }


def _append_view_control_record(output_dir: Path, record: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with _view_control_record_path(output_dir).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_view_control_records(output_dir: Path) -> list[dict]:
    record_path = _view_control_record_path(output_dir)
    if not record_path.exists():
        return []
    records = []
    for line in record_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _latest_view_record(records: list[dict], phase: str) -> dict | None:
    matched = [item for item in records if item.get("phase") == phase]
    if not matched:
        return None
    return sorted(matched, key=lambda item: item.get("created_at", ""))[-1]


# 下面这一组函数把视角取证记录重新整理成截图证据。
# Compare 阶段会重新读取 before 和 after 图片做差异计算，用图片证据复核文字记录。
# The helpers below turn view-control records back into screenshot evidence.
# The compare phase does not trust text alone; it reloads before and after images and measures the pixel difference.
def _record_as_evidence(record: dict) -> dict:
    path = record.get("capture_path") or record.get("screenshot_path")
    window = {
        "handle": record.get("window_handle"),
        "pid": record.get("window_pid"),
        "process_name": record.get("window_process_name"),
        "title": record.get("window_title"),
        "rect": record.get("window_rect"),
        "interaction_ready": record.get("window_interaction_ready", True),
    }
    return {
        "capture": {
            "path": path,
            "focused_window": {"focused": True, "window": window},
        },
        "status": record.get("evidence_status"),
    }


# 下面这一组函数执行动画播放 profile，并把每一步都包在安全检查里。
# 执行前检查窗口标题和工序，执行后确认窗口没有换目标，再用结果视图区变化判断播放是否真的发生。
# The helpers below execute animation playback profiles with safety checks around each step.
# They check the window title and operation first, confirm the target window did not change, and use result-view changes as playback evidence.
def _execute_animation_control_profile(
    *,
    operation: str | None,
    action: str,
    duration_seconds: float | None,
    control_profile: str,
    click_x: float | None,
    click_y: float | None,
    output_dir: str | Path,
) -> dict:
    profile = _animation_control_profile(control_profile)
    if profile is None:
        return _animation_execution_failure(
            "unknown_animation_control_profile",
            control_profile=control_profile,
            evidence={"known_profiles": sorted(ANIMATION_CONTROL_PROFILES)},
        )

    precheck = _animation_profile_precheck(profile, operation=operation, action=action)
    if precheck["status"] != "pass":
        return _animation_execution_failure(
            precheck["failure_reason"],
            control_profile=control_profile,
            evidence=precheck,
        )

    coordinate = _animation_click_coordinate(profile, click_x=click_x, click_y=click_y)
    if coordinate["status"] != "pass":
        return _animation_execution_failure(
            coordinate["failure_reason"],
            control_profile=control_profile,
            evidence=coordinate,
        )

    before = _safe_result_evidence(
        output_dir=output_dir,
        execute=True,
        context={"action": "play_forming_animation", "phase": "before_click", "control_profile": control_profile},
    )
    click_result = click_autoform_window(
        coordinate["x"],
        coordinate["y"],
        relative=True,
        focus_first=True,
        restore_window=False,
        wait_seconds=0.2,
    )
    if duration_seconds and duration_seconds > 0:
        time.sleep(min(duration_seconds, 30))
    after = _safe_result_evidence(
        output_dir=output_dir,
        execute=True,
        context={"action": "play_forming_animation", "phase": "after_click", "control_profile": control_profile},
    )
    clicked = bool(click_result.get("clicked"))
    visual_validation = _animation_visual_change_check(before, after, profile)
    if clicked and visual_validation["status"] == "pass":
        status = "played_with_guarded_mcp_click_profile"
        failure_reason = None
    elif clicked and visual_validation["status"] == "fail":
        status = "clicked_without_result_view_change_detected"
        failure_reason = "animation_visual_change_not_detected"
    elif clicked:
        status = "clicked_without_visual_validation"
        failure_reason = visual_validation.get("failure_reason", "animation_visual_validation_unavailable")
    else:
        status = "blocked_for_gui_execution"
        failure_reason = click_result.get("reason", "click_failed")
    return {
        "schema_version": "1.1",
        "status": status,
        "executed": clicked,
        "backend": profile["backend"],
        "control_profile": control_profile,
        "operation": operation,
        "action": action,
        "duration_seconds": duration_seconds,
        "precheck": precheck,
        "coordinate": coordinate,
        "before_evidence": before,
        "click_result": click_result,
        "after_evidence": after,
        "visual_validation": visual_validation,
        "failure_reason": failure_reason,
        "evidence_boundary": profile["evidence_boundary"],
    }


def _execute_manual_animation_observation(
    *,
    operation: str | None,
    action: str,
    duration_seconds: float | None,
    control_profile: str,
    output_dir: str | Path,
) -> dict:
    profile = _animation_control_profile(control_profile)
    if profile is None:
        return _animation_execution_failure(
            "unknown_animation_control_profile",
            control_profile=control_profile,
            evidence={"known_profiles": sorted(ANIMATION_CONTROL_PROFILES)},
        )

    precheck = _animation_profile_precheck(profile, operation=operation, action=action)
    if precheck["status"] != "pass":
        return _animation_execution_failure(
            precheck["failure_reason"],
            control_profile=control_profile,
            evidence=precheck,
            backend=profile["backend"],
        )

    before = _safe_result_evidence(
        output_dir=output_dir,
        execute=True,
        context={
            "action": "play_forming_animation",
            "phase": "before_manual_playback",
            "control_profile": control_profile,
            "operator": "user",
        },
    )
    wait_seconds = max(0.0, min(float(duration_seconds or 0.0), 30.0))
    if wait_seconds:
        time.sleep(wait_seconds)
    after = _safe_result_evidence(
        output_dir=output_dir,
        execute=True,
        context={
            "action": "play_forming_animation",
            "phase": "after_manual_playback",
            "control_profile": control_profile,
            "operator": "user",
        },
    )
    visual_validation = _animation_visual_change_check(before, after, profile)
    if visual_validation["status"] == "pass":
        status = "manual_playback_observed_with_result_view_change"
        failure_reason = None
    elif visual_validation["status"] == "fail":
        status = "manual_playback_not_confirmed"
        failure_reason = "animation_visual_change_not_detected"
    else:
        status = "manual_playback_observation_inconclusive"
        failure_reason = visual_validation.get("failure_reason", "animation_visual_validation_unavailable")
    return {
        "schema_version": "1.1",
        "status": status,
        "executed": True,
        "backend": profile["backend"],
        "control_profile": control_profile,
        "operation": operation,
        "action": action,
        "duration_seconds": duration_seconds,
        "wait_seconds": wait_seconds,
        "precheck": precheck,
        "before_evidence": before,
        "after_evidence": after,
        "visual_validation": visual_validation,
        "failure_reason": failure_reason,
        "manual_operator_required": True,
        "manual_operator_steps": list(profile.get("operator_steps", ())),
        "evidence_boundary": profile["evidence_boundary"],
    }


def _animation_execution_failure(
    reason: str,
    *,
    control_profile: str,
    evidence: dict,
    backend: str = "mcp_win32_gui_primitives",
) -> dict:
    return {
        "schema_version": "1.1",
        "status": "blocked_for_gui_execution",
        "executed": False,
        "backend": backend,
        "control_profile": control_profile,
        "failure_reason": reason,
        "precheck": evidence,
    }


def _animation_profile_precheck(profile: dict, *, operation: str | None, action: str) -> dict:
    action_key = _normalize_text(action)
    supported_actions = tuple(_normalize_text(item) for item in profile.get("supported_actions", ()))
    if action_key not in supported_actions:
        return {
            "status": "fail",
            "failure_reason": "animation_action_not_supported_by_profile",
            "requested_action": action,
            "supported_actions": list(profile.get("supported_actions", ())),
        }

    operation_terms = tuple(profile.get("operation_terms", ()))
    if operation and operation_terms:
        normalized_operation = _normalize_text(operation)
        if not any(_normalize_text(term) in normalized_operation or normalized_operation in _normalize_text(term) for term in operation_terms):
            return {
                "status": "fail",
                "failure_reason": "animation_operation_not_supported_by_profile",
                "requested_operation": operation,
                "supported_operations": list(operation_terms),
            }

    snapshot = autoform_window_snapshot()
    if snapshot.get("window_count", 0) <= 0:
        return {
            "status": "fail",
            "failure_reason": "no_visible_autoform_window",
            "window_snapshot": snapshot,
        }
    if snapshot.get("interaction_ready_window_count", 0) <= 0:
        return {
            "status": "fail",
            "failure_reason": "no_interaction_ready_autoform_window",
            "window_snapshot": snapshot,
        }
    candidate_windows = _interaction_ready_windows(snapshot)
    matching_windows = _windows_matching_terms(candidate_windows, profile.get("title_terms", ()))
    if not matching_windows:
        return {
            "status": "fail",
            "failure_reason": "animation_profile_window_title_not_matched",
            "required_title_terms": list(profile.get("title_terms", ())),
            "window_snapshot": snapshot,
        }
    return {
        "status": "pass",
        "profile_status": profile["status"],
        "matched_windows": matching_windows,
        "window_snapshot": snapshot,
        "evidence_record_key": profile["evidence_record_key"],
    }


def _animation_click_coordinate(profile: dict, *, click_x: float | None, click_y: float | None) -> dict:
    default_click = profile.get("default_click", {})
    x = default_click.get("x") if click_x is None else click_x
    y = default_click.get("y") if click_y is None else click_y
    if x is None or y is None:
        return {"status": "fail", "failure_reason": "animation_click_coordinate_missing"}
    if not 0 <= float(x) <= 1 or not 0 <= float(y) <= 1:
        return {
            "status": "fail",
            "failure_reason": "animation_click_coordinate_out_of_relative_bounds",
            "x": x,
            "y": y,
        }
    return {
        "status": "pass",
        "x": float(x),
        "y": float(y),
        "relative": True,
        "label": default_click.get("label"),
        "source": default_click.get("source"),
        "overridden": click_x is not None or click_y is not None,
    }


def _safe_result_evidence(*, output_dir: str | Path, execute: bool, context: dict) -> dict:
    try:
        return capture_result_evidence(output_dir=output_dir, execute=execute, context=context)
    except Exception as exc:
        return {
            "schema_version": "1.1",
            "status": "capture_failed",
            "execute": execute,
            "context": context,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _animation_visual_change_check(before: dict, after: dict, profile: dict) -> dict:
    """Compare before/after screenshots and confirm change in the result viewport."""

    before_path = _evidence_image_path(before)
    after_path = _evidence_image_path(after)
    before_window = _evidence_target_window(before)
    after_window = _evidence_target_window(after)
    if before_window is None or after_window is None:
        return {
            "status": "inconclusive",
            "failure_reason": "animation_visual_validation_target_window_missing",
            "before_image": str(before_path) if before_path else None,
            "after_image": str(after_path) if after_path else None,
            "evidence_boundary": "Animation evidence must be tied to a focused, interaction-ready AutoForm window.",
        }
    if not _same_evidence_window(before_window, after_window):
        return {
            "status": "inconclusive",
            "failure_reason": "animation_visual_validation_target_window_changed",
            "before_image": str(before_path) if before_path else None,
            "after_image": str(after_path) if after_path else None,
            "before_window": _compact_window_evidence(before_window),
            "after_window": _compact_window_evidence(after_window),
        }
    if before_path is None or after_path is None:
        return {
            "status": "inconclusive",
            "failure_reason": "animation_visual_validation_image_missing",
            "before_image": str(before_path) if before_path else None,
            "after_image": str(after_path) if after_path else None,
        }
    if not before_path.exists() or not after_path.exists():
        return {
            "status": "inconclusive",
            "failure_reason": "animation_visual_validation_image_not_found",
            "before_image": str(before_path),
            "after_image": str(after_path),
        }
    try:
        with Image.open(before_path) as before_image_raw, Image.open(after_path) as after_image_raw:
            before_image = before_image_raw.convert("RGB")
            after_image = after_image_raw.convert("RGB")
            if before_image.size != after_image.size:
                return {
                    "status": "inconclusive",
                    "failure_reason": "animation_visual_validation_size_mismatch",
                    "before_image": str(before_path),
                    "after_image": str(after_path),
                    "before_size": before_image.size,
                    "after_size": after_image.size,
                }

            crop_fraction = tuple(profile.get("visual_validation", {}).get("crop_fraction", (0.15, 0.12, 0.82, 0.70)))
            window_box = _window_crop_box(before_image.size, before_window)
            if window_box is None:
                return {
                    "status": "inconclusive",
                    "failure_reason": "animation_visual_validation_window_rect_outside_image",
                    "before_image": str(before_path),
                    "after_image": str(after_path),
                    "before_window": _compact_window_evidence(before_window),
                    "image_size": before_image.size,
                }
            result_view_box = _fractional_crop_box_within(window_box, crop_fraction)
            result_view_metrics = _image_difference_metrics(
                before_image.crop(result_view_box),
                after_image.crop(result_view_box),
            )
            full_image_metrics = _image_difference_metrics(before_image, after_image)
    except Exception as exc:
        return {
            "status": "inconclusive",
            "failure_reason": "animation_visual_validation_failed",
            "before_image": str(before_path),
            "after_image": str(after_path),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    validation_config = profile.get("visual_validation", {})
    min_ratio = float(validation_config.get("min_result_view_changed_pixel_ratio", 0.005))
    min_mean = float(validation_config.get("min_result_view_mean_delta", 0.10))
    result_changed = (
        result_view_metrics["changed_pixel_ratio"] >= min_ratio
        or result_view_metrics["mean_delta"] >= min_mean
    )
    return {
        "status": "pass" if result_changed else "fail",
        "failure_reason": None if result_changed else "animation_visual_change_not_detected",
        "before_image": str(before_path),
        "after_image": str(after_path),
        "target_window": _compact_window_evidence(before_window),
        "result_view_crop_fraction": list(crop_fraction),
        "window_box": window_box,
        "result_view_box": result_view_box,
        "thresholds": {
            "min_result_view_changed_pixel_ratio": min_ratio,
            "min_result_view_mean_delta": min_mean,
        },
        "result_view_metrics": result_view_metrics,
        "full_image_metrics": full_image_metrics,
        "evidence_boundary": (
            "The confirmation compares the result-view crop inside the focused AutoForm window and ignores changes outside it."
        ),
    }


def _evidence_image_path(evidence: dict) -> Path | None:
    capture = evidence.get("capture") if isinstance(evidence, dict) else None
    if isinstance(capture, dict) and capture.get("path"):
        return Path(capture["path"])
    screenshot_path = evidence.get("screenshot_path") if isinstance(evidence, dict) else None
    return Path(screenshot_path) if screenshot_path else None


def _evidence_target_window(evidence: dict) -> dict | None:
    capture = evidence.get("capture") if isinstance(evidence, dict) else None
    focused = capture.get("focused_window") if isinstance(capture, dict) else None
    window = focused.get("window") if isinstance(focused, dict) else None
    if not isinstance(window, dict):
        return None
    if not isinstance(window.get("rect"), dict):
        return None
    if not window.get("interaction_ready", True):
        return None
    return window


def _same_evidence_window(left: dict, right: dict) -> bool:
    left_rect = _compact_rect(left.get("rect") or {})
    right_rect = _compact_rect(right.get("rect") or {})
    if left_rect != right_rect:
        return False
    left_handle = left.get("handle")
    right_handle = right.get("handle")
    if left_handle and right_handle:
        return left_handle == right_handle
    left_title = (left.get("title") or "").strip()
    right_title = (right.get("title") or "").strip()
    if left_title and right_title and left_title != right_title:
        return False
    return True


def _compact_window_evidence(window: dict) -> dict:
    return {
        "handle": window.get("handle"),
        "pid": window.get("pid"),
        "process_name": window.get("process_name"),
        "title": window.get("title"),
        "rect": _compact_rect(window.get("rect") or {}),
        "interaction_ready": window.get("interaction_ready"),
    }


def _compact_rect(rect: dict) -> dict:
    return {
        "left": int(rect.get("left") or 0),
        "top": int(rect.get("top") or 0),
        "width": int(rect.get("width") or 0),
        "height": int(rect.get("height") or 0),
    }


def _window_crop_box(image_size: tuple[int, int], window: dict) -> tuple[int, int, int, int] | None:
    image_width, image_height = image_size
    rect = window.get("rect") or {}
    left = int(rect.get("left") or 0)
    top = int(rect.get("top") or 0)
    width = int(rect.get("width") or 0)
    height = int(rect.get("height") or 0)
    right = left + width
    bottom = top + height
    clipped_left = max(0, min(image_width, left))
    clipped_top = max(0, min(image_height, top))
    clipped_right = max(0, min(image_width, right))
    clipped_bottom = max(0, min(image_height, bottom))
    if clipped_right - clipped_left < 100 or clipped_bottom - clipped_top < 100:
        return None
    return (clipped_left, clipped_top, clipped_right, clipped_bottom)


def _fractional_crop_box(size: tuple[int, int], crop_fraction: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    width, height = size
    left, top, right, bottom = crop_fraction
    left_px = max(0, min(width - 1, int(width * left)))
    top_px = max(0, min(height - 1, int(height * top)))
    right_px = max(left_px + 1, min(width, int(width * right)))
    bottom_px = max(top_px + 1, min(height, int(height * bottom)))
    return (left_px, top_px, right_px, bottom_px)


def _fractional_crop_box_within(
    box: tuple[int, int, int, int],
    crop_fraction: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    window_left, window_top, window_right, window_bottom = box
    width = max(1, window_right - window_left)
    height = max(1, window_bottom - window_top)
    left, top, right, bottom = crop_fraction
    left_px = window_left + max(0, min(width - 1, int(width * left)))
    top_px = window_top + max(0, min(height - 1, int(height * top)))
    right_px = window_left + max(left_px - window_left + 1, min(width, int(width * right)))
    bottom_px = window_top + max(top_px - window_top + 1, min(height, int(height * bottom)))
    return (left_px, top_px, min(window_right, right_px), min(window_bottom, bottom_px))


def _image_difference_metrics(before_image: Image.Image, after_image: Image.Image) -> dict:
    diff = ImageChops.difference(before_image, after_image).convert("L")
    histogram = diff.histogram()
    total_pixels = before_image.size[0] * before_image.size[1]
    changed_pixels = total_pixels - histogram[0]
    bbox = diff.getbbox()
    return {
        "size": before_image.size,
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "changed_pixel_ratio": changed_pixels / total_pixels if total_pixels else 0.0,
        "mean_delta": ImageStat.Stat(diff).mean[0],
        "bbox": bbox,
    }


def _animation_control_profile(control_profile: str) -> dict | None:
    profile = ANIMATION_CONTROL_PROFILES.get(control_profile)
    if profile is None:
        return None
    return {"key": control_profile, **profile}


def _animation_profiles_for_scope(normalized_scope: str) -> list[dict]:
    if normalized_scope not in {"", "all", "*", "animation", "postprocessing", "time step strip"}:
        return []
    return [_animation_control_profile(key) for key in sorted(ANIMATION_CONTROL_PROFILES)]


def _windows_matching_terms(windows: list[dict], terms: Iterable[str]) -> list[dict]:
    required = [_normalize_text(term) for term in terms if term]
    if not required:
        return windows
    matches = []
    for window in windows:
        haystack = _normalize_text(f"{window.get('title') or ''} {window.get('process_name') or ''}")
        if all(term in haystack for term in required):
            matches.append(window)
    return matches


def _interaction_ready_windows(snapshot: dict) -> list[dict]:
    ready_windows = snapshot.get("interaction_ready_windows")
    if isinstance(ready_windows, list) and ready_windows:
        return ready_windows
    return [window for window in snapshot.get("windows", []) if window.get("interaction_ready")]


def _dialog_classification_for_scope(normalized_scope: str) -> dict:
    if not _scope_wants_dialog_classifier(normalized_scope):
        return {
            "schema_version": "1.1",
            "status": "not_requested_for_scope",
            "classifier": "title_class_window_classifier",
        }
    try:
        return classify_autoform_dialogs()
    except Exception as exc:
        return {
            "schema_version": "1.1",
            "status": "classification_unavailable",
            "classifier": "title_class_window_classifier",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _scope_wants_dialog_classifier(normalized_scope: str) -> bool:
    if normalized_scope in {"", "all", "*"}:
        return True
    return normalized_scope in {"dialog", "dialogs", "blocker", "readiness", "recovery", "postprocessing"}


def _classify_autoform_dialog_window(window: dict) -> dict | None:
    text = _dialog_text(window)
    for classifier in DIALOG_CLASSIFIERS:
        matched_terms = [_normalize_text(term) for term in classifier["terms"] if _normalize_text(term) in text]
        if matched_terms:
            return _dialog_result_from_window(window, classifier, matched_terms=matched_terms)
    if _is_generic_dialog_candidate(window, text):
        classifier = {
            "key": "generic_dialog_candidate",
            "category": "generic_popup",
            "confidence": "low",
            "blocks_result_view_when_visible": True,
            "next_action": "Capture the popup screenshot before any click.",
        }
        return _dialog_result_from_window(window, classifier, matched_terms=["class_or_geometry"])
    return None


def _dialog_result_from_window(window: dict, classifier: dict, *, matched_terms: list[str]) -> dict:
    visible = bool(window.get("visible"))
    blocks_result_view = visible and bool(classifier.get("blocks_result_view_when_visible"))
    return {
        "key": classifier["key"],
        "category": classifier["category"],
        "confidence": classifier["confidence"],
        "matched_terms": matched_terms,
        "title": window.get("title"),
        "class_name": window.get("class_name"),
        "visible": visible,
        "interaction_ready": bool(window.get("interaction_ready")),
        "blocks_result_view": blocks_result_view,
        "window": _compact_dialog_window(window),
        "next_action": classifier["next_action"],
    }


def _dialog_text(window: dict) -> str:
    return _normalize_text(
        f"{window.get('title') or ''} {window.get('class_name') or ''} {window.get('process_name') or ''}"
    )


def _is_generic_dialog_candidate(window: dict, text: str) -> bool:
    title = _normalize_text(window.get("title") or "")
    class_name = _normalize_text(window.get("class_name") or "")
    if ".afd" in title:
        return False
    if not window.get("visible"):
        return False
    if any(term in class_name or term in text for term in GENERIC_DIALOG_CLASS_TERMS):
        return True
    return bool(title in {"autoform", "autoform forming", "autoform forming r13"} and not window.get("interaction_ready"))


def _compact_dialog_window(window: dict) -> dict:
    return {
        "handle": window.get("handle"),
        "pid": window.get("pid"),
        "process_name": window.get("process_name"),
        "title": window.get("title"),
        "class_name": window.get("class_name"),
        "visible": bool(window.get("visible")),
        "rect": _compact_rect(window.get("rect") or {}),
        "interaction_ready": window.get("interaction_ready"),
    }


def _dialog_next_actions(dialogs: list[dict], blocking: list[dict]) -> list[str]:
    if blocking:
        return _dedupe_texts(item["next_action"] for item in blocking if item.get("next_action"))
    if dialogs:
        return _dedupe_texts(item["next_action"] for item in dialogs if item.get("next_action"))
    return ["No AutoForm dialog candidate is visible in the current window snapshot."]


def _gui_record_matches_scope(record: GuiEvidenceRecord, normalized_scope: str) -> bool:
    if normalized_scope in {"", "all", "*"}:
        return True
    fields = (record.key, record.status, *record.scopes)
    return any(normalized_scope == _normalize_text(field) or normalized_scope in _normalize_text(field) for field in fields)


def _gui_evidence_status(matched_records: list[dict], gaps: list[dict], observed: list[dict]) -> str:
    if not matched_records:
        return "no_records_for_scope"
    if observed and gaps:
        return "partial_evidence_with_known_gaps"
    if observed:
        return "observed"
    return "gaps_only"


def _gui_status_is_observed(status: str) -> bool:
    normalized = str(status or "")
    return normalized.startswith("locally_observed") or "observed" in normalized or "confirmed" in normalized


def _evidence_path_status(path: str, *, workspace: str | Path | None = None) -> dict:
    raw_path = Path(path)
    base = Path(workspace or Path.cwd())
    resolved = raw_path if raw_path.is_absolute() else (base / raw_path)
    try:
        exists = resolved.exists()
    except OSError:
        exists = False
    return {
        "path": path,
        "resolved_path": str(resolved),
        "exists": exists,
    }


def _dedupe_texts(items: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _normalize_text(value: str) -> str:
    return value.casefold().replace("_", " ").replace("-", " ").strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
