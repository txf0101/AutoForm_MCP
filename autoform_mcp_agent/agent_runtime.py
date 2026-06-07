"""这个文件保留可选的 OpenAI Agents SDK 运行时。MCP 不依赖它，但命令行可以用它把自然语言请求整理成本项目已经登记过的工具调用。

This file keeps the optional OpenAI Agents SDK runtime. MCP does not depend on it, but the CLI can use it to turn natural-language requests into registered project tool calls.

确定性的 AutoForm 动作仍放在普通业务模块里。这里不会让模型随便发明 AutoForm 命令，只能调用已经注册、可测试、可维护的 Python 函数。

Deterministic AutoForm actions still live in the normal business modules. This runtime does not let a model invent AutoForm commands; it can only call registered, testable, maintainable Python functions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Callable

from .commands import list_command_specs
from .coverage import MODULE_COVERAGE
from .diagnostics import environment_snapshot
from .inventory import get_afd_project_summary, list_example_projects
from .paths import discover_installations
from .project_workflow import project_run_workflow, resolve_project_input
from .queue import queue_health_check
from .quicklink import list_quicklink_exports
from .solver import forming_solver_kinematic_plan


DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_MAX_TURNS = 8
SUPPORTED_AGENT_API_MODES = {"responses", "chat_completions"}
PLACEHOLDER_API_KEYS = {
    "your_provider_api_key_here",
    "your_openai_api_key_here",
    "your_deepseek_api_key_here",
}


PROVIDER_PRESETS: dict[str, dict[str, str | None]] = {
    "openai": {
        "label": "OpenAI",
        "model": DEFAULT_MODEL,
        "base_url": None,
        "api_mode": "responses",
    },
    "deepseek": {
        "label": "DeepSeek",
        "model": DEFAULT_DEEPSEEK_MODEL,
        "base_url": "https://api.deepseek.com",
        "api_mode": "chat_completions",
    },
    "custom": {
        "label": "OpenAI-compatible custom provider",
        "model": DEFAULT_MODEL,
        "base_url": None,
        "api_mode": "chat_completions",
    },
}


@dataclass(frozen=True)
class AgentRuntimeConfig:
    """Resolved settings for one AutoForm Agent runtime invocation."""

    provider: str
    model: str
    base_url: str | None
    api_mode: str
    api_key: str | None
    api_key_configured: bool
    api_key_source: str
    sdk_available: bool
    project_root: Path
    tracing_enabled: bool


@dataclass(frozen=True)
class AgentRuntimeResult:
    """Frontend-ready result returned by the Python runtime."""

    role: str
    text: str
    time: str
    timeline: list[dict[str, str]]
    preview: dict[str, str]
    metrics: dict[str, str]
    runtime: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable response for HTTP and CLI callers."""

        return {
            "role": self.role,
            "text": self.text,
            "time": self.time,
            "timeline": self.timeline,
            "preview": self.preview,
            "metrics": self.metrics,
            "runtime": self.runtime,
        }


