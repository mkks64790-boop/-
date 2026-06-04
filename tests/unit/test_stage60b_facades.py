def test_stage60b_facades_import_public_contracts():
    from backend.services import artifact_lifecycle_service as artifact
    from backend.services import execution_safety_service as safety
    from backend.services import short_chain_service as short_chain
    from backend.services import uvr_smoke_service as smoke

    assert short_chain.plan_short_chain_uvr
    assert short_chain.evaluate_uvr_ab_readiness
    assert safety.evaluate_execution_policy
    assert safety.evaluate_execution_guards
    assert artifact.build_run_persistence_bundle
    assert artifact.build_job_artifact_promotion_plan
    assert smoke.mock_execute_uvr_ab
    assert smoke.evaluate_real_smoke_plan


def test_stage60b_facades_delegate_to_existing_implementations():
    from backend.services import execution_safety_service as safety
    from backend.services import stage59_execution_policy_service as old_policy
    from backend.services import uvr_smoke_service as smoke
    from backend.services import stage59_real_smoke_plan_service as old_smoke

    assert safety.evaluate_execution_policy is old_policy.evaluate_execution_policy
    assert smoke.evaluate_real_smoke_plan is old_smoke.evaluate_real_smoke_plan


# Stage60 DB Governance Phase 3: basic repo facade smoke (added per task; uses existing test file)
def test_stage60_db_repositories_import_and_basic_contract():
    from backend.repositories import (
        JobRepository,
        VoiceModelRepository,
        ArtifactRepository,
        TrackRepository,
        MaterialRepository,
    )

    assert JobRepository
    assert VoiceModelRepository
    assert ArtifactRepository
    assert TrackRepository
    assert MaterialRepository

    # instantiate (conn optional)
    jr = JobRepository()
    vmr = VoiceModelRepository()
    ar = ArtifactRepository()
    tr = TrackRepository()
    mr = MaterialRepository()
    assert hasattr(jr, "upsert")
    assert hasattr(jr, "update_status")
    assert hasattr(jr, "get_next_pending")
    assert hasattr(vmr, "upsert")
    assert hasattr(vmr, "find_by_name_or_path")
    assert hasattr(ar, "list_for_job")
    assert hasattr(ar, "upsert_artifact")
    assert hasattr(tr, "upsert_track")
    assert hasattr(mr, "upsert_asset")

    # optional conn injection shape
    import sqlite3
    # can't easily open mem without schema, just check accepts
    assert JobRepository(conn=None) is not None
