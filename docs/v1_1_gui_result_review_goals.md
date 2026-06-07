# V1.1 GUI 结果审阅与傻瓜式后处理目标

本文档定义 AutoForm Agent V1.1 的开发目标。目标来自当前仓库源码、本机 AutoForm R13 安装证据、已经验证的 GUI 操作实验，以及用户对傻瓜式后处理操作的明确要求。

## 一、版本定位

V1.1 的核心目标是让 MCP 具备面向 AutoForm 后处理的稳定演示能力。用户发出自然语言指令后，Agent 应能通过 MCP 工具打开结果工程、映射结果栏目、调整已验证视角、观察冲压过程动画，并返回可检查的截图或状态证据。

典型用户指令如下：

```text
打开刚才跑完的结果，切到流入量，给我看等轴测视角。
```

```text
把冲压成形过程动画播放给我看。
```

```text
切到拆分结果，再切到 D-20，帮我截一张图。
```

2026-06-01 范围冻结后，V1.1 采用“稳定演示优先”的边界：快捷键可稳定触发的等轴测、俯视、正视和侧视纳入自动视角切换。2026-06-02 的实机取证进一步确认，`autocomp_r13_bottom_strip` 可在本机 AutoComp_R13 结果窗口中完成受控播放点击，并在窗口几何稳定条件下通过结果视图区差异校验；`manual_user_playback` 保留为布局不匹配时的人工 fallback。受 UI 格局影响的跨工程精确按钮、坐标和滑条定位移入 V1.2 或更后续版本。

## 二、当前依据

当前已经具备以下本机与源码依据：

| 能力或事实 | 依据 |
| --- | --- |
| MCP 已能运行工程并打开 GUI 观察窗口 | `autoform_mcp_agent/mcp_tools/project.py` 中的 `autoform_project_run(open_gui=True)` |
| CLI 已有窗口枚举、恢复、聚焦、截图、坐标点击能力 | `autoform_mcp_agent/gui_automation.py` 与 `autoform_mcp_agent/cli.py` 中的 `gui-window-snapshot`、`gui-restore-window`、`gui-focus`、`gui-screenshot`、`gui-click` |
| AutoForm 帮助映射包含结果页入口 | `D:\Program Files\AutoForm\AFplus\R13F\help\helpLinks.cfg` 中的 `SolverResultsPagePresenter`、`PostProcessingPagePresenter`、`EvaluationAreaEditor` |
| AutoForm 帮助映射包含部分评估结果栏目 | 同一文件中的 `SplitsPresenter`、`DrawInPresenter`、`EvalSpringbackPresenter`、`SurfacePresenter`、`ProcessTotalForcesPresenter` |
| 当前窗口枚举和恢复命令可稳定返回 JSON | `python -m autoform_mcp_agent.cli gui-window-snapshot` 返回窗口标题、句柄、进程号、矩形和 `interaction_ready`；`python -m autoform_mcp_agent.cli gui-restore-window --wait 0` 在窗口已就绪时返回 `already_ready` |
| 当前 MCP 已接入 GUI 和结果审阅工具层 | `autoform_mcp_agent/mcp_tools/__init__.py` 当前注册 status、project、jobs、materials、quicklink、environment、queue、solver、commands、reporting、release、reference 和 gui 共 13 个工具层，工具总数为 112 |
| 官方样例可作为结果审阅输入 | 本轮 7 个本机 R13 官方样例均已有运动学运行证据；`official-sample-run-summary --search-dir output\project_runs --mode kinematic` 读取 23 个运行清单并返回 `status=all_expected_examples_passed`、`covered_example_count=7` 和 `passing_example_count=7`；最新 `Solver_R13` 运行目录为 `output/project_runs/v1_1_20260531_live/20260531_152442_Solver_R13_kinematic` |
| P1 高层审阅计划已形成结构化入口 | `autoform_mcp_agent/result_viewer.py` 的 `build_result_review_plan()`、CLI `result-plan`、MCP `autoform_result_plan_review` 和 Agent runtime `autoform_result_review_plan_tool` |
| GUI 就绪诊断已形成结构化入口 | `autoform_mcp_agent/result_viewer.py` 的 `assess_result_review_readiness()`、CLI `result-readiness`、MCP `autoform_result_readiness` 和 Agent runtime `autoform_result_readiness_tool` |
| 桌面观察就绪探针已形成结构化入口 | `autoform_mcp_agent/gui_automation.py` 的 `computer_use_probe()`、CLI `computer-use-probe`、MCP `autoform_computer_use_probe` 和 Agent runtime `autoform_computer_use_probe_tool`；当前会话截图尝试返回 `screen grab failed` |
| GUI 控件证据登记已形成结构化入口 | `autoform_mcp_agent/result_viewer.py` 的 `result_gui_evidence()`、CLI `result-gui-evidence`、MCP `autoform_result_gui_evidence` 和 Agent runtime `autoform_result_gui_evidence_tool` |
| 输出时间步设置已有本机 GUI 证据 | `output/project_runs/frame_rate_experiment/AutoComp_R13_every_time_step_20260531_185003/run_recap.md` 记录了 `Simulation > Control > Output`、`每一时间步`、`Apply`、保存、重算和 Job Log 成功结果 |
| 底部时间步播放控件已有本机结果证据 | 同一 `run_recap.md` 记录了最终结果中底部时间步长控制条可以播放 `D-20 Drawing` 中间变形并切换到 `D-20 Springback` 末端状态 |
| 动画播放已有受控 MCP 执行分支、人工播放观察分支和视觉校验 | `autoform_result_play_forming_animation` 可在 `execute=true` 时使用 `autocomp_r13_bottom_strip` profile，经窗口标题和工序检查后调用 Win32 GUI 原语点击；2026-06-02 证据目录 `tmp/result_review_auto_play_v1_1_geometry_guard_probe` 显示窗口矩形稳定且结果视图区差异达到阈值；`manual_user_playback` 作为人工 fallback 保留 |
| 视角切换取证已有准备入口，主要快捷键已验证 | `autoform_mcp_agent/result_viewer.py` 的 `view_control_evidence_protocol()`、CLI `result-view-evidence`、MCP `autoform_result_view_evidence` 和 Agent runtime `autoform_result_view_evidence_tool` 已覆盖等轴测、俯视、正视、侧视、适合窗口和复位的 before、after、compare 流程；2026-06-01 对 AutoComp_R13 窗口实测确认 `E`、`Z`、`X` 和 `Shift+Y` 自动切换有效 |

