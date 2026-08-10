"""E2E: retrieval-augmented planning surfaces relevant memory from a prior task for the same
user, and stays isolated from other users."""
import uuid

from orchestrator.db.task_repo import upsert_task
from orchestrator.memory.long_term import delete_user_memories, extract_and_store_memory, query_similar_memories


def test_memory_retrieval_surfaces_relevant_past_task_and_is_user_scoped():
    user_id = f"e2e-memory-{uuid.uuid4().hex[:8]}"
    task_id = str(uuid.uuid4())
    upsert_task(task_id, user_id=user_id, user_request="original", status="completed")

    try:
        extract_and_store_memory(
            task_id=task_id,
            user_id=user_id,
            user_request="Research best practices for structuring a Python project",
            tool_calls=["web_search"],
            final_output="Use a src layout, virtual environments, and pytest for tests.",
        )

        memories = query_similar_memories(user_id, "How should I organize a new Python codebase?")
        assert len(memories) >= 1
        assert any(kw in memories[0]["summary"].lower() for kw in ("python", "project", "src"))

        assert query_similar_memories(f"{user_id}-someone-else", "python project structure") == []
    finally:
        delete_user_memories(user_id)
