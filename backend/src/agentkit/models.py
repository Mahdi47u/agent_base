from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AgentSession(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_sessions")
    title = models.CharField(max_length=160, default="New conversation")
    provider = models.CharField(max_length=32, blank=True)
    model_name = models.CharField(max_length=120, blank=True)
    context = models.JSONField(default=dict, blank=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_activity_at",)
        indexes = [models.Index(fields=("owner", "last_activity_at"), name="agent_session_owner_idx")]

    def __str__(self):
        return self.title


class AgentMessage(TimestampedModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AgentSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    tool_name = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("session", "created_at"), name="agent_message_session_idx")]

    def __str__(self):
        return f"{self.role} · {self.session_id}"


class AgentCitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(AgentMessage, on_delete=models.CASCADE, related_name="citations")
    title = models.CharField(max_length=240)
    source_url = models.URLField(max_length=500, blank=True)
    version = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=160, blank=True)
    excerpt = models.TextField(blank=True)

    def __str__(self):
        return self.title


class AgentActionProposal(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        EXECUTED = "executed", "Executed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        CONFLICT = "conflict", "Conflict"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AgentSession, on_delete=models.CASCADE, related_name="action_proposals")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_action_proposals")
    action_type = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    payload = models.JSONField(default=dict)
    argument_fingerprint = models.CharField(max_length=64)
    target_key = models.CharField(max_length=200, blank=True)
    target_version = models.CharField(max_length=200, blank=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=("owner", "status", "expires_at"), name="agent_proposal_owner_idx")]

    def __str__(self):
        return f"{self.action_type} · {self.status}"


class AgentAuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session = models.ForeignKey(AgentSession, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.event_type
