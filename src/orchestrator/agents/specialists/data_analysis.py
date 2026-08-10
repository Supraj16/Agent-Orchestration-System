from __future__ import annotations

from orchestrator.agents.schemas import Subtask, SubtaskResult
from orchestrator.agents.specialist_factory import run_specialist_subtask

SYSTEM_PROMPT = """You are the Data Analysis specialist agent. You are given one subtask at a
time. Use query_database for read-only data inspection, execute_python for computation
(pandas/statistics/etc. is available in the sandbox), and read_file/write_file to consume or
save intermediate artifacts. Produce output in exactly the expected_output_format described,
showing your reasoning and any numbers you computed."""


def run_data_analysis_subtask(
    subtask: Subtask,
    task_id: str,
    feedback: str | None = None,
    dependency_outputs: dict[str, str] | None = None,
) -> SubtaskResult:
    return run_specialist_subtask("data_analysis", SYSTEM_PROMPT, subtask, task_id, feedback, dependency_outputs)
