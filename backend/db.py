"""
FeiShark Studio - 数据库模块
轻量解耦方案：任务队列 + 模型资产管理

支持双任务类型:
  - cover: AI 翻唱任务（分离→修音→变声→混音）
  - train: 音色训练任务（切片→训练→入库）
"""

import os
import sqlite3
import threading
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "feishark.db")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_DIR = os.path.join(PROJECT_ROOT, "shared_data", "weights")
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "outputs")
JOBS_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "jobs")

ACTIVE_COMPUTE_STATUSES = {
    "分离中",
    "修音中",
    "变声中",
    "混音中",
    "切片中",
    "训练中",
    "processing",
}
TERMINAL_STATUSES = {"完成", "失败", "已取消"}
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


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，启用 WAL 模式和外键约束"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，创建基础表（兼容旧数据自动迁移）"""
    conn = get_connection()
    try:
        conn.executescript("""
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
                strategy_key   TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'pending',
                current_stage  TEXT DEFAULT '',
                compute_ready  INTEGER NOT NULL DEFAULT 0,
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
                metadata_json  TEXT DEFAULT '{}',
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_job_id) REFERENCES jobs(job_id)
            );
        """)

        # 兼容迁移：旧表缺少 task_type 和 voice_name 时自动添加
        _migrate_add_column(conn, "tasks", "task_type", "TEXT NOT NULL DEFAULT 'cover'")
        _migrate_add_column(conn, "tasks", "voice_name", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "tasks", "model_id", "TEXT DEFAULT ''")
        _migrate_add_column(conn, "tasks", "compute_ready", "INTEGER NOT NULL DEFAULT 0")

        conn.execute(
            "INSERT OR IGNORE INTO compute_mutex (mutex_name, owner_task_id, owner_task_type, owner_status) "
            "VALUES (?, '', '', '')",
            (COMPUTE_MUTEX_NAME,),
        )
        _dedupe_new_tables(conn)
        _create_unique_indexes(conn)
        _backfill_legacy_jobs(conn)
        _backfill_legacy_voice_models(conn)
        _backfill_job_current_stages(conn)
        conn.commit()

        # 确保权重目录存在
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        os.makedirs(JOBS_ROOT, exist_ok=True)

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
        """
    )


def _backfill_legacy_jobs(conn):
    conn.execute(
        """
        INSERT OR IGNORE INTO jobs (
            job_id, legacy_task_id, job_type, strategy_key, status, current_stage,
            compute_ready, voice_model_id, voice_name, input_path, output_root,
            error_log, metadata_json, created_at, updated_at
        )
        SELECT
            task_id,
            task_id,
            CASE WHEN task_type = 'train' THEN 'train' ELSE 'cover' END,
            CASE
                WHEN task_type = 'train' THEN 'legacy_train'
                WHEN task_type = 'cover' THEN 'cover_strategy'
                ELSE 'legacy_import'
            END,
            status,
            ?,
            compute_ready,
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


def _backfill_legacy_voice_models(conn):
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


def _backfill_job_current_stages(conn):
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


def add_voice_asset(model_id, model_name, pth_path, index_path, default_pitch=0, source_job_id: str = "") -> bool:
    """添加音色资产到知识库"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO voice_assets (model_id, model_name, pth_path, index_path, default_pitch) "
            "VALUES (?, ?, ?, ?, ?)",
            (model_id, model_name, pth_path, index_path, default_pitch),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO voice_models (
                voice_model_id, legacy_model_id, model_name, source_job_id,
                pth_path, index_path, default_pitch, status, metadata_json,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, COALESCE(NULLIF(?, ''), (SELECT source_job_id FROM voice_models WHERE voice_model_id = ?), NULL),
                ?, ?, ?, 'ready', '{}',
                COALESCE((SELECT created_at FROM voice_models WHERE voice_model_id = ?), CURRENT_TIMESTAMP),
                CURRENT_TIMESTAMP
            )
            """,
            (model_id, model_id, model_name, source_job_id, model_id, pth_path, index_path, default_pitch, model_id),
        )
        conn.commit()
        ok = True
        if ok:
            print(f"[OK] 音色入库: {model_name} ({model_id})")
        if conn.total_changes == 0:
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
                        job_id, legacy_task_id, job_type, strategy_key, status, current_stage,
                        compute_ready, voice_model_id, voice_name, input_path, output_root,
                        error_log, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, 'cover', 'cover_strategy', 'pending', '', 0, '', '', ?, ?, '', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                    job_id, legacy_task_id, job_type, strategy_key, status, current_stage,
                    compute_ready, voice_model_id, voice_name, input_path, output_root,
                    error_log, metadata_json, created_at, updated_at
                ) VALUES (?, ?, 'train', 'legacy_train', 'pending', '', 0, '', ?, ?, ?, '', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
            SET voice_model_id = ?, job_type = 'cover', strategy_key = 'cover_strategy',
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
            SET job_type = ?, compute_ready = 1, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (task_type, task_id, task_id),
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
        if status == "pending":
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = 'pending', error_log = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (status, error_log, task_id, task_id),
            )
        elif status == "已取消":
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, current_stage = 'cancelled', error_log = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (status, error_log, task_id, task_id),
            )
        elif status in TERMINAL_STATUSES:
            job_cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, error_log = ?, updated_at = CURRENT_TIMESTAMP
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
            if status in TERMINAL_STATUSES:
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
            task_affected = conn.execute(
                """
                UPDATE tasks
                SET status = 'pending', error_log = ''
                WHERE status IN ({})
                """.format(",".join("?" for _ in ACTIVE_COMPUTE_STATUSES)),
                tuple(ACTIVE_COMPUTE_STATUSES),
            ).rowcount
            job_affected = conn.execute(
                """
                UPDATE jobs
                SET status = 'pending',
                    current_stage = 'pending',
                    error_log = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ({})
                """.format(",".join("?" for _ in ACTIVE_COMPUTE_STATUSES)),
                tuple(ACTIVE_COMPUTE_STATUSES),
            ).rowcount
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
            affected = max(task_affected, job_affected)
            print(f"[Mutex] 启动恢复完成，回收 tasks={task_affected}, jobs={job_affected}")
            return affected
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _schedule_file_lifecycle_cleanup() -> None:
    """终态触发时，异步挂起一次文件生命周期清理。"""
    if not _cleanup_lock.acquire(blocking=False):
        return

    def _worker():
        try:
            file_lifecycle_cleanup()
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
    candidates = [
        row["task_id"]
        for row in _query_old_tasks(cutoff)
    ]

    deleted = 0
    scanned = 0
    for task_id in candidates:
        task_dir = os.path.join(OUTPUT_ROOT, task_id)
        if not os.path.isdir(task_dir):
            continue
        scanned += 1
        for name in LIFECYCLE_DELETE_FILENAMES:
            path = os.path.join(task_dir, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    deleted += 1
                    print(f"[Cleanup] 已删除: {path}")
                except Exception as exc:
                    print(f"[Cleanup] 删除失败 {path}: {exc}")

    print(f"[Cleanup] 盘点完成: 扫描 {scanned} 个任务, 清理 {deleted} 个中间文件")
    return {"scanned_tasks": scanned, "deleted_files": deleted}


def _query_old_tasks(cutoff: str) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
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
