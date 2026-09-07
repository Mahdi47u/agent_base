# Security model

An LLM is an untrusted planner and text generator. Authentication, authorization, validation, and write execution stay in deterministic application code.

## Non-negotiable boundaries

- Scope every session and proposal lookup by `request.user`.
- Scope every business query before returning rows to a tool.
- Treat page context, model arguments, document text, and tool output as untrusted input.
- Keep provider keys server-side.
- Use an explicit provider allowlist based on privacy/security approval.
- Never give the model a direct side-effect tool when confirmation is required.
- Re-check authorization and target freshness inside the confirmed action transaction.
- Return safe errors to the browser and keep raw exceptions in protected server logs.
- Bound message length, history length, tool output, citations, UI items, and recursion.

## Prompt injection

System prompts are guidance, not a security boundary. A retrieved document may say “ignore previous rules”; tools must still expose only permitted data. Label retrieved text as data in your prompt, keep action execution outside the model loop, and test hostile document content.

## Authentication and CSRF

The reference app uses Django session cookies. CSRF protection remains enabled for login, logout, session mutation, message streaming, and action decisions. The frontend obtains a token before unsafe requests and refreshes it after login rotation.

For production, enable HTTPS and set secure cookie/HSTS settings at the deployment layer. Use the authentication mechanism already approved by the consuming product. Do not expose the Django development server publicly.

## Action proposals

The proposal hash detects database payload mutation; it does not prove the proposal is still correct. `target_version` lets your executor detect a stale target. The registered handler must validate payload shape, permissions, business state, and version under a database lock.

Idempotency is enforced by locking a unique proposal and allowing execution only from `pending`. If an external API is involved, also pass `idempotency_key` to that API or store an outbox record in the same transaction.

## Data retention and privacy

The base limits the number of sessions, not message age. Add a scheduled retention job for your jurisdiction and product policy. Decide whether deletion must also remove provider-side logs, vector-store records, backups, and analytics events.

Do not put secrets, full access tokens, passwords, or unnecessary personal data in messages, citations, action payloads, UI metadata, or audit metadata. Review each provider's storage/training controls before approval.

## Before production

- Replace the development secret and disable debug.
- Restrict allowed hosts and trusted origins.
- Use PostgreSQL for concurrent action confirmation.
- Configure HTTPS, secure cookies, HSTS, proxy headers, timeouts, and SSE buffering.
- Add rate limits per user and per IP.
- Add structured logs, request IDs, metrics, and alerting.
- Define provider and tool timeouts and circuit breakers.
- Review object-level permissions and tenant boundaries.
- Threat-model every action handler and retrieval source.
