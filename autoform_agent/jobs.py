"""这个文件管理本地作业生命周期：提交、查看状态、等待、取消、看日志和归档。

This file manages the local job lifecycle: submit, status, wait, cancel, logs, and archive.

作业登记使用文件保存，CLI、MCP 和后续界面都能读取同一份记录，不需要一直保持某个 Python 进程不退出。

The registry is file-based so CLI, MCP, and future UI calls can inspect the same records without keeping one Python process alive.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
from uuid import uuid4

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime guard
    psutil = None


JOB_SCHEMA_VERSION = "1.0"
DEFAULT_JOB_ROOT = Path("autoform_agent_data") / "jobs"
TEXT_PREVIEW_EXTENSIONS = {".log", ".txt", ".out", ".err", ".json"}


def submit_job(
    command: list[str],
    *,
    job_name: str | None = None,
    working_dir: str | Path | None = None,
    job_root: str | Path | None = None,
    execute: bool = False,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Plan or start one external AutoForm-related command.

    `execute=False` is the default because AutoForm jobs may consume licenses or
    modify project files.  When execution is requested, stdout and stderr are
    redirected into the job directory and a manifest is written immediately.
    """

    if not command:
        raise ValueError("command must not be empty")

    resolved_working_dir = Path(working_dir or Path.cwd()).resolve()
    job_id = _new_job_id(job_name)
    job_dir = _job_root(job_root) / job_id
    manifest = {
        "schema_version": JOB_SCHEMA_VERSION,
        "job_id": job_id,
        "job_name": job_name,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "status": "planned",
        "command": [str(item) for item in command],
        "working_dir": str(resolved_working_dir),
        "job_dir": str(job_dir.resolve()),
        "stdout_path": str((job_dir / "stdout.txt").resolve()),
        "stderr_path": str((job_dir / "stderr.txt").resolve()),
        "extra_env_keys": sorted(extra_env) if extra_env else [],
        "execute_requested": execute,
    }
    if not execute:
        return {**manifest, "dry_run": True}

    job_dir.mkdir(parents=True, exist_ok=True)
    stdout_handle = (job_dir / "stdout.txt").open("w", encoding="utf-8", errors="replace")
    stderr_handle = (job_dir / "stderr.txt").open("w", encoding="utf-8", errors="replace")
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(resolved_working_dir),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    finally:
        # Handles are safely owned by the child process after Popen returns; the
        # parent closes its descriptors so Windows can flush them when the child
        # exits.
        stdout_handle.close()
        stderr_handle.close()

    manifest.update(
        {
            "dry_run": False,
            "status": "running",
            "pid": process.pid,
            "started_at": _utc_now(),
        }
    )
    _write_manifest(job_dir, manifest)
    return manifest


def job_status(job_id: str, *, job_root: str | Path | None = None) -> dict:
    """Return the latest known status for one registered job."""

    manifest = _read_manifest(job_id, job_root)
    status = _refresh_process_status(manifest)
    _write_manifest(Path(status["job_dir"]), status)
    return status


def wait_for_job(job_id: str, *, timeout: float | None = None, job_root: str | Path | None = None) -> dict:
    """Wait for one registered process and persist its final status."""

    manifest = _read_manifest(job_id, job_root)
    pid = manifest.get("pid")
    if pid is None:
        return _update_manifest(manifest, status="not_started", wait_error="job has no pid")
    process = _get_process(pid)
    if process is None:
        return job_status(job_id, job_root=job_root)
    try:
        returncode = process.wait(timeout=timeout)
    except Exception as exc:
        return _update_manifest(manifest, status="running", wait_error=str(exc))
    return _update_manifest(
        manifest,
        status="completed" if returncode == 0 else "failed",
        returncode=returncode,
        finished_at=_utc_now(),
    )


def cancel_job(job_id: str, *, force: bool = False, job_root: str | Path | None = None) -> dict:
    """Request termination for a registered job and update the manifest."""

    manifest = _read_manifest(job_id, job_root)
    pid = manifest.get("pid")
    if pid is None:
        return _update_manifest(manifest, status="not_started", cancel_error="job has no pid")
    process = _get_process(pid)
    if process is None:
        return job_status(job_id, job_root=job_root)
    try:
        if force:
            process.kill()
        else:
            process.terminate()
    except Exception as exc:
        return _update_manifest(manifest, status=manifest.get("status", "unknown"), cancel_error=str(exc))
    return _update_manifest(manifest, status="cancel_requested", cancel_requested_at=_utc_now(), cancel_force=force)


def job_logs(job_id: str, *, job_root: str | Path | None = None, preview_bytes: int = 2048) -> dict:
    """Return stdout, stderr and nearby AutoForm log file facts for a job."""

    manifest = _read_manifest(job_id, job_root)
    paths = [
        Path(manifest["stdout_path"]),
        Path(manifest["stderr_path"]),
    ]
    paths.extend(_nearby_log_files(Path(manifest["job_dir"])))
    paths.extend(_nearby_log_files(Path(manifest["working_dir"])))
    return {
        "job_id": job_id,
        "log_count": len({str(path.resolve()).casefold() for path in paths if path.exists()}),
        "logs": _file_records(paths, preview_bytes=preview_bytes),
    }


