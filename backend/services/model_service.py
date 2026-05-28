import json
import os
import uuid

try:
    from ..db import get_connection
    from .smoke_filter import is_smoke_model_record
except ImportError:
    from db import get_connection
    from services.smoke_filter import is_smoke_model_record


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
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO voice_models (
                voice_model_id, legacy_model_id, model_name, source_job_id,
                pth_path, index_path, default_pitch, status, metadata_json,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
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
                json.dumps(metadata or {}, ensure_ascii=False),
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


def resolve_voice_model_file(model_id: str, project_root: str, weights_dir: str) -> dict:
    model = get_voice_model(model_id)
    if not model:
        return {
            "ok": False,
            "model_id": model_id,
            "model": None,
            "resolved_path": "",
            "source": "missing",
        }

    pth_path = model["pth_path"] or ""
    candidates = []
    if pth_path:
        candidates.append(pth_path if os.path.isabs(pth_path) else os.path.join(project_root, pth_path))
    candidates.append(os.path.join(weights_dir, f"{model['model_name']}.pth"))

    for candidate in candidates:
        if os.path.exists(candidate):
            return {
                "ok": True,
                "model_id": model_id,
                "model": model,
                "resolved_path": candidate,
                "source": "direct" if os.path.abspath(candidate) == os.path.abspath(pth_path) else "fallback_name",
            }

    return {
        "ok": False,
        "model_id": model_id,
        "model": model,
        "resolved_path": candidates[-1] if candidates else "",
        "source": "not_found",
    }


def get_voice_model_detail(model_id: str, project_root: str, weights_dir: str) -> dict | None:
    resolved = resolve_voice_model_file(model_id, project_root, weights_dir)
    model = resolved["model"]
    if not model:
        return None
    return {
        **model,
        "exists": True,
        "model_id": model.get("legacy_model_id") or model.get("voice_model_id"),
        "usable": bool(resolved["ok"]),
        "resolved_pth_path": resolved["resolved_path"],
        "resolved_source": resolved["source"],
    }


def list_models(
    project_root: str,
    weights_dir: str,
    include_unavailable: bool = False,
    include_smoke: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM voice_models
            ORDER BY datetime(created_at), rowid
            """
        ).fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        row_dict = dict(row)
        if not include_smoke and is_smoke_model_record(row_dict):
            continue
        resolved = resolve_voice_model_file(row["legacy_model_id"] or row["voice_model_id"], project_root, weights_dir)
        item = {
            "exists": True,
            "model_id": row["legacy_model_id"] or row["voice_model_id"],
            "model_name": row["model_name"],
            "default_pitch": row["default_pitch"],
            "usable": bool(resolved["ok"]),
            "pth_exists": bool(resolved["ok"]),
            "resolved_pth_path": resolved["resolved_path"],
            "resolved_source": resolved["source"],
        }
        if include_unavailable or item["usable"]:
            result.append(item)
    return result


def list_available_models(project_root: str, weights_dir: str) -> list[dict]:
    return list_models(project_root, weights_dir, include_unavailable=False)


def import_voice_model(
    model_name: str,
    pth_path: str,
    index_path: str = "",
    default_pitch: int = 0,
    project_root: str = "",
    weights_dir: str = "",
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
    upsert_voice_model(
        voice_model_id=model_id,
        legacy_model_id=model_id,
        model_name=model_name,
        pth_path=stored_pth,
        index_path=stored_index,
        default_pitch=int(default_pitch or 0),
        status="ready",
        metadata={"imported": True},
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
        )
        imported += 1

    refreshed = list_models(project_root, weights_dir, include_unavailable=True)
    return {
        "imported_count": imported,
        "model_count": len(refreshed),
        "usable_count": sum(1 for item in refreshed if item["usable"]),
        "models": refreshed,
    }
