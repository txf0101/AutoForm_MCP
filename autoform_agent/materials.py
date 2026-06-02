"""这个文件处理材料库的查看、暂存、安装和备份。材料库通常位于共享 AutoForm ProgramData 中。

This file handles material-library inspection, staging, installation, and backup. Material libraries often live under shared AutoForm ProgramData.

因为材料操作可能写入公共目录，所以公开函数会先给出 dry-run 计划、复制摘要和文件事实，让用户确认源路径和目标路径。

Because material operations may write into shared folders, public functions first expose dry-run plans, copy summaries, and file facts so users can verify source and destination paths.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .paths import AutoFormInstallation, get_default_installation

MATERIAL_EXTENSIONS = {".mat", ".mtb"}
# CSV files may be referenced by material definitions as raw data support files.
SUPPORT_EXTENSIONS = {".csv"}
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}
ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z", ".tar", ".gz", ".tgz"}
SCALAR_MATERIAL_KEYS = {
    "YoungsModulus",
    "PoissonsRatio",
    "SpecificWeight",
    "SpecificHeatCapacity",
    "ThermalConductivity",
}
GENERATION_NEEDLES = {
    "Material Editor": "material_editor",
    "Material Generator": "material_generator",
    "AutoForm design": "autoform_design_export",
}
NUMERIC_LINE_RE = re.compile(r"^\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?:\s+[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)+\s*$")


@dataclass(frozen=True)
class MaterialFile:
    """One file selected for installation into the AutoForm materials tree."""

    path: Path
    relative_path: Path
    category: str

    def as_dict(self) -> dict:
        """Return one selected file as JSON-ready metadata."""
        return {
            "path": str(self.path),
            "relative_path": str(self.relative_path),
            "category": self.category,
        }


@dataclass(frozen=True)
class MaterialInstallResult:
    """Outcome for a material install plan or copy operation."""

    source: Path
    target_dir: Path
    copied_files: list[Path]
    planned_files: list[MaterialFile]
    dry_run: bool

    def as_dict(self) -> dict:
        """Return install results with paths converted to strings."""
        return {
            "source": str(self.source),
            "target_dir": str(self.target_dir),
            "dry_run": self.dry_run,
            "planned_count": len(self.planned_files),
            "copied_count": len(self.copied_files),
            "planned_files": [item.as_dict() for item in self.planned_files],
            "copied_files": [str(path) for path in self.copied_files],
        }


def list_material_libraries(
    install: AutoFormInstallation | None = None,
    materials_dir: Path | None = None,
) -> list[dict]:
    """Return a summary of top-level material libraries and loose files."""

    install = install or get_default_installation()
    root = (materials_dir or install.materials_dir).resolve()
    if not root.exists():
        return []

    libraries: list[dict] = []
    for item in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if item.is_dir():
            libraries.append(_summarize_material_directory(item))
        elif item.is_file():
            libraries.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "kind": "file",
                    "size_bytes": item.stat().st_size,
                    "material_count": 1 if item.suffix.lower() in MATERIAL_EXTENSIONS else 0,
                    "support_count": 1 if item.suffix.lower() in SUPPORT_EXTENSIONS else 0,
                    "document_count": 1 if item.suffix.lower() in DOC_EXTENSIONS else 0,
                    "other_count": 0
                    if item.suffix.lower() in MATERIAL_EXTENSIONS | SUPPORT_EXTENSIONS | DOC_EXTENSIONS
                    else 1,
                }
            )
    return libraries


def find_duplicate_material_files(
    install: AutoFormInstallation | None = None,
    materials_dir: Path | None = None,
    match_mode: str = "name_size",
    limit: int | None = 50,
) -> list[dict]:
    """Find likely duplicate material files in the AutoForm materials tree."""

    install = install or get_default_installation()
    root = (materials_dir or install.materials_dir).resolve()
    if not root.exists():
        return []
    if match_mode not in {"name_size", "content_hash"}:
        raise ValueError("match_mode must be 'name_size' or 'content_hash'")

    groups: dict[str, list[Path]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MATERIAL_EXTENSIONS:
            continue
        key = _duplicate_key(path, match_mode)
        groups.setdefault(key, []).append(path)

    duplicates: list[dict] = []
    for key, files in groups.items():
        if len(files) < 2:
            continue
        file_items = [_material_file_summary(path, root) for path in sorted(files, key=lambda item: str(item).casefold())]
        duplicates.append(
            {
                "match_mode": match_mode,
                "key": key,
                "count": len(files),
                "total_size_bytes": sum(item["size_bytes"] for item in file_items),
                "files": file_items,
            }
        )
    duplicates.sort(key=lambda item: (-item["count"], item["key"]))
    return duplicates[:limit] if limit is not None else duplicates


def material_library_backup_plan(
    library_name: str,
    backup_root: Path,
    install: AutoFormInstallation | None = None,
    materials_dir: Path | None = None,
    dry_run: bool = True,
    timestamp: str | None = None,
) -> dict:
    """Plan or create a backup copy of one top-level AutoForm material library."""

    install = install or get_default_installation()
    materials_root = (materials_dir or install.materials_dir).resolve()
    source = (materials_root / library_name).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if materials_root not in [source, *source.parents]:
        raise ValueError(f"Source is outside the materials directory: {source}")
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = (backup_root.resolve() / f"{source.name}_{stamp}").resolve()
    summary = _summarize_backup_source(source)
    copied = False
    if not dry_run:
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        copied = True
    return {
        "source": str(source),
        "destination": str(destination),
        "dry_run": dry_run,
        "copied": copied,
        "summary": summary,
    }


def inspect_material_file(path: Path, preview_lines: int = 20, hash_contents: bool = False) -> dict:
    """Inspect one AutoForm .mat or .mtb material file."""

    source = path.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in MATERIAL_EXTENSIONS:
        raise ValueError(f"Unsupported material file extension: {source.suffix}")
    stat = source.stat()
    result = {
        "path": str(source),
        "name": source.name,
        "suffix": source.suffix.lower(),
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
        "hash_sha256": _sha256_file(source) if hash_contents else None,
    }
    if source.suffix.lower() == ".mtb":
        with source.open("rb") as handle:
            prefix = handle.read(16)
        return {
            **result,
            "format": "mtb_binary",
            "binary": True,
            "magic_hex": prefix.hex(),
            "preview_lines": [],
        }
    return {
        **result,
        **_inspect_mat_text(source, preview_lines=preview_lines),
    }


def plan_material_files(source_dir: Path, include_docs: bool = False) -> list[MaterialFile]:
    """Return AutoForm material files while preserving their relative layout."""

    source_dir = source_dir.resolve()
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)
    if not source_dir.is_dir():
        raise NotADirectoryError(source_dir)

    files: list[MaterialFile] = []
    allowed = set(MATERIAL_EXTENSIONS) | set(SUPPORT_EXTENSIONS)
    if include_docs:
        # Documentation is useful for reference, but AutoForm only consumes the
        # material and support files directly.
        allowed |= DOC_EXTENSIONS

    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in allowed:
            continue
        if suffix in MATERIAL_EXTENSIONS:
            category = "material"
        elif suffix in SUPPORT_EXTENSIONS:
            category = "support"
        else:
            category = "document"
        files.append(MaterialFile(path=path, relative_path=path.relative_to(source_dir), category=category))
    return files


def install_material_library(
    source: Path,
    install: AutoFormInstallation | None = None,
    library_name: str | None = None,
    target_dir: Path | None = None,
    include_docs: bool = False,
    dry_run: bool = False,
) -> MaterialInstallResult:
    """Copy a material library into AutoForm's shared materials directory."""

    install = install or get_default_installation()
    source = source.resolve()
    is_archive = source.is_file() and source.suffix.lower() in ARCHIVE_EXTENSIONS

    with _prepared_source(source) as prepared_source:
        # Archives often contain one top-level folder named after the package.
        # Directory sources are left untouched so repeated installs keep the
        # caller's intended layout.
        root = _choose_content_root(prepared_source) if is_archive else prepared_source
        library = library_name or source.stem
        target = (target_dir or install.materials_dir / library).resolve()
        planned = plan_material_files(root, include_docs=include_docs)
        copied: list[Path] = []

        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
            for item in planned:
                destination = target / item.relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item.path, destination)
                copied.append(destination)

        return MaterialInstallResult(
            source=source,
            target_dir=target,
            copied_files=copied,
            planned_files=planned,
            dry_run=dry_run,
        )


