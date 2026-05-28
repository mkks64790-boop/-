from __future__ import annotations

import json
import re
from typing import Any


_SMOKE_NAME_PATTERN = re.compile(r"^stage\d+_(single|multi)_(smoke|probe)", re.IGNORECASE)


def _is_explicit_smoke_metadata(metadata: dict) -> bool:
    if bool(metadata.get("smoke")):
        return True
    return str(metadata.get("test_scope") or "").strip().lower() in {"smoke", "probe", "verify", "self_check"}


def parse_metadata(raw: Any) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def is_smoke_name(value: str) -> bool:
    return bool(_SMOKE_NAME_PATTERN.match((value or "").strip()))


def is_smoke_job_record(row: dict | None) -> bool:
    if not row:
        return False
    metadata = parse_metadata(row.get("metadata_json"))
    if _is_explicit_smoke_metadata(metadata):
        return True

    if is_smoke_name(row.get("voice_name") or ""):
        return True

    original_filename = str(metadata.get("original_filename") or "").strip().lower()
    file_size = int(metadata.get("file_size") or 0)
    if original_filename == "suno_test.wav" and file_size == 441044:
        return True

    return False


def is_smoke_model_record(row: dict | None) -> bool:
    if not row:
        return False
    metadata = parse_metadata(row.get("metadata_json"))
    if _is_explicit_smoke_metadata(metadata):
        return True
    return is_smoke_name(row.get("model_name") or "")


def is_smoke_dataset_record(row: dict | None, job_row: dict | None = None) -> bool:
    if not row:
        return False
    metadata = parse_metadata(row.get("metadata_json"))
    if _is_explicit_smoke_metadata(metadata):
        return True
    if is_smoke_name(row.get("dataset_name") or ""):
        return True
    return is_smoke_job_record(job_row)
