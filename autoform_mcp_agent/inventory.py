"""这个文件做只读清点：查看 AutoForm 安装、工程文件、可执行程序和帮助主题。它只读已有文件。

This file performs read-only inventory work: it inspects AutoForm installations, project files, executables, and help topics from files already on disk.

这些函数适合暴露给 MCP，因为它们不会启动 AutoForm，也不会写入 ProgramData。

These functions are safe to expose through MCP because they do not launch AutoForm or write into ProgramData.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from .paths import AutoFormInstallation, get_default_installation


KNOWN_EXECUTABLE_PURPOSES = {
    "AFSplash.exe": "Start AutoForm product UI through splash entry",
    "AFFormingUI.exe": "Open AutoForm Forming UI and .afd projects",
    "AFFormingJob.exe": "Run forming jobs through command line arguments",
    "AFQueueClient.exe": "Interact with AutoForm queue client commands",
    "AFQueueServer.exe": "Run AutoForm queue server process",
    "AFMat2Mtb.exe": "Material conversion entry; parameters still need evidence",
    "AFReportMSOffice.exe": "Office report entry; parameters still need evidence",
}
PRINTABLE_ASCII_RE = re.compile(rb"[ -~]{4,}")
PRINTABLE_UTF16LE_RE = re.compile(rb"(?<![ -~])(?:[ -~]\x00){4,}")
KNOWN_AFD_FIELDS = {
    "Project Name",
    "Process Design Iteration",
    "Created",
    "Last Modified",
    "Contact Information",
    "Order Data",
    "OEM",
    "Vehicle Program",
    "Requested Material",
    "Requested Blank Thickness",
    "Comment",
    "Additional Information",
    "Status",
    "Operation",
    "Feature Name",
    "Operation Name",
    "Material Name",
    "Material String",
    "Material Thickness",
    "Material Type",
    "Materials String",
    "DieFace usage",
    "Formcheck usage",
    "Hemming usage",
    "Hotforming usage",
    "MultiBlank usage",
    "PhaseChange usage",
    "Reporting usage",
    "TriboForm usage",
}


def list_example_projects(
    install: AutoFormInstallation | None = None,
    test_dir: Path | None = None,
) -> list[dict]:
    """Return .afd examples shipped under AutoForm ProgramData."""

    root = test_dir.resolve() if test_dir is not None else (install or get_default_installation()).test_dir
    if not root.exists():
        return []
    return [_file_summary(path) for path in sorted(root.glob("*.afd"))]


def inspect_afd(afd_path: Path) -> dict:
    """Return basic file facts for an .afd project without parsing internals."""

    path = afd_path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_file():
        raise IsADirectoryError(path)
    return {
        **_file_summary(path),
        "suffix": path.suffix.lower(),
        "is_zipfile": zipfile.is_zipfile(path),
        "direct_internal_parser": None,
        "note": "Only file-level metadata is confirmed by this tool.",
    }


def get_afd_readable_index(
    afd_path: Path,
    query: str | None = None,
    min_length: int = 4,
    limit: int = 200,
) -> dict:
    """Extract printable fragments from an .afd file for evidence discovery."""

    path = afd_path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_file():
        raise IsADirectoryError(path)
    data = path.read_bytes()
    strings = _extract_printable_strings(data, min_length=min_length)
    needle = query.casefold() if query else None
    filtered = [item for item in strings if needle in item.casefold()] if needle else strings
    return {
        **_file_summary(path),
        "suffix": path.suffix.lower(),
        "min_length": min_length,
        "query": query,
        "total_string_count": len(strings),
        "matched_string_count": len(filtered),
        "known_fields": _collect_known_afd_fields(strings),
        "fragments": filtered[:limit],
    }


def get_afd_project_summary(afd_path: Path) -> dict:
    """Return a compact candidate summary extracted from readable .afd fragments."""

    index = get_afd_readable_index(afd_path, limit=0)
    fields = index["known_fields"]
    material_string = _first_field_value(fields, "Material String") or _first_field_value(fields, "Materials String")
    material_name = _first_field_value(fields, "Material Name") or _material_name_from_string(material_string)
    material_thickness = _first_field_value(fields, "Material Thickness") or _material_thickness_from_string(material_string)
    return {
        "path": index["path"],
        "name": index["name"],
        "size_bytes": index["size_bytes"],
        "source": "afd_readable_index_candidate",
        "project_name": _first_field_value(fields, "Project Name"),
        "created": _first_field_value(fields, "Created"),
        "last_modified_field": _first_field_value(fields, "Last Modified"),
        "comment": _first_field_value(fields, "Comment"),
        "feature_name": _first_field_value(fields, "Feature Name"),
        "operation_name": _first_field_value(fields, "Operation Name"),
        "material": {
            "name": material_name,
            "string": material_string,
            "thickness": material_thickness,
            "type": _first_field_value(fields, "Material Type"),
        },
        "usage": {
            "die_face": _first_field_value(fields, "DieFace usage"),
            "formcheck": _first_field_value(fields, "Formcheck usage"),
            "hemming": _first_field_value(fields, "Hemming usage"),
            "hotforming": _first_field_value(fields, "Hotforming usage"),
            "multiblank": _first_field_value(fields, "MultiBlank usage"),
            "phase_change": _first_field_value(fields, "PhaseChange usage"),
            "reporting": _first_field_value(fields, "Reporting usage"),
            "triboform": _first_field_value(fields, "TriboForm usage"),
        },
        "total_string_count": index["total_string_count"],
        "candidate_field_count": len(fields),
        "note": "Values are candidates extracted from printable .afd fragments and should be cross-checked with QuickLink or official exports before simulation decisions.",
    }


def list_executables(
    install: AutoFormInstallation | None = None,
    bin_dir: Path | None = None,
) -> list[dict]:
    """Return executable and command entries from AutoForm's bin directory."""

    root = bin_dir.resolve() if bin_dir is not None else (install or get_default_installation()).bin_dir
    if not root.exists():
        return []
    entries: list[dict] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.suffix.lower() not in {".exe", ".cmd"}:
            continue
        summary = _file_summary(path)
        summary["extension"] = path.suffix.lower()
        summary["known_purpose"] = KNOWN_EXECUTABLE_PURPOSES.get(path.name)
        entries.append(summary)
    return entries


