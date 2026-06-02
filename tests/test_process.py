"""这个测试文件检查AutoForm 进程、求解器和 GUI 打开命令。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks AutoForm processes, solver commands, and GUI launch commands. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

from pathlib import Path

from autoform_agent.paths import AutoFormInstallation
from autoform_agent.process import collect_forming_job_logs, forming_job_plan, open_afd_observer


def _install(tmp_path: Path) -> AutoFormInstallation:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    return AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)


def test_forming_job_plan_uses_executable_and_working_dir(tmp_path: Path) -> None:
    install = _install(tmp_path)
    bin_dir = install.bin_dir
    (bin_dir / "AFFormingJob.exe").write_text("exe", encoding="utf-8")

    plan = forming_job_plan(["-example"], install=install, working_dir=tmp_path)

    assert plan["command"] == [str(bin_dir / "AFFormingJob.exe"), "-example"]
    assert plan["executable_exists"] is True
    assert plan["working_dir"] == str(tmp_path.resolve())


def test_collect_forming_job_logs_returns_preview(tmp_path: Path) -> None:
    log = tmp_path / "log_AFFormingJob_123.txt"
    log.write_text("first line\nsecond line", encoding="utf-8")

    logs = collect_forming_job_logs(tmp_path)

    assert len(logs) == 1
    assert logs[0]["name"] == "log_AFFormingJob_123.txt"
    assert logs[0]["preview"].startswith("first line")


def test_open_afd_observer_dry_run_records_visibility_boundary(tmp_path: Path) -> None:
    install = _install(tmp_path)
    project = tmp_path / "example.afd"
    project.write_text("afd", encoding="utf-8")

    observation = open_afd_observer(project, install=install, dry_run=True)

    assert observation["mode"] == "gui_project_observer"
    assert observation["dry_run"] is True
    assert observation["launched"] is False
    assert observation["command"] == [str(install.forming_ui), "-file", str(project.resolve())]
    assert observation["progress_visibility"] == "best_effort"
