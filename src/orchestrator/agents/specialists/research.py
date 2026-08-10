from __future__ import annotations

from orchestrator.agents.schemas import Subtask, SubtaskResult
from orchestrator.agents.specialist_factory import run_specialist_subtask

SYSTEM_PROMPT = """You are the Research specialist agent. You are given one subtask at a time.
Use web_search to find sources and call_api for structured external data when useful. Produce
output in exactly the expected_output_format described. Be concise and cite sources by URL
where relevant."""


def run_research_subtask(
    subtask: Subtask,
    task_id: str,
    feedback: str | None = None,
    dependency_outputs: dict[str, str] | None = None,
) -> SubtaskResult:
    return run_specialist_subtask("research", SYSTEM_PROMPT, subtask, task_id, feedback, dependency_outputs)
