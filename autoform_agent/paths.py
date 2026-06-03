"""这个文件负责发现 AutoForm 安装位置，并计算后续模块要用的标准路径。

This file discovers AutoForm installation locations and calculates the canonical paths used by the rest of the project.

它是整个项目的移植边界。其他模块不应该硬编码 `Program Files`、`ProgramData` 或具体版本目录，而应该向这里询问路径。

It is the portability boundary for the whole project. Other modules should ask this module for paths instead of hard-coding `Program Files`, `ProgramData`, or version-specific directories.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ENV_INSTALL_DIR = "AUTOFORM_INSTALL_DIR"
ENV_PROGRAM_DATA_DIR = "AUTOFORM_PROGRAM_DATA_DIR"
ENV_VERSION_DIR = "AUTOFORM_VERSION_DIR"
ENV_MATERIALS_DIR = "AUTOFORM_MATERIALS_DIR"
ENV_SCRIPTS_DIR = "AUTOFORM_SCRIPTS_DIR"
ENV_TEST_DIR = "AUTOFORM_TEST_DIR"
ENV_QUICKLINK_TEMPLATES_DIR = "AUTOFORM_QUICKLINK_TEMPLATES_DIR"
ENV_SYSTEM_CONFIG_FILE = "AUTOFORM_SYSTEM_CONFIG_FILE"
ENV_HELP_LINKS_FILE = "AUTOFORM_HELP_LINKS_FILE"


@dataclass(frozen=True)
class AutoFormInstallation:
    """Resolved paths and registry metadata for one AutoForm Forming install.

    The object stores only facts that identify the installation.  Derived
    directories such as `materials_dir` or `scripts_dir` are computed through
    properties so that future overrides can be added in one place.
    """

    display_name: str
    version: str | None
    install_location: Path
    install_date: str | None = None
    publisher: str | None = None

    @property
    def version_dir_name(self) -> str:
        """Return the folder name used below `%ProgramData%\\AutoForm\\AFplus`.

        AutoForm R13 installs into a directory such as `R13F`; the same token is
        used in ProgramData. Users can override product layouts with
        `AUTOFORM_VERSION_DIR` when a target machine uses a different layout.
        """
        override = _env_path_text(ENV_VERSION_DIR)
        if override:
            return override
        return self.install_location.name

    @property
    def bin_dir(self) -> Path:
        """Return the directory that contains AutoForm executables."""
        return self.install_location / "bin"

    @property
    def package_info_file(self) -> Path:
        """Return the optional installer metadata file shipped by AutoForm."""
        return self.install_location / "package_info_lite.json"

    @property
    def forming_ui(self) -> Path:
        """Return the GUI executable used to start AutoForm Forming."""
        return self.bin_dir / "AFFormingUI.exe"

    @property
    def splash(self) -> Path:
        """Return the splash launcher used by Start Menu shortcuts."""
        return self.bin_dir / "AFSplash.exe"

    @property
    def forming_job(self) -> Path:
        """Return the batch job executable used by command-line workflows."""
        return self.bin_dir / "AFFormingJob.exe"

    @property
    def forming_job_cmd(self) -> Path:
        """Return the versioned command wrapper observed in the R13 install."""
        return self.bin_dir / "AFFormingJob_R13.cmd"

    @property
    def autoform_program_data(self) -> Path:
        """Return the ProgramData root for this AutoForm version directory."""
        exact_override = _env_path(ENV_PROGRAM_DATA_DIR)
        if exact_override is not None:
            return exact_override
        # AutoForm keeps mutable product data under ProgramData, while executables
        # live under the installation directory in Program Files.
        system_drive = os.environ.get("SystemDrive")
        fallback_program_data = str(Path(system_drive) / "ProgramData") if system_drive else "ProgramData"
        program_data = Path(os.environ.get("PROGRAMDATA", fallback_program_data))
        return program_data / "AutoForm" / "AFplus" / self.version_dir_name

    @property
    def materials_dir(self) -> Path:
        """Return the mutable material library root used by AutoForm."""
        override = _env_path(ENV_MATERIALS_DIR)
        if override is not None:
            return override
        return self.autoform_program_data / "materials"

    @property
    def scripts_dir(self) -> Path:
        """Return the QuickLink and automation script directory."""
        override = _env_path(ENV_SCRIPTS_DIR)
        if override is not None:
            return override
        return self.autoform_program_data / "scripts"

    @property
    def test_dir(self) -> Path:
        """Return the official sample project directory under ProgramData."""
        override = _env_path(ENV_TEST_DIR)
        if override is not None:
            return override
        return self.autoform_program_data / "test"

    @property
    def quicklink_templates_dir(self) -> Path:
        """Return the QuickLink template and standard definition directory."""
        override = _env_path(ENV_QUICKLINK_TEMPLATES_DIR)
        if override is not None:
            return override
        return self.autoform_program_data / "templates" / "quicklink"

    @property
    def system_config_file(self) -> Path:
        """Return the queue, remote computing and logging configuration file."""
        override = _env_path(ENV_SYSTEM_CONFIG_FILE)
        if override is not None:
            return override
        return self.autoform_program_data / "systemConfigFile.xml"

    @property
    def help_links_file(self) -> Path:
        """Return the help topic mapping file shipped with the installation."""
        override = _env_path(ENV_HELP_LINKS_FILE)
        if override is not None:
            return override
        return self.install_location / "help" / "helpLinks.cfg"

    def package_info(self) -> dict:
        """Read installer package metadata if the file is present and valid.

        Missing or malformed metadata is treated as an empty dictionary because
        installation discovery should remain usable even when optional installer
        evidence is unavailable.
        """
        if not self.package_info_file.exists():
            return {}
        try:
            return json.loads(self.package_info_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def as_dict(self) -> dict:
        """Return a JSON-ready installation snapshot for CLI and MCP clients."""
        package = self.package_info()
        return {
            "display_name": self.display_name,
            "version": self.version,
            "install_date": self.install_date,
            "publisher": self.publisher,
            "install_location": str(self.install_location),
            "bin_dir": str(self.bin_dir),
            "forming_ui": str(self.forming_ui),
            "splash": str(self.splash),
            "forming_job": str(self.forming_job),
            "forming_job_cmd": str(self.forming_job_cmd),
            "program_data": str(self.autoform_program_data),
            "materials_dir": str(self.materials_dir),
            "scripts_dir": str(self.scripts_dir),
            "test_dir": str(self.test_dir),
            "quicklink_templates_dir": str(self.quicklink_templates_dir),
            "system_config_file": str(self.system_config_file),
            "help_links_file": str(self.help_links_file),
            "package_info": package,
            "exists": {
                "install_location": self.install_location.exists(),
                "forming_ui": self.forming_ui.exists(),
                "splash": self.splash.exists(),
                "forming_job": self.forming_job.exists(),
                "materials_dir": self.materials_dir.exists(),
                "scripts_dir": self.scripts_dir.exists(),
                "system_config_file": self.system_config_file.exists(),
                "help_links_file": self.help_links_file.exists(),
            },
        }


def discover_installations() -> list[AutoFormInstallation]:
    """Find AutoForm through Windows uninstall metadata, then known fallbacks."""

    installs = _explicit_installations()
    installs.extend(_discover_from_registry())
    installs.extend(_fallback_installations())
    return _dedupe_installations(installs)


def get_default_installation() -> AutoFormInstallation:
    """Return the best available AutoForm installation for single-install flows.

    Current behavior prefers records whose install directory exists.  When
    multi-version support is added, this function should become the policy
    point for version selection.
    """
    installs = discover_installations()
    if not installs:
        raise FileNotFoundError("No AutoForm Forming installation was found.")
    return sorted(installs, key=lambda item: item.install_location.exists(), reverse=True)[0]


def _discover_from_registry() -> Iterable[AutoFormInstallation]:
    """Read Windows uninstall registry keys for AutoForm Forming installs."""
    if os.name != "nt":
        return []

    try:
        import winreg
    except ImportError:
        return []

    roots = [
        # 64-bit and 32-bit uninstall registries are both cheap to inspect and
        # keep this function tolerant of installer differences.
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
    ]

    found: list[AutoFormInstallation] = []
    for root, subkey in roots:
        try:
            with winreg.OpenKey(root, subkey) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        child_name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, child_name) as child:
                            display_name = _read_reg_value(winreg, child, "DisplayName")
                            if not display_name or "AutoForm Forming" not in display_name:
                                continue
                            install_location = _read_reg_value(winreg, child, "InstallLocation")
                            if not install_location:
                                continue
                            found.append(
                                AutoFormInstallation(
                                    display_name=display_name,
                                    version=_read_reg_value(winreg, child, "DisplayVersion"),
                                    install_location=Path(install_location),
                                    install_date=_read_reg_value(winreg, child, "InstallDate"),
                                    publisher=_read_reg_value(winreg, child, "Publisher"),
                                )
                            )
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _read_reg_value(winreg_module, key, name: str) -> str | None:
    """Read one registry value and normalize missing values to `None`."""
    try:
        value, _ = winreg_module.QueryValueEx(key, name)
    except OSError:
        return None
    return str(value) if value is not None else None


def _fallback_installations() -> list[AutoFormInstallation]:
    """Use conservative defaults for machines where registry reads are blocked."""

    base_dirs = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(env_name)
        if value:
            base_dirs.append(Path(value))
    candidates = [base / "AutoForm" / "AFplus" / "R13F" for base in base_dirs]
    return [
        AutoFormInstallation(
            display_name="AutoForm Forming R13",
            version=None,
            install_location=path,
        )
        for path in candidates
        if path.exists()
    ]


def _explicit_installations() -> list[AutoFormInstallation]:
    """Return the user-configured installation when `AUTOFORM_INSTALL_DIR` is set."""

    install_dir = _env_path(ENV_INSTALL_DIR)
    if install_dir is None:
        return []
    return [
        AutoFormInstallation(
            display_name=f"AutoForm Forming ({ENV_INSTALL_DIR})",
            version=None,
            install_location=install_dir,
        )
    ]


def _dedupe_installations(installs: Iterable[AutoFormInstallation]) -> list[AutoFormInstallation]:
    """Merge registry and fallback discoveries by normalized install path."""
    deduped: dict[str, AutoFormInstallation] = {}
    for install in installs:
        key = str(install.install_location).casefold().rstrip("\\/")
        existing = deduped.get(key)
        # Prefer registry records with a concrete version over fallback guesses.
        if existing is None or (existing.version is None and install.version is not None):
            deduped[key] = install
    return list(deduped.values())


def _env_path(name: str) -> Path | None:
    """Read one path override from the environment and normalize blank values."""

    value = _env_path_text(name)
    return Path(value).expanduser() if value else None


def _env_path_text(name: str) -> str | None:
    """Return a stripped environment value, preserving Windows path text."""

    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip().strip('"')
    return value or None
