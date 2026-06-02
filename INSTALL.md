# AutoForm_MCP Installation

## Quick Install

PowerShell:

```powershell
git clone https://github.com/txf0101/AutoForm_MCP.git AutoForm_MCP
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
python -m autoform_agent.cli status
```

cmd:

```cmd
git clone https://github.com/txf0101/AutoForm_MCP.git AutoForm_MCP
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
python -m autoform_agent.cli status
```

If AutoForm_MCP is inside the larger `AUTO_AutoForm` workspace, enter the subfolder first:

如果 AutoForm_MCP 位于完整 `AUTO_AutoForm` 工作区内，先进入子目录：

```powershell
cd AutoForm_MCP
```

## Connect MCP Host

Use `README.md` first. It contains Codex, Claude Code, OpenCalw, and generic stdio MCP configuration examples.

优先阅读 `README.md`。里面已经把 Codex、Claude Code、OpenCalw 和通用 stdio MCP 配置写在最前面。

The portable Codex/TOML template is:

可移植 Codex/TOML 模板文件是：

```text
codex_mcp_config.autoform-mcp.toml
```

Replace `<repo-root>` with the absolute path of the `AutoForm_MCP` folder on the current computer.

把 `<repo-root>` 替换成当前电脑上 `AutoForm_MCP` 文件夹的绝对路径。

## AutoForm Paths

AutoForm_MCP does not ship AutoForm software, licenses, or proprietary example projects. It can discover standard local AutoForm Forming installations. If discovery fails, copy `.env.example` to `.env` and fill only the paths that are different on that computer.

AutoForm_MCP 不包含 AutoForm 软件、许可证或专有样例工程。它会尝试发现标准本机 AutoForm Forming 安装。如果自动发现失败，复制 `.env.example` 为 `.env`，只填写当前电脑上不同的路径。

```powershell
Copy-Item .env.example .env
```

## Test

```powershell
$env:TEMP=(Resolve-Path .).Path + "\tmp\pytest_env"
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest tests\test_mcp_tools.py tests\test_gui_automation.py tests\test_result_viewer.py tests\test_r12_demo.py tests\test_project_workflow.py tests\test_process.py -q --basetemp tmp\pytest_mcp
```

Expected MCP_V1.1 result:

当前 MCP_V1.1 预期结果：

```text
54 passed
```
