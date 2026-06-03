import json
import os
import uuid

try:
    from ..db import get_connection
    from .lifecycle_service import enrich_voice_model, infer_voice_model_lifecycle, should_default_hide_lifecycle
    from .smoke_filter import explain_test_data_filter_reason, is_smoke_model_record
except ImportError:
    from db import get_connection
    from services.lifecycle_service import enrich_voice_model, infer_voice_model_lifecycle, should_default_hide_lifecycle
    from services.smoke_filter import explain_test_data_filter_reason, is_smoke_model_record


ORIGIN_LABELS = {
    "trained_local": "本地训练",
    "imported_external": "外部导入",
    "rescanned_local": "目录扫描",
}

STRATEGY_LABELS = {
    "single_long_preprocess": "单文件快速训练",
    "multi_clean_direct": "多文件精训",
    "cover_strategy": "AI 翻唱",
}

MATERIAL_PROFILE_LABELS = {
    "single_long_candidate": "单文件长样本",
    "single_short_out_of_window": "单文件短样本",
    "single_long_out_of_window": "单文件超长样本",
    "multi_file_dataset": "多文件素材集",
}


def _normalize_path(path: str, project_root: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        try:
            common = os.path.commonpath([os.path.abspath(path), os.path.abspath(project_root)])
            if common == os.path.abspath(project_root):
                return os.path.relpath(path, project_root).replace("\\", "/")
        except Exception:
            pass
        return path
    return path.replace("\\", "/")


def _parse_json_object(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _as_abs_path(path: str, project_root: str) -> str:
    if not path:
        return ""
    return path if os.path.isabs(path) else os.path.join(project_root, path)


def _sync_legacy_voice_asset(model_id: str, model_name: str, pth_path: str, index_path: str, default_pitch: int):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO voice_assets (
                model_id, model_name, pth_path, index_path, default_pitch
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (model_id, model_name, pth_path, index_path, default_pitch),
        )
        conn.commit()
    finally:
        conn.close()


def _resolve_registered_file(stored_path: str, fallback_path: str, project_root: str) -> dict:
    direct_abs = _as_abs_path(stored_path, project_root) if stored_path else ""
    candidates = [candidate for candidate in [direct_abs, fallback_path] if candidate]
    seen = set()
    unique_candidates: list[str] = []
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)

    for candidate in unique_candidates:
        if os.path.exists(candidate):
            return {
                "ok": True,
                "resolved_path": candidate,
                "source": "direct" if direct_abs and os.path.abspath(candidate) == os.path.abspath(direct_abs) else "fallback_name",
            }

    return {
        "ok": False,
        "resolved_path": unique_candidates[-1] if unique_candidates else "",
        "source": "not_found",
    }


def _strategy_label(strategy_key: str) -> str:
    return STRATEGY_LABELS.get(strategy_key or "", strategy_key or "")


def _material_profile_label(profile: str) -> str:
    return MATERIAL_PROFILE_LABELS.get(profile or "", profile or "")


def _origin_kind_from_model(model: dict, metadata: dict) -> str:
    origin_kind = str(metadata.get("origin_kind") or "").strip()
    if origin_kind:
        return origin_kind
    if model.get("source_job_id"):
        return "trained_local"
    if metadata.get("rescanned"):
        return "rescanned_local"
    if metadata.get("imported"):
        return "imported_external"
    return "imported_external"


def _build_source_summary(
    origin_kind: str,
    *,
    source_job_id: str = "",
    source_strategy_key: str = "",
    source_material_profile: str = "",
    source_file_count: int | None = None,
    source_duration_label: str = "",
) -> str:
    if origin_kind == "trained_local":
        parts = [f"来自本地训练任务 {source_job_id}" if source_job_id else "来自本地训练"]
        strategy_label = _strategy_label(source_strategy_key)
        if strategy_label:
            parts.append(strategy_label)
        material_label = _material_profile_label(source_material_profile)
        if material_label:
            parts.append(material_label)
        if source_file_count:
            parts.append(f"{source_file_count} 个文件")
        if source_duration_label:
            parts.append(source_duration_label)
        return " · ".join(parts)

    if origin_kind == "rescanned_local":
        return "来自本地 weights 目录扫描，已按当前文件自动登记。"

    return "来自外部导入，路径由用户手动登记。"


def _load_train_source_context(source_job_id: str) -> dict:
    if not source_job_id:
        return {}

    conn = get_connection()
    try:
        job_row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ? OR legacy_task_id = ? LIMIT 1",
            (source_job_id, source_job_id),
        ).fetchone()
        dataset_row = conn.execute(
            """
            SELECT *
            FROM datasets
            WHERE job_id = ?
            ORDER BY datetime(created_at) DESC, rowid DESC
            LIMIT 1
            """,
            (source_job_id,),
        ).fetchone()
    finally:
        conn.close()

    job = dict(job_row) if job_row else {}
    dataset = dict(dataset_row) if dataset_row else {}
    job_metadata = _parse_json_object(job.get("metadata_json"))
    dataset_metadata = _parse_json_object(dataset.get("metadata_json"))
    material = _parse_json_object(job_metadata.get("material_decision")) or _parse_json_object(dataset_metadata.get("material_decision"))

    file_count = material.get("file_count")
    if file_count in (None, ""):
        file_count = dataset.get("file_count")
    if file_count in (None, ""):
        file_count = job_metadata.get("file_count")
    try:
        file_count = int(file_count) if file_count not in (None, "") else None
    except (TypeError, ValueError):
        file_count = None

    source_strategy_key = (
        str(material.get("recommended_route") or "").strip()
        or str(dataset.get("strategy_key") or "").strip()
        or str(job.get("strategy_key") or "").strip()
    )
    source_material_profile = str(material.get("material_profile") or "").strip()
    source_duration_label = str(material.get("duration_label") or "").strip()

    return {
        "source_job_id": source_job_id,
        "source_strategy_key": source_strategy_key,
        "source_dataset_id": str(dataset.get("dataset_id") or "").strip(),
        "source_material_profile": source_material_profile,
        "source_file_count": file_count,
        "source_duration_label": source_duration_label,
        "source_job_status": str(job.get("status") or "").strip(),
        "source_job_current_stage": str(job.get("current_stage") or "").strip(),
        "source_job_created_at": str(job.get("created_at") or "").strip(),
    }


