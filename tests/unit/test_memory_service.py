from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.memory_service import list_memories, memory_summary, rescan_agent_reports, upsert_memory


def _write_stage47_report(root: Path) -> Path:
    report_dir = root / "docs" / "agent-md" / "worker"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / "stage-47a-real-single-long-training-cover-closure-report.md"
    report.write_text(
        "\n".join(
            [
                "# Stage 47A Real Single Long Training + Cover Closure Report",
                "- Stage47 real model: v_d4d7e1c1 / 朱朱_stage47_single_long",
                "- Stage47 cover smoke: task_b2272d133fff",
                "- UVR duration fixed: BLOCK_TRAINING=false",
            ]
        ),
        encoding="utf-8",
    )
    return report


def test_rescan_agent_reports_indexes_stage47_key_facts(isolated_backend):
    _write_stage47_report(isolated_backend)

    result = rescan_agent_reports()

    assert result["ok"] is True
    assert result["scanned_files"] == 1
    assert result["upserted_count"] >= 4

    model_hits = list_memories(q="v_d4d7e1c1", limit=20)
    assert any(item["category"] == "key_fact" for item in model_hits)
    assert any("朱朱_stage47_single_long" in item["title"] for item in model_hits)

    cover_hits = list_memories(q="task_b2272d133fff", limit=20)
    assert any("cover smoke" in item["title"] for item in cover_hits)

    summary = memory_summary()
    assert summary["total_count"] >= 4
    assert summary["pinned_count"] >= 3


def test_manual_memory_rejects_source_path_outside_allowed_dirs(isolated_backend):
    outside = isolated_backend / "README.md"
    outside.write_text("outside", encoding="utf-8")

    with pytest.raises(ValueError, match="memory_source_path_not_allowed"):
        upsert_memory(
            category="decision",
            title="Unsafe source",
            summary="should fail",
            source_path=str(outside),
        )
