from __future__ import annotations

# Stage60 durable facade for UVR A/B mock execution and real-smoke planning.
# Real execution remains blocked.
# Old stage59_* files are now legacy shims. Internal references cleaned.

from .stage59_real_smoke_plan_service import (
    REAL_SMOKE_NOT_EXECUTED_REASON,
    REAL_SMOKE_PLAN_MODE,
    REAL_SMOKE_REQUIRES_FILE_CHECK_REASON,
    build_expected_real_smoke_artifacts,
    evaluate_real_smoke_plan,
)
from .stage59_uvr_mock_execute_service import mock_execute_uvr_ab
from .stage59_uvr_runner_contract import (
    INVALID_RUNNER_MODE_REASON,
    REAL_RUNNER_BLOCKED_REASON,
    STAGE59C1_REAL_EXECUTE_BLOCKED,
    MockUvrAbRunner,
    RealUvrAbRunnerAdapter,
    RunnerMode,
    UvrAbArtifactContract,
    UvrAbRunnerPlan,
    UvrAbRunnerRequest,
    build_runner_request,
    evaluate_runner_readiness,
    evaluate_runner_readiness_from_paths,
)


__all__ = [
    "INVALID_RUNNER_MODE_REASON",
    "MockUvrAbRunner",
    "REAL_RUNNER_BLOCKED_REASON",
    "REAL_SMOKE_NOT_EXECUTED_REASON",
    "REAL_SMOKE_PLAN_MODE",
    "REAL_SMOKE_REQUIRES_FILE_CHECK_REASON",
    "STAGE59C1_REAL_EXECUTE_BLOCKED",
    "RealUvrAbRunnerAdapter",
    "RunnerMode",
    "UvrAbArtifactContract",
    "UvrAbRunnerPlan",
    "UvrAbRunnerRequest",
    "build_expected_real_smoke_artifacts",
    "build_runner_request",
    "evaluate_real_smoke_plan",
    "evaluate_runner_readiness",
    "evaluate_runner_readiness_from_paths",
    "mock_execute_uvr_ab",
]

# Lazy import to break circular with thin shims
def __getattr__(name):
    if name in {
        "REAL_SMOKE_NOT_EXECUTED_REASON",
        "REAL_SMOKE_PLAN_MODE",
        "REAL_SMOKE_REQUIRES_FILE_CHECK_REASON",
        "build_expected_real_smoke_artifacts",
        "evaluate_real_smoke_plan",
    }:
        from .stage59_real_smoke_plan_service import (
            REAL_SMOKE_NOT_EXECUTED_REASON,
            REAL_SMOKE_PLAN_MODE,
            REAL_SMOKE_REQUIRES_FILE_CHECK_REASON,
            build_expected_real_smoke_artifacts,
            evaluate_real_smoke_plan,
        )
        return locals().get(name) or globals().get(name)
    if name in {
        "mock_execute_uvr_ab",
    }:
        from .stage59_uvr_mock_execute_service import mock_execute_uvr_ab
        return mock_execute_uvr_ab
    if name in {
        "INVALID_RUNNER_MODE_REASON",
        "REAL_RUNNER_BLOCKED_REASON",
        "STAGE59C1_REAL_EXECUTE_BLOCKED",
        "MockUvrAbRunner",
        "RealUvrAbRunnerAdapter",
        "RunnerMode",
        "UvrAbArtifactContract",
        "UvrAbRunnerPlan",
        "UvrAbRunnerRequest",
        "build_runner_request",
        "evaluate_runner_readiness",
        "evaluate_runner_readiness_from_paths",
    }:
        from .stage59_uvr_runner_contract import (
            INVALID_RUNNER_MODE_REASON,
            REAL_RUNNER_BLOCKED_REASON,
            STAGE59C1_REAL_EXECUTE_BLOCKED,
            MockUvrAbRunner,
            RealUvrAbRunnerAdapter,
            RunnerMode,
            UvrAbArtifactContract,
            UvrAbRunnerPlan,
            UvrAbRunnerRequest,
            build_runner_request,
            evaluate_runner_readiness,
            evaluate_runner_readiness_from_paths,
        )
        return locals().get(name) or globals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

