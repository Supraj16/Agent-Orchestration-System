from __future__ import annotations

from orchestrator.agents.schemas import Subtask, SubtaskResult
from orchestrator.agents.specialist_factory import run_specialist_subtask

SYSTEM_PROMPT = """You are the Writing specialist agent. You are given one subtask at a time,
typically synthesizing or polishing content produced by other specialists (passed to you in the
"Outputs from the subtasks this one depends on" section below, if any).

Your final chat response MUST directly contain the complete output matching
expected_output_format — full prose, not a description of it. Only use write_file if the subtask
explicitly asks you to save a file instead of returning text; if you do, still include the full
text in your final response as well, since that response is what gets reviewed. Use
list_directory/directory_tree to browse the shared workspace if you need to find a file. Never
leave the final response empty or merely referencing a file you wrote."""


def run_writing_subtask(
    subtask: Subtask,
    task_id: str,
    feedback: str | None = None,
    dependency_outputs: dict[str, str] | None = None,
) -> SubtaskResult:
    return run_specialist_subtask("writing", SYSTEM_PROMPT, subtask, task_id, feedback, dependency_outputs)
