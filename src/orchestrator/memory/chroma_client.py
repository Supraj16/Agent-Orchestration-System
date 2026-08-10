from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions

from orchestrator.config import get_settings

COLLECTION_NAME = "task_memories"


@lru_cache
def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


@lru_cache
def get_memory_collection() -> Collection:
    settings = get_settings()
    embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=settings.openai_api_key, model_name="text-embedding-3-small"
    )
    return get_chroma_client().get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=embedding_fn, metadata={"hnsw:space": "cosine"}
    )