def archive_members(archive_path: Path) -> list[str]:
    """List archive members through `tar` without extracting the archive."""
    archive_path = archive_path.resolve()
    if not archive_path.exists():
        raise FileNotFoundError(archive_path)
    result = subprocess.run(
        ["tar", "-tf", str(archive_path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


class _prepared_source:
    """Context manager that exposes a directory for either folders or archives."""

    def __init__(self, source: Path):
        """Remember the caller source and defer extraction until enter time."""
        self.source = source
        self._tmp: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> Path:
        """Return a directory view of the source for downstream file planning."""
        if self.source.is_dir():
            return self.source
        if self.source.suffix.lower() not in ARCHIVE_EXTENSIONS:
            raise ValueError(f"Unsupported material source: {self.source}")
        # Windows bsdtar handles the RAR5 file found in this workflow, while the
        # older 7za bundled with AutoForm may fail to list it.
        self._tmp = tempfile.TemporaryDirectory(prefix="autoform_materials_")
        tmp_path = Path(self._tmp.name)
        subprocess.run(["tar", "-xf", str(self.source), "-C", str(tmp_path)], check=True)
        return tmp_path

    def __exit__(self, exc_type, exc, tb) -> None:
        """Delete temporary extraction directories created for archives."""
        if self._tmp is not None:
            self._tmp.cleanup()


def _choose_content_root(path: Path) -> Path:
    """Drop a single archive wrapper directory when it adds no information."""

    children = [child for child in path.iterdir() if child.is_dir()]
    files = [child for child in path.iterdir() if child.is_file()]
    if len(children) == 1 and not files:
        return children[0]
    return path


def result_to_json(result: MaterialInstallResult) -> str:
    """Serialize a material install result for CLI output."""
    return json.dumps(result.as_dict(), ensure_ascii=False, indent=2)


def _inspect_mat_text(path: Path, preview_lines: int) -> dict:
    """Extract maintainable, stable facts from a text `.mat` file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    generation_tools = sorted(
        token for needle, token in GENERATION_NEEDLES.items() if any(needle in line for line in lines[:80])
    )
    scalar_properties = {}
    top_level_keys = []
    thickness_values = []
    numeric_table_rows = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("##") or stripped.startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            key = stripped.split()[0]
            if key not in top_level_keys:
                top_level_keys.append(key)
        parts = stripped.split()
        if len(parts) >= 2 and parts[0] in SCALAR_MATERIAL_KEYS:
            scalar_properties[parts[0]] = parts[1]
        if len(parts) >= 2 and parts[0] == "Thickness":
            thickness_values.append(parts[1])
        if NUMERIC_LINE_RE.match(line):
            numeric_table_rows += 1
    return {
        "format": "mat_text",
        "binary": False,
        "line_count": len(lines),
        "comment_line_count": sum(1 for line in lines if line.strip().startswith("#")),
        "generation_tools": generation_tools,
        "warning_lines": [line.strip("# ") for line in lines[:80] if "WARNING" in line][:10],
        "top_level_keys": top_level_keys[:40],
        "scalar_properties": scalar_properties,
        "has_hardening_curve": "HardeningCurve" in top_level_keys,
        "thickness_section_count": len(thickness_values),
        "thickness_values": thickness_values[:50],
        "numeric_table_rows": numeric_table_rows,
        "preview_lines": lines[:preview_lines],
    }


def _sha256_file(path: Path) -> str:
    """Compute a SHA256 hash using bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _summarize_material_directory(path: Path) -> dict:
    """Count material, support, document and other files under one directory."""
    counts = {
        "material_count": 0,
        "support_count": 0,
        "document_count": 0,
        "other_count": 0,
    }
    size_bytes = 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        suffix = item.suffix.lower()
        size_bytes += item.stat().st_size
        if suffix in MATERIAL_EXTENSIONS:
            counts["material_count"] += 1
        elif suffix in SUPPORT_EXTENSIONS:
            counts["support_count"] += 1
        elif suffix in DOC_EXTENSIONS:
            counts["document_count"] += 1
        else:
            counts["other_count"] += 1
    return {
        "name": path.name,
        "path": str(path),
        "kind": "directory",
        "size_bytes": size_bytes,
        **counts,
    }


def _duplicate_key(path: Path, match_mode: str) -> str:
    """Return the grouping key used by duplicate material detection."""
    stat = path.stat()
    if match_mode == "content_hash":
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"{path.suffix.lower()}:{stat.st_size}:{digest.hexdigest()}"
    return f"{path.name.casefold()}:{stat.st_size}"


def _material_file_summary(path: Path, root: Path) -> dict:
    """Return one material file summary relative to the scanned root."""
    stat = path.stat()
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(root)),
        "name": path.name,
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
    }


def _summarize_backup_source(path: Path) -> dict:
    """Summarize a file or directory before a material backup is created."""
    if path.is_file():
        suffix = path.suffix.lower()
        return {
            "kind": "file",
            "file_count": 1,
            "size_bytes": path.stat().st_size,
            "material_count": 1 if suffix in MATERIAL_EXTENSIONS else 0,
            "support_count": 1 if suffix in SUPPORT_EXTENSIONS else 0,
            "document_count": 1 if suffix in DOC_EXTENSIONS else 0,
            "other_count": 0 if suffix in MATERIAL_EXTENSIONS | SUPPORT_EXTENSIONS | DOC_EXTENSIONS else 1,
        }
    summary = _summarize_material_directory(path)
    return {
        "kind": "directory",
        "file_count": sum(1 for item in path.rglob("*") if item.is_file()),
        "size_bytes": summary["size_bytes"],
        "material_count": summary["material_count"],
        "support_count": summary["support_count"],
        "document_count": summary["document_count"],
        "other_count": summary["other_count"],
    }
