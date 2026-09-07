# Pulse extraction notes

This repository is an architectural extraction, not a source dump. The People Pulse source workspace was read but not modified.

## Mapping

| Pulse area | Agent Base destination | Treatment |
| --- | --- | --- |
| `apps/agent/runtime.py` | `agentkit/runtime.py` | Kept bounded history, provider gating, LangGraph loop, tool timing, and streaming; made prompt/language configurable |
| `apps/agent/models.py` | `agentkit/models.py` | Kept sessions, messages, citations, proposals, and audits; removed service-desk and policy/benchmark foreign keys |
| `apps/agent/views.py` | `agentkit/views.py` | Kept owner scoping, session cap, SSE headers, safe terminal errors, persistence |
| `apps/agent/tooling/*` | `contracts.py`, `registry.py`, `default_tools.py` | Replaced fixed HR categories with importable tool modules and generic permission gates |
| `apps/agent/actions.py` | `agentkit/actions.py` | Replaced request-specific writes with a generic registered executor boundary |
| `apps/agent/rag.py` and vector ports | Integration guide only | Omitted because retrieval storage and document permissions are product-specific |
| `features/agent/api.ts` | `frontend/lib/agent-api.ts` | Kept typed SSE parser, terminal-event handling, and request contract; added session/CSRF helper |
| `manager-assistant.tsx` | `frontend/app/page.tsx` | Reduced dependencies and Pulse navigation; kept history, cancellation, progress, citations, proposals |
| `generative-ui.tsx` | Envelope and extension docs | Omitted HR cards/charts; client ignores unknown UI until a consuming project validates/renderers them |

## Intentionally excluded

- Nilva and People Pulse names, logos, Persian-only copy, employee data, service-desk requests, voting, analytics, and role helpers
- Deployment IDs, GitLab/Yadollah configuration, internal registries, internal endpoints, and environment files
- Qdrant collections and policy repository paths
- Provider credentials and private model gateway details
- Existing Pulse migrations and production history

## Improvements made during extraction

- Same-origin session authentication is included instead of assuming the host application's auth helpers.
- Provider settings are centralized and fail closed.
- Tool and action modules are explicit extension points.
- Confirmable proposals are reloaded from the database rather than trusted from model output.
- The base uses a deterministic no-key provider so local UI and API work before model integration.
- Documentation separates query, orchestration, streaming, action, and browser test doors.

## Features to add only when a project needs them

- PostgreSQL and tenant-aware row scoping
- RAG ingestion/versioning/vector aliases
- Generative charts or domain cards with strict schemas
- Background jobs for long tools and retention cleanup
- Provider benchmarking and evaluation datasets
- OAuth/OIDC/JWT integration
- Outbox processing for external write actions

These are intentionally extensions, because making them generic without a real domain often weakens authorization and produces misleading tests.
