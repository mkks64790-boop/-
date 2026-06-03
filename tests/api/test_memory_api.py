from __future__ import annotations


def _seed_report(root):
    report_dir = root / "docs" / "agent-md" / "worker"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "stage-47a-real-single-long-training-cover-closure-report.md").write_text(
        "\n".join(
            [
                "# Stage 47A Real Single Long Training + Cover Closure Report",
                "Stage47 real model: v_d4d7e1c1 / 朱朱_stage47_single_long",
                "Stage47 cover smoke: task_b2272d133fff",
                "UVR duration fixed: BLOCK_TRAINING=false",
            ]
        ),
        encoding="utf-8",
    )


def test_memory_rescan_summary_search_and_patch(client, isolated_backend):
    _seed_report(isolated_backend)

    rescan_resp = client.post("/api/memory/rescan")
    assert rescan_resp.status_code == 200
    rescan = rescan_resp.json()
    assert rescan["ok"] is True
    assert rescan["scanned_files"] == 1
    assert rescan["upserted_count"] >= 4

    summary_resp = client.get("/api/memory/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_count"] >= 4
    assert summary["pinned_count"] >= 3

    search_resp = client.get("/api/memory?q=v_d4d7e1c1&limit=20")
    assert search_resp.status_code == 200
    hits = search_resp.json()["items"]
    assert any("Stage47 real model" in item["title"] for item in hits)

    create_resp = client.post(
        "/api/memory",
        json={
            "category": "decision",
            "title": "Local-only Memory Lab",
            "summary": "Do not call external AI or upload project reports.",
            "tags": ["memory", "constraint"],
            "importance": 88,
            "pinned": True,
        },
    )
    assert create_resp.status_code == 200
    memory = create_resp.json()
    assert memory["category"] == "decision"
    assert memory["pinned"] is True

    patch_resp = client.patch(f"/api/memory/{memory['memory_id']}", json={"importance": 90, "pinned": False})
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["importance"] == 90
    assert patched["pinned"] is False


def test_memory_post_rejects_unsafe_source_path(client, isolated_backend):
    unsafe_path = isolated_backend / "README.md"
    unsafe_path.write_text("outside allowed memory dirs", encoding="utf-8")

    resp = client.post(
        "/api/memory",
        json={
            "category": "note",
            "title": "Unsafe",
            "source_path": str(unsafe_path),
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "memory_source_path_not_allowed"
