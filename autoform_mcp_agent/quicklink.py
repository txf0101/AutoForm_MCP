"""这个文件处理 QuickLink 桥接安装、导出压缩包索引和 XML 摘要。QuickLink 是当前最结构化的工程数据来源之一。

This file handles QuickLink bridge installation, export archive indexing, and XML summaries. QuickLink is one of the most structured evidence sources for project data.

公开函数可以接收文件、压缩包、manifest 或导出目录，并返回稳定字典，方便测试、CLI 和 MCP 共用。

Public functions accept files, archives, manifests, or export directories and return stable dictionaries for tests, CLI output, and MCP responses.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .paths import AutoFormInstallation, get_default_installation

GEOMETRY_EXTENSIONS = {".af", ".igs", ".iges", ".stp", ".step", ".stl"}
QUICKLINK_STANDARD_EXTENSIONS = {".xml", ".xsd", ".xlsm", ".afr", ".zip"}


def bridge_script_text(workspace: Path, python_executable: str | None = None) -> str:
    """Build the .cmd file that AutoForm can call from QuickLink Export."""

    python_executable = python_executable or sys.executable
    workspace = workspace.resolve()
    lines = [
        "@echo off",
        # AutoForm projects live under a Chinese path in this workspace. Setting
        # UTF-8 avoids cmd.exe mangling the path before Python receives it.
        "chcp 65001 >nul",
        "set \"QUICKLINK_ARCHIVE=%~1\"",
        # AutoForm runs scripts from its own scripts directory, so the project
        # root is added explicitly for `python -m autoform_mcp_agent...`.
        f"set \"PYTHONPATH={workspace};%PYTHONPATH%\"",
        f'"{python_executable}" -m autoform_mcp_agent.quicklink_bridge "%QUICKLINK_ARCHIVE%" --workspace "{workspace}"',
        "exit /b %ERRORLEVEL%",
        "",
    ]
    return "\n".join(lines)


def install_quicklink_bridge(
    workspace: Path,
    install: AutoFormInstallation | None = None,
    script_name: str = "CodexAgentBridge.cmd",
    dry_run: bool = False,
) -> Path:
    """Install or preview the QuickLink bridge script path."""

    install = install or get_default_installation()
    destination = install.scripts_dir / script_name
    if not dry_run:
        install.scripts_dir.mkdir(parents=True, exist_ok=True)
        destination.write_text(bridge_script_text(workspace), encoding="utf-8")
    return destination


def quicklink_bridge_status(
    workspace: Path,
    install: AutoFormInstallation | None = None,
    script_name: str = "CodexAgentBridge.cmd",
    python_executable: str | None = None,
) -> dict:
    """Return installed QuickLink bridge status without modifying files."""

    install = install or get_default_installation()
    destination = install.scripts_dir / script_name
    expected = bridge_script_text(workspace, python_executable=python_executable)
    actual = destination.read_text(encoding="utf-8", errors="replace") if destination.exists() else None
    return {
        "script_name": script_name,
        "path": str(destination),
        "exists": destination.exists(),
        "matches_expected": _normalize_script(actual) == _normalize_script(expected) if actual is not None else False,
        "expected_line_count": len(expected.splitlines()),
        "actual_line_count": len(actual.splitlines()) if actual is not None else None,
    }


def list_quicklink_exports(workspace: Path) -> list[dict]:
    """Return QuickLink exports collected by the bridge script."""

    root = _quicklink_data_dir(workspace)
    if not root.exists():
        return []

    exports: list[dict] = []
    for item in sorted(root.iterdir(), key=lambda path: path.name, reverse=True):
        if not item.is_dir():
            continue
        manifest_path = item / "manifest.json"
        manifest = _read_manifest(manifest_path)
        target = _target_from_manifest(manifest)
        archive = target if target is not None and target.suffix.lower() == ".zip" else None
        if archive is None:
            archives = sorted(item.glob("*.zip"))
            archive = archives[0] if archives else None
        exports.append(
            {
                "name": item.name,
                "directory": str(item),
                "manifest_path": str(manifest_path) if manifest_path.exists() else None,
                "target_path": str(target) if target is not None else None,
                "target_exists": target.exists() if target is not None else False,
                "archive_path": str(archive) if archive is not None else None,
                "archive_exists": archive.exists() if archive is not None else False,
                "collected_at": manifest.get("collected_at"),
                "size_bytes": manifest.get("size_bytes"),
            }
        )
    return exports


def latest_quicklink_export(workspace: Path) -> dict | None:
    """Return the newest collected QuickLink export, if one exists."""

    exports = list_quicklink_exports(workspace)
    return exports[0] if exports else None


def parse_quicklink_xml(source: Path) -> dict:
    """Parse a QuickLink XML file, zip archive, export directory, or manifest."""

    resolved_source = source.resolve()
    xml_text, xml_name, members, archive_path = _read_quicklink_xml(resolved_source)
    root = ET.fromstring(xml_text)
    title = _first_child(root, "Title")
    project_data = _project_data(root)
    blank = _blank_info(root)
    process_items = _section_summary(root, "ProcessItems")
    process_definition = _section_summary(root, "ProcessDefinition")
    process_plan = _section_summary(root, "ProcessPlan")
    die_face = _section_summary(root, "DieFace")
    evaluation = _section_summary(root, "Evaluation")
    xml_file_refs = _xml_file_references(root)
    geometry_members = [
        name for name in members if Path(name).suffix.lower() in GEOMETRY_EXTENSIONS
    ]

    return {
        "source": str(resolved_source),
        "archive_path": str(archive_path) if archive_path is not None else None,
        "xml_name": xml_name,
        "quicklink_namespace": _namespace(root.tag),
        "title": dict(title.attrib) if title is not None else {},
        "project_data": project_data,
        "blank": blank,
        "process_items": process_items,
        "process_definition": process_definition,
        "process_plan": process_plan,
        "die_face": die_face,
        "evaluation": evaluation,
        "file_references": xml_file_refs,
        "geometry_files": sorted(set(xml_file_refs + geometry_members)),
        "archive_members": members,
    }


def quicklink_schema(source: Path) -> dict:
    """Return a stable V1 schema view over a QuickLink export.

    `parse_quicklink_xml()` intentionally keeps a close shape to the source XML.
    This function provides the public 1.0 contract used by baselines, reports and
    downstream tools: section counts, named items, project data and geometry are
    normalized into predictable keys.
    """

    parsed = parse_quicklink_xml(source)
    return {
        "schema_version": "1.0",
        "source": parsed["source"],
        "archive_path": parsed["archive_path"],
        "quicklink_namespace": parsed["quicklink_namespace"],
        "title": parsed["title"],
        "project_data": _project_data_map(parsed["project_data"]),
        "blank": parsed.get("blank") or {},
        "sections": {
            "process_items": _section_schema(parsed["process_items"]),
            "process_definition": _section_schema(parsed["process_definition"]),
            "process_plan": _section_schema(parsed["process_plan"]),
            "die_face": _section_schema(parsed["die_face"]),
            "evaluation": _section_schema(parsed["evaluation"]),
        },
        "geometry_files": parsed["geometry_files"],
        "archive_member_count": len(parsed["archive_members"]),
    }


def get_project_data(source: Path) -> list[dict]:
    """Return the parsed `ProjectData` entries from any supported source."""
    return parse_quicklink_xml(source)["project_data"]


def get_blank_info(source: Path) -> dict | None:
    """Return the parsed `Blank` section from any supported source."""
    return parse_quicklink_xml(source)["blank"]


def list_exported_geometry(source: Path) -> list[str]:
    """Return geometry file references declared in a QuickLink export."""
    return parse_quicklink_xml(source)["geometry_files"]


def quicklink_archive_inventory(source: Path) -> dict:
    """Return member-level facts for a QuickLink XML source or archive."""

    resolved_source = source.resolve()
    xml_text, xml_name, members, archive_path = _read_quicklink_xml(resolved_source)
    root = ET.fromstring(xml_text)
    if archive_path is None:
        size_bytes = resolved_source.stat().st_size if resolved_source.exists() and resolved_source.is_file() else None
        items = [
            {
                "name": xml_name,
                "category": "quicklink_xml" if _local_name(root.tag) == "QuickLink" else "xml",
                "size_bytes": size_bytes,
                "compressed_size": None,
                "crc": None,
            }
        ]
    else:
        items = []
        with ZipFile(archive_path) as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename.casefold()):
                items.append(
                    {
                        "name": info.filename,
                        "category": _archive_member_category(info.filename, xml_name),
                        "size_bytes": info.file_size,
                        "compressed_size": info.compress_size,
                        "crc": info.CRC,
                    }
                )
    counts: dict[str, int] = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {
        "source": str(resolved_source),
        "archive_path": str(archive_path) if archive_path is not None else None,
        "xml_name": xml_name,
        "quicklink_namespace": _namespace(root.tag),
        "member_count": len(items),
        "category_counts": counts,
        "members": items,
        "raw_member_names": members,
    }


def compare_quicklink_exports(left: Path, right: Path) -> dict:
    """Compare two QuickLink exports at a stable summary level."""

    left_parsed = parse_quicklink_xml(left)
    right_parsed = parse_quicklink_xml(right)
    return {
        "left_source": left_parsed["source"],
        "right_source": right_parsed["source"],
        "title_differences": _dict_differences(left_parsed["title"], right_parsed["title"]),
        "project_data_differences": _project_data_differences(
            left_parsed["project_data"],
            right_parsed["project_data"],
        ),
        "blank_differences": _dict_differences(
            left_parsed.get("blank") or {},
            right_parsed.get("blank") or {},
        ),
        "geometry_added": sorted(set(right_parsed["geometry_files"]) - set(left_parsed["geometry_files"])),
        "geometry_removed": sorted(set(left_parsed["geometry_files"]) - set(right_parsed["geometry_files"])),
        "section_counts": {
            "left": _section_count_snapshot(left_parsed),
            "right": _section_count_snapshot(right_parsed),
        },
    }


def get_quicklink_section(source: Path, section_name: str, value_limit: int = 100) -> dict:
    """Return a deeper summary for one named QuickLink XML section."""

    resolved_source = source.resolve()
    xml_text, xml_name, members, archive_path = _read_quicklink_xml(resolved_source)
    root = ET.fromstring(xml_text)
    section = _first_child_casefold(root, section_name)
    if section is None:
        return {
            "source": str(resolved_source),
            "archive_path": str(archive_path) if archive_path is not None else None,
            "xml_name": xml_name,
            "section": section_name,
            "present": False,
            "children": [],
            "counts": {},
            "named_items": [],
            "values": [],
            "file_references": [],
            "archive_members": members,
        }
    return {
        "source": str(resolved_source),
        "archive_path": str(archive_path) if archive_path is not None else None,
        "xml_name": xml_name,
        "section": _local_name(section.tag),
        "present": True,
        "attributes": dict(section.attrib),
        **_deep_section_summary(section, value_limit=value_limit),
        "archive_members": members,
    }


def get_process_plan(source: Path, value_limit: int = 100) -> dict:
    """Return a deep summary of the `ProcessPlan` QuickLink section."""
    return get_quicklink_section(source, "ProcessPlan", value_limit=value_limit)


def get_evaluation(source: Path, value_limit: int = 100) -> dict:
    """Return a deep summary of the `Evaluation` QuickLink section."""
    return get_quicklink_section(source, "Evaluation", value_limit=value_limit)


def get_die_face(source: Path, value_limit: int = 100) -> dict:
    """Return a deep summary of the `DieFace` QuickLink section."""
    return get_quicklink_section(source, "DieFace", value_limit=value_limit)


def list_quicklink_standards(
    install: AutoFormInstallation | None = None,
    templates_dir: Path | None = None,
) -> list[dict]:
    """Return QuickLink standards and templates shipped with AutoForm."""

    root = (
        templates_dir.resolve()
        if templates_dir is not None
        else (install or get_default_installation()).quicklink_templates_dir.resolve()
    )
    if not root.exists():
        return []
    standards: list[dict] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.suffix.lower() not in QUICKLINK_STANDARD_EXTENSIONS:
            continue
        stat = path.stat()
        standards.append(
            {
                "name": path.name,
                "path": str(path),
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "xml_valid": _xml_is_valid(path) if path.suffix.lower() in {".xml", ".xsd"} else None,
            }
        )
    return standards


def validate_quicklink_standard(path: Path) -> dict:
    """Parse one QuickLink standard XML or XSD file and report root metadata."""

    source = path.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in {".xml", ".xsd"}:
        raise ValueError(f"Only .xml and .xsd QuickLink standards can be XML-validated: {source}")
    try:
        root = ET.parse(source).getroot()
    except ET.ParseError as exc:
        return {
            "path": str(source),
            "xml_valid": False,
            "error": str(exc),
        }
    return {
        "path": str(source),
        "xml_valid": True,
        "root_tag": _local_name(root.tag),
        "namespace": _namespace(root.tag),
        "child_count": len(list(root)),
    }


def _quicklink_data_dir(workspace: Path) -> Path:
    """Return the workspace directory where bridge exports are collected."""
    return workspace.resolve() / "autoform_mcp_agent_data" / "quicklink"


def _read_manifest(path: Path) -> dict:
    """Read a bridge-generated manifest and fail clearly if it is missing."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _target_from_manifest(manifest: dict) -> Path | None:
    """Resolve the archive path recorded in a QuickLink manifest."""
    archive = manifest.get("target_archive")
    return Path(archive) if archive else None