def run_agent_runtime_turn(
    payload: dict[str, Any],
    *,
    config: AgentRuntimeConfig | None = None,
    snapshot: dict[str, Any] | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> dict[str, Any]:
    """Run one user turn through the backend AutoForm Agent runtime.

    The function intentionally accepts the same payload shape used by the HTTP
    bridge.  That keeps browser code small: it only forwards user text and UI
    context, while this module handles OpenAI configuration, SDK availability,
    tool registration, deterministic fallback, and response shaping.
    """

    runtime_config = _apply_payload_runtime_config(
        payload=payload,
        config=config or load_agent_runtime_config(),
    )
    prompt = str(payload.get("prompt") or "").strip()
    conversation_id = str(payload.get("conversationId") or "unknown")
    runtime_snapshot = snapshot or collect_agent_runtime_snapshot(runtime_config.project_root)

    if not prompt:
        return _build_local_runtime_result(
            prompt="空 prompt",
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            reason="收到空 prompt，后端运行时未执行工具选择。",
        ).as_dict()

    if not runtime_config.sdk_available:
        return _build_local_runtime_result(
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            reason="当前 Python 环境未安装 openai-agents，后端运行时返回本地检查结果。",
        ).as_dict()

    if not runtime_config.api_key_configured:
        return _build_local_runtime_result(
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            reason="未检测到 API key；可在页面临时输入，或在 .env 中配置 OPENAI_API_KEY。",
        ).as_dict()

    try:
        return _run_openai_agents_sdk_turn(
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            max_turns=max_turns,
        ).as_dict()
    except Exception as exc:  # pragma: no cover - depends on live provider behavior
        return _build_local_runtime_result(
            prompt=prompt,
            conversation_id=conversation_id,
            config=runtime_config,
            snapshot=runtime_snapshot,
            reason=f"{_provider_label(runtime_config.provider)} 调用失败：{_sanitize_runtime_error(exc, runtime_config)}",
        ).as_dict()


def load_agent_runtime_config(project_root: Path | None = None) -> AgentRuntimeConfig:
    """Load OpenAI runtime settings from `.env` and process environment.

    The loader mirrors the environment style used by OpenAI-compatible
    prototypes: local `.env` values are read first without overriding explicit
    shell variables, then provider, model, base URL, API mode, and API key are
    resolved for the current process.  Secrets are kept inside the config object
    and are never copied into the frontend response payload.
    """

    resolved_root = project_root or _find_project_root()
    _load_env_file(resolved_root / ".env")

    provider = _normalize_provider(os.getenv("CHAT_PROVIDER"))
    preset = _provider_preset(provider)
    model = _clean_text(os.getenv("OPENAI_MODEL")) or str(preset["model"])
    base_url = _clean_base_url(os.getenv("OPENAI_BASE_URL")) or preset["base_url"]
    api_mode = _resolve_api_mode(os.getenv("OPENAI_AGENTS_API_MODE"), provider, base_url)
    api_key = _clean_secret(os.getenv("OPENAI_API_KEY"))

    return AgentRuntimeConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        api_key=api_key,
        api_key_configured=bool(api_key),
        api_key_source="environment" if api_key else "none",
        sdk_available=_is_agents_sdk_available(),
        project_root=resolved_root,
        tracing_enabled=os.getenv("OPENAI_AGENTS_TRACING", "0") in {"1", "true", "True"},
    )


def _apply_payload_runtime_config(
    *,
    payload: dict[str, Any],
    config: AgentRuntimeConfig,
) -> AgentRuntimeConfig:
    """Merge optional frontend runtime settings into the base config.

    The browser may send a `runtimeConfig` object when the user chooses a
    provider such as DeepSeek or a custom OpenAI-compatible endpoint.  This
    helper keeps those settings request-scoped: it never writes `.env`, never
    mutates process environment variables, and never returns the secret key in
    the HTTP response.  Empty UI fields mean "use the provider preset or the
    existing environment value" so the same page works for both IT-provided
    `.env` keys and one-off session keys typed into the page.
    """

    runtime_config = payload.get("runtimeConfig")
    if not isinstance(runtime_config, dict):
        return config

    requested_provider = _clean_text(runtime_config.get("provider"))
    provider = _normalize_provider(requested_provider or config.provider)
    preset = _provider_preset(provider)

    provider_changed = provider != config.provider
    requested_model = _clean_text(runtime_config.get("model"))
    model = requested_model or (str(preset["model"]) if provider_changed else config.model)

    requested_base_url = runtime_config.get("baseUrl")
    if requested_base_url is None and not provider_changed:
        base_url = config.base_url
    else:
        base_url = _clean_base_url(requested_base_url) or preset["base_url"]

    requested_api_mode = _clean_text(runtime_config.get("apiMode"))
    api_mode = _resolve_api_mode(
        requested_api_mode or (None if provider_changed else config.api_mode),
        provider,
        base_url,
    )

    request_api_key = _clean_secret(runtime_config.get("apiKey"))
    api_key = request_api_key or config.api_key

    return replace(
        config,
        provider=provider,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        api_key=api_key,
        api_key_configured=bool(api_key),
        api_key_source="request" if request_api_key else config.api_key_source,
    )


