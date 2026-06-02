# AutoForm_MCP

Version: `MCP_V1.1`

## Install And Connect First

AutoForm_MCP is an independent stdio MCP server project for local AutoForm helper workflows. Clone this repository, or enter the `AutoForm_MCP` folder if you received it inside the larger `AUTO_AutoForm` workspace.

AutoForm_MCP 是一个可以独立运行的本地 stdio MCP server 项目，用来让 Codex、Claude Code、OpenCalw 或其他 MCP host 调用 AutoForm 辅助工具。如果你拿到的是独立仓库，就克隆它；如果你拿到的是完整 `AUTO_AutoForm` 工作区，就先进入其中的 `AutoForm_MCP` 文件夹。

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

If you are inside the larger `AUTO_AutoForm` workspace, use this instead of cloning:

如果你已经在完整 `AUTO_AutoForm` 工作区里，不需要重新克隆，直接进入子目录：

```powershell
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
```

Replace `<repo-root>` below with the absolute path of this `AutoForm_MCP` folder on the current computer. Do not copy another user's absolute path.

下面所有 `<repo-root>` 都要替换成当前电脑上这个 `AutoForm_MCP` 文件夹的绝对路径。不要复制别人电脑上的绝对路径。

## Codex

Add this block to `%USERPROFILE%\.codex\config.toml`. The same block is saved in `codex_mcp_config.autoform-mcp.toml`.

把下面这段加入 `%USERPROFILE%\.codex\config.toml`。仓库内也提供同样内容的 `codex_mcp_config.autoform-mcp.toml` 模板。

```toml
[mcp_servers."autoform-mcp"]
command = 'conda'
args = ['run', '-n', 'afagent', 'python', '-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-mcp".env]
PYTHONPATH = '<repo-root>'
```

If Codex cannot find `conda`, use the Python executable inside your `afagent` environment:

如果 Codex 找不到 `conda`，改用你自己 `afagent` 环境里的 `python.exe`：

```toml
[mcp_servers."autoform-mcp"]
command = '<path-to-afagent-python.exe>'
args = ['-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-mcp".env]
PYTHONPATH = '<repo-root>'
```

Common Windows examples are `C:\Users\<user>\miniconda3\envs\afagent\python.exe` and `C:\ProgramData\miniconda3\envs\afagent\python.exe`. Use the path that exists on the target computer.

Windows 上常见位置包括 `C:\Users\<user>\miniconda3\envs\afagent\python.exe` 和 `C:\ProgramData\miniconda3\envs\afagent\python.exe`。以目标电脑真实存在的路径为准。

## Claude Code

PowerShell:

```powershell
claude mcp add --transport stdio --scope user --env PYTHONPATH="<repo-root>" autoform-mcp -- conda run -n afagent python -m autoform_agent.mcp_server
claude mcp list
claude mcp get autoform-mcp
```

cmd:

```cmd
claude mcp add --transport stdio --scope user --env PYTHONPATH="<repo-root>" autoform-mcp -- conda run -n afagent python -m autoform_agent.mcp_server
claude mcp list
claude mcp get autoform-mcp
```

If quoting is awkward, use JSON:

如果命令行引号不好处理，可以用 JSON：

```powershell
claude mcp add-json autoform-mcp '{"type":"stdio","command":"conda","args":["run","-n","afagent","python","-m","autoform_agent.mcp_server"],"env":{"PYTHONPATH":"<repo-root>"}}'
```

## OpenCalw Or Any Stdio MCP Host

Use the same command, args, and environment fields in any stdio-compatible MCP client:

其他支持 stdio MCP 的客户端也使用同样的 command、args 和 environment：

```json
{
  "mcpServers": {
    "autoform-mcp": {
      "type": "stdio",
      "command": "conda",
      "args": ["run", "-n", "afagent", "python", "-m", "autoform_agent.mcp_server"],
      "env": {
        "PYTHONPATH": "<repo-root>"
      }
    }
  }
}
```

## Manual Server Check

Run this only to check that the stdio server can start. A real MCP host keeps the process open and talks to it with JSON-RPC over standard input and output.

这条命令只用于确认 server 能启动。真实 MCP host 会让进程保持打开，并通过标准输入输出发送 JSON-RPC 消息。

```powershell
conda run -n afagent python -m autoform_agent.mcp_server
```

After connecting from a host, verify in this order:

连接到 host 后，按下面顺序检查：

1. Read `autoform://status`, or call `autoform_status_snapshot`.
2. Call `autoform_discover_installation`.
3. Call `autoform_result_blockers` to see the MCP_V1.1 result-review boundary.
4. Keep execution tools in planning mode until you really want AutoForm to run.
5. Use `execute=true` only after the project, license, output folder, and visible desktop are confirmed.

## What V1.1 Contains

MCP_V1.1 exposes 112 `autoform_` tools and the `autoform://status` resource. The count is checked by `tests/test_mcp_tools.py`.

MCP_V1.1 暴露 112 个 `autoform_` 工具，并提供 `autoform://status` 资源。工具数量由 `tests/test_mcp_tools.py` 检查。

