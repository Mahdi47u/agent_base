# API and SSE contract

All agent endpoints use Django session authentication. Unsafe requests require the `X-CSRFToken` returned by `GET /api/agent/auth/csrf/` and the matching CSRF cookie. The reference Next.js client proxies `/api/*` to Django and sends cookies with `credentials: include`.

## Authentication

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/agent/auth/csrf/` | Set CSRF cookie and return token |
| `POST` | `/api/agent/auth/login/` | Login with `username` and `password` |
| `POST` | `/api/agent/auth/logout/` | End current session |
| `GET` | `/api/agent/auth/me/` | Read current identity |

## Agent endpoints

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/api/agent/capabilities/` | Approved providers and authorized tool manifest |
| `GET` | `/api/agent/sessions/` | Current user's newest conversations |
| `POST` | `/api/agent/sessions/` | Create a conversation |
| `GET/PATCH/DELETE` | `/api/agent/sessions/{id}/` | Read, rename/reconfigure, or delete owned conversation |
| `POST` | `/api/agent/sessions/{id}/messages/stream/` | Run agent and stream SSE |
| `POST` | `/api/agent/actions/{id}/confirm/` | Confirm an owned pending proposal |
| `POST` | `/api/agent/actions/{id}/cancel/` | Cancel an owned pending proposal |

Unknown or foreign session/proposal IDs return `404`, not `403`, to avoid revealing their existence.

## Message request

```json
{
  "content": "What changed in this project?",
  "context": {
    "pathname": "/projects/123",
    "entity": { "type": "project", "id": "123" }
  }
}
```

`content` is limited to 12,000 characters. `context` is limited to 4 KiB and is untrusted model context—not authorization evidence.

## SSE events

Every frame has an explicit event and one JSON data line:

```text
event: delta
data: {"text":"partial text"}

```

Event order:

1. `start` exactly once
2. zero or more `tool` and `delta` events
3. exactly one terminal `complete` or `error`

Payloads:

```json
{"event":"start","session_id":"uuid","request_id":"caller-id"}
{"event":"tool","tool":"get_project","tool_call_id":"call-id","status":"running"}
{"event":"tool","tool":"get_project","tool_call_id":"call-id","status":"complete","duration_ms":81}
{"event":"delta","text":"partial model text"}
```

The `complete` payload contains `message_id`, `content`, `provider`, `model`, `proposals`, `citations`, `tool_events`, and `ui`. The `error` payload contains a stable error code, a safe user message, a request ID, and a retryable flag. It never includes the raw exception.

Reverse proxies must disable response buffering and compression for this route. The backend sends `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, and identity encoding.

## Tool result envelope

Registered tools return a JSON string:

```json
{
  "ok": true,
  "data": {},
  "citations": [],
  "proposals": [],
  "ui": []
}
```

On expected failure:

```json
{"ok":false,"error":{"code":"not_found","message":"Safe explanation"}}
```

Only proposal IDs found in the database for the current owner and session are sent to the client. A model-authored proposal object cannot manufacture a confirmable write.
