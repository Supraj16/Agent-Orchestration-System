"""Provider-agnostic LLM access for agent roles.

Each agent role (supervisor / specialist / reviewer) is configured with a provider
in Settings. OpenAI is fully wired now; Anthropic is wired the same way but only
becomes usable once ANTHROPIC_API_KEY is set — no code changes needed to switch.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from orchestrator.config import get_settings

Role = Literal["supervisor", "specialist", "reviewer"]
Provider = Literal["openai", "anthropic"]


def _build_openai(model: str | None = None) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    from orchestrator.observability.cost import UsageTrackingCallbackHandler

    settings = get_settings()
    return ChatOpenAI(
        model=model or settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        callbacks=[UsageTrackingCallbackHandler()],
    )


def _build_anthropic(model: str | None = None) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    from orchestrator.observability.cost import UsageTrackingCallbackHandler

    settings = get_settings()
    return ChatAnthropic(
        model=model or settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0,
        callbacks=[UsageTrackingCallbackHandler()],
    )


_BUILDERS = {
    "openai": _build_openai,
    "anthropic": _build_anthropic,
}


@lru_cache
def get_chat_model(provider: Provider, model: str | None = None) -> BaseChatModel:
    if provider not in _BUILDERS:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return _BUILDERS[provider](model)


def get_model_for_role(role: Role) -> BaseChatModel:
    settings = get_settings()
    provider = {
        "supervisor": settings.supervisor_provider,
        "specialist": settings.specialist_provider,
        "reviewer": settings.reviewer_provider,
    }[role]
    return get_chat_model(provider)  # type: ignore[arg-type]
