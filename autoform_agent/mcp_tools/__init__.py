"""这个文件集中登记所有 MCP 工具函数。新增工具必须进入这里的总清单，测试会检查工具数量和工具名是否稳定。

This file registers all MCP tool functions in one place. New tools must be added to this master list, and tests check that tool counts and names stay stable.
"""

from __future__ import annotations

from typing import Any, Callable

from .status import *
from .status import register_status_tools
from .project import *
from .project import register_project_tools
from .jobs import *
from .jobs import register_job_tools
from .materials import *
from .materials import register_material_tools
from .quicklink import *
from .quicklink import register_quicklink_tools
from .environment import *
from .environment import register_environment_tools
from .queue import *
from .queue import register_queue_tools
from .solver import *
from .solver import register_solver_tools
from .commands import *
from .commands import register_command_tools
from .reporting import *
from .reporting import register_reporting_tools
from .release import *
from .release import register_release_tools
from .reference import *
from .reference import register_reference_tools
from .gui import *
from .gui import register_gui_tools


MCP_TOOL_LAYERS: tuple[tuple[str, Callable[[Any], None]], ...] = (
    ('status', register_status_tools),
    ('project', register_project_tools),
    ('jobs', register_job_tools),
    ('materials', register_material_tools),
    ('quicklink', register_quicklink_tools),
    ('environment', register_environment_tools),
    ('queue', register_queue_tools),
    ('solver', register_solver_tools),
    ('commands', register_command_tools),
    ('reporting', register_reporting_tools),
    ('release', register_release_tools),
    ('reference', register_reference_tools),
    ('gui', register_gui_tools),
)


def register_all_tools(mcp: Any) -> None:
    """Register every MCP tool layer on the provided FastMCP instance.

    The order is intentionally explicit.  It mirrors the project domains and
    makes duplicate registration easy to diagnose during import checks.
    """
    for _layer_name, register_layer in MCP_TOOL_LAYERS:
        register_layer(mcp)


ALL_TOOL_FUNCTIONS = (
    autoform_status_snapshot,
    autoform_discover_installation,
    autoform_start_ui,
    autoform_open_afd,
    autoform_resolve_project,
    autoform_project_run,
    autoform_example_project_baseline,
    autoform_official_sample_run_summary,
    autoform_run_forming_job,
    autoform_forming_job_plan,
    autoform_collect_forming_job_logs,
    autoform_list_example_projects,
    autoform_inspect_afd,
    autoform_get_afd_readable_index,
    autoform_get_afd_project_summary,
    autoform_list_executables,
    autoform_job_submit,
    autoform_job_status,
    autoform_job_wait,
    autoform_job_cancel,
    autoform_job_logs,
    autoform_job_archive,
    autoform_list_jobs,
    autoform_install_materials,
    autoform_list_material_libraries,
    autoform_find_duplicate_material_files,
    autoform_material_library_backup_plan,
    autoform_inspect_material_file,
    autoform_install_quicklink_bridge,
    autoform_get_quicklink_bridge_status,
    autoform_list_quicklink_exports,
    autoform_parse_quicklink_xml,
    autoform_quicklink_schema,
    autoform_get_project_data,
    autoform_get_blank_info,
    autoform_list_exported_geometry,
    autoform_quicklink_archive_inventory,
    autoform_compare_quicklink_exports,
    autoform_get_quicklink_section,
    autoform_get_quicklink_process_plan,
    autoform_get_quicklink_evaluation,
    autoform_get_quicklink_die_face,
    autoform_list_quicklink_standards,
    autoform_validate_quicklink_standard,
    autoform_get_queue_config,
    autoform_get_remote_hosts,
    autoform_get_logging_config,
    autoform_collect_recent_logs,
    autoform_collect_gui_project_events,
    autoform_diagnostic_bundle_plan,
    autoform_environment_snapshot,
    autoform_queue_health_check,
    autoform_queue_command_plan,
    autoform_queue_client_probe,
    autoform_lsf_command_plan,
    autoform_solver_capability_specs,
    autoform_solver_log_events,
    autoform_solver_command_probe,
    autoform_forming_job_check_plan,
    autoform_forming_solver_kinematic_plan,
    autoform_forming_solver_full_plan,
    autoform_forming_solver_kinematic_batch_probe,
    autoform_forming_solver_full_batch_probe,
    autoform_postsolve_plan,
    autoform_rgen_plan,
    autoform_list_command_specs,
    autoform_executable_command_plan,
    autoform_executable_help_probe,
    autoform_mat_to_mtb_plan,
    autoform_mat_to_mtb_convert,
    autoform_report_ms_office_plan,
    autoform_report_inventory,
    autoform_report_log_events,
    autoform_result_inventory,
    autoform_report_delivery_plan,
    autoform_copy_result_evidence,
    autoform_release_readiness_check,
    autoform_release_package_plan,
    autoform_install_check_plan,
    autoform_public_release_scan,
    autoform_write_safety_plan,
    autoform_internal_extension_boundary,
    autoform_list_help_topics,
    autoform_help_topic_agent_mapping,
    autoform_list_af_api_modules,
    autoform_check_af_api_build_env,
    autoform_af_api_template_plan,
    autoform_af_api_build_preview,
    autoform_module_coverage_matrix,
    autoform_gui_window_snapshot,
    autoform_gui_focus,
    autoform_gui_restore_window,
    autoform_gui_screenshot,
    autoform_gui_click,
    autoform_gui_drag,
    autoform_computer_use_probe,
    autoform_gui_control_demo,
    autoform_r12_project_view_demo,
    autoform_result_query_capabilities,
    autoform_result_gui_evidence,
    autoform_result_blockers,
    autoform_result_find_latest,
    autoform_result_open_latest,
    autoform_result_open_project,
    autoform_result_show_variable,
    autoform_result_set_view,
    autoform_result_view_evidence,
    autoform_result_play_forming_animation,
    autoform_result_capture_evidence,
    autoform_result_route_task,
    autoform_result_plan_review,
    autoform_result_readiness,
)

RESOURCE_FUNCTIONS = (autoform_status_resource,)

EXPORTED_FUNCTION_NAMES = tuple(
    function.__name__
    for function in (*RESOURCE_FUNCTIONS, *ALL_TOOL_FUNCTIONS)
)

__all__ = [
    "MCP_TOOL_LAYERS",
    "ALL_TOOL_FUNCTIONS",
    "RESOURCE_FUNCTIONS",
    "EXPORTED_FUNCTION_NAMES",
    "register_all_tools",
    "register_status_tools",
    "register_project_tools",
    "register_job_tools",
    "register_material_tools",
    "register_quicklink_tools",
    "register_environment_tools",
    "register_queue_tools",
    "register_solver_tools",
    "register_command_tools",
    "register_reporting_tools",
    "register_release_tools",
    "register_reference_tools",
    "register_gui_tools",
    *EXPORTED_FUNCTION_NAMES,
]
