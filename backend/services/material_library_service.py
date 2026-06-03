from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from ..db import get_connection, init_db
    from .asset_service import list_final_cover_review_artifacts
    from .audio_material_service import probe_audio_material
except ImportError:
    from db import get_connection, init_db
    from services.asset_service import list_final_cover_review_artifacts
    from services.audio_material_service import probe_audio_material


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATERIAL_LIBRARY_RELATIVE = Path("shared_data") / "material_library"
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}
SONOVOX_DEMO_DATASET_ENV = "FEISHARK_SONOVOX_DEMO_DATASET_ROOT"
AUTHORIZED_DRY_VOCAL_ROOTS_ENV = "FEISHARK_AUTHORIZED_DRY_VOCAL_ROOTS"
MAX_SCAN_FILES_PER_LIBRARY = int(os.getenv("FEISHARK_MATERIAL_LIBRARY_MAX_FILES", "200"))
RISKY_MIX_KEYWORDS = {"dj", "dj版", "remix", "bootleg", "成品", "混音", "母带", "master", "final", "release"}


def scan_material_library(project_root: str | Path | None = None, *, max_files: int = MAX_SCAN_FILES_PER_LIBRARY) -> dict:
    root = Path(project_root) if project_root else PROJECT_ROOT
    specs = _material_library_specs(root)
    _ensure_material_dirs(root)
    init_db()

    scanned_at = _now_iso()
    libraries = []
    items = []
    conn = get_connection()
    try:
        for spec in specs:
            library = _upsert_library(conn, spec, scanned_at)
            libraries.append(library)
            conn.execute("DELETE FROM material_assets WHERE library_id = ?", (library["library_id"],))
            if not spec["root_path"].is_dir():
                continue
            for path in _iter_audio_files(spec["root_path"], max_files=max_files):
                item = _build_material_item(path, spec, library["library_id"])
                _insert_material_item(conn, item)
                items.append(item)
        manifest_library = next((item for item in libraries if item["library_key"] == "manifest_user_external"), None)
        if manifest_library:
            for item in _external_manifest_items(root, manifest_library["library_id"]):
                _insert_material_item(conn, item)
                items.append(item)
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "scanned_at": scanned_at,
        "root": str(root),
        "summary": _summarize_items(items, libraries),
        "libraries": libraries,
        "items": items,
        "safety": {
            "raw_dataset_committed_to_git": False,
            "destructive_cleanup": False,
            "max_scan_files_per_library": max_files,
            "supported_extensions": sorted(SUPPORTED_AUDIO_EXTENSIONS),
        },
    }


def material_library_summary(project_root: str | Path | None = None, *, auto_scan: bool = True) -> dict:
    if auto_scan and not _has_material_rows():
        return scan_material_library(project_root)
    libraries = _read_libraries()
    items = _read_items(limit=500)
    return {
        "ok": True,
        "summary": _summarize_items(items, libraries),
        "libraries": libraries,
        "safety": {
            "raw_dataset_committed_to_git": False,
            "destructive_cleanup": False,
            "supported_extensions": sorted(SUPPORTED_AUDIO_EXTENSIONS),
        },
    }


def material_library_items(
    project_root: str | Path | None = None,
    *,
    role: str = "",
    profile: str = "",
    retention: str = "active",
    limit: int = 100,
) -> dict:
    if not _has_material_rows():
        scan_material_library(project_root)
    items = _read_items(role=role, profile=profile, retention=retention, limit=limit)
    return {"ok": True, "items": items, "count": len(items)}


