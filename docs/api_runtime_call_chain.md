# AutoForm_MCP stdio MCP 调用链说明

本文说明独立 `AutoForm_MCP` 项目的运行链路。它只描述本目录内实际存在的源码、配置和测试。

## 总体链路

MCP host 启动本地 Python 进程：

```powershell
python -m autoform_mcp_agent.mcp_server
```

`autoform_mcp_agent/mcp_server.py` 创建 `FastMCP("autoform-mcp")`，调用 `autoform_mcp_agent.mcp_tools.register_all_tools()`，把 `autoform_mcp_agent/mcp_tools/` 下分组维护的 wrapper 函数注册为 MCP 工具。文件末尾的 `mcp.run()` 让进程通过标准输入和标准输出接收 MCP JSON-RPC 消息。

外部调用顺序可以理解为：

```text
Codex / Claude Code / OpenCalw / other MCP host
  -> stdio JSON-RPC
  -> python -m autoform_mcp_agent.mcp_server
  -> autoform_mcp_agent.mcp_tools.register_all_tools()
  -> autoform_mcp_agent.mcp_tools.<tool_family>.autoform_*
  -> autoform_mcp_agent.<business_module>.<function>
  -> JSON-serializable result back to the MCP host
```

## 资源和工具

`autoform://status` 是只读资源。它调用 `autoform_mcp_agent.diagnostics.autoform_status_snapshot()`，返回项目版本、服务默认值、本机 AutoForm 安装发现、队列检查、QuickLink 导出、近期日志和能力覆盖。

MCP_V1.8 当前注册 112 个 `autoform_` 工具。工具分组在 `autoform_mcp_agent/mcp_tools/__init__.py` 的 `MCP_TOOL_LAYERS` 和 `ALL_TOOL_FUNCTIONS` 中集中列出，`tests/test_mcp_tools.py` 会检查工具数量、关键工具名和 `autoform://status` 资源。

## 分层职责

`autoform_mcp_agent/mcp_server.py` 只做启动和注册。它不写业务规则，目的是让 `python -m autoform_mcp_agent.mcp_server` 这个入口长期稳定。

`autoform_mcp_agent/mcp_tools/` 是 MCP wrapper 层。每个文件负责一个工具家族，例如 status、project、jobs、materials、quicklink、environment、queue、solver、commands、reporting、release、reference 和 gui。wrapper 负责把 MCP 传来的字符串、布尔值和列表转换成内部函数需要的 `Path` 或参数，再返回可序列化对象。

`autoform_mcp_agent/*.py` 是业务层。安装发现、工程运行、求解器计划、结果证据、GUI 窗口检查、结果审阅、材料、QuickLink、作业生命周期和发布检查都放在这里。CLI 和 MCP 可以共用这些函数。

`tests/` 是验证层。MCP_V1.8 的核心测试包括工具注册、进程命令、工程运行、GUI 原语、R12 可见窗口演示和结果审阅。

## 安全边界

大多数会影响本机 AutoForm、文件系统或桌面的动作默认是 planning、dry run 或需要显式 `execute=true`。调用者应从 `autoform://status` 和只读工具开始检查环境，确认工程、许可证、输出目录和可见桌面后再开启真实执行。

MCP_V1.8 不生成工程判断报告。它只返回证据、就绪检查、GUI 边界和审阅计划。工程阈值和 pass/fail 结论属于后续可选输入。`autoform_r12_project_view_demo` 不内置默认视角切换序列；调用方传入 `view_sequence` 后才发送视角快捷键。已有结果窗口的续接视角切换应优先使用 `autoform_result_set_view`，并按需要传入 `title_contains` 或 `target_pid`。

## 维护要求

新增 MCP 能力时，按下面顺序做：

1. 先在业务模块中实现可测试函数。
2. 再在 `autoform_mcp_agent/mcp_tools/` 中对应工具家族新增薄 wrapper。
3. 把 wrapper 加入对应 `register_*_tools()`。
4. 如果是新工具，还要加入 `autoform_mcp_agent/mcp_tools/__init__.py` 的 `ALL_TOOL_FUNCTIONS`。
5. 更新测试，至少检查工具注册、默认安全行为和关键返回字段。
6. 同步更新 `README.md`、`README.zh-CN.md` 和 `codex_mcp_config.autoform-mcp.toml` 中受影响的安装或调用说明。