def _collect_lineage_fields(model: dict) -> dict:
    metadata = _parse_json_object(model.get("metadata_json"))
    origin_kind = _origin_kind_from_model(model, metadata)

    source_job_id = str(metadata.get("source_job_id") or model.get("source_job_id") or "").strip()
    lineage = {
        "origin_kind": origin_kind,
        "source_job_id": source_job_id,
        "source_strategy_key": str(metadata.get("source_strategy_key") or "").strip(),
        "source_dataset_id": str(metadata.get("source_dataset_id") or "").strip(),
        "source_material_profile": str(metadata.get("source_material_profile") or "").strip(),
        "source_file_count": metadata.get("source_file_count"),
        "source_duration_label": str(metadata.get("source_duration_label") or "").strip(),
        "source_job_status": str(metadata.get("source_job_status") or "").strip(),
        "source_job_current_stage": str(metadata.get("source_job_current_stage") or "").strip(),
        "source_job_created_at": str(metadata.get("source_job_created_at") or "").strip(),
    }

    if origin_kind == "trained_local":
        resolved = _load_train_source_context(source_job_id)
        for key, value in resolved.items():
            if lineage.get(key) in ("", None):
                lineage[key] = value

    try:
        file_count = lineage.get("source_file_count")
        lineage["source_file_count"] = int(file_count) if file_count not in (None, "") else None
    except (TypeError, ValueError):
        lineage["source_file_count"] = None

    lineage["source_summary"] = (
        str(metadata.get("source_summary") or "").strip()
        or _build_source_summary(
            lineage["origin_kind"],
            source_job_id=lineage["source_job_id"],
            source_strategy_key=lineage["source_strategy_key"],
            source_material_profile=lineage["source_material_profile"],
            source_file_count=lineage["source_file_count"],
            source_duration_label=lineage["source_duration_label"],
        )
    )
    return lineage


