from __future__ import annotations

import json
import logging

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from .actions import cancel_action, confirm_action, serialize_proposal
from .config import get_config
from .models import AgentActionProposal, AgentAuditEvent, AgentCitation, AgentMessage, AgentSession
from .registry import capability_manifest
from .renderers import EventStreamRenderer
from .runtime import RuntimeResult, stream_agent
from .serializers import AgentSessionSerializer, MessageInputSerializer

logger = logging.getLogger(__name__)


def _feature_denied(request):
    config = get_config()
    if config.enabled and request.user.is_authenticated and request.user.is_active:
        return None
    return Response(
        {"detail": "The agent is disabled for this account.", "code": "agent_not_enabled"},
        status=status.HTTP_403_FORBIDDEN,
    )


def _prune_old_sessions(owner):
    old_ids = list(
        AgentSession.objects.filter(owner=owner)
        .order_by("-last_activity_at")
        .values_list("pk", flat=True)[get_config().max_sessions :]
    )
    if old_ids:
        AgentSession.objects.filter(pk__in=old_ids).delete()


def _session_for(request, session_id):
    return AgentSession.objects.prefetch_related("messages__citations").get(pk=session_id, owner=request.user)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def capabilities(request):
    if denied := _feature_denied(request):
        return denied
    config = get_config()
    return Response(
        {
            "enabled": True,
            "default_provider": config.default_provider,
            "approved_providers": sorted(config.approved_providers),
            "tools": capability_manifest(request.user),
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sessions(request):
    if denied := _feature_denied(request):
        return denied
    if request.method == "GET":
        _prune_old_sessions(request.user)
        rows = AgentSession.objects.filter(owner=request.user).prefetch_related("messages__citations")[
            : get_config().max_sessions
        ]
        return Response(AgentSessionSerializer(rows, many=True).data)

    provider = str(request.data.get("provider") or get_config().default_provider).strip().lower()
    if provider not in get_config().approved_providers:
        return Response({"provider": "This provider is not approved."}, status=status.HTTP_400_BAD_REQUEST)
    session = AgentSession.objects.create(
        owner=request.user,
        title=str(request.data.get("title") or "New conversation").strip()[:160] or "New conversation",
        provider=provider,
    )
    _prune_old_sessions(request.user)
    return Response(AgentSessionSerializer(session).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    if denied := _feature_denied(request):
        return denied
    try:
        session = _session_for(request, session_id)
    except (AgentSession.DoesNotExist, ValueError):
        return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if request.method == "PATCH":
        fields = []
        if "title" in request.data:
            session.title = str(request.data["title"]).strip()[:160] or session.title
            fields.append("title")
        if "provider" in request.data:
            provider = str(request.data["provider"]).strip().lower()
            if provider not in get_config().approved_providers:
                return Response({"provider": "This provider is not approved."}, status=status.HTTP_400_BAD_REQUEST)
            session.provider = provider
            fields.append("provider")
        if fields:
            session.save(update_fields=(*fields, "updated_at", "last_activity_at"))
    return Response(AgentSessionSerializer(session).data)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@renderer_classes([EventStreamRenderer, JSONRenderer])
def message_stream(request, session_id):
    if denied := _feature_denied(request):
        return denied
    serializer = MessageInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        session = AgentSession.objects.get(pk=session_id, owner=request.user)
    except (AgentSession.DoesNotExist, ValueError):
        return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

    content = serializer.validated_data["content"]
    AgentMessage.objects.create(session=session, role=AgentMessage.Role.USER, content=content)
    if context := serializer.validated_data.get("context"):
        session.context = context
    if session.title == "New conversation":
        session.title = content[:60]
    session.save(update_fields=("title", "context", "updated_at", "last_activity_at"))

    user = request.user
    request_id = str(request.headers.get("X-Request-ID", ""))[:100]

    def generate():
        yield sse("start", {"session_id": str(session.pk), "request_id": request_id})
        try:
            result = None
            for event, payload in stream_agent(session=session, user=user):
                if event == "result":
                    result = payload
                else:
                    yield sse(event, payload)
            if not isinstance(result, RuntimeResult):
                raise RuntimeError("The agent stream ended without a result.")
            assistant = AgentMessage.objects.create(
                session=session,
                role=AgentMessage.Role.ASSISTANT,
                content=result.content,
                metadata={
                    "provider": result.provider,
                    "model": result.model_name,
                    "proposal_ids": [item["id"] for item in result.proposals],
                    "tool_events": result.tool_events,
                    "ui": result.ui,
                },
            )
            for citation in result.citations:
                AgentCitation.objects.create(
                    message=assistant,
                    title=str(citation.get("title") or "Source")[:240],
                    source_url=str(citation.get("source_url") or "")[:500],
                    version=str(citation.get("version") or "")[:40],
                    location=str(citation.get("location") or "")[:160],
                    excerpt=str(citation.get("excerpt") or "")[:2000],
                )
            yield sse(
                "complete",
                {
                    "message_id": str(assistant.pk),
                    "content": result.content,
                    "provider": result.provider,
                    "model": result.model_name,
                    "proposals": result.proposals,
                    "citations": result.citations,
                    "tool_events": result.tool_events,
                    "ui": result.ui,
                },
            )
        except Exception as exc:
            logger.exception(
                "agent stream failed: request_id=%s session_id=%s error_type=%s",
                request_id or "-",
                session.pk,
                type(exc).__name__,
            )
            AgentAuditEvent.objects.create(
                actor=user,
                session=session,
                event_type="agent_run_failed",
                metadata={"error_type": type(exc).__name__, "request_id": request_id},
            )
            yield sse(
                "error",
                {
                    "detail": "The assistant could not complete this request.",
                    "error": {"code": "agent_stream_failed", "request_id": request_id, "retryable": True},
                },
            )

    response = StreamingHttpResponse(generate(), content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    response["Content-Encoding"] = "identity"
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def proposal_confirm(request, proposal_id):
    if denied := _feature_denied(request):
        return denied
    try:
        proposal = confirm_action(proposal_id=proposal_id, user=request.user)
    except AgentActionProposal.DoesNotExist:
        return Response({"detail": "Action proposal not found."}, status=status.HTTP_404_NOT_FOUND)
    except PermissionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except (LookupError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    except Exception as exc:
        request_id = str(request.headers.get("X-Request-ID", ""))[:100]
        logger.exception(
            "agent action failed: request_id=%s proposal_id=%s error_type=%s",
            request_id or "-",
            proposal_id,
            type(exc).__name__,
        )
        return Response(
            {
                "detail": "The action could not be completed.",
                "error": {"code": "agent_action_failed", "request_id": request_id, "retryable": False},
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(serialize_proposal(proposal))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def proposal_cancel(request, proposal_id):
    if denied := _feature_denied(request):
        return denied
    try:
        proposal = cancel_action(proposal_id=proposal_id, user=request.user)
    except AgentActionProposal.DoesNotExist:
        return Response({"detail": "Action proposal not found."}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    return Response(serialize_proposal(proposal))
