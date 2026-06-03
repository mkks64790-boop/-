import json
import math
import os
import shutil
import sys
import uuid
import wave
from array import array
from datetime import datetime, timezone
from urllib.parse import urlencode

try:
    from ..db import PROJECT_ROOT as _DEFAULT_PROJECT_ROOT, get_connection
    from .dataset_service import ensure_job_dirs
    from .lifecycle_service import (
        enrich_job_artifact,
        lifecycle_blocks_download,
        resolve_register_audio_asset_lifecycle,
        resolve_register_job_artifact_lifecycle,
    )
except ImportError:
    from db import PROJECT_ROOT as _DEFAULT_PROJECT_ROOT, get_connection
    from services.dataset_service import ensure_job_dirs
    from services.lifecycle_service import (
        enrich_job_artifact,
        lifecycle_blocks_download,
        resolve_register_audio_asset_lifecycle,
        resolve_register_job_artifact_lifecycle,
    )


def resolve_project_file_path(path: str, project_root: str | None = None) -> str:
    """Resolve a stored path to an absolute file under project_root, or '' if outside sandbox."""
    raw = (path or "").strip()
    if not raw:
        return ""
    root = os.path.abspath(project_root or _DEFAULT_PROJECT_ROOT)
    candidate = raw if os.path.isabs(raw) else os.path.join(root, raw)
    resolved = os.path.abspath(candidate)
    if not (resolved == root or resolved.startswith(root + os.sep)):
        return ""
    return resolved


LISTENING_REVIEW_SMOKE_NOTE = "stage49 browser smoke only - not a human quality verdict"
LISTENING_REVIEW_VERDICTS = {
    "unreviewed",
    "needs_work",
    "usable",
    "release_candidate",
    "rejected",
}
LISTENING_REVIEW_ROUTE_BY_VERDICT = {
    "unreviewed": "needs_human_review",
    "needs_work": "route_to_rework",
    "usable": "route_to_candidate_pool",
    "release_candidate": "route_to_release_candidate",
    "rejected": "route_to_archive_or_rerun",
}
LISTENING_REVIEW_LABEL_BY_VERDICT = {
    "unreviewed": "未验收",
    "needs_work": "需返工",
    "usable": "可用",
    "release_candidate": "发布候选",
    "rejected": "已拒绝",
}
LISTENING_REVIEW_PRIORITY_BY_VERDICT = {
    "unreviewed": 30,
    "needs_work": 70,
    "usable": 50,
    "release_candidate": 90,
    "rejected": 10,
}
ARTIFACT_QUALITY_VERDICTS = {
    "reviewable",
    "needs_manual_quality_check",
    "blocked_auto",
}
AUDIO_REVIEW_TINY_FILE_BYTES = 4096
AUDIO_REVIEW_MIN_MANUAL_SEC = 10.0
AUDIO_REVIEW_MIN_REVIEWABLE_SEC = 30.0
AUDIO_REVIEW_SCAN_LIMIT_SEC = 60.0
AUDIO_REVIEW_NEAR_SILENT_RMS_DBFS = -55.0
AUDIO_REVIEW_NEAR_SILENT_PEAK_DBFS = -45.0
AUDIO_REVIEW_LOW_LEVEL_RMS_DBFS = -38.0
_AUDIO_QUALITY_CACHE: dict[tuple[str, int, int], dict] = {}