def _enrich_model_row(model: dict, project_root: str, weights_dir: str, *, resolved: dict | None = None) -> dict:
    resolved = resolved or resolve_voice_model_file(model.get("legacy_model_id") or model.get("voice_model_id"), project_root, weights_dir)
    lineage = _collect_lineage_fields(model)
    lifecycle_state = infer_voice_model_lifecycle(model)
    return {
        **enrich_voice_model(model),
        "exists": True,
        "model_id": model.get("legacy_model_id") or model.get("voice_model_id"),
        "usable": bool(resolved["ok"]),
        "pth_exists": bool(resolved["ok"]),
        "index_exists": bool(resolved.get("index_ok")),
        "resolved_pth_path": resolved["resolved_path"],
        "resolved_source": resolved["source"],
        "resolved_index_path": resolved.get("resolved_index_path", ""),
        "resolved_index_source": resolved.get("index_source", ""),
        "metadata": _parse_json_object(model.get("metadata_json")),
        "lifecycle_state": lifecycle_state,
        **lineage,
    }


def build_trained_model_metadata(source_job_id: str) -> dict:
    lineage = _load_train_source_context(source_job_id)
    metadata = {
        "origin_kind": "trained_local",
        "source_job_id": source_job_id or "",
        "source_strategy_key": lineage.get("source_strategy_key") or "",
        "source_dataset_id": lineage.get("source_dataset_id") or "",
        "source_material_profile": lineage.get("source_material_profile") or "",
        "source_file_count": lineage.get("source_file_count"),
        "source_duration_label": lineage.get("source_duration_label") or "",
        "source_summary": _build_source_summary(
            "trained_local",
            source_job_id=source_job_id or "",
            source_strategy_key=lineage.get("source_strategy_key") or "",
            source_material_profile=lineage.get("source_material_profile") or "",
            source_file_count=lineage.get("source_file_count"),
            source_duration_label=lineage.get("source_duration_label") or "",
        ),
    }
    return metadata


