from __future__ import annotations

from fastapi import FastAPI

from api.routes import approvals, memory, tasks, traces

app = FastAPI(title="Agent Orchestration System", version="0.1.0")

app.include_router(tasks.router)
app.include_router(approvals.router)
app.include_router(memory.router)
app.include_router(traces.router)


@app.get("/health")
def health():
    return {"status": "ok"}
