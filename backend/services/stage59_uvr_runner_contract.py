"""
Stage59C-1 — UVR A/B runner contract (metadata-only; no real separation).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from backend.services.short_chain_manifest_service import (
    ManifestPathSafetyError,
    build_short_chain_whitelist,
    load_manifest,
    resolve_safe_manifest_path,
)
from backend.services.short_chain_uvr_service import (
    UVR_STAGE,
    _clamp_clip_seconds,
    _entries_by_id,
    _entry_has_uvr_stage,
    _looks_like_path,
)


class RunnerMode(str, Enum):
    MOCK = "mock"
    REAL = "real"


REAL_RUNNER_BLOCKED_REASON = "real_uvr_runner_requires_manual_approval"
STAGE59C1_REAL_EXECUTE_BLOCKED = "real_execute_blocked_stage59c1"


@dataclass
class UvrAbArtifactContract:
    artifact_type: str
    lifecycle_state: str = "transient"
    relative_path_pattern: str = ""
    mime_type: str = "audio/wav"
    metadata_only: bool = True


@dataclass
class UvrAbRunnerPlan:
    entry_id: str
    source_path: str
    clip_seconds: int
    stages: list[str] = field(default_factory=lambda: [UVR_STAGE])
    artifact_contracts: list[UvrAbArtifactContract] = field(default_factory=list)


@dataclass
class UvrAbRunnerRequest:
    entry_id: str
    manifest_path: Path
    clip_seconds: int = 45
    runner_mode: RunnerMode = RunnerMode.MOCK
    check_file_exists: bool = True
    project_root: Path | None = None


def _default_artifact_contracts(entry_id: str) -> list[UvrAbArtifactContract]:
    return [
        UvrAbArtifactContract(
            artifact_type="uvr_vocal",
            relative_path_pattern=f"shared_data/separation_eval/stage59/{entry_id}/uvr_vocal.wav",
        ),
        UvrAbArtifactContract(
            artifact_type="uvr_instrumental",
            relative_path_pattern=f"shared_data/separation_eval/stage59/{entry_id}/uvr_instrumental.wav",
        ),
    ]


def _blocked_payload(reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "blocked": True,
        "blocked_reason": reason,
        "real_execute_allowed": False,
    }
    payload.update(extra)
    return payload


class MockUvrAbRunner:
    """Metadata-only readiness runner; never writes audio or starts UVR engines."""

    def run(
        self,
        request: UvrAbRunnerRequest,
        *,
        data: dict[str, Any],
        entry: dict[str, Any],
        whitelist: frozenset[str],
    ) -> dict[str, Any]:
        plan = UvrAbRunnerPlan(
            entry_id=request.entry_id,
            source_path=str(entry.get("source_path") or ""),
            clip_seconds=request.clip_seconds,
            artifact_contracts=_default_artifact_contracts(request.entry_id),
        )
        return {
            "ok": True,
            "blocked": False,
            "runner_mode": RunnerMode.MOCK.value,
            "real_execute_allowed": False,
            "requires_manual_approval": False,
            "plan": {
                **asdict(plan),
                "artifact_contracts": [asdict(item) for item in plan.artifact_contracts],
            },
            "artifact_contracts": [asdict(item) for item in plan.artifact_contracts],
            "safety": {
                "uvr_subprocess": False,
                "rvc_inference": False,
                "gpu_required": False,
                "audio_files_written": False,
            },
        }


class RealUvrAbRunnerAdapter:
    """Placeholder for future real UVR — always blocked in Stage59C-1."""

    def run(self, request: UvrAbRunnerRequest, **_: Any) -> dict[str, Any]:
        return _blocked_payload(
            REAL_RUNNER_BLOCKED_REASON,
            runner_mode=RunnerMode.REAL.value,
            requires_manual_approval=True,
            requires_extra_tooling=True,
        )


def build_runner_request(
    entry_id: str,
    manifest_path: Path | str | None,
    *,
    project_root: Path | None = None,
    clip_seconds: int = 45,
    runner_mode: RunnerMode | str = RunnerMode.MOCK,
    check_file_exists: bool = True,
) -> UvrAbRunnerRequest:
    mode = RunnerMode(runner_mode) if isinstance(runner_mode, str) else runner_mode
    safe_manifest = resolve_safe_manifest_path(manifest_path, project_root=project_root)
    return UvrAbRunnerRequest(
        entry_id=entry_id.strip(),
        manifest_path=safe_manifest,
        clip_seconds=_clamp_clip_seconds(clip_seconds),
        runner_mode=mode,
        check_file_exists=check_file_exists,
        project_root=project_root,
    )


def evaluate_runner_readiness(request: UvrAbRunnerRequest) -> dict[str, Any]:
    """Validate whitelist + chain and return mock metadata plan or real-runner block."""
    if not request.entry_id:
        return _blocked_payload("entry_id_required")
    if _looks_like_path(request.entry_id):
        return _blocked_payload("entry_id_must_not_be_path", entry_id=request.entry_id)

    if request.runner_mode == RunnerMode.REAL:
        return RealUvrAbRunnerAdapter().run(request)

    if not request.manifest_path.is_file():
        return _blocked_payload(
            "manifest_missing",
            manifest_path=str(request.manifest_path),
        )

    data = load_manifest(request.manifest_path)
    whitelist = build_short_chain_whitelist(
        data,
        project_root=request.project_root,
        check_file_exists=request.check_file_exists,
    )
    by_id = _entries_by_id(data)
    entry = by_id.get(request.entry_id)
    if entry is None:
        return _blocked_payload("entry_id_not_in_manifest", entry_id=request.entry_id)
    if request.entry_id not in whitelist:
        return _blocked_payload("entry_id_not_whitelisted", entry_id=request.entry_id)
    if not _entry_has_uvr_stage(entry):
        return _blocked_payload("entry_missing_uvr_ab_stage", entry_id=request.entry_id)

    return MockUvrAbRunner().run(
        request,
        data=data,
        entry=entry,
        whitelist=whitelist,
    )


def evaluate_runner_readiness_from_paths(
    entry_id: str,
    manifest_path: Path | str | None,
    *,
    project_root: Path | None = None,
    clip_seconds: int = 45,
    runner_mode: RunnerMode | str = RunnerMode.MOCK,
    check_file_exists: bool = True,
) -> dict[str, Any]:
    try:
        request = build_runner_request(
            entry_id,
            manifest_path,
            project_root=project_root,
            clip_seconds=clip_seconds,
            runner_mode=runner_mode,
            check_file_exists=check_file_exists,
        )
    except ManifestPathSafetyError as exc:
        return _blocked_payload(exc.reason)
    return evaluate_runner_readiness(request)