def material_hygiene_summary() -> dict:
    init_db()
    review_payload = list_final_cover_review_artifacts(limit=100)
    artifact_items = review_payload.get("items") or []
    review_summary = review_payload.get("summary") or {}
    conn = get_connection()
    try:
        model_rows = conn.execute(
            """
            SELECT voice_model_id, model_name, source_job_id, pth_path, index_path, status, metadata_json
            FROM voice_models
            ORDER BY updated_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    artifacts = [_artifact_review_hygiene_item(item) for item in artifact_items]
    models = [_model_hygiene_item(row) for row in model_rows]
    archive_candidates = [item for item in artifacts if item["retention_recommendation"] == "archive_candidate"]
    keep_candidates = [item for item in artifacts if item["retention_recommendation"] == "keep_reviewable"]
    protected_models = [item for item in models if item["protected"]]
    return {
        "ok": True,
        "policy": {
            "mode": "non_destructive_review_only",
            "delete_files": False,
            "protected_user_material": ["朱朱", "recovered", "stage47"],
        },
        "summary": {
            "cover_master_total": int(review_summary.get("total") or len(artifacts)),
            "cover_master_keep_reviewable": int(review_summary.get("quality_reviewable") or len(keep_candidates)),
            "cover_master_manual_quality_check": int(review_summary.get("quality_manual_check") or 0),
            "cover_master_archive_candidates": int(review_summary.get("quality_blocked") or len(archive_candidates)),
            "voice_model_total": len(models),
            "voice_model_protected": len(protected_models),
        },
        "archive_candidates": archive_candidates[:50],
        "keep_candidates": keep_candidates[:50],
        "protected_models": protected_models[:50],
    }


def _material_library_specs(root: Path) -> list[dict[str, Any]]:
    material_root = root / MATERIAL_LIBRARY_RELATIVE
    specs: list[dict[str, Any]] = []
    sonovox_root = os.environ.get(SONOVOX_DEMO_DATASET_ENV, "").strip()
    if sonovox_root:
        specs.append(
            _library_spec(
                "sonovox_demo_env",
                "Sonovox Demo Dataset",
                Path(sonovox_root),
                "sonovox_demo",
                "user_provided_local",
                "user_provided_local_sonovox_demo",
                "external_read_only",
            )
        )
    for index, path in enumerate(_split_env_paths(os.environ.get(AUTHORIZED_DRY_VOCAL_ROOTS_ENV, "")), start=1):
        specs.append(
            _library_spec(
                f"authorized_dry_vocal_env_{index}",
                f"Authorized Dry Vocal Root {index}",
                Path(path),
                "authorized_dry_vocal",
                "user_provided_local",
                "user_provided_local_authorized_dry_vocal",
                "external_read_only",
            )
        )

    specs.extend(
        [
            _library_spec(
                "repo_user_dry_vocals",
                "User Dry Vocals",
                material_root / "authorized_dry_vocals" / "user",
                "authorized_dry_vocal",
                "user_provided_local",
                "user_provided_local_authorized_dry_vocal",
                "repo_local_manifested",
            ),
            _library_spec(
                "manifest_user_external",
                "Manifested External User Material",
                material_root / "manifests",
                "authorized_dry_vocal",
                "user_provided_local",
                "user_provided_local_manifest",
                "external_manifest_only",
            ),
            _library_spec(
                "repo_sonovox_demo",
                "Sonovox Demo Dataset Placeholder",
                material_root / "authorized_dry_vocals" / "sonovox_demo",
                "sonovox_demo",
                "user_provided_local",
                "user_provided_local_sonovox_demo",
                "repo_local_manifested",
            ),
            _library_spec(
                "public_domain_voice",
                "Public Domain Voice Samples",
                material_root / "authorized_dry_vocals" / "public_domain_voice",
                "authorized_dry_vocal",
                "public_domain_or_cc",
                "public_domain_or_cc_verified_voice",
                "repo_local_manifested",
            ),
            _library_spec(
                "cover_source_user",
                "User Cover Source Candidates",
                material_root / "cover_source_candidates" / "user",
                "cover_source",
                "user_provided_local",
                "user_provided_local_cover_source_manual_confirmation",
                "repo_local_manifested",
            ),
            _library_spec(
                "separation_public_domain",
                "Public Domain Separation Benchmarks",
                material_root / "separation_benchmarks" / "public_domain",
                "separation_benchmark",
                "public_domain_or_cc",
                "public_domain_or_cc_verified",
                "repo_local_manifested",
            ),
            _library_spec(
                "separation_synthetic",
                "Synthetic Separation Benchmarks",
                material_root / "separation_benchmarks" / "synthetic",
                "separation_benchmark",
                "generated_local",
                "generated_local_cc0",
                "repo_local_manifested",
            ),
            _library_spec(
                "quarantine",
                "Quarantine",
                material_root / "quarantine",
                "quarantine",
                "unknown",
                "quarantine_review_required",
                "repo_local_manifested",
            ),
        ]
    )
    return specs


def _library_spec(
    library_key: str,
    display_name: str,
    root_path: Path,
    source_group: str,
    license_status: str,
    license_tag: str,
    storage_policy: str,
) -> dict[str, Any]:
    return {
        "library_key": library_key,
        "display_name": display_name,
        "root_path": root_path,
        "source_group": source_group,
        "license_status": license_status,
        "license_tag": license_tag,
        "storage_policy": storage_policy,
    }


def _ensure_material_dirs(root: Path) -> None:
    material_root = root / MATERIAL_LIBRARY_RELATIVE
    for relative in (
        "authorized_dry_vocals/user",
        "authorized_dry_vocals/sonovox_demo",
        "authorized_dry_vocals/public_domain_voice",
        "cover_source_candidates/user",
        "separation_benchmarks/public_domain",
        "separation_benchmarks/synthetic",
        "manifests",
        "quarantine",
    ):
        (material_root / relative).mkdir(parents=True, exist_ok=True)


def _upsert_library(conn, spec: dict[str, Any], scanned_at: str) -> dict:
    library_id = _stable_id("lib", spec["library_key"])
    payload = {
        "exists": spec["root_path"].is_dir(),
        "storage_policy": spec["storage_policy"],
    }
    conn.execute(
        """
        INSERT INTO material_libraries (
            library_id, library_key, display_name, source_group, root_path, license_status,
            license_tag, storage_policy, enabled, metadata_json, last_scanned_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(library_key) DO UPDATE SET
            display_name=excluded.display_name,
            source_group=excluded.source_group,
            root_path=excluded.root_path,
            license_status=excluded.license_status,
            license_tag=excluded.license_tag,
            storage_policy=excluded.storage_policy,
            metadata_json=excluded.metadata_json,
            last_scanned_at=excluded.last_scanned_at,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            library_id,
            spec["library_key"],
            spec["display_name"],
            spec["source_group"],
            str(spec["root_path"]),
            spec["license_status"],
            spec["license_tag"],
            spec["storage_policy"],
            json.dumps(payload, ensure_ascii=False),
            scanned_at,
        ),
    )
    return {
        "library_id": library_id,
        "library_key": spec["library_key"],
        "display_name": spec["display_name"],
        "source_group": spec["source_group"],
        "root_path": str(spec["root_path"]),
        "exists": spec["root_path"].is_dir(),
        "license_status": spec["license_status"],
        "license_tag": spec["license_tag"],
        "storage_policy": spec["storage_policy"],
        "last_scanned_at": scanned_at,
    }


