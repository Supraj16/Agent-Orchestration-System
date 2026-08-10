"""E2E: a specialist correctly uses its tools to complete a subtask."""
from orchestrator.agents.schemas import Subtask
from orchestrator.agents.specialists.research import run_research_subtask


def test_research_specialist_uses_web_search():
    subtask = Subtask(
        id="st-1",
        description="Find the current stable major version number of the Python programming language.",
        assigned_specialist="research",
        depends_on=[],
        required_inputs="none",
        expected_output_format="one sentence stating the version",
        estimated_complexity=1,
    )
    result = run_research_subtask(subtask, task_id="e2e-tool-use-task")
    assert result.success
    assert len(result.tool_calls) > 0
    assert any(call.startswith("web_search(") for call in result.tool_calls)
