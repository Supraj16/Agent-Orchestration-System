"""Registers every tool with the registry, mapped to the specialists allowed to use it. Called
once (idempotently) before any specialist agent is built."""
from __future__ import annotations

from orchestrator.tools.api_call import call_api
from orchestrator.tools.code_exec import execute_python
from orchestrator.tools.db_query import query_database
from orchestrator.tools.file_io import read_file, write_file
from orchestrator.tools.mcp_client import load_mcp_tools
from orchestrator.tools.registry import tool_registry
from orchestrator.tools.web_search import web_search

_bootstrapped = False


def bootstrap_tools() -> None:
    global _bootstrapped
    if _bootstrapped:
        return

    tool_registry.register(
        web_search,
        name="web_search",
        description="Search the web for a query and return titles, snippets, and URLs.",
        allowed_specialists=["research"],
        rate_limit_per_minute=20,
    )
    tool_registry.register(
        call_api,
        name="call_api",
        description="Call an external HTTP API (GET/POST/PUT/PATCH/DELETE) and return the response.",
        allowed_specialists=["research", "data_analysis"],
        rate_limit_per_minute=20,
        sensitive=True,  # can trigger external side effects -> flagged for HITL (milestone 4)
    )
    tool_registry.register(
        query_database,
        name="query_database",
        description="Run a read-only SQL query (SELECT/WITH only) against the orchestrator database.",
        allowed_specialists=["data_analysis"],
        rate_limit_per_minute=30,
    )
    tool_registry.register(
        execute_python,
        name="execute_python",
        description="Run Python code in an isolated, network-disabled sandbox and return stdout/stderr.",
        allowed_specialists=["data_analysis", "code_execution"],
        rate_limit_per_minute=20,
    )
    tool_registry.register(
        read_file,
        name="read_file",
        description="Read a text file from the shared sandboxed workspace.",
        allowed_specialists=["data_analysis", "writing", "code_execution"],
        rate_limit_per_minute=60,
    )
    tool_registry.register(
        write_file,
        name="write_file",
        description="Write a text file into the shared sandboxed workspace.",
        allowed_specialists=["writing", "code_execution", "data_analysis"],
        rate_limit_per_minute=60,
    )

    # MCP-sourced tools (@modelcontextprotocol/server-filesystem, over stdio) — best-effort,
    # degrades to [] if npx/the server isn't reachable so the rest of the system still starts.
    for mcp_tool in load_mcp_tools():
        tool_registry.register_prebuilt(
            mcp_tool,
            allowed_specialists=["data_analysis", "writing", "code_execution"],
            rate_limit_per_minute=30,
        )

    _bootstrapped = True
