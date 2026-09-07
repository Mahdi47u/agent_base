from django.contrib import admin

from .models import AgentActionProposal, AgentAuditEvent, AgentCitation, AgentMessage, AgentSession

admin.site.register(AgentSession)
admin.site.register(AgentMessage)
admin.site.register(AgentCitation)
admin.site.register(AgentActionProposal)
admin.site.register(AgentAuditEvent)
