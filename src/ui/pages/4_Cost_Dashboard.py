import pandas as pd
import streamlit as st

from orchestrator.observability.query import get_aggregate_cost_stats

st.set_page_config(page_title="Cost Dashboard", page_icon="💰", layout="wide")
st.title("💰 Cost & Performance Dashboard")
st.caption("Aggregated across the most recent tasks — LLM spend, tool usage, and escalation rate.")

limit = st.slider("Tasks to include", min_value=10, max_value=500, value=200, step=10)
stats = get_aggregate_cost_stats(limit_tasks=limit)

if stats["task_count"] == 0:
    st.info("No tasks recorded yet. Run scripts/run_task.py first.")
else:
    cols = st.columns(4)
    cols[0].metric("Tasks", stats["task_count"])
    cols[1].metric("Total LLM cost", f"${stats['total_cost_usd']:.4f}")
    cols[2].metric("Avg cost / task", f"${stats['total_cost_usd'] / stats['task_count']:.4f}")
    cols[3].metric("Escalation rate", f"{stats['escalation_rate'] * 100:.1f}%")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Cost by model")
        if stats["by_model"]:
            df = pd.DataFrame(
                [{"model": k, "cost_usd": v["cost_usd"], "calls": v["calls"]} for k, v in stats["by_model"].items()]
            ).set_index("model")
            st.bar_chart(df["cost_usd"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No LLM calls recorded.")

    with col2:
        st.subheader("Cost by agent node")
        if stats["by_node"]:
            df = pd.DataFrame(
                [{"node": k, "cost_usd": v["cost_usd"], "calls": v["calls"]} for k, v in stats["by_node"].items()]
            ).set_index("node")
            st.bar_chart(df["cost_usd"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No LLM calls recorded.")

    st.divider()
    st.subheader("Tool usage")
    if stats["tool_usage"]:
        df = (
            pd.DataFrame([{"tool": k, "calls": v} for k, v in stats["tool_usage"].items()])
            .set_index("tool")
            .sort_values("calls", ascending=False)
        )
        st.bar_chart(df["calls"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No tool calls recorded.")
