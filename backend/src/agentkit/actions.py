from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from .config import get_config
from .models import AgentActionProposal, AgentAuditEvent, AgentSession
from .registry import action_handler


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def serialize_proposal(proposal: AgentActionProposal) -> dict:
    return {
        "id": str(proposal.pk),
        "action_type": proposal.action_type,
        "title": proposal.title,
        "payload": proposal.payload,
        "target_key": proposal.target_key,
        "target_version": proposal.target_version,
        "status": proposal.status,
        "expires_at": proposal.expires_at.isoformat(),
        "result": proposal.result,
    }


def propose_action(
    *,
    session: AgentSession,
    user: Any,
    action_type: str,
    title: str,
    payload: dict,
    target_key: str = "",
    target_version: str = "",
) -> dict:
    """Persist an inert proposal. The domain write happens only in confirm_action."""

    action_handler(action_type)  # Fail early if integration forgot the executor.
    proposal = AgentActionProposal.objects.create(
        session=session,
        owner=user,
        action_type=action_type,
        title=title[:200],
        payload=payload,
        argument_fingerprint=_fingerprint(payload),
        target_key=target_key[:200],
        target_version=target_version[:200],
        expires_at=timezone.now() + timedelta(seconds=get_config().action_ttl_seconds),
    )
    return serialize_proposal(proposal)


def confirm_action(*, proposal_id, user: Any) -> AgentActionProposal:
    """Lock, revalidate, execute once, and audit in one database transaction."""

    domain_error: Exception | None = None
    try:
        with transaction.atomic():
            proposal = AgentActionProposal.objects.select_for_update().select_related("session").get(
                pk=proposal_id, owner=user
            )
            if proposal.status != AgentActionProposal.Status.PENDING:
                raise ValueError("This action proposal is no longer pending.")
            if proposal.expires_at <= timezone.now():
                proposal.status = AgentActionProposal.Status.EXPIRED
                proposal.save(update_fields=("status", "updated_at"))
                return proposal
            if _fingerprint(proposal.payload) != proposal.argument_fingerprint:
                proposal.status = AgentActionProposal.Status.CONFLICT
                proposal.save(update_fields=("status", "updated_at"))
                return proposal

            handler = action_handler(proposal.action_type)
            try:
                result = handler(proposal=proposal, user=user)
            except (PermissionError, ValueError) as exc:
                domain_error = exc
                proposal.status = AgentActionProposal.Status.CONFLICT
                proposal.save(update_fields=("status", "updated_at"))
            else:
                if result is not None and not isinstance(result, dict):
                    raise TypeError("Action handlers must return a dictionary or None.")
                proposal.status = AgentActionProposal.Status.EXECUTED
                proposal.executed_at = timezone.now()
                proposal.result = result or {}
                proposal.save(update_fields=("status", "executed_at", "result", "updated_at"))
                AgentAuditEvent.objects.create(
                    actor=user,
                    session=proposal.session,
                    event_type="agent_action_executed",
                    target_type=proposal.action_type,
                    target_id=proposal.target_key,
                    metadata={"proposal_id": str(proposal.pk), "idempotency_key": str(proposal.idempotency_key)},
                )
    except (AgentActionProposal.DoesNotExist, LookupError, PermissionError, ValueError):
        raise
    except Exception:
        AgentActionProposal.objects.filter(
            pk=proposal_id,
            owner=user,
            status=AgentActionProposal.Status.PENDING,
        ).update(status=AgentActionProposal.Status.FAILED, updated_at=timezone.now())
        raise
    if domain_error is not None:
        raise domain_error
    return proposal


@transaction.atomic
def cancel_action(*, proposal_id, user: Any) -> AgentActionProposal:
    proposal = AgentActionProposal.objects.select_for_update().get(pk=proposal_id, owner=user)
    if proposal.status != AgentActionProposal.Status.PENDING:
        raise ValueError("This action proposal is no longer pending.")
    proposal.status = AgentActionProposal.Status.CANCELLED
    proposal.save(update_fields=("status", "updated_at"))
    return proposal
