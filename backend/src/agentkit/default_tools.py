from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.tools import StructuredTool

from .contracts import ToolContext, ToolSpec, tool_result
from .registry import capability_manifest, register_tool


def _capabilities_factory(context: ToolContext):
    def list_capabilities() -> str:
        """List the tools currently available to the signed-in user."""

        rows = capability_manifest(context.user)
        return tool_result(rows)

    return StructuredTool.from_function(list_capabilities, name="list_capabilities")


def _time_factory(_context: ToolContext):
    def get_current_time() -> str:
        """Return the current UTC date and time from the application server."""

        return tool_result({"timezone": "UTC", "iso": datetime.now(UTC).isoformat()})

    return StructuredTool.from_function(get_current_time, name="get_current_time")


register_tool(
    ToolSpec(
        name="list_capabilities",
        description="List the tools available to the current user.",
        category="system",
        factory=_capabilities_factory,
    )
)
register_tool(
    ToolSpec(
        name="get_current_time",
        description="Read the current UTC time from the server.",
        category="system",
        factory=_time_factory,
    )
)