def collect_agent_runtime_snapshot(project_root: Path | None = None) -> dict[str, Any]:
    """Collect read-only local facts used by tools and fallback replies."""

    resolved_root = project_root or _find_project_root()
    installations, install_error = _safe_call(
        lambda: [installation.as_dict() for installation in discover_installations()],
        fallback=[],
    )
    queue_status, queue_error = _safe_call(queue_health_check, fallback={})
    examples, examples_error = _safe_call(list_example_projects, fallback=[])
    quicklinks, quicklinks_error = _safe_call(
        lambda: list_quicklink_exports(resolved_root),
        fallback=[],
    )
    tool_count = sum(len(row.get("tools", [])) for row in MODULE_COVERAGE)

    return {
        "project_root": str(resolved_root),
        "install_count": len(installations),
        "installations": installations,
        "install_error": install_error,
        "queue_status": queue_status,
        "queue_error": queue_error,
        "queue_summary": _queue_summary(queue_status, queue_error),
        "example_count": len(examples),
        "examples_error": examples_error,
        "quicklink_export_count": len(quicklinks),
        "quicklinks_error": quicklinks_error,
        "tool_count": tool_count,
    }


def build_autoform_manager_agent(config: AgentRuntimeConfig):
    """Build the single manager agent used by the AutoForm runtime.

    Imports happen inside this function so the project remains importable in
    test and offline environments that have not installed `openai-agents`.
    """

    from agents import Agent, ModelSettings

    return Agent(
        name="AutoForm Agent Manager",
        model=config.model,
        instructions=AGENT_INSTRUCTIONS,
        model_settings=ModelSettings(max_tokens=900),
        tools=build_agent_tools(config.project_root),
    )


def build_agent_tools(project_root: Path | None = None) -> list[Any]:
    """Create Agents SDK function tools that wrap existing AutoForm modules."""

    from agents import function_tool

    resolved_root = project_root or _find_project_root()

    @function_tool
    def autoform_discover_installation_tool() -> dict[str, Any]:
        """Return discovered AutoForm installations and key paths."""

        return {"installations": [installation.as_dict() for installation in discover_installations()]}

    @function_tool
    def autoform_environment_snapshot_tool() -> dict[str, Any]:
        """Return a compact read-only AutoForm Agent environment snapshot."""

        return environment_snapshot(write=False)

    @function_tool
    def autoform_queue_health_tool() -> dict[str, Any]:
        """Return whether known AutoForm queue processes are running."""

        return queue_health_check()

    @function_tool
    def autoform_example_projects_tool() -> dict[str, Any]:
        """Return official AutoForm example projects discovered locally."""

        return {"examples": list_example_projects()}

    @function_tool
    def autoform_command_specs_tool() -> dict[str, Any]:
        """Return known AutoForm command entries grounded in local binaries."""

        return {"commands": list_command_specs()}

    @function_tool
    def autoform_quicklink_exports_tool(workspace: str = "") -> dict[str, Any]:
        """Return QuickLink exports collected by the AutoForm bridge script."""

        workspace_path = Path(workspace) if workspace else resolved_root
        return {"exports": list_quicklink_exports(workspace_path)}

    @function_tool
    def autoform_afd_summary_tool(afd_path: str) -> dict[str, Any]:
        """Return a compact summary extracted from one `.afd` project file."""

        return get_afd_project_summary(Path(afd_path))

    @function_tool
    def autoform_kinematic_plan_tool(afd_path: str, threads: int = 1) -> dict[str, Any]:
        """Plan a direct AFFormingSolver kinematic check without executing it."""

        return forming_solver_kinematic_plan(afd_path, threads=threads)

    @function_tool
    def autoform_resolve_project_tool(example_name: str = "Solver_R13", afd_path: str = "") -> dict[str, Any]:
        """Resolve an official example name or explicit .afd path for project runs."""

        return resolve_project_input(afd_path=afd_path or None, example_name=example_name)

    @function_tool
    def autoform_project_run_plan_tool(example_name: str = "Solver_R13", mode: str = "kinematic", threads: int = 1) -> dict[str, Any]:
        """Plan a reproducible AutoForm project run without executing the solver."""

        return project_run_workflow(example_name=example_name, mode=mode, threads=threads, execute=False)

    return [
        autoform_discover_installation_tool,
        autoform_environment_snapshot_tool,
        autoform_queue_health_tool,
        autoform_example_projects_tool,
        autoform_command_specs_tool,
        autoform_quicklink_exports_tool,
        autoform_afd_summary_tool,
        autoform_kinematic_plan_tool,
        autoform_resolve_project_tool,
        autoform_project_run_plan_tool,
    ]