def _build_material_item(path: Path, spec: dict[str, Any], library_id: str) -> dict[str, Any]:
    stat = path.stat()
    probe: dict[str, Any] = {}
    quality_state = "metadata_only"
    try:
        probe = probe_audio_material(str(path), file_name=path.name, file_size=stat.st_size)
        quality_state = "probe_ok"
    except Exception as exc:
        probe = {"probe_error": str(exc)}
        quality_state = "probe_failed"

    classification = _classify_material(path, spec, quality_state)
    relative_path = _safe_relative(path, spec["root_path"])
    return {
        "material_id": _stable_id("mat", f"{library_id}:{path.resolve()}"),
        "library_id": library_id,
        "source_group": spec["source_group"],
        "file_name": path.name,
        "file_ext": path.suffix.lower(),
        "file_path": str(path),
        "relative_path": relative_path,
        "file_size": stat.st_size,
        "duration_sec": probe.get("duration_seconds"),
        "sample_rate": probe.get("sample_rate"),
        "channels": probe.get("channels"),
        "codec": probe.get("codec") or "",
        "material_role": classification["material_role"],
        "material_profile": classification["material_profile"],
        "quality_state": quality_state,
        "route_hint": classification["route_hint"],
        "license_tag": spec["license_tag"],
        "license_status": spec["license_status"],
        "retention_status": classification["retention_status"],
        "metadata": {
            "probe": probe,
            "risk_flags": classification["risk_flags"],
            "storage_policy": spec["storage_policy"],
        },
    }


