import json
import uuid

try:
    from ..db import get_connection
except ImportError:
    from db import get_connection


def log_stage(job_id: str, stage_name: str, status: str, message: str = "", detail: dict | None = None) -> str:
    stage_updates_current = stage_name not in {"job_dispatch", "job_control"}
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT log_id
            FROM job_stage_logs
            WHERE job_id = ? AND stage_name = ? AND status = ? AND message = ?
            LIMIT 1
            """,
            (job_id, stage_name, status, message),
        ).fetchone()
        if row:
            if stage_updates_current:
                conn.execute(
                    """
                    UPDATE jobs
                    SET current_stage = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                    """,
                    (stage_name, job_id, job_id),
                )
            conn.commit()
            return row["log_id"]

        log_id = f"log_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO job_stage_logs (log_id, job_id, stage_name, status, message, detail_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (log_id, job_id, stage_name, status, message, json.dumps(detail or {}, ensure_ascii=False)),
        )
        if stage_updates_current:
            conn.execute(
                """
                UPDATE jobs
                SET current_stage = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (stage_name, job_id, job_id),
            )
        conn.commit()
        return log_id
    finally:
        conn.close()


def list_stage_logs(job_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM job_stage_logs WHERE job_id = ? ORDER BY datetime(created_at), rowid",
            (job_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