def _read_quicklink_xml(source: Path) -> tuple[str, str, list[str], Path | None]:
    """Load QuickLink XML text from directory, manifest, zip or XML file."""
    if source.is_dir():
        manifest_target = _target_from_manifest(_read_manifest(source / "manifest.json"))
        if manifest_target is not None and manifest_target.exists() and manifest_target.suffix.lower() in {".zip", ".xml"}:
            return _read_quicklink_xml(manifest_target)
        archives = sorted(source.glob("*.zip"))
        if archives:
            return _read_quicklink_xml(archives[0])
        xml_files = sorted(source.glob("*.xml"))
        if xml_files:
            return _read_quicklink_xml(xml_files[0])
        raise FileNotFoundError(f"No QuickLink XML or archive found in {source}")

    if source.name.lower() == "manifest.json":
        manifest_target = _target_from_manifest(_read_manifest(source))
        if manifest_target is None:
            raise FileNotFoundError(f"No target_archive in {source}")
        if manifest_target.exists() and manifest_target.suffix.lower() in {".zip", ".xml"}:
            return _read_quicklink_xml(manifest_target)
        return _read_quicklink_xml(source.parent)

    if source.suffix.lower() == ".zip":
        with ZipFile(source) as archive:
            members = archive.namelist()
            xml_candidates = [name for name in members if name.lower().endswith(".xml")]
            for name in xml_candidates:
                text = archive.read(name).decode("utf-8-sig")
                try:
                    root = ET.fromstring(text)
                except ET.ParseError:
                    continue
                if _local_name(root.tag) == "QuickLink":
                    return text, name, members, source
            if xml_candidates:
                name = xml_candidates[0]
                return archive.read(name).decode("utf-8-sig"), name, members, source
        raise FileNotFoundError(f"No XML file found in {source}")

    if source.suffix.lower() == ".xml":
        return source.read_text(encoding="utf-8-sig"), source.name, [], None

    raise ValueError(f"Unsupported QuickLink source: {source}")


