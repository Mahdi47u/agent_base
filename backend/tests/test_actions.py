from __future__ import annotations

from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from agentkit.actions import confirm_action, propose_action
from agentkit.models import AgentActionProposal, AgentAuditEvent, AgentSession
from agentkit.registry import register_action

pytestmark = pytest.mark.django_db


def setup_proposal(handler, action_type):
    register_action(action_type, handler)
    owner = get_user_model().objects.create_user(username="action-owner")
    session = AgentSession.objects.create(owner=owner, provider="mock")
    data = propose_action(
        session=session,
        user=owner,
        action_type=action_type,
        title="Change the example",
        payload={"value": 7},
        target_key="example:1",
        target_version="4",
    )
    return owner, AgentActionProposal.objects.get(pk=data["id"])


def test_confirmation_executes_exactly_once_and_audits():
    handler = Mock(return_value={"saved": True})
    owner, proposal = setup_proposal(handler, "tests.capture_once")
    result = confirm_action(proposal_id=proposal.pk, user=owner)
    assert result.status == AgentActionProposal.Status.EXECUTED
    assert result.result == {"saved": True}
    assert handler.call_count == 1
    assert AgentAuditEvent.objects.filter(event_type="agent_action_executed").count() == 1
    with pytest.raises(ValueError):
        confirm_action(proposal_id=proposal.pk, user=owner)
    assert handler.call_count == 1


def test_tampered_payload_becomes_a_conflict_without_execution():
    handler = Mock(return_value={"saved": True})
    owner, proposal = setup_proposal(handler, "tests.capture_tamper")
    proposal.payload = {"value": 999}
    proposal.save(update_fields=("payload", "updated_at"))
    result = confirm_action(proposal_id=proposal.pk, user=owner)
    assert result.status == AgentActionProposal.Status.CONFLICT
    handler.assert_not_called()


def test_handler_failure_is_persisted_and_not_a_false_success():
    handler = Mock(side_effect=RuntimeError("domain failure"))
    owner, proposal = setup_proposal(handler, "tests.capture_failure")
    with pytest.raises(RuntimeError, match="domain failure"):
        confirm_action(proposal_id=proposal.pk, user=owner)
    proposal.refresh_from_db()
    assert proposal.status == AgentActionProposal.Status.FAILED


def test_expired_proposal_does_not_execute():
    handler = Mock(return_value={"saved": True})
    owner, proposal = setup_proposal(handler, "tests.capture_expired")
    proposal.expires_at = timezone.now()
    proposal.save(update_fields=("expires_at", "updated_at"))
    result = confirm_action(proposal_id=proposal.pk, user=owner)
    assert result.status == AgentActionProposal.Status.EXPIRED
    handler.assert_not_called()


def test_domain_conflict_is_persisted_without_execution_success():
    handler = Mock(side_effect=ValueError("target changed"))
    owner, proposal = setup_proposal(handler, "tests.capture_conflict")
    with pytest.raises(ValueError, match="target changed"):
        confirm_action(proposal_id=proposal.pk, user=owner)
    proposal.refresh_from_db()
    assert proposal.status == AgentActionProposal.Status.CONFLICT
    assert AgentAuditEvent.objects.filter(event_type="agent_action_executed").count() == 0


def test_other_user_cannot_confirm_a_proposal():
    handler = Mock(return_value={"saved": True})
    _owner, proposal = setup_proposal(handler, "tests.capture_foreign")
    other = get_user_model().objects.create_user(username="action-other")
    with pytest.raises(AgentActionProposal.DoesNotExist):
        confirm_action(proposal_id=proposal.pk, user=other)
    handler.assert_not_called()
