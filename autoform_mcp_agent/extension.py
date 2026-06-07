"""这个文件用证据说明 AutoForm 内部扩展边界。它回答“当前能安全自动化到哪里，哪里还不能承诺”。

This file explains AutoForm internal extension boundaries with evidence. It answers what can be safely automated now and what should not be promised yet.

它会读取可执行程序、QuickLink 脚本、帮助主题和模板标记，返回一份有依据的边界说明。

It reads executables, QuickLink scripts, help topics, and template markers, then returns a grounded boundary summary.
"""

from __future__ import annotations

from pathlib import Path

from .commands import list_command_specs
from .inventory import list_help_topics
from .paths import AutoFormInstallation, get_default_installation
from .quicklink import quicklink_bridge_status
from .report import report_inventory


def internal_extension_boundary(
    *,
    workspace: str | Path | None = None,
    install: AutoFormInstallation | None = None,
) -> dict:
    """Return confirmed and unconfirmed AutoForm extension paths."""

    install = install or get_default_installation()
    workspace_path = Path(workspace or Path.cwd()).resolve()
    report = report_inventory(
        install=install,
        bin_dir=install.bin_dir,
        templates_root=install.autoform_program_data / "templates",
        help_links_file=install.help_links_file,
    )
    commands = list_command_specs(install=install)
    help_topics = list_help_topics(query="script") + list_help_topics(query="export")
    confirmed = [
        {
            "capability": "external_cli",
            "evidence": "AutoForm bin executables and command wrappers",
            "entries": [item["key"] for item in commands if item.get("exists")],
        },
        {
            "capability": "quicklink_export_script",
            "evidence": "ProgramData scripts directory and QuickLink bridge status",
            "status": quicklink_bridge_status(workspace_path, install=install),
        },
        {
            "capability": "report_templates",
            "evidence": "AFReportMSOffice binaries and report templates",
            "template_count": len(report.get("templates", [])),
        },
    ]
    return {
        "schema_version": "1.0",
        "install": install.as_dict(),
        "workspace": str(workspace_path),
        "confirmed_extension_paths": confirmed,
        "help_topic_count": len(help_topics),
        "help_topics": help_topics[:20],
        "generic_internal_script_host": {
            "confirmed": False,
            "evidence": "No local evidence has been found for a stable AutoForm-internal generic Python script host comparable to Abaqus execute_script.",
            "v1_boundary": "Use external CLI tools, QuickLink bridge exports and report templates as the supported 1.0 automation boundary.",
        },
    }