def _classify_material(path: Path, spec: dict[str, Any], quality_state: str) -> dict[str, Any]:
    source_group = spec["source_group"]
    text = f"{path.name} {path.parent.name}".lower()
    risk_flags = [keyword for keyword in RISKY_MIX_KEYWORDS if keyword in text]
    if source_group == "quarantine" or risk_flags:
        return {
            "material_role": "unknown",
            "material_profile": "unsupported_risky_mix" if risk_flags else "quarantine_review",
            "route_hint": "quarantine_review_required",
            "retention_status": "quarantined",
            "risk_flags": risk_flags or ["quarantine"],
        }
    if source_group in {"authorized_dry_vocal", "sonovox_demo"}:
        return {
            "material_role": "dry_vocal",
            "material_profile": "clean_dry_vocal" if quality_state == "probe_ok" else "dry_vocal_probe_pending",
            "route_hint": "training_baseline_multi_clean_direct",
            "retention_status": "active",
            "risk_flags": [],
        }
    if source_group == "cover_source":
        return {
            "material_role": "cover_source",
            "material_profile": "cover_source_manual_candidate",
            "route_hint": "cover_source_manual_review_only",
            "retention_status": "active",
            "risk_flags": [],
        }
    if source_group == "separation_benchmark":
        synthetic = "synthetic" in str(spec["root_path"]).lower()
        return {
            "material_role": "clean_song" if not synthetic else "synthetic_mix",
            "material_profile": "separation_eval_candidate" if not synthetic else "synthetic_separation_benchmark",
            "route_hint": "separation_eval_clip_only",
            "retention_status": "active",
            "risk_flags": [],
        }
    return {
        "material_role": "unknown",
        "material_profile": "needs_manual_review",
        "route_hint": "manual_review_required",
        "retention_status": "review",
        "risk_flags": [],
    }


def _external_manifest_items(root: Path, library_id: str) -> list[dict[str, Any]]:
    manifests_root = root / MATERIAL_LIBRARY_RELATIVE / "manifests"
    result: list[dict[str, Any]] = []
    if not manifests_root.is_dir():
        return result
    for manifest_path in sorted(manifests_root.glob("*.json")):
        manifest = _loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
        entries = manifest.get("entries") if isinstance(manifest, dict) else []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("external_path"):
                continue
            project_path = str(entry.get("project_path") or "").strip()
            if project_path and (root / project_path).is_file():
                continue
            category = str(entry.get("category") or "").lower()
            if "dry" not in category and "vocal" not in category:
                continue
            result.append(_build_external_manifest_item(entry, library_id, manifest_path))
    return result


