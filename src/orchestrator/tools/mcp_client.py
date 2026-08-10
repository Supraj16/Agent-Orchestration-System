"""Sources tools from a real MCP server (the official filesystem reference server,
`@modelcontextprotocol/server-filesystem`, launched over stdio via `npx`) instead of
hand-writing them. This proves the "Custom + MCP" tool framework: agents call these tools
through the exact same registry as the hand-written ones and can't tell the difference.

Only tools that don't collide with our custom `read_file`/`write_file` (in
`orchestrator.tools.file_io`) are pulled in, so the MCP integration adds genuinely new
capabilities (browsing/searching the workspace) rather than shadowing the sandboxed custom
tools.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from pathlib import Path

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = str((Path(__file__).resolve().parents[3] / "data" / "workspace").resolve())

_MCP_FILESYSTEM_CONNECTION = {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", _WORKSPACE_ROOT],
}

# read_file/write_file are deliberately excluded: they'd shadow our own sandboxed tools
# (orchestrator.tools.file_io) of the same name in the registry.
INCLUDED_TOOL_NAMES = {"list_directory", "directory_tree", "search_files", "get_file_info"}


def _add_sync_bridge(tool: BaseTool) -> BaseTool:
    """langchain-mcp-adapters builds MCP tools with only an async `coroutine` (no sync `func`)
    -- each call opens its own fresh MCP session, so bridging with asyncio.run() per call is
    safe. Our specialist agents run synchronously (create_agent(...).invoke()), so without this
    every MCP tool call fails with "StructuredTool does not support sync invocation"."""
    if getattr(tool, "func", None) is None and getattr(tool, "coroutine", None) is not None:
        coroutine = tool.coroutine
        tool.func = lambda *args, **kwargs: asyncio.run(coroutine(*args, **kwargs))
    return tool


async def _load_mcp_tools_async() -> list[BaseTool]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({"filesystem": _MCP_FILESYSTEM_CONNECTION})
    tools = await client.get_tools(server_name="filesystem")
    return [_add_sync_bridge(t) for t in tools if t.name in INCLUDED_TOOL_NAMES]


def _has_working_fileno(stream) -> bool:
    try:
        stream.fileno()
        return True
    except Exception:
        return False


@contextlib.contextmanager
def _real_stdio():
    """Celery's prefork workers replace sys.stdout/stderr with a LoggingProxy that has no
    working fileno() -- asyncio's subprocess creation (used here to launch the MCP server via
    npx) needs a real file descriptor to redirect the child's stdio to. Swap in the original
    streams (still reachable via sys.__stdout__/__stderr__) for the duration of the call."""
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    swapped = False
    if sys.__stdout__ is not None and not _has_working_fileno(sys.stdout):
        sys.stdout = sys.__stdout__
        swapped = True
    if sys.__stderr__ is not None and not _has_working_fileno(sys.stderr):
        sys.stderr = sys.__stderr__
        swapped = True
    try:
        yield
    finally:
        if swapped:
            sys.stdout, sys.stderr = orig_stdout, orig_stderr


def load_mcp_tools(timeout_seconds: float = 60.0) -> list[BaseTool]:
    """Best-effort load of MCP-sourced tools. Returns [] (and logs) if the MCP server can't be
    reached, e.g. `npx` isn't available — the rest of the system should not fail to start just
    because one optional MCP integration is unavailable."""
    try:
        with _real_stdio():
            return asyncio.run(asyncio.wait_for(_load_mcp_tools_async(), timeout=timeout_seconds))
    except Exception:
        logger.warning("Could not load MCP filesystem server tools; continuing without them.", exc_info=True)
        return []
