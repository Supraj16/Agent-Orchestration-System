import pandas as pd
import streamlit as st

from orchestrator.memory.importance import run_memory_maintenance
from orchestrator.memory.long_term import delete_user_memories, list_user_memories

st.set_page_config(page_title="Memory Dashboard", page_icon="🧠", layout="wide")
st.title("🧠 Memory Dashboard")
st.caption("What the system remembers about a user — and a way to delete it on request.")

user_id = st.text_input("User ID", value="demo-user")

col_load, col_maintain, col_delete = st.columns(3)
with col_load:
    load_clicked = st.button("Load memories", type="primary")
with col_maintain:
    maintain_clicked = st.button("Run maintenance now")
with col_delete:
    delete_clicked = st.button("Delete all memories for this user", type="secondary")

if maintain_clicked:
    with st.spinner("Applying decay and consolidating near-duplicate memories across all users..."):
        result = run_memory_maintenance()
    st.success(
        f"Decay: {result['decayed_updated']} updated, {result['expired']} expired. "
        f"Consolidation: {result['consolidation_merges']} merge(s)."
    )

if delete_clicked:
    deleted = delete_user_memories(user_id)
    st.warning(f"Deleted {deleted} memory record(s) for user '{user_id}'.")

if load_clicked or maintain_clicked or delete_clicked:
    memories = list_user_memories(user_id)
    if not memories:
        st.info(f"No memories stored for user '{user_id}' yet.")
    else:
        df = pd.DataFrame(memories)
        df = df[["importance_score", "access_count", "last_accessed_at", "created_at", "summary", "id"]]
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "importance_score": st.column_config.ProgressColumn(
                    "Importance", min_value=0.0, max_value=1.0, format="%.2f"
                ),
                "summary": st.column_config.TextColumn("Summary", width="large"),
            },
            hide_index=True,
        )
