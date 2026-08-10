import pandas as pd
import streamlit as st
from langchain_core.messages import HumanMessage

from orchestrator.db.task_repo import get_task
from orchestrator.hitl.approval_queue import get_pending_approvals
from orchestrator.hitl.resume import resume_task
from orchestrator.llm.router import get_model_for_role
from orchestrator.memory.long_term import query_similar_memories

st.set_page_config(page_title="Approval Queue", page_icon="🛂", layout="wide")
st.title("🛂 Approval Queue")
st.caption("Escalations waiting on a human decision — full context, then approve / modify / reject / take over.")

LEVEL_LABELS = {
    "approve_plan": "🗂️ Approve Plan",
    "approve_action": "⚠️ Approve Action",
    "take_over": "🆘 Take Over",
    "notify": "ℹ️ Notify",
}


def render_context(kind: str, ctx: dict) -> None:
    if kind == "plan":
        st.markdown(f"**Reasoning:** {ctx.get('reasoning') or ctx.get('reason', '')}")
        st.markdown(f"**Confidence:** {ctx.get('plan', {}).get('confidence', ctx.get('confidence'))}")
        subtasks = ctx.get("plan", {}).get("subtasks", [])
        if subtasks:
            st.dataframe(pd.DataFrame(subtasks), use_container_width=True, hide_index=True)
    elif kind == "sensitive_action":
        st.markdown(f"**Subtask:** {ctx.get('subtask_description')}")
        st.markdown(f"**Sensitive tool(s) used:** {', '.join(ctx.get('sensitive_tools', []))}")
        with st.expander("Tool calls"):
            for call in ctx.get("tool_calls", []):
                st.code(call, language=None)
        st.markdown("**Proposed output:**")
        st.write(ctx.get("proposed_output"))
    elif kind == "takeover_subtask":
        st.markdown(f"**Subtask:** {ctx.get('subtask_description')}")
        st.markdown(f"**Failed attempts:** {ctx.get('attempts')}")
        st.markdown(f"**Last reviewer feedback:** {ctx.get('last_feedback')}")
        st.markdown("**Last (rejected) output:**")
        st.write(ctx.get("last_output"))


def render_approval(approval: dict) -> None:
    task = get_task(approval["task_id"]) or {}
    level_label = LEVEL_LABELS.get(approval["level"], approval["level"])

    with st.container(border=True):
        st.subheader(f"{level_label} — task `{approval['task_id'][:8]}`")
        st.caption(f"Requested: {task.get('user_request', '(unknown)')}")

        render_context(approval["kind"], approval["context"])

        user_id = task.get("user_id")
        if user_id:
            memories = query_similar_memories(user_id, task.get("user_request", ""), top_k=3)
            if memories:
                with st.expander("Relevant memories / past similar decisions"):
                    for mem in memories:
                        st.markdown(f"- {mem['summary']}")

        with st.expander("Ask the agent a clarifying question before deciding"):
            question = st.text_input("Question", key=f"question_{approval['id']}")
            if st.button("Ask", key=f"ask_{approval['id']}") and question:
                model = get_model_for_role("supervisor")
                prompt = (
                    f"An operator is reviewing this pending escalation:\n{approval['context']}\n\n"
                    f"Original user request: {task.get('user_request')}\n\n"
                    f"Operator's question: {question}\n\nAnswer concisely."
                )
                answer = model.invoke([HumanMessage(content=prompt)]).content
                st.info(answer)

        edited_content = st.text_area(
            "Edited content (used for Modify / Take Over)", key=f"edit_{approval['id']}", height=100
        )

        cols = st.columns(4)
        action = None
        if cols[0].button("✅ Approve", key=f"approve_{approval['id']}", type="primary"):
            action = "approve"
        if cols[1].button("✏️ Modify", key=f"modify_{approval['id']}"):
            action = "modify"
        if cols[2].button("❌ Reject", key=f"reject_{approval['id']}"):
            action = "reject"
        if cols[3].button("🆘 Take Over", key=f"takeover_{approval['id']}"):
            action = "take_over"

        if action:
            resolution = {
                "action": action,
                "edited_content": edited_content or None,
                "resolver": st.session_state.get("operator_name", "operator"),
            }
            with st.spinner(f"Resuming task with resolution '{action}'..."):
                result = resume_task(approval["task_id"], resolution)
            if result["paused"]:
                st.warning("Task paused again for further review — refresh to see the new escalation.")
            else:
                st.success("Task resumed and completed. See the Trace/Task views for the result.")
                st.write(result["values"].get("final_output"))
            st.rerun()


st.session_state.setdefault("operator_name", "operator")
st.text_input("Your name (recorded as resolver)", key="operator_name")

if st.button("🔄 Refresh"):
    st.rerun()

pending = get_pending_approvals()
if not pending:
    st.info("No approvals pending. 🎉")
else:
    for approval in pending:
        render_approval(approval)
