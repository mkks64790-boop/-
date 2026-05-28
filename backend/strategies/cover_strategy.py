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


class CoverStrategy(BaseStrategy):
    strategy_key = "cover_strategy"

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
            register_cover_stage_outputs(job.job_id, "cover_split")
            self.stage_completed(job.job_id, "cover_split", "分离完成", split_result)

            self.stage_started(job.job_id, "cover_pitch", "开始修音")
            pitch_result = fix_vocal_pitch(job.job_id, key="C", mode="major", strength=0.4, deess_strength=0.3)
            if not pitch_result.get("success"):
                self.stage_failed(job.job_id, "cover_pitch", pitch_result.get("error", "修音失败"))
                return pitch_result
            register_cover_stage_outputs(job.job_id, "cover_pitch")
            self.stage_completed(job.job_id, "cover_pitch", "修音完成", pitch_result)

            self.stage_started(job.job_id, "cover_voice", f"开始变声：{job.voice_model_id}")
            voice_result = transform_voice(job.job_id, model_id=job.voice_model_id or "v_001")
            if not voice_result.get("success"):
                self.stage_failed(job.job_id, "cover_voice", voice_result.get("error", "变声失败"))
                return voice_result
            register_cover_stage_outputs(job.job_id, "cover_voice")
            self.stage_completed(job.job_id, "cover_voice", "变声完成", voice_result)

            self.stage_started(job.job_id, "cover_mix", "开始混音")
            mix_result = merge_master_audio(job.job_id)
            if not mix_result.get("success"):
                self.stage_failed(job.job_id, "cover_mix", mix_result.get("error", "混音失败"))
                return mix_result
            register_cover_stage_outputs(job.job_id, "cover_mix")
            self.stage_completed(job.job_id, "cover_mix", "混音完成", mix_result)

            return {"success": True, "stage": "cover_mix", "result": mix_result}
        finally:
            cleanup_job_transients(job.job_id)
