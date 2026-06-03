# GUI Result Review Scope

This document explains the public V1.1 scope for AutoForm_MCP result review. It is written for people who install the standalone MCP server and want to know which GUI actions are supported, which actions are guarded, and which items remain future work.

本文件说明 AutoForm_MCP V1.1 在结果审阅方面的公开范围。它面向安装独立 MCP server 的用户，帮助用户理解哪些 GUI 操作已经接入，哪些操作带有保护条件，哪些内容留到后续版本。

## What V1.1 Includes

V1.1 provides these result review capabilities:

- Discover visible AutoForm windows and return title, process, rectangle and readiness facts.
- Focus, restore and screenshot AutoForm windows through explicit MCP calls.
- Open a supplied or recently produced `.afd` project through guarded execution paths.
- Map common result-review requests to result variables, view directions and review plans.
- Switch stable AutoForm R13 result views with verified shortcut profiles for isometric, top, front and side views.
- Capture before and after screenshots for visible result-review actions.
- Use a guarded AutoComp_R13 bottom-strip playback profile only when the window title, operation text and geometry checks match the known safe conditions.
- Fall back to manual playback observation when the project, window layout or target operation is different from the guarded profile.

V1.1 包含以下结果审阅能力：

- 发现可见的 AutoForm 窗口，并返回标题、进程、窗口位置和就绪状态。
- 通过显式 MCP 调用聚焦、恢复和截图 AutoForm 窗口。
- 在带保护条件的执行路径中打开用户指定或最近生成的 `.afd` 工程。
- 将常见结果审阅请求映射到结果变量、视角方向和审阅计划。
- 使用已验证的 AutoForm R13 快捷键配置切换等轴测、俯视、正视和侧视。
- 对可见的结果审阅动作采集前后截图。
- 仅在窗口标题、工序文本和窗口几何检查都匹配时，使用 AutoComp_R13 底部时间步控制条的受控播放配置。
- 当工程、窗口布局或目标工序不匹配受控配置时，退回到人工播放观察流程。

## Guarded GUI Boundary

AutoForm_MCP treats visible GUI control as a high risk boundary. A tool that may move the AutoForm GUI keeps one or more of these controls:

- `dry_run` defaults for planning-only behavior.
- explicit `execute=true` before sending GUI actions.
- AutoForm window title and class checks.
- window rectangle stability checks before and after a click.
- result-view screenshot difference checks.
- screenshot-first recovery instructions when a visible dialog blocks the workflow.

AutoForm_MCP 将可见 GUI 控制视为高风险边界。可能移动 AutoForm GUI 的工具会保留以下一种或多种保护：

- 默认 `dry_run`，先返回计划而不执行动作。
- 只有显式传入 `execute=true` 后才发送 GUI 动作。
- 检查 AutoForm 窗口标题和窗口类名。
- 点击前后检查窗口矩形是否稳定。
- 对结果视图区做截图差异检查。
- 当可见弹窗阻塞流程时，先截图，再给出恢复建议。

## Deferred Items

These items are outside the public V1.1 scope:

- generalized coordinate automation for every AutoForm result window layout.
- toolbar-only fit-window automation.
- direct reset-button discovery beyond the verified isometric shortcut surrogate.
- exact result frame-count reading.
- engineering pass/fail report generation.
- threshold rule templates for minimum thickness, thinning, FLD, springback deviation, force and material-flow judgments.

以下内容不纳入公开 V1.1 范围：

- 面向所有 AutoForm 结果窗口布局的通用坐标自动化。
- 只依赖工具栏定位的适合窗口自动化。
- 超出已验证等轴测快捷键替代方案的直接复位按钮发现。
- 精确结果帧数读取。
- 工程 pass/fail 报告生成。
- 最小厚度、减薄率、FLD、回弹偏差、载荷和材料流动判断阈值模板。

## Portable Path Rules

The standalone repository does not assume a private workstation path. Installation discovery uses these sources:

- `AUTOFORM_INSTALL_DIR` when the user sets it.
- Windows registry entries when available.
- `ProgramFiles` and `ProgramFiles(x86)` environment locations as conservative fallbacks.

Generated screenshots, copied evidence, temporary pytest data and release package output are written under ignored folders such as `tmp/`, `output/`, `.pytest_cache/` or `autoform_agent_data/`. Those folders are runtime output and are not part of the public repository.

独立仓库不假定某台电脑上的私人路径。安装发现使用以下来源：

- 用户设置的 `AUTOFORM_INSTALL_DIR`。
- 可读取时使用 Windows 注册表。
- 将 `ProgramFiles` 和 `ProgramFiles(x86)` 环境位置作为保守兜底。

截图、复制的证据、pytest 临时数据和发布包输出会写入 `tmp/`、`output/`、`.pytest_cache/` 或 `autoform_agent_data/` 等已忽略目录。这些目录属于运行输出，不属于公开仓库内容。

## Repository Evidence

The public repository keeps the implementation and tests needed to verify this scope:

- `autoform_agent/gui_automation.py` contains the low level visible-window primitives.
- `autoform_agent/result_viewer.py` contains result variable mapping, view switching, readiness checks and animation observation logic.
- `autoform_agent/mcp_tools/gui.py` exposes the GUI and result-review functions as MCP tools.
- `tests/test_result_viewer.py` covers readiness blocking, manual playback observation, guarded click behavior, visual-change validation and geometry-change rejection.
- `tests/test_gui_automation.py` covers window control planning and visible-window guard behavior.

公开仓库保留了验证上述范围所需的实现和测试：

- `autoform_agent/gui_automation.py` 包含可见窗口底层控制能力。
- `autoform_agent/result_viewer.py` 包含结果变量映射、视角切换、就绪检查和动画观察逻辑。
- `autoform_agent/mcp_tools/gui.py` 将 GUI 和结果审阅功能暴露为 MCP 工具。
- `tests/test_result_viewer.py` 覆盖就绪阻塞、人工播放观察、受控点击、视觉变化校验和窗口几何变化拒绝。
- `tests/test_gui_automation.py` 覆盖窗口控制计划和可见窗口保护行为。
