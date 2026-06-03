from __future__ import annotations

from pathlib import Path

from backend import db as backend_db
from backend import main as backend_main
from backend.services.asset_service import (
    LISTENING_REVIEW_SMOKE_NOTE,
    register_job_artifact,
    summarize_listening_review,
)
from backend.services.job_service import create_cover_job


def _seed_cover_job(root: Path, job_id: str, *, track_id: str = "") -> None:
    input_path = root / "shared_data" / "jobs" / job_id / "input" / "source.wav"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"RIFF-STAGE50-SOURCE")

    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage50_review_routing_test"},
        track_id=track_id,
        voice_model_id="v_stage50",
        voice_name="Stage50 Voice",
    )
    backend_db.update_task_status(job_id, "完成", "")


def _seed_cover_artifact(
    root: Path,
    job_id: str,
    *,
    review: dict | None = None,
    track_id: str = "",
) -> str:
    _seed_cover_job(root, job_id, track_id=track_id)

    final_path = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(b"RIFF-STAGE50-FINAL")
    metadata = {"source": "stage50_review_routing_test"}
    if review is not None:
        metadata["listening_review"] = review
    artifact_id = register_job_artifact(
        job_id,
        "cover_mix",
        "cover_master",
        str(final_path),
        is_final=True,
        metadata=metadata,
    )
    assert artifact_id
    return artifact_id


def test_summarize_listening_review_routes_and_smoke_note():
    expected_routes = {
        "unreviewed": "needs_human_review",
        "needs_work": "route_to_rework",
        "usable": "route_to_candidate_pool",
        "release_candidate": "route_to_release_candidate",
        "rejected": "route_to_archive_or_rerun",
    }

    for verdict, route in expected_routes.items():
        summary = summarize_listening_review({"listening_review": {"verdict": verdict}})
        assert summary["verdict"] == verdict
        assert summary["route"] == route

    human_summary = summarize_listening_review(
        {"listening_review": {"verdict": "release_candidate", "notes": "human A/B pass"}}
    )
    assert human_summary["is_human_reviewed"] is True

    smoke_summary = summarize_listening_review(
        {
            "listening_review": {
                "verdict": "release_candidate",
                "notes": LISTENING_REVIEW_SMOKE_NOTE,
            }
        }
    )
    assert smoke_summary["is_human_reviewed"] is False
    assert len(smoke_summary["notes_preview"]) <= 80


def test_job_artifacts_return_review_summary(client, isolated_backend):
    job_id = "task_stage50_artifacts"
    artifact_id = _seed_cover_artifact(
        isolated_backend,
        job_id,
        review={
            "verdict": "needs_work",
            "overall_score": 2,
            "vocal_score": 3,
            "noise_score": 2,
            "mix_score": 2,
            "notes": "needs another pass " + ("x" * 120),
            "reviewed_at": "2026-06-02T00:00:00+00:00",
        },
    )

    resp = client.get(f"/api/jobs/{job_id}/artifacts")

    assert resp.status_code == 200
    item = next(artifact for artifact in resp.json()["artifacts"] if artifact["artifact_id"] == artifact_id)
    summary = item["listening_review_summary"]
    assert item["download_url"] == f"/api/jobs/{job_id}/artifacts/{artifact_id}/download"
    assert item["review_verdict"] == "needs_work"
    assert item["review_route"] == "route_to_rework"
    assert summary["overall_score"] == 2
    assert len(summary["notes_preview"]) == 80


