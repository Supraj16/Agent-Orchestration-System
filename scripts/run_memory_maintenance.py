"""Runs one pass of memory maintenance (importance decay + expiration + consolidation of
near-duplicate memories). Manual for now; becomes a Celery-beat periodic task in milestone 6.

Usage:
    python scripts/run_memory_maintenance.py
"""
from __future__ import annotations

from orchestrator.memory.importance import run_memory_maintenance


def main() -> None:
    result = run_memory_maintenance()
    print(
        f"Decay: {result['decayed_updated']} updated, {result['expired']} expired. "
        f"Consolidation: {result['consolidation_merges']} merge(s)."
    )


if __name__ == "__main__":
    main()