Common tools:

| Tool | Use |
| --- | --- |
| `autoform_status_snapshot` | Read local health, AutoForm discovery, logs, and capability coverage. |
| `autoform_discover_installation` | Find local AutoForm Forming installations and important folders. |
| `autoform_project_run` | Plan or execute a copied `.afd` project run. Real execution requires `execute=true`. |
| `autoform_official_sample_run_summary` | Summarize local official-example run evidence from `run_manifest.json` files. |
| `autoform_result_inventory` | Inspect result-like files in a run folder or workspace. |
| `autoform_result_plan_review` | Convert a result-review request into a structured plan. |
| `autoform_result_set_view` | Plan or execute verified view shortcuts such as isometric, top, front, and side. |
| `autoform_result_play_forming_animation` | Use a guarded playback profile or a manual observation profile. |
| `autoform_gui_window_snapshot` | List visible AutoForm windows and interaction-ready windows. |
| `autoform_gui_restore_window` | Restore a visible AutoForm project window before audited GUI actions. |

常用工具：

| 工具 | 用途 |
| --- | --- |
| `autoform_status_snapshot` | 读取本机健康状态、AutoForm 安装发现、日志和能力覆盖。 |
| `autoform_discover_installation` | 查找本机 AutoForm Forming 安装和关键目录。 |
| `autoform_project_run` | 规划或执行复制后的 `.afd` 工程运行。真实执行需要 `execute=true`。 |
| `autoform_official_sample_run_summary` | 从 `run_manifest.json` 汇总本机官方样例运行证据。 |
| `autoform_result_inventory` | 检查运行目录或工作区里的结果类文件。 |
| `autoform_result_plan_review` | 把结果审阅请求整理成结构化计划。 |
| `autoform_result_set_view` | 规划或执行已验证的等轴测、俯视、正视和侧视快捷键。 |
| `autoform_result_play_forming_animation` | 使用受控播放 profile 或人工观察 profile。 |
| `autoform_gui_window_snapshot` | 列出可见 AutoForm 窗口和可交互窗口。 |
| `autoform_gui_restore_window` | 在审计型 GUI 动作前恢复可见 AutoForm 工程窗口。 |

MCP_V1.1 does not generate engineering pass/fail reports. It returns evidence, readiness checks, GUI boundaries, and review plans. Engineering threshold rules remain future optional input.

MCP_V1.1 不生成工程判断报告。它返回证据、就绪检查、GUI 边界和审阅计划。工程阈值规则属于后续可选输入。

## Portability Rules

Every computer must use its own repository path, Python environment path, AutoForm installation, and license. This repository does not include AutoForm software, AutoForm licenses, or proprietary example projects.

每台电脑都要使用自己的仓库路径、Python 环境路径、AutoForm 安装和许可证。本仓库不包含 AutoForm 软件、许可证或专有样例工程。

If automatic AutoForm discovery fails, copy `.env.example` to `.env` and fill only the paths that are different on that computer:

如果自动发现 AutoForm 失败，复制 `.env.example` 为 `.env`，只填写当前电脑上不同的路径：

```powershell
Copy-Item .env.example .env
```

## Tests

Use a project-local temp directory on Windows if the default temp folder has permission problems:

如果 Windows 默认临时目录权限异常，把临时目录放到项目内：

```powershell
$env:TEMP=(Resolve-Path .).Path + "\tmp\pytest_env"
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest tests\test_mcp_tools.py tests\test_gui_automation.py tests\test_result_viewer.py tests\test_r12_demo.py tests\test_project_workflow.py tests\test_process.py -q --basetemp tmp\pytest_mcp
```

Expected MCP_V1.1 result in this workspace:

当前工作区 MCP_V1.1 的预期结果：

```text
54 passed
```

## Project Layout

| Path | Meaning |
| --- | --- |
| `autoform_agent/mcp_server.py` | Stable stdio MCP entry point. |
| `autoform_agent/mcp_tools/` | Thin MCP wrappers grouped by tool family. |
| `autoform_agent/*.py` | Shared business functions used by MCP and CLI. |
| `tests/` | Focused MCP, GUI, result-review, process, and workflow tests. |
| `codex_mcp_config.autoform-mcp.toml` | Portable Codex/TOML MCP config template. |
| `environment.yml` | Conda environment used by the examples above. |
| `README.zh-CN.md` | Chinese-only usage guide. |

## Relationship To AUTO_AutoForm

`AUTO_AutoForm` can include this folder as a subproject so the larger Agent application has a local MCP capability. This folder can also be pushed as its own GitHub repository named `AutoForm_MCP`; the repository root should be this folder, not the full `AUTO_AutoForm` workspace.

`AUTO_AutoForm` 可以把本目录作为子项目包含进去，让完整 Agent 应用拥有本地 MCP 能力。本目录也可以单独推送为名叫 `AutoForm_MCP` 的 GitHub 仓库；独立仓库的根目录应该就是本目录，而不是整个 `AUTO_AutoForm` 工作区。
