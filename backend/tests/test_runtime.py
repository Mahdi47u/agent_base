from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from langchain_core.messages import AIMessage, ToolMessage

from agentkit.models import AgentMessage, AgentSession
from agentkit.runtime import build_history, parse_tool_payloads, tool_complete_event, tool_start_events

pytestmark = pytest.mark.django_db


@override_settings(AGENT_BASE={"SYSTEM_PROMPT": "System contract", "HISTORY_LIMIT": 4})
def test_history_is_bounded_and_chronological():
    owner = get_user_model().objects.create_user(username="history-owner")
    session = AgentSession.objects.create(owner=owner)
    for index in range(6):
        AgentMessage.objects.create(session=session, role="user", content=f"message {index}")
    history = build_history(session)
    assert history[0].content == "System contract"
    assert [item.content for item in history[1:]] == ["message 2", "message 3", "message 4", "message 5"]


def test_tool_progress_uses_call_id_and_duration():
    starts = {}
    call = AIMessage(content="", tool_calls=[{"id": "call-1", "name": "lookup", "args": {}}])
    assert tool_start_events(call, starts, 10.0) == [
        {"tool": "lookup", "tool_call_id": "call-1", "status": "running"}
    ]
    event = tool_complete_event(
        ToolMessage(name="lookup", tool_call_id="call-1", content='{"ok": true}'), starts, 10.125, 0.0
    )
    assert event == {"tool": "lookup", "tool_call_id": "call-1", "status": "complete", "duration_ms": 125}


def test_tool_envelope_extracts_only_bounded_structured_output():
    payload = {
        "ok": True,
        "data": {},
        "citations": [{"title": "Guide"}],
        "ui": [{"type": "notice", "message": "Done"}],
    }
    messages = [ToolMessage(name="lookup", tool_call_id="1", content=json.dumps(payload))]
    proposals, citations, ui = parse_tool_payloads(messages)
    assert proposals == []
    assert citations == [{"title": "Guide"}]
    assert ui == [{"type": "notice", "message": "Done"}]