动画播放入口已有 AutoComp_R13 底部时间步控制条的本机观察证据，并已接入受控 MCP 执行分支、人工播放观察分支和结果视图区截图差异校验。2026-05-31 的本机实测记录了默认点击和右侧点击覆盖的失败证据。2026-06-02 在补充窗口恢复和窗口几何稳定性闸门后，`autocomp_r13_bottom_strip` profile 返回 `played_with_guarded_mcp_click_profile`，证据目录为 `tmp/result_review_auto_play_v1_1_geometry_guard_probe`，结果视图区 `changed_pixel_ratio=0.2101411782097716`、`mean_delta=19.197265134156257`。当前剩余缺口集中在跨工程播放控件泛化、精确帧数读取和坐标式结果栏目切换，进入 V1.2 或更后续版本。

## 三、V1.1 交付范围

### 1. GUI 基础工具层

新增 MCP 工具层：

```text
autoform_mcp_agent/mcp_tools/gui.py
```

建议暴露以下低层工具：

| MCP 工具 | 目标 |
| --- | --- |
| `autoform_gui_window_snapshot` | 列出可见 AutoForm 窗口、标题、句柄、进程号和位置 |
| `autoform_gui_restore_window` | 恢复可见 AutoForm 项目窗口，并复核是否达到可交互尺寸和屏幕位置 |
| `autoform_gui_focus` | 聚焦指定 AutoForm 窗口，默认优先选择当前结果工程窗口 |
| `autoform_gui_screenshot` | 抓取当前桌面或 AutoForm 窗口截图，返回图片路径和窗口信息 |
| `autoform_gui_click` | 在指定 AutoForm 窗口中按相对坐标或绝对坐标点击 |
| `autoform_gui_drag` | 在指定 AutoForm 窗口中按相对坐标或绝对坐标拖动，用于后续验证底部滑条扫帧 |
| `autoform_computer_use_probe` | 探测当前会话是否能看到 AutoForm 窗口和抓取桌面截图 |
| `autoform_gui_control_demo` | 规划或显式执行 R12 基础可见窗口控制演示切片，默认只返回窗口快照、来源依据、执行边界和计划阶段 |
| `autoform_result_gui_evidence` | 返回本机控件证据、证据文件存在性、V1.1 卡点和 V1.2 延后项 |
| `autoform_result_blockers` | 返回当前卡点、推荐对策、进度估算和需要用户协助的事项 |
| `autoform_result_view_evidence` | 返回视角切换取证计划，或记录人工切换前后的截图并执行视图区差异校验 |

