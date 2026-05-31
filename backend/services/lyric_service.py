from __future__ import annotations

import json
import os
import uuid

try:
    from ..db import PROJECT_ROOT, get_connection
    from .audit_service import record_audit_event
    from .batch_service import get_batch_root
    from .track_service import get_track, set_track_current_lyrics
except ImportError:
    from db import PROJECT_ROOT, get_connection
    from services.audit_service import record_audit_event
    from services.batch_service import get_batch_root
    from services.track_service import get_track, set_track_current_lyrics


def _ensure_lyric_dirs(batch_id: str, track_id: str) -> dict[str, str]:
    root = os.path.join(get_batch_root(batch_id), "tracks", track_id, "lyrics")
    paths = {
        "root": root,
        "documents": os.path.join(root, "documents"),
        "timelines": os.path.join(root, "timelines"),
    }
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
    return paths


def _safe_relpath(path: str) -> str:
    return os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")


def _default_lyric_text(track: dict) -> str:
    title = track.get("title") or track.get("track_id") or "Untitled Track"
    artist = track.get("artist") or "Unknown Artist"
    return "\n".join(
        [
            f"[Title] {title}",
            f"[Artist] {artist}",
            "",
            "This is a staged lyric draft for Milestone 1.",
            "Replace it with reviewed lyrics before publishing.",
        ]
    )


def _split_lines(text: str) -> list[str]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if lines:
        return lines
    fallback = (text or "").replace("。", "\n").replace("，", "\n").replace(",", "\n")
    return [line.strip() for line in fallback.splitlines() if line.strip()] or [text.strip() or "Lyrics draft"]


