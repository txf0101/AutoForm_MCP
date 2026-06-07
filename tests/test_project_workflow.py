"""这个测试文件检查工程解析、复制、求解和官方样例汇总。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks project resolution, copying, solver runs, and official-example summaries. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

import json
from pathlib import Path

import autoform_mcp_agent.project_workflow as workflow
from autoform_mcp_agent.paths import AutoFormInstallation
from autoform_mcp_agent.project_workflow import (
    example_project_baseline,
    official_sample_run_summary,
    project_run_workflow,
    resolve_project_input,
)


def _install(tmp_path: Path, monkeypatch) -> AutoFormInstallation:
    install_root = tmp_path / "AutoForm" / "AFplus" / "R13F"
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "AFFormingUI.exe").write_text("ui", encoding="utf-8")
    (bin_dir / "AFFormingSolver.exe").write_text("solver", encoding="utf-8")
    (bin_dir / "MBA_Trans.dll").write_text("dll", encoding="utf-8")
    test_dir = tmp_path / "ProgramData" / "AutoForm" / "AFplus" / "R13F" / "test"
    test_dir.mkdir(parents=True)
    (test_dir / "Solver_R13.afd").write_text("Project Name\0Solver Test", encoding="utf-8")
    monkeypatch.setenv("AUTOFORM_TEST_DIR", str(test_dir))
    return AutoFormInstallation("AutoForm Forming R13", "13.0.1.02", install_root)


def test_resolve_project_input_finds_official_example(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)

    resolved = resolve_project_input(example_name="Solver_R13", install=install)

    assert resolved["source"] == "official_example"
    assert resolved["name"] == "Solver_R13.afd"


def test_project_run_workflow_defaults_to_plan(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)

    result = project_run_workflow(
        example_name="Solver_R13",
        mode="kinematic",
        output_root=tmp_path / "runs",
        execute=False,
        install=install,
    )

    assert result["status"] == "planned"
    assert result["solver"]["executed"] is False
    assert result["gui_command"][0].endswith("AFFormingUI.exe")
    assert result["gui_observation"]["dry_run"] is True
    assert not Path(result["run_dir"]).exists()


def test_project_run_workflow_execute_copies_project_before_gui_plan(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)

    def fake_solver_probe(afd_path: Path, *_args, **_kwargs) -> dict:
        assert Path(afd_path).exists()
        return {"executed": True, "cases": [{"executed": True, "returncode": 0}]}

    monkeypatch.setattr(workflow, "_solver_probe", fake_solver_probe)
    monkeypatch.setattr(workflow, "result_inventory", lambda **_kwargs: {"items": []})
    monkeypatch.setattr(workflow, "report_delivery_plan", lambda _target, **_kwargs: {"written": True})

    result = project_run_workflow(
        example_name="Solver_R13",
        mode="kinematic",
        output_root=tmp_path / "runs",
        execute=True,
        install=install,
    )

    assert result["status"] == "completed"
    assert Path(result["working_project"]).exists()
    assert result["gui_command"][1] == "-file"
    assert result["gui_command"][2] == result["working_project"]
    assert result["gui_observation"]["dry_run"] is True


def test_project_run_workflow_open_gui_records_observer_launch(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)

    def fake_solver_probe(afd_path: Path, *_args, **_kwargs) -> dict:
        assert Path(afd_path).exists()
        return {"executed": True, "cases": [{"executed": True, "returncode": 0}]}

    def fake_open_afd_observer(afd_path: Path, *_args, dry_run: bool = True, **_kwargs) -> dict:
        return {
            "mode": "gui_project_observer",
            "dry_run": dry_run,
            "command": ["AFFormingUI.exe", "-file", str(Path(afd_path).resolve())],
            "launched": not dry_run,
            "pid": 1234 if not dry_run else None,
            "progress_visibility": "best_effort",
        }

    sleeps = []
    monkeypatch.setattr(workflow, "_solver_probe", fake_solver_probe)
    monkeypatch.setattr(workflow, "open_afd_observer", fake_open_afd_observer)
    monkeypatch.setattr(workflow.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(workflow, "result_inventory", lambda **_kwargs: {"items": []})
    monkeypatch.setattr(workflow, "report_delivery_plan", lambda _target, **_kwargs: {"written": True})

    result = project_run_workflow(
        example_name="Solver_R13",
        mode="kinematic",
        output_root=tmp_path / "runs",
        execute=True,
        open_gui=True,
        gui_wait_seconds=0.25,
        install=install,
    )

    assert result["status"] == "completed"
    assert result["gui_open_requested"] is True
    assert result["gui_observation"]["launched"] is True
    assert result["gui_observation"]["pid"] == 1234
    assert result["gui_observation"]["startup_wait_seconds"] == 0.25
    assert sleeps == [0.25]


def test_example_project_baseline_can_write(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path, monkeypatch)
    output = tmp_path / "baseline.json"

    baseline = example_project_baseline(output_path=output, install=install)

    assert baseline["example_count"] == 1
    assert baseline["examples"][0]["name"] == "Solver_R13.afd"
    assert output.exists()


def test_official_sample_run_summary_reports_latest_passed_runs(tmp_path: Path) -> None:
    old_run = tmp_path / "runs" / "old"
    new_run = tmp_path / "runs" / "new"
    old_run.mkdir(parents=True)
    new_run.mkdir(parents=True)
    _write_manifest(old_run, "Solver_R13.afd", returncode=1, created_at="2026-05-28T00:00:00+00:00")
    _write_manifest(new_run, "Solver_R13.afd", returncode=0, created_at="2026-05-29T00:00:00+00:00")

    summary = official_sample_run_summary(
        tmp_path / "runs",
        expected_examples=["Solver_R13.afd"],
    )

    assert summary["status"] == "all_expected_examples_passed"
    assert summary["covered_example_count"] == 1
    assert summary["passing_example_count"] == 1
    assert summary["examples"][0]["status"] == "passed"
    assert summary["examples"][0]["solver_returncode"] == 0
    assert "Simulation successfully finished" in summary["examples"][0]["stdout_evidence"][0]


def test_official_sample_run_summary_reports_missing_expected_example(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "solver"
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir, "Solver_R13.afd", returncode=0, created_at="2026-05-29T00:00:00+00:00")

    summary = official_sample_run_summary(
        tmp_path / "runs",
        expected_examples=["Solver_R13.afd", "Trim_R13.afd"],
    )

    assert summary["status"] == "incomplete_or_failed"
    assert summary["missing_examples"] == ["Trim_R13.afd"]
    assert summary["covered_example_count"] == 1


def _write_manifest(run_dir: Path, name: str, *, returncode: int, created_at: str) -> None:
    payload = {
        "created_at": created_at,
        "mode": "kinematic",
        "execute": True,
        "project": {"name": name},
        "run_dir": str(run_dir),
        "working_project": str(run_dir / name),
        "solver": {
            "cases": [
                {
                    "returncode": returncode,
                    "stdout_summary": {
                        "simulation_successful": returncode == 0,
                        "program_end": {"code": returncode},
                    },
                    "stdout_tail": [
                        "ct: Simulation successfully finished.",
                        f" ++++++ Program END [123 {returncode}].",
                    ],
                }
            ]
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
