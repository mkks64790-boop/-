# FeiShark External Engines (Self-Contained for Stable Training)

This folder allows you to drop complete, full RVC-WebUI and AudioPipeline deployments **inside the workspace**.

Benefits:
- All in one tree with your code and `shared_data/` materials.
- No risk of accidental deletion of external folders.
- Launcher will auto-discover and start them.
- Stable for training with your prepared materials + 秋风RVC as backup model.

Structure:
- `rvc-webui/`: **Primary** RVC WebUI (your main engine). Port 7866. Used for both training and inference.
- `rvc-webui-backup/`: **Backup** RVC WebUI for 秋风RVC (or Qiufeng RVC) as enabled in Studio. Port 7865. Inference fallback only (training stays on primary).
- `audio-pipeline/`: Complete AudioPipeline for UVR separation (for cover and material prep).

## How to Integrate Your Complete Engines (for stable training)

1. Copy your **full, working** RVC-WebUI deployment (the one with all your models, including 秋风RVC if it's in the backup instance) into:
   - `external/rvc-webui/` for the main one.
   - `external/rvc-webui-backup/` for the 秋风RVC backup instance (if you run it separately on 7865).

2. For AudioPipeline/UVR:
   - Copy your complete AudioPipeline (with venv, run_uvr5_split.py, models/UVR-MDX-NET-Voc_FT.onnx etc.) into `external/audio-pipeline/`.

3. Run the setup helper (optional, it ensures skeleton):
   powershell -ExecutionPolicy Bypass -File scripts\setup_training_engines.ps1

4. Start with the launcher:
   - It will detect the external/ dirs and start main RVC on 7866 + backup on 7865 if present.
   - Then start backend.

5. Your prepared materials in `shared_data/` (uploads/, batches/ etc.) can now be used via:
   - /api/train for RVC model training (primary engine).
   - Studio for assigning 秋风RVC as backup voice model on tracks.
   - Cover flows will use the bundled UVR + RVC.

Do **not** commit:
- model weights (*.pth, *.index)
- audio files
- venv/, runtime/, logs/, generated outputs
- large binaries

The code (engine_paths.py, launcher, voice_changer etc.) now prefers `external/...` over old D:\ paths.

This completes the bundling part of Stage60 governance for stable self-contained training.

See sub-READMEs in each dir for exact expected files.
