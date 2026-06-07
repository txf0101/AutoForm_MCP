"""这个文件启动可选的 MCP stdio server。支持 MCP 的外部客户端可以通过它调用 `autoform_` 工具和读取 `autoform://status` 状态资源。

This file starts the optional MCP stdio server. External MCP-capable clients can use it to call `autoform_` tools and read the `autoform://status` resource.
"""

from __future__ import annotations

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - depends on optional package
    raise SystemExit(
        "The optional 'mcp' package is required. Install this project with the mcp extra."
    ) from exc

from .mcp_tools import *  # Re-export MCP wrapper functions for older direct imports.
from .mcp_tools import EXPORTED_FUNCTION_NAMES, register_all_tools


# 独立 AutoForm_MCP 仓库只暴露 MCP server，不包含完整网页主链路。
# 外部 MCP host 启动这里后，会看到名为 autoform-mcp 的服务和一组 `autoform_` 工具。
# 工具注册仍集中在 `autoform_mcp_agent.mcp_tools`，这个文件只负责“开门”和“挂工具”。
mcp = FastMCP("autoform-mcp")
register_all_tools(mcp)

__all__ = ["mcp", "register_all_tools", *EXPORTED_FUNCTION_NAMES]


if __name__ == "__main__":
    # Running the module directly starts the stdio MCP server used by Codex and
    # other MCP clients.
    mcp.run()
