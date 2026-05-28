from __future__ import annotations

import os
import uuid

try:
    from ..db import update_task_status
    from ..model_trainer import (
        prepare_multi_clean_direct_dataset,
        register_trained_model,
        run_training_core,
        run_training_feature_extract,
        run_training_index,
        run_training_pitch_extract,
    )
    from ..services.asset_service import register_job_artifact
    from ..services.dataset_service import get_dataset_for_job
    from ..temp_cleanup_service import cleanup_job_transients
    from .base_strategy import BaseStrategy
except ImportError:
    from db import update_task_status
    from model_trainer import (
        prepare_multi_clean_direct_dataset,
        register_trained_model,
        run_training_core,
        run_training_feature_extract,
        run_training_index,
        run_training_pitch_extract,
    )
    from services.asset_service import register_job_artifact
    from services.dataset_service import get_dataset_for_job
    from temp_cleanup_service import cleanup_job_transients
    from strategies.base_strategy import BaseStrategy


class TrainMultiCleanStrategy(BaseStrategy):
    strategy_key = "multi_clean_direct"

    def execute(self, job):
        dataset = get_dataset_for_job(job.job_id)
        dataset_root = dataset["root_path"] if dataset else job.input_path
        if not os.path.isabs(dataset_root):
            dataset_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), dataset_root)

        model_id = f"v_{uuid.uuid4().hex[:8]}"
        exp_name = f"feishark_{model_id}"
        current_stage = "train_dataset_prepare"

        self.stage_started(job.job_id, current_stage, f"prepare training dataset: {dataset_root}")
        self.stage_completed(job.job_id, current_stage, "training dataset ready", {"dataset_root": dataset_root})

        try:
            current_stage = "train_direct_prepare"
            self.stage_started(job.job_id, current_stage, f"direct prepare: {dataset_root}")
            slice_count = prepare_multi_clean_direct_dataset(dataset_root, exp_name)
            self.stage_completed(job.job_id, current_stage, "direct prepare completed", {"slice_count": slice_count, "exp_name": exp_name})

            update_task_status(job.job_id, "训练中", "")

            current_stage = "train_pitch_extract"
            self.stage_started(job.job_id, current_stage, f"pitch extract: {exp_name}")
            run_training_pitch_extract(exp_name)
            self.stage_completed(job.job_id, current_stage, "pitch extract completed", {"exp_name": exp_name})

            current_stage = "train_feature_extract"
            self.stage_started(job.job_id, current_stage, f"feature extract: {exp_name}")
            run_training_feature_extract(exp_name)
            self.stage_completed(job.job_id, current_stage, "feature extract completed", {"exp_name": exp_name})

            current_stage = "train_core"
            self.stage_started(job.job_id, current_stage, f"train core: {exp_name}")
            run_training_core(exp_name)
            self.stage_completed(job.job_id, current_stage, "train core completed", {"exp_name": exp_name})

            current_stage = "train_index"
            self.stage_started(job.job_id, current_stage, f"index build: {exp_name}")
            run_training_index(exp_name)
            self.stage_completed(job.job_id, current_stage, "index build completed", {"exp_name": exp_name})

            current_stage = "train_register_model"
            self.stage_started(job.job_id, current_stage, f"register model: {job.voice_name}")
            pth_final, index_final = register_trained_model(exp_name, model_id, job.voice_name, source_job_id=job.job_id)
            for artifact_type, path in (
                ("train_model_pth", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), pth_final.replace("/", os.sep))),
                ("train_model_index", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), index_final.replace("/", os.sep))),
            ):
                register_job_artifact(job.job_id, current_stage, artifact_type, path, is_final=True)

            result = {
                "success": True,
                "model_id": model_id,
                "model_name": job.voice_name,
                "slice_count": slice_count,
                "mode": self.strategy_key,
                "pth_path": pth_final,
                "index_path": index_final,
            }
            self.stage_completed(job.job_id, current_stage, "model registered", result)
            update_task_status(job.job_id, "完成", "")
            return result
        except Exception as exc:
            self.stage_failed(job.job_id, current_stage, str(exc), {"error": str(exc), "exp_name": exp_name})
            update_task_status(job.job_id, "失败", str(exc)[:500])
            return {"success": False, "error": str(exc)}
        finally:
            cleanup_job_transients(job.job_id)
