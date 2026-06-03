from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from .. import db as backend_db
except ImportError:
    import db as backend_db


ALLOWED_MEMORY_DIRS = (
    Path("docs") / "agent-md" / "worker",
    Path("docs") / "agent-md" / "architect",
    Path("docs") / "agent-md" / "handoff",
)
_MEMORY_TABLE_READY_PATH = ""


def _ensure_memory_table() -> None:
    global _MEMORY_TABLE_READY_PATH
    db_path = str(getattr(backend_db, "DB_PATH", ""))
    if _MEMORY_TABLE_READY_PATH == db_path:
        return
    conn = backend_db.get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS project_memories (
                memory_id     TEXT PRIMARY KEY,
                category      TEXT NOT NULL DEFAULT 'note',
                title         TEXT NOT NULL DEFAULT '',
                summary       TEXT NOT NULL DEFAULT '',
                source_type   TEXT NOT NULL DEFAULT 'manual',
                source_path   TEXT NOT NULL DEFAULT '',
                source_stage  TEXT NOT NULL DEFAULT '',
                tags_json     TEXT DEFAULT '[]',
                importance    INTEGER NOT NULL DEFAULT 50,
                pinned        INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT DEFAULT '{}',
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_project_memories_category_updated
            ON project_memories(category, updated_at);

            CREATE INDEX IF NOT EXISTS idx_project_memories_stage_updated
            ON project_memories(source_stage, updated_at);

            CREATE INDEX IF NOT EXISTS idx_project_memories_pinned_updated
            ON project_memories(pinned, updated_at);
            """
        )
        conn.commit()
        _MEMORY_TABLE_READY_PATH = db_path
    finally:
        conn.close()


def _project_root() -> Path:
    return Path(backend_db.PROJECT_ROOT).resolve()


def _json_dumps(value: Any, fallback: Any) -> str:
    if value is None:
        value = fallback
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(raw: str, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _memory_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"mem_{digest}"


def _safe_rel_source_path(path: str) -> str:
    value = (path or "").strip()
    if not value:
        return ""

    root = _project_root()
    candidate = Path(value)
    abs_path = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    allowed_roots = [(root / rel).resolve() for rel in ALLOWED_MEMORY_DIRS]
    if not any(abs_path == allowed or allowed in abs_path.parents for allowed in allowed_roots):
        raise ValueError("memory_source_path_not_allowed")
    if abs_path.suffix.lower() != ".md":
        raise ValueError("memory_source_path_must_be_markdown")
    return abs_path.relative_to(root).as_posix()


def _row_to_memory(row) -> dict:
    payload = dict(row)
    payload["tags"] = _json_loads(payload.pop("tags_json", "[]"), [])
    payload["metadata"] = _json_loads(payload.pop("metadata_json", "{}"), {})
    payload["pinned"] = bool(payload.get("pinned"))
    return payload


def upsert_memory(
    *,
    memory_id: str = "",
    category: str = "note",
    title: str,
    summary: str = "",
    source_type: str = "manual",
    source_path: str = "",
    source_stage: str = "",
    tags: list[str] | None = None,
    importance: int = 50,
    pinned: bool = False,
    metadata: dict | None = None,
) -> dict:
    _ensure_memory_table()
    safe_source_path = _safe_rel_source_path(source_path) if source_path else ""
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("memory_title_required")

    clean_category = (category or "note").strip() or "note"
    clean_source_type = (source_type or "manual").strip() or "manual"
    clean_stage = (source_stage or "").strip()
    clean_summary = (summary or "").strip()
    clean_tags = sorted({str(tag).strip() for tag in (tags or []) if str(tag).strip()})
    clean_importance = max(0, min(100, int(importance or 0)))
    clean_metadata = metadata or {}
    resolved_id = memory_id.strip() if memory_id else _memory_id(clean_category, clean_source_type, safe_source_path, clean_title)

    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO project_memories (
                memory_id, category, title, summary, source_type, source_path,
                source_stage, tags_json, importance, pinned, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                category = excluded.category,
                title = excluded.title,
                summary = excluded.summary,
                source_type = excluded.source_type,
                source_path = excluded.source_path,
                source_stage = excluded.source_stage,
                tags_json = excluded.tags_json,
                importance = excluded.importance,
                pinned = excluded.pinned,
                metadata_json = excluded.metadata_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                resolved_id,
                clean_category,
                clean_title,
                clean_summary,
                clean_source_type,
                safe_source_path,
                clean_stage,
                _json_dumps(clean_tags, []),
                clean_importance,
                1 if pinned else 0,
                _json_dumps(clean_metadata, {}),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_memory(resolved_id) or {}


def patch_memory(memory_id: str, updates: dict) -> dict | None:
    current = get_memory(memory_id)
    if not current:
        return None
    return upsert_memory(
        memory_id=memory_id,
        category=updates.get("category", current["category"]),
        title=updates.get("title", current["title"]),
        summary=updates.get("summary", current["summary"]),
        source_type=updates.get("source_type", current["source_type"]),
        source_path=updates.get("source_path", current["source_path"]),
        source_stage=updates.get("source_stage", current["source_stage"]),
        tags=updates.get("tags", current.get("tags") or []),
        importance=updates.get("importance", current["importance"]),
        pinned=updates.get("pinned", current["pinned"]),
        metadata=updates.get("metadata", current.get("metadata") or {}),
    )


def get_memory(memory_id: str) -> dict | None:
    _ensure_memory_table()
    conn = backend_db.get_connection()
    try:
        row = conn.execute("SELECT * FROM project_memories WHERE memory_id = ? LIMIT 1", (memory_id,)).fetchone()
        return _row_to_memory(row) if row else None
    finally:
        conn.close()


def list_memories(
    *,
    category: str = "",
    tag: str = "",
    q: str = "",
    pinned: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    _ensure_memory_table()
    query = "SELECT * FROM project_memories WHERE 1=1"
    params: list[Any] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if tag:
        query += " AND tags_json LIKE ?"
        params.append(f"%{tag}%")
    if pinned is not None:
        query += " AND pinned = ?"
        params.append(1 if pinned else 0)
    if q:
        like = f"%{q}%"
        query += " AND (title LIKE ? OR summary LIKE ? OR source_stage LIKE ? OR source_path LIKE ?)"
        params.extend([like, like, like, like])
    query += " ORDER BY pinned DESC, importance DESC, datetime(updated_at) DESC, rowid DESC LIMIT ? OFFSET ?"
    params.extend([max(1, min(int(limit or 50), 200)), max(0, int(offset or 0))])

    conn = backend_db.get_connection()
    try:
        rows = conn.execute(query, tuple(params)).fetchall()
        return [_row_to_memory(row) for row in rows]
    finally:
        conn.close()


def memory_summary() -> dict:
    _ensure_memory_table()
    conn = backend_db.get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM project_memories").fetchone()[0]
        pinned = conn.execute("SELECT COUNT(*) FROM project_memories WHERE pinned = 1").fetchone()[0]
        categories = [
            {"category": row[0], "count": row[1]}
            for row in conn.execute(
                "SELECT category, COUNT(*) FROM project_memories GROUP BY category ORDER BY COUNT(*) DESC, category"
            ).fetchall()
        ]
        stages = [
            {"source_stage": row[0], "count": row[1]}
            for row in conn.execute(
                """
                SELECT source_stage, COUNT(*)
                FROM project_memories
                WHERE source_stage != ''
                GROUP BY source_stage
                ORDER BY MAX(datetime(updated_at)) DESC, COUNT(*) DESC
                LIMIT 10
                """
            ).fetchall()
        ]
        recent = [
            _row_to_memory(row)
            for row in conn.execute(
                """
                SELECT *
                FROM project_memories
                ORDER BY datetime(updated_at) DESC, rowid DESC
                LIMIT 5
                """
            ).fetchall()
        ]
    finally:
        conn.close()
    return {
        "total_count": total,
        "pinned_count": pinned,
        "categories": categories,
        "recent_stages": stages,
        "recent": recent,
    }


def _extract_stage(rel_path: str, content: str) -> str:
    text = f"{rel_path}\n{content[:500]}"
    match = re.search(r"stage[-_\s]*(\d+[a-zA-Z]?)", text, re.IGNORECASE)
    return f"Stage{match.group(1).upper()}" if match else ""


def _extract_title(path: Path, content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:160] or path.stem
    return path.stem


def _extract_summary(content: str, max_chars: int = 520) -> str:
    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
        if len(" ".join(lines)) >= max_chars:
            break
    return " ".join(lines)[:max_chars]


def _category_for_rel_path(rel_path: str) -> str:
    if "/worker/" in rel_path:
        return "agent_report"
    if "/architect/" in rel_path:
        return "architect_prompt"
    if "/handoff/" in rel_path:
        return "handoff"
    return "agent_md"


def _tags_for(rel_path: str, stage: str, content: str) -> list[str]:
    tags = {"agent-md"}
    if stage:
        tags.add(stage.lower())
    lower = f"{rel_path}\n{content[:2000]}".lower()
    for keyword in ["uvr", "cover", "train", "training", "studio", "factory", "memory", "stage47"]:
        if keyword in lower:
            tags.add(keyword)
    if "/worker/" in rel_path:
        tags.add("report")
    if "/architect/" in rel_path:
        tags.add("prompt")
    if "/handoff/" in rel_path:
        tags.add("handoff")
    return sorted(tags)


def _importance_for(category: str, stage: str, content: str) -> int:
    score = 55
    if category == "agent_report":
        score += 10
    if stage in {"Stage47A", "Stage47B", "Stage46B"}:
        score += 15
    lower = content.lower()
    if "pass" in lower or "block_training=false" in lower or "v_d4d7e1c1" in lower:
        score += 10
    return min(score, 95)


def _ingest_report_file(path: Path) -> list[dict]:
    root = _project_root()
    rel_path = path.resolve().relative_to(root).as_posix()
    content = path.read_text(encoding="utf-8", errors="replace")
    stage = _extract_stage(rel_path, content)
    category = _category_for_rel_path(rel_path)
    title = _extract_title(path, content)
    summary = _extract_summary(content)
    tags = _tags_for(rel_path, stage, content)
    stat = path.stat()
    memories = [
        upsert_memory(
            memory_id=_memory_id("report", rel_path),
            category=category,
            title=title,
            summary=summary,
            source_type="agent_md_report",
            source_path=rel_path,
            source_stage=stage,
            tags=tags,
            importance=_importance_for(category, stage, content),
            pinned=False,
            metadata={
                "file_name": path.name,
                "size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
                "ingest_mode": "summary_only",
            },
        )
    ]
    memories.extend(_extract_key_fact_memories(rel_path, stage, content))
    return memories


def _extract_key_fact_memories(rel_path: str, stage: str, content: str) -> list[dict]:
    facts: list[dict] = []
    lower = content.lower()
    if "block_training=false" in lower:
        facts.append(
            {
                "title": "UVR duration fixed: BLOCK_TRAINING=false",
                "summary": "Latest separation acceptance indicates UVR duration preservation is unblocked and training is allowed.",
                "tags": ["uvr", "blocker", "training", "stage45r", "stage46b"],
            }
        )
    if "v_d4d7e1c1" in content or "朱朱_stage47_single_long" in content:
        facts.append(
            {
                "title": "Stage47 real model: v_d4d7e1c1 / 朱朱_stage47_single_long",
                "summary": "Stage47A real single-long training produced usable local model v_d4d7e1c1 with real pth and index artifacts.",
                "tags": ["stage47", "stage47a", "train", "model"],
            }
        )
    if "task_b2272d133fff" in content:
        facts.append(
            {
                "title": "Stage47 cover smoke: task_b2272d133fff",
                "summary": "Stage47A trained-model cover smoke completed with Studio-readable final_master.wav and UVR duration ratio 1.000.",
                "tags": ["stage47", "stage47a", "cover", "studio"],
            }
        )

    result = []
    for fact in facts:
        result.append(
            upsert_memory(
                memory_id=_memory_id("fact", rel_path, fact["title"]),
                category="key_fact",
                title=fact["title"],
                summary=fact["summary"],
                source_type="agent_md_report",
                source_path=rel_path,
                source_stage=stage,
                tags=fact["tags"],
                importance=95,
                pinned=True,
                metadata={"derived_from": rel_path, "ingest_mode": "key_fact"},
            )
        )
    return result


def rescan_agent_reports() -> dict:
    root = _project_root()
    scanned_files = 0
    upserted_ids: set[str] = set()
    errors: list[dict] = []
    for rel_dir in ALLOWED_MEMORY_DIRS:
        abs_dir = (root / rel_dir).resolve()
        if not abs_dir.exists():
            continue
        if root not in abs_dir.parents and abs_dir != root:
            errors.append({"path": rel_dir.as_posix(), "error": "directory_outside_project"})
            continue
        for path in sorted(abs_dir.glob("*.md")):
            try:
                scanned_files += 1
                for memory in _ingest_report_file(path):
                    upserted_ids.add(memory["memory_id"])
            except Exception as exc:
                errors.append({"path": path.relative_to(root).as_posix(), "error": str(exc)})
    return {
        "ok": not errors,
        "scanned_files": scanned_files,
        "upserted_count": len(upserted_ids),
        "errors": errors,
        "summary": memory_summary(),
    }