AGENT_INSTRUCTIONS = """
You are the backend AutoForm Agent Manager.

Your task is to understand the user request, choose registered AutoForm tools
when evidence is needed, and answer from tool results.  The browser frontend is
only a display surface.  Do not ask the browser to execute AutoForm actions.

Tool policy:
- Use read-only inspection tools before giving facts about local installation,
  queues, examples, QuickLink exports, command availability, or AFD contents.
- Use planning tools for solver actions unless the user explicitly asks for a
  real execution path and the project exposes a safe execution wrapper.
- Do not invent AutoForm command names, paths, project facts, or tool results.
- If required information is missing, state the missing input and the tool that
  can verify it.

Reply in concise Chinese by default.  Include concrete evidence such as tool
names, counts, paths, or returned status when available.
""".strip()


def _run_openai_agents_sdk_turn(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    max_turns: int,
) -> AgentRuntimeResult:
    """Execute one prompt through OpenAI Agents SDK and shape the UI response."""

    _configure_openai_agents_sdk(config)

    from agents import Runner

    agent = build_autoform_manager_agent(config)
    result = Runner.run_sync(agent, prompt, max_turns=max_turns)
    final_output = str(getattr(result, "final_output", "") or "").strip()

    return AgentRuntimeResult(
        role="assistant",
        text=final_output or "OpenAI Agents SDK 已完成调用，但未返回可见文本。",
        time=_utc_now(),
        timeline=_runtime_timeline(openai_called=True, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="openai_agents_sdk",
            phase="Agents SDK",
            title="OpenAI Agents SDK 后端运行时",
            subtitle=f"conversationId={conversation_id}",
            solver="后端已接管",
            solver_detail=_queue_summary(snapshot.get("queue_status", {}), snapshot.get("queue_error")),
        ),
        metrics=_runtime_metrics(config=config, snapshot=snapshot, openai_called=True),
        runtime={
            "name": "autoform-openai-agents-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "openaiCalled": True,
            "sdkAvailable": True,
            "apiKeyConfigured": True,
            "apiKeySource": config.api_key_source,
            "frontendOwnsControl": False,
        },
    )


def _configure_openai_agents_sdk(config: AgentRuntimeConfig) -> None:
    """Configure the Agents SDK client for the selected provider.

    OpenAI's default path uses the Responses API.  OpenAI-compatible providers
    that only expose chat completion semantics can switch the SDK to
    `chat_completions`, which is the mode used by the DeepSeek page preset.
    """

    from agents import set_default_openai_api, set_default_openai_client, set_tracing_disabled
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=config.api_key or "", base_url=config.base_url)
    set_default_openai_client(client, use_for_tracing=config.tracing_enabled)
    set_default_openai_api(config.api_mode)  # type: ignore[arg-type]
    set_tracing_disabled(not config.tracing_enabled)


