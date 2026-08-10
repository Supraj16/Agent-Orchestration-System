import json

import pandas as pd
import streamlit as st

from orchestrator.observability.query import get_task_cost_summary, get_trace_tree, list_recent_tasks

st.set_page_config(page_title="Trace Explorer", page_icon="🔍", layout="wide")
st.title("🔍 Trace Explorer")
st.caption("Every agent decision, tool call, and LLM call for one task, as a tree.")

STATUS_COLORS = {
    "success": "#1a7f37",
    "error": "#cf222e",
    "escalated": "#9a6700",
    "paused": "#0969da",
}
KIND_ICONS = {"agent": "🤖", "tool": "🔧", "llm_call": "🧠", "system": "⚙️", "escalation": "🛂"}


def render_span(span: dict, children_by_parent: dict, depth: int = 0) -> None:
    color = STATUS_COLORS.get(span["status"], "#57606a")
    icon = KIND_ICONS.get(span["span_kind"], "•")
    indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * depth
    label = f"{indent}{icon} **{span['name']}** — <span style='color:{color}'>{span['status']}</span> ({span['latency_ms']:.0f}ms)"
    st.markdown(label, unsafe_allow_html=True)

    with st.expander("details", expanded=False):
        attrs = dict(span["attributes"])
        result_raw = attrs.pop("result", None)
        st.json(attrs)
        if result_raw:
            try:
                st.markdown("**Result:**")
                st.json(json.loads(result_raw))
            except (TypeError, ValueError):
                st.text(result_raw)

    for child in children_by_parent.get(span["span_id"], []):
        render_span(child, children_by_parent, depth + 1)


tasks = list_recent_tasks(limit=50)
if not tasks:
    st.info("No tasks recorded yet. Run scripts/run_task.py first.")
else:
    options = {f"{t['created_at']:%Y-%m-%d %H:%M} — {t['user_request'][:60]} ({t['status']})": t["id"] for t in tasks}
    selected_label = st.selectbox("Task", list(options.keys()))
    task_id = options[selected_label]

    cost = get_task_cost_summary(task_id)
    cols = st.columns(4)
    cols[0].metric("Total cost", f"${cost['total_cost_usd']:.4f}")
    cols[1].metric("LLM calls", cost["llm_call_count"])
    cols[2].metric("Tool calls", cost["tool_call_count"])
    cols[3].metric("Tokens (in/out)", f"{cost['total_input_tokens']}/{cost['total_output_tokens']}")

    st.divider()

    spans = get_trace_tree(task_id)
    if not spans:
        st.info("No spans recorded for this task.")
    else:
        children_by_parent: dict = {}
        roots = []
        for span in spans:
            if span["parent_span_id"]:
                children_by_parent.setdefault(span["parent_span_id"], []).append(span)
            else:
                roots.append(span)

        for root in roots:
            render_span(root, children_by_parent)
