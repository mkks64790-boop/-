from __future__ import annotations


def _create_track(client):
    batch = client.post("/api/batches", json={"batch_name": "Lyrics API Batch"}).json()
    batch_id = batch["batch_id"]
    import_resp = client.post(
        f"/api/batches/{batch_id}/tracks/import",
        data={
            "titles_json": '["Lyrics API Track"]',
            "artist": "API Artist",
            "metadata_json": '{"source":"pytest"}',
        },
        files=[("files", ("lyrics-api.wav", b"lyrics-api", "audio/wav"))],
    )
    assert import_resp.status_code == 200
    return import_resp.json()["imported_tracks"][0]["track_id"]


def test_lyrics_extract_align_versions_promote(client):
    track_id = _create_track(client)

    extract_resp = client.post(
        f"/api/tracks/{track_id}/lyrics/extract",
        json={"lyric_text": "Alpha\nBeta", "source": "api_test"},
    )
    assert extract_resp.status_code == 200
    extract_payload = extract_resp.json()
    document = extract_payload["lyric_document"]
    assert document["track_id"] == track_id

    align_resp = client.post(
        f"/api/tracks/{track_id}/lyrics/align",
        json={"lyric_document_id": document["lyric_document_id"], "engine": "api_align_v1"},
    )
    assert align_resp.status_code == 200
    align_payload = align_resp.json()
    assert align_payload["current_timeline_version_id"]
    assert len(align_payload["versions"]) == 1

    versions_resp = client.get(f"/api/tracks/{track_id}/lyrics/versions")
    assert versions_resp.status_code == 200
    versions_payload = versions_resp.json()
    assert versions_payload["documents"]
    assert versions_payload["versions"]

    second_align_resp = client.post(
        f"/api/tracks/{track_id}/lyrics/align",
        json={"lyric_text": "Gamma\nDelta", "engine": "api_align_v2"},
    )
    assert second_align_resp.status_code == 200
    second_payload = second_align_resp.json()
    assert len(second_payload["versions"]) == 2
    old_version_id = next(item["timeline_id"] for item in second_payload["versions"] if item["timeline_id"] != second_payload["current_timeline_version_id"])

    promote_resp = client.post(f"/api/tracks/{track_id}/lyrics/{old_version_id}/promote")
    assert promote_resp.status_code == 200
    promoted = promote_resp.json()
    assert promoted["current_timeline_version_id"] == old_version_id

    track_resp = client.get(f"/api/tracks/{track_id}")
    assert track_resp.status_code == 200
    track_detail = track_resp.json()
    assert track_detail["lyrics"]["current_timeline_version_id"] == old_version_id
