from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
import uuid
import wave
from pathlib import Path
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is expected in FeiShark, but keep dry-run safe.
    np = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT_RELATIVE = Path("shared_data") / "separation_eval" / "runs"
INPUT_ROOT_RELATIVE = Path("shared_data") / "separation_eval" / "input"
MAX_CANDIDATES = 5
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac"}
SONOVOX_DEMO_DATASET_ENV = "FEISHARK_SONOVOX_DEMO_DATASET_ROOT"
AUTHORIZED_DRY_VOCAL_ROOTS_ENV = "FEISHARK_AUTHORIZED_DRY_VOCAL_ROOTS"
LEGACY_TEST_MUSIC_OPT_IN_ENV = "FEISHARK_INCLUDE_LEGACY_TEST_MUSIC"
MAX_AUTHORIZED_SCAN_FILES = 200
MAX_EXCLUDED_PREVIEW = 20
FIXED_SOURCE_DIRS = [
    Path(r"D:\测试音乐"),
    Path(r"D:\测试音频"),
    Path(r"D:\音乐测试"),
    Path(r"D:\MusicTest"),
    Path(r"D:\TestMusic"),
]
SHALLOW_SCAN_KEYWORDS = ["测试", "音乐", "音频", "music", "audio", "test"]
RISKY_MIX_KEYWORDS = [
    "dj",
    "dj版",
    "remix",
    "bootleg",
    "成品",
    "混音",
    "母带",
    "master",
    "final",
    "release",
]
DRY_VOCAL_KEYWORDS = [
    "sonovox",
    "sonja",
    "dry",
    "vocal",
    "vocals",
    "lead",
    "bgv",
    "harmony",
    "harmonies",
    "adlib",
    "ad-libs",
    "vox",
    "人声",
    "干声",
]
BACKING_KEYWORDS = ["instrumental", "backing", "accompaniment", "伴奏"]


def discover_sources(project_root: str | Path | None = None, *, max_items: int = MAX_CANDIDATES) -> dict:
    root = Path(project_root) if project_root else PROJECT_ROOT
    material_roots = _build_material_roots(root)
    scanned_dirs = [item["path"] for item in material_roots if item["path"].is_dir()]
    fallback_used = any(item["source_group"] == "legacy_fallback" for item in material_roots)
    legacy_opt_in = _truthy_env(LEGACY_TEST_MUSIC_OPT_IN_ENV)

    discovered = _collect_audio_candidates(material_roots)
    candidates = [item for item in discovered if not item.get("excluded")]
    excluded_candidates = [item for item in discovered if item.get("excluded")]
    separation_eval_candidates = [item for item in candidates if item.get("separation_eval_allowed")]
    training_candidates = [item for item in candidates if item.get("training_candidate_allowed")]
    selected = sorted(
        candidates,
        key=lambda item: (
            0 if item.get("default_candidate") else 1,
            0 if _preferred_duration(item.get("duration_seconds")) else 1,
            item.get("duration_seconds") is None,
            str(item.get("path") or "").lower(),
        ),
    )[: max(1, min(int(max_items or MAX_CANDIDATES), MAX_CANDIDATES))]
    selected_separation = sorted(
        separation_eval_candidates,
        key=lambda item: (
            0 if item.get("default_candidate") else 1,
            0 if _preferred_duration(item.get("duration_seconds")) else 1,
            item.get("duration_seconds") is None,
            str(item.get("path") or "").lower(),
        ),
    )[: max(1, min(int(max_items or MAX_CANDIDATES), MAX_CANDIDATES))]

    return {
        "ok": True,
        "dry_run": True,
        "safe_rules": {
            "recursive_full_d_scan": False,
            "legacy_test_music_opt_in_env": LEGACY_TEST_MUSIC_OPT_IN_ENV,
            "legacy_test_music_included": legacy_opt_in,
            "fixed_dirs_first": [str(path) for path in FIXED_SOURCE_DIRS],
            "fallback": "D drive top-level keyword dirs only when legacy opt-in is enabled",
            "max_candidates": MAX_CANDIDATES,
            "max_authorized_scan_files": MAX_AUTHORIZED_SCAN_FILES,
            "extensions": sorted(SUPPORTED_AUDIO_EXTENSIONS),
        },
        "authorized_root_config": {
            "sonovox_env": SONOVOX_DEMO_DATASET_ENV,
            "sonovox_root": os.environ.get(SONOVOX_DEMO_DATASET_ENV, "").strip(),
            "authorized_dry_vocal_roots_env": AUTHORIZED_DRY_VOCAL_ROOTS_ENV,
            "authorized_dry_vocal_roots": _split_env_paths(os.environ.get(AUTHORIZED_DRY_VOCAL_ROOTS_ENV, "")),
            "legacy_test_music_opt_in_env": LEGACY_TEST_MUSIC_OPT_IN_ENV,
            "legacy_test_music_included": legacy_opt_in,
        },
        "material_libraries": _summarize_material_libraries(discovered, material_roots),
        "fallback_used": fallback_used,
        "scanned_dirs": [str(path) for path in scanned_dirs],
        "total_candidates": len(candidates),
        "separation_eval_total": len(separation_eval_candidates),
        "training_candidate_total": len(training_candidates),
        "excluded_total": len(excluded_candidates),
        "candidates": selected,
        "separation_eval_candidates": selected_separation,
        "excluded_candidates": excluded_candidates[:MAX_EXCLUDED_PREVIEW],
    }