这些工具是可见桌面操作的基础设施。它们需要保留 `dry_run` 或显式执行参数，并且默认只作用于 AutoForm 窗口。

### 2. 结果工程打开工具

新增高层 MCP 工具：

```text
autoform_result_open_latest
autoform_result_open_project
```

目标行为：

1. 从最近一次 `project-run` 输出目录或用户指定目录定位 `.afd` 结果工程。
2. 打开 AutoForm Forming 结果窗口。
3. 等待窗口可见。
4. 返回窗口句柄、进程号、工程路径、截图路径和运行清单路径。

验收指令：

```text
打开刚才跑完的结果。
```

Agent 应完成打开操作，并返回当前 AutoForm 结果窗口截图。

### 3. 结果栏目映射工具

新增高层 MCP 工具：

```text
autoform_result_show_variable
```

建议参数：

```json
{
  "result_name": "流入量",
  "operation": "D-20",
  "project_hint": "latest",
  "verify_screenshot": true
}
```

V1.1 需要维护一份结果栏目语义映射表。坐标式栏目切换受左侧面板布局影响，移入 V1.2；V1.1 返回语义映射、审阅路线、建议截图字段和需要人工确认的证据边界。第一版映射建议如下：

| 用户说法 | AutoForm 入口依据 | V1.1 初始动作 |
| --- | --- | --- |
| 总览、OV、评估总览 | `PostProcessingPagePresenter`、`EvaluationAreaEditor` | 返回评估页与 `OV` 页签候选 |
| 拆分、开裂、破裂、成形性 | `SplitsPresenter` | 返回左侧拆分栏目候选 |
| 高级 FLD | `SplitsPresenter[Advanced FLD_Button]` | 返回高级 FLD 子项候选 |
| 表面失效 | `SplitsPresenter[Surface Failure_Button]` | 返回表面失效子项候选 |
| 流入量、拉入量、Draw In | `DrawInPresenter` | 返回左侧流入量栏目候选 |
| 滑移线 | `MaterialFlowSkidLinesPresenter` | 返回滑移线栏目候选 |
| 回弹 | `EvalSpringbackPresenter` | 返回回弹栏目候选 |
| 回弹结果 | `EvalSpringbackOperationPresenter[m_resultsPage]` | 返回回弹结果页候选 |
| 表面 | `SurfacePresenter` | 返回表面栏目候选 |
| 力、总力、工具力 | `ProcessDataGeneralPresenter`、`ProcessTotalForcesPresenter`、`ProcessDataToolPresenter` | 返回力相关栏目候选 |
| 求解结果页 | `SolverResultsPagePresenter` | 返回 Simulation 控制结果页候选 |

该工具需要返回：

1. 目标结果栏目。
2. 目标工序或页签。
3. 截图证据需求。
4. 若识别失败，返回失败原因和下一步可尝试的控件候选。

### 4. 结果视角控制工具

新增高层 MCP 工具：

```text
autoform_result_set_view
autoform_result_view_evidence
```

建议支持以下视角：

| 用户说法 | 目标行为 |
| --- | --- |
| 等轴测、三维视角 | 切到 3D 等轴测视角 |
| 俯视 | 切到上视角 |
| 正视 | 切到前视角 |
| 侧视 | 切到左视或右视 |
| 放大结果区域 | V1.1 仅保留人工证据和计划返回，工具栏自动化移入 V1.2 |
| 旋转一点 | V1.1 仅保留计划返回，小幅拖拽旋转移入 V1.2 |

当前源码中已有坐标点击和截图能力。2026-06-01 本机 AutoForm R13 实测已确认主要视角菜单名：等轴测为 `等轴测视图`，俯视为 `+Z向视图`，正视为 `+X向视图`，侧视为 `-Y向视图`，适合窗口为工具栏控件；复位视角暂采用 `等轴测视图` 和快捷键 `E` 作为替代路径。V1.1 自动执行只采用可复现的快捷键 profile：`E`、`Z`、`X` 和 `Shift+Y`。工具栏 `适合窗口`、独立复位按钮和坐标回退路径受 UI 格局影响，移入 V1.2 或更后续版本。

