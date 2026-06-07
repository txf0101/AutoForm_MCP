"""这个文件用表格方式说明当前 MCP 能力覆盖了哪些 AutoForm 领域，还有哪些领域需要后续扩展。

This file summarizes which AutoForm domains are covered by the current MCP tools and which domains still need future expansion.
"""

from __future__ import annotations

from .inventory import list_help_topics


MODULE_COVERAGE = [
    {
        "module": "Installation and environment",
        "status": "implemented",
        "tools": ["autoform_discover_installation", "autoform_list_executables"],
        "evidence": ["registry discovery", "package_info_lite.json", "bin directory"],
    },
    {
        "module": "Project files",
        "status": "implemented-index",
        "tools": [
            "autoform_list_example_projects",
            "autoform_inspect_afd",
            "autoform_get_afd_readable_index",
            "autoform_get_afd_project_summary",
        ],
        "evidence": ["ProgramData test projects", "file metadata", "printable .afd fragments"],
    },
    {
        "module": "QuickLink",
        "status": "implemented",
        "tools": [
            "autoform_install_quicklink_bridge",
            "autoform_get_quicklink_bridge_status",
            "autoform_list_quicklink_exports",
            "autoform_parse_quicklink_xml",
            "autoform_get_quicklink_process_plan",
            "autoform_get_quicklink_evaluation",
            "autoform_get_quicklink_die_face",
            "autoform_quicklink_archive_inventory",
            "autoform_compare_quicklink_exports",
            "autoform_quicklink_schema",
            "autoform_list_quicklink_standards",
        ],
        "evidence": ["Scripts_Readme.txt", "QuickLink templates", "collected archive"],
    },
    {
        "module": "Diagnostics",
        "status": "implemented-read-only-and-preview",
        "tools": [
            "autoform_status_snapshot",
            "autoform_collect_recent_logs",
            "autoform_collect_gui_project_events",
            "autoform_diagnostic_bundle_plan",
            "autoform_environment_snapshot",
        ],
        "evidence": ["autoform://status", "systemConfigFile.xml", "workspace log files", "installation discovery"],
    },
    {
        "module": "Queue and remote computing",
        "status": "implemented-read-only-and-probe",
        "tools": [
            "autoform_get_queue_config",
            "autoform_get_remote_hosts",
            "autoform_queue_health_check",
            "autoform_queue_client_probe",
            "autoform_lsf_command_plan",
        ],
        "evidence": ["systemConfigFile.xml", "AFQueueClient wrappers", "AFQueueClient config probe", "aflsf wrappers"],
    },
    {
        "module": "Materials",
        "status": "implemented",
        "tools": [
            "autoform_install_materials",
            "autoform_list_material_libraries",
            "autoform_find_duplicate_material_files",
            "autoform_material_library_backup_plan",
            "autoform_inspect_material_file",
            "autoform_mat_to_mtb_plan",
            "autoform_mat_to_mtb_convert",
        ],
        "evidence": ["materials directory", "material file extensions", "material file headers", "AFMat2Mtb conversion probe", "tests"],
    },
    {
        "module": "Reports and executable command planning",
        "status": "implemented-inventory-preview-and-delivery-package",
        "tools": [
            "autoform_list_command_specs",
            "autoform_executable_command_plan",
            "autoform_executable_help_probe",
            "autoform_report_ms_office_plan",
            "autoform_report_inventory",
            "autoform_report_log_events",
            "autoform_result_inventory",
            "autoform_report_delivery_plan",
            "autoform_copy_result_evidence",
            "autoform_project_run",
            "autoform_example_project_baseline",
        ],
        "evidence": ["bin directory", "helpLinks.cfg", "report templates", "GUI logs", "QuickLink exports", "command preview tests"],
    },
    {
        "module": "AF_API",
        "status": "implemented-preview",
        "tools": [
            "autoform_list_af_api_modules",
            "autoform_check_af_api_build_env",
            "autoform_af_api_template_plan",
            "autoform_af_api_build_preview",
        ],
        "evidence": ["AF_API headers and C samples"],
    },
    {
        "module": "Simulation jobs",
        "status": "implemented-lifecycle-kinematic-and-full-execution",
        "tools": [
            "autoform_run_forming_job",
            "autoform_forming_job_plan",
            "autoform_collect_forming_job_logs",
            "autoform_job_submit",
            "autoform_job_status",
            "autoform_job_wait",
            "autoform_job_cancel",
            "autoform_job_logs",
            "autoform_job_archive",
            "autoform_list_jobs",
            "autoform_resolve_project",
            "autoform_project_run",
            "autoform_example_project_baseline",
            "autoform_solver_capability_specs",
            "autoform_solver_log_events",
            "autoform_solver_command_probe",
            "autoform_forming_job_check_plan",
            "autoform_forming_solver_kinematic_plan",
            "autoform_forming_solver_kinematic_batch_probe",
            "autoform_forming_solver_full_plan",
            "autoform_forming_solver_full_batch_probe",
            "autoform_postsolve_plan",
            "autoform_rgen_plan",
        ],
        "evidence": [
            "AFFormingJob_R13.cmd",
            "AFFormingJob.exe",
            "AFFormingSolver.exe",
            "AFFormingPostSolve.exe",
            "Business_CommonAFRGen.dll",
            "Solver_R13.afd kinematic check returncode 0",
            "7 copied official examples batch kinematic probe",
            "3 copied official examples full/default solve returncode 0",
            "file-based lifecycle registry",
            "tests/test_jobs.py",
            "tests/test_project_workflow.py",
        ],
    },
    {
        "module": "Safety and extension boundary",
        "status": "implemented-publication-scan-and-extension-boundary",
        "tools": [
            "autoform_public_release_scan",
            "autoform_write_safety_plan",
            "autoform_internal_extension_boundary",
        ],
        "evidence": ["autoform_mcp_agent/safety.py", "autoform_mcp_agent/extension.py", "tests/test_safety_extension.py"],
    },
    {
        "module": "Release packaging",
        "status": "implemented-readiness-and-package-plan",
        "tools": [
            "autoform_release_readiness_check",
            "autoform_release_package_plan",
            "autoform_install_check_plan",
        ],
        "evidence": [
            "INSTALL.md",
            "UNINSTALL.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "RELEASE_CHECKLIST.md",
            "environment.yml",
            "pyproject.toml",
            "tests/test_release.py",
        ],
    },
    {
        "module": "GUI topics",
        "status": "implemented-index",
        "tools": [
            "autoform_list_help_topics",
            "autoform_help_topic_agent_mapping",
            "autoform_module_coverage_matrix",
        ],
        "evidence": ["helpLinks.cfg"],
    },
]


