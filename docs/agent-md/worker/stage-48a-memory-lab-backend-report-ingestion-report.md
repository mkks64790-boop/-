# Stage 48A Memory Lab Backend Report Ingestion Report

## Completion

- Status: PASS.
- Memory Lab backend is now a real local SQLite-backed engineering memory system.
- No external AI was called.
- No files were uploaded.
- No whole-drive scan was performed.
- No user files were deleted, moved, or renamed.

## New Table

- Added `project_memories` in `backend\db.py`.
- Fields:
  - `memory_id`
  - `category`
  - `title`
  - `summary`
  - `source_type`
  - `source_path`
  - `source_stage`
  - `tags_json`
  - `importance`
  - `pinned`
  - `metadata_json`
  - `created_at`
  - `updated_at`
- Indexes:
  - `idx_project_memories_category_updated`
  - `idx_project_memories_stage_updated`
  - `idx_project_memories_pinned_updated`

## New Backend Service

- Added `backend\services\memory_service.py`.
- Responsibilities:
  - Idempotent memory upsert.
  - Local-only report ingestion.
  - Safe source path validation.
  - Summary-only Markdown indexing.
  - Stage extraction such as `Stage47A`, `Stage46B`, `Stage45R`.
  - Key-fact extraction for important conclusions.
- Allowed scan directories only:
  - `docs/agent-md/worker`
  - `docs/agent-md/architect`
  - `docs/agent-md/handoff`
- `source_path` validation rejects Markdown paths outside those allowed project-local directories.
- Full report text is not stored in the database; only title, summary, path, stage, tags, and metadata are stored.

## New API

- `GET /api/memory`
  - Supports `category`, `tag`, `q`, `pinned`, `limit`, `offset`.
- `GET /api/memory/summary`
  - Returns total count, pinned count, category counts, recent stages, recent memories.
- `POST /api/memory/rescan`
  - Scans only the allowed `agent-md` directories.
  - Upserts Markdown report/prompt/handoff memories.
- `POST /api/memory`
  - Creates/upserts a local manual memory.
  - Rejects unsafe `source_path`.
- `PATCH /api/memory/{memory_id}`
  - Light update for existing memories.

## Rescan Result

Final required TestClient command:

```powershell
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.post('/api/memory/rescan').json()); print(c.get('/api/memory/summary').json())"
```

Result summary:

- `ok`: true
- `scanned_files`: 139
- `upserted_count`: 163
- `errors`: []
- `total_count`: 163
- `pinned_count`: 24
- Categories:
  - `agent_report`: 55
  - `architect_prompt`: 55
  - `handoff`: 29
  - `key_fact`: 24

## Stage47A Memory Retrieval

Query:

```text
GET /api/memory?q=v_d4d7e1c1&limit=10
```

Result:

- Stage47A key memory is retrievable.
- Important returned memory:
  - Title: `Stage47 real model: v_d4d7e1c1 / 朱朱_stage47_single_long`
  - Category: `key_fact`
  - Source path includes:
    - `docs/agent-md/worker/stage-47a-real-single-long-training-cover-closure-report.md`
- Related Stage47 cover memory is also ingested:
  - `Stage47 cover smoke: task_b2272d133fff`
- UVR/training unblock memory is ingested:
  - `UVR duration fixed: BLOCK_TRAINING=false`

## Self Check Update

- Updated `backend\self_check.py`.
- Added `memory lab contract` check:
  - Calls `POST /api/memory/rescan`.
  - Reads `GET /api/memory/summary`.
  - Searches `GET /api/memory?q=v_d4d7e1c1`.
  - Requires Stage47A key memory to be discoverable.

Observed self_check result:

```text
[PASS] memory lab contract :: scanned=139 total=163 stage47_matches=10
SELF_CHECK_SUMMARY PASS
```

## Tests Added

- Added `tests\unit\test_memory_service.py`.
  - Verifies report rescan.
  - Verifies Stage47 key-fact extraction.
  - Verifies summary counts.
  - Verifies unsafe source path rejection.
- Added `tests\api\test_memory_api.py`.
  - Verifies `/api/memory/rescan`.
  - Verifies `/api/memory/summary`.
  - Verifies `/api/memory?q=...`.
  - Verifies manual memory create.
  - Verifies patch.
  - Verifies unsafe source path rejection.

## Validation Results

- `python -m pytest -q`
  - PASS
  - `71 passed, 2 warnings`
- `python -m backend.self_check`
  - PASS
  - `SELF_CHECK_SUMMARY PASS`
- Required TestClient command:
  - PASS
  - `scanned_files=139`
  - `total_count=163`
  - `errors=[]`

## Changed Files

- `backend\db.py`
- `backend\main.py`
- `backend\services\memory_service.py`
- `backend\self_check.py`
- `tests\unit\test_memory_service.py`
- `tests\api\test_memory_api.py`
- `docs\agent-md\worker\stage-48a-memory-lab-backend-report-ingestion-report.md`

## Remaining Risks

- Key-fact extraction is rule-based and local-only. It intentionally does not call AI, so summaries are simple and may need product-side curation later.
- Rescan currently indexes only top-level `*.md` files in the three allowed `agent-md` directories. This is deliberate to avoid broad filesystem scans.
- Some key facts can appear from multiple stage files if later prompts repeat the same IDs. This is acceptable for Stage48A backend landing, but Stage48B UI may want grouping/deduped display.
