# Testing strategy

The fastest reliable route is to test the boundary you changed. Running a real model for every test is slow, nondeterministic, and often checks the wrong thing.

## Pick the right door

| You changed | First test | Then verify | Do not start with |
| --- | --- | --- | --- |
| Query or access scope | Tool unit test with allowed and forbidden users | Tool registry permission test | Browser or real model |
| Tool schema/envelope | Tool unit test | Mocked runtime tool-call test | Prompt tweaking |
| Agent loop | Runtime test with fake model/messages | Mock-provider API SSE test | Production provider |
| SSE parser | Frontend parser unit test with split chunks/CRLF | Browser stream | Full UI snapshot |
| Session API | DRF API test with two owners | Browser history flow | Provider call |
| Action executor | Transaction test: fresh, stale, forbidden, duplicate | API confirmation test | Asking a model to trigger it |
| UI layout | Component/browser test | Real mobile and desktop viewport | Backend test suite |
| Reverse proxy | `curl -N` through the browser-visible URL | Browser network panel | Internal container URL only |
| Provider adapter | Constructor/unit contract | One opt-in smoke request | Entire suite with live billing |

## Commands

```bash
make test-backend
make test-frontend
make typecheck
make migrations       # verifies model/migration agreement without applying schema
```

For an end-to-end local check:

```bash
docker compose up --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Then sign in at <http://localhost:3100>, send a mock message, create a second conversation, reload, and delete one. In browser developer tools, confirm the message response stays `text/event-stream` and terminates with `complete`.

## Required tests for every read tool

- Authorized user receives only allowed records.
- Unauthorized or foreign object looks absent.
- Invalid identifiers and limits produce a bounded safe error.
- Output is JSON-serializable and contains no ORM/model objects.
- Result count and field lengths are bounded.
- Sensitive fields are excluded explicitly, not merely omitted by the prompt.

## Required tests for every proposed write

- Creating a proposal causes no domain write.
- A different user cannot see or confirm it.
- Expired and tampered proposals do not execute.
- Stale `target_version` does not execute.
- Permission is rechecked during confirmation.
- Repeated confirmation executes at most once.
- Domain failure does not report success.
- Successful domain write, proposal status, and audit event commit together.

## Live provider smoke tests

Keep these opt-in and outside the normal unit suite. Use a dedicated low-privilege test account and synthetic data. Assert contract properties—tool selected, no forbidden data, terminal SSE event—rather than exact prose. Record latency and provider/model identifiers but never prompts containing secrets or raw credentials.
