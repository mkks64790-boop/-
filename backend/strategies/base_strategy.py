from abc import ABC, abstractmethod

try:
    from ..services.asset_service import register_job_artifact
    from ..services.stage_log_service import log_stage
except ImportError:
    from services.asset_service import register_job_artifact
    from services.stage_log_service import log_stage


class BaseStrategy(ABC):
    strategy_key = ""

    @abstractmethod
    def execute(self, job):
        raise NotImplementedError

    def stage_started(self, job_id: str, stage_name: str, message: str):
        log_stage(job_id, stage_name, "started", message)

    def stage_completed(self, job_id: str, stage_name: str, message: str, detail: dict | None = None):
        log_stage(job_id, stage_name, "completed", message, detail or {})

    def stage_failed(self, job_id: str, stage_name: str, message: str, detail: dict | None = None):
        log_stage(job_id, stage_name, "failed", message, detail or {})

    def artifact(self, job_id: str, stage_name: str, artifact_type: str, path: str, is_final: bool = False, metadata: dict | None = None):
        return register_job_artifact(job_id, stage_name, artifact_type, path, is_final=is_final, metadata=metadata)
