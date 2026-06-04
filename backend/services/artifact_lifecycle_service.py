from __future__ import annotations

# Stage60 durable facade for artifact contracts, transient records, listening metadata,
# and file-backed promotion planning. Old Stage59 modules remain the implementation.

from .stage59_artifact_persistence_service import (
    CANONICAL_STORE,
    CONTRACT_SCHEMA,
    DEFAULT_LIFECYCLE,
    REQUIRES_LATER_DB_INTEGRATION,
    UVR_ARTIFACT_KINDS,
    build_artifact_contract_record,
    build_file_backed_uvr_artifact_contracts,
    build_mock_uvr_artifact_contracts,
    build_run_persistence_bundle,
    clear_persistence_store,
    get_run_artifact_contract,
    planned_sandbox_path,
    safe_runtime_run_id,
    stable_artifact_id,
    store_run_artifact_contract,
    validate_artifact_contract_record,
)
from .stage59_job_artifact_promotion_service import (
    REGISTER_REQUIRES_PHYSICAL_FILE,
    build_job_artifact_promotion_plan,
    promote_file_backed_uvr_artifacts,
)
from .stage59_listening_bridge_service import (
    LISTENING_BRIDGE_SCHEMA,
    METADATA_ONLY_REASON,
    STAGE49_COMPATIBLE_SCHEMA,
    build_listening_contract,
    get_listening_contract_for_run,
)
from .stage59_transient_artifact_service import (
    attach_listening_contract,
    clear_transient_store,
    get_artifact_contract_for_run,
    get_transient_run,
    list_transient_artifact_records,
    register_transient_uvr_artifacts,
)


__all__ = [
    "CANONICAL_STORE",
    "CONTRACT_SCHEMA",
    "DEFAULT_LIFECYCLE",
    "LISTENING_BRIDGE_SCHEMA",
    "METADATA_ONLY_REASON",
    "REGISTER_REQUIRES_PHYSICAL_FILE",
    "REQUIRES_LATER_DB_INTEGRATION",
    "STAGE49_COMPATIBLE_SCHEMA",
    "UVR_ARTIFACT_KINDS",
    "attach_listening_contract",
    "build_artifact_contract_record",
    "build_file_backed_uvr_artifact_contracts",
    "build_job_artifact_promotion_plan",
    "build_listening_contract",
    "build_mock_uvr_artifact_contracts",
    "build_run_persistence_bundle",
    "clear_persistence_store",
    "clear_transient_store",
    "get_artifact_contract_for_run",
    "get_listening_contract_for_run",
    "get_run_artifact_contract",
    "get_transient_run",
    "list_transient_artifact_records",
    "planned_sandbox_path",
    "promote_file_backed_uvr_artifacts",
    "register_transient_uvr_artifacts",
    "safe_runtime_run_id",
    "stable_artifact_id",
    "store_run_artifact_contract",
    "validate_artifact_contract_record",
]

# Lazy import to break circular with thin shims (old stage59_* now import from facade)
def __getattr__(name):
    if name in {
        "CANONICAL_STORE",
        "CONTRACT_SCHEMA",
        "DEFAULT_LIFECYCLE",
        "REQUIRES_LATER_DB_INTEGRATION",
        "UVR_ARTIFACT_KINDS",
        "build_artifact_contract_record",
        "build_file_backed_uvr_artifact_contracts",
        "build_mock_uvr_artifact_contracts",
        "build_run_persistence_bundle",
        "clear_persistence_store",
        "get_run_artifact_contract",
        "planned_sandbox_path",
        "safe_runtime_run_id",
        "stable_artifact_id",
        "store_run_artifact_contract",
        "validate_artifact_contract_record",
    }:
        from .stage59_artifact_persistence_service import (
            CANONICAL_STORE,
            CONTRACT_SCHEMA,
            DEFAULT_LIFECYCLE,
            REQUIRES_LATER_DB_INTEGRATION,
            UVR_ARTIFACT_KINDS,
            build_artifact_contract_record,
            build_file_backed_uvr_artifact_contracts,
            build_mock_uvr_artifact_contracts,
            build_run_persistence_bundle,
            clear_persistence_store,
            get_run_artifact_contract,
            planned_sandbox_path,
            safe_runtime_run_id,
            stable_artifact_id,
            store_run_artifact_contract,
            validate_artifact_contract_record,
        )
        return locals().get(name) or globals().get(name)
    if name in {
        "REGISTER_REQUIRES_PHYSICAL_FILE",
        "build_job_artifact_promotion_plan",
        "promote_file_backed_uvr_artifacts",
    }:
        from .stage59_job_artifact_promotion_service import (
            REGISTER_REQUIRES_PHYSICAL_FILE,
            build_job_artifact_promotion_plan,
            promote_file_backed_uvr_artifacts,
        )
        return locals().get(name) or globals().get(name)
    if name in {
        "LISTENING_BRIDGE_SCHEMA",
        "METADATA_ONLY_REASON",
        "STAGE49_COMPATIBLE_SCHEMA",
        "build_listening_contract",
        "get_listening_contract_for_run",
    }:
        from .stage59_listening_bridge_service import (
            LISTENING_BRIDGE_SCHEMA,
            METADATA_ONLY_REASON,
            STAGE49_COMPATIBLE_SCHEMA,
            build_listening_contract,
            get_listening_contract_for_run,
        )
        return locals().get(name) or globals().get(name)
    if name in {
        "attach_listening_contract",
        "clear_transient_store",
        "get_artifact_contract_for_run",
        "get_transient_run",
        "list_transient_artifact_records",
        "register_transient_uvr_artifacts",
    }:
        from .stage59_transient_artifact_service import (
            attach_listening_contract,
            clear_transient_store,
            get_artifact_contract_for_run,
            get_transient_run,
            list_transient_artifact_records,
            register_transient_uvr_artifacts,
        )
        return locals().get(name) or globals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

