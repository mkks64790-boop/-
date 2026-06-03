import os

try:
    from ..audio_mixer import merge_master_audio
    from ..pitch_processor import fix_vocal_pitch
    from ..services.asset_service import register_cover_stage_outputs
    from ..temp_cleanup_service import cleanup_job_transients
    from ..vocal_separator import split_audio
    from ..voice_changer import transform_voice
    from .base_strategy import BaseStrategy
except ImportError:
    from audio_mixer import merge_master_audio
    from pitch_processor import fix_vocal_pitch
    from services.asset_service import register_cover_stage_outputs
    from temp_cleanup_service import cleanup_job_transients
    from vocal_separator import split_audio
    from voice_changer import transform_voice
    from strategies.base_strategy import BaseStrategy


EXPECTED_COVER_STAGE_ARTIFACTS = {
    "cover_split": 2,
    "cover_pitch": 1,
    "cover_voice": 1,
    "cover_mix": 1,
}


def _with_artifacts(result: dict, artifact_ids: list[str]) -> dict:
    detail = dict(result or {})
    detail["artifact_ids"] = artifact_ids
    return detail


class CoverStrategy(BaseStrategy):
    strategy_key = "cover_strategy"

    def _register_stage_outputs(self, job_id: str, stage_name: str, result: dict) -> list[str] | None:
        artifact_ids = register_cover_stage_outputs(job_id, stage_name)
        expected = EXPECTED_COVER_STAGE_ARTIFACTS.get(stage_name, 0)
        if len(artifact_ids) < expected:
            error = f"{stage_name} artifact registration incomplete: {len(artifact_ids)}/{expected}"
            self.stage_failed(job_id, stage_name, error, _with_artifacts(result, artifact_ids))
            return None
        return artifact_ids

    def execute(self, job):
        input_path = job.input_path
        if not os.path.isabs(input_path):
            input_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), input_path)

        try:
            self.stage_started(job.job_id, "cover_split", f"开始分离：{input_path}")
            split_result = split_audio(job.job_id, input_path)
            if not split_result.get("success"):
                self.stage_failed(job.job_id, "cover_split", split_result.get("error", "分离失败"))
                return split_result
            split_artifacts = self._register_stage_outputs(job.job_id, "cover_split", split_result)
            if split_artifacts is None:
                return {"success": False, "stage": "cover_split", "error": "artifact registration incomplete"}
            self.stage_completed(job.job_id, "cover_split", "分离完成", _with_artifacts(split_result, split_artifacts))

            self.stage_started(job.job_id, "cover_pitch", "开始修音")
            pitch_result = fix_vocal_pitch(job.job_id, key="C", mode="major", strength=0.4, deess_strength=0.3)
            if not pitch_result.get("success"):
                self.stage_failed(job.job_id, "cover_pitch", pitch_result.get("error", "修音失败"))
                return pitch_result
            pitch_artifacts = self._register_stage_outputs(job.job_id, "cover_pitch", pitch_result)
            if pitch_artifacts is None:
                return {"success": False, "stage": "cover_pitch", "error": "artifact registration incomplete"}
            self.stage_completed(job.job_id, "cover_pitch", "修音完成", _with_artifacts(pitch_result, pitch_artifacts))

            self.stage_started(job.job_id, "cover_voice", f"开始变声：{job.voice_model_id}")
            voice_result = transform_voice(job.job_id, model_id=job.voice_model_id or "v_001")
            if not voice_result.get("success"):
                self.stage_failed(job.job_id, "cover_voice", voice_result.get("error", "变声失败"))
                return voice_result
            voice_artifacts = self._register_stage_outputs(job.job_id, "cover_voice", voice_result)
            if voice_artifacts is None:
                return {"success": False, "stage": "cover_voice", "error": "artifact registration incomplete"}
            self.stage_completed(job.job_id, "cover_voice", "变声完成", _with_artifacts(voice_result, voice_artifacts))

            self.stage_started(job.job_id, "cover_mix", "开始混音")
            mix_result = merge_master_audio(job.job_id)
            if not mix_result.get("success"):
                self.stage_failed(job.job_id, "cover_mix", mix_result.get("error", "混音失败"))
                return mix_result
            mix_artifacts = self._register_stage_outputs(job.job_id, "cover_mix", mix_result)
            if mix_artifacts is None:
                return {"success": False, "stage": "cover_mix", "error": "artifact registration incomplete"}
            self.stage_completed(job.job_id, "cover_mix", "混音完成", _with_artifacts(mix_result, mix_artifacts))

            return {"success": True, "stage": "cover_mix", "result": _with_artifacts(mix_result, mix_artifacts)}
        finally:
            cleanup_job_transients(job.job_id)