def upsert_voice_model(
    voice_model_id: str,
    model_name: str,
    pth_path: str,
    index_path: str,
    default_pitch: int = 0,
    source_job_id: str = "",
    legacy_model_id: str | None = None,
    status: str = "ready",
    metadata: dict | None = None,
) -> str:
    legacy_model_id = legacy_model_id or voice_model_id
    source_job_id = source_job_id or None
    metadata_payload = metadata or {}
    lifecycle_state = infer_voice_model_lifecycle(
        {
            "voice_model_id": voice_model_id,
            "model_name": model_name,
            "status": status,
            "metadata_json": json.dumps(metadata_payload, ensure_ascii=False),
        }
    )
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO voice_models (
                voice_model_id, legacy_model_id, model_name, source_job_id,
                pth_path, index_path, default_pitch, status, lifecycle_state, metadata_json,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                COALESCE((SELECT created_at FROM voice_models WHERE voice_model_id = ?), CURRENT_TIMESTAMP),
                CURRENT_TIMESTAMP
            )
            """,
            (
                voice_model_id,
                legacy_model_id,
                model_name,
                source_job_id,
                pth_path,
                index_path,
                default_pitch,
                status,
                lifecycle_state,
                json.dumps(metadata_payload, ensure_ascii=False),
                voice_model_id,
            ),
        )
        conn.commit()
        _sync_legacy_voice_asset(voice_model_id, model_name, pth_path, index_path, default_pitch)
        return voice_model_id
    finally:
        conn.close()


def get_voice_model(model_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM voice_models WHERE voice_model_id = ? OR legacy_model_id = ? LIMIT 1",
            (model_id, model_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_voice_model_by_source_job(source_job_id: str, project_root: str, weights_dir: str) -> dict | None:
    if not source_job_id:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT voice_model_id, legacy_model_id
            FROM voice_models
            WHERE source_job_id = ?
            ORDER BY datetime(updated_at) DESC, rowid DESC
            LIMIT 1
            """,
            (source_job_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return get_voice_model_detail(row["legacy_model_id"] or row["voice_model_id"], project_root, weights_dir)


def resolve_voice_model_file(model_id: str, project_root: str, weights_dir: str) -> dict:
    model = get_voice_model(model_id)
    if not model:
        return {
            "ok": False,
            "index_ok": False,
            "model_id": model_id,
            "model": None,
            "resolved_path": "",
            "source": "missing",
            "resolved_index_path": "",
            "index_source": "missing",
        }

    pth_resolution = _resolve_registered_file(
        model.get("pth_path") or "",
        os.path.join(weights_dir, f"{model['model_name']}.pth"),
        project_root,
    )
    index_resolution = _resolve_registered_file(
        model.get("index_path") or "",
        os.path.join(weights_dir, f"{model['model_name']}.index"),
        project_root,
    )

    return {
        "ok": bool(pth_resolution["ok"]),
        "index_ok": bool(index_resolution["ok"]),
        "model_id": model_id,
        "model": model,
        "resolved_path": pth_resolution["resolved_path"],
        "source": pth_resolution["source"],
        "resolved_index_path": index_resolution["resolved_path"],
        "index_source": index_resolution["source"],
    }


def get_voice_model_detail(model_id: str, project_root: str, weights_dir: str) -> dict | None:
    resolved = resolve_voice_model_file(model_id, project_root, weights_dir)
    model = resolved["model"]
    if not model:
        return None
    return _enrich_model_row(model, project_root, weights_dir, resolved=resolved)


def list_models(
    project_root: str,
    weights_dir: str,
    include_unavailable: bool = False,
    include_smoke: bool = False,
    include_test_data: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        include_filtered = bool(include_smoke or include_test_data)
        query = "SELECT * FROM voice_models"
        if not include_filtered:
            query += " WHERE COALESCE(lifecycle_state, 'active') NOT IN ('test_data', 'purged')"
        query += " ORDER BY datetime(created_at), rowid"
        rows = conn.execute(query).fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        row_dict = dict(row)
        filter_reason = explain_test_data_filter_reason(row_dict, kind="model")
        if not include_filtered and filter_reason:
            continue
        if not include_filtered and should_default_hide_lifecycle(row_dict.get("lifecycle_state")):
            continue
        enriched = _enrich_model_row(
            row_dict,
            project_root,
            weights_dir,
            resolved=resolve_voice_model_file(row["legacy_model_id"] or row["voice_model_id"], project_root, weights_dir),
        )
        item = {
            "exists": True,
            "model_id": enriched["model_id"],
            "model_name": enriched["model_name"],
            "default_pitch": enriched["default_pitch"],
            "usable": enriched["usable"],
            "pth_exists": enriched["pth_exists"],
            "resolved_pth_path": enriched["resolved_pth_path"],
            "resolved_source": enriched["resolved_source"],
            "index_path": enriched.get("index_path") or "",
            "resolved_index_path": enriched.get("resolved_index_path") or "",
            "origin_kind": enriched.get("origin_kind") or "",
            "source_job_id": enriched.get("source_job_id") or "",
            "source_strategy_key": enriched.get("source_strategy_key") or "",
            "source_dataset_id": enriched.get("source_dataset_id") or "",
            "source_material_profile": enriched.get("source_material_profile") or "",
            "source_file_count": enriched.get("source_file_count"),
            "source_duration_label": enriched.get("source_duration_label") or "",
            "source_summary": enriched.get("source_summary") or "",
            "lifecycle_state": enriched.get("lifecycle_state") or infer_voice_model_lifecycle(row_dict),
            "created_at": enriched.get("created_at") or "",
            "updated_at": enriched.get("updated_at") or "",
        }
        if filter_reason:
            item["filter_reason"] = filter_reason
        if include_unavailable or item["usable"]:
            result.append(item)
    return result


def list_available_models(project_root: str, weights_dir: str) -> list[dict]:
    return list_models(project_root, weights_dir, include_unavailable=False)


def hidden_test_model_count(
    project_root: str,
    weights_dir: str,
    include_unavailable: bool = False,
) -> int:
    visible_items = list_models(
        project_root,
        weights_dir,
        include_unavailable=include_unavailable,
        include_smoke=False,
        include_test_data=False,
    )
    included_items = list_models(
        project_root,
        weights_dir,
        include_unavailable=include_unavailable,
        include_smoke=True,
        include_test_data=True,
    )
    return max(0, len(included_items) - len(visible_items))


def import_voice_model(
    model_name: str,
    pth_path: str,
    index_path: str = "",
    default_pitch: int = 0,
    project_root: str = "",
    weights_dir: str = "",
    *,
    origin_kind: str = "imported_external",
) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT voice_model_id, legacy_model_id
            FROM voice_models
            WHERE model_name = ? OR pth_path = ?
            LIMIT 1
            """,
            (model_name, _normalize_path(pth_path, project_root) if project_root else pth_path),
        ).fetchone()
    finally:
        conn.close()

    model_id = (row["legacy_model_id"] or row["voice_model_id"]) if row else f"vm_{uuid.uuid4().hex[:8]}"
    stored_pth = _normalize_path(pth_path, project_root) if project_root else pth_path
    stored_index = _normalize_path(index_path, project_root) if project_root else index_path
    metadata = {
        "origin_kind": origin_kind,
        "imported": origin_kind == "imported_external",
        "rescanned": origin_kind == "rescanned_local",
        "source_summary": _build_source_summary(origin_kind),
    }
    upsert_voice_model(
        voice_model_id=model_id,
        legacy_model_id=model_id,
        model_name=model_name,
        pth_path=stored_pth,
        index_path=stored_index,
        default_pitch=int(default_pitch or 0),
        status="ready",
        metadata=metadata,
    )
    return get_voice_model_detail(model_id, project_root, weights_dir)


def rescan_voice_models(project_root: str, weights_dir: str) -> dict:
    weights_dir = os.path.abspath(weights_dir)
    registered_before = list_models(project_root, weights_dir, include_unavailable=True)
    imported = 0

    existing_names = {item["model_name"] for item in registered_before}
    for name in sorted(os.listdir(weights_dir)) if os.path.isdir(weights_dir) else []:
        if not name.lower().endswith(".pth"):
            continue
        model_name = os.path.splitext(name)[0]
        if model_name in existing_names:
            continue
        pth_rel = os.path.relpath(os.path.join(weights_dir, name), project_root).replace("\\", "/")
        index_abs = os.path.join(weights_dir, f"{model_name}.index")
        index_rel = os.path.relpath(index_abs, project_root).replace("\\", "/") if os.path.exists(index_abs) else ""
        import_voice_model(
            model_name=model_name,
            pth_path=pth_rel,
            index_path=index_rel,
            default_pitch=0,
            project_root=project_root,
            weights_dir=weights_dir,
            origin_kind="rescanned_local",
        )
        imported += 1

    refreshed = list_models(project_root, weights_dir, include_unavailable=True)
    return {
        "imported_count": imported,
        "model_count": len(refreshed),
        "usable_count": sum(1 for item in refreshed if item["usable"]),
        "models": refreshed,
    }