def _format_lrc_time(seconds: float) -> str:
    total = max(0, float(seconds))
    mins = int(total // 60)
    secs = total % 60
    return f"[{mins:02d}:{secs:05.2f}]"


def _format_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    mins = total_ms // 60_000
    total_ms %= 60_000
    secs = total_ms // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def _format_ass_time(seconds: float) -> str:
    total_cs = max(0, int(round(float(seconds) * 100)))
    hours = total_cs // 360_000
    total_cs %= 360_000
    mins = total_cs // 6_000
    total_cs %= 6_000
    secs = total_cs // 100
    cs = total_cs % 100
    return f"{hours:d}:{mins:02d}:{secs:02d}.{cs:02d}"


def create_lyric_document(
    track_id: str,
    text_content: str,
    *,
    source: str = "manual",
    title: str = "",
    language: str = "zh-CN",
    structure: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    track = get_track(track_id)
    if not track:
        raise ValueError("track_not_found")

    dirs = _ensure_lyric_dirs(track["batch_id"], track_id)
    lyric_document_id = f"lyr_{uuid.uuid4().hex[:10]}"
    document_path = os.path.join(dirs["documents"], f"{lyric_document_id}.txt")
    with open(document_path, "w", encoding="utf-8") as handle:
        handle.write(text_content or "")

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO lyric_documents (
                lyric_document_id, track_id, source, language, title,
                text_content, structure_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lyric_document_id,
                track_id,
                source,
                language,
                title or track.get("title") or "",
                text_content or "",
                json.dumps(structure or {"line_count": len(_split_lines(text_content))}, ensure_ascii=False),
                json.dumps(
                    {
                        **(metadata or {}),
                        "document_path": _safe_relpath(document_path),
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.execute(
            """
            UPDATE tracks
            SET current_lyric_document_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE track_id = ?
            """,
            (lyric_document_id, track_id),
        )
        conn.commit()
    finally:
        conn.close()

    record_audit_event(
        "track",
        track_id,
        "lyrics_document_create",
        {"lyric_document_id": lyric_document_id, "source": source},
    )
    return get_lyric_document(lyric_document_id) or {}


def get_lyric_document(lyric_document_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM lyric_documents WHERE lyric_document_id = ? LIMIT 1",
            (lyric_document_id,),
        ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["structure"] = json.loads(payload["structure_json"] or "{}")
        payload["metadata"] = json.loads(payload["metadata_json"] or "{}")
        return payload
    finally:
        conn.close()


def list_lyric_versions(track_id: str) -> dict:
    conn = get_connection()
    try:
        documents = [dict(row) for row in conn.execute(
            "SELECT * FROM lyric_documents WHERE track_id = ? ORDER BY datetime(created_at) DESC, rowid DESC",
            (track_id,),
        ).fetchall()]
        versions = [dict(row) for row in conn.execute(
            "SELECT * FROM lyric_timeline_versions WHERE track_id = ? ORDER BY datetime(created_at) DESC, rowid DESC",
            (track_id,),
        ).fetchall()]
        track = get_track(track_id)
        return {
            "track_id": track_id,
            "track": track,
            "documents": [
                {**doc, "structure": json.loads(doc["structure_json"] or "{}"), "metadata": json.loads(doc["metadata_json"] or "{}")}
                for doc in documents
            ],
            "versions": [
                {**version, "preview": json.loads(version["preview_json"] or "[]"), "metadata": json.loads(version["metadata_json"] or "{}")}
                for version in versions
            ],
            "current_lyric_document_id": track.get("current_lyric_document_id") if track else "",
            "current_timeline_version_id": track.get("current_timeline_version_id") if track else "",
        }
    finally:
        conn.close()


def extract_lyrics(
    track_id: str,
    *,
    lyric_text: str = "",
    source: str = "stub_extract_v1",
    language: str = "zh-CN",
    title: str = "",
    metadata: dict | None = None,
) -> dict:
    track = get_track(track_id)
    if not track:
        raise ValueError("track_not_found")
    text = lyric_text.strip() or _default_lyric_text(track)
    document = create_lyric_document(
        track_id,
        text,
        source=source,
        title=title or f"{track.get('title') or track_id} - lyrics draft",
        language=language,
        structure={"line_count": len(_split_lines(text)), "kind": "draft"},
        metadata=metadata or {},
    )
    record_audit_event(
        "track",
        track_id,
        "lyrics_extract",
        {"lyric_document_id": document.get("lyric_document_id"), "source": source},
    )
    return {
        "track_id": track_id,
        "lyric_document": document,
        "documents": list_lyric_versions(track_id)["documents"],
        "versions": list_lyric_versions(track_id)["versions"],
    }


def align_lyrics(
    track_id: str,
    *,
    lyric_document_id: str = "",
    lyric_text: str = "",
    engine: str = "stub_align_v1",
    align_mode: str = "balanced_lines",
    line_split_mode: str = "balanced",
    append_outro_card: bool = True,
    metadata: dict | None = None,
) -> dict:
    track = get_track(track_id)
    if not track:
        raise ValueError("track_not_found")

    document = None
    if lyric_document_id:
        document = get_lyric_document(lyric_document_id)
    if not document:
        current_doc_id = track.get("current_lyric_document_id") or ""
        if current_doc_id:
            document = get_lyric_document(current_doc_id)
    if not document and lyric_text.strip():
        document = create_lyric_document(
            track_id,
            lyric_text.strip(),
            source="align_input",
            title=f"{track.get('title') or track_id} - align input",
            metadata=metadata or {},
        )
    if not document:
        document = create_lyric_document(
            track_id,
            _default_lyric_text(track),
            source="align_fallback",
            title=f"{track.get('title') or track_id} - fallback lyrics",
            metadata=metadata or {},
        )

    text = lyric_text.strip() or document.get("text_content") or ""
    lines = _split_lines(text)
    if append_outro_card and not lines[-1].lower().startswith("[outro]"):
        lines.append("[Outro]")

    dirs = _ensure_lyric_dirs(track["batch_id"], track_id)
    version_id = f"tl_{uuid.uuid4().hex[:10]}"
    version_dir = os.path.join(dirs["timelines"], version_id)
    os.makedirs(version_dir, exist_ok=True)
    conn = get_connection()
    try:
        existing_count = conn.execute(
            "SELECT COUNT(*) FROM lyric_timeline_versions WHERE track_id = ?",
            (track_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    total_lines = max(1, len(lines))
    segment_seconds = 4.0
    preview = []
    lrc_lines = []
    srt_lines = []
    ass_events = []
    txt_lines = []
    for index, line in enumerate(lines, start=1):
        start = (index - 1) * segment_seconds
        end = index * segment_seconds
        preview.append({"index": index, "start": round(start, 3), "end": round(end, 3), "text": line})
        lrc_lines.append(f"{_format_lrc_time(start)}{line}")
        srt_lines.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
                    line,
                    "",
                ]
            )
        )
        ass_events.append(
            f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{line}"
        )
        txt_lines.append(line)

    txt_path = os.path.join(version_dir, "lyrics.txt")
    lrc_path = os.path.join(version_dir, "lyrics.lrc")
    srt_path = os.path.join(version_dir, "lyrics.srt")
    ass_path = os.path.join(version_dir, "lyrics.ass")

    with open(txt_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(txt_lines))
    with open(lrc_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lrc_lines))
    with open(srt_path, "w", encoding="utf-8") as handle:
        handle.write("\n\n".join(srt_lines).strip() + "\n")
    with open(ass_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: Default,Arial,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,20,1",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
                *ass_events,
                "",
            ]
        ))

    conn = get_connection()
    try:
        conn.execute("UPDATE lyric_timeline_versions SET is_current = 0, updated_at = CURRENT_TIMESTAMP WHERE track_id = ?", (track_id,))
        conn.execute(
            """
            INSERT INTO lyric_timeline_versions (
                timeline_id, track_id, lyric_document_id, engine, align_mode, status,
                version_label, txt_path, lrc_path, srt_path, ass_path, preview_json, metadata_json, is_current
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                version_id,
                track_id,
                document["lyric_document_id"],
                engine,
                align_mode,
                "completed",
                f"v{existing_count + 1:02d}",
                _safe_relpath(txt_path),
                _safe_relpath(lrc_path),
                _safe_relpath(srt_path),
                _safe_relpath(ass_path),
                json.dumps(preview, ensure_ascii=False),
                json.dumps(
                    {
                        **(metadata or {}),
                        "line_split_mode": line_split_mode,
                        "append_outro_card": bool(append_outro_card),
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.execute(
            """
            UPDATE tracks
            SET current_lyric_document_id = ?, current_timeline_version_id = ?, status = 'lyrics_ready', updated_at = CURRENT_TIMESTAMP
            WHERE track_id = ?
            """,
            (document["lyric_document_id"], version_id, track_id),
        )
        conn.commit()
    finally:
        conn.close()

    record_audit_event(
        "track",
        track_id,
        "lyrics_align",
        {"timeline_id": version_id, "lyric_document_id": document["lyric_document_id"], "engine": engine},
    )
    return get_lyric_versions(track_id, version_id)


def get_lyric_versions(track_id: str, current_timeline_id: str | None = None) -> dict:
    payload = list_lyric_versions(track_id)
    if current_timeline_id:
        payload["current_timeline_version_id"] = current_timeline_id
    return payload


def promote_lyric_timeline(track_id: str, timeline_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM lyric_timeline_versions WHERE track_id = ? AND timeline_id = ? LIMIT 1",
            (track_id, timeline_id),
        ).fetchone()
        if not row:
            raise ValueError("timeline_not_found")
        conn.execute("UPDATE lyric_timeline_versions SET is_current = 0, updated_at = CURRENT_TIMESTAMP WHERE track_id = ?", (track_id,))
        conn.execute(
            """
            UPDATE lyric_timeline_versions
            SET is_current = 1, updated_at = CURRENT_TIMESTAMP
            WHERE track_id = ? AND timeline_id = ?
            """,
            (track_id, timeline_id),
        )
        conn.commit()
    finally:
        conn.close()

    track = get_track(track_id) or {}
    document_id = row["lyric_document_id"]
    set_track_current_lyrics(track_id, document_id, timeline_id)
    record_audit_event("track", track_id, "lyrics_promote", {"timeline_id": timeline_id, "lyric_document_id": document_id})
    return get_lyric_versions(track_id, timeline_id)
