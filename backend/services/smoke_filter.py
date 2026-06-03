from __future__ import annotations

import json
import re
from typing import Any


_SMOKE_PREFIX_PATTERN = re.compile(r"^smoke[_-]", re.IGNORECASE)
_TMP_TEST_PREFIX_PATTERN = re.compile(r"^tmp[_-]", re.IGNORECASE)
_TEST_PREFIX_PATTERN = re.compile(r"^test[_-]", re.IGNORECASE)
_TRAIN_STAGE_PATTERN = re.compile(r"^train[_-]stage\d+", re.IGNORECASE)
_LEGACY_SMOKE_NAME_PATTERN = re.compile(r"^stage\d+_(single|multi)_(smoke|probe)", re.IGNORECASE)
_STAGE_TEST_NAME_PATTERN = re.compile(
    r"^stage\d+.*(?:smoke|probe|test|playwright|self[_-]?check|separation[_-]?eval|eval)",
    re.IGNORECASE,
)
_STAGE_PREFIX_PATTERN = re.compile(r"^stage\d+(?:[_-]|$)", re.IGNORECASE)
_REAL_STAGE_NAME_PATTERN = re.compile(r"^stage(?:47|56).*(?:real|actual|acceptance|closure|product)", re.IGNORECASE)
_TEST_SCOPE_VALUES = {
    "smoke",
    "probe",
    "verify",
    "self_check",
    "self-check",
    "playwright",
    "api_test",
    "test",
    "stage_test",
    "separation_eval",
    "separation-eval",
}
_TEST_MARKER_PATTERN = re.compile(
    r"(?:^|[_\-/\s])(?:smoke|probe|playwright|self[_-]?check|api[_-]?test|stage\d+[_-]?(?:test|smoke|probe)|separation[_-]?eval)(?:$|[_\-/\s])",
    re.IGNORECASE,
)


def _is_explicit_smoke_metadata(metadata: dict) -> bool:
    if bool(metadata.get("smoke")):
        return True
    return str(metadata.get("test_scope") or "").strip().lower() in {"smoke", "probe", "verify", "self_check"}


def _explicit_test_metadata_reason(metadata: dict) -> str:
    if bool(metadata.get("smoke")):
        return "metadata.smoke"
    if bool(metadata.get("test_data")):
        return "metadata.test_data"
    if bool(metadata.get("playwright")):
        return "metadata.playwright"
    if bool(metadata.get("self_check")):
        return "metadata.self_check"

    test_scope = str(metadata.get("test_scope") or "").strip().lower()
    if test_scope in _TEST_SCOPE_VALUES:
        return "metadata.test_scope"

    for key in ("source", "generated_by", "runner", "suite", "origin"):
        value = str(metadata.get(key) or "").strip()
        if value and _TEST_MARKER_PATTERN.search(value):
            return f"metadata.{key}"
    return ""


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
    return bool(_LEGACY_SMOKE_NAME_PATTERN.match((value or "").strip()))


def explain_test_data_name_reason(
    value: str,
    *,
    protect_real_stage: bool = True,
    allow_stage_prefix: bool = True,
) -> str:
    name = (value or "").strip()
    if not name:
        return ""
    lowered = name.lower()
    if any(marker in lowered for marker in ("smoke", "playwright", "self_check", "self-check", "api_test", "separation_eval")):
        return "name.test_marker"
    if _SMOKE_PREFIX_PATTERN.match(name):
        return "name.smoke_prefix"
    if _TMP_TEST_PREFIX_PATTERN.match(name):
        return "name.tmp_prefix"
    if _TEST_PREFIX_PATTERN.match(name):
        return "name.test_prefix"
    if _TRAIN_STAGE_PATTERN.match(name):
        return "name.train_stage_prefix"
    if protect_real_stage and _REAL_STAGE_NAME_PATTERN.match(name):
        return ""
    if _LEGACY_SMOKE_NAME_PATTERN.match(name):
        return "name.stage_smoke"
    if _STAGE_TEST_NAME_PATTERN.match(name):
        return "name.stage_test"
    if allow_stage_prefix and _STAGE_PREFIX_PATTERN.match(name):
        return "name.stage_prefix"
    if _TEST_MARKER_PATTERN.search(name):
        return "name.test_marker"
    return ""


def explain_test_data_filter_reason(row: dict | None, *, kind: str = "job") -> str:
    if not row:
        return ""
    metadata = parse_metadata(row.get("metadata_json"))
    reason = _explicit_test_metadata_reason(metadata)
    if reason:
        return reason

    name_fields = {
        "job": ("job_id", "legacy_task_id", "voice_name", "input_path", "output_root"),
        "model": ("voice_model_id", "legacy_model_id", "model_name", "source_job_id", "pth_path", "index_path"),
        "dataset": ("dataset_id", "dataset_name", "job_id", "root_path"),
        "batch": ("batch_id", "batch_name", "output_root"),
        "track": ("track_id", "title", "source_audio_path", "batch_id"),
        "audit": ("event_id", "entity_type", "entity_id", "action", "detail_json"),
    }.get(kind, ("job_id", "voice_name"))
    for field in name_fields:
        reason = explain_test_data_name_reason(
            str(row.get(field) or ""),
            protect_real_stage=(kind == "job"),
            allow_stage_prefix=True,
        )
        if reason:
            return f"{field}.{reason}"

    original_filename = str(metadata.get("original_filename") or "").strip().lower()
    try:
        file_size = int(metadata.get("file_size") or 0)
    except (TypeError, ValueError):
        file_size = 0
    if original_filename == "suno_test.wav" and file_size == 441044:
        return "legacy.suno_test_fixture"
    return ""


def is_test_data_job_record(row: dict | None) -> bool:
    return bool(explain_test_data_filter_reason(row, kind="job"))


def is_test_data_model_record(row: dict | None) -> bool:
    return bool(explain_test_data_filter_reason(row, kind="model"))


def is_test_data_dataset_record(row: dict | None, job_row: dict | None = None) -> bool:
    if explain_test_data_filter_reason(row, kind="dataset"):
        return True
    return is_test_data_job_record(job_row)


def is_test_data_batch_record(row: dict | None) -> bool:
    return bool(explain_test_data_filter_reason(row, kind="batch"))


def is_test_data_track_record(row: dict | None, batch_row: dict | None = None) -> bool:
    if explain_test_data_filter_reason(row, kind="track"):
        return True
    return is_test_data_batch_record(batch_row)


def is_test_data_audit_record(row: dict | None) -> bool:
    return bool(explain_test_data_filter_reason(row, kind="audit"))


def is_smoke_job_record(row: dict | None) -> bool:
    return is_test_data_job_record(row)


def is_smoke_model_record(row: dict | None) -> bool:
    return is_test_data_model_record(row)


def is_smoke_dataset_record(row: dict | None, job_row: dict | None = None) -> bool:
    return is_test_data_dataset_record(row, job_row)