def list_help_topics(
    install: AutoFormInstallation | None = None,
    query: str | None = None,
    help_links_file: Path | None = None,
) -> list[dict]:
    """Return helpLinks.cfg topic mappings, optionally filtered by text."""

    source = help_links_file.resolve() if help_links_file is not None else (install or get_default_installation()).help_links_file
    if not source.exists():
        return []

    topics: list[dict] = []
    needle = query.casefold() if query else None
    for line_no, raw_line in enumerate(source.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("@") or stripped.startswith("$"):
            continue
        parts = stripped.split()
        if len(parts) < 2 or not parts[-1].startswith("/"):
            continue
        key = " ".join(parts[:-1])
        target = parts[-1]
        haystack = f"{key} {target}".casefold()
        if needle and needle not in haystack:
            continue
        topics.append(
            {
                "source": str(source),
                "line": line_no,
                "key": key,
                "target": target,
            }
        )
    return topics


def _file_summary(path: Path) -> dict:
    """Return common file metadata in a JSON-friendly shape."""
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
    }


def _extract_printable_strings(data: bytes, min_length: int) -> list[str]:
    """Extract ASCII and UTF-16LE printable strings from binary project data."""
    seen = set()
    strings: list[str] = []
    for regex, encoding in ((PRINTABLE_ASCII_RE, "ascii"), (PRINTABLE_UTF16LE_RE, "utf-16le")):
        for match in regex.finditer(data):
            raw = match.group(0)
            if encoding == "utf-16le" and len(raw) % 2:
                continue
            text = raw.decode(encoding, errors="ignore").strip()
            if len(text) < min_length or text in seen:
                continue
            seen.add(text)
            strings.append(text)
    return strings


def _collect_known_afd_fields(strings: list[str]) -> dict:
    """Collect candidate values that follow known readable `.afd` labels."""
    fields = {}
    for index, text in enumerate(strings):
        canonical = _match_known_afd_field(text)
        if not canonical:
            continue
        values = []
        for candidate in strings[index + 1 : index + 5]:
            if _match_known_afd_field(candidate):
                break
            if candidate.startswith("IDX_"):
                continue
            values.append(candidate)
        fields.setdefault(canonical, values[:3])
    return fields


def _match_known_afd_field(text: str) -> str | None:
    """Return the canonical field name if text looks like a known `.afd` label."""
    lowered = text.casefold()
    for field in sorted(KNOWN_AFD_FIELDS, key=len, reverse=True):
        field_lower = field.casefold()
        if lowered == field_lower:
            return field
        suffix = text[len(field) :]
        suffix_is_artifact = suffix and not any(char.isalpha() for char in suffix)
        suffix_is_comment_artifact = field == "Comment" and len(suffix) <= 2
        if lowered.startswith(field_lower) and len(text) <= len(field) + 3 and (suffix_is_artifact or suffix_is_comment_artifact):
            return field
    return None


def _first_field_value(fields: dict, field: str) -> str | None:
    """Return the first usable candidate value for one field."""
    values = fields.get(field, [])
    for value in values:
        stripped = value.strip()
        cleaned = _clean_afd_field_value(field, stripped)
        if cleaned and len(cleaned) < 200:
            return cleaned
    return None


def _clean_afd_field_value(field: str, value: str) -> str | None:
    """Filter noisy binary fragments from candidate `.afd` field values."""
    if not value or value in {"IHDR", "pHYs", "IDATx^", "IEND"}:
        return None
    if field == "Last Modified" and (value.startswith("Contact Information") or value in {"Name", "Department", "Company"}):
        return None
    if field.endswith("usage"):
        lowered = value.casefold()
        if lowered.startswith("not used"):
            return "Not used"
        if lowered.startswith("used"):
            return "Used"
    return value


def _material_name_from_string(material_string: str | None) -> str | None:
    """Extract a material name candidate from a readable material summary."""
    if not material_string:
        return None
    match = re.search(r"\b(?:Constant\s+)?([^/\s]+)/(?:\d|\.)", material_string)
    return match.group(1) if match else None


def _material_thickness_from_string(material_string: str | None) -> str | None:
    """Extract a thickness candidate from a readable material summary."""
    if not material_string:
        return None
    match = re.search(r"/([0-9.]+)\s*mm", material_string, flags=re.IGNORECASE)
    return match.group(1) if match else None
