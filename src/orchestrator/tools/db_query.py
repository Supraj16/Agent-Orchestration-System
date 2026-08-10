"""Read-only SQL query tool. Only SELECT/WITH statements are allowed — agents cannot mutate
or delete data through this tool, only inspect it."""
from __future__ import annotations

import re

from sqlalchemy import text

from orchestrator.db.session import get_engine

_DISALLOWED = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create)\b", re.IGNORECASE
)
MAX_ROWS = 200


def query_database(sql: str) -> str:
    """Run a read-only SQL query (SELECT/WITH only) against the orchestrator database."""
    stripped = sql.strip().rstrip(";")
    if not re.match(r"^\s*(select|with)\b", stripped, re.IGNORECASE):
        return "Error: only SELECT/WITH statements are permitted."
    if _DISALLOWED.search(stripped):
        return "Error: query contains a disallowed keyword (only read-only queries are permitted)."

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(stripped))
        rows = result.fetchmany(MAX_ROWS)
        columns = list(result.keys())

    if not rows:
        return "Query returned no rows."

    lines = [" | ".join(columns)]
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    return "\n".join(lines)