def archive_job(
    job_id: str,
    output_dir: str | Path,
    *,
    job_root: str | Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Plan or create a compact archive directory for one job record."""

    manifest = job_status(job_id, job_root=job_root)
    destination = Path(output_dir).resolve() / job_id
    files = [Path(manifest["job_dir"]) / "job.json"]
    files.extend(Path(item["path"]) for item in job_logs(job_id, job_root=job_root, preview_bytes=0)["logs"])
    planned_files = [
        {
            "source": str(path.resolve()),
            "destination": str(destination / path.name),
            "exists": path.exists(),
        }
        for path in _dedupe_paths(files)
    ]
    plan = {
        "job_id": job_id,
        "destination": str(destination),
        "dry_run": dry_run,
        "planned_files": planned_files,
    }
    if dry_run:
        return plan
    destination.mkdir(parents=True, exist_ok=True)
    for item in planned_files:
        source = Path(item["source"])
        if source.exists():
            shutil.copy2(source, item["destination"])
    (destination / "archive_manifest.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return plan


def list_jobs(*, job_root: str | Path | None = None) -> list[dict]:
    """Return all known job manifests, newest first."""

    root = _job_root(job_root)
    if not root.exists():
        return []
    jobs = []
    for manifest in sorted(root.glob("*/job.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            jobs.append(job_status(manifest.parent.name, job_root=root))
        except Exception:
            continue
    return jobs


def _job_root(job_root: str | Path | None) -> Path:
    """Resolve the registry root used for job manifests."""
    return Path(job_root or DEFAULT_JOB_ROOT).resolve()


def _new_job_id(job_name: str | None) -> str:
    """Build a sortable, filesystem-safe job id."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in (job_name or "autoform-job"))
    return f"{stamp}-{safe_name[:32]}-{uuid4().hex[:8]}"


def _manifest_path(job_id: str, job_root: str | Path | None) -> Path:
    """Return the manifest path for one job id."""
    return _job_root(job_root) / job_id / "job.json"


def _read_manifest(job_id: str, job_root: str | Path | None) -> dict:
    """Load one job manifest or raise a clear file error."""
    path = _manifest_path(job_id, job_root)
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(job_dir: Path, manifest: dict) -> None:
    """Persist a job manifest with stable UTF-8 JSON."""
    job_dir.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = _utc_now()
    (job_dir / "job.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_manifest(manifest: dict, **updates: Any) -> dict:
    """Apply updates and persist the manifest."""
    manifest.update(updates)
    _write_manifest(Path(manifest["job_dir"]), manifest)
    return manifest


def _refresh_process_status(manifest: dict) -> dict:
    """Inspect the pid and update running or finished state when possible."""
    if manifest.get("dry_run"):
        return manifest
    pid = manifest.get("pid")
    if pid is None:
        return manifest
    process = _get_process(pid)
    if process is None:
        if manifest.get("status") == "running":
            return _manifest_copy(manifest, status="exited_unobserved", observed_at=_utc_now())
        return manifest
    if process.is_running() and process.status() != "zombie":
        return _manifest_copy(manifest, status="running", observed_at=_utc_now())
    return _manifest_copy(manifest, status="exited_unobserved", observed_at=_utc_now())


def _manifest_copy(manifest: dict, **updates: Any) -> dict:
    """Return an updated manifest copy without writing it."""
    copied = dict(manifest)
    copied.update(updates)
    return copied


def _get_process(pid: int):
    """Return a psutil process object when the optional dependency is usable."""
    if psutil is None:
        return None
    try:
        return psutil.Process(int(pid))
    except Exception:
        return None


def _nearby_log_files(root: Path) -> list[Path]:
    """Collect AutoForm-like logs in one directory without recursive scanning."""
    if not root.exists() or not root.is_dir():
        return []
    return [
        path
        for path in root.iterdir()
        if path.is_file() and (path.name.startswith("log_AF") or path.suffix.lower() in {".out", ".err"})
    ]


def _file_records(paths: list[Path], preview_bytes: int) -> list[dict]:
    """Return de-duplicated file records with bounded text previews."""
    records = []
    for path in _dedupe_paths(paths):
        if not path.exists() or not path.is_file():
            continue
        stat = path.stat()
        records.append(
            {
                "name": path.name,
                "path": str(path.resolve()),
                "size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "preview": _read_preview(path, preview_bytes),
            }
        )
    return records


def _read_preview(path: Path, preview_bytes: int) -> str:
    """Read a small preview for text-like log files."""
    if preview_bytes <= 0 or path.suffix.lower() not in TEXT_PREVIEW_EXTENSIONS:
        return ""
    return path.read_bytes()[:preview_bytes].decode("utf-8", errors="replace")


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    """Keep the first occurrence of each resolved path."""
    seen: set[str] = set()
    result = []
    for path in paths:
        key = str(path.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp for job manifests."""
    return datetime.now(timezone.utc).isoformat()
