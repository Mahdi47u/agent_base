from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True, slots=True)
class AgentConfig:
    enabled: bool
    default_provider: str
    approved_providers: frozenset[str]
    system_prompt: str
    history_limit: int
    max_sessions: int
    action_ttl_seconds: int
    provider_timeout_seconds: int
    openai_api_key: str
    openai_model: str
    openai_base_url: str
    tool_modules: tuple[str, ...]
    action_modules: tuple[str, ...]


def get_config() -> AgentConfig:
    values = getattr(settings, "AGENT_BASE", {})
    approved = values.get("APPROVED_PROVIDERS", "mock")
    if isinstance(approved, str):
        approved = frozenset(item.strip().lower() for item in approved.split(",") if item.strip())
    else:
        approved = frozenset(str(item).strip().lower() for item in approved)
    return AgentConfig(
        enabled=bool(values.get("ENABLED", False)),
        default_provider=str(values.get("DEFAULT_PROVIDER", "mock")).strip().lower(),
        approved_providers=approved,
        system_prompt=str(values.get("SYSTEM_PROMPT", "You are a helpful assistant.")),
        history_limit=max(2, min(int(values.get("HISTORY_LIMIT", 40)), 200)),
        max_sessions=max(1, min(int(values.get("MAX_SESSIONS", 50)), 500)),
        action_ttl_seconds=max(30, min(int(values.get("ACTION_TTL_SECONDS", 600)), 86400)),
        provider_timeout_seconds=max(1, min(int(values.get("PROVIDER_TIMEOUT_SECONDS", 45)), 300)),
        openai_api_key=str(values.get("OPENAI_API_KEY", "")),
        openai_model=str(values.get("OPENAI_MODEL", "")),
        openai_base_url=str(values.get("OPENAI_BASE_URL", "")),
        tool_modules=tuple(values.get("TOOL_MODULES", ())),
        action_modules=tuple(values.get("ACTION_MODULES", ())),
    )
