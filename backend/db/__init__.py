"""
FeiShark Studio - 数据库模块 (Stage60 Governance refactored)

轻量解耦方案：任务队列 + 模型资产管理

支持双任务类型:
  - cover: AI 翻唱任务（分离→修音→变声→混音）
  - train: 音色训练任务（切片→训练→入库）

Phase 2A: Schema and Connection Restructure complete.
- backend/db/connection.py : path resolution + get_connection + PRAGMA only
- backend/db/schema.py : DDL + schema snapshot helpers only
- This __init__.py : thin orchestrator. Keeps init_db, all backfills, CRUD, legacy mirrors for compat.
- All public names re-exported for backward compatibility (from backend.db import get_connection, DB_PATH, create_task, ...)

No new features. Existing tables preserved exactly.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

# ── Split imports (relative, governance) ─────────────────────────────────────
from .connection import DB_PATH as _DEFAULT_DB_PATH
from .connection import get_connection as _raw_get_connection
from .schema import (
    init_schema,
    get_schema_ddl,
    get_schema_snapshot,
    _table_exists,
)

# DB_PATH lives here (re-export + patch target for tests/conftest that do
# setattr(backend_db, "DB_PATH", tmp_path) ). The wrapper below ensures
# get_connection() always sees the (possibly patched) value.
DB_PATH = _DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    """Single source of truth.

    Thin wrapper so that monkeypatching backend.db.DB_PATH (standard in this
    codebase's tests) affects connections, while implementation lives in
    connection.py per Phase 2A plan.
    """
    # Lookup of DB_PATH here is against this module's globals -> runtime patch visible
    return _raw_get_connection(DB_PATH)


# Re-export for consumers who do "from backend.db import ..."
__all__ = [
    "DB_PATH",
    "get_connection",
    "init_db",
    "PROJECT_ROOT",
    "WEIGHTS_DIR",
    "OUTPUT_ROOT",
    "JOBS_ROOT",
    "BATCHES_ROOT",
    "ACTIVE_COMPUTE_STATUSES",
    "TERMINAL_STATUSES",
    "COMPUTE_MUTEX_NAME",
    "LIFECYCLE_DELETE_FILENAMES",
    # CRUD and helpers (kept here for Phase 2A compat; will migrate to repos later)
    "add_voice_asset",
    "create_task",
    "create_train_task",
    "set_task_model_id",
    "mark_task_compute_ready",
    "update_task_status",
    "get_task",
    "get_voice_asset",
    "get_all_voice_assets",
    "get_next_pending_compute_task",
    "reserve_compute_slot",
    "release_compute_slot",
    "recover_stale_compute_state",
    "file_lifecycle_cleanup",
    "seed_default_data",
    "smoke_test",
    # internals exposed for tests / self_check / patching
    "_normalize_status",
    "_migrate_add_column",
    "_dedupe_new_tables",
    "_create_unique_indexes",
    "_backfill_legacy_jobs",
    "_backfill_extended_job_fields",
    "_backfill_legacy_voice_models",
    "_backfill_job_current_stages",
    "_backfill_asset_lifecycle_states",
    "_schedule_file_lifecycle_cleanup",
    "_collect_lifecycle_cleanup_ids",
    "_query_old_tasks",
    "_query_old_cover_jobs",
    "_table_exists",
    "_has_unclosed_stage",
    "_resolve_voice_model_fields",
    "_metadata_json_equal",
    "_voice_model_materially_changed",
    "_status_to_stage",
    # schema helpers
    "get_schema_ddl",
    "get_schema_snapshot",
    "init_schema",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(DB_PATH))
WEIGHTS_DIR = os.path.join(PROJECT_ROOT, "shared_data", "weights")
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "outputs")
JOBS_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "jobs")
BATCHES_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "batches")

ACTIVE_COMPUTE_STATUSES = {
    "分离中",
    "修音中",
    "变声中",
    "混音中",
    "切片中",
    "训练中",
    "处理中",
    "running",
    "processing",
}
TERMINAL_STATUSES = {"完成", "已完成", "completed", "失败", "failed", "已取消", "cancelled"}
COMPUTE_MUTEX_NAME = "gpu"
LIFECYCLE_DELETE_FILENAMES = (
    "vocal.wav",
    "instrumental.wav",
    "fixed.wav",
    "transformed.wav",
    "vocal_fixed.wav",
    "vocal_transformed.wav",
)

_cleanup_lock = threading.Lock()
_mutex_lock = threading.Lock()


def _normalize_status(status: str) -> str:
    value = (status or "").strip().lower()
    if value in {"pending", "queued", "排队中", "等待中"}:
        return "pending"
    if value in {"完成", "已完成", "completed", "complete", "done", "success", "succeeded"}:
        return "completed"
    if value in {"失败", "failed", "fail", "error"}:
        return "failed"
    if value in {"已取消", "cancelled", "canceled"}:
        return "cancelled"
    if value in {"训练中", "处理中", "running", "processing", "分离中", "修音中", "变声中", "混音中", "切片中"}:
        return "processing"
    return value


def init_db():
    """初始化数据库，创建基础表（兼容旧数据自动迁移）

    Schema creation now delegated to backend.db.schema (Phase 2A).
    This function still owns post-DDL migrations, backfills, indexes, and side effects
    (per current governance freeze: no new backfills allowed, existing kept for compat).
    """
    conn = get_connection()
    try:
        # All CREATE TABLE IF NOT EXISTS now live in schema.py
        init_schema(conn)

        # Phase 2B: apply idempotent migrations from backend/db/migrations/ after basic schema.
        # This enables future DDL to live in ordered .sql/.py files (no more large edits in this file).
        apply_migrations(conn)

        # 兼容迁移：旧表缺少 task_type 和 voice_name 时自动添加
        _migrate_add_column(conn, "tasks", "task_type", "TEXT NOT NULL DEFAULT 'cover'")
        _migrate_add_column(conn, "tasks", "voice_name", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "tasks", "model_id", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "tasks", "compute_ready", "INTEGER NOT NULL DEFAULT 0")
        _migrate_add_column(conn, "jobs", "job_kind", "TEXT NOT NULL DEFAULT ''")
        _migrate_add_column(conn, "jobs", "track_id", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "jobs", "resource_class", "TEXT NOT NULL DEFAULT 'gpu_heavy'")
        _migrate_add_column(conn, "jobs", "depends_on_json", "TEXT DEFAULT '[]'")
        _migrate_add_column(conn, "tracks", "current_master_job_id", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "tracks", "current_master_artifact_id", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "audio_assets", "lifecycle_state", "TEXT NOT NULL DEFAULT 'active'")
        _migrate_add_column(conn, "job_artifacts", "lifecycle_state", "TEXT NOT NULL DEFAULT 'active'")
        _migrate_add_column(conn, "voice_models", "lifecycle_state", "TEXT NOT NULL DEFAULT 'active'")
        _migrate_add_column(conn, "material_assets", "lifecycle_state", "TEXT NOT NULL DEFAULT 'active'")

        conn.execute(
            "INSERT OR IGNORE INTO compute_mutex (mutex_name, owner_task_id, owner_task_type, owner_status) "
            "VALUES (?, '', '', '')",
            (COMPUTE_MUTEX_NAME,),
        )
        _dedupe_new_tables(conn)
        _create_unique_indexes(conn)

        # ── Backfill retirement (Phase 4: DB Governance) ──────────────────────────────
        # Historical backfills moved out of startup for fast, side-effect-free init.
        # These ran unbounded scans/rewrites on every startup (legacy compat for pre-jobs/pre-lifecycle data).
        # Now: only idempotent minimal setup here (CREATE IF NOT EXISTS, ALTER ADD COLUMN IF, seed, dedupe, indexes).
        # Use the verifier scripts in scripts/verify_backfill_*.py for one-time or verification runs.
        #   (similar for extended_job_fields, legacy_voice_models, job_current_stages, asset_lifecycle_states)
        # Safe: functions use INSERT OR IGNORE / conditional UPDATEs where possible; always dry-run first.
        # No data loss: dual-writes in create paths + recover still populate both legacy+canonical for new ops.
        print("[OK] init_db: minimal idempotent setup only (backfills retired from startup path)")
        # _backfill_legacy_jobs(conn)  # RETIRED from here
        # _backfill_extended_job_fields(conn)
        # _backfill_legacy_voice_models(conn)
        # _backfill_job_current_stages(conn)
        # _backfill_asset_lifecycle_states(conn)
        conn.commit()

        # 确保权重目录存在
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        os.makedirs(JOBS_ROOT, exist_ok=True)
        os.makedirs(BATCHES_ROOT, exist_ok=True)

        print(f"[OK] 数据库初始化完成: {DB_PATH}")
        print(f"[OK] 权重目录: {WEIGHTS_DIR}")
    finally:
        conn.close()


def _migrate_add_column(conn, table: str, column: str, col_def: str):
    """安全迁移：如果列不存在则添加"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        print(f"[MIGRATE] {table} 新增列: {column}")


def _dedupe_new_tables(conn):
    conn.executescript(
        """
        DELETE FROM audio_assets
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM audio_assets
            GROUP BY job_id, dataset_id, asset_role, file_path
        );

        DELETE FROM job_artifacts
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM job_artifacts
            GROUP BY job_id, stage_name, artifact_type, file_path
        );

        DELETE FROM job_stage_logs
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM job_stage_logs
            GROUP BY job_id, stage_name, status, message
        );
        """
    )


def _create_unique_indexes(conn):
    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_audio_assets_identity
        ON audio_assets(job_id, dataset_id, asset_role, file_path);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_job_artifacts_identity
        ON job_artifacts(job_id, stage_name, artifact_type, file_path);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_job_stage_logs_identity
        ON job_stage_logs(job_id, stage_name, status, message);

        CREATE INDEX IF NOT EXISTS idx_tracks_batch_created
        ON tracks(batch_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_lyric_documents_track_created
        ON lyric_documents(track_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_lyric_versions_track_created
        ON lyric_timeline_versions(track_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_audit_events_entity_created
        ON audit_events(entity_type, entity_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_project_memories_category_updated
        ON project_memories(category, updated_at);

        CREATE INDEX IF NOT EXISTS idx_project_memories_stage_updated
        ON project_memories(source_stage, updated_at);

        CREATE INDEX IF NOT EXISTS idx_project_memories_pinned_updated
        ON project_memories(pinned, updated_at);

        CREATE INDEX IF NOT EXISTS idx_material_assets_library_profile
        ON material_assets(library_id, material_profile, retention_status);

        CREATE INDEX IF NOT EXISTS idx_material_assets_role_status
        ON material_assets(material_role, quality_state, retention_status);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_material_assets_library_path
        ON material_assets(library_id, file_path);
        """
    )


# ── Phase 2B: Schema Migrations (governance only; future changes go in backend/db/migrations/) ──

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT,
            checksum TEXT
        )
        """
    )


def _compute_checksum(content: str) -> str:
    import hashlib
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def get_applied_migrations(conn: sqlite3.Connection | None = None) -> list[dict]:
    if conn is None:
        conn = get_connection()
    _ensure_migrations_table(conn)
    rows = conn.execute(
        "SELECT id, applied_at, checksum FROM schema_migrations ORDER BY id"
    ).fetchall()
    return [{"id": r[0], "applied_at": r[1], "checksum": r[2]} for r in rows]


def _list_migration_files() -> list[str]:
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    files = []
    for name in sorted(os.listdir(MIGRATIONS_DIR)):
        if name.endswith((".sql", ".py")) and not name.startswith("__"):
            files.append(name)
    return files


def apply_migrations(conn: sqlite3.Connection | None = None) -> list[str]:
    """Idempotent migration application runner.
    - Scans backend/db/migrations/ for 000N_*.sql or .py (sorted).
    - If not in schema_migrations, apply + record with checksum.
    - If already applied, verify checksum matches (fail on tampering).
    - .sql: use executescript (idempotent IF NOT).
    - .py: exec with 'conn' in globals.
    """
    if conn is None:
        conn = get_connection()
    _ensure_migrations_table(conn)
    applied = {row["id"]: row["checksum"] for row in get_applied_migrations(conn)}
    applied_ids = []
    for mig_id in _list_migration_files():
        path = os.path.join(MIGRATIONS_DIR, mig_id)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        checksum = _compute_checksum(content)
        if mig_id in applied:
            if applied[mig_id] != checksum:
                raise RuntimeError(f"[MIGRATE] Checksum mismatch for {mig_id} (tamper?)")
            continue
        if mig_id.endswith(".sql"):
            if content.strip():
                conn.executescript(content)
            print(f"[MIGRATE] Applied SQL migration: {mig_id}")
        elif mig_id.endswith(".py"):
            ns = {"conn": conn}
            exec(compile(content, path, "exec"), ns)
            print(f"[MIGRATE] Applied PY migration: {mig_id}")
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations (id, applied_at, checksum) VALUES (?, ?, ?)",
            (mig_id, datetime.now(timezone.utc).isoformat(), checksum),
        )
        applied_ids.append(mig_id)
    return applied_ids


def _backfill_legacy_jobs(conn):
    """RETIRED Phase 4 (Backfill Retirement & Legacy Cleanup).
    Retained ONLY for one-time verifier / migration scripts.
    NEVER called from init_db or any startup path.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO jobs (
            job_id, legacy_task_id, job_type, job_kind, strategy_key, status, current_stage,
            compute_ready, track_id, resource_class, depends_on_json, voice_model_id, voice_name, input_path, output_root,
            error_log, metadata_json, created_at, updated_at
        )
        SELECT
            task_id,
            task_id,
            CASE WHEN task_type = 'train' THEN 'train' ELSE 'cover' END,
            CASE WHEN task_type = 'train' THEN 'train' ELSE 'cover' END,
            CASE
                WHEN task_type = 'train' THEN 'legacy_train'
                WHEN task_type = 'cover' THEN 'cover_strategy'
                ELSE 'legacy_import'
            END,
            status,
            ?,
            compute_ready,
            '',
            'gpu_heavy',
            '[]',
            COALESCE(model_id, ''),
            COALESCE(voice_name, ''),
            input_file,
            ? || task_id,
            COALESCE(error_log, ''),
            '{}',
            created_at,
            CURRENT_TIMESTAMP
        FROM tasks
        """,
        ("", os.path.join("shared_data", "jobs") + os.sep),
    )


def _backfill_extended_job_fields(conn):
    """RETIRED Phase 4 (Backfill Retirement & Legacy Cleanup).
    Retained ONLY for one-time verifier / migration scripts.
    NEVER called from init_db or any startup path.
    """
    conn.execute(
        """
        UPDATE jobs
        SET job_kind = CASE
                WHEN COALESCE(job_kind, '') != '' THEN job_kind
                WHEN COALESCE(job_type, '') = 'train' THEN 'train'
                ELSE 'cover'
            END,
            track_id = COALESCE(track_id, ''),
            resource_class = CASE
                WHEN COALESCE(resource_class, '') != '' THEN resource_class
                ELSE 'gpu_heavy'
            END,
            depends_on_json = CASE
                WHEN COALESCE(depends_on_json, '') != '' THEN depends_on_json
                ELSE '[]'
            END
        """
    )


def _backfill_legacy_voice_models(conn):
    """RETIRED Phase 4 (Backfill Retirement & Legacy Cleanup).
    Retained ONLY for one-time verifier / migration scripts.
    NEVER called from init_db or any startup path.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO voice_models (
            voice_model_id, legacy_model_id, model_name, source_job_id,
            pth_path, index_path, default_pitch, status, metadata_json,
            created_at, updated_at
        )
        SELECT
            model_id,
            model_id,
            model_name,
            NULL,
            pth_path,
            index_path,
            default_pitch,
            'ready',
            '{}',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM voice_assets
        """
    )


def _backfill_asset_lifecycle_states(conn):
    """RETIRED Phase 4 (Backfill Retirement & Legacy Cleanup).
    Retained ONLY for one-time verifier / migration scripts.
    NEVER called from init_db or any startup path.
    """
    try:
        from ..services.lifecycle_service import backfill_lifecycle_states
    except ImportError:
        from services.lifecycle_service import backfill_lifecycle_states

    stats = backfill_lifecycle_states(conn)
    if any(stats.values()):
        print(f"[MIGRATE] lifecycle_state backfill: {stats}")


def _backfill_job_current_stages(conn):
    """RETIRED Phase 4 (Backfill Retirement & Legacy Cleanup).
    Retained ONLY for one-time verifier / migration scripts.
    NEVER called from init_db or any startup path.
    """
    rows = conn.execute(
        """
        SELECT job_id, job_type, status, current_stage
        FROM jobs
        WHERE COALESCE(current_stage, '') = ''
        """
    ).fetchall()
    for row in rows:
        stage_rows = conn.execute(
            """
            SELECT stage_name
            FROM job_stage_logs
            WHERE job_id = ? AND stage_name NOT IN ('job_dispatch', 'job_control')
            ORDER BY datetime(created_at), rowid
            """,
            (row["job_id"],),
        ).fetchall()
        if stage_rows:
            current_stage = stage_rows[-1]["stage_name"]
        elif row["status"] == "完成":
            current_stage = "cover_mix" if row["job_type"] == "cover" else "train_register_model"
        elif row["status"] == "失败":
            current_stage = "failed"
        elif row["status"] == "pending":
            current_stage = "pending"
        else:
            current_stage = row["status"] or ""
        if current_stage:
            conn.execute(
                """
                UPDATE jobs
                SET current_stage = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                """,
                (current_stage, row["job_id"]),
            )


# ── CRUD ──────────────────────────────────────────────


def _resolve_voice_model_fields(
    model_id: str,
    model_name: str,
    pth_path: str,
    index_path: str,
    default_pitch: int,
    source_job_id: str,
    metadata: dict | None,
    existing: sqlite3.Row | None,
) -> dict:
    """Resolve voice_models column values (matches INSERT OR REPLACE COALESCE semantics)."""
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    if existing is None:
        return {
            "voice_model_id": model_id,
            "legacy_model_id": model_id,
            "model_name": model_name,
            "source_job_id": source_job_id or None,
            "pth_path": pth_path,
            "index_path": index_path,
            "default_pitch": default_pitch,
            "status": "ready",
            "metadata_json": metadata_json or "{}",
        }
    return {
        "voice_model_id": model_id,
        "legacy_model_id": model_id,
        "model_name": model_name,
        "source_job_id": source_job_id or existing["source_job_id"],
        "pth_path": pth_path,
        "index_path": index_path,
        "default_pitch": default_pitch,
        "status": "ready",
        "metadata_json": metadata_json or (existing["metadata_json"] or "{}"),
    }


def _metadata_json_equal(left: str, right: str) -> bool:
    try:
        return json.loads(left or "{}") == json.loads(right or "{}")
    except json.JSONDecodeError:
        return (left or "") == (right or "")


def _voice_model_materially_changed(existing: sqlite3.Row | None, fields: dict) -> bool:
    if existing is None:
        return True
    return (
        existing["legacy_model_id"] != fields["legacy_model_id"]
        or existing["model_name"] != fields["model_name"]
        or (existing["source_job_id"] or None) != fields["source_job_id"]
        or existing["pth_path"] != fields["pth_path"]
        or existing["index_path"] != fields["index_path"]
        or int(existing["default_pitch"]) != int(fields["default_pitch"])
        or existing["status"] != fields["status"]
        or not _metadata_json_equal(existing["metadata_json"] or "{}", fields["metadata_json"])
    )


def add_voice_asset(model_id, model_name, pth_path, index_path, default_pitch=0, source_job_id: str = "", metadata: dict | None = None) -> bool:
    """添加音色资产到知识库。返回 True 表示新插入 voice_assets 或 voice_models 有实质更新。"""
    conn = get_connection()
    try:
        existing_model = conn.execute(
            """
            SELECT voice_model_id, legacy_model_id, model_name, source_job_id,
                   pth_path, index_path, default_pitch, status, metadata_json, created_at
            FROM voice_models
            WHERE voice_model_id = ?
            """,
            (model_id,),
        ).fetchone()
        model_fields = _resolve_voice_model_fields(
            model_id, model_name, pth_path, index_path, default_pitch, source_job_id, metadata, existing_model
        )
        model_changed = _voice_model_materially_changed(existing_model, model_fields)

        cur = conn.execute(
            "INSERT OR IGNORE INTO voice_assets (model_id, model_name, pth_path, index_path, default_pitch) "
            "VALUES (?, ?, ?, ?, ?)",
            (model_id, model_name, pth_path, index_path, default_pitch),
        )
        assets_inserted = cur.rowcount > 0

        if assets_inserted or model_changed:
            conn.execute(
                """
                INSERT OR REPLACE INTO voice_models (
                    voice_model_id, legacy_model_id, model_name, source_job_id,
                    pth_path, index_path, default_pitch, status, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    COALESCE(?, CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    model_fields["voice_model_id"],
                    model_fields["legacy_model_id"],
                    model_fields["model_name"],
                    model_fields["source_job_id"],
                    model_fields["pth_path"],
                    model_fields["index_path"],
                    model_fields["default_pitch"],
                    model_fields["status"],
                    model_fields["metadata_json"],
                    existing_model["created_at"] if existing_model else None,
                ),
            )

        conn.commit()
        ok = assets_inserted or model_changed
        if ok:
            print(f"[OK] 音色入库: {model_name} ({model_id})")
        else:
            print(f"[SKIP] 音色已存在: {model_id}")
        return ok
    finally:
        conn.close()


def create_task(task_id, input_file, task_type="cover") -> bool:
    """创建翻唱任务，status 默认 pending"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO tasks (task_id, input_file, task_type) VALUES (?, ?, ?)",
            (task_id, input_file, task_type),
        )
        conn.commit()
        ok = conn.total_changes > 0
        if ok:
            print(f"[OK] 任务入队: {task_id} [{task_type}] -> {input_file}")
            if task_type == "cover":
                conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs (
                        job_id, legacy_task_id, job_type, job_kind, strategy_key, status, current_stage,
                        compute_ready, track_id, resource_class, depends_on_json, voice_model_id, voice_name, input_path, output_root,
                        error_log, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, 'cover', 'cover', 'cover_strategy', 'pending', '', 0, '', 'gpu_heavy', '[]', '', '', ?, ?, '', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (task_id, task_id, input_file, os.path.join("shared_data", "jobs", task_id)),
                )
                conn.commit()
        else:
            print(f"[SKIP] 任务已存在: {task_id}")
        return ok
    finally:
        conn.close()


def create_train_task(task_id, voice_name, dataset_path) -> bool:
    """
    创建音色训练任务

    Args:
        task_id:      训练任务 ID
        voice_name:   新音色名称（如"牢大专属音色"）
        dataset_path: 干声音频文件路径
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO tasks (task_id, input_file, task_type, voice_name) "
            "VALUES (?, ?, 'train', ?)",
            (task_id, dataset_path, voice_name),
        )
        conn.commit()
        ok = conn.total_changes > 0
        if ok:
            print(f"[OK] 训练任务入队: {task_id} -> {voice_name} ({dataset_path})")
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    job_id, legacy_task_id, job_type, job_kind, strategy_key, status, current_stage,
                    compute_ready, track_id, resource_class, depends_on_json, voice_model_id, voice_name, input_path, output_root,
                    error_log, metadata_json, created_at, updated_at
                ) VALUES (?, ?, 'train', 'train', 'legacy_train', 'pending', '', 0, '', 'gpu_heavy', '[]', '', ?, ?, ?, '', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (task_id, task_id, voice_name, dataset_path, os.path.join("shared_data", "jobs", task_id)),
            )
            conn.commit()
        else:
            print(f"[SKIP] 任务已存在: {task_id}")
        return ok
    finally:
        conn.close()


def set_task_model_id(task_id: str, model_id: str) -> bool:
    """记录翻唱任务选择的音色模型，并同步写入 legacy tasks。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET voice_model_id = ?, job_type = 'cover', job_kind = 'cover', strategy_key = 'cover_strategy',
                compute_ready = 1, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (model_id, task_id, task_id),
        )
        cursor = conn.execute(
            "UPDATE tasks SET model_id = ?, task_type = 'cover', compute_ready = 1 WHERE task_id = ?",
            (model_id, task_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def mark_task_compute_ready(task_id: str, task_type: str) -> bool:
    """把任务标记为允许进入全局 GPU 队列，并同步 jobs/tasks。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET job_type = ?, job_kind = ?, resource_class = 'gpu_heavy', compute_ready = 1, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (task_type, task_type, task_id, task_id),
        )
        cursor = conn.execute(
            "UPDATE tasks SET task_type = ?, compute_ready = 1 WHERE task_id = ?",
            (task_type, task_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_task_status(task_id, status, error_log="") -> bool:
    """主写 jobs 状态，再镜像到 legacy tasks。"""
    conn = get_connection()
    try:
        normalized_status = _normalize_status(status)
        if normalized_status == "pending":
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = 'pending', error_log = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (status, error_log, task_id, task_id),
            )
        elif normalized_status == "cancelled":
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = 'cancelled', error_log = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (status, error_log, task_id, task_id),
            )
        elif normalized_status == "failed":
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    current_stage = CASE
                        WHEN COALESCE(current_stage, '') IN ('', 'pending', 'job_dispatch', 'job_control')
                        THEN 'failed'
                        ELSE current_stage
                    END,
                    error_log = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (status, error_log, task_id, task_id),
            )
        elif normalized_status == "completed":
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    current_stage = CASE
                        WHEN COALESCE(current_stage, '') IN ('', 'pending', 'job_dispatch', 'job_control')
                        THEN CASE WHEN job_type = 'train' THEN 'train_register_model' ELSE 'cover_mix' END
                        ELSE current_stage
                    END,
                    error_log = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (status, error_log, task_id, task_id),
            )
        else:
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, error_log = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (status, error_log, task_id, task_id),
            )
        task_cursor = conn.execute(
            "UPDATE tasks SET status = ?, error_log = ? WHERE task_id = ?",
            (status, error_log, task_id),
        )
        conn.commit()
        ok = (job_cursor.rowcount > 0) or (task_cursor.rowcount > 0)
        if ok:
            print(f"[OK] 任务状态: {task_id} -> {status}")
            if normalized_status in {"completed", "failed", "cancelled"}:
                _schedule_file_lifecycle_cleanup()
        else:
            print(f"[WARN] 任务不存在: {task_id}")
        return ok
    finally:
        conn.close()


def _status_to_stage(status: str) -> str:
    return {
        "pending": "pending",
        "processing": "cover_split",
        "分离中": "cover_split",
        "修音中": "cover_pitch",
        "变声中": "cover_voice",
        "混音中": "cover_mix",
        "切片中": "train_preprocess",
        "训练中": "train_core",
        "完成": "done",
        "失败": "failed",
    }.get(status, status)


def get_task(task_id: str) -> dict | None:
    """查询单个任务完整信息"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_voice_asset(model_id: str) -> dict | None:
    """查询单个音色资产"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM voice_assets WHERE model_id = ?", (model_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_all_voice_assets() -> list[dict]:
    """查询全部音色资产"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM voice_assets ORDER BY rowid"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_next_pending_compute_task() -> dict | None:
    """按创建顺序取出下一个待执行的算力任务。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = 'pending'
              AND compute_ready = 1
            ORDER BY datetime(created_at) ASC, rowid ASC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def reserve_compute_slot(task_id: str, task_type: str, start_status: str, model_id: str = "") -> bool:
    """
    争抢全局唯一算力槽。

    成功时会把任务状态直接推进到对应的起始工作态，并锁定 mutex；
    失败时保留 pending，让任务留在队列中。
    """
    with _mutex_lock:
        conn = get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            mutex = conn.execute(
                "SELECT owner_task_id, owner_status FROM compute_mutex WHERE mutex_name = ?",
                (COMPUTE_MUTEX_NAME,),
            ).fetchone()
            active = conn.execute(
                """
                SELECT job_id
                FROM jobs
                WHERE status IN ({})
                  AND (job_id != ? AND COALESCE(legacy_task_id, '') != ?)
                LIMIT 1
                """.format(",".join("?" for _ in ACTIVE_COMPUTE_STATUSES)),
                tuple(ACTIVE_COMPUTE_STATUSES) + (task_id, task_id),
            ).fetchone()

            if (mutex and mutex["owner_task_id"]) or active:
                conn.rollback()
                return False

            if model_id:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, current_stage = ?, job_type = ?, voice_model_id = ?,
                        compute_ready = 1, error_log = '', updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                    """,
                    (start_status, _status_to_stage(start_status), task_type, model_id, task_id, task_id),
                )
                conn.execute(
                    "UPDATE tasks SET status = ?, task_type = ?, model_id = ?, compute_ready = 1, error_log = '' WHERE task_id = ?",
                    (start_status, task_type, model_id, task_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, current_stage = ?, job_type = ?, compute_ready = 1,
                        error_log = '', updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                    """,
                    (start_status, _status_to_stage(start_status), task_type, task_id, task_id),
                )
                conn.execute(
                    "UPDATE tasks SET status = ?, task_type = ?, compute_ready = 1, error_log = '' WHERE task_id = ?",
                    (start_status, task_type, task_id),
                )

            if conn.total_changes <= 0:
                conn.rollback()
                return False

            conn.execute(
                """
                UPDATE compute_mutex
                SET owner_task_id = ?, owner_task_type = ?, owner_status = ?, locked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE mutex_name = ?
                """,
                (task_id, task_type, start_status, COMPUTE_MUTEX_NAME),
            )
            conn.commit()
            print(f"[Mutex] 已锁定算力槽: {task_id} [{task_type}] -> {start_status}")
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def release_compute_slot(task_id: str) -> None:
    """释放全局算力槽。"""
    with _mutex_lock:
        conn = get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT owner_task_id FROM compute_mutex WHERE mutex_name = ?",
                (COMPUTE_MUTEX_NAME,),
            ).fetchone()
            if row and row["owner_task_id"] == task_id:
                conn.execute(
                    """
                    UPDATE compute_mutex
                    SET owner_task_id = '', owner_task_type = '', owner_status = '',
                        locked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE mutex_name = ?
                    """,
                    (COMPUTE_MUTEX_NAME,),
                )
                conn.commit()
                print(f"[Mutex] 已释放算力槽: {task_id}")
            else:
                conn.rollback()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def recover_stale_compute_state() -> int:
    """
    启动时回收上一次进程遗留的 active 状态和互斥锁。

    由于本系统是单进程调度，服务重启后历史 active 状态只会阻塞队列，
    因此统一回收为 pending，等待调度器重新派发。
    """
    with _mutex_lock:
        conn = get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            active_jobs = conn.execute(
                """
                SELECT job_id, job_type
                FROM jobs
                WHERE status IN ({})
                """.format(",".join("?" for _ in ACTIVE_COMPUTE_STATUSES)),
                tuple(ACTIVE_COMPUTE_STATUSES),
            ).fetchall()
            job_affected = 0
            blocked_train_jobs: list[str] = []
            duplicate_guard_message = (
                "检测到服务重启时核心训练未闭合，已阻止自动重复派发。"
                "请人工确认 RVC 训练进程或 checkpoint 后再处理。"
            )
            for row in active_jobs:
                job_id = row["job_id"]
                if row["job_type"] == "train" and _has_unclosed_stage(conn, job_id, "train_core"):
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = '失败',
                            current_stage = 'train_core',
                            error_log = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE job_id = ?
                        """,
                        (duplicate_guard_message, job_id),
                    )
                    conn.execute(
                        "UPDATE tasks SET status = '失败', error_log = ? WHERE task_id = ?",
                        (duplicate_guard_message, job_id),
                    )
                    blocked_train_jobs.append(job_id)
                else:
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = 'pending',
                            current_stage = 'pending',
                            error_log = '',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE job_id = ?
                        """,
                        (job_id,),
                    )
                    conn.execute(
                        "UPDATE tasks SET status = 'pending', error_log = '' WHERE task_id = ?",
                        (job_id,),
                    )
                job_affected += 1
            conn.execute(
                """
                UPDATE compute_mutex
                SET owner_task_id = '', owner_task_type = '', owner_status = '',
                    locked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE mutex_name = ?
                """,
                (COMPUTE_MUTEX_NAME,),
            )
            conn.commit()
            task_affected = job_affected
            affected = job_affected
            print(
                "[Mutex] 启动恢复完成，"
                f"回收 tasks={task_affected}, jobs={job_affected}, "
                f"blocked_train_core={len(blocked_train_jobs)}"
            )
            return affected
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _has_unclosed_stage(conn, job_id: str, stage_name: str) -> bool:
    rows = conn.execute(
        """
        SELECT status
        FROM job_stage_logs
        WHERE job_id = ? AND stage_name = ?
        ORDER BY datetime(created_at), rowid
        """,
        (job_id, stage_name),
    ).fetchall()
    return bool(rows and rows[-1]["status"] == "started")


def _schedule_file_lifecycle_cleanup() -> None:
    """终态触发时，异步挂起一次文件生命周期清理。"""
    if not _cleanup_lock.acquire(blocking=False):
        return

    def _worker():
        try:
            file_lifecycle_cleanup()
        except Exception as exc:
            print(f"[Cleanup] 后台清理跳过: {exc}")
        finally:
            _cleanup_lock.release()

    threading.Thread(target=_worker, daemon=True).start()


def file_lifecycle_cleanup(days: int = 7) -> dict:
    """
    清理超过 days 天的历史翻唱输出中间体。

    仅删除中间体，不触碰最终母带：
      - vocal.wav / instrumental.wav
      - fixed.wav / transformed.wav
      - vocal_fixed.wav / vocal_transformed.wav

    严禁触碰 final_master.wav 和数据库记录。
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    candidates = _collect_lifecycle_cleanup_ids(cutoff)

    deleted = 0
    scanned = 0
    try:
        from ..services.lifecycle_service import mark_job_transient_artifacts_purged
    except ImportError:
        from services.lifecycle_service import mark_job_transient_artifacts_purged

    for task_id in candidates:
        task_dir = os.path.join(OUTPUT_ROOT, task_id)
        if not os.path.isdir(task_dir):
            continue
        scanned += 1
        removed_paths: list[str] = []
        for name in LIFECYCLE_DELETE_FILENAMES:
            path = os.path.join(task_dir, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    deleted += 1
                    removed_paths.append(path)
                    print(f"[Cleanup] 已删除: {path}")
                except Exception as exc:
                    print(f"[Cleanup] 删除失败 {path}: {exc}")
        if removed_paths:
            try:
                mark_job_transient_artifacts_purged(task_id, deleted_paths=removed_paths)
            except Exception as exc:
                print(f"[Cleanup] lifecycle 标记失败 {task_id}: {exc}")

    print(f"[Cleanup] 盘点完成: 扫描 {scanned} 个任务, 清理 {deleted} 个中间文件")
    return {"scanned_tasks": scanned, "deleted_files": deleted}


def _collect_lifecycle_cleanup_ids(cutoff: str) -> list[str]:
    """Merge legacy tasks.task_id and jobs.job_id candidates, deduplicated in order."""
    seen: set[str] = set()
    ordered: list[str] = []
    try:
        task_rows = _query_old_tasks(cutoff)
    except Exception as exc:
        print(f"[Cleanup] legacy tasks 查询跳过: {exc}")
        task_rows = []
    for row in task_rows:
        task_id = row["task_id"]
        if task_id not in seen:
            seen.add(task_id)
            ordered.append(task_id)
    try:
        cover_job_ids = _query_old_cover_jobs(cutoff)
    except Exception as exc:
        print(f"[Cleanup] cover jobs 查询跳过: {exc}")
        cover_job_ids = []
    for job_id in cover_job_ids:
        if job_id not in seen:
            seen.add(job_id)
            ordered.append(job_id)
    return ordered


def _query_old_tasks(cutoff: str) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        if not _table_exists(conn, "tasks"):
            return []
        rows = conn.execute(
            """
            SELECT task_id
            FROM tasks
            WHERE datetime(created_at) < datetime(?)
              AND task_type = 'cover'
              AND status IN ('完成', '失败')
            ORDER BY datetime(created_at) ASC, rowid ASC
            """,
            (cutoff,),
        ).fetchall()
        return rows
    finally:
        conn.close()


def _query_old_cover_jobs(cutoff: str) -> list[str]:
    """Old terminal cover jobs from jobs table (jobs-only path uses job_id as output dir)."""
    conn = get_connection()
    try:
        if not _table_exists(conn, "jobs"):
            return []
        rows = conn.execute(
            """
            SELECT job_id, status
            FROM jobs
            WHERE datetime(created_at) < datetime(?)
              AND job_type = 'cover'
            ORDER BY datetime(created_at) ASC, rowid ASC
            """,
            (cutoff,),
        ).fetchall()
        return [
            row["job_id"]
            for row in rows
            if _normalize_status(row["status"]) in {"completed", "failed", "cancelled"}
        ]
    finally:
        conn.close()


# ── 种子数据 & 冒烟测试 ──────────────────────────────


def seed_default_data():
    """插入初代音色"""
    add_voice_asset(
        model_id="v_001",
        model_name="肥鲨test001代",
        pth_path="shared_data/weights/feishark_test001.pth",
        index_path="shared_data/weights/feishark_test001.index",
        default_pitch=-12,
    )


def smoke_test():
    """冒烟测试：创建任务 -> 打印全表 -> 更新状态 -> 再打印"""
    init_db()
    create_task("test_001", "shared_data/uploads/suno_test.wav")
    create_train_task("train_test_001", "测试音色", "shared_data/uploads/dry_vocal.wav")
    update_task_status("test_001", "processing")

    conn = get_connection()
    try:
        print("\n=== 音色资产 ===")
        for r in conn.execute("SELECT * FROM voice_assets"):
            print(f"  {r['model_id']} | {r['model_name']} | pitch={r['default_pitch']}")

        print("\n=== 任务队列 ===")
        for r in conn.execute("SELECT * FROM tasks"):
            print(f"  {r['task_id']} | type={r['task_type']} | {r['status']} | voice={r['voice_name']} | {r['created_at']}")

        print("\n[OK] 冒烟测试通过")
    finally:
        conn.close()


if __name__ == "__main__":
    smoke_test()