def register_audio_asset(
    job_id: str,
    asset_role: str,
    file_path: str,
    dataset_id: str = "",
    file_name: str | None = None,
    file_ext: str | None = None,
    file_size: int | None = None,
    duration_sec: float = 0.0,
    metadata: dict | None = None,
) -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT asset_id
            FROM audio_assets
            WHERE job_id = ? AND COALESCE(dataset_id, '') = COALESCE(?, '') AND asset_role = ? AND file_path = ?
            LIMIT 1
            """,
            (job_id, dataset_id, asset_role, file_path),
        ).fetchone()
        if row:
            return row["asset_id"]
    finally:
        conn.close()

    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    file_name = file_name or os.path.basename(file_path)
    file_ext = file_ext or os.path.splitext(file_name)[1].lower()
    file_size = file_size if file_size is not None else (os.path.getsize(file_path) if os.path.exists(file_path) else 0)

    conn = get_connection()
    try:
        job_row = conn.execute(
            "SELECT job_id, job_type, status, metadata_json, voice_name, strategy_key FROM jobs WHERE job_id = ? LIMIT 1",
            (job_id,),
        ).fetchone()
        job_dict = dict(job_row) if job_row else None
        lifecycle_state = resolve_register_audio_asset_lifecycle(asset_role=asset_role, job_row=job_dict)
        conn.execute(
            """
            INSERT INTO audio_assets (
                asset_id, dataset_id, job_id, asset_role, file_name, file_ext,
                file_path, file_size, duration_sec, lifecycle_state, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                dataset_id,
                job_id,
                asset_role,
                file_name,
                file_ext,
                file_path,
                file_size,
                duration_sec,
                lifecycle_state,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
        return asset_id
    finally:
        conn.close()


def register_job_artifact(
    job_id: str,
    stage_name: str,
    artifact_type: str,
    source_path: str,
    is_final: bool = False,
    mirror_into_job_dir: bool = True,
    metadata: dict | None = None,
) -> str | None:
    if not source_path or not os.path.exists(source_path):
        return None

    artifact_path = source_path
    if mirror_into_job_dir:
        dirs = ensure_job_dirs(job_id)
        stage_dir = os.path.join(dirs["artifacts"], stage_name)
        os.makedirs(stage_dir, exist_ok=True)
        artifact_path = os.path.join(stage_dir, os.path.basename(source_path))
        if os.path.abspath(source_path) != os.path.abspath(artifact_path):
            shutil.copy2(source_path, artifact_path)

    file_size = os.path.getsize(artifact_path)
    metadata_payload = {"source_path": source_path}
    if metadata:
        metadata_payload.update(metadata)

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT artifact_id, is_final, metadata_json
            FROM job_artifacts
            WHERE job_id = ? AND stage_name = ? AND artifact_type = ? AND file_path = ?
            LIMIT 1
            """,
            (job_id, stage_name, artifact_type, artifact_path),
        ).fetchone()
        if row:
            existing_metadata = _parse_metadata(row["metadata_json"])
            existing_metadata.update(metadata_payload)
            conn.execute(
                """
                UPDATE job_artifacts
                SET file_size = ?,
                    is_final = CASE WHEN is_final = 1 OR ? = 1 THEN 1 ELSE 0 END,
                    metadata_json = ?
                WHERE artifact_id = ?
                """,
                (
                    file_size,
                    1 if is_final else 0,
                    json.dumps(existing_metadata, ensure_ascii=False),
                    row["artifact_id"],
                ),
            )
            conn.commit()
            return row["artifact_id"]
    finally:
        conn.close()

    artifact_id = f"art_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    try:
        job_row = conn.execute(
            "SELECT job_id, job_type, status, metadata_json, voice_name, strategy_key FROM jobs WHERE job_id = ? LIMIT 1",
            (job_id,),
        ).fetchone()
        job_dict = dict(job_row) if job_row else None
        lifecycle_state = resolve_register_job_artifact_lifecycle(
            artifact_type=artifact_type,
            is_final=is_final,
            job_row=job_dict,
        )
        conn.execute(
            """
            INSERT INTO job_artifacts (
                artifact_id, job_id, stage_name, artifact_type,
                file_path, file_size, is_final, lifecycle_state, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                job_id,
                stage_name,
                artifact_type,
                artifact_path,
                file_size,
                1 if is_final else 0,
                lifecycle_state,
                json.dumps(metadata_payload, ensure_ascii=False),
            ),
        )
        conn.commit()
        return artifact_id
    finally:
        conn.close()


