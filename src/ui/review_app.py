"""Entry point for the operator UI (Streamlit multi-page app).

Run with: streamlit run src/ui/review_app.py
"""
import streamlit as st

st.set_page_config(page_title="Agent Orchestrator", page_icon="🤖", layout="wide")

st.title("Agent Orchestration System — Operator Console")
st.markdown(
    """
Use the sidebar to navigate:

- **Memory Dashboard** — see what the system remembers about a user, and delete it on request.
- **Approval Queue** — escalations waiting on a human decision: approve, modify, reject, or take
  over, with full task context and relevant past memories.
- **Trace Explorer** — every agent decision, tool call, and LLM call for one task, as a tree,
  color-coded by status, with full prompt/response detail.
- **Cost Dashboard** — LLM spend by model and agent node, tool usage counts, and escalation rate
  across recent tasks.
- **Replay** — step through a past task's checkpoint history and fork from any step with a
  modified field to see how execution diverges.
"""
)
