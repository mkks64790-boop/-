# Stage58C Real Material Quality Acceptance Report

Generated at: 2026-06-03

## Scope And Safety

- Project root: `D:\FeiSharkStudio-v2`
- Manifest: `shared_data/materials/stage58/material_manifest.json`
- Verifier: `backend/verify_stage58_material_quality.py`
- Test: `tests/unit/test_stage58_material_quality_manifest.py`
- No long training was run.
- RVC 7866 was not started.
- UVR separation was not executed.
- No music was downloaded.
- No user material was deleted, moved, renamed, or overwritten.

## Material Sources

Read-only sources checked:

- `D:\FeiSharkStudio-v2\shared_data`
- `C:\Users\ASUS\Desktop\干声文件`
- `D:\测试音乐`

Project-local material library sources:

- User dry vocals copied from the desktop dry-voice folder: `朱朱干声.mp3`, `朱朱干声唱.mp3`
- Public/traceable speech samples: Jimmy Wales CC0 voice, LibriVox public-domain voice
- Public/traceable non-vocal benchmark: Wikimedia public-domain acoustic guitar
- Internal synthetic smoke signal: `synthetic_vowel_tone_mix_8s.wav`
- Manual-review cover source candidate: `归不了岸的船.mp3`

Historical project outputs checked:

- `shared_data/uploads`: 11 audio files
- `shared_data/outputs`: 94 `final_master.wav` files
- `shared_data/separation_eval`: 28 audio files
- `shared_data/stage47`: 1 short completed-cover smoke artifact

## Classification Results

Training dry voice references:

- `shared_data/material_library/authorized_dry_vocals/user/朱朱干声.mp3`: 932.702s, 44.1kHz, stereo MP3, mean `-26.2 dB`, peak `-0.3 dB`. Technically audible and not silent. Suitable only as long dry-voice training candidate after manual rights confirmation.
- `shared_data/material_library/authorized_dry_vocals/user/朱朱干声唱.mp3`: 2709.995s, 44.1kHz, stereo MP3, mean `-21.3 dB`, peak `0.0 dB`. Best available singing dry-voice reference, but very long and rights-pending.

Speaking dry voice:

- `jimmy_wales_voice_cc0.ogg`: 9.533s, speech-only, CC0, too short for RVC quality judgment.
- `librivox_abou_hunt_py_public_domain.mp3`: 108.991s, speech-only, public domain, good import/probe material but not singing.
- `stage56_librivox_public_domain_voice_30s.mp3`: 30.0s, legal short speech; useful for connectivity, not singing-cover quality.

Singing dry voice:

- Only `朱朱干声唱.mp3` is a meaningful real singing dry-voice candidate. It should be clipped/preflighted before any future training, and only after manual rights confirmation.

Mixed songs / separation evaluation:

- `D:\测试音乐\如愿-孔老师.wav`: 260.0s, 44.1kHz stereo WAV, mean `-15.2 dB`, peak `-1.4 dB`. Good technical UVR A/B candidate, but external read-only and rights unknown.
- `D:\测试音乐\依邦妮 - 口哨战歌 (DJ版).flac`: 248.415s, 48kHz stereo FLAC, mean `-7.0 dB`, peak `0.0 dB`. Hot master/clipping risk; Stage45R latest UVR artifact remains `noise_risk=high`.
- `shared_data/material_library/cover_source_candidates/user/归不了岸的船.mp3`: 180.04s per prior Stage56B probe. Manual-review cover source only; do not train from it.

Completed cover products:

- `shared_data/stage47/stage47_cover_smoke_60s_ruyuan.wav`: 60.0s, 44.1kHz stereo WAV, mean `-17.4 dB`, peak `-4.8 dB`. Best existing short completed-cover listening baseline found.
- `shared_data/outputs/*/final_master.wav`: 20 files are technically reviewable at 20-180s; they still need human A/B listening and lineage checks.

Bad samples / quarantine recommended:

- 43 historical `final_master.wav` files are about 1 second long. They are smoke residue, not completed covers.
- 31 additional `final_master.wav` files are 2-20 seconds. They are short smoke outputs, not quality acceptance material.
- 5 upload files are 1-3 second mono tone-like smoke inputs. They cannot judge RVC, UVR, or VST sound quality.
- `synthetic_vowel_tone_mix_8s.wav` is valid for waveform smoke only, not real-material quality.
- Latest Stage45R UVR stems for the DJ source are marked `quarantine_recommended=true` because `noise_risk=high` and source clipping is documented.

## Bad Sample Reasons

- Too short: 1-3 second uploads and 1 second final masters cannot represent voice conversion, separation, or VST mastering behavior.
- Synthetic/smoke-only: deterministic tones and smoke artifacts are useful for pipeline checks but invalid for real audio quality.
- Hot/clipped source: the DJ FLAC peaks at `0.0 dB`; Stage45R also reported high clipping/noise risk.
- Unresolved UVR risk: latest Stage45R quality report has `stage45r_noise_risk=high`; do not use those stems for training or cover acceptance.
- Rights unknown/manual review: D drive songs and user cover source candidates can support local read-only testing only after explicit review; they are not training or publishable material.

## Recommended Next Test Materials

- RVC training direction: use `朱朱干声唱.mp3` only after manual rights confirmation, then create a short clipped preflight sample before any long training.
- RVC cover acceptance: use `shared_data/stage47/stage47_cover_smoke_60s_ruyuan.wav` as the existing short product baseline for A/B listening; still do not infer model quality without human review.
- UVR direction: use `D:\测试音乐\如愿-孔老师.wav` as the cleaner mixed-song A/B candidate after the Stage45/46 UVR noise issue is resolved.
- Connectivity-only legal smoke: use `shared_data/separation_eval/input/stage56_librivox_public_domain_voice_30s.mp3`; label results as speech/connectivity only.
- Do not use: 1s/3s smoke outputs, synthetic vowel tone, high-risk Stage45R DJ stems, or unconfirmed mixed songs for training conclusions.

## Manifest Summary

`backend/verify_stage58_material_quality.py` reported:

```text
entries=17
verified_usable=10
quarantine_recommended=6
suitability={"cover": 3, "listening_acceptance": 13, "separation": 4, "training": 2}
STAGE58_MATERIAL_QUALITY PASS
```

Blocking flags intentionally left in the manifest:

- `manual_rights_confirmation_required=true`
- `short_legal_vocal_cover_source_missing=true`
- `separation_noise_risk_unresolved=true`
- `bad_smoke_outputs_present=true`

## Verification Commands And Results

```powershell
python -m py_compile backend\verify_stage58_material_quality.py
```

Result: pass.

```powershell
python backend\verify_stage58_material_quality.py
```

Result: `STAGE58_MATERIAL_QUALITY PASS`.

```powershell
python -m pytest -q tests\unit\test_stage58_material_quality_manifest.py
```

Result: `3 passed, 2 warnings`.

## Files Modified

- `backend/verify_stage58_material_quality.py`
- `shared_data/materials/stage58/material_manifest.json`
- `tests/unit/test_stage58_material_quality_manifest.py`
- `docs/agent-md/worker/stage-58c-real-material-quality-report.md`
