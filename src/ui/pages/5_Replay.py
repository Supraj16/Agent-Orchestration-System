import json
from datetime import datetime

import streamlit as st

from orchestrator.observability.query import list_recent_tasks
from orchestrator.observability.replay import fork_and_replay, list_checkpoints

st.set_page_config(page_title="Replay", page_icon="⏪", layout="wide")
st.title("⏪ Replay / Time Travel")
st.caption(
    "Step through a past task's checkpoint history, then fork from any step with a modified "
    "field to see how execution diverges. Built on LangGraph's own checkpointer -- no separate "
    "replay engine."
)
st.warning(
    "Forking re-runs the graph for real (same task record) -- it isn't a side-effect-free "
    "simulation. New tool calls, LLM calls, and memory writes will happen.",
    icon="⚠️",
)

tasks = list_recent_tasks(limit=50)
if not tasks:
    st.info("No tasks recorded yet. Run scripts/run_task.py first.")
else:
    options = {f"{t['created_at']:%Y-%m-%d %H:%M} — {t['user_request'][:60]} ({t['status']})": t["id"] for t in tasks}
    selected_label = st.selectbox("Task", list(options.keys()))
    task_id = options[selected_label]

    checkpoints = list_checkpoints(task_id)
    step_labels = [
        f"Step {len(checkpoints) - i}: next={cp['next'] or ['(finished)']} "
        f"@ {datetime.fromisoformat(cp['created_at']):%H:%M:%S}"
        for i, cp in enumerate(checkpoints)
    ]
    if not checkpoints:
        st.info("No checkpoints found for this task.")
    else:
        idx = st.selectbox("Checkpoint", range(len(checkpoints)), format_func=lambda i: step_labels[i])
        checkpoint = checkpoints[idx]

        with st.expander("Full state at this checkpoint", expanded=False):
            st.json(json.loads(json.dumps(checkpoint["values"], default=str)))

        st.subheader("Fork from here")
        st.caption("Paste a JSON object of state fields to override (e.g. {\"user_request\": \"...\"}). Leave as {} to replay unmodified.")
        override_text = st.text_area("State overrides (JSON)", value="{}", height=100)

        if st.button("🔀 Fork & Replay", type="primary"):
            try:
                overrides = json.loads(override_text)
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")
            else:
                with st.spinner("Forking and replaying..."):
                    try:
                        result = fork_and_replay(task_id, checkpoint["checkpoint_id"], overrides)
                    except Exception as exc:  # noqa: BLE001 - surfaced directly to the operator
                        st.error(f"Replay failed: {exc}")
                    else:
                        st.success("Replay complete.")
                        st.markdown("**New final output:**")
                        st.write(result.get("final_output"))