def list_eval_runs(project_root: str | Path | None = None) -> dict:
    runs_root = _runs_root(project_root)
    items = []
    if runs_root.is_dir():
        for run_dir in sorted(runs_root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
            if not run_dir.is_dir():
                continue
            manifest = _read_json(run_dir / "run_manifest.json")
            items.append(
                {
                    "run_id": run_dir.name,
                    "path": str(run_dir),
                    "created_at": manifest.get("created_at") or "",
                    "executed": bool(manifest.get("executed")),
                    "source_count": int(manifest.get("source_count") or 0),
                    "status": manifest.get("status") or "unknown",
                }
            )
    return {"ok": True, "runs": items}


def get_eval_run(run_id: str, project_root: str | Path | None = None) -> dict | None:
    safe_run_id = _safe_name(run_id)
    if not safe_run_id:
        return None
    run_dir = _runs_root(project_root) / safe_run_id
    if not run_dir.is_dir():
        return None
    manifest = _read_json(run_dir / "run_manifest.json")
    manifest_changed = False
    reports = []
    items = []
    for index, report_path in enumerate(sorted(run_dir.glob("*/quality_report.json")), start=1):
        item_dir = report_path.parent
        report = _read_json(report_path)
        report = _ensure_report_contract(report, report_path)
        artifact_urls = build_artifact_urls(safe_run_id, index)
        report["artifact_urls"] = artifact_urls
        reports.append(report)
        items.append(
            {
                "item_index": index,
                "item_dir": str(item_dir),
                "artifact_urls": artifact_urls,
                "duration_mismatch": bool(report.get("duration_mismatch")),
                "duration_ratio": report.get("duration_ratio"),
                "duration_mismatch_risk": report.get("duration_mismatch_risk") or "low",
                "noise_risk": report.get("noise_risk") or "unknown",
            }
        )
        if isinstance(manifest.get("items"), list) and index <= len(manifest["items"]):
            manifest_item = manifest["items"][index - 1]
            if isinstance(manifest_item, dict):
                if manifest_item.get("report") != report:
                    manifest_item["report"] = report
                    manifest_changed = True
                if manifest_item.get("artifact_urls") != artifact_urls:
                    manifest_item["artifact_urls"] = artifact_urls
                    manifest_changed = True
                for key in (
                    "duration_mismatch",
                    "duration_ratio",
                    "duration_mismatch_risk",
                    "duration_mismatch_next_step",
                ):
                    if manifest_item.get(key) != report.get(key):
                        manifest_item[key] = report.get(key)
                        manifest_changed = True
    block_training = any(item["duration_mismatch_risk"] == "high" for item in items)
    if manifest.get("block_training") != block_training:
        manifest["block_training"] = block_training
        manifest_changed = True
    if manifest_changed:
        _write_json(run_dir / "run_manifest.json", manifest)
    return {
        "ok": True,
        "run_id": safe_run_id,
        "path": str(run_dir),
        "manifest": manifest,
        "items": items,
        "reports": reports,
        "block_training": block_training,
    }


def build_artifact_urls(run_id: str, item_index: int) -> dict:
    base = f"/api/separation/eval/runs/{_safe_name(run_id)}/items/{int(item_index)}/artifacts"
    return {
        "original": f"{base}/original",
        "vocal": f"{base}/vocal",
        "instrumental": f"{base}/instrumental",
    }


def resolve_eval_artifact(
    run_id: str,
    item_index: int,
    artifact_key: str,
    project_root: str | Path | None = None,
) -> Path | None:
    safe_run_id = _safe_name(run_id)
    artifact_map = {
        "original": "original_excerpt.wav",
        "original_excerpt": "original_excerpt.wav",
        "vocal": "vocal.wav",
        "instrumental": "instrumental.wav",
    }
    filename = artifact_map.get(str(artifact_key or "").strip().lower())
    if not safe_run_id or not filename:
        return None

    runs_root = _runs_root(project_root).resolve()
    run_dir = (runs_root / safe_run_id).resolve()
    if not _is_within(run_dir, runs_root) or not run_dir.is_dir():
        return None

    try:
        safe_index = int(item_index)
    except (TypeError, ValueError):
        return None
    if safe_index < 1:
        return None

    item_dirs = sorted(path for path in run_dir.iterdir() if path.is_dir())
    if safe_index > len(item_dirs):
        return None
    artifact_path = (item_dirs[safe_index - 1] / filename).resolve()
    if not _is_within(artifact_path, runs_root) or not artifact_path.is_file():
        return None
    return artifact_path


def audit_environment() -> dict:
    ffmpeg_path = _find_tool("ffmpeg")
    ffprobe_path = _find_tool("ffprobe")
    try:
        from .. import vocal_separator
    except ImportError:
        import vocal_separator

    uvr_checks = [
        {"check": "audio_pipeline_dir", "ok": Path(vocal_separator.AUDIO_PIPELINE_DIR).is_dir(), "value": vocal_separator.AUDIO_PIPELINE_DIR},
        {"check": "audio_pipeline_python", "ok": Path(vocal_separator.AUDIO_PIPELINE_VENV).is_file(), "value": vocal_separator.AUDIO_PIPELINE_VENV},
        {"check": "uvr5_model", "ok": Path(vocal_separator.UVR5_MODEL_PATH).is_file(), "value": vocal_separator.UVR5_MODEL_PATH},
    ]
    return {
        "ffmpeg": {"ok": bool(ffmpeg_path), "path": ffmpeg_path},
        "ffprobe": {"ok": bool(ffprobe_path), "path": ffprobe_path},
        "uvr": {
            "ok": all(item["ok"] for item in uvr_checks),
            "checks": uvr_checks,
        },
    }


def execute_separation_audit(
    *,
    project_root: str | Path | None = None,
    limit: int = 3,
    clip_seconds: int = 45,
) -> dict:
    safe_limit = max(1, min(int(limit or 3), 3))
    safe_clip_seconds = max(1, min(int(clip_seconds or 45), 60))
    env = audit_environment()
    source_discovery = discover_sources(project_root, max_items=max(MAX_CANDIDATES, safe_limit))
    sources = source_discovery.get("separation_eval_candidates", [])[:safe_limit]
    run_id = time.strftime("stage45r_%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_dir = _runs_root(project_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "executed": True,
        "limit": safe_limit,
        "clip_seconds": safe_clip_seconds,
        "source_count": len(sources),
        "status": "running",
        "environment": env,
        "source_discovery": {
            "scanned_dirs": source_discovery.get("scanned_dirs", []),
            "material_libraries": source_discovery.get("material_libraries", []),
            "total_candidates": source_discovery.get("total_candidates", 0),
            "separation_eval_total": source_discovery.get("separation_eval_total", 0),
            "training_candidate_total": source_discovery.get("training_candidate_total", 0),
            "excluded_total": source_discovery.get("excluded_total", 0),
        },
        "items": [],
        "train_py_started": False,
        "rvc_inference_called": False,
    }
    _write_json(run_dir / "run_manifest.json", manifest)

    if not sources:
        manifest["status"] = "blocked"
        manifest["blockers"] = [
            "no separation_eval_allowed sources; configure project input or opt in clean legacy test music",
        ]
        manifest["source_count"] = 0
        _write_json(run_dir / "run_manifest.json", manifest)
        return manifest

    if not env["ffmpeg"]["ok"] or not env["uvr"]["ok"]:
        manifest["status"] = "blocked"
        manifest["blockers"] = _environment_blockers(env)
        _write_json(run_dir / "run_manifest.json", manifest)
        return manifest

    for index, source in enumerate(sources, start=1):
        item_dir = run_dir / f"{index:02d}_{_safe_name(Path(source['path']).stem)[:40]}"
        item_dir.mkdir(parents=True, exist_ok=True)
        item_result = _execute_one_source(source, item_dir, safe_clip_seconds)
        manifest["items"].append(item_result)
        _write_json(run_dir / "run_manifest.json", manifest)

    manifest["status"] = "completed" if all(item.get("ok") for item in manifest["items"]) else "partial"
    _write_json(run_dir / "run_manifest.json", manifest)
    return manifest


def build_quality_report(
    *,
    source_path: str,
    item_dir: str | Path,
    products: dict[str, str],
    error: str = "",
) -> dict:
    metrics = {}
    for label, path in products.items():
        metrics[label] = analyze_wav_metrics(path) if path and Path(path).is_file() else {"ok": False, "error": "missing"}
    duration_contract = compute_duration_contract(metrics)
    risk = classify_noise_risk(metrics, error=error, duration_contract=duration_contract)
    report = {
        "ok": not bool(error),
        "source_path": source_path,
        "products": products,
        "metrics": metrics,
        "noise_risk": risk["noise_risk"],
        "suspected_causes": risk["suspected_causes"],
        "next_step": risk["next_step"],
        "error": error,
        **duration_contract,
    }
    _write_json(Path(item_dir) / "quality_report.json", report)
    return report


def analyze_wav_metrics(path: str | Path) -> dict:
    wav_path = Path(path)
    try:
        with wave.open(str(wav_path), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            frames = wf.getnframes()
            raw = wf.readframes(frames)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    duration = frames / sample_rate if sample_rate else 0.0
    if not raw or not sample_rate or np is None:
        return {
            "ok": bool(raw and sample_rate),
            "duration_seconds": round(duration, 3),
            "sample_rate": sample_rate,
            "channels": channels,
            "peak_db": None,
            "rms_db": None,
            "clipping_risk": "unknown",
            "silence_ratio": None,
            "high_freq_energy_ratio": None,
            "zero_crossing_rate": None,
            "dc_offset_estimate": None,
        }

    samples = _pcm_to_float(raw, sample_width)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    if samples.size == 0:
        peak = 0.0
        rms = 0.0
    else:
        peak = float(np.max(np.abs(samples)))
        rms = float(np.sqrt(np.mean(np.square(samples))))

    peak_db = _linear_to_db(peak)
    rms_db = _linear_to_db(rms)
    silence_ratio = float(np.mean(np.abs(samples) < 0.001)) if samples.size else 1.0
    zero_crossing_rate = _zero_crossing_rate(samples)
    high_ratio = _high_freq_energy_ratio(samples, sample_rate)
    dc_offset = float(np.mean(samples)) if samples.size else 0.0

    return {
        "ok": True,
        "duration_seconds": round(duration, 3),
        "sample_rate": sample_rate,
        "channels": channels,
        "peak_db": round(peak_db, 3),
        "rms_db": round(rms_db, 3),
        "clipping_risk": "high" if peak >= 0.99 else "medium" if peak >= 0.95 else "low",
        "silence_ratio": round(silence_ratio, 6),
        "high_freq_energy_ratio": round(high_ratio, 6),
        "zero_crossing_rate": round(zero_crossing_rate, 6),
        "dc_offset_estimate": round(dc_offset, 8),
    }


def compute_duration_contract(metrics: dict) -> dict:
    original = metrics.get("original_excerpt") or {}
    original_duration = float(original.get("duration_seconds") or 0)
    stem_durations = [
        float((metrics.get(label) or {}).get("duration_seconds") or 0)
        for label in ("vocal", "instrumental")
    ]
    stem_durations = [value for value in stem_durations if value > 0]
    if original_duration <= 0 or not stem_durations:
        return {
            "duration_mismatch": False,
            "duration_ratio": None,
            "duration_mismatch_risk": "unknown",
            "duration_mismatch_next_step": "duration metrics incomplete",
        }

    shortest_ratio = min(stem_durations) / original_duration
    longest_ratio = max(stem_durations) / original_duration
    mismatch = any(abs(value - original_duration) / original_duration > 0.05 for value in stem_durations)
    risk = "high" if mismatch else "low"
    return {
        "duration_mismatch": bool(mismatch),
        "duration_ratio": round(shortest_ratio, 4),
        "duration_ratio_max": round(longest_ratio, 4),
        "duration_mismatch_risk": risk,
        "duration_mismatch_next_step": (
            "inspect UVR runner output trimming before training"
            if mismatch
            else "duration contract ok"
        ),
    }


def classify_noise_risk(metrics: dict, *, error: str = "", duration_contract: dict | None = None) -> dict:
    causes = []
    high_count = 0
    medium_count = 0

    if error:
        return {
            "noise_risk": "high",
            "suspected_causes": ["UVR execution failed or output is incomplete."],
            "next_step": "Check AudioPipeline/UVR logs before running cover or training.",
        }

    duration_contract = duration_contract or compute_duration_contract(metrics)
    if duration_contract.get("duration_mismatch_risk") == "high":
        high_count += 1
        causes.append(
            "duration mismatch: vocal/instrumental duration differs from original excerpt by more than 5%"
        )

    for label, item in metrics.items():
        if not item.get("ok"):
            high_count += 1
            causes.append(f"{label}: missing or unreadable wav")
            continue
        if item.get("clipping_risk") == "high":
            high_count += 1
            causes.append(f"{label}: clipping risk is high")
        elif item.get("clipping_risk") == "medium":
            medium_count += 1
            causes.append(f"{label}: peak is close to clipping")
        if float(item.get("high_freq_energy_ratio") or 0) > 0.18:
            medium_count += 1
            causes.append(f"{label}: high frequency energy ratio is elevated")
        if abs(float(item.get("dc_offset_estimate") or 0)) > 0.02:
            medium_count += 1
            causes.append(f"{label}: possible DC offset")
        if float(item.get("silence_ratio") or 0) > 0.85:
            medium_count += 1
            causes.append(f"{label}: mostly silence")

    if high_count:
        risk = "high"
        next_step = "Do not start training; inspect UVR model/config and output trimming before cover or training."
    elif medium_count:
        risk = "medium"
        next_step = "A/B listen to original, vocal, and instrumental excerpts; tune UVR config before training if noise is audible."
    else:
        risk = "low"
        next_step = "Separation metrics look stable; proceed with product-side A/B listening before resuming training."

    return {
        "noise_risk": risk,
        "suspected_causes": causes or ["No obvious clipping, silence, DC offset, or high-frequency noise metric was detected."],
        "next_step": next_step,
    }


def _ensure_report_contract(report: dict, report_path: Path | None = None) -> dict:
    if not isinstance(report, dict):
        report = {}
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    duration_contract = compute_duration_contract(metrics)
    changed = False
    for key, value in duration_contract.items():
        if report.get(key) != value:
            report[key] = value
            changed = True

    if duration_contract.get("duration_mismatch_risk") == "high":
        risk = classify_noise_risk(metrics, error=report.get("error") or "", duration_contract=duration_contract)
        for key in ("noise_risk", "suspected_causes", "next_step"):
            if report.get(key) != risk[key]:
                report[key] = risk[key]
                changed = True

    if changed and report_path:
        _write_json(report_path, report)
    return report


def _execute_one_source(source: dict, item_dir: Path, clip_seconds: int) -> dict:
    source_path = source["path"]
    excerpt_path = item_dir / "original_excerpt.wav"
    products = {
        "original_excerpt": str(excerpt_path),
        "vocal": str(item_dir / "vocal.wav"),
        "instrumental": str(item_dir / "instrumental.wav"),
    }
    try:
        _clip_audio(source_path, excerpt_path, clip_seconds)
        task_id = f"stage45r_eval_{uuid.uuid4().hex[:12]}"
        _create_eval_task(task_id, str(excerpt_path))

        try:
            from .. import vocal_separator
        except ImportError:
            import vocal_separator

        split_result = vocal_separator.split_audio(task_id, str(excerpt_path))
        if not split_result.get("success"):
            error = str(split_result.get("error") or "UVR split failed")
            report = build_quality_report(source_path=source_path, item_dir=item_dir, products=products, error=error)
            return {"ok": False, "source": source, "item_dir": str(item_dir), "report": report, "error": error}

        shutil.copy2(split_result["vocal"], products["vocal"])
        shutil.copy2(split_result["instrumental"], products["instrumental"])
        report = build_quality_report(source_path=source_path, item_dir=item_dir, products=products)
        return {
            "ok": True,
            "source": source,
            "item_dir": str(item_dir),
            "products": products,
            "report": report,
        }
    except Exception as exc:
        report = build_quality_report(source_path=source_path, item_dir=item_dir, products=products, error=str(exc))
        return {"ok": False, "source": source, "item_dir": str(item_dir), "report": report, "error": str(exc)}


def _build_material_roots(root: Path) -> list[dict[str, Any]]:
    material_roots: list[dict[str, Any]] = []

    sonovox_root = os.environ.get(SONOVOX_DEMO_DATASET_ENV, "").strip()
    if sonovox_root:
        material_roots.append(
            _material_root_spec(
                Path(sonovox_root),
                source_group="sonovox_demo",
                library_key="sonovox_ai_demo_dataset",
                license_tag="user_provided_local_sonovox_demo",
                license_status="user_provided_local",
                recursive=True,
            )
        )

    for index, configured_root in enumerate(_split_env_paths(os.environ.get(AUTHORIZED_DRY_VOCAL_ROOTS_ENV, "")), start=1):
        material_roots.append(
            _material_root_spec(
                Path(configured_root),
                source_group="authorized_dry_vocal",
                library_key=f"authorized_dry_vocal_{index}",
                license_tag="user_provided_local_authorized_dry_vocal",
                license_status="user_provided_local",
                recursive=True,
            )
        )

    material_roots.append(
        _material_root_spec(
            root / INPUT_ROOT_RELATIVE,
            source_group="project_input",
            library_key="project_separation_eval_input",
            license_tag="user_provided_project_input",
            license_status="user_provided_local",
            recursive=True,
        )
    )

    if _truthy_env(LEGACY_TEST_MUSIC_OPT_IN_ENV):
        for path in FIXED_SOURCE_DIRS:
            material_roots.append(
                _material_root_spec(
                    path,
                    source_group="legacy_test_music",
                    library_key="legacy_test_music",
                    license_tag="legacy_local_test_music_opt_in",
                    license_status="local_opt_in_review_required",
                    recursive=False,
                )
            )
        if not any(path.is_dir() for path in FIXED_SOURCE_DIRS):
            for path in _shallow_d_drive_keyword_dirs():
                material_roots.append(
                    _material_root_spec(
                        path,
                        source_group="legacy_fallback",
                        library_key="legacy_d_drive_keyword_fallback",
                        license_tag="legacy_local_test_music_opt_in",
                        license_status="local_opt_in_review_required",
                        recursive=False,
                    )
                )

    return material_roots


def _material_root_spec(
    path: Path,
    *,
    source_group: str,
    library_key: str,
    license_tag: str,
    license_status: str,
    recursive: bool,
) -> dict[str, Any]:
    return {
        "path": path,
        "source_group": source_group,
        "library_key": library_key,
        "license_tag": license_tag,
        "license_status": license_status,
        "recursive": recursive,
    }


def _collect_audio_candidates(material_roots: list[dict[str, Any]]) -> list[dict]:
    items = []
    seen = set()
    for spec in material_roots:
        directory = spec["path"]
        if not directory.is_dir():
            continue
        files_seen_in_root = 0
        for path in _iter_audio_files(directory, recursive=bool(spec.get("recursive"))):
            if files_seen_in_root >= MAX_AUTHORIZED_SCAN_FILES:
                break
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            files_seen_in_root += 1
            try:
                stat = path.stat()
            except OSError:
                continue
            duration = _probe_duration(path)
            classification = _classify_material(path, spec, duration)
            items.append(
                {
                    "path": str(path),
                    "file_name": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": stat.st_size,
                    "duration_seconds": duration,
                    "preferred": _preferred_duration(duration),
                    **classification,
                }
            )
    return items


def _iter_audio_files(directory: Path, *, recursive: bool):
    count = 0
    try:
        iterator = directory.rglob("*") if recursive else directory.iterdir()
        for path in iterator:
            if count >= MAX_AUTHORIZED_SCAN_FILES:
                break
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue
            count += 1
            yield path
    except OSError:
        return


def _classify_material(path: Path, spec: dict[str, Any], duration: float | None) -> dict[str, Any]:
    source_group = str(spec.get("source_group") or "unknown")
    text = " ".join([path.name, *[parent.name for parent in path.parents[:3]]]).lower()
    risk_flags = [keyword for keyword in RISKY_MIX_KEYWORDS if keyword.lower() in text]
    has_dry_hint = source_group in {"sonovox_demo", "authorized_dry_vocal"} or any(
        keyword.lower() in text for keyword in DRY_VOCAL_KEYWORDS
    )
    has_backing_hint = any(keyword.lower() in text for keyword in BACKING_KEYWORDS)

    if any(flag.startswith("dj") for flag in risk_flags):
        material_role = "dj_mix"
    elif risk_flags:
        material_role = "finished_mix"
    elif has_backing_hint:
        material_role = "backing"
    elif has_dry_hint:
        material_role = "dry_vocal"
    elif source_group in {"legacy_test_music", "legacy_fallback", "project_input"}:
        material_role = "clean_song"
    else:
        material_role = "unknown"

    risky = bool(risk_flags)
    separation_eval_allowed = (
        not risky
        and source_group in {"project_input", "legacy_test_music", "legacy_fallback"}
        and material_role in {"clean_song", "finished_mix", "unknown"}
    )
    training_candidate_allowed = (
        not risky
        and material_role == "dry_vocal"
        and source_group in {"sonovox_demo", "authorized_dry_vocal", "project_input"}
    )

    if risky:
        material_profile = "unsupported_risky_mix"
        training_route_hint = "DJ/remix/master/final/成品混音只允许人工压力测试，不进入默认分离或训练队列。"
    elif training_candidate_allowed:
        material_profile = "clean_dry_vocal"
        training_route_hint = "可作为 RVC/UVC/VST 干声训练或调音基准；不要直接跑 UVR 分离。"
    elif has_backing_hint:
        material_profile = "backing_reference_only"
        training_route_hint = "伴奏/底轨只做试听或混音参照，不进入干声训练。"
    elif separation_eval_allowed:
        material_profile = "separation_eval_candidate"
        training_route_hint = "可用于 UVR 短片段分离质检；不直接进入训练。"
    else:
        material_profile = "needs_manual_review"
        training_route_hint = "素材用途不明确，需要人工确认后再进入分离或训练流程。"

    return {
        "source_group": source_group,
        "library_key": spec.get("library_key") or source_group,
        "license_tag": spec.get("license_tag") or "unknown",
        "license_status": spec.get("license_status") or "unknown",
        "material_role": material_role,
        "material_profile": material_profile,
        "training_route_hint": training_route_hint,
        "separation_eval_allowed": separation_eval_allowed,
        "training_candidate_allowed": training_candidate_allowed,
        "risk_flags": risk_flags,
        "default_candidate": separation_eval_allowed and _preferred_duration(duration),
        "excluded": risky,
    }


def _summarize_material_libraries(items: list[dict], material_roots: list[dict[str, Any]]) -> list[dict]:
    summaries = []
    for spec in material_roots:
        root_items = [item for item in items if item.get("library_key") == spec.get("library_key")]
        summaries.append(
            {
                "library_key": spec.get("library_key"),
                "source_group": spec.get("source_group"),
                "root": str(spec.get("path")),
                "configured": True,
                "exists": spec["path"].is_dir(),
                "recursive": bool(spec.get("recursive")),
                "license_tag": spec.get("license_tag"),
                "license_status": spec.get("license_status"),
                "file_count": len(root_items),
                "separation_eval_count": sum(1 for item in root_items if item.get("separation_eval_allowed")),
                "training_candidate_count": sum(1 for item in root_items if item.get("training_candidate_allowed")),
                "excluded_count": sum(1 for item in root_items if item.get("excluded")),
            }
        )
    return summaries


def _split_env_paths(raw: str) -> list[str]:
    result = []
    for chunk in str(raw or "").replace("\n", ";").replace(",", ";").split(";"):
        value = chunk.strip().strip('"')
        if value:
            result.append(value)
    return result


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _shallow_d_drive_keyword_dirs() -> list[Path]:
    d_root = Path(r"D:\\")
    if not d_root.is_dir():
        return []
    result = []
    try:
        children = list(d_root.iterdir())
    except OSError:
        return []
    for child in children:
        if not child.is_dir():
            continue
        lowered = child.name.lower()
        if any(keyword.lower() in lowered for keyword in SHALLOW_SCAN_KEYWORDS):
            result.append(child)
    return result


def _probe_duration(path: Path) -> float | None:
    ffprobe = _find_tool("ffprobe")
    if not ffprobe:
        return None
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    try:
        return round(float(completed.stdout.strip()), 3)
    except ValueError:
        return None


def _clip_audio(source_path: str, output_path: Path, clip_seconds: int) -> None:
    ffmpeg = _find_tool("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not available")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-i",
        source_path,
        "-t",
        str(clip_seconds),
        "-vn",
        "-ar",
        "44100",
        "-ac",
        "2",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(30, clip_seconds + 30),
    )
    if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg clip failed")[:1000])


def _create_eval_task(task_id: str, excerpt_path: str) -> None:
    try:
        from ..db import get_connection, init_db
    except ImportError:
        from db import get_connection, init_db

    init_db()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO tasks (task_id, task_type, input_file, compute_ready, status, error_log)
            VALUES (?, 'separation_eval', ?, 0, 'pending', '')
            """,
            (task_id, excerpt_path),
        )
        conn.commit()
    finally:
        conn.close()


def _pcm_to_float(raw: bytes, sample_width: int):
    if sample_width == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        return (data - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sample_width == 3:
        bytes_array = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        signed = (
            bytes_array[:, 0].astype(np.int32)
            | (bytes_array[:, 1].astype(np.int32) << 8)
            | (bytes_array[:, 2].astype(np.int32) << 16)
        )
        signed = np.where(signed & 0x800000, signed - 0x1000000, signed)
        return signed.astype(np.float32) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    raise ValueError(f"unsupported sample width: {sample_width}")


def _zero_crossing_rate(samples) -> float:
    if samples.size < 2:
        return 0.0
    signs = np.signbit(samples)
    return float(np.mean(signs[1:] != signs[:-1]))


def _high_freq_energy_ratio(samples, sample_rate: int) -> float:
    if samples.size < 64 or sample_rate <= 0:
        return 0.0
    max_samples = min(samples.size, sample_rate * 30)
    windowed = samples[:max_samples] * np.hanning(max_samples)
    spectrum = np.fft.rfft(windowed)
    power = np.abs(spectrum) ** 2
    total = float(np.sum(power))
    if total <= 0:
        return 0.0
    freqs = np.fft.rfftfreq(max_samples, d=1.0 / sample_rate)
    high = float(np.sum(power[freqs >= 10000]))
    return high / total


def _linear_to_db(value: float) -> float:
    if value <= 0:
        return -120.0
    return 20.0 * math.log10(value)


def _preferred_duration(duration: float | None) -> bool:
    return duration is not None and duration >= 30 and duration <= 20 * 60


def _find_tool(name: str) -> str:
    configured = os.environ.get(f"FEISHARK_{name.upper()}_PATH", "").strip()
    if configured and Path(configured).is_file():
        return configured
    return shutil.which(name) or ""


def _environment_blockers(env: dict) -> list[str]:
    blockers = []
    if not env["ffmpeg"]["ok"]:
        blockers.append("ffmpeg missing")
    for item in env["uvr"]["checks"]:
        if not item["ok"]:
            blockers.append(f"{item['check']} missing")
    return blockers


def _runs_root(project_root: str | Path | None = None) -> Path:
    root = Path(project_root) if project_root else PROJECT_ROOT
    return root / RUNS_ROOT_RELATIVE


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_name(value: str) -> str:
    allowed = []
    for char in str(value or ""):
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed).strip("_")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
