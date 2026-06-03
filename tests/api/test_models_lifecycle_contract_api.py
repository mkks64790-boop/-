from __future__ import annotations

from backend.main import VoiceAssetResponse
from backend.services.model_service import upsert_voice_model


def test_models_list_exposes_lifecycle_state_field(client, isolated_backend):
    upsert_voice_model(
        "v_stage59a_contract",
        "Stage59AContractVoice",
        "shared_data/weights/stage59a_contract.pth",
        "shared_data/weights/stage59a_contract.index",
        metadata={"source": "stage47_real_acceptance"},
    )

    resp = client.get("/api/models?include_unavailable=true")
    assert resp.status_code == 200
    payload = resp.json()
    match = next((item for item in payload if item["model_id"] == "v_stage59a_contract"), None)
    assert match is not None
    assert match["lifecycle_state"] == "active"

    validated = VoiceAssetResponse.model_validate(match)
    assert validated.lifecycle_state == "active"


def test_models_include_test_data_shows_lifecycle_state(client, isolated_backend):
    upsert_voice_model(
        "v_smoke_lifecycle_contract",
        "smoke_lifecycle_voice",
        "shared_data/weights/smoke.pth",
        "shared_data/weights/smoke.index",
        metadata={"smoke": True, "test_scope": "smoke"},
    )

    hidden = client.get("/api/models?include_unavailable=true").json()
    assert all(item["model_id"] != "v_smoke_lifecycle_contract" for item in hidden)

    visible = client.get(
        "/api/models?include_unavailable=true&include_test_data=true"
    ).json()
    match = next((item for item in visible if item["model_id"] == "v_smoke_lifecycle_contract"), None)
    assert match is not None
    assert match["lifecycle_state"] == "test_data"
    VoiceAssetResponse.model_validate(match)