def _build_external_manifest_item(entry: dict[str, Any], library_id: str, manifest_path: Path) -> dict[str, Any]:
    external_path = Path(str(entry.get("external_path") or ""))
    file_exists = external_path.is_file()
    size = int(entry.get("size_bytes") or 0)
    probe: dict[str, Any] = {"manifest_path": str(manifest_path)}
    quality_state = "metadata_only"
    if file_exists:
        try:
            size = external_path.stat().st_size
            probe = probe_audio_material(str(external_path), file_name=external_path.name, file_size=size)
            probe["manifest_path"] = str(manifest_path)
            quality_state = "probe_ok"
        except Exception as exc:
            probe = {"probe_error": str(exc), "manifest_path": str(manifest_path)}
            quality_state = "probe_failed"
    else:
        probe["file_missing"] = True

    return {
        "material_id": _stable_id("mat", f"{library_id}:{entry.get('id') or external_path}"),
        "library_id": library_id,
        "source_group": "authorized_dry_vocal",
        "file_name": external_path.name or str(entry.get("id") or "external_material"),
        "file_ext": external_path.suffix.lower(),
        "file_path": str(external_path),
        "relative_path": str(entry.get("id") or external_path.name),
        "file_size": size,
        "duration_sec": probe.get("duration_seconds"),
        "sample_rate": probe.get("sample_rate"),
        "channels": probe.get("channels"),
        "codec": probe.get("codec") or "",
        "material_role": "dry_vocal",
        "material_profile": "clean_dry_vocal" if quality_state == "probe_ok" else "dry_vocal_manifest_pending",
        "quality_state": quality_state,
        "route_hint": "training_baseline_external_manifest",
        "license_tag": str(entry.get("license_or_rights_basis") or "user_provided_local_manifest"),
        "license_status": "user_provided_local",
        "retention_status": "active" if file_exists else "review",
        "metadata": {
            "manifest_entry": entry,
            "probe": probe,
            "storage_policy": "external_manifest_only",
        },
    }


def _insert_material_item(conn, item: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO material_assets (
            material_id, library_id, source_group, file_name, file_ext, file_path, relative_path,
            file_size, duration_sec, sample_rate, channels, codec, material_role, material_profile,
            quality_state, route_hint, license_tag, license_status, retention_status, metadata_json,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            item["material_id"],
            item["library_id"],
            item["source_group"],
            item["file_name"],
            item["file_ext"],
            item["file_path"],
            item["relative_path"],
            item["file_size"],
            item["duration_sec"],
            item["sample_rate"],
            item["channels"],
            item["codec"],
            item["material_role"],
            item["material_profile"],
            item["quality_state"],
            item["route_hint"],
            item["license_tag"],
            item["license_status"],
            item["retention_status"],
            json.dumps(item["metadata"], ensure_ascii=False),
        ),
    )


