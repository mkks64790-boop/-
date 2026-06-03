"""
Stage 59A — explicit asset lifecycle states.

Authoritative cleanup and acceptance gates should prefer lifecycle_state over regex-only smoke_filter.
smoke_filter remains the default list-hide layer for Dashboard/Factory.
"""

from __future__ import annotations

import os
from typing import Any

try:
    from ..db import get_connection
    from .smoke_filter import explain_test_data_filter_reason, parse_metadata
except ImportError:
    from db import get_connection
    from services.smoke_filter import explain_test_data_filter_reason, parse_metadata

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_TRANSIENT = "transient"
LIFECYCLE_ARCHIVED = "archived"
LIFECYCLE_PURGED = "purged"
LIFECYCLE_TEST_DATA = "test_data"

LIFECYCLE_STATES = frozenset(
    {
        LIFECYCLE_ACTIVE,
        LIFECYCLE_TRANSIENT,
        LIFECYCLE_ARCHIVED,
        LIFECYCLE_PURGED,
        LIFECYCLE_TEST_DATA,
    }
)

COVER_TRANSIENT_ARTIFACT_TYPES = frozenset(
    {
        "cover_vocal",
        "cover_instrumental",
        "cover_fixed",
        "cover_transformed",
    }
)

FINAL_ARTIFACT_TYPES = frozenset(
    {
        "cover_master",
        "studio_effect_draft_master",
        "studio_effect_render_master",
        "train_model_pth",
        "train_model_index",
    }
)

TRANSIENT_OUTPUT_FILENAMES = frozenset(
    {
        "vocal.wav",
        "instrumental.wav",
        "fixed.wav",
        "transformed.wav",
        "vocal_fixed.wav",
        "vocal_transformed.wav",
    }
)

RETENTION_TO_LIFECYCLE = {
    "active": LIFECYCLE_ACTIVE,
    "review": LIFECYCLE_ACTIVE,
    "quarantined": LIFECYCLE_ARCHIVED,
    "archived": LIFECYCLE_ARCHIVED,
    "purged": LIFECYCLE_PURGED,
}


def normalize_lifecycle_state(value: str | None) -> str:
    state = (value or "").strip().lower()
    return state if state in LIFECYCLE_STATES else ""


def retention_status_to_lifecycle(retention_status: str | None) -> str:
    key = (retention_status or "").strip().lower()
    return RETENTION_TO_LIFECYCLE.get(key, LIFECYCLE_ACTIVE)


def is_test_data_job(job_row: dict | None) -> bool:
    if not job_row:
        return False
    return bool(explain_test_data_filter_reason(job_row, kind="job"))


def is_test_data_model(model_row: dict | None) -> bool:
    if not model_row:
        return False
    return bool(explain_test_data_filter_reason(model_row, kind="model"))


