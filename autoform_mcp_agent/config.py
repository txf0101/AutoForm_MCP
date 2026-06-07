"""这个文件只读解析 AutoForm 的 `systemConfigFile.xml`。它用来查看本机队列、远程计算主机和日志设置。

This file reads AutoForm `systemConfigFile.xml` without modifying it. It is used to inspect local queues, remote compute hosts, and logging settings.

返回值使用普通字典，CLI、MCP 和测试都能直接复用，不需要依赖任何界面。

It returns plain dictionaries so CLI commands, MCP tools, and tests can reuse the same data without any UI dependency.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from .paths import AutoFormInstallation, get_default_installation


def get_queue_config(
    install: AutoFormInstallation | None = None,
    config_path: Path | None = None,
) -> dict:
    """Return queue settings from AutoForm's systemConfigFile.xml."""

    source, root = _read_config(install, config_path)
    section = root.find("QueuingConfiguration")
    queues: list[dict] = []
    if section is not None:
        for queue in section.findall("queue"):
            queues.append(
                {
                    "key": queue.attrib.get("key"),
                    "name": _text(queue, "QueueName"),
                    "max_jobs": _int_text(queue, "MaxJobs"),
                    "license_server": _text(queue, "LicenseServer"),
                    "restrict_to_parallel_solver": _int_text(queue, "RestrictToParallelSolver"),
                    "restrict_queuing_options": _text(queue, "RestrictQueuingOptions"),
                }
            )

    return {
        "source": str(source),
        "queuing_only_host": _bool_text(section, "queuingOnlyHost") if section is not None else None,
        "queues": queues,
    }


def get_remote_hosts(
    install: AutoFormInstallation | None = None,
    config_path: Path | None = None,
) -> dict:
    """Return remote computing hosts and supported module names."""

    source, root = _read_config(install, config_path)
    section = root.find("RemoteComputingConfiguration")
    hosts: list[dict] = []
    host_parent = section.find("HostAndJobsConfiguration") if section is not None else None
    if host_parent is not None:
        for host in host_parent.findall("host"):
            module = host.find("module")
            modules = [_clean(item.text) for item in module.findall("item")] if module is not None else []
            hosts.append(
                {
                    "key": host.attrib.get("key"),
                    "name": _text(host, "name"),
                    "host": _text(host, "host"),
                    "port": _int_text(host, "port"),
                    "parallel_option": _int_text(host, "parallelOption"),
                    "modules": [item for item in modules if item],
                }
            )

    return {
        "source": str(source),
        "use_auto_config": _bool_text(section, "useAutoConfig") if section is not None else None,
        "auto_config_url": _text(section, "autoConfigURL") if section is not None else None,
        "kin_check_on_localhost": _bool_text(section, "kinCheckOnLocalhost") if section is not None else None,
        "default_host": _text(section, "defaultHost") if section is not None else None,
        "hosts": hosts,
    }


def get_logging_config(
    install: AutoFormInstallation | None = None,
    config_path: Path | None = None,
) -> dict:
    """Return logging settings from AutoForm's systemConfigFile.xml."""

    source, root = _read_config(install, config_path)
    section = root.find("LoggingConfiguration")
    values = {child.tag: _clean(child.text) for child in list(section)} if section is not None else {}
    return {
        "source": str(source),
        "values": values,
    }


def _read_config(
    install: AutoFormInstallation | None,
    config_path: Path | None,
) -> tuple[Path, ET.Element]:
    """Resolve and parse the XML config used by all public readers."""
    source = (config_path or (install or get_default_installation()).system_config_file).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    return source, ET.parse(source).getroot()


def _text(parent: ET.Element | None, name: str) -> str | None:
    """Return cleaned child text while treating missing nodes as `None`."""
    if parent is None:
        return None
    child = parent.find(name)
    if child is None:
        return None
    return _clean(child.text)


def _int_text(parent: ET.Element | None, name: str) -> int | None:
    """Parse optional integer XML text and ignore malformed values."""
    value = _text(parent, name)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bool_text(parent: ET.Element | None, name: str) -> bool | None:
    """Parse AutoForm's `true`/`false` text into a Python boolean."""
    value = _text(parent, name)
    if value is None or value == "":
        return None
    return value.lower() == "true"


def _clean(value: str | None) -> str | None:
    """Strip XML text without turning missing values into empty strings."""
    if value is None:
        return None
    return value.strip()
