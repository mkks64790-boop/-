from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "shared_data" / "materials" / "stage58" / "material_manifest.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "generated_at",
    "stage",
    "entries",
    "blocking_flags",
}
REQUIRED_ENTRY_KEYS = {
    "id",
    "path",
    "source",
    "category",
    "intended_uses",
    "suitability",
    "quality_tags",
    "metrics",
    "quarantine_recommended",
    "reason",
}
SUITABILITY_KEYS = {
    "training",
    "separation",
    "cover",
    "listening_acceptance",
}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_manifest(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing_top = sorted(REQUIRED_TOP_LEVEL_KEYS - set(data))
    if missing_top:
        errors.append(f"missing top-level keys: {', '.join(missing_top)}")
    if not str(data.get("schema_version", "")).startswith("stage58.material_quality."):
        errors.append("schema_version must start with stage58.material_quality.")

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry {index} must be an object")
            continue

        entry_id = str(entry.get("id", f"#{index}"))
        if entry_id in seen_ids:
            errors.append(f"duplicate entry id: {entry_id}")
        seen_ids.add(entry_id)

        missing_entry = sorted(REQUIRED_ENTRY_KEYS - set(entry))
        if missing_entry:
            errors.append(f"{entry_id}: missing keys: {', '.join(missing_entry)}")

        suitability = entry.get("suitability")
        if not isinstance(suitability, dict):
            errors.append(f"{entry_id}: suitability must be an object")
        else:
            missing_suitability = sorted(SUITABILITY_KEYS - set(suitability))
            if missing_suitability:
                errors.append(f"{entry_id}: missing suitability keys: {', '.join(missing_suitability)}")
            for key in SUITABILITY_KEYS:
                if key in suitability and not isinstance(suitability[key], bool):
                    errors.append(f"{entry_id}: suitability.{key} must be boolean")

        metrics = entry.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{entry_id}: metrics must be an object")
        elif not any(key in metrics for key in ("duration_seconds", "representative_duration_seconds", "count")):
            errors.append(f"{entry_id}: metrics must include duration_seconds, representative_duration_seconds, or count")

        if not isinstance(entry.get("quality_tags"), list):
            errors.append(f"{entry_id}: quality_tags must be a list")
        if not isinstance(entry.get("intended_uses"), list):
            errors.append(f"{entry_id}: intended_uses must be a list")
        if not isinstance(entry.get("quarantine_recommended"), bool):
            errors.append(f"{entry_id}: quarantine_recommended must be boolean")

    return errors


def summarize_manifest(data: dict[str, Any]) -> dict[str, Any]:
    entries = data.get("entries") or []
    categories = Counter(str(entry.get("category", "unknown")) for entry in entries)
    tags = Counter(tag for entry in entries for tag in entry.get("quality_tags", []))
    suitability_counts = {
        key: sum(1 for entry in entries if bool((entry.get("suitability") or {}).get(key)))
        for key in sorted(SUITABILITY_KEYS)
    }
    quarantine_entries = [
        entry.get("id")
        for entry in entries
        if bool(entry.get("quarantine_recommended"))
    ]
    verified_entries = [
        entry.get("id")
        for entry in entries
        if "verified_audio_metrics" in set(entry.get("quality_tags") or [])
        and not bool(entry.get("quarantine_recommended"))
        and any(bool((entry.get("suitability") or {}).get(key)) for key in SUITABILITY_KEYS)
    ]
    return {
        "stage": data.get("stage"),
        "schema_version": data.get("schema_version"),
        "entry_count": len(entries),
        "category_counts": dict(categories),
        "suitability_counts": suitability_counts,
        "top_quality_tags": dict(tags.most_common(20)),
        "quarantine_recommended_count": len(quarantine_entries),
        "quarantine_recommended_ids": quarantine_entries,
        "verified_usable_entry_count": len(verified_entries),
        "verified_usable_ids": verified_entries,
        "blocking_flags": data.get("blocking_flags") or {},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage58 material quality manifest verifier.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary only.")
    args = parser.parse_args(argv)

    try:
        data = load_manifest(args.manifest)
    except FileNotFoundError:
        print(f"STAGE58_MATERIAL_QUALITY FAIL manifest missing: {args.manifest}")
        return 1

    errors = validate_manifest(data)
    summary = summarize_manifest(data)

    if args.json:
        print(json.dumps({"errors": errors, "summary": summary}, ensure_ascii=False, indent=2))
    else:
        print("STAGE58_MATERIAL_QUALITY")
        print(f"manifest={args.manifest}")
        print(f"entries={summary['entry_count']}")
        print(f"verified_usable={summary['verified_usable_entry_count']}")
        print(f"quarantine_recommended={summary['quarantine_recommended_count']}")
        print("categories=" + json.dumps(summary["category_counts"], ensure_ascii=False, sort_keys=True))
        print("suitability=" + json.dumps(summary["suitability_counts"], ensure_ascii=False, sort_keys=True))
        if errors:
            print("errors=" + json.dumps(errors, ensure_ascii=False))

    no_verified_materials = bool((data.get("blocking_flags") or {}).get("no_verified_materials"))
    if errors:
        print("STAGE58_MATERIAL_QUALITY FAIL")
        return 1
    if summary["verified_usable_entry_count"] < 1 and not no_verified_materials:
        print("STAGE58_MATERIAL_QUALITY FAIL no verified usable entry and no no_verified_materials block")
        return 1

    print("STAGE58_MATERIAL_QUALITY PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