def _read_libraries() -> list[dict]:
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT library_id, library_key, display_name, source_group, root_path, license_status,
                   license_tag, storage_policy, enabled, metadata_json, last_scanned_at, created_at, updated_at
            FROM material_libraries
            ORDER BY library_key
            """
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(row) for row in rows]


def _read_items(role: str = "", profile: str = "", retention: str = "active", limit: int = 100) -> list[dict]:
    init_db()
    clauses = []
    params: list[Any] = []
    if role:
        clauses.append("material_role = ?")
        params.append(role)
    if profile:
        clauses.append("material_profile = ?")
        params.append(profile)
    if retention:
        clauses.append("retention_status = ?")
        params.append(retention)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit or 100), 500)))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT material_id, library_id, source_group, file_name, file_ext, file_path, relative_path,
                   file_size, duration_sec, sample_rate, channels, codec, material_role, material_profile,
                   quality_state, route_hint, license_tag, license_status, retention_status, metadata_json,
                   created_at, updated_at
            FROM material_assets
            {where}
            ORDER BY updated_at DESC, file_name
            LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        conn.close()
    return [_material_row_to_dict(row) for row in rows]


def _summarize_items(items: list[dict], libraries: list[dict]) -> dict:
    active_items = [item for item in items if item.get("retention_status") == "active"]
    dry_vocals = [item for item in active_items if item.get("material_role") == "dry_vocal"]
    cover_sources = [item for item in active_items if item.get("material_role") == "cover_source"]
    separation = [
        item
        for item in active_items
        if item.get("material_profile") in {"separation_eval_candidate", "synthetic_separation_benchmark"}
    ]
    quarantined = [item for item in items if item.get("retention_status") == "quarantined"]
    total_duration = sum(float(item.get("duration_sec") or 0) for item in active_items)
    return {
        "library_count": len(libraries),
        "configured_library_count": sum(1 for library in libraries if library.get("root_path")),
        "existing_library_count": sum(1 for library in libraries if Path(library.get("root_path") or "").is_dir()),
        "item_count": len(items),
        "active_item_count": len(active_items),
        "dry_vocal_count": len(dry_vocals),
        "cover_source_count": len(cover_sources),
        "separation_benchmark_count": len(separation),
        "quarantined_count": len(quarantined),
        "total_duration_seconds": round(total_duration, 3),
        "total_duration_minutes": round(total_duration / 60, 2) if total_duration else 0,
    }


def _artifact_review_hygiene_item(item: dict) -> dict:
    quality_verdict = item.get("quality_verdict") or ""
    recommendation = "archive_candidate" if quality_verdict == "blocked_auto" else "keep_reviewable"
    return {
        "artifact_id": item.get("artifact_id") or "",
        "job_id": item.get("job_id") or "",
        "file_path": item.get("file_path") or item.get("download_url") or "",
        "file_size": item.get("file_size") or item.get("file_size_bytes") or 0,
        "quality_verdict": quality_verdict,
        "quality_flags": item.get("quality_flags") or [],
        "quality_reason": item.get("quality_reason") or "",
        "retention_recommendation": recommendation,
        "delete_allowed": False,
        "created_at": item.get("created_at") or "",
    }


def _artifact_hygiene_item(row) -> dict:
    metadata = _loads(row["metadata_json"])
    quality_verdict = metadata.get("quality_verdict") or metadata.get("quality", {}).get("verdict") or ""
    flags = metadata.get("quality_flags") or metadata.get("quality", {}).get("flags") or []
    if not quality_verdict:
        if int(row["file_size"] or 0) < 100_000:
            quality_verdict = "blocked_auto"
            flags = [*flags, "tiny_file"]
        else:
            quality_verdict = "unreviewed"
    recommendation = "archive_candidate" if quality_verdict == "blocked_auto" else "keep_reviewable"
    return {
        "artifact_id": row["artifact_id"],
        "job_id": row["job_id"],
        "file_path": row["file_path"],
        "file_size": row["file_size"],
        "quality_verdict": quality_verdict,
        "quality_flags": flags,
        "retention_recommendation": recommendation,
        "delete_allowed": False,
        "created_at": row["created_at"],
    }


def _model_hygiene_item(row) -> dict:
    text = " ".join(str(row[key] or "") for key in ("voice_model_id", "model_name", "source_job_id", "pth_path", "index_path"))
    protected = any(token in text.lower() for token in ("朱朱".lower(), "recovered", "stage47"))
    return {
        "voice_model_id": row["voice_model_id"],
        "model_name": row["model_name"],
        "source_job_id": row["source_job_id"],
        "status": row["status"],
        "protected": protected,
        "retention_recommendation": "keep_protected" if protected else "review",
    }


def _has_material_rows() -> bool:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM material_libraries").fetchone()
        return bool(row and row["count"])
    finally:
        conn.close()


def _iter_audio_files(directory: Path, *, max_files: int):
    count = 0
    try:
        iterator = directory.rglob("*")
        for path in iterator:
            if count >= max_files:
                break
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue
            count += 1
            yield path
    except OSError:
        return


def _split_env_paths(raw: str) -> list[str]:
    result = []
    for chunk in str(raw or "").replace("\n", ";").replace(",", ";").split(";"):
        value = chunk.strip().strip('"')
        if value:
            result.append(value)
    return result


def _row_to_dict(row) -> dict:
    payload = dict(row)
    payload["enabled"] = bool(payload.get("enabled"))
    payload["metadata"] = _loads(payload.pop("metadata_json", "{}"))
    payload["exists"] = Path(payload.get("root_path") or "").is_dir()
    return payload


def _material_row_to_dict(row) -> dict:
    try:
        from .lifecycle_service import enrich_material_asset
    except ImportError:
        from services.lifecycle_service import enrich_material_asset

    payload = dict(row)
    payload["metadata"] = _loads(payload.pop("metadata_json", "{}"))
    return enrich_material_asset(payload)


def _loads(raw: str) -> dict:
    try:
        payload = json.loads(raw or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha1(value.encode('utf-8', errors='ignore')).hexdigest()[:16]}"


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()
