from __future__ import annotations

import json
import os

try:
    from ..repositories.artifact_repository import ArtifactRepository
    from ..repositories.job_repository import JobRepository
    from ..repositories.track_repository import TrackRepository
    from .asset_service import get_final_job_artifact, get_job_artifact
    from .audit_service import record_audit_event
    from .smoke_filter import explain_test_data_filter_reason, is_test_data_track_record
    from .stage_log_service import list_stage_logs
except ImportError:
    from repositories.artifact_repository import ArtifactRepository
    from repositories.job_repository import JobRepository
    from repositories.track_repository import TrackRepository
    from services.asset_service import get_final_job_artifact, get_job_artifact
    from services.audit_service import record_audit_event
    from services.smoke_filter import explain_test_data_filter_reason, is_test_data_track_record
    from services.stage_log_service import list_stage_logs


def _track_repo() -> TrackRepository:
    return TrackRepository()


def _job_repo() -> JobRepository:
    return JobRepository()


def _artifact_repo() -> ArtifactRepository:
    return ArtifactRepository()


TRACK_MUTABLE_FIELDS = {
    "title",
    "artist",
    "source_type",
    "status",
    "notes",
}

TRACK_COVER_PENDING_STATUS = "cover_pending"
TRACK_COVER_PROCESSING_STATUS = "cover_processing"
TRACK_COVER_READY_STATUS = "cover_ready"
TRACK_COVER_FAILED_STATUS = "cover_failed"
STUDIO_MASTER_ARTIFACT_TYPES = {"cover_master", "studio_effect_draft_master", "studio_effect_render_master"}
STUDIO_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}


