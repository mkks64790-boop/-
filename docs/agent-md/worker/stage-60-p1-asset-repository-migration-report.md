# Stage60 P1 — asset_service → ArtifactRepository

**Status**: PASS  
**Date**: 2026-06-05

## Scope

Migrate `backend/services/asset_service.py` direct `get_connection()` usage to `ArtifactRepository` + `JobRepository` (Stage60D Phase 3 continuation). No schema changes.

## Changes

- `backend/repositories/artifact_repository.py`: added `find_audio_asset`, `find_job_artifact`, `update_artifact_metadata`, `patch_job_artifact`, `get_final_job_artifact_prioritized`, `get_final_cover_master`, `list_final_cover_master_with_track`.
- `backend/services/asset_service.py`: all artifact/audio DB paths now use repositories; zero `get_connection()` in this service.

## Verification

```text
python -m pytest tests/unit/ -q -k "stage59c or stage60"  → 101 passed
python -m pytest tests/api/test_stage49_listening_review_api.py tests/api/test_stage59a_asset_lifecycle_api.py -q → passed
```

## Debt

- Other services still use direct `get_connection()` (track, batch, lyric, etc.) — next P1 slices per inventory.