from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.base import SerializerProtocol
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from orchestrator.config import get_settings

_checkpointer: PostgresSaver | None = None


@lru_cache
def get_pool() -> ConnectionPool:
    conninfo = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    return ConnectionPool(conninfo=conninfo, max_size=10, kwargs={"autocommit": True, "row_factory": dict_row})


def get_checkpointer(serde: SerializerProtocol | None = None) -> PostgresSaver:
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = PostgresSaver(get_pool(), serde=serde)
        _checkpointer.setup()
    return _checkpointer