本轮新增 `autoform_result_view_evidence` 作为取证入口。`plan` 阶段会列出 `isometric`、`top`、`front`、`side`、`fit` 和 `reset` 六个目标视角，并返回 R13 菜单名、快捷键和证据状态；`before` 阶段由 MCP 抓取用户操作前截图；用户手动切换 AutoForm 视角后，`after` 阶段抓取操作后截图；`compare` 阶段读取 `view_control_evidence_records.jsonl` 并对结果视图区裁剪区域做像素差异校验。`autoform_result_set_view` 在 `execute=true` 时可对已有快捷键 profile 执行受控按键，但会先检查 `interaction_ready_window_count`，避免对最小化、离屏或尺寸过小的 AutoForm 句柄发送输入。2026-06-01 对 AutoComp_R13 窗口的实测已确认 `+Z向视图`、`+X向视图`、`-Y向视图` 和 `等轴测视图` 的自动快捷键切换。`fit` 和直接 `reset` 的按钮级自动化保留取证资料，当前不计入 V1.1 关闭项。

### 5. 冲压动画播放工具

新增高层 MCP 工具：

```text
autoform_result_play_forming_animation
```

建议参数：

```json
{
  "operation": "D-20",
  "duration_seconds": 8,
  "capture": "screenshots",
  "view": "isometric"
}
```

目标行为：

1. 打开最近结果工程。
2. 切到评估或求解结果中的成形过程视图。
3. 选择指定工序。
4. 找到动画播放控件或等价快捷键。
5. 播放指定时长。
6. 在播放开始、中间、结束分别抓取截图，必要时生成短视频或动图。
7. 返回操作证据，包括窗口、结果项、播放状态、截图或视频路径。

动画播放是 V1.1 的关键验收项。第一阶段已经形成 AutoComp_R13 底部播放控件的观察证据，提供 `autocomp_r13_bottom_strip` 受控执行 profile，并新增 `manual_user_playback` 人工播放观察 profile 和 `autoform_gui_drag` 底部滑条扫帧低层原语。2026-06-02 的本机 AutoComp_R13 取证显示，`autocomp_r13_bottom_strip` 可在窗口几何稳定条件下返回 `played_with_guarded_mcp_click_profile`，并通过结果视图区截图差异校验；窗口或工程布局不匹配时，`manual_user_playback` 作为 fallback。后续要把证据扩展到更多工程和更强读数能力，至少补齐以下 V1.2 材料：

1. AutoForm GUI 日志中与播放按钮、时间步、增量条或动画控制相关的控件路径。
2. 一组手动播放时的截图，用于确定按钮位置和状态变化。
3. 若存在快捷键，记录快捷键来源和执行效果。
4. 若需要坐标回退，记录窗口尺寸、DPI、按钮相对坐标、拖动起止点和失败检测方式。
5. 将 `tmp/result_review_validation`、`tmp/result_review_validation_right_icon` 和 `tmp/result_review_drag_probe` 的截图差异结果纳入下一轮定位判断，避免把下方控件区域变化误判为动画播放。
6. 将 `autocomp_r13_bottom_strip` 的窗口几何闸门和结果视图区差异校验扩展到更多工程布局。

## 四、用户指令到工具编排

V1.1 的交互应采用高层工具优先、低层工具回退的编排方式。

示例一：

```text
把刚才的结果打开，切到流入量。
```

预期工具序列：

1. `autoform_result_open_latest`
2. `autoform_result_show_variable(result_name="流入量")`
3. `autoform_gui_screenshot`

示例二：

```text
播放冲压动画给我看。
```

预期工具序列：

1. `autoform_result_open_latest`
2. `autoform_result_set_view(view="isometric")`
3. `autoform_result_play_forming_animation(duration_seconds=8)`
4. `autoform_gui_screenshot` 或视频导出工具

示例三：

```text
切到拆分结果，换成俯视角，然后截图。
```

预期工具序列：

1. `autoform_result_open_latest`
2. `autoform_result_show_variable(result_name="拆分")`
3. `autoform_result_set_view(view="top")`
4. `autoform_gui_screenshot`

## 五、工程结构建议

建议新增以下文件：

```text
autoform_mcp_agent/result_viewer.py
autoform_mcp_agent/mcp_tools/gui.py
tests/test_gui_automation.py
tests/test_result_viewer.py
tests/test_mcp_tools.py
docs/v1_1_gui_result_review_goals.md
```

职责划分：

