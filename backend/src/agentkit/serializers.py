from rest_framework import serializers

from .actions import serialize_proposal
from .models import AgentMessage, AgentSession


class AgentMessageSerializer(serializers.ModelSerializer):
    citations = serializers.SerializerMethodField()

    class Meta:
        model = AgentMessage
        fields = ("id", "role", "content", "tool_name", "metadata", "citations", "created_at")

    def get_citations(self, obj):
        return [
            {
                "id": str(item.pk),
                "title": item.title,
                "source_url": item.source_url,
                "version": item.version,
                "location": item.location,
                "excerpt": item.excerpt,
            }
            for item in obj.citations.all()
        ]


class AgentSessionSerializer(serializers.ModelSerializer):
    messages = AgentMessageSerializer(many=True, read_only=True)
    action_proposals = serializers.SerializerMethodField()

    class Meta:
        model = AgentSession
        fields = (
            "id",
            "title",
            "provider",
            "model_name",
            "context",
            "messages",
            "action_proposals",
            "created_at",
            "updated_at",
            "last_activity_at",
        )
        read_only_fields = ("model_name", "created_at", "updated_at", "last_activity_at")

    def get_action_proposals(self, obj):
        return [
            serialize_proposal(item)
            for item in obj.action_proposals.filter(status="pending").order_by("created_at")
        ]


class MessageInputSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=12000, trim_whitespace=True)
    context = serializers.DictField(required=False)

    def validate_context(self, value):
        import json

        if len(json.dumps(value, default=str)) > 4096:
            raise serializers.ValidationError("Context must be no larger than 4 KiB.")
        return value
