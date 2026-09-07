from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from threading import Lock
from typing import Any

from .config import get_config
from .contracts import ToolContext, ToolMode, ToolSpec

_tool_specs: dict[str, ToolSpec] = {}
_action_handlers: dict[str, Callable[..., dict]] = {}
_loaded = False
_lock = Lock()


def register_tool(spec: ToolSpec) -> ToolSpec:
    existing = _tool_specs.get(spec.name)
    if existing is not None and existing != spec:
        raise RuntimeError(f"Agent tool name is already registered: {spec.name}")
    _tool_specs[spec.name] = spec
    return spec


def register_action(action_type: str, handler: Callable[..., dict]) -> Callable[..., dict]:
    existing = _action_handlers.get(action_type)
    if existing is not None and existing is not handler:
        raise RuntimeError(f"Agent action type is already registered: {action_type}")
    _action_handlers[action_type] = handler
    return handler


def action_handler(action_type: str) -> Callable[..., dict]:
    try:
        return _action_handlers[action_type]
    except KeyError as exc:
        raise LookupError(f"No action handler is registered for {action_type!r}.") from exc


def load_extensions() -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
        import_module("agentkit.default_tools")
        config = get_config()
        for module in (*config.tool_modules, *config.action_modules):
            import_module(module)
        _loaded = True


def registered_tools() -> tuple[ToolSpec, ...]:
    load_extensions()
    return tuple(_tool_specs.values())


def build_tools(*, user: Any, session: Any, modes: frozenset[ToolMode] | None = None) -> list[Any]:
    requested_modes = modes or frozenset({ToolMode.READ, ToolMode.PROPOSE})
    context = ToolContext(user=user, session=session)
    tools = []
    for spec in registered_tools():
        if spec.mode not in requested_modes:
            continue
        if spec.required_permissions and not user.has_perms(spec.required_permissions):
            continue
        if not spec.is_available(user):
            continue
        tool = spec.factory(context)
        if tool.name != spec.name:
            raise RuntimeError(f"Tool factory for {spec.name!r} returned {tool.name!r}.")
        tools.append(tool)
    return tools


def capability_manifest(user: Any) -> list[dict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "category": spec.category,
            "mode": spec.mode.value,
        }
        for spec in registered_tools()
        if (not spec.required_permissions or user.has_perms(spec.required_permissions)) and spec.is_available(user)
    ]