def _project_data(root: ET.Element) -> list[dict]:
    """Convert the `ProjectData` XML section into a list of values."""
    section = _first_child(root, "ProjectData")
    if section is None:
        return []
    values: list[dict] = []
    for item in _children(section, "ProjectValue"):
        values.append(
            {
                "group": item.attrib.get("Group"),
                "key": item.attrib.get("Key"),
                "name": item.attrib.get("Name"),
                "value": item.attrib.get("value", ""),
            }
        )
    return values


def _blank_info(root: ET.Element) -> dict | None:
    """Extract basic blank geometry and material references from XML."""
    blank = _first_child(root, "Blank")
    if blank is None:
        return None
    children = {}
    for child in list(blank):
        children[_local_name(child.tag)] = {
            "value": (child.text or "").strip(),
            **child.attrib,
        }
    return {
        "attributes": dict(blank.attrib),
        "values": children,
    }


def _section_summary(root: ET.Element, name: str) -> dict:
    """Return a shallow section summary used in the top-level parse output."""
    section = _first_child(root, name)
    if section is None:
        return {"present": False, "children": [], "counts": {}}
    children = [_local_name(child.tag) for child in list(section)]
    counts: dict[str, int] = {}
    for child_name in children:
        counts[child_name] = counts.get(child_name, 0) + 1
    named_items: list[dict] = []
    for child in section.iter():
        item_name = child.attrib.get("Name")
        if item_name:
            named_items.append({"type": _local_name(child.tag), "name": item_name})
    return {
        "present": True,
        "children": children,
        "counts": counts,
        "named_items": named_items,
    }


