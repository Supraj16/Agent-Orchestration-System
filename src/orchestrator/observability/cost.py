"""LLM token usage + cost tracking. Pricing is list price per million tokens, current as of
2026-08; update when providers change pricing. A LangChain callback captures usage from every
model call (regardless of whether it went through .invoke() or .with_structured_output()) and
records it as a span, keyed by whatever task/subtask/node the current contextvars say we're in.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)

# (input $ / 1M tokens, output $ / 1M tokens)
PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "text-embedding-3-small": (0.02, 0.0),
    # Anthropic (list price; see claude-api skill for current rates)
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def _lookup_rates(model: str) -> tuple[float, float]:
    if model in PRICING_PER_MILLION_TOKENS:
        return PRICING_PER_MILLION_TOKENS[model]
    # Providers often return a dated/versioned model string (e.g. "gpt-4o-mini-2024-07-18")
    # instead of the bare alias we price by -- match the longest known prefix.
    matches = [key for key in PRICING_PER_MILLION_TOKENS if model.startswith(key)]
    if matches:
        return PRICING_PER_MILLION_TOKENS[max(matches, key=len)]
    logger.warning("No pricing entry for model '%s'; cost will be recorded as $0", model)
    return (0.0, 0.0)


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = _lookup_rates(model)
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


class UsageTrackingCallbackHandler(BaseCallbackHandler):
    """Attached at chat-model construction time (see llm/router.py) so it fires for every call
    made through that model instance, including calls wrapped by with_structured_output()."""

    def __init__(self) -> None:
        super().__init__()
        self._start_times: dict[str, float] = {}

    def _record_start(self, run_id: Any, **kwargs: Any) -> None:
        if run_id is not None:
            self._start_times[str(run_id)] = time.monotonic()

    def on_llm_start(self, serialized: dict, prompts: list[str], *, run_id: Any = None, **kwargs: Any) -> None:
        self._record_start(run_id)

    def on_chat_model_start(self, serialized: dict, messages: list, *, run_id: Any = None, **kwargs: Any) -> None:
        self._record_start(run_id)

    def on_llm_end(self, response: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        from orchestrator.observability.tracing import record_llm_usage

        start = self._start_times.pop(str(run_id), None) if run_id is not None else None
        latency_ms = (time.monotonic() - start) * 1000 if start is not None else 0.0

        try:
            for generation_list in response.generations:
                for generation in generation_list:
                    message = getattr(generation, "message", None)
                    usage = getattr(message, "usage_metadata", None) if message else None
                    if not usage:
                        continue
                    model = ""
                    if message is not None:
                        model = (getattr(message, "response_metadata", None) or {}).get("model_name", "")
                    record_llm_usage(
                        model=model,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        latency_ms=latency_ms,
                    )
        except Exception:  # noqa: BLE001 - usage tracking must never break an LLM call
            logger.exception("Failed to record LLM usage")
