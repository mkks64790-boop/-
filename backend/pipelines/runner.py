from __future__ import annotations

try:
    from .registry import resolve_pipeline_executor
except ImportError:
    from pipelines.registry import resolve_pipeline_executor


def run_registered_pipeline(job) -> dict:
    executor = resolve_pipeline_executor(job)
    return executor(job)
