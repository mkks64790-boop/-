from __future__ import annotations


def test_batches_create_list_detail_and_import(client):
    page_resp = client.get("/factory")
    assert page_resp.status_code == 200
    assert "Release Factory" in page_resp.text

    create_resp = client.post(
        "/api/batches",
        json={"batch_name": "API Batch", "target_platforms": ["douyin", "youtube"]},
    )
    assert create_resp.status_code == 200
    batch = create_resp.json()
    batch_id = batch["batch_id"]

    list_resp = client.get("/api/batches?limit=20&offset=0")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(item["batch_id"] == batch_id for item in items)

    import_resp = client.post(
        f"/api/batches/{batch_id}/tracks/import",
        data={
            "titles_json": '["Track One","Track Two"]',
            "artist": "API Singer",
            "notes": "api import",
            "metadata_json": '{"source":"pytest"}',
        },
        files=[
            ("files", ("track-one.wav", b"track-one", "audio/wav")),
            ("files", ("track-two.mp3", b"track-two", "audio/mpeg")),
        ],
    )
    assert import_resp.status_code == 200
    import_payload = import_resp.json()
    assert import_payload["imported_count"] == 2
    assert len(import_payload["imported_tracks"]) == 2

    detail_resp = client.get(f"/api/batches/{batch_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["batch_id"] == batch_id
    assert detail["track_count"] == 2
    assert len(detail["tracks"]) == 2

    summary_resp = client.get("/api/factory/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["batch_count"] >= 1
    assert summary["track_count"] >= 2
