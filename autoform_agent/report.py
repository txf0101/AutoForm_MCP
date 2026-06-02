"""这个文件读取报告、Office 模板和 GUI 报告事件证据。它先找证据，不急着生成正式报告。

This file reads report, Office-template, and GUI report-event evidence. It looks for evidence first instead of rushing into report generation.

这些 helper 会识别已安装的报告程序、模板和日志标记，为以后把确认过的行为做成安全工具打基础。

These helpers identify installed report binaries, templates, and log markers so later work can turn confirmed behavior into safe tools.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from .inventory import list_help_topics
from .paths import AutoFormInstallation, get_default_installation


REPORT_BINARIES = [
    "AFReportMSOffice.exe",
    "Application_ReportManager.dll",
    "Presentation_MSOffice.dll",
    "Presentation_ExcelReport.dll",
    "Presentation_PowerPointReport.dll",
    "Presentation_PostprocessingGenerator.dll",
    "AFFormingPostSolve.exe",
    "Business_QuickLinkExport.dll",
    "Business_ReportingInterface.dll",
    "Business_ReportModuleConnection.dll",
]
REPORT_TEMPLATE_SUFFIXES = {".afr", ".xlsx", ".pptx", ".xlsm"}
OFFICE_PROXY_MARKERS = [
    "OfficeProxy.Program",
    "OfficeProxyCommunicatorClient",
    "OfficeProxyCommunicatorServer",
    "NamedPipeClientStream",
    "GetCommandLineArgs",
    "Excel_loadTemplate",
    "Excel_writeViews",
    "Excel_writeGeneratedReportViewInExcelFile",
    "Excel_writeGeneratedReportViewInExcelFile3D",
    "Excel_writeGeneratedReportViewInExcelFile2D",
    "Excel_writeGeneratedReportViewInExcelFile3D2D",
    "Excel_writeGeneratedReportViewInExcelFilePageLayout",
    "Excel_writeGeneratedReportViewInExcelFilePageLayout3D",
    "Excel_writeGeneratedReportViewInExcelFilePageLayout2D",
    "Excel_writeGeneratedReportViewInExcelFilePageLayout3D2D",
    "Excel_writeGeneratedReportViewInExcelFilePageLayout3D2DTable",
    "Excel_writeGeneratedReportViewInExcelFilePageLayout3DTable",
    "Excel_writeGeneratedReportViewInExcelFilePageLayout2DTable",
    "Excel_writeGeneratedReportViewInExcelFileTable",
    "Excel_writeGeneratedReportViewInExcelFile3DTable",
    "Excel_writeGeneratedReportViewInExcelFile2DTable",
    "PowerPoint_writeImages",
    "PowerPoint_writeGeneratedImage",
    "PowerPoint_saveAsPowerPointFile",
    "saveAsExcelFile",
    "saveAsPowerPointFile",
]
REPORT_LOG_PATTERNS = {
    "export_view": re.compile(r"ExportViewClass", re.IGNORECASE),
    "quicklink_script": re.compile(r"ExecuteScript|CodexAgentBridge|IntegrateUsingQuickLink", re.IGNORECASE),
    "report_manager": re.compile(r"ReportManager|ReportError", re.IGNORECASE),
    "result_sync": re.compile(r"SyncResultsActionButton|SyncResults", re.IGNORECASE),
    "postprocessing": re.compile(r"PostProcessingPagePresenter|PostProcessing", re.IGNORECASE),
    "office_proxy": re.compile(r"AFReportMSOffice|OfficeProxy|MSOffice", re.IGNORECASE),
}
TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
PRINTABLE_ASCII_RE = re.compile(rb"[ -~]{4,}")


def report_inventory(
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
    templates_root: Path | None = None,
    help_links_file: Path | None = None,
) -> dict:
    """Return report, Office and result-view related local evidence."""

    install = install or get_default_installation()
    selected_bin = bin_dir.resolve() if bin_dir is not None else install.bin_dir
    selected_templates = templates_root.resolve() if templates_root is not None else install.autoform_program_data / "templates"
    selected_help = help_links_file.resolve() if help_links_file is not None else install.help_links_file
    binaries = [_file_fact(selected_bin / name) for name in REPORT_BINARIES]
    marker_sources = [
        selected_bin / "AFReportMSOffice.exe",
        selected_bin / "Presentation_MSOffice.dll",
    ]
    return {
        "bin_dir": str(selected_bin),
        "templates_root": str(selected_templates),
        "help_links_file": str(selected_help),
        "binaries": binaries,
        "templates": _collect_report_templates(selected_templates),
        "help_topics": _collect_report_help_topics(selected_help),
        "office_proxy_markers": [_marker_source_info(path) for path in marker_sources],
    }


def report_log_events(log_dir: Path | None = None, limit: int = 100) -> list[dict]:
    """Parse AutoForm GUI logs for report, export and postprocessing events."""

    root = log_dir.resolve() if log_dir is not None else _default_gui_log_dir()
    if not root.exists():
        return []
    events: list[dict] = []
    for log_path in sorted(root.glob("log_AFFormingUI_*.txt"), key=lambda item: item.stat().st_mtime, reverse=True):
        events.extend(_parse_report_log(log_path))
    return events[:limit]


def _collect_report_templates(root: Path) -> list[dict]:
    """Collect report template files under the AutoForm templates tree."""
    if not root.exists():
        return []
    templates = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file() or path.suffix.lower() not in REPORT_TEMPLATE_SUFFIXES:
            continue
        templates.append(_template_fact(path, root))
    return templates


def _collect_report_help_topics(help_links_file: Path) -> list[dict]:
    """Collect help topics related to reports, postprocessing and images."""
    queries = ["report", "ExportViewClass", "evaluation-stage", "postprocessing", "image"]
    seen = set()
    topics = []
    for query in queries:
        for topic in list_help_topics(query=query, help_links_file=help_links_file):
            key = (topic["line"], topic["key"], topic["target"])
            if key in seen:
                continue
            seen.add(key)
            topics.append(topic)
    return topics


def _template_fact(path: Path, root: Path) -> dict:
    """Return file facts and format-specific markers for one template."""
    fact = {
        **_file_fact(path),
        "relative_path": str(path.relative_to(root)),
        "is_zipfile": zipfile.is_zipfile(path),
        "kind": path.suffix.lower().lstrip("."),
    }
    if zipfile.is_zipfile(path):
        fact.update(_zip_template_fact(path))
    else:
        fact["header_ascii"] = path.read_bytes()[:32].decode("ascii", errors="replace").rstrip("\x00")
    return fact


def _zip_template_fact(path: Path) -> dict:
    """Inspect zipped Office templates for custom XML mapping markers."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        custom_xml = [name for name in names if name.casefold().startswith("customxml/")]
        media = [name for name in names if "/media/" in name.casefold()]
        has_vba = any(name.casefold().endswith("vbaproject.bin") for name in names)
        mapping_markers = []
        for name in custom_xml:
            if not name.casefold().endswith(".xml"):
                continue
            text = archive.read(name).decode("utf-8", errors="replace")
            for marker in ["AutoFormMappingParameters", "ViewParameters", "3DView", "RGFormingMainViewProperty"]:
                if marker in text and marker not in mapping_markers:
                    mapping_markers.append(marker)
        return {
            "zip_entry_count": len(names),
            "custom_xml_entries": custom_xml[:20],
            "media_count": len(media),
            "has_vba_project": has_vba,
            "mapping_markers": mapping_markers,
        }