def _parse_json(raw: str | None, fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def get_track(track_id: str) -> dict | None:
    row = _track_repo().get_with_batch(track_id)
    if not row:
        return None
    payload = dict(row)
    payload["metadata"] = _parse_json(payload.get("metadata_json"), {})
    return payload


def _resolve_track_artifact(job_id: str, preferred_artifact_id: str = "") -> dict | None:
    if preferred_artifact_id:
        artifact = get_job_artifact(job_id, preferred_artifact_id)
        if artifact:
            return artifact
    return get_final_job_artifact(job_id)


def _artifact_metadata(artifact: dict | None) -> dict:
    return _parse_json((artifact or {}).get("metadata_json"), {})


def _is_downloadable_audio_artifact(artifact: dict | None) -> bool:
    if not artifact:
        return False
    file_path = artifact.get("file_path") or ""
    if not file_path or not os.path.exists(file_path):
        return False
    file_ext = os.path.splitext(file_path)[1].lower()
    return file_ext in STUDIO_AUDIO_EXTENSIONS


def _studio_processing_mode(artifact: dict | None) -> str:
    artifact_type = (artifact or {}).get("artifact_type") or ""
    if artifact_type == "cover_master":
        return "original_cover"
    if artifact_type == "studio_effect_draft_master":
        return str(_artifact_metadata(artifact).get("processing_mode") or "copy_only_no_dsp")
    if artifact_type == "studio_effect_render_master":
        return str(_artifact_metadata(artifact).get("processing_mode") or "ffmpeg_dsp_v0")
    return ""


def _serialize_studio_version(
    artifact: dict,
    job: dict,
    *,
    track_id: str,
    batch_id: str = "",
    current_master_job_id: str = "",
    current_master_artifact_id: str = "",
) -> dict:
    artifact_id = artifact.get("artifact_id") or ""
    job_id = job.get("job_id") or artifact.get("job_id") or ""
    metadata = _artifact_metadata(artifact)
    file_path = artifact.get("file_path") or ""
    is_processing_draft = artifact.get("artifact_type") in {"studio_effect_draft_master", "studio_effect_render_master"}
    studio_url = f"/studio?track_id={track_id}&job_id={job_id}&artifact_id={artifact_id}"
    if batch_id:
        studio_url += f"&batch_id={batch_id}"
    return {
        "version_id": artifact_id,
        "job_id": job_id,
        "track_id": track_id,
        "artifact_id": artifact_id,
        "artifact_type": artifact.get("artifact_type") or "",
        "stage_name": artifact.get("stage_name") or "",
        "file_name": os.path.basename(file_path),
        "file_path": file_path,
        "file_size": artifact.get("file_size") or 0,
        "created_at": artifact.get("created_at") or "",
        "is_final": bool(artifact.get("is_final")),
        "is_current_master": bool(
            current_master_job_id
            and current_master_artifact_id
            and job_id == current_master_job_id
            and artifact_id == current_master_artifact_id
        ),
        "is_processing_draft": is_processing_draft,
        "processing_mode": _studio_processing_mode(artifact),
        "source_job_id": metadata.get("source_job_id") or "",
        "source_artifact_id": metadata.get("source_artifact_id") or "",
        "downloadable": _is_downloadable_audio_artifact(artifact),
        "download_url": f"/api/jobs/{job_id}/artifacts/{artifact_id}/download",
        "studio_url": studio_url,
        "warning": metadata.get("warning") or "",
    }


def _canonical_track_job_stage(job_row: dict, stage_logs: list[dict] | None = None) -> str:
    if not job_row:
        return ""

    status = job_row.get("status") or ""
    metadata = _parse_json(job_row.get("metadata_json"), {})
    if (
        (job_row.get("job_type") or "") == "train"
        and status in {"完成", "已完成", "completed"}
        and (metadata.get("recovered_from_checkpoint") or metadata.get("recovered_model_id"))
    ):
        return "train_register_model"
    if status == "pending":
        return "pending"
    if status == "\u5df2\u53d6\u6d88":
        return "cancelled"

    business_logs = [
        log for log in (stage_logs or [])
        if log.get("stage_name") not in {"job_dispatch", "job_control"}
    ]
    if business_logs:
        return business_logs[-1].get("stage_name") or ""

    current_stage = (job_row.get("current_stage") or "").strip()
    if current_stage and current_stage not in {"job_dispatch", "job_control"}:
        return current_stage

    job_type = job_row.get("job_type") or ""
    if status == "\u5df2\u5b8c\u6210":
        return "cover_mix" if job_type == "cover" else "train_register_model"
    if status == "\u5931\u8d25":
        return "failed"
    return status


def _latest_failed_message(stage_logs: list[dict]) -> str:
    for item in reversed(stage_logs):
        if item.get("status") in {"failed", "\u5931\u8d25"}:
            return item.get("message") or ""
    return ""


def _serialize_track_job(
    item: dict,
    *,
    track_id: str,
    batch_id: str = "",
    current_master_job_id: str = "",
    current_master_artifact_id: str = "",
    preferred_artifact_id: str = "",
) -> dict:
    job_id = item.get("job_id") or ""
    metadata = _parse_json(item.get("metadata_json"), {})
    stage_logs = list_stage_logs(job_id)
    current_stage = _canonical_track_job_stage(item, stage_logs)
    final_artifact = _resolve_track_artifact(job_id, preferred_artifact_id)
    artifact_id = final_artifact.get("artifact_id") if final_artifact else ""
    has_final_artifact = bool(
        final_artifact
        and final_artifact.get("file_path")
        and os.path.exists(final_artifact["file_path"])
    )
    artifact_type = final_artifact.get("artifact_type") if final_artifact else ""
    processing_mode = _studio_processing_mode(final_artifact)
    can_open_studio = bool(
        has_final_artifact
        and item.get("job_type") == "cover"
        and artifact_type in STUDIO_MASTER_ARTIFACT_TYPES
        and _is_downloadable_audio_artifact(final_artifact)
    )
    is_current_master = bool(
        current_master_job_id
        and job_id == current_master_job_id
        and (not current_master_artifact_id or artifact_id == current_master_artifact_id)
    )
    return {
        "job_id": job_id,
        "job_type": item.get("job_type") or "",
        "job_kind": item.get("job_kind") or "",
        "status": item.get("status") or "",
        "current_stage": current_stage,
        "voice_model_id": item.get("voice_model_id") or "",
        "voice_name": item.get("resolved_voice_name") or item.get("voice_name") or "",
        "voice_model_origin_kind": metadata.get("voice_model_origin_kind") or "",
        "voice_model_source_job_id": metadata.get("voice_model_source_job_id") or "",
        "voice_model_source_summary": metadata.get("voice_model_source_summary") or "",
        "voice_model_source_strategy_key": metadata.get("voice_model_source_strategy_key") or "",
        "voice_model_source_material_profile": metadata.get("voice_model_source_material_profile") or "",
        "output_root": item.get("output_root") or "",
        "created_at": item.get("created_at") or "",
        "updated_at": item.get("updated_at") or "",
        "error_log": item.get("error_log") or "",
        "error_summary": item.get("error_log") or _latest_failed_message(stage_logs),
        "latest_stage_message": stage_logs[-1].get("message") if stage_logs else "",
        "depends_on": _parse_json(item.get("depends_on_json"), []),
        "has_final_artifact": has_final_artifact,
        "final_artifact_id": artifact_id,
        "final_artifact_type": artifact_type,
        "final_artifact_path": final_artifact.get("file_path") if final_artifact else "",
        "final_artifact_processing_mode": processing_mode,
        "final_artifact_download_url": (
            f"/api/jobs/{job_id}/artifacts/{artifact_id}/download"
            if artifact_id
            else ""
        ),
        "track_id": track_id,
        "batch_id": batch_id,
        "track_title": item.get("track_title") or "",
        "batch_name": item.get("batch_name") or "",
        "can_open_studio": can_open_studio,
        "studio_url": (
            f"/studio?batch_id={batch_id}&track_id={track_id}&job_id={job_id}&artifact_id={artifact_id}"
            if can_open_studio and artifact_id
            else f"/studio?batch_id={batch_id}&track_id={track_id}&job_id={job_id}"
        ),
        "is_current_master": is_current_master,
        "is_current_master_job": bool(current_master_job_id and job_id == current_master_job_id),
        "current_master_artifact_id": current_master_artifact_id if current_master_job_id == job_id else "",
        "current_master_artifact_type": artifact_type if is_current_master else "",
        "current_master_processing_mode": processing_mode if is_current_master else "",
    }


def _set_track_status(track_id: str, status: str) -> None:
    _track_repo().update_status(track_id, status)


def _track_idle_status(track: dict | None) -> str:
    if not track:
        return "imported"
    if track.get("current_timeline_version_id"):
        return "lyrics_ready"
    return "imported"


def mark_track_cover_job_created(
    track_id: str,
    job_id: str,
    *,
    model_id: str = "",
    voice_name: str = "",
    depends_on: list[str] | None = None,
    metadata: dict | None = None,
) -> None:
    track = get_track(track_id)
    if not track:
        return
    _set_track_status(track_id, TRACK_COVER_PENDING_STATUS)
    record_audit_event(
        "track",
        track_id,
        "track_cover_job_create",
        {
            "job_id": job_id,
            "model_id": model_id,
            "voice_name": voice_name,
            "depends_on": depends_on or [],
            "track_title": track.get("title") or track_id,
            "batch_id": track.get("batch_id") or "",
            "metadata": metadata or {},
        },
    )


def mark_track_cover_job_pending(track_id: str) -> None:
    if not get_track(track_id):
        return
    _set_track_status(track_id, TRACK_COVER_PENDING_STATUS)


def mark_track_cover_job_processing(
    track_id: str,
    job_id: str,
    *,
    model_id: str = "",
    voice_name: str = "",
) -> None:
    if not get_track(track_id):
        return
    _set_track_status(track_id, TRACK_COVER_PROCESSING_STATUS)


def mark_track_cover_job_complete(
    track_id: str,
    job_id: str,
    *,
    model_id: str = "",
    voice_name: str = "",
) -> None:
    track = get_track(track_id)
    if not track:
        return

    artifact = get_final_job_artifact(job_id)
    artifact_id = artifact.get("artifact_id") if artifact else ""
    can_open_studio = bool(
        artifact
        and artifact.get("artifact_type") == "cover_master"
        and artifact.get("file_path")
        and os.path.exists(artifact["file_path"])
    )
    _set_track_status(track_id, TRACK_COVER_READY_STATUS)
    record_audit_event(
        "track",
        track_id,
        "track_cover_job_complete",
        {
            "job_id": job_id,
            "model_id": model_id,
            "voice_name": voice_name,
            "track_title": track.get("title") or track_id,
            "artifact_id": artifact_id,
            "artifact_type": artifact.get("artifact_type") if artifact else "",
            "download_url": f"/api/jobs/{job_id}/artifacts/{artifact_id}/download" if artifact_id else "",
            "studio_url": (
                f"/studio?batch_id={track.get('batch_id') or ''}&track_id={track_id}&job_id={job_id}&artifact_id={artifact_id}"
                if can_open_studio and artifact_id
                else f"/studio?batch_id={track.get('batch_id') or ''}&track_id={track_id}&job_id={job_id}"
            ),
        },
    )


def mark_track_cover_job_failed(
    track_id: str,
    job_id: str,
    *,
    error: str = "",
    model_id: str = "",
    voice_name: str = "",
) -> None:
    track = get_track(track_id)
    if not track:
        return
    _set_track_status(track_id, TRACK_COVER_FAILED_STATUS)
    record_audit_event(
        "track",
        track_id,
        "track_cover_job_fail",
        {
            "job_id": job_id,
            "model_id": model_id,
            "voice_name": voice_name,
            "track_title": track.get("title") or track_id,
            "error": error,
        },
    )


def reset_track_cover_job_state(track_id: str) -> None:
    track = get_track(track_id)
    if not track:
        return
    _set_track_status(track_id, _track_idle_status(track))


def get_track_job_entry(track_id: str, job_id: str, preferred_artifact_id: str = "") -> dict | None:
    track = get_track(track_id)
    if not track:
        return None
    item = _job_repo().get_for_track_with_voice_name(track_id, job_id)
    if not item:
        return None
    return _serialize_track_job(
        item,
        track_id=track_id,
        batch_id=track.get("batch_id") or "",
        current_master_job_id=track.get("current_master_job_id") or "",
        current_master_artifact_id=track.get("current_master_artifact_id") or "",
        preferred_artifact_id=preferred_artifact_id,
    )


def get_track_current_master(track_id: str) -> dict | None:
    track = get_track(track_id)
    if not track:
        return None
    master_job_id = track.get("current_master_job_id") or ""
    if not master_job_id:
        return None
    return get_track_job_entry(
        track_id,
        master_job_id,
        preferred_artifact_id=track.get("current_master_artifact_id") or "",
    )


def list_track_studio_versions(track_id: str, limit: int = 50, offset: int = 0) -> dict | None:
    track = get_track(track_id)
    if not track:
        return None

    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    current_master_job_id = track.get("current_master_job_id") or ""
    current_master_artifact_id = track.get("current_master_artifact_id") or ""

    rows = _artifact_repo().list_studio_versions_for_track(track_id, limit=limit, offset=offset)

    items = []
    for row in rows:
        payload = dict(row)
        artifact = {key: payload.get(key) for key in payload.keys() if not key.startswith("version_")}
        job = {
            "job_id": payload.get("version_job_id") or payload.get("job_id") or "",
            "job_type": payload.get("job_type") or "",
            "job_kind": payload.get("job_kind") or "",
            "status": payload.get("job_status") or "",
            "track_id": payload.get("job_track_id") or "",
        }
        if not _is_downloadable_audio_artifact(artifact):
            continue
        items.append(
            _serialize_studio_version(
                artifact,
                job,
                track_id=track_id,
                batch_id=track.get("batch_id") or "",
                current_master_job_id=current_master_job_id,
                current_master_artifact_id=current_master_artifact_id,
            )
        )

    return {
        "track_id": track_id,
        "current_master_job_id": current_master_job_id,
        "current_master_artifact_id": current_master_artifact_id,
        "current_master": get_track_current_master(track_id),
        "items": items,
        "limit": limit,
        "offset": offset,
    }


def set_track_current_master(track_id: str, job_id: str, artifact_id: str = "") -> dict | None:
    track = get_track(track_id)
    if not track:
        return None

    _track_repo().set_current_master(track_id, job_id, artifact_id or "")

    record_audit_event(
        "track",
        track_id,
        "track_master_set",
        {
            "job_id": job_id,
            "artifact_id": artifact_id or "",
            "track_title": track.get("title") or track_id,
            "batch_id": track.get("batch_id") or "",
        },
    )
    return get_track_current_master(track_id)


def list_track_jobs(track_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    track = get_track(track_id)
    batch_id = track.get("batch_id") if track else ""
    current_master_job_id = track.get("current_master_job_id") if track else ""
    current_master_artifact_id = track.get("current_master_artifact_id") if track else ""
    items = _job_repo().list_for_track_with_voice_name(track_id, limit=limit, offset=offset)

    payload: list[dict] = []
    for item in items:
        item_job_id = item.get("job_id") or ""
        payload.append(
            _serialize_track_job(
                item,
                track_id=track_id,
                batch_id=batch_id or "",
                current_master_job_id=current_master_job_id or "",
                current_master_artifact_id=current_master_artifact_id or "",
                preferred_artifact_id=current_master_artifact_id if item_job_id == current_master_job_id else "",
            )
        )
    return payload


def list_tracks(
    batch_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    *,
    include_smoke: bool = False,
    include_test_data: bool = False,
) -> list[dict]:
    repo = _track_repo()
    items = repo.list_all(batch_id=batch_id)
    batch_rows = repo.release_batches_by_id()
    include_filtered = bool(include_smoke or include_test_data)
    if not include_filtered:
        items = [
            item for item in items
            if not is_test_data_track_record(item, batch_rows.get(item.get("batch_id") or ""))
        ]
    else:
        for item in items:
            reason = explain_test_data_filter_reason(item, kind="track")
            if not reason:
                reason = explain_test_data_filter_reason(batch_rows.get(item.get("batch_id") or ""), kind="batch")
            if reason:
                item["filter_reason"] = reason
    return items[offset: offset + limit]


def hidden_test_track_count(batch_id: str | None = None) -> int:
    repo = _track_repo()
    rows = repo.list_all(batch_id=batch_id)
    batch_rows = repo.release_batches_by_id()
    return sum(
        1 for row in rows
        if is_test_data_track_record(row, batch_rows.get(row.get("batch_id") or ""))
    )


def update_track(track_id: str, payload: dict) -> dict | None:
    updates = {key: value for key, value in payload.items() if key in TRACK_MUTABLE_FIELDS}
    if not updates:
        return get_track(track_id)

    _track_repo().update_fields(track_id, updates)
    return get_track(track_id)


def set_track_current_lyrics(track_id: str, lyric_document_id: str | None = None, timeline_id: str | None = None) -> None:
    _track_repo().set_current_lyrics(track_id, lyric_document_id, timeline_id)
