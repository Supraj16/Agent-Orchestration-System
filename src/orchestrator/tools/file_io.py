"""File read/write tools, sandboxed to a single workspace directory. All paths are resolved
relative to WORKSPACE_ROOT and checked to prevent escaping it via `..` or absolute paths."""
from __future__ import annotations

from pathlib import Path

WORKSPACE_ROOT = (Path(__file__).resolve().parents[3] / "data" / "workspace").resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

MAX_READ_BYTES = 200_000
MAX_WRITE_BYTES = 200_000


def _resolve_in_workspace(relative_path: str) -> Path:
    candidate = (WORKSPACE_ROOT / relative_path).resolve()
    if WORKSPACE_ROOT not in candidate.parents and candidate != WORKSPACE_ROOT:
        raise ValueError(f"Path '{relative_path}' escapes the sandboxed workspace directory.")
    return candidate


def read_file(path: str) -> str:
    """Read a text file from the sandboxed workspace. `path` is relative to the workspace root."""
    target = _resolve_in_workspace(path)
    if not target.is_file():
        return f"Error: '{path}' does not exist in the workspace."
    data = target.read_bytes()[:MAX_READ_BYTES]
    return data.decode("utf-8", errors="replace")


def write_file(path: str, content: str) -> str:
    """Write a text file into the sandboxed workspace, creating parent directories as needed."""
    target = _resolve_in_workspace(path)
    payload = content.encode("utf-8")[:MAX_WRITE_BYTES]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return f"Wrote {len(payload)} bytes to {path}"
