# AutoForm_MCP 新手上手指南

本文档只说明独立 `AutoForm_MCP` 项目。它的核心用途是启动一个本地 stdio MCP server，让 Codex、Claude Code、OpenCalw 或其他 MCP host 调用 AutoForm 辅助工具。

## 先认识几个名字

`AutoForm` 指你电脑上已经安装好的 AutoForm Forming 软件。本仓库不包含 AutoForm 软件和许可证。

`MCP host` 指能连接 MCP server 的客户端，例如 Codex、Claude Code 或其他支持 stdio MCP 的工具。

`AutoForm_MCP` 指本目录。独立 GitHub 仓库的根目录应该就是本目录，不是完整 `AUTO_AutoForm` 工作区。

`stdio` 指标准输入输出。MCP host 启动 `python -m autoform_agent.mcp_server` 后，会通过标准输入输出和它交换 JSON-RPC 消息。

`autoform://status` 是只读状态资源。连接成功后，优先读取它，确认本机环境、AutoForm 安装发现和工具能力。

## 第一次安装

PowerShell：

```powershell
git clone https://github.com/txf0101/AutoForm_MCP.git AutoForm_MCP
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
python -m autoform_agent.cli status
```

cmd：

```cmd
git clone https://github.com/txf0101/AutoForm_MCP.git AutoForm_MCP
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
python -m autoform_agent.cli status
```

如果你拿到的是完整 `AUTO_AutoForm` 工作区，先进入子目录再执行环境检查：

```powershell
cd AutoForm_MCP
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
```

## 配置 MCP host

Codex 的 TOML 配置示例在：

```text
codex_mcp_config.autoform-mcp.toml
```

把其中内容加入 `%USERPROFILE%\.codex\config.toml`，并把 `<repo-root>` 改成当前电脑上 `AutoForm_MCP` 文件夹的绝对路径。

Claude Code 可以用：

```powershell
claude mcp add --transport stdio --scope user --env PYTHONPATH="<repo-root>" autoform-mcp -- conda run -n afagent python -m autoform_agent.mcp_server
claude mcp list
claude mcp get autoform-mcp
```

其他 stdio MCP 客户端使用同样的命令结构：command 是 `conda`，args 是 `run -n afagent python -m autoform_agent.mcp_server`，环境变量 `PYTHONPATH` 指向 `<repo-root>`。

## 连接后怎么用

1. 先读取 `autoform://status`，或调用 `autoform_status_snapshot`。
2. 再调用 `autoform_discover_installation`，确认本机 AutoForm 安装是否被发现。
3. 需要了解 V1.1 结果审阅边界时，调用 `autoform_result_blockers`。
4. 需要规划工程运行时，调用 `autoform_project_run`，先不要传 `execute=true`。
5. 只有确认工程、许可证、输出目录和可见桌面状态后，才给执行类工具传 `execute=true`。

## 每个目录负责什么

`autoform_agent/mcp_server.py` 是 MCP 启动入口。

`autoform_agent/mcp_tools/` 是 MCP wrapper 层，负责把外部 MCP 参数转成内部函数参数。

`autoform_agent/*.py` 是业务层，负责 AutoForm 安装发现、工程运行、求解器计划、GUI 窗口、结果审阅、材料、QuickLink 和发布检查。

`tests/` 是测试目录，重点检查 MCP 工具注册、GUI 原语、结果审阅和工程运行计划。

`README.md` 是英文和中文混排的主说明，第一屏就是安装和连接 MCP。

`README.zh-CN.md` 是中文专用说明。

## 路径规则

不要把别人电脑上的绝对路径复制到自己的 MCP 配置里。每台电脑都要使用自己的：

- `AutoForm_MCP` 仓库路径。
- Python 或 Conda 环境路径。
- AutoForm 安装路径。
- AutoForm 许可证。

如果自动发现 AutoForm 失败，复制 `.env.example` 为 `.env`，只填写当前电脑上的真实路径。

```powershell
Copy-Item .env.example .env
```

## 测试

Windows 默认临时目录没有权限时，用项目内临时目录：

```powershell
$env:TEMP=(Resolve-Path .).Path + "\tmp\pytest_env"
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest tests\test_mcp_tools.py tests\test_gui_automation.py tests\test_result_viewer.py tests\test_r12_demo.py tests\test_project_workflow.py tests\test_process.py -q --basetemp tmp\pytest_mcp
```

当前 MCP_V1.1 预期结果是：

```text
54 passed
```

## V1.1 边界

MCP_V1.1 暴露 112 个 `autoform_` 工具和 `autoform://status` 资源。

MCP_V1.1 不生成工程判断报告。它返回证据、就绪检查、GUI 边界和审阅计划。工程阈值和 pass/fail 结论属于后续可选输入。