| 文件 | 职责 |
| --- | --- |
| `gui_automation.py` | 保留 Win32 窗口枚举、聚焦、截图和坐标点击等低层动作 |
| `result_viewer.py` | 维护结果工程定位、结果栏目映射、视角控制和动画播放编排 |
| `mcp_tools/gui.py` | 将低层和高层 GUI 能力以 MCP 工具形式暴露 |
| `tests/test_mcp_tools.py` | 验证 MCP 工具注册、参数默认值和安全边界 |
| `tests/test_result_viewer.py` | 验证结果栏目语义映射、最近结果定位和失败返回结构 |

## 六、安全边界与可维护要求

V1.1 的 GUI 工具会操作真实桌面窗口，需要保留以下约束：

1. 默认只匹配 `AFFormingUI.exe` 窗口。
2. 点击前返回目标窗口标题、句柄、进程号和坐标。
3. 涉及真实点击、播放和截图时需要显式执行参数。
4. 截图默认写入 `tmp/` 或 `output/`，这些目录已由 `.gitignore` 排除。
5. 每个高层工具都要返回操作前后证据，至少包含截图路径或 GUI 日志事件。
6. 结果正确性仍以求解器返回码、stdout 摘要、`.afd` 文件、`run_manifest.json` 和结果证据包为依据。
7. 新增函数必须写清楚输入、输出、可见副作用和失败原因。

## 七、验收标准

V1.1 最小可验收标准如下：

1. MCP 注册表新增 GUI 工具层，`tests/test_mcp_tools.py` 或新增测试能确认工具数量和工具名。
2. `autoform_project_run(open_gui=True)` 后，Agent 能通过 MCP 打开最近结果，并返回结果栏目映射或证据边界。
3. 用户说“流入量”“拆分”“回弹”“力”时，工具能映射到稳定的 AutoForm 结果栏目和审阅路线。
4. 用户说“等轴测”“俯视”“正视”“侧视”时，工具能使用已验证快捷键调整当前结果视角，并通过截图确认视图变化。
5. 用户说“播放冲压动画”时，V1.1 对本机 AutoComp_R13 使用 `autocomp_r13_bottom_strip` 受控 profile；窗口或工程布局不匹配时使用 `manual_user_playback` fallback。两条路径都必须完成前后截图和结果视图区差异校验，并在 JSON 中记录执行边界。
6. 每个真实 GUI 动作都有前后截图或日志事件作为证据。
7. 全量测试通过，至少包含 MCP 注册、语义映射、最近结果定位、窗口选择和安全默认值测试。

## 八、建议开发顺序

1. 把现有 CLI GUI 辅助能力接入 MCP：窗口快照、聚焦、截图、点击。
2. 新增 `result_viewer.py`，实现最近运行结果定位和结果栏目语义映射。
3. 基于 7 个已验证的本机 R13 官方示例，建立结果栏目切换回归检查。覆盖状态优先通过 `official-sample-run-summary` 读取本地 `run_manifest.json` 复核。
4. 用 `autocomp_r13_bottom_strip` 完成一次本机 AutoComp_R13 V1.1 真实演示证据包，并保留 `manual_user_playback` fallback。
5. 将工具栏适合窗口、独立复位按钮、结果栏目坐标切换、跨工程自动播放定位器和精确帧数读取整理为 V1.2 工作包。
6. 将高层工具接入多 Agent 角色。建议新增或扩展 `result_review` 角色，并更新 `docs/multi_agent_architecture.md`。
7. 更新 README、中文新手文档、开发者指南、API runtime 调用链说明和版本记录。

## 九、版本结论

V1.1 应把稳定可演示的后处理审阅闭环作为核心交付。MCP 需要承担结果工程定位、结果栏目语义映射、已验证快捷键视角控制、受控动画播放、manual fallback、截图回传和证据记录。当前仓库已经具备底层 GUI 操作原型、窗口恢复能力、工程运行能力、输出时间步设置证据、AutoComp_R13 底部时间步控件证据、受控 MCP 点击 profile、拖动原语、视角快捷键 profile 和结果视图区视觉校验。受 UI 格局影响的跨工程精确按钮、坐标、滑条和帧数读取能力进入 V1.2 或更后续版本。

工程判断报告属于 V1.2 或更后续版本的可选输入项，不纳入当前 V1.1 验收范围。当前已提供 `schemas/result_review_report_rules_v1_1.schema.json` 和 `fixtures/result_review_report_rules_template_v1_1.json`，用于后续填写最小厚度、减薄率、FLD 风险、回弹偏差、最大力和材料流动异常等阈值。未填写阈值时，工具只输出证据包和待判定项，不给出工程 pass/fail 结论。
