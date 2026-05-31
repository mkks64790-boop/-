from __future__ import annotations

from backend import main as backend_main


def _fake_preflight(strategy_key: str, material_decision: dict | None = None) -> dict:
    material_decision = material_decision or {}
    submission_allowed = material_decision.get("submission_allowed")
    ok = True if submission_allowed is None else bool(submission_allowed)
    return {
        "ok": ok,
        "environment_ok": True,
        "material_ok": True if submission_allowed is None else bool(submission_allowed),
        "submission_allowed": submission_allowed if submission_allowed is not None else True,
        "job_type": "train",
        "strategy_key": strategy_key,
        "recommended_route": material_decision.get("recommended_route") or strategy_key,
        "material_profile": material_decision.get("material_profile") or "",
        "duration_seconds": material_decision.get("duration_seconds"),
        "duration_label": material_decision.get("duration_label") or "",
        "sample_rate": material_decision.get("sample_rate"),
        "channels": material_decision.get("channels"),
        "codec": material_decision.get("codec") or "",
        "container": material_decision.get("container") or "",
        "bit_rate": material_decision.get("bit_rate"),
        "single_long_eligible": material_decision.get("single_long_eligible"),
        "reason": material_decision.get("reason") or "",
        "next_step": material_decision.get("next_step") or "",
        "material_decision": material_decision,
        "checks": [],
        "errors": [] if ok else [{"check": "train_material_profile", "detail": material_decision.get("reason") or ""}],
    }


def test_train_preflight_routes_single_long_and_short(client, monkeypatch):
    monkeypatch.setattr(backend_main, "run_train_preflight", _fake_preflight)

    long_resp = client.get("/api/preflight/train?file_count=1&duration_seconds=2709.9951")
    short_resp = client.get("/api/preflight/train?file_count=1&duration_seconds=932.702025")

    assert long_resp.status_code == 200
    assert short_resp.status_code == 200

    long_data = long_resp.json()
    short_data = short_resp.json()
    assert long_data["recommended_route"] == "single_long_preprocess"
    assert long_data["single_long_eligible"] is True
    assert long_data["submission_allowed"] is True

    assert short_data["recommended_route"] == "multi_clean_direct"
    assert short_data["single_long_eligible"] is False
    assert short_data["submission_allowed"] is False


def test_train_submit_rejects_short_single_material(client, monkeypatch):
    short_material = {
        "input_mode": "single_file",
        "material_profile": "single_short_out_of_window",
        "recommended_route": "multi_clean_direct",
        "single_long_eligible": False,
        "submission_allowed": False,
        "duration_seconds": 932.702025,
        "duration_label": "15分33秒",
        "reason": "单文件时长约 15分33秒，未达到 30 分钟下限，不能按单文件长干声快速训练处理。",
        "next_step": "请改用多文件精训素材，或准备 30-50 分钟单干声后再提交。",
    }
    monkeypatch.setattr(backend_main, "profile_train_saved_uploads", lambda saved_files: short_material)
    monkeypatch.setattr(backend_main, "run_train_preflight", _fake_preflight)

    resp = client.post(
        "/api/train",
        data={"voice_name": "short-sample"},
        files=[("files", ("short.mp3", b"short-sample", "audio/mpeg"))],
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["material_profile"] == "single_short_out_of_window"
    assert detail["recommended_route"] == "multi_clean_direct"
    assert detail["single_long_eligible"] is False


def test_train_submit_accepts_single_long_route_without_dispatch(client, monkeypatch):
    long_material = {
        "input_mode": "single_file",
        "material_profile": "single_long_candidate",
        "recommended_route": "single_long_preprocess",
        "single_long_eligible": True,
        "submission_allowed": True,
        "duration_seconds": 2709.9951,
        "duration_label": "45分10秒",
        "sample_rate": 44100,
        "channels": 2,
        "codec": "mp3",
        "container": "mp3",
        "bit_rate": 320000,
        "reason": "单文件时长约 45分10秒，命中 30-50 分钟快速训练窗口。",
        "next_step": "可直接创建单文件快速训练任务。",
    }
    monkeypatch.setattr(backend_main, "profile_train_saved_uploads", lambda saved_files: long_material)
    monkeypatch.setattr(backend_main, "run_train_preflight", _fake_preflight)
    monkeypatch.setattr(backend_main, "reserve_job", lambda job, start_status: False)

    resp = client.post(
        "/api/train",
        data={"voice_name": "long-sample"},
        files=[("files", ("long.mp3", b"long-sample", "audio/mpeg"))],
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["strategy_key"] == "single_long_preprocess"
    assert payload["recommended_route"] == "single_long_preprocess"
    assert payload["single_long_eligible"] is True
    assert payload["status"] == "pending"