def test_jobs_list_and_detail_return_final_artifact_review_contract(client, isolated_backend):
    job_id = "task_stage50_jobs_contract"
    _seed_cover_artifact(
        isolated_backend,
        job_id,
        review={
            "verdict": "release_candidate",
            "overall_score": 5,
            "notes": "ready for release candidate pool",
            "reviewed_at": "2026-06-02T00:00:00+00:00",
        },
    )

    list_resp = client.get("/api/jobs")
    detail_resp = client.get(f"/api/jobs/{job_id}")

    assert list_resp.status_code == 200
    job_item = next(item for item in list_resp.json()["items"] if item["job_id"] == job_id)
    assert job_item["has_reviewable_final_artifact"] is True
    assert job_item["final_artifact_review_verdict"] == "release_candidate"
    assert job_item["final_artifact_review_route"] == "route_to_release_candidate"
    assert job_item["final_artifact_review_summary"]["is_human_reviewed"] is True

    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["has_reviewable_final_artifact"] is True
    assert detail["final_artifact_review_verdict"] == "release_candidate"
    assert detail["final_artifact_review_summary"]["overall_score"] == 5


def test_job_detail_without_final_artifact_is_not_reviewed(client, isolated_backend):
    job_id = "task_stage50_no_final"
    _seed_cover_job(isolated_backend, job_id)

    resp = client.get(f"/api/jobs/{job_id}")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["has_reviewable_final_artifact"] is False
    assert payload["final_artifact_review_verdict"] == "unreviewed"
    assert payload["final_artifact_review_route"] == "needs_human_review"
    assert payload["final_artifact_review_summary"]["is_human_reviewed"] is False


def test_review_artifacts_queue_returns_summary_counts_and_studio_url(client, isolated_backend):
    release_job_id = "task_stage50_review_queue_release"
    unreviewed_job_id = "task_stage50_review_queue_unreviewed"
    release_artifact_id = _seed_cover_artifact(
        isolated_backend,
        release_job_id,
        track_id="track_stage50_queue",
        review={
            "verdict": "release_candidate",
            "overall_score": 5,
            "notes": "release candidate",
            "reviewed_at": "2026-06-02T00:00:00+00:00",
        },
    )
    _seed_cover_artifact(isolated_backend, unreviewed_job_id)

    resp = client.get("/api/reviews/artifacts?limit=20")
    filtered_resp = client.get("/api/reviews/artifacts?verdict=release_candidate&limit=20")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["release_candidate"] == 1
    assert payload["summary"]["unreviewed"] == 1

    release_item = next(item for item in payload["items"] if item["artifact_id"] == release_artifact_id)
    assert release_item["download_url"] == f"/api/jobs/{release_job_id}/artifacts/{release_artifact_id}/download"
    assert f"job_id={release_job_id}" in release_item["studio_url"]
    assert f"artifact_id={release_artifact_id}" in release_item["studio_url"]
    assert "track_id=track_stage50_queue" in release_item["studio_url"]
    assert release_item["review_summary"]["route"] == "route_to_release_candidate"

    assert filtered_resp.status_code == 200
    filtered = filtered_resp.json()
    assert filtered["summary"]["total"] == 1
    assert filtered["items"][0]["review_summary"]["verdict"] == "release_candidate"


def test_review_artifacts_invalid_verdict_returns_422(client):
    resp = client.get("/api/reviews/artifacts?verdict=ship_it")

    assert resp.status_code == 422


def test_review_routing_read_apis_do_not_dispatch_compute(client, isolated_backend, monkeypatch):
    calls: list[str] = []

    def forbidden_dispatch(*args, **kwargs):
        calls.append("dispatch")
        raise AssertionError("review routing read API must not dispatch compute work")

    def forbidden_run(*args, **kwargs):
        calls.append("run")
        raise AssertionError("review routing read API must not run jobs")

    monkeypatch.setattr(backend_main, "_dispatch_pending_compute_task", forbidden_dispatch)
    monkeypatch.setattr(backend_main, "_safe_dispatch_pending_compute_task", forbidden_dispatch)
    monkeypatch.setattr(backend_main, "_run_job", forbidden_run)

    job_id = "task_stage50_no_dispatch"
    _seed_cover_artifact(isolated_backend, job_id)

    responses = [
        client.get("/api/jobs"),
        client.get(f"/api/jobs/{job_id}"),
        client.get(f"/api/jobs/{job_id}/artifacts"),
        client.get("/api/reviews/artifacts"),
    ]

    assert [resp.status_code for resp in responses] == [200, 200, 200, 200]
    assert calls == []
