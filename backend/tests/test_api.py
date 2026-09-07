from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from rest_framework.test import APIClient

from agentkit.models import AgentMessage, AgentSession

pytestmark = pytest.mark.django_db


def user(username="owner"):
    return get_user_model().objects.create_user(username=username, password="correct-horse")


def test_login_requires_csrf_and_uses_a_server_session():
    user()
    client = Client(enforce_csrf_checks=True)
    rejected = client.post(
        "/api/agent/auth/login/",
        data=json.dumps({"username": "owner", "password": "correct-horse"}),
        content_type="application/json",
    )
    assert rejected.status_code == 403

    csrf = client.get("/api/agent/auth/csrf/").json()["csrfToken"]
    accepted = client.post(
        "/api/agent/auth/login/",
        data=json.dumps({"username": "owner", "password": "correct-horse"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert accepted.status_code == 200
    assert accepted.json()["username"] == "owner"
    assert client.get("/api/agent/auth/me/").status_code == 200


def test_sessions_are_owner_scoped():
    owner = user()
    other = user("other")
    session = AgentSession.objects.create(owner=owner, provider="mock")
    client = APIClient()
    client.force_authenticate(other)
    assert client.get(f"/api/agent/sessions/{session.pk}/").status_code == 404


@override_settings(
    AGENT_BASE={
        "ENABLED": True,
        "DEFAULT_PROVIDER": "mock",
        "APPROVED_PROVIDERS": "mock",
        "SYSTEM_PROMPT": "Test prompt",
        "MAX_SESSIONS": 2,
    }
)
def test_session_retention_is_bounded():
    owner = user()
    rows = [AgentSession.objects.create(owner=owner, title=f"Chat {index}") for index in range(3)]
    client = APIClient()
    client.force_authenticate(owner)
    response = client.get("/api/agent/sessions/")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert not AgentSession.objects.filter(pk=rows[0].pk).exists()


def test_mock_message_uses_the_documented_sse_contract():
    owner = user()
    session = AgentSession.objects.create(owner=owner, provider="mock")
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post(
        f"/api/agent/sessions/{session.pk}/messages/stream/",
        {"content": "hello"},
        format="json",
        HTTP_ACCEPT="text/event-stream",
        HTTP_X_REQUEST_ID="test-request",
    )
    body = b"".join(response.streaming_content).decode()
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert response["Cache-Control"] == "no-cache, no-transform"
    assert response["X-Accel-Buffering"] == "no"
    assert "event: start\n" in body
    assert "event: delta\n" in body
    assert "event: complete\n" in body
    assert '"request_id": "test-request"' in body
    assert AgentMessage.objects.filter(session=session, role="user").count() == 1
    assert AgentMessage.objects.filter(session=session, role="assistant").count() == 1


def test_unapproved_provider_is_rejected():
    owner = user()
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post("/api/agent/sessions/", {"provider": "unreviewed"}, format="json")
    assert response.status_code == 400