def register_cover_stage_outputs(job_id: str, stage_name: str) -> list[str]:
    legacy_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "shared_data", "outputs", job_id)
    stage_map = {
        "cover_split": [("cover_vocal", "vocal.wav"), ("cover_instrumental", "instrumental.wav")],
        "cover_pitch": [("cover_fixed", "vocal_fixed.wav")],
        "cover_voice": [("cover_transformed", "vocal_transformed.wav")],
        "cover_mix": [("cover_master", "final_master.wav")],
    }
    artifact_ids: list[str] = []
    for artifact_type, file_name in stage_map.get(stage_name, []):
        artifact_id = register_job_artifact(
            job_id=job_id,
            stage_name=stage_name,
            artifact_type=artifact_type,
            source_path=os.path.join(legacy_dir, file_name),
            is_final=(file_name == "final_master.wav"),
        )
        if artifact_id:
            artifact_ids.append(artifact_id)
    return artifact_ids


def _job_row_for_lifecycle(conn, job_id: str) -> dict | None:
    row = conn.execute(
        "SELECT job_id, job_type, status, metadata_json, voice_name, strategy_key FROM jobs WHERE job_id = ? LIMIT 1",
        (job_id,),
    ).fetchone()
    return dict(row) if row else None


def list_job_artifacts(job_id: str) -> list[dict]:
    conn = get_connection()
    try:
        job_row = _job_row_for_lifecycle(conn, job_id)
        rows = conn.execute(
            "SELECT * FROM job_artifacts WHERE job_id = ? ORDER BY datetime(created_at), rowid",
            (job_id,),
        ).fetchall()
        return [enrich_job_artifact(dict(row), job_row=job_row) for row in rows]
    finally:
        conn.close()


def get_job_artifact(job_id: str, artifact_id: str) -> dict | None:
    conn = get_connection()
    try:
        job_row = _job_row_for_lifecycle(conn, job_id)
        row = conn.execute(
            """
            SELECT *
            FROM job_artifacts
            WHERE job_id = ? AND artifact_id = ?
            LIMIT 1
            """,
            (job_id, artifact_id),
        ).fetchone()
        return enrich_job_artifact(dict(row), job_row=job_row) if row else None
    finally:
        conn.close()


def artifact_allows_download(artifact: dict | None) -> bool:
    if not artifact:
        return False
    return not lifecycle_blocks_download(str(artifact.get("lifecycle_state") or ""))


