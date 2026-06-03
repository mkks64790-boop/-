from __future__ import annotations

import os

try:
    from ..db import update_task_status
    from ..model_trainer import (
        prepare_single_long_preprocess_dataset,
        register_trained_model,
        run_training_core,
        run_training_feature_extract,
        run_training_index,
        run_training_pitch_extract,
    )
    from ..services.asset_service import register_job_artifact
    from ..services.dataset_service import get_dataset_for_job
    from ..services.training_runtime_guard import ensure_training_identity, summarize_training_error
    from ..temp_cleanup_service import cleanup_job_transients
    from .base_strategy import BaseStrategy
except ImportError:
    from db import update_task_status
    from model_trainer import (
        prepare_single_long_preprocess_dataset,
        register_trained_model,
        run_training_core,
        run_training_feature_extract,
        run_training_index,
        run_training_pitch_extract,
    )
    from services.asset_service import register_job_artifact
    from services.dataset_service import get_dataset_for_job
    from services.training_runtime_guard import ensure_training_identity, summarize_training_error
    from temp_cleanup_service import cleanup_job_transients
    from strategies.base_strategy import BaseStrategy


class TrainSingleLongStrategy(BaseStrategy):
    strategy_key = "single_long_preprocess"

    def execute(self, job):
        dataset = get_dataset_for_job(job.job_id)
        dataset_root = dataset["root_path"] if dataset else job.input_path
        if not os.path.isabs(dataset_root):
            dataset_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), dataset_root)

        model_id, exp_name = ensure_training_identity(job)
        training_config = (job.metadata or {}).get("training_config") or {}
        current_stage = "train_dataset_prepare"

        self.stage_started(job.job_id, current_stage, f"prepare training dataset: {dataset_root}")
        self.stage_completed(
            job.job_id,
            current_stage,
            "training dataset ready",
            {"dataset_root": dataset_root, "training_config": training_config},
        )

        try:
            current_stage = "train_preprocess"
            self.stage_started(job.job_id, current_stage, f"single long preprocess: {dataset_root}")
            slice_count = prepare_single_long_preprocess_dataset(dataset_root, exp_name, training_config=training_config)
            self.stage_completed(job.job_id, current_stage, "preprocess completed", {"slice_count": slice_count, "exp_name": exp_name})

            update_task_status(job.job_id, "训练中", "")

            current_stage = "train_pitch_extract"
            self.stage_started(job.job_id, current_stage, f"pitch extract: {exp_name}")
            run_training_pitch_extract(exp_name, training_config=training_config)
            self.stage_completed(job.job_id, current_stage, "pitch extract completed", {"exp_name": exp_name})

            current_stage = "train_feature_extract"
            self.stage_started(job.job_id, current_stage, f"feature extract: {exp_name}")
            run_training_feature_extract(exp_name, training_config=training_config)
            self.stage_completed(job.job_id, current_stage, "feature extract completed", {"exp_name": exp_name})

            current_stage = "train_core"
            self.stage_started(job.job_id, current_stage, f"train core: {exp_name}")
            run_training_core(exp_name, training_config=training_config)
            self.stage_completed(job.job_id, current_stage, "train core completed", {"exp_name": exp_name, "training_config": training_config})

            if training_config.get("index_enabled", True):
                current_stage = "train_index"
                self.stage_started(job.job_id, current_stage, f"index build: {exp_name}")
                run_training_index(exp_name, training_config=training_config)
                self.stage_completed(job.job_id, current_stage, "index build completed", {"exp_name": exp_name})

            current_stage = "train_register_model"
            self.stage_started(job.job_id, current_stage, f"register model: {job.voice_name}")
            pth_final, index_final = register_trained_model(
                exp_name,
                model_id,
                job.voice_name,
                source_job_id=job.job_id,
                training_config=training_config,
            )
            artifacts = [
                ("train_model_pth", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), pth_final.replace("/", os.sep))),
            ]
            if index_final:
                artifacts.append(("train_model_index", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), index_final.replace("/", os.sep))))
            for artifact_type, path in artifacts:
                register_job_artifact(job.job_id, current_stage, artifact_type, path, is_final=True)

            result = {
                "success": True,
                "model_id": model_id,
                "model_name": job.voice_name,
                "slice_count": slice_count,
                "mode": self.strategy_key,
                "pth_path": pth_final,
                "index_path": index_final,
                "training_config": training_config,
            }
            self.stage_completed(job.job_id, current_stage, "model registered", result)
            update_task_status(job.job_id, "完成", "")
            return result
        except Exception as exc:
            error_summary = summarize_training_error(exc, exp_name=exp_name) or {}
            message = error_summary.get("error_summary") or str(exc)[:500]
            self.stage_failed(
                job.job_id,
                current_stage,
                message,
                {
                    "error": str(exc)[:500],
                    "exp_name": exp_name,
                    "error_summary": error_summary,
                },
            )
            update_task_status(job.job_id, "失败", message[:500])
            return {"success": False, "error": message, "error_summary": error_summary}
        finally:
            cleanup_job_transients(job.job_id)
