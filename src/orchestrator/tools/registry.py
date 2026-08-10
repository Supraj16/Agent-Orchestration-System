from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Callable

from langchain_core.tools import BaseTool, StructuredTool

from orchestrator.tools.rate_limit import ToolRateLimitExceeded, check_rate_limit


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    allowed_specialists: list[str]
    rate_limit_per_minute: int = 60
    sensitive: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._specs: dict[str, ToolSpec] = {}

    def register(
        self,
        fn: Callable,
        *,
        name: str,
        description: str,
        allowed_specialists: list[str],
        rate_limit_per_minute: int = 60,
        sensitive: bool = False,
    ) -> BaseTool:
        spec = ToolSpec(
            name=name,
            description=description,
            allowed_specialists=allowed_specialists,
            rate_limit_per_minute=rate_limit_per_minute,
            sensitive=sensitive,
        )

        @functools.wraps(fn)
        def guarded(*args, **kwargs):
            allowed, retry_after = check_rate_limit(name, rate_limit_per_minute)
            if not allowed:
                raise ToolRateLimitExceeded(
                    f"Rate limit exceeded for tool '{name}' ({rate_limit_per_minute}/min); retry in {retry_after}s"
                )
            # Logging + tracing happen uniformly for every tool (custom and MCP alike) via
            # ToolObservabilityCallbackHandler, attached at agent-invocation time -- see
            # agents/specialist_factory.py. This wrapper only enforces the rate limit.
            return fn(*args, **kwargs)

        wrapped = StructuredTool.from_function(func=guarded, name=name, description=description)
        self._tools[name] = wrapped
        self._specs[name] = spec
        return wrapped

    def register_prebuilt(
        self,
        tool: BaseTool,
        *,
        allowed_specialists: list[str],
        rate_limit_per_minute: int = 60,
        sensitive: bool = False,
    ) -> BaseTool:
        """Register a tool that's already a BaseTool (e.g. sourced from an MCP server)."""
        self._tools[tool.name] = tool
        self._specs[tool.name] = ToolSpec(
            name=tool.name,
            description=tool.description,
            allowed_specialists=allowed_specialists,
            rate_limit_per_minute=rate_limit_per_minute,
            sensitive=sensitive,
        )
        return tool

    def tools_for_specialist(self, specialist: str) -> list[BaseTool]:
        return [self._tools[n] for n, s in self._specs.items() if specialist in s.allowed_specialists]

    def spec(self, name: str) -> ToolSpec:
        return self._specs[name]

    def all_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())


tool_registry = ToolRegistry()
