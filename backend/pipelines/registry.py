from __future__ import annotations

from typing import Callable

try:
    from ..strategies.strategy_registry import get_strategy
except ImportError:
    from strategies.strategy_registry import get_strategy


PipelineExecutor = Callable[[object], dict]

_PIPELINE_REGISTRY: dict[str, PipelineExecutor] = {}


def register_pipeline_step(step_key: str, executor: PipelineExecutor) -> None:
    _PIPELINE_REGISTRY[step_key] = executor


def has_pipeline_step(step_key: str) -> bool:
    return step_key in _PIPELINE_REGISTRY


def resolve_pipeline_executor(job) -> PipelineExecutor:
    candidates = [
        getattr(job, "strategy_key", "") or "",
        getattr(job, "job_kind", "") or "",
        getattr(job, "job_type", "") or "",
    ]
    for key in candidates:
        if key in _PIPELINE_REGISTRY:
            return _PIPELINE_REGISTRY[key]

    strategy_key = getattr(job, "strategy_key", "") or ""
    if strategy_key:
        strategy = get_strategy(strategy_key)
        return strategy.execute

    raise KeyError(f"no_pipeline_executor_for_job: {getattr(job, 'job_id', '')}")


def bootstrap_default_pipeline_steps() -> None:
    if _PIPELINE_REGISTRY:
        return

    def _strategy_executor(strategy_key: str) -> PipelineExecutor:
        strategy = get_strategy(strategy_key)
        return strategy.execute

    register_pipeline_step("cover_strategy", _strategy_executor("cover_strategy"))
    register_pipeline_step("single_long_preprocess", _strategy_executor("single_long_preprocess"))
    register_pipeline_step("multi_clean_direct", _strategy_executor("multi_clean_direct"))
    register_pipeline_step("cover", _strategy_executor("cover_strategy"))
    register_pipeline_step("train", _strategy_executor("single_long_preprocess"))


bootstrap_default_pipeline_steps()
