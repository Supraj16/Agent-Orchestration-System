"""Submit a new task directly from the Operator Console, instead of the CLI
(scripts/run_task.py). Runs the same graph, in this Streamlit process, so you see live
node-by-node progress and the final output right here.

Run with the rest of the app: streamlit run src/ui/review_app.py
"""
from __future__ import annotations

import uuid

import streamlit as st

from orchestrator.graph.build_graph import build_graph, initial_state

st.set_page_config(page_title="Submit Task", page_icon="🚀", layout="wide")
st.title("🚀 Submit Task")
st.caption(
    "Kick off a new task through the full agent graph (Supervisor → specialists → "
    "Reviewer → Synthesis) without touching the terminal. If it escalates for human review, "
    "it pauses here — resolve it on the Approval Queue page, then come back."
)


def _summarize(update: dict) -> str:
    """Mirrors scripts/run_task.py's _summarize so the CLI and UI report progress identically."""
    parts = []
    if "plan" in update and update["plan"] is not None:
        plan = update["plan"]
        parts.append(f"plan with {len(plan.subtasks)} subtask(s), confidence={plan.confidence:.2f}")
    if "current_subtask_id" in update:
        parts.append(f"current_subtask_id={update['current_subtask_id']}")
    if "pending_result" in update and update["pending_result"] is not None:
        parts.append(f"specialist_success={update['pending_result'].success}")
    if "latest_review" in update and update["latest_review"] is not None:
        review = update["latest_review"]
        parts.append(f"review={review.verdict.value} score={review.quality_score:.2f}")
    if update.get("escalated"):
        parts.append(f"escalated={update['escalated']}")
    if "final_output" in update and update["final_output"]:
        parts.append("final_output produced")
    return ", ".join(parts) if parts else str(update)


with st.form("submit_task"):
    user_request = st.text_area(
        "Task request", height=100,
        placeholder="Write a short report comparing LangGraph and a plain LangChain AgentExecutor.",
    )
    col1, col2 = st.columns([3, 1])
    user_id = col1.text_input("User ID", value="demo-user")
    force_review = col2.checkbox(
        "Force human review", value=False,
        help="Always pause for plan approval before executing (same as --force-review on the CLI).",
    )
    submitted = st.form_submit_button("▶️ Run task", type="primary")

if submitted:
    if not user_request.strip():
        st.error("Enter a task request first.")
        st.stop()

    task_id = str(uuid.uuid4())
    graph = build_graph()
    config = {"configurable": {"thread_id": task_id}}

    st.info(f"Task `{task_id}` — user `{user_id}`")
    log = st.container(border=True)
    paused = False
    interrupt_payload = None

    with st.spinner("Running through Supervisor → specialists → Reviewer..."):
        for step in graph.stream(
            initial_state(task_id, user_request, user_id, force_review),
            config=config,
            stream_mode="updates",
        ):
            if "__interrupt__" in step:
                paused = True
                interrupt_payload = step["__interrupt__"][0].value
                break
            for node_name, update in step.items():
                log.write(f"**[{node_name}]** {_summarize(update)}")

    if paused:
        st.warning(
            f"⏸️ Paused for human review — level `{interrupt_payload.get('level')}`, "
            f"kind `{interrupt_payload.get('kind')}`.\n\n"
            f"Reason: {interrupt_payload.get('reason', '')}"
        )
        if st.button("Go to Approval Queue →"):
            st.switch_page("pages/2_Approval_Queue.py")
    else:
        state = graph.get_state(config).values
        st.success("✅ Task completed.")
        st.markdown("### Final output")
        st.write(state.get("final_output"))