def _build_local_runtime_result(
    *,
    prompt: str,
    conversation_id: str,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    reason: str,
) -> AgentRuntimeResult:
    """Build a deterministic backend response when cloud runtime cannot run."""

    text = (
        f"AutoForm Agent 后端运行时已接管请求，conversationId={conversation_id}。"
        f" 本次 prompt 为：{prompt}。"
        f" {reason}"
        f" 当前本地检查读取到 {snapshot['install_count']} 条安装记录、"
        f"{snapshot['tool_count']} 个工具入口、{snapshot['example_count']} 个示例工程、"
        f"{snapshot['quicklink_export_count']} 条 QuickLink 导出记录。"
        " 配置 API key 并安装 openai-agents 后，同一路径会调用 OpenAI Agents SDK。"
    )

    return AgentRuntimeResult(
        role="assistant",
        text=text,
        time=_utc_now(),
        timeline=_runtime_timeline(openai_called=False, snapshot=snapshot, config=config),
        preview=_runtime_preview(
            active_tool="autoform_mcp_agent_runtime",
            phase="Backend Runtime",
            title="Python 后端运行时",
            subtitle=reason,
            solver="本地降级",
            solver_detail=snapshot["queue_summary"],
        ),
        metrics=_runtime_metrics(config=config, snapshot=snapshot, openai_called=False),
        runtime={
            "name": "autoform-openai-agents-runtime",
            "provider": config.provider,
            "providerLabel": _provider_label(config.provider),
            "model": config.model,
            "baseUrl": config.base_url,
            "apiMode": config.api_mode,
            "openaiCalled": False,
            "sdkAvailable": config.sdk_available,
            "apiKeyConfigured": config.api_key_configured,
            "apiKeySource": config.api_key_source,
            "frontendOwnsControl": False,
            "reason": reason,
        },
    )


def _runtime_timeline(
    openai_called: bool,
    snapshot: dict[str, Any],
    config: AgentRuntimeConfig | None = None,
) -> list[dict[str, str]]:
    """Return the three visual steps consumed by the existing frontend."""

    runtime_state = "complete" if openai_called else "ready"
    if openai_called:
        runtime_detail = f"{_provider_label(config.provider) if config else 'OpenAI'} 已通过 Agents SDK 执行"
    elif config is not None and config.sdk_available and not config.api_key_configured:
        runtime_detail = "等待 API key"
    elif config is not None and not config.sdk_available:
        runtime_detail = "等待 openai-agents"
    else:
        runtime_detail = "等待云端运行时配置"
    return [
        {
            "id": "step-discover",
            "title": "后端读取本机状态",
            "detail": f"安装记录 {snapshot['install_count']} 条，工具入口 {snapshot['tool_count']} 个",
            "state": "complete",
        },
        {
            "id": "step-parse",
            "title": "后端 Agent Runtime",
            "detail": runtime_detail,
            "state": runtime_state,
        },
        {
            "id": "step-solver",
            "title": "工具层等待调用",
            "detail": "求解、QuickLink、队列和材料能力仍由 Python 工具层执行",
            "state": "ready",
        },
    ]


def _runtime_preview(
    *,
    active_tool: str,
    phase: str,
    title: str,
    subtitle: str,
    solver: str,
    solver_detail: str,
) -> dict[str, str]:
    """Build the preview card state used by `frontend/app.js`."""

    return {
        "phase": phase,
        "title": title,
        "subtitle": subtitle,
        "solver": solver,
        "solverDetail": solver_detail,
        "activeTool": active_tool,
    }


def _runtime_metrics(
    *,
    config: AgentRuntimeConfig,
    snapshot: dict[str, Any],
    openai_called: bool,
) -> dict[str, str]:
    """Build compact status metrics for the frontend."""

    if openai_called:
        connection = "OpenAI Agents SDK 已调用"
    elif not config.sdk_available:
        connection = "缺少 openai-agents"
    elif not config.api_key_configured:
        connection = "缺少 API key"
    else:
        connection = "后端本地模式"

    return {
        "connection": connection,
        "provider": _provider_label(config.provider),
        "tools": str(snapshot["tool_count"]),
        "queue": snapshot["queue_summary"],
        "model": config.model,
        "apiMode": config.api_mode,
        "baseUrl": config.base_url or "OpenAI default",
    }