def _xml_file_references(root: ET.Element) -> list[str]:
    """Collect likely file references from XML attributes and leaf text."""
    refs: list[str] = []
    for item in root.iter():
        if _local_name(item.tag) != "Name":
            continue
        text = (item.text or "").strip()
        if Path(text).suffix.lower() in GEOMETRY_EXTENSIONS:
            refs.append(text)
    return refs


def _children(parent: ET.Element, name: str) -> list[ET.Element]:
    """Return direct children whose local XML name matches exactly."""
    return [child for child in list(parent) if _local_name(child.tag) == name]


def _first_child(parent: ET.Element, name: str) -> ET.Element | None:
    """Return the first direct child with the requested local name."""
    matches = _children(parent, name)
    return matches[0] if matches else None


def _first_child_casefold(parent: ET.Element, name: str) -> ET.Element | None:
    """Return the first direct child using case-insensitive matching."""
    needle = name.casefold()
    for child in list(parent):
        if _local_name(child.tag).casefold() == needle:
            return child
    return None


def _deep_section_summary(section: ET.Element, value_limit: int = 100) -> dict:
    """Summarize nested XML without exposing raw, bulky QuickLink XML."""
    children = [_local_name(child.tag) for child in list(section)]
    counts: dict[str, int] = {}
    for child_name in children:
        counts[child_name] = counts.get(child_name, 0) + 1
    named_items: list[dict] = []
    for child in section.iter():
        item_name = child.attrib.get("Name")
        if item_name:
            named_items.append(
                {
                    "type": _local_name(child.tag),
                    "name": item_name,
                    "attributes": dict(child.attrib),
                }
            )
    return {
        "children": children,
        "counts": counts,
        "named_items": named_items[:value_limit],
        "values": _leaf_values(section, value_limit=value_limit),
        "file_references": _xml_file_references(section),
    }


