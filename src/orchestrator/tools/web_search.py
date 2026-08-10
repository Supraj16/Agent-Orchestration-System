"""Keyless web search tool (DuckDuckGo). Swappable for a paid provider by changing only this
module — specialists depend on the `web_search` tool by name via the registry, not this file."""
from __future__ import annotations


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for a query and return a list of titles, snippets, and URLs."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        hits = list(ddgs.text(query, max_results=max_results))

    if not hits:
        return "No results found."

    lines = []
    for i, hit in enumerate(hits, start=1):
        title = hit.get("title", "")
        body = hit.get("body", "")
        href = hit.get("href", "")
        lines.append(f"{i}. {title}\n   {body}\n   {href}")
    return "\n".join(lines)
