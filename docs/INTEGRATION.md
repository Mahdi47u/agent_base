# Integrating Agent Base

Use this guide when moving the agent into another Django/Next.js project. Make one boundary work at a time; do not begin with a real provider, RAG, and write tools simultaneously.

## 1. Install the Django app

Copy `backend/src/agentkit` into an installable package or depend on this repository. Add `agentkit` and DRF to `INSTALLED_APPS`, include the URLs, then create a new migration in the consuming project if its migration policy requires local migrations.

```python
# urls.py
path("api/agent/", include("agentkit.urls"))
```

Do not copy `0001_initial.py` into an app label that already has an applied migration history. For an existing project, follow that project's migration rules.

## 2. Configure the runtime

```python
AGENT_BASE = {
    "ENABLED": True,
    "DEFAULT_PROVIDER": "mock",
    "APPROVED_PROVIDERS": "mock,openai",
    "SYSTEM_PROMPT": "Your reviewed application contract...",
    "HISTORY_LIMIT": 40,
    "MAX_SESSIONS": 50,
    "ACTION_TTL_SECONDS": 600,
    "PROVIDER_TIMEOUT_SECONDS": 45,
    "OPENAI_API_KEY": env("OPENAI_API_KEY", default=""),
    "OPENAI_MODEL": env("OPENAI_MODEL", default=""),
    "OPENAI_BASE_URL": env("OPENAI_BASE_URL", default=""),
    "TOOL_MODULES": ["my_project.agent_tools"],
    "ACTION_MODULES": ["my_project.agent_actions"],
}
```

Start with `mock`. Switch to `openai` only after ownership, CSRF, streaming, and tool tests pass. `OPENAI_BASE_URL` supports compatible gateways; leave it empty for OpenAI.

## 3. Register a read tool

Every query must begin with the authenticated user's permitted queryset. Filtering an unrestricted result after fetching it is too late.

```python
from langchain_core.tools import StructuredTool

from agentkit.contracts import ToolContext, ToolSpec, tool_error, tool_result
from agentkit.registry import register_tool


def project_status_factory(context: ToolContext):
    def get_project_status(project_id: str) -> str:
        """Read a project visible to the signed-in user."""
        project = Project.objects.visible_to(context.user).filter(pk=project_id).first()
        if project is None:
            return tool_error("not_found", "Project not found in your access scope.")
        return tool_result({"id": str(project.pk), "name": project.name, "status": project.status})

    return StructuredTool.from_function(get_project_status, name="get_project_status")


register_tool(
    ToolSpec(
        name="get_project_status",
        description="Read a visible project's current status.",
        category="projects",
        required_permissions=frozenset({"projects.view_project"}),
        factory=project_status_factory,
    )
)
```

Tool descriptions are model-visible contracts. State whether a tool reads or proposes, what identifiers it accepts, and what it returns. Keep result envelopes small and JSON-serializable.

## 4. Add citations or UI metadata

Use the structured envelope; do not hide machine data in prose.

```python
return tool_result(
    data=rows,
    citations=[{
        "title": policy.title,
        "source_url": policy.public_url,
        "version": policy.version,
        "location": "section 4",
        "excerpt": excerpt,
    }],
    ui=[{"type": "status_list", "rows": rows}],
)
```

The base client displays citations and safely ignores unknown UI objects. Add a strict parser and renderer for each UI type; validate type, length, row count, URLs, and numeric ranges before rendering.

## 5. Add a proposed write

Create one tool that validates the request and calls `propose_action`. Register a separate executor that cannot be reached through the tool registry.

```python
# my_project/agent_tools.py
from agentkit.actions import propose_action
from agentkit.contracts import ToolContext, ToolMode, ToolSpec, tool_result

def rename_factory(context):
    def propose_project_rename(project_id: str, name: str) -> str:
        project = Project.objects.editable_by(context.user).get(pk=project_id)
        proposal = propose_action(
            session=context.session,
            user=context.user,
            action_type="projects.rename",
            title=f"Rename {project.name}",
            payload={"name": name.strip()},
            target_key=str(project.pk),
            target_version=str(project.updated_at.timestamp()),
        )
        return tool_result({"message": "Confirmation required."}, proposals=[proposal])
    return StructuredTool.from_function(propose_project_rename, name="propose_project_rename")

register_tool(ToolSpec(
    name="propose_project_rename",
    description="Propose renaming an editable project; never performs the rename.",
    category="projects",
    mode=ToolMode.PROPOSE,
    required_permissions=frozenset({"projects.change_project"}),
    factory=rename_factory,
))
```

```python
# my_project/agent_actions.py
from django.core.exceptions import PermissionDenied
from agentkit.registry import register_action

def execute_rename(*, proposal, user):
    project = Project.objects.select_for_update().editable_by(user).get(pk=proposal.target_key)
    if str(project.updated_at.timestamp()) != proposal.target_version:
        raise ValueError("Project changed after this proposal was prepared.")
    if not user.has_perm("projects.change_project", project):
        raise PermissionDenied
    project.name = proposal.payload["name"]
    project.save(update_fields=("name", "updated_at"))
    return {"project_id": str(project.pk), "name": project.name}

register_action("projects.rename", execute_rename)
```

The executor must validate the payload again, lock mutable targets, re-check object-level authorization, compare target versions, and make the domain write transaction-safe. Never log the full proposal if it can contain sensitive data.

## 6. Integrate the client

You can copy `frontend/lib/agent-api.ts` and the chat screen or implement the [API contract](API.md) in an existing UI. Keep the browser on a same-origin `/api` path through an application proxy. This avoids leaking internal container hostnames and makes session cookies and CSRF behavior predictable.

If your product uses JWT, OIDC, or another existing authentication mechanism, replace the reference login UI and request helper. Do not run two competing auth systems in the same product.

## 7. Customize safely

Review these in order:

1. Authentication and object ownership
2. System prompt and language
3. Read-only tool authorization
4. Provider data-processing approval
5. Retention and audit requirements
6. Proposed actions and domain conflict checks
7. RAG and document-level access control
8. Generative UI schemas

Keep Pulse-specific policy ingestion, analytics, charts, and business tools as separate integration modules. They were intentionally not copied into the base.
