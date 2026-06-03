from __future__ import annotations

from pathlib import Path

from backend.verify_stage58_material_quality import (
    DEFAULT_MANIFEST,
    load_manifest,
    summarize_manifest,
    validate_manifest,
)


def test_stage58_material_manifest_schema_and_gate():
    manifest = load_manifest(DEFAULT_MANIFEST)

    errors = validate_manifest(manifest)
    summary = summarize_manifest(manifest)

    assert errors == []
    assert summary["entry_count"] >= 1
    assert (
        summary["verified_usable_entry_count"] >= 1
        or manifest["blocking_flags"].get("no_verified_materials") is True
    )


def test_stage58_material_manifest_marks_bad_samples_without_deleting_them():
    manifest = load_manifest(DEFAULT_MANIFEST)
    by_id = {entry["id"]: entry for entry in manifest["entries"]}

    tiny_group = by_id["stage58_tiny_final_master_group"]
    uvr_group = by_id["stage58_latest_stage45r_uvr_stems_whistle_dj"]

    assert tiny_group["quarantine_recommended"] is True
    assert tiny_group["metrics"]["count"] >= 1
    assert "too_short" in tiny_group["quality_tags"]
    assert uvr_group["quarantine_recommended"] is True
    assert uvr_group["metrics"]["stage45r_noise_risk"] == "high"


def test_stage58_manifest_paths_stay_in_allowed_material_or_read_only_sources():
    manifest = load_manifest(DEFAULT_MANIFEST)
    allowed_prefixes = (
        "shared_data/",
        "D:/测试音乐/",
        "C:/Users/ASUS/Desktop/干声文件/",
    )

    for entry in manifest["entries"]:
        path = str(entry["path"]).replace("\\", "/")
        assert path.startswith(allowed_prefixes), path

    assert Path(DEFAULT_MANIFEST).as_posix().endswith("shared_data/materials/stage58/material_manifest.json")
