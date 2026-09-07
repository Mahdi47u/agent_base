from __future__ import annotations

from .config import AgentConfig


def build_model(provider: str, config: AgentConfig):
    provider = provider.strip().lower()
    if provider not in config.approved_providers:
        raise PermissionError(f"Provider {provider!r} is not approved.")
    if provider == "mock":
        return None, "mock-v1"
    if provider == "openai":
        if not config.openai_api_key or not config.openai_model:
            raise RuntimeError("OPENAI_API_KEY and OPENAI_MODEL must be configured.")
        from langchain_openai import ChatOpenAI

        kwargs = {
            "api_key": config.openai_api_key,
            "model": config.openai_model,
            "temperature": 0,
            "timeout": config.provider_timeout_seconds,
            "max_retries": 1,
        }
        if config.openai_base_url:
            kwargs["base_url"] = config.openai_base_url
        return ChatOpenAI(**kwargs), config.openai_model
    raise RuntimeError(f"Provider {provider!r} has no adapter.")
