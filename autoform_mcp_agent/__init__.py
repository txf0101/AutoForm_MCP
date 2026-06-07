"""这个包提供 AutoForm_MCP 的公共 Python 入口。外部代码通常只需要从这里拿到安装发现相关对象。

This package exposes the public Python entry points for AutoForm_MCP. External code usually only needs the installation discovery objects from here.
"""

from .paths import AutoFormInstallation, discover_installations, get_default_installation

__version__ = "1.8.0"

__all__ = [
    "__version__",
    "AutoFormInstallation",
    "discover_installations",
    "get_default_installation",
]