def _parse_metadata(raw: dict | str | None) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _score_or_none(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_listening_review(metadata: dict | str | None) -> dict:
    parsed = _parse_metadata(metadata)
    review = parsed.get("listening_review")
    if isinstance(review, dict):
        return review
    if any(
        key in parsed
        for key in (
            "verdict",
            "overall_score",
            "vocal_score",
            "noise_score",
            "mix_score",
            "notes",
            "reviewed_at",
        )
    ):
        return parsed
    return {}


def _copy_quality_summary(summary: dict) -> dict:
    copied = dict(summary)
    copied["quality_flags"] = list(summary.get("quality_flags") or [])
    copied["flags"] = list(summary.get("flags") or copied["quality_flags"])
    return copied


def _safe_round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _dbfs(amplitude: float, full_scale: float) -> float | None:
    if amplitude <= 0 or full_scale <= 0:
        return None
    return 20.0 * math.log10(amplitude / full_scale)


def _iter_pcm_samples(data: bytes, sample_width: int):
    if sample_width == 1:
        for value in data:
            yield value - 128
        return

    if sample_width == 2:
        usable = len(data) - (len(data) % 2)
        samples = array("h")
        samples.frombytes(data[:usable])
        if sys.byteorder != "little":
            samples.byteswap()
        yield from samples
        return

    if sample_width == 4:
        usable = len(data) - (len(data) % 4)
        samples = array("i")
        samples.frombytes(data[:usable])
        if sys.byteorder != "little":
            samples.byteswap()
        yield from samples
        return

    if sample_width == 3:
        usable = len(data) - (len(data) % 3)
        for index in range(0, usable, 3):
            yield int.from_bytes(data[index : index + 3], "little", signed=True)


def _scan_wave_quality(file_path: str) -> dict:
    with wave.open(file_path, "rb") as handle:
        frame_rate = int(handle.getframerate() or 0)
        frame_count = int(handle.getnframes() or 0)
        channels = int(handle.getnchannels() or 0)
        sample_width = int(handle.getsampwidth() or 0)
        duration_sec = (frame_count / frame_rate) if frame_rate > 0 else 0.0

        scan_frames = frame_count
        if frame_rate > 0:
            scan_frames = min(frame_count, int(frame_rate * AUDIO_REVIEW_SCAN_LIMIT_SEC))

        full_scale = float((1 << (sample_width * 8 - 1)) - 1) if sample_width > 0 else 0.0
        total_square = 0.0
        sample_count = 0
        peak = 0
        remaining = scan_frames
        chunk_frames = max(1024, min(frame_rate or 44100, 44100))

        while remaining > 0:
            chunk = handle.readframes(min(chunk_frames, remaining))
            if not chunk:
                break
            remaining -= min(chunk_frames, remaining)
            for sample in _iter_pcm_samples(chunk, sample_width):
                absolute = abs(int(sample))
                peak = max(peak, absolute)
                total_square += float(sample) * float(sample)
                sample_count += 1

        rms = math.sqrt(total_square / sample_count) if sample_count else 0.0
        return {
            "duration_sec": duration_sec,
            "sample_rate": frame_rate,
            "channels": channels,
            "sample_width": sample_width,
            "scan_duration_sec": min(duration_sec, AUDIO_REVIEW_SCAN_LIMIT_SEC) if duration_sec else 0.0,
            "rms_dbfs": _dbfs(rms, full_scale),
            "peak_dbfs": _dbfs(float(peak), full_scale),
        }


def summarize_artifact_audio_quality(artifact: dict) -> dict:
    file_path = str(artifact.get("file_path") or "")
    file_size = int(artifact.get("file_size") or 0)
    flags: list[str] = []

    if not file_path or not os.path.exists(file_path):
        flags.append("missing_file")
        return {
            "schema": "stage51_artifact_quality_v1",
            "quality_verdict": "blocked_auto",
            "verdict": "blocked_auto",
            "quality_flags": flags,
            "flags": flags,
            "quality_reason": "not ready for listening review: missing_file",
            "reason": "not ready for listening review: missing_file",
            "duration_sec": None,
            "file_size_bytes": file_size,
            "rms_dbfs": None,
            "peak_dbfs": None,
            "sample_rate": None,
            "channels": None,
            "sample_width": None,
            "scan_duration_sec": None,
        }

    stat = os.stat(file_path)
    cache_key = (os.path.abspath(file_path), int(stat.st_size), int(stat.st_mtime))
    cached = _AUDIO_QUALITY_CACHE.get(cache_key)
    if cached:
        return _copy_quality_summary(cached)

    file_size = int(stat.st_size)
    if file_size < AUDIO_REVIEW_TINY_FILE_BYTES:
        flags.append("tiny_file")

    wave_summary: dict = {}
    try:
        wave_summary = _scan_wave_quality(file_path)
    except (wave.Error, EOFError, OSError):
        flags.append("duration_unknown")

    duration_sec = wave_summary.get("duration_sec")
    rms_dbfs = wave_summary.get("rms_dbfs")
    peak_dbfs = wave_summary.get("peak_dbfs")

    if duration_sec is None or duration_sec <= 0:
        if "duration_unknown" not in flags:
            flags.append("duration_unknown")
    elif duration_sec < AUDIO_REVIEW_MIN_MANUAL_SEC:
        flags.append("too_short_under_10s")
        if duration_sec < 3.5:
            flags.append("short_smoke")

    if wave_summary and rms_dbfs is None and peak_dbfs is None and duration_sec and duration_sec > 0:
        flags.append("near_silent")
    elif rms_dbfs is not None and peak_dbfs is not None:
        if rms_dbfs <= AUDIO_REVIEW_NEAR_SILENT_RMS_DBFS and peak_dbfs <= AUDIO_REVIEW_NEAR_SILENT_PEAK_DBFS:
            flags.append("near_silent")

    blocked_flags = {
        "missing_file",
        "tiny_file",
        "duration_unknown",
        "too_short_under_10s",
        "near_silent",
    }
    if any(flag in blocked_flags for flag in flags):
        quality_verdict = "blocked_auto"
    elif duration_sec is not None and duration_sec < AUDIO_REVIEW_MIN_REVIEWABLE_SEC:
        flags.append("short_under_30s")
        quality_verdict = "needs_manual_quality_check"
    elif rms_dbfs is not None and rms_dbfs <= AUDIO_REVIEW_LOW_LEVEL_RMS_DBFS:
        flags.append("low_level")
        quality_verdict = "needs_manual_quality_check"
    else:
        quality_verdict = "reviewable"

    if quality_verdict == "reviewable":
        reason = "ready for human listening review"
    elif quality_verdict == "needs_manual_quality_check":
        reason = f"manual quality check required: {', '.join(flags) or 'borderline_audio'}"
    else:
        reason = f"not ready for listening review: {', '.join(flags)}"

    summary = {
        "schema": "stage51_artifact_quality_v1",
        "quality_verdict": quality_verdict,
        "verdict": quality_verdict,
        "quality_flags": flags,
        "flags": flags,
        "quality_reason": reason,
        "reason": reason,
        "duration_sec": _safe_round(duration_sec),
        "file_size_bytes": file_size,
        "rms_dbfs": _safe_round(rms_dbfs),
        "peak_dbfs": _safe_round(peak_dbfs),
        "sample_rate": wave_summary.get("sample_rate"),
        "channels": wave_summary.get("channels"),
        "sample_width": wave_summary.get("sample_width"),
        "scan_duration_sec": _safe_round(wave_summary.get("scan_duration_sec")),
    }
    if len(_AUDIO_QUALITY_CACHE) > 512:
        _AUDIO_QUALITY_CACHE.clear()
    _AUDIO_QUALITY_CACHE[cache_key] = _copy_quality_summary(summary)
    return summary


def _is_audio_review_artifact(artifact: dict) -> bool:
    artifact_type = str(artifact.get("artifact_type") or "")
    if artifact_type in {"cover_master", "studio_effect_draft_master", "studio_effect_render_master"}:
        return True
    ext = os.path.splitext(str(artifact.get("file_path") or ""))[1].lower()
    return ext in {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}


def add_artifact_quality_summary(artifact: dict) -> dict:
    item = dict(artifact)
    if not _is_audio_review_artifact(item):
        return item
    summary = summarize_artifact_audio_quality(item)
    item["quality_summary"] = summary
    item["quality_verdict"] = summary["quality_verdict"]
    item["quality_flags"] = summary["quality_flags"]
    item["quality_reason"] = summary["quality_reason"]
    return item


def summarize_listening_review(metadata: dict | str | None) -> dict:
    review = _extract_listening_review(metadata)
    verdict = str(review.get("verdict") or "unreviewed").strip()
    if verdict not in LISTENING_REVIEW_VERDICTS:
        verdict = "unreviewed"

    notes = str(review.get("notes") or "")
    is_smoke_note = LISTENING_REVIEW_SMOKE_NOTE in notes
    is_human_reviewed = verdict != "unreviewed" and not is_smoke_note

    return {
        "verdict": verdict,
        "label": LISTENING_REVIEW_LABEL_BY_VERDICT[verdict],
        "route": LISTENING_REVIEW_ROUTE_BY_VERDICT[verdict],
        "priority": LISTENING_REVIEW_PRIORITY_BY_VERDICT[verdict],
        "overall_score": _score_or_none(review.get("overall_score")),
        "vocal_score": _score_or_none(review.get("vocal_score")),
        "noise_score": _score_or_none(review.get("noise_score")),
        "mix_score": _score_or_none(review.get("mix_score")),
        "notes_preview": notes[:80],
        "reviewed_at": str(review.get("reviewed_at") or ""),
        "is_human_reviewed": is_human_reviewed,
    }


def add_listening_review_summary(artifact: dict) -> dict:
    item = dict(artifact)
    summary = summarize_listening_review(item.get("metadata_json"))
    item["listening_review_summary"] = summary
    item["review_verdict"] = summary["verdict"]
    item["review_route"] = summary["route"]
    return add_artifact_quality_summary(item)


def get_job_artifact_review(job_id: str, artifact_id: str) -> dict | None:
    artifact = get_job_artifact(job_id, artifact_id)
    if not artifact:
        return None
    metadata = _parse_metadata(artifact.get("metadata_json"))
    review = metadata.get("listening_review")
    if not isinstance(review, dict):
        review = {}
    return {
        "job_id": job_id,
        "artifact_id": artifact_id,
        "review": review,
        "metadata": metadata,
    }


def update_job_artifact_review(
    job_id: str,
    artifact_id: str,
    *,
    verdict: str = "unreviewed",
    overall_score: int | None = None,
    vocal_score: int | None = None,
    noise_score: int | None = None,
    mix_score: int | None = None,
    notes: str = "",
) -> dict | None:
    artifact = get_job_artifact(job_id, artifact_id)
    if not artifact:
        return None

    metadata = _parse_metadata(artifact.get("metadata_json"))
    review = {
        "verdict": verdict,
        "overall_score": overall_score,
        "vocal_score": vocal_score,
        "noise_score": noise_score,
        "mix_score": mix_score,
        "notes": notes[:500],
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "schema": "stage49_listening_review_v1",
    }
    metadata["listening_review"] = review

    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE job_artifacts
            SET metadata_json = ?
            WHERE job_id = ? AND artifact_id = ?
            """,
            (json.dumps(metadata, ensure_ascii=False), job_id, artifact_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "job_id": job_id,
        "artifact_id": artifact_id,
        "review": review,
        "metadata": metadata,
    }


def get_final_job_artifact(job_id: str) -> dict | None:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM job_artifacts
            WHERE job_id = ? AND is_final = 1
            ORDER BY
                CASE
                    WHEN artifact_type IN ('cover_master', 'train_model_pth') THEN 0
                    WHEN artifact_type IN ('cover_model', 'train_model_index') THEN 1
                    ELSE 2
                END,
                datetime(created_at) DESC,
                rowid DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        if not rows:
            return None
        job_row = _job_row_for_lifecycle(conn, job_id)
        return enrich_job_artifact(dict(rows), job_row=job_row)
    finally:
        conn.close()


def get_final_cover_job_artifact(job_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM job_artifacts
            WHERE job_id = ? AND is_final = 1 AND artifact_type = 'cover_master'
            ORDER BY datetime(created_at) DESC, rowid DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        if not row:
            return None
        job_row = _job_row_for_lifecycle(conn, job_id)
        return enrich_job_artifact(dict(row), job_row=job_row)
    finally:
        conn.close()


def get_final_cover_artifact_review_contract(job_id: str) -> dict:
    artifact = get_final_cover_job_artifact(job_id)
    summary = summarize_listening_review(artifact.get("metadata_json") if artifact else None)
    quality_summary = summarize_artifact_audio_quality(artifact) if artifact else None
    return {
        "has_reviewable_final_artifact": artifact is not None,
        "final_artifact_review_summary": summary,
        "final_artifact_review_verdict": summary["verdict"],
        "final_artifact_review_route": summary["route"],
        "final_artifact_quality_summary": quality_summary,
        "final_artifact_quality_verdict": quality_summary["quality_verdict"] if quality_summary else "",
        "final_artifact_quality_flags": quality_summary["quality_flags"] if quality_summary else [],
    }


def _empty_review_counts() -> dict:
    return {
        "total": 0,
        "unreviewed": 0,
        "needs_work": 0,
        "usable": 0,
        "release_candidate": 0,
        "rejected": 0,
        "quality_reviewable": 0,
        "quality_manual_check": 0,
        "quality_needs_manual_quality_check": 0,
        "quality_blocked": 0,
        "quality_blocked_auto": 0,
        "quality": {
            "reviewable": 0,
            "needs_manual_quality_check": 0,
            "blocked_auto": 0,
        },
    }


def _increment_quality_counts(counts: dict, quality_verdict: str) -> None:
    quality_counts = counts.setdefault("quality", {})
    quality_counts[quality_verdict] = int(quality_counts.get(quality_verdict) or 0) + 1
    if quality_verdict == "reviewable":
        counts["quality_reviewable"] += 1
    elif quality_verdict == "needs_manual_quality_check":
        counts["quality_manual_check"] += 1
        counts["quality_needs_manual_quality_check"] += 1
    elif quality_verdict == "blocked_auto":
        counts["quality_blocked"] += 1
        counts["quality_blocked_auto"] += 1


def _build_review_artifact_item(row: dict, review_summary: dict, quality_summary: dict) -> dict:
    job_id = row.get("job_id") or ""
    artifact_id = row.get("artifact_id") or ""
    track_id = row.get("track_id") or ""
    studio_params: dict[str, str] = {}
    if track_id:
        studio_params["track_id"] = track_id
    studio_params["job_id"] = job_id
    studio_params["artifact_id"] = artifact_id
    file_path = row.get("file_path") or ""
    return {
        "job_id": job_id,
        "artifact_id": artifact_id,
        "artifact_type": row.get("artifact_type") or "",
        "file_name": os.path.basename(file_path),
        "download_url": f"/api/jobs/{job_id}/artifacts/{artifact_id}/download",
        "studio_url": f"/studio?{urlencode(studio_params)}",
        "review_summary": review_summary,
        "review_verdict": review_summary["verdict"],
        "review_route": review_summary["route"],
        "quality_summary": quality_summary,
        "quality_verdict": quality_summary["quality_verdict"],
        "quality_flags": quality_summary["quality_flags"],
        "quality_reason": quality_summary["quality_reason"],
        "created_at": str(row.get("created_at") or ""),
    }


def list_final_cover_review_artifacts(
    verdict: str | None = None,
    quality: str | None = None,
    limit: int = 50,
) -> dict:
    capped_limit = max(1, min(int(limit), 100))
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT ja.*, j.track_id
            FROM job_artifacts ja
            LEFT JOIN jobs j ON j.job_id = ja.job_id
            WHERE ja.is_final = 1 AND ja.artifact_type = 'cover_master'
            ORDER BY datetime(ja.created_at) DESC, ja.rowid DESC
            """
        ).fetchall()
    finally:
        conn.close()

    items: list[dict] = []
    counts = _empty_review_counts()
    for row in rows:
        artifact = dict(row)
        review_summary = summarize_listening_review(artifact.get("metadata_json"))
        quality_summary = summarize_artifact_audio_quality(artifact)
        if verdict and review_summary["verdict"] != verdict:
            continue
        if quality and quality_summary["quality_verdict"] != quality:
            continue
        counts["total"] += 1
        counts[review_summary["verdict"]] += 1
        _increment_quality_counts(counts, quality_summary["quality_verdict"])
        if len(items) < capped_limit:
            items.append(_build_review_artifact_item(artifact, review_summary, quality_summary))

    return {"items": items, "summary": counts}
