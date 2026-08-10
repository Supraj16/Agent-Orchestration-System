# mcp.client.stdio.stdio_client's `errlog` parameter defaults to `sys.stderr`, evaluated once
# at function-definition (import) time -- not per call. If that import happens lazily, later,
# inside a Celery worker task, it binds to Celery's LoggingProxy (which has no working
# fileno()) and every MCP subprocess launch fails. Importing it here, before Celery's worker
# bootstrap replaces sys.stdout/stderr, binds the default to the real stream instead.
import mcp.client.stdio  # noqa: F401,E402

from celery import Celery

from orchestrator.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "agent_orchestrator",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=["api.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
