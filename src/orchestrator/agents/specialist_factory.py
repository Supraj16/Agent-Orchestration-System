from __future__ import annotations

from langchain.agents import create_agent

from orchestrator.agents.schemas import Subtask, SubtaskResult
from orchestrator.llm.router import get_model_for_role
from orchestrator.observability.context import current_subtask_id, current_task_id
from orchestrator.observability.tool_logging import ToolObservabilityCallbackHandler
from orchestrator.tools.bootstrap import bootstrap_tools
from orchestrator.tools.registry import tool_registry


def run_specialist_subtask(
    specialist_name: str,
    system_prompt: str,
    subtask: Subtask,
    task_id: str,
    feedback: str | None = None,
    dependency_outputs: dict[str, str] | None = None,
) -> SubtaskResult:
    bootstrap_tools()
    tools = tool_registry.tools_for_specialist(specialist_name)
    agent = create_agent(get_model_for_role("specialist"), tools=tools, system_prompt=system_prompt)

    prompt = (
        f"Subtask: {subtask.description}\n"
        f"Required inputs/context: {subtask.required_inputs}\n"
        f"Expected output format: {subtask.expected_output_format}"
    )
    if dependency_outputs:
        rendered = "\n\n".join(f"--- Output of '{dep_id}' ---\n{output}" for dep_id, output in dependency_outputs.items())
        prompt += f"\n\nOutputs from the subtasks this one depends on:\n{rendered}"
    if feedback:
        prompt += f"\n\nThe reviewer rejected your previous attempt. Feedback:\n{feedback}"

    task_token = current_task_id.set(task_id)
    subtask_token = current_subtask_id.set(subtask.id)
    tool_calls: list[str] = []
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"callbacks": [ToolObservabilityCallbackHandler()]},
        )
        messages = result["messages"]
        for msg in messages:
            for call in getattr(msg, "tool_calls", None) or []:
                tool_calls.append(f"{call['name']}({call['args']})")

        final_output = messages[-1].content
        return SubtaskResult(subtask_id=subtask.id, output=final_output, tool_calls=tool_calls, success=True)
    except Exception as exc:  # noqa: BLE001 - specialist failures are routed, not raised
        return SubtaskResult(subtask_id=subtask.id, output="", tool_calls=tool_calls, success=False, error=str(exc))
    finally:
        current_task_id.reset(task_token)
        current_subtask_id.reset(subtask_token)
