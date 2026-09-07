from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ToolMode(StrEnum):
    READ = "read"
    PROPOSE = "propose"


@dataclass(frozen=True, slots=True)
class ToolContext:
    user: Any
    session: Any


ToolFactory = Callable[[ToolContext], Any]
AvailabilityCheck = Callable[[Any], bool]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    factory: ToolFactory
    category: str = "general"
    mode: ToolMode = ToolMode.READ
    required_permissions: frozenset[str] = frozenset()
    is_available: AvailabilityCheck = lambda _user: True


def tool_result(
    data: Any,
    *,
    citations: list[dict] | None = None,
    proposals: list[dict] | None = None,
    ui: list[dict] | None = None,
) -> str:
    """Return the envelope understood by the runtime and reference client."""

    payload = {"ok": True, "data": data}
    if citations:
        payload["citations"] = citations
    if proposals:
        payload["proposals"] = proposals
    if ui:
        payload["ui"] = ui
    return json.dumps(payload, ensure_ascii=False, default=str)


def tool_error(code: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False)
