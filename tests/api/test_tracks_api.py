from __future__ import annotations


def test_track_detail_and_patch(client):
    batch = client.post("/api/batches", json={"batch_name": "Track API Batch"}).json()
    batch_id = batch["batch_id"]
    import_resp = client.post(
        f"/api/batches/{batch_id}/tracks/import",
        data={"titles_json": '["Patch Me"]', "artist": "Initial Artist"},
        files=[("files", ("patch-me.wav", b"patch-me", "audio/wav"))],
    )
    track_id = import_resp.json()["imported_tracks"][0]["track_id"]

    patch_resp = client.patch(
        f"/api/tracks/{track_id}",
        json={"title": "Patched Title", "artist": "Patched Artist", "notes": "edited"},
    )
    assert patch_resp.status_code == 200
    patch_payload = patch_resp.json()
    assert patch_payload["title"] == "Patched Title"
    assert patch_payload["artist"] == "Patched Artist"

    detail_resp = client.get(f"/api/tracks/{track_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["title"] == "Patched Title"
    assert detail["artist"] == "Patched Artist"
