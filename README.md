# Agent Base

A reusable, production-minded chatbot and tool-using agent starter extracted from the architecture of People Pulse. It contains an installable Django app, a small Next.js chat client, a deterministic mock provider, and explicit extension points for model providers, tools, citations, generative UI, and human-approved write actions.

The starter is intentionally domain-neutral. Pulse-specific HR models, permissions, prompts, branding, infrastructure, and credentials are not included.

## What is included

- Persistent, user-owned conversations and messages
- Server-Sent Events (SSE) for tokens, tool progress, completion, and errors
- LangGraph tool loop with an OpenAI-compatible provider adapter
- A no-key mock provider for local development and tests
- Permission-aware tool registry
- Generic, tamper-evident action proposals that require explicit confirmation
- Session-cookie authentication and CSRF-safe login
- Minimal responsive Next.js chat UI
- Docker Compose and VS Code live-development tasks
- Backend and frontend tests plus a CI workflow
- Integration, architecture, API, security, testing, and troubleshooting guides

## Quick start

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Start the live stack:

   ```bash
   docker compose up --build
   ```

3. In another terminal, apply the new local schema and create a user:

   ```bash
   docker compose exec backend python manage.py migrate
   docker compose exec backend python manage.py createsuperuser
   ```

4. Open <http://localhost:3100>, sign in, and chat using the mock provider.

The backend is available at <http://localhost:8100>. Source files are mounted into both containers, so Django autoreload and Next.js hot reload work without rebuilding images.

To use a real OpenAI-compatible model, set `AGENT_PROVIDER=openai`, add `OPENAI_API_KEY`, and restart the backend. See [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Documentation map

- [Architecture and request flow](docs/ARCHITECTURE.md)
- [Adopting Agent Base in another project](docs/INTEGRATION.md)
- [HTTP and SSE API contract](docs/API.md)
- [Testing strategy and the right test door](docs/TESTING.md)
- [Security model](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [What was extracted from Pulse](docs/PULSE_EXTRACTION.md)

## Common commands

```bash
docker compose up --build                   # live full stack
docker compose run --rm backend pytest      # backend tests
docker compose run --rm frontend npm test   # frontend unit tests
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build
```

## Project layout

```text
backend/                 Django project and reusable agentkit app
frontend/                Next.js reference client
docs/                    Architecture and adoption runbooks
.github/workflows/ci.yml GitHub CI
docker-compose.yml       Live local topology
```

## License

MIT. See [LICENSE](LICENSE).
