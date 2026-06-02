"""这个测试文件检查MCP 工具注册、工具数量和兼容入口。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks MCP tool registration, tool counts, and compatibility entry points. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from __future__ import annotations

import pytest

pytest.importorskip("mcp.server.fastmcp")


def test_mcp_server_registers_all_tool_layers() -> None:
    """The stable MCP entry point should still expose the V1.0 tool surface."""
    from autoform_agent import mcp_server
    from autoform_agent.mcp_tools import ALL_TOOL_FUNCTIONS, MCP_TOOL_LAYERS

    tool_names = set(mcp_server.mcp._tool_manager._tools)

    assert len(MCP_TOOL_LAYERS) == 13
    assert len(ALL_TOOL_FUNCTIONS) == 112
    assert len(tool_names) == 112
    assert "autoform_status_snapshot" in tool_names
    assert "autoform_project_run" in tool_names
    assert "autoform_official_sample_run_summary" in tool_names
    assert "autoform_module_coverage_matrix" in tool_names
    assert "autoform_gui_window_snapshot" in tool_names
    assert "autoform_gui_restore_window" in tool_names
    assert "autoform_gui_drag" in tool_names
    assert "autoform_computer_use_probe" in tool_names
    assert "autoform_gui_control_demo" in tool_names
    assert "autoform_r12_project_view_demo" in tool_names
    assert "autoform_result_show_variable" in tool_names
    assert "autoform_result_gui_evidence" in tool_names
    assert "autoform_result_blockers" in tool_names
    assert "autoform_result_view_evidence" in tool_names
    assert "autoform_result_route_task" in tool_names
    assert "autoform_result_plan_review" in tool_names
    assert "autoform_result_readiness" in tool_names


def test_mcp_server_keeps_status_resource_and_legacy_exports() -> None:
    """Existing imports from `mcp_server` should keep working after the split."""
    from autoform_agent import mcp_server

    resource_uris = set(mcp_server.mcp._resource_manager._resources)

    assert "autoform://status" in resource_uris
    assert mcp_server.autoform_project_run.__name__ == "autoform_project_run"
    assert mcp_server.autoform_status_snapshot.__name__ == "autoform_status_snapshot"