def _is_agents_sdk_available() -> bool:
    """Return whether the optional Agents SDK dependency is importable."""

    try:
        import agents  # noqa: F401
        import openai  # noqa: F401
    except Exception:
        return False
    return True


def _load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE lines without overriding shell variables."""

    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _find_project_root() -> Path:
    """Locate the project root from this module path."""

    return Path(__file__).resolve().parents[1]


def _clean_base_url(value: str | None) -> str | None:
    """Normalize optional OpenAI-compatible base URLs."""

    cleaned = (value or "").strip().rstrip("/")
    return cleaned or None


def _clean_text(value: Any) -> str:
    """Return a stripped text value for provider, model and API-mode fields."""

    return str(value or "").strip()


def _clean_secret(value: Any) -> str | None:
    """Return a stripped secret without logging, displaying or persisting it."""

    cleaned = _clean_text(value)
    if cleaned.lower() in PLACEHOLDER_API_KEYS:
        return None
    return cleaned or None


def _normalize_provider(value: Any) -> str:
    """Map user-facing provider names to the small set the runtime supports.

    The project currently keeps one SDK wiring path based on OpenAI's Python
    client.  Unknown providers are treated as `custom`, which lets users enter
    an OpenAI-compatible Base URL and model without adding new Python branches.
    """

    normalized = _clean_text(value).lower().replace(" ", "_") or "openai"
    aliases = {
        "openai_compatible": "custom",
        "compatible": "custom",
        "other": "custom",
        "custom_provider": "custom",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in PROVIDER_PRESETS else "custom"


def _provider_preset(provider: str) -> dict[str, str | None]:
    """Return provider defaults used by both `.env` and frontend overrides."""

    return PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])


def _provider_label(provider: str) -> str:
    """Return a display label for status summaries and terminal output."""

    return str(_provider_preset(provider)["label"])


def _resolve_api_mode(value: Any, provider: str, base_url: str | None) -> str:
    """Resolve the Agents SDK API mode for the selected provider.

    The installed Agents SDK exposes `responses` and `chat_completions` as the
    supported values.  OpenAI keeps the Responses API default, while DeepSeek
    and custom OpenAI-compatible endpoints default to Chat Completions because
    that is the more widely implemented compatibility surface.
    """

    requested = _clean_text(value).lower()
    if requested in SUPPORTED_AGENT_API_MODES:
        return requested
    if provider == "openai" and not base_url:
        return "responses"
    return str(_provider_preset(provider)["api_mode"])


def _sanitize_runtime_error(exc: Exception, config: AgentRuntimeConfig) -> str:
    """Strip obvious secrets from live provider errors before showing the UI."""

    message = str(exc).strip() or exc.__class__.__name__
    if config.api_key:
        message = message.replace(config.api_key, "[redacted-api-key]")
    return message[:900]


def _safe_call(func: Callable[[], Any], fallback: Any) -> tuple[Any, str | None]:
    """Execute a local probe and return its error as data instead of raising."""

    try:
        return func(), None
    except Exception as exc:  # pragma: no cover - depends on local AutoForm state
        return fallback, str(exc)


def _queue_summary(queue_status: dict[str, Any], error: str | None) -> str:
    """Summarize queue process status for compact UI display."""

    if error:
        return "队列状态待检查"

    processes = queue_status.get("processes") if isinstance(queue_status, dict) else None
    if not processes:
        return "队列状态无进程记录"

    running = [item for item in processes if item.get("running")]
    return f"队列进程 {len(running)}/{len(processes)} 运行中"


def _utc_now() -> str:
    """Return an ISO timestamp for UI messages and test assertions."""

    return datetime.now(timezone.utc).isoformat()
