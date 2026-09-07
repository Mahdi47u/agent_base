# Troubleshooting

## Decide which layer failed

1. `GET http://localhost:8100/api/health/` fails: backend process, host port, or container health.
2. Backend health works but `http://localhost:3100/api/health/` fails: Next.js rewrite or `BACKEND_URL`.
3. Login returns `403`: CSRF cookie/header mismatch or incorrect trusted origin.
4. Login returns `401`: request reached Django; username/password or active status is wrong.
5. Session API returns `403`: browser has no valid session cookie or agent is disabled.
6. Message request returns JSON instead of SSE: validation/auth failed before streaming.
7. SSE starts then emits `error`: provider, tool, graph, or persistence failed; correlate the request ID in backend logs.
8. Internal URL works but browser URL fails: test the published host port and same-origin proxy, not the Docker service name.

## Common fixes

### `no such table` or login crashes

The local schema has not been applied:

```bash
docker compose exec backend python manage.py migrate
```

Do this only for the intended local database. In an established project, review migrations before applying them.

### `CSRF verification failed`

- Access the UI through exactly `http://localhost:3100`.
- Ensure `DJANGO_CSRF_TRUSTED_ORIGINS` contains that complete origin.
- Do not mix `127.0.0.1` and `localhost` between requests.
- Clear cookies after changing hosts.
- Confirm the client fetches `/api/agent/auth/csrf/` before POST and refreshes after login.

### The request hangs until the full answer appears

A proxy is buffering SSE. Disable proxy buffering and compression for the message stream. Test with:

```bash
curl -N -b cookies.txt -H 'Accept: text/event-stream' http://localhost:3100/api/agent/sessions/SESSION/messages/stream/
```

Use a valid CSRF-protected POST when doing the full request; the example is only to inspect routing behavior.

### `/api/path/` and `/api/path` redirect forever

Next.js and Django are fighting over slash normalization. Keep `skipTrailingSlashRedirect: true` and the trailing slash in the rewrite destination (`/api/:path*/`) in `next.config.ts`. The reference client consistently calls slash-terminated Django routes.

### Provider is not approved

Both conditions must be true: the provider appears in `AGENT_APPROVED_PROVIDERS`, and `providers.py` has an adapter. Add approval only after the provider's data-handling review.

### Mock works but OpenAI does not

Check backend-only `OPENAI_API_KEY`, exact `OPENAI_MODEL`, optional compatible `OPENAI_BASE_URL`, outbound network access, and timeout. Never add the key to a `NEXT_PUBLIC_*` variable.

### A tool never appears

- Its module must be in `TOOL_MODULES` and import without error.
- The `ToolSpec.name` must match the `StructuredTool.name`.
- Required permissions and `is_available` must pass for the current user.
- Restart Django after adding a module; registry loading happens during app startup.

### An action stays pending or conflicts

Confirm that the action module is loaded, its type matches exactly, and the executor can find the target in the user's current access scope. A changed `target_version` should conflict; create a fresh proposal rather than bypassing that check.

## Useful checks

```bash
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
docker compose exec backend python manage.py check
docker compose run --rm backend pytest
docker compose run --rm frontend npm test
docker compose run --rm frontend npm run typecheck
```

Do not diagnose browser routing with only an internal address such as `http://backend:8000`; that hostname is for containers, not the host browser.