def _marker_source_info(path: Path) -> dict:
    """Read binary/text marker evidence from a report-related executable."""
    fact = _file_fact(path)
    if not path.exists():
        return {**fact, "markers": []}
    data = path.read_bytes()
    strings = {
        match.group(0).decode("ascii", errors="ignore")
        for match in PRINTABLE_ASCII_RE.finditer(data)
    }
    markers = [marker for marker in OFFICE_PROXY_MARKERS if any(marker in item for item in strings)]
    return {**fact, "markers": markers}


def _parse_report_log(log_path: Path) -> list[dict]:
    """Extract report, export and result-sync events from a GUI log."""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    events = []
    current_timestamp = None
    for line_no, line in enumerate(lines, 1):
        timestamp_match = TIMESTAMP_RE.search(line)
        if timestamp_match:
            current_timestamp = timestamp_match.group("timestamp")
        categories = [name for name, pattern in REPORT_LOG_PATTERNS.items() if pattern.search(line)]
        if not categories:
            continue
        events.append(
            {
                "timestamp": current_timestamp,
                "categories": categories,
                "line": line_no,
                "log_path": str(log_path),
                "message": line.strip()[:500],
            }
        )
    return events


def _file_fact(path: Path) -> dict:
    """Return existence and size metadata for report evidence files."""
    if not path.exists():
        return {
            "name": path.name,
            "path": str(path),
            "exists": False,
            "size_bytes": None,
            "last_modified": None,
        }
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
    }


def _default_gui_log_dir() -> Path:
    """Return the default AutoForm GUI log directory for report events."""
    return Path.home() / "AppData" / "Local" / "AutoForm" / "AFplus" / "R13F" / "log"
