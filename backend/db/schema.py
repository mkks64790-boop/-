"""
backend/db/schema.py

Stage60 DB Governance Phase 2A: Schema ownership only.

Owns:
- current create-table DDL (all CREATE TABLE IF NOT EXISTS baseline)
- schema_migrations table (for future versioning, added here per plan)
- snapshot helpers

No migrations application logic, no backfills (those stay in db orchestrator for now).
All existing tables preserved exactly: tasks, jobs, voice_models, release_*, tracks,
lyric_*, material_*, audit, memories, etc.
"""

import sqlite3


# Baseline DDL extracted verbatim from legacy init_db executescript.
# DO NOT EDIT without governance process; this is the current "create all" snapshot.
SCHEMA_DDL = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id TEXT PRIMARY KEY,
        applied_at TEXT,
        checksum TEXT
    );

    CREATE TABLE IF NOT EXISTS tasks (
        task_id      TEXT PRIMARY KEY,
        task_type    TEXT NOT NULL DEFAULT 'cover',
        input_file   TEXT NOT NULL,
        voice_name   TEXT DEFAULT '',
        compute_ready INTEGER NOT NULL DEFAULT 0,
        status       TEXT NOT NULL DEFAULT 'pending',
        error_log    TEXT DEFAULT '',
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS voice_assets (
        model_id      TEXT PRIMARY KEY,
        model_name    TEXT NOT NULL,
        pth_path      TEXT NOT NULL,
        index_path    TEXT NOT NULL,
        default_pitch INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS compute_mutex (
        mutex_name    TEXT PRIMARY KEY,
        owner_task_id TEXT DEFAULT '',
        owner_task_type TEXT DEFAULT '',
        owner_status  TEXT DEFAULT '',
        locked_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS jobs (
        job_id         TEXT PRIMARY KEY,
        legacy_task_id TEXT UNIQUE,
        job_type       TEXT NOT NULL,
        job_kind       TEXT NOT NULL DEFAULT '',
        strategy_key   TEXT NOT NULL DEFAULT '',
        status         TEXT NOT NULL DEFAULT 'pending',
        current_stage  TEXT DEFAULT '',
        compute_ready  INTEGER NOT NULL DEFAULT 0,
        track_id       TEXT DEFAULT '',
        resource_class TEXT NOT NULL DEFAULT 'gpu_heavy',
        depends_on_json TEXT DEFAULT '[]',
        voice_model_id TEXT DEFAULT '',
        voice_name     TEXT DEFAULT '',
        input_path     TEXT DEFAULT '',
        output_root    TEXT DEFAULT '',
        error_log      TEXT DEFAULT '',
        metadata_json  TEXT DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS datasets (
        dataset_id     TEXT PRIMARY KEY,
        job_id         TEXT NOT NULL,
        dataset_name   TEXT DEFAULT '',
        strategy_key   TEXT DEFAULT '',
        root_path      TEXT NOT NULL,
        file_count     INTEGER NOT NULL DEFAULT 0,
        total_bytes    INTEGER NOT NULL DEFAULT 0,
        metadata_json  TEXT DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(job_id) REFERENCES jobs(job_id)
    );

    CREATE TABLE IF NOT EXISTS audio_assets (
        asset_id       TEXT PRIMARY KEY,
        dataset_id     TEXT DEFAULT '',
        job_id         TEXT NOT NULL,
        asset_role     TEXT NOT NULL,
        file_name      TEXT NOT NULL,
        file_ext       TEXT DEFAULT '',
        file_path      TEXT NOT NULL,
        file_size      INTEGER NOT NULL DEFAULT 0,
        duration_sec   REAL NOT NULL DEFAULT 0,
        lifecycle_state TEXT NOT NULL DEFAULT 'active',
        metadata_json  TEXT DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(job_id) REFERENCES jobs(job_id)
    );

    CREATE TABLE IF NOT EXISTS job_artifacts (
        artifact_id    TEXT PRIMARY KEY,
        job_id         TEXT NOT NULL,
        stage_name     TEXT NOT NULL,
        artifact_type  TEXT NOT NULL,
        file_path      TEXT NOT NULL,
        file_size      INTEGER NOT NULL DEFAULT 0,
        is_final       INTEGER NOT NULL DEFAULT 0,
        lifecycle_state TEXT NOT NULL DEFAULT 'active',
        metadata_json  TEXT DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(job_id) REFERENCES jobs(job_id)
    );

    CREATE TABLE IF NOT EXISTS job_stage_logs (
        log_id         TEXT PRIMARY KEY,
        job_id         TEXT NOT NULL,
        stage_name     TEXT NOT NULL,
        status         TEXT NOT NULL,
        message        TEXT DEFAULT '',
        detail_json    TEXT DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(job_id) REFERENCES jobs(job_id)
    );

    CREATE TABLE IF NOT EXISTS voice_models (
        voice_model_id TEXT PRIMARY KEY,
        legacy_model_id TEXT UNIQUE,
        model_name     TEXT NOT NULL,
        source_job_id  TEXT DEFAULT NULL,
        pth_path       TEXT NOT NULL,
        index_path     TEXT NOT NULL,
        default_pitch  INTEGER NOT NULL DEFAULT 0,
        status         TEXT NOT NULL DEFAULT 'ready',
        lifecycle_state TEXT NOT NULL DEFAULT 'active',
        metadata_json  TEXT DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(source_job_id) REFERENCES jobs(job_id)
    );

    CREATE TABLE IF NOT EXISTS release_batches (
        batch_id              TEXT PRIMARY KEY,
        batch_name            TEXT NOT NULL,
        status                TEXT NOT NULL DEFAULT 'draft',
        target_platforms_json TEXT DEFAULT '[]',
        output_root           TEXT NOT NULL DEFAULT '',
        metadata_json         TEXT DEFAULT '{}',
        created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tracks (
        track_id                    TEXT PRIMARY KEY,
        batch_id                    TEXT NOT NULL,
        title                       TEXT NOT NULL DEFAULT '',
        artist                      TEXT NOT NULL DEFAULT '',
        source_type                 TEXT NOT NULL DEFAULT 'upload',
        status                      TEXT NOT NULL DEFAULT 'draft',
        notes                       TEXT DEFAULT '',
        source_audio_path           TEXT NOT NULL DEFAULT '',
        current_master_job_id       TEXT DEFAULT '',
        current_master_artifact_id  TEXT DEFAULT '',
        current_lyric_document_id   TEXT DEFAULT '',
        current_timeline_version_id TEXT DEFAULT '',
        metadata_json               TEXT DEFAULT '{}',
        created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(batch_id) REFERENCES release_batches(batch_id)
    );

    CREATE TABLE IF NOT EXISTS lyric_documents (
        lyric_document_id TEXT PRIMARY KEY,
        track_id          TEXT NOT NULL,
        source            TEXT NOT NULL DEFAULT 'manual',
        language          TEXT NOT NULL DEFAULT 'zh-CN',
        title             TEXT DEFAULT '',
        text_content      TEXT NOT NULL DEFAULT '',
        structure_json    TEXT DEFAULT '{}',
        metadata_json     TEXT DEFAULT '{}',
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(track_id) REFERENCES tracks(track_id)
    );

    CREATE TABLE IF NOT EXISTS lyric_timeline_versions (
        timeline_id        TEXT PRIMARY KEY,
        track_id           TEXT NOT NULL,
        lyric_document_id  TEXT NOT NULL,
        engine             TEXT NOT NULL DEFAULT 'stub_align_v1',
        align_mode         TEXT NOT NULL DEFAULT 'balanced_lines',
        status             TEXT NOT NULL DEFAULT 'draft',
        version_label      TEXT NOT NULL DEFAULT '',
        txt_path           TEXT DEFAULT '',
        lrc_path           TEXT DEFAULT '',
        srt_path           TEXT DEFAULT '',
        ass_path           TEXT DEFAULT '',
        preview_json       TEXT DEFAULT '[]',
        metadata_json      TEXT DEFAULT '{}',
        is_current         INTEGER NOT NULL DEFAULT 0,
        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(track_id) REFERENCES tracks(track_id),
        FOREIGN KEY(lyric_document_id) REFERENCES lyric_documents(lyric_document_id)
    );

    CREATE TABLE IF NOT EXISTS audit_events (
        event_id     TEXT PRIMARY KEY,
        entity_type  TEXT NOT NULL,
        entity_id    TEXT NOT NULL,
        action       TEXT NOT NULL,
        detail_json  TEXT DEFAULT '{}',
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS project_memories (
        memory_id     TEXT PRIMARY KEY,
        category      TEXT NOT NULL DEFAULT 'note',
        title         TEXT NOT NULL DEFAULT '',
        summary       TEXT NOT NULL DEFAULT '',
        source_type   TEXT NOT NULL DEFAULT 'manual',
        source_path   TEXT NOT NULL DEFAULT '',
        source_stage   TEXT NOT NULL DEFAULT '',
        tags_json     TEXT DEFAULT '[]',
        importance    INTEGER NOT NULL DEFAULT 50,
        pinned        INTEGER NOT NULL DEFAULT 0,
        metadata_json TEXT DEFAULT '{}',
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS material_libraries (
        library_id     TEXT PRIMARY KEY,
        library_key    TEXT NOT NULL UNIQUE,
        display_name   TEXT NOT NULL DEFAULT '',
        source_group   TEXT NOT NULL DEFAULT '',
        root_path      TEXT NOT NULL DEFAULT '',
        license_status TEXT NOT NULL DEFAULT 'unknown',
        license_tag    TEXT NOT NULL DEFAULT '',
        storage_policy TEXT NOT NULL DEFAULT 'external_read_only',
        enabled        INTEGER NOT NULL DEFAULT 1,
        metadata_json  TEXT DEFAULT '{}',
        last_scanned_at TIMESTAMP DEFAULT NULL,
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS material_assets (
        material_id    TEXT PRIMARY KEY,
        library_id     TEXT NOT NULL,
        source_group   TEXT NOT NULL DEFAULT '',
        file_name      TEXT NOT NULL DEFAULT '',
        file_ext       TEXT NOT NULL DEFAULT '',
        file_path      TEXT NOT NULL DEFAULT '',
        relative_path  TEXT NOT NULL DEFAULT '',
        file_size      INTEGER NOT NULL DEFAULT 0,
        duration_sec   REAL DEFAULT NULL,
        sample_rate    INTEGER DEFAULT NULL,
        channels       INTEGER DEFAULT NULL,
        codec          TEXT NOT NULL DEFAULT '',
        material_role  TEXT NOT NULL DEFAULT 'unknown',
        material_profile TEXT NOT NULL DEFAULT 'needs_manual_review',
        quality_state  TEXT NOT NULL DEFAULT 'metadata_only',
        route_hint     TEXT NOT NULL DEFAULT '',
        license_tag    TEXT NOT NULL DEFAULT '',
        license_status TEXT NOT NULL DEFAULT 'unknown',
        retention_status TEXT NOT NULL DEFAULT 'active',
        lifecycle_state  TEXT NOT NULL DEFAULT 'active',
        metadata_json  TEXT DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(library_id) REFERENCES material_libraries(library_id)
    );
"""


def get_schema_ddl() -> str:
    """Return the full current baseline schema DDL string (for inspection or tests)."""
    return SCHEMA_DDL


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables using current baseline DDL (idempotent via IF NOT EXISTS).

    This is the single place for "CREATE TABLE" statements.
    Callers (init_db) remain responsible for post-create _migrate_add_column etc.
    """
    conn.executescript(SCHEMA_DDL)


def get_schema_snapshot(conn: sqlite3.Connection) -> dict:
    """Basic schema snapshot helper for diagnostics / governance verification.

    Returns table names and column lists. Does not include indexes or full defs.
    """
    tables: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall():
        name = row[0]
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({name})")]
        tables[name] = cols
    return {
        "tables": tables,
        "table_count": len(tables),
    }


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Internal helper (duplicated from old db for snapshot safety; prefer schema later)."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