def infer_job_artifact_lifecycle(
    artifact_row: dict,
    *,
    job_row: dict | None = None,
    use_stored: bool = True,
) -> str:
    if use_stored:
        stored = normalize_lifecycle_state(artifact_row.get("lifecycle_state"))
        if stored:
            return stored

    metadata = parse_metadata(artifact_row.get("metadata_json"))
    if metadata.get("lifecycle_state"):
        stored = normalize_lifecycle_state(metadata.get("lifecycle_state"))
        if stored:
            return stored

    artifact_type = str(artifact_row.get("artifact_type") or "")
    is_final = bool(artifact_row.get("is_final"))
    if is_test_data_job(job_row):
        return LIFECYCLE_TEST_DATA

    if is_final or artifact_type in FINAL_ARTIFACT_TYPES:
        return LIFECYCLE_ACTIVE

    if artifact_type in COVER_TRANSIENT_ARTIFACT_TYPES:
        return LIFECYCLE_TRANSIENT

    basename = artifact_row.get("file_path", "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    if basename in TRANSIENT_OUTPUT_FILENAMES:
        return LIFECYCLE_TRANSIENT

    return LIFECYCLE_ACTIVE


def infer_audio_asset_lifecycle(asset_row: dict, *, job_row: dict | None = None, use_stored: bool = True) -> str:
    if use_stored:
        stored = normalize_lifecycle_state(asset_row.get("lifecycle_state"))
        if stored:
            return stored

    if is_test_data_job(job_row):
        return LIFECYCLE_TEST_DATA

    role = str(asset_row.get("asset_role") or "").strip().lower()
    if role in {"input", "source", "upload", "dataset", "cover_source"}:
        return LIFECYCLE_ACTIVE
    if role in {"intermediate", "transient", "scratch"}:
        return LIFECYCLE_TRANSIENT
    return LIFECYCLE_ACTIVE


def infer_voice_model_lifecycle(model_row: dict, *, use_stored: bool = True) -> str:
    if use_stored:
        stored = normalize_lifecycle_state(model_row.get("lifecycle_state"))
        if stored:
            return stored

    if is_test_data_model(model_row):
        return LIFECYCLE_TEST_DATA
    if str(model_row.get("status") or "").strip().lower() in {"archived", "retired"}:
        return LIFECYCLE_ARCHIVED
    return LIFECYCLE_ACTIVE


def infer_material_asset_lifecycle(material_row: dict) -> str:
    stored = normalize_lifecycle_state(material_row.get("lifecycle_state"))
    if stored:
        return stored
    return retention_status_to_lifecycle(material_row.get("retention_status"))


def lifecycle_allows_file_delete(state: str) -> bool:
    return normalize_lifecycle_state(state) == LIFECYCLE_TRANSIENT


def lifecycle_blocks_download(state: str) -> bool:
    return normalize_lifecycle_state(state) in {LIFECYCLE_PURGED, LIFECYCLE_ARCHIVED}


def should_default_hide_lifecycle(state: str | None) -> bool:
    """Default product lists hide test_data and purged rows (lifecycle authority)."""
    return normalize_lifecycle_state(state) in {LIFECYCLE_TEST_DATA, LIFECYCLE_PURGED}


def should_backfill_lifecycle_state(stored_raw: str | None, inferred: str) -> bool:
    """
    Legacy DB rows get DEFAULT 'active' on ALTER; skip backfill only when stored is
    a non-active explicit state. Re-infer when stored is active but inference differs.
    """
    stored = normalize_lifecycle_state(stored_raw)
    inferred_norm = normalize_lifecycle_state(inferred) or LIFECYCLE_ACTIVE
    if not stored:
        return True
    if stored == LIFECYCLE_ACTIVE and inferred_norm != LIFECYCLE_ACTIVE:
        return True
    return False


def is_valid_lifecycle_transition(current: str, target: str) -> bool:
    cur = normalize_lifecycle_state(current) or LIFECYCLE_ACTIVE
    nxt = normalize_lifecycle_state(target)
    if not nxt or cur == nxt:
        return bool(nxt)
    if cur == LIFECYCLE_PURGED:
        return False
    allowed = {
        LIFECYCLE_ACTIVE: {LIFECYCLE_ARCHIVED, LIFECYCLE_TEST_DATA, LIFECYCLE_TRANSIENT},
        LIFECYCLE_TRANSIENT: {LIFECYCLE_ACTIVE, LIFECYCLE_ARCHIVED, LIFECYCLE_PURGED, LIFECYCLE_TEST_DATA},
        LIFECYCLE_TEST_DATA: {LIFECYCLE_ACTIVE, LIFECYCLE_ARCHIVED},
        LIFECYCLE_ARCHIVED: {LIFECYCLE_ACTIVE, LIFECYCLE_TEST_DATA},
    }
    return nxt in allowed.get(cur, set())


def enrich_job_artifact(artifact_row: dict, *, job_row: dict | None = None) -> dict:
    enriched = dict(artifact_row)
    state = infer_job_artifact_lifecycle(enriched, job_row=job_row)
    enriched["lifecycle_state"] = state
    enriched["lifecycle_deletable"] = lifecycle_allows_file_delete(state)
    enriched["lifecycle_downloadable"] = not lifecycle_blocks_download(state)
    return enriched


def enrich_audio_asset(asset_row: dict, *, job_row: dict | None = None) -> dict:
    enriched = dict(asset_row)
    state = infer_audio_asset_lifecycle(enriched, job_row=job_row)
    enriched["lifecycle_state"] = state
    enriched["lifecycle_deletable"] = lifecycle_allows_file_delete(state)
    enriched["lifecycle_downloadable"] = not lifecycle_blocks_download(state)
    return enriched


def enrich_voice_model(model_row: dict) -> dict:
    enriched = dict(model_row)
    state = infer_voice_model_lifecycle(enriched)
    enriched["lifecycle_state"] = state
    enriched["lifecycle_downloadable"] = not lifecycle_blocks_download(state)
    return enriched


def enrich_material_asset(material_row: dict) -> dict:
    enriched = dict(material_row)
    state = infer_material_asset_lifecycle(enriched)
    enriched["lifecycle_state"] = state
    enriched["retention_status"] = enriched.get("retention_status") or "active"
    return enriched


def resolve_register_job_artifact_lifecycle(
    *,
    artifact_type: str,
    is_final: bool,
    job_row: dict | None = None,
) -> str:
    if is_test_data_job(job_row):
        return LIFECYCLE_TEST_DATA
    if is_final or artifact_type in FINAL_ARTIFACT_TYPES:
        return LIFECYCLE_ACTIVE
    if artifact_type in COVER_TRANSIENT_ARTIFACT_TYPES:
        return LIFECYCLE_TRANSIENT
    return LIFECYCLE_ACTIVE


def resolve_register_audio_asset_lifecycle(*, asset_role: str, job_row: dict | None = None) -> str:
    if is_test_data_job(job_row):
        return LIFECYCLE_TEST_DATA
    role = (asset_role or "").strip().lower()
    if role in {"intermediate", "transient", "scratch"}:
        return LIFECYCLE_TRANSIENT
    return LIFECYCLE_ACTIVE


def _fetch_job_row(conn, job_id: str) -> dict | None:
    row = conn.execute(
        "SELECT job_id, job_type, status, metadata_json, voice_name, strategy_key FROM jobs WHERE job_id = ? LIMIT 1",
        (job_id,),
    ).fetchone()
    return dict(row) if row else None


def mark_job_transient_artifacts_purged(job_id: str, *, deleted_paths: list[str] | None = None) -> int:
    """After filesystem cleanup, mark matching transient artifacts as purged."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT artifact_id, file_path, lifecycle_state, artifact_type, is_final, metadata_json
            FROM job_artifacts
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchall()
        affected = 0
        deleted_abs = {path.replace("\\", "/") for path in (deleted_paths or [])}
        for row in rows:
            row_dict = dict(row)
            state = infer_job_artifact_lifecycle(row_dict)
            if state not in {LIFECYCLE_TRANSIENT, LIFECYCLE_TEST_DATA}:
                continue
            file_path = str(row_dict.get("file_path") or "")
            if deleted_paths is not None:
                normalized = file_path.replace("\\", "/")
                deleted_names = {p.replace("\\", "/").rsplit("/", 1)[-1] for p in deleted_abs}
                if normalized not in deleted_abs and os.path.basename(normalized) not in deleted_names:
                    continue
            conn.execute(
                "UPDATE job_artifacts SET lifecycle_state = ? WHERE artifact_id = ?",
                (LIFECYCLE_PURGED, row_dict["artifact_id"]),
            )
            affected += 1
        conn.commit()
        return affected
    finally:
        conn.close()


def backfill_lifecycle_states(conn) -> dict[str, int]:
    """Populate lifecycle_state columns for legacy rows."""
    stats = {"job_artifacts": 0, "audio_assets": 0, "voice_models": 0, "material_assets": 0}
    job_cache: dict[str, dict | None] = {}

    def job_for(job_id: str) -> dict | None:
        if job_id not in job_cache:
            job_cache[job_id] = _fetch_job_row(conn, job_id)
        return job_cache[job_id]

    artifact_rows = conn.execute(
        "SELECT artifact_id, job_id, artifact_type, is_final, file_path, metadata_json, lifecycle_state FROM job_artifacts"
    ).fetchall()
    for row in artifact_rows:
        row_dict = dict(row)
        state = infer_job_artifact_lifecycle(
            row_dict, job_row=job_for(row_dict["job_id"]), use_stored=False
        )
        if not should_backfill_lifecycle_state(row_dict.get("lifecycle_state"), state):
            continue
        conn.execute(
            "UPDATE job_artifacts SET lifecycle_state = ? WHERE artifact_id = ?",
            (state, row_dict["artifact_id"]),
        )
        stats["job_artifacts"] += 1

    audio_rows = conn.execute(
        "SELECT asset_id, job_id, asset_role, metadata_json, lifecycle_state FROM audio_assets"
    ).fetchall()
    for row in audio_rows:
        row_dict = dict(row)
        state = infer_audio_asset_lifecycle(
            row_dict, job_row=job_for(row_dict["job_id"]), use_stored=False
        )
        if not should_backfill_lifecycle_state(row_dict.get("lifecycle_state"), state):
            continue
        conn.execute(
            "UPDATE audio_assets SET lifecycle_state = ? WHERE asset_id = ?",
            (state, row_dict["asset_id"]),
        )
        stats["audio_assets"] += 1

    model_rows = conn.execute(
        "SELECT voice_model_id, model_name, status, metadata_json, lifecycle_state FROM voice_models"
    ).fetchall()
    for row in model_rows:
        row_dict = dict(row)
        state = infer_voice_model_lifecycle(row_dict, use_stored=False)
        if not should_backfill_lifecycle_state(row_dict.get("lifecycle_state"), state):
            continue
        conn.execute(
            "UPDATE voice_models SET lifecycle_state = ? WHERE voice_model_id = ?",
            (state, row_dict["voice_model_id"]),
        )
        stats["voice_models"] += 1

    try:
        material_rows = conn.execute(
            "SELECT material_id, retention_status, lifecycle_state FROM material_assets"
        ).fetchall()
    except Exception:
        material_rows = []

    for row in material_rows:
        row_dict = dict(row)
        state = retention_status_to_lifecycle(row_dict.get("retention_status"))
        if not should_backfill_lifecycle_state(row_dict.get("lifecycle_state"), state):
            continue
        conn.execute(
            "UPDATE material_assets SET lifecycle_state = ? WHERE material_id = ?",
            (state, row_dict["material_id"]),
        )
        stats["material_assets"] += 1

    return stats


def update_job_artifact_lifecycle_state(job_id: str, artifact_id: str, lifecycle_state: str) -> dict | None:
    target = normalize_lifecycle_state(lifecycle_state)
    if not target:
        raise ValueError("lifecycle_state_invalid")

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM job_artifacts
            WHERE job_id = ? AND artifact_id = ?
            LIMIT 1
            """,
            (job_id, artifact_id),
        ).fetchone()
        if not row:
            return None
        job_row = _fetch_job_row(conn, job_id)
        current = infer_job_artifact_lifecycle(dict(row), job_row=job_row)
        if not is_valid_lifecycle_transition(current, target):
            raise ValueError("lifecycle_transition_not_allowed")
        conn.execute(
            "UPDATE job_artifacts SET lifecycle_state = ? WHERE artifact_id = ?",
            (target, artifact_id),
        )
        conn.commit()
        updated = dict(row)
        updated["lifecycle_state"] = target
        return enrich_job_artifact(updated, job_row=job_row)
    finally:
        conn.close()