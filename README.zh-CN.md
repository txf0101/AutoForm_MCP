# AutoForm_MCP 中文使用说明

版本：`MCP_V1.1`

## 先安装并连接 MCP

AutoForm_MCP 是一个可以独立运行的本地 stdio MCP server。它让 Codex、Claude Code、OpenCalw 或其他 MCP host 调用 AutoForm 辅助工具。下面的 `<repo-root>` 要替换成当前电脑上 `AutoForm_MCP` 文件夹的绝对路径。

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

如果你拿到的是完整 `AUTO_AutoForm` 工作区，不需要重新克隆，直接进入子目录：

```powershell
cd AutoForm_MCP
conda env create -f environment.yml
conda activate afagent
python -c "import autoform_agent.mcp_server; print('mcp import ok')"
```

## Codex 配置

把下面内容加入 `%USERPROFILE%\.codex\config.toml`：

```toml
[mcp_servers."autoform-mcp"]
command = 'conda'
args = ['run', '-n', 'afagent', 'python', '-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-mcp".env]
PYTHONPATH = '<repo-root>'
```

如果 Codex 找不到 `conda`，把 `command` 改成当前电脑上 `afagent` 环境里的 `python.exe`：

```toml
[mcp_servers."autoform-mcp"]
command = '<path-to-afagent-python.exe>'
args = ['-m', 'autoform_agent.mcp_server']
startup_timeout_sec = 60
enabled = true

[mcp_servers."autoform-mcp".env]
PYTHONPATH = '<repo-root>'
```

## Claude Code 配置

```powershell
claude mcp add --transport stdio --scope user --env PYTHONPATH="<repo-root>" autoform-mcp -- conda run -n afagent python -m autoform_agent.mcp_server
claude mcp list
claude mcp get autoform-mcp
```

如果引号不好处理，可以用 JSON：

```powershell
claude mcp add-json autoform-mcp '{"type":"stdio","command":"conda","args":["run","-n","afagent","python","-m","autoform_agent.mcp_server"],"env":{"PYTHONPATH":"<repo-root>"}}'
```

## OpenCalw 或其他 MCP 客户端

只要客户端支持 stdio MCP，就使用同样的 command、args 和 env：

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

## 连接后怎么确认正常

1. 读取 `autoform://status`，或调用 `autoform_status_snapshot`。
2. 调用 `autoform_discover_installation`，确认本机 AutoForm 安装是否被发现。
3. 调用 `autoform_result_blockers`，查看 MCP_V1.1 的结果审阅边界。
4. 在没有确认许可证、工程、输出目录和可见桌面之前，不要给执行类工具传 `execute=true`。

## 当前能力

MCP_V1.1 暴露 112 个 `autoform_` 工具，并提供 `autoform://status` 资源。常用工具包括：

| 工具 | 用途 |
| --- | --- |
| `autoform_status_snapshot` | 读取本机健康状态、AutoForm 安装发现、日志和能力覆盖。 |
| `autoform_discover_installation` | 查找本机 AutoForm Forming 安装和关键目录。 |
| `autoform_project_run` | 规划或执行复制后的 `.afd` 工程运行。真实执行需要 `execute=true`。 |
| `autoform_official_sample_run_summary` | 汇总本机官方样例运行证据。 |
| `autoform_result_plan_review` | 把结果审阅请求整理成结构化计划。 |
| `autoform_result_set_view` | 规划或执行已验证的视角快捷键。 |
| `autoform_result_play_forming_animation` | 使用受控播放 profile 或人工观察 profile。 |
| `autoform_gui_window_snapshot` | 列出可见 AutoForm 窗口和可交互窗口。 |

MCP_V1.1 不生成工程判断报告。它只返回证据、就绪检查、GUI 边界和审阅计划。

## 路径和移植规则

每台电脑都要使用自己的仓库路径、Python 环境路径、AutoForm 安装和许可证。本仓库不包含 AutoForm 软件、许可证或专有样例工程。

如果自动发现 AutoForm 失败，复制 `.env.example` 为 `.env`，只填写当前电脑上的真实路径：

```powershell
Copy-Item .env.example .env
```

## 测试

Windows 默认临时目录权限异常时，把临时目录放到项目内：

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

## 和 AUTO_AutoForm 的关系

`AUTO_AutoForm` 可以把本目录作为子项目包含进去，让完整 Agent 应用拥有本地 MCP 能力。本目录也可以单独推送成名为 `AutoForm_MCP` 的 GitHub 仓库。独立仓库只需要本目录里的源码、测试、README、环境文件、许可证和配置模板，不需要复制整个 `AUTO_AutoForm` 工作区。