def _leaf_values(section: ET.Element, value_limit: int = 100) -> list[dict]:
    """Collect representative leaf node values for developer inspection."""
    values: list[dict] = []

    def visit(node: ET.Element, parent_path: str) -> None:
        """Depth-first traversal that stops after the requested value limit."""
        if len(values) >= value_limit:
            return
        name = _local_name(node.tag)
        current_path = f"{parent_path}/{name}" if parent_path else name
        children = list(node)
        text = (node.text or "").strip()
        if not children and (text or node.attrib):
            values.append(
                {
                    "path": current_path,
                    "value": text,
                    "attributes": dict(node.attrib),
                }
            )
        for child in children:
            visit(child, current_path)

    for child in list(section):
        visit(child, _local_name(section.tag))
    return values


def _local_name(tag: str) -> str:
    """Strip an XML namespace from a tag name."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _namespace(tag: str) -> str | None:
    """Return the XML namespace URI from a namespaced tag."""
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


def _xml_is_valid(path: Path) -> bool:
    """Return whether a standard XML/XSD file can be parsed."""
    try:
        ET.parse(path)
    except ET.ParseError:
        return False
    return True


def _normalize_script(text: str | None) -> str | None:
    """Normalize generated `.cmd` text before bridge status comparison."""
    if text is None:
        return None
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def _archive_member_category(name: str, quicklink_xml_name: str) -> str:
    """Classify a zip member as XML, geometry or auxiliary content."""
    suffix = Path(name).suffix.lower()
    if name == quicklink_xml_name:
        return "quicklink_xml"
    if suffix == ".xml":
        return "xml"
    if suffix in GEOMETRY_EXTENSIONS:
        return "geometry"
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        return "image"
    if suffix in {".xls", ".xlsx", ".xlsm", ".doc", ".docx", ".ppt", ".pptx", ".pdf"}:
        return "office"
    return "other"


def _dict_differences(left: dict, right: dict) -> dict:
    """Return key-level differences between two flat dictionaries."""
    differences = {}
    keys = sorted(set(left) | set(right))
    for key in keys:
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value != right_value:
            differences[key] = {"left": left_value, "right": right_value}
    return differences


def _project_data_differences(left: list[dict], right: list[dict]) -> dict:
    """Compare ProjectData entries by stable group/key/name identity."""
    left_values = {_project_data_key(item): item.get("value") for item in left}
    right_values = {_project_data_key(item): item.get("value") for item in right}
    return _dict_differences(left_values, right_values)


def _project_data_key(item: dict) -> str:
    """Build a stable identity key for one ProjectData item."""
    return "|".join(str(item.get(key) or "") for key in ("group", "key", "name"))


def _section_count_snapshot(parsed: dict) -> dict:
    """Return section child-counts for QuickLink export comparison."""
    sections = {}
    for name in ("process_items", "process_definition", "process_plan", "die_face", "evaluation"):
        section = parsed.get(name) or {}
        sections[name] = dict(section.get("counts") or {})
    return sections


def _project_data_map(project_data: list[dict]) -> dict:
    """Normalize ProjectData rows by key while preserving display names."""

    normalized = {}
    for item in project_data:
        key = item.get("key") or item.get("name")
        if not key:
            continue
        normalized[key] = {
            "group": item.get("group"),
            "name": item.get("name"),
            "value": item.get("value"),
        }
    return normalized


def _section_schema(section: dict) -> dict:
    """Return one compact section schema with stable default fields."""

    return {
        "present": bool(section.get("present")),
        "children": section.get("children", []),
        "counts": section.get("counts", {}),
        "named_items": section.get("named_items", []),
    }
