"""Sandboxed Python execution: spins up a throwaway container (python:3.11-slim + pandas/numpy)
with no network access and hard memory/CPU/time limits, runs the code, and tears the container
down. Real isolation (not a subprocess/exec sandbox), reusing the Docker dependency this whole
system already has."""
from __future__ import annotations

from pathlib import Path

IMAGE = "agent-orchestrator-sandbox:latest"
DOCKERFILE_DIR = Path(__file__).resolve().parents[3] / "docker"
MEM_LIMIT = "256m"
CPU_QUOTA = 50_000  # 0.5 CPU (cpu_period defaults to 100_000)
DEFAULT_TIMEOUT_SECONDS = 15
MAX_OUTPUT_BYTES = 20_000


def execute_python(code: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Execute Python code (pandas/numpy available) in an isolated, network-disabled Docker
    container and return stdout/stderr."""
    import docker
    from docker.errors import DockerException, ImageNotFound

    timeout_seconds = min(timeout_seconds, 60)

    try:
        client = docker.from_env()
    except DockerException as exc:
        return f"Error: Docker is not available ({exc}). Is Docker Desktop running?"

    try:
        client.images.get(IMAGE)
    except ImageNotFound:
        # Self-bootstrapping: build the sandbox image locally on first use, then it's cached.
        client.images.build(path=str(DOCKERFILE_DIR), dockerfile="sandbox.Dockerfile", tag=IMAGE)

    container = None
    try:
        container = client.containers.run(
            IMAGE,
            ["python", "-c", code],
            network_disabled=True,
            mem_limit=MEM_LIMIT,
            cpu_period=100_000,
            cpu_quota=CPU_QUOTA,
            detach=True,
        )
        try:
            result = container.wait(timeout=timeout_seconds)
        except Exception:
            container.kill()
            return f"Error: execution exceeded the {timeout_seconds}s timeout and was killed."

        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
        exit_code = result.get("StatusCode", 0)
        if exit_code != 0:
            return f"Execution failed (exit {exit_code}):\n{logs}"
        return logs
    except Exception as exc:  # noqa: BLE001 - surfaced to the agent as a tool error, not raised
        return f"Error running sandboxed code: {exc}"
    finally:
        if container is not None:
            container.remove(force=True)
