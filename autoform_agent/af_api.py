"""这个文件读取 AutoForm 自带的 AF_API 示例，并生成构建预览。默认只看文件和给出计划，不编译、不加载用户代码。

This file reads the AF_API samples shipped with AutoForm and builds preview commands. By default it only inspects files and returns plans; it does not compile or load user code.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from .paths import AutoFormInstallation, get_default_installation

MODULE_SOURCES = {
    "friction": {
        "source": "af_friction.c",
        "header": "af_friction.h",
        "control_variable": "UserFriction",
        "linux_compile": ["gcc", "-fPIC", "-c", "af_friction.c", "-o", "af_friction.o"],
        "linux_link": ["gcc", "-shared", "-o", "libafuser.so", "af_friction.o"],
        "windows_cl": ["cl", "-DWIN32", "/LD", "/Felibafuser.dll", "af_friction.c"],
    },
    "heattransfer": {
        "source": "af_heattransfer.c",
        "header": "af_heattransfer.h",
        "control_variable": "UserHeatTransfer",
        "linux_compile": ["gcc", "-fPIC", "-c", "af_heattransfer.c", "-o", "af_heattransfer.o"],
        "linux_link": ["gcc", "-shared", "-o", "libafuser.so", "af_heattransfer.o"],
        "windows_cl": ["cl", "-DWIN32", "/LD", "/Felibafuser.dll", "af_heattransfer.c"],
    },
    "oneelementpost": {
        "source": "af_oneelementpost.c",
        "header": "af_oneelementpost.h",
        "control_variable": None,
        "linux_compile": ["gcc", "-fPIC", "-c", "af_oneelementpost.c", "-o", "af_oneelementpost.o"],
        "linux_link": ["gcc", "-shared", "-o", "libafuser.so", "af_oneelementpost.o"],
        "windows_cl": ["cl", "-DWIN32", "/LD", "/Felibafuser.dll", "af_oneelementpost.c"],
    },
}


def list_af_api_modules(install: AutoFormInstallation | None = None) -> list[dict]:
    """Return AF_API sample modules and exported function names."""

    install = install or get_default_installation()
    root = install.install_location / "AF_API"
    modules: list[dict] = []
    for name, info in MODULE_SOURCES.items():
        source = root / info["source"]
        header = root / info["header"]
        modules.append(
            {
                "name": name,
                "source": str(source),
                "header": str(header),
                "source_exists": source.exists(),
                "header_exists": header.exists(),
                "control_variable": info["control_variable"],
                "exports": _exports_from_header(header),
            }
        )
    return modules


def check_af_api_build_env() -> dict:
    """Return available C compiler commands and AF_HOME_LIB state."""

    compilers = {name: shutil.which(name) for name in ["gcc", "cl", "icl"]}
    return {
        "compilers": compilers,
        "available_compilers": [name for name, path in compilers.items() if path],
        "af_home_lib": os.environ.get("AF_HOME_LIB"),
    }


def af_api_template_plan(
    module: str,
    output_dir: Path,
    install: AutoFormInstallation | None = None,
    dry_run: bool = True,
) -> dict:
    """Plan or create local AF_API starter files by copying installed samples."""

    info = _module_info(module)
    install = install or get_default_installation()
    root = install.install_location / "AF_API"
    source = root / info["source"]
    header = root / info["header"]
    destination_dir = output_dir.resolve()
    planned = [
        {"source": str(source), "destination": str(destination_dir / source.name), "exists": source.exists()},
        {"source": str(header), "destination": str(destination_dir / header.name), "exists": header.exists()},
    ]
    if not dry_run:
        destination_dir.mkdir(parents=True, exist_ok=True)
        for item in planned:
            if not item["exists"]:
                raise FileNotFoundError(item["source"])
            shutil.copy2(item["source"], item["destination"])
    return {
        "module": module,
        "output_dir": str(destination_dir),
        "dry_run": dry_run,
        "planned_files": planned,
        "control_variable": info["control_variable"],
    }


def af_api_build_preview(
    module: str,
    compiler: str = "cl",
    source_file: str | None = None,
) -> dict:
    """Return compiler commands for an AF_API user library without executing them."""

    info = _module_info(module)
    source = source_file or info["source"]
    if compiler == "gcc":
        compile_cmd = [*info["linux_compile"]]
        link_cmd = [*info["linux_link"]]
        if source_file:
            object_name = f"{Path(source_file).stem}.o"
            compile_cmd = ["gcc", "-fPIC", "-c", source, "-o", object_name]
            link_cmd = ["gcc", "-shared", "-o", "libafuser.so", object_name]
        commands = [compile_cmd, link_cmd]
    elif compiler == "cl":
        commands = [["cl", "-DWIN32", "/LD", "/Felibafuser.dll", source]]
    elif compiler == "icl":
        commands = [["icl", "-DWIN32", "/LD", "/Felibafuser.dll", source]]
    else:
        raise ValueError("compiler must be gcc, cl, or icl")
    return {
        "module": module,
        "compiler": compiler,
        "commands": commands,
        "executes": False,
    }


def _module_info(module: str) -> dict:
    """Return metadata for one supported AF_API sample module."""
    normalized = module.lower().strip()
    if normalized not in MODULE_SOURCES:
        raise ValueError(f"Unsupported AF_API module: {module}")
    return MODULE_SOURCES[normalized]


def _exports_from_header(header: Path) -> list[str]:
    """Find exported `af_...` functions declared in an AF_API header."""
    if not header.exists():
        return []
    text = header.read_text(encoding="utf-8", errors="replace")
    return sorted(set(re.findall(r"\bDLLEXPORT\s+\w+\s+(af_[A-Za-z0-9_]+)", text)))
