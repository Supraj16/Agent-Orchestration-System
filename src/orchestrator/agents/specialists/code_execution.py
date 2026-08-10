from __future__ import annotations

from orchestrator.agents.schemas import Subtask, SubtaskResult
from orchestrator.agents.specialist_factory import run_specialist_subtask

SYSTEM_PROMPT = """You are the Code Execution specialist agent. You are given one subtask at a
time. Use execute_python to run and verify code in an isolated, network-disabled sandbox
(pandas/numpy available), and read_file/write_file for supporting files. Always run and verify
code before reporting a result. Produce output in exactly the expected_output_format described,
including the code you ran and its actual output."""


def run_code_execution_subtask(
    subtask: Subtask,
    task_id: str,
    feedback: str | None = None,
    dependency_outputs: dict[str, str] | None = None,
) -> SubtaskResult:
    return run_specialist_subtask("code_execution", SYSTEM_PROMPT, subtask, task_id, feedback, dependency_outputs)
