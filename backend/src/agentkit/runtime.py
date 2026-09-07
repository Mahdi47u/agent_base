from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .actions import serialize_proposal
from .config import get_config
from .models import AgentActionProposal, AgentMessage, AgentSession
from .providers import build_model
from .registry import build_tools, capability_manifest


@dataclass(slots=True)
class RuntimeResult:
    content: str
    provider: str
    model_name: str
    proposals: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    tool_events: list[dict] = field(default_factory=list)
    ui: list[dict] = field(default_factory=list)


RuntimeEventName = Literal["tool", "delta", "result"]
RuntimeEvent = tuple[RuntimeEventName, dict | RuntimeResult]


def build_history(session: AgentSession):
    config = get_config()
    messages = [SystemMessage(content=config.system_prompt)]
    rows = list(
        session.messages.exclude(role=AgentMessage.Role.TOOL).order_by("-created_at")[: config.history_limit]
    )
    for row in reversed(rows):
        if row.role == AgentMessage.Role.USER:
            messages.append(HumanMessage(content=row.content))
        elif row.role == AgentMessage.Role.ASSISTANT:
            messages.append(AIMessage(content=row.content))
    return messages


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(
        str(block.get("text") or "")
        for block in content
        if isinstance(block, dict) and block.get("type") in {"text", "output_text"}
    )


def compile_graph(*, model_with_tools, tools):
    def call_model(state: MessagesState):
        return {"messages": [model_with_tools.invoke(state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("assistant", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "assistant")
    return builder.compile()


def parse_tool_payloads(messages) -> tuple[list[dict], list[dict], list[dict]]:
    proposals: list[dict] = []
    citations: list[dict] = []
    ui: list[dict] = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        try:
            payload = json.loads(str(message.content))
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not payload.get("ok"):
            continue
        proposals.extend(item for item in payload.get("proposals", []) if isinstance(item, dict))
        citations.extend(item for item in payload.get("citations", []) if isinstance(item, dict))
        ui.extend(item for item in payload.get("ui", []) if isinstance(item, dict))
    return proposals[:20], citations[:20], ui[:20]


def tool_start_events(message, started_at: dict[str, float], now: float) -> list[dict]:
    if not isinstance(message, AIMessage):
        return []
    events = []
    for call in getattr(message, "tool_calls", []) or []:
        if not isinstance(call, dict) or not call.get("id"):
            continue
        call_id = str(call["id"])
        if call_id in started_at:
            continue
        started_at[call_id] = now
        events.append({"tool": str(call.get("name") or "tool"), "tool_call_id": call_id, "status": "running"})
    return events


def tool_complete_event(message: ToolMessage, started_at: dict[str, float], now: float, fallback: float) -> dict:
    call_id = str(getattr(message, "tool_call_id", "") or "")
    began_at = started_at.pop(call_id, fallback)
    return {
        "tool": message.name or "tool",
        "tool_call_id": call_id,
        "status": "complete",
        "duration_ms": max(0, round((now - began_at) * 1000)),
    }


def mock_result(*, session: AgentSession, user) -> RuntimeResult:
    latest = session.messages.filter(role=AgentMessage.Role.USER).order_by("-created_at").first()
    prompt = latest.content if latest else ""
    names = ", ".join(item["name"] for item in capability_manifest(user))
    return RuntimeResult(
        content=(
            f"Mock provider received: {prompt}\n\nAvailable tools: {names}. "
            "Set AGENT_PROVIDER=openai and configure an API key to use a real model."
        ),
        provider="mock",
        model_name="mock-v1",
    )


def stream_agent(*, session: AgentSession, user) -> Iterator[RuntimeEvent]:
    config = get_config()
    provider = (session.provider or config.default_provider).strip().lower()
    model, model_name = build_model(provider, config)
    if model is None:
        result = mock_result(session=session, user=user)
        yield "delta", {"text": result.content}
        yield "result", result
        return

    tools = build_tools(user=user, session=session)
    graph = compile_graph(model_with_tools=model.bind_tools(tools), tools=tools)
    graph_messages = []
    run_started_at = perf_counter()
    starts: dict[str, float] = {}
    completed: list[dict] = []

    for mode, data in graph.stream(
        {"messages": build_history(session)},
        config={"recursion_limit": 12},
        stream_mode=["messages", "updates"],
    ):
        if mode == "messages":
            chunk, metadata = data
            if metadata.get("langgraph_node") == "assistant" and (text := message_text(chunk)):
                yield "delta", {"text": text}
            continue
        for update in data.values():
            if not isinstance(update, dict):
                continue
            messages = update.get("messages") or []
            if not isinstance(messages, list):
                messages = [messages]
            graph_messages.extend(messages)
            for message in messages:
                for event in tool_start_events(message, starts, perf_counter()):
                    yield "tool", event
                if isinstance(message, ToolMessage):
                    event = tool_complete_event(message, starts, perf_counter(), run_started_at)
                    completed.append(event)
                    yield "tool", event

    proposals, citations, ui = parse_tool_payloads(graph_messages)
    # Re-read proposals from the database so a tool cannot forge the confirmation contract.
    proposal_ids = [item.get("id") for item in proposals if item.get("id")]
    verified = AgentActionProposal.objects.filter(pk__in=proposal_ids, owner=user, session=session)
    proposals = [serialize_proposal(item) for item in verified]
    final = next((item for item in reversed(graph_messages) if isinstance(item, AIMessage)), None)
    content = message_text(final).strip() if final else ""
    if not content:
        content = "The model returned no text. Please try again."
    yield "result", RuntimeResult(content, provider, model_name, proposals, citations, completed, ui)


def run_agent(*, session: AgentSession, user) -> RuntimeResult:
    result = None
    for event, payload in stream_agent(session=session, user=user):
        if event == "result":
            result = payload
    if not isinstance(result, RuntimeResult):
        raise RuntimeError("The agent graph ended without a result.")
    return result