HELP_TOPIC_DOMAIN_RULES = [
    {
        "domain": "materials",
        "needles": ["material"],
        "agent_tools": [
            "autoform_list_material_libraries",
            "autoform_find_duplicate_material_files",
            "autoform_inspect_material_file",
            "autoform_mat_to_mtb_plan",
            "autoform_mat_to_mtb_convert",
        ],
    },
    {
        "domain": "part_stage",
        "needles": ["part-stage"],
        "agent_tools": ["autoform_parse_quicklink_xml", "autoform_list_exported_geometry"],
    },
    {
        "domain": "blank_stage",
        "needles": ["blank-stage", "blank"],
        "agent_tools": ["autoform_get_blank_info", "autoform_parse_quicklink_xml"],
    },
    {
        "domain": "process_stage",
        "needles": ["process-stage", "process"],
        "agent_tools": ["autoform_get_quicklink_process_plan", "autoform_parse_quicklink_xml"],
    },
    {
        "domain": "simulation_stage",
        "needles": ["simulation-stage", "simulation"],
        "agent_tools": [
            "autoform_solver_capability_specs",
            "autoform_forming_job_check_plan",
            "autoform_forming_solver_kinematic_plan",
            "autoform_collect_forming_job_logs",
        ],
    },
    {
        "domain": "evaluation_stage",
        "needles": ["evaluation-stage", "evaluation"],
        "agent_tools": ["autoform_get_quicklink_evaluation"],
    },
    {
        "domain": "reporting",
        "needles": ["reportmanager", "report"],
        "agent_tools": ["autoform_report_inventory", "autoform_report_log_events", "autoform_report_ms_office_plan"],
    },
]


def module_coverage_matrix() -> list[dict]:
    """Return a high-level module coverage matrix for Agent planning."""

    topics = list_help_topics()
    topic_counts = {
        "Material": _count_topics(topics, "material"),
        "Part Stage": _count_topics(topics, "part-stage"),
        "Blank Stage": _count_topics(topics, "blank-stage"),
        "Process Stage": _count_topics(topics, "process-stage"),
        "Simulation Stage": _count_topics(topics, "simulation-stage"),
        "Evaluation Stage": _count_topics(topics, "evaluation-stage"),
        "Report Manager": _count_topics(topics, "reportmanager"),
    }
    matrix = []
    for item in MODULE_COVERAGE:
        row = dict(item)
        row["help_topic_counts"] = topic_counts if item["module"] == "GUI topics" else {}
        matrix.append(row)
    return matrix


def help_topic_agent_mapping(query: str | None = None) -> dict:
    """Map helpLinks.cfg topics to current Agent domains and tools."""

    topics = list_help_topics(query=query)
    mapped_topics = []
    domain_counts: dict[str, int] = {}
    for topic in topics:
        mapping = _map_help_topic(topic)
        domain_counts[mapping["domain"]] = domain_counts.get(mapping["domain"], 0) + 1
        mapped_topics.append({**topic, **mapping})
    return {
        "topic_count": len(mapped_topics),
        "domain_counts": domain_counts,
        "topics": mapped_topics,
    }


def _count_topics(topics: list[dict], needle: str) -> int:
    """Count installed help topics matching one capability keyword."""
    return sum(1 for topic in topics if needle.casefold() in f"{topic['key']} {topic['target']}".casefold())


def _map_help_topic(topic: dict) -> dict:
    """Map one help topic to an Agent domain and related tool names."""
    haystack = f"{topic['key']} {topic['target']}".casefold()
    for rule in HELP_TOPIC_DOMAIN_RULES:
        if any(needle.casefold() in haystack for needle in rule["needles"]):
            return {
                "domain": rule["domain"],
                "agent_tools": rule["agent_tools"],
                "evidence_status": "mapped_by_help_link_text",
            }
    return {
        "domain": "unmapped",
        "agent_tools": [],
        "evidence_status": "needs_manual_mapping",
    }
