# Stage53 素材库统一归档与验收报告

## 范围

- 项目根目录：`D:\FeiSharkStudio-v2`
- 目标：把本阶段真正需要保留的本地 C/D 盘素材统一归档到 `shared_data/material_library/**`，避免桌面或外部测试目录误删导致验证断链。
- 边界：不删除原文件，不物理清理历史成品，不搬运 RVC/UVR/ffmpeg/Python 等运行依赖，不运行真实 UVR/RVC/训练。

## 已归档到项目内的本地素材

| 原始路径 | 项目内备份路径 | 用途分类 | 路由约束 |
| --- | --- | --- | --- |
| `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3` | `shared_data/material_library/authorized_dry_vocals/user/朱朱干声.mp3` | 干声训练基准 | 可作为训练候选；仍需人工确认权利边界 |
| `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3` | `shared_data/material_library/authorized_dry_vocals/user/朱朱干声唱.mp3` | 单文件长干声训练基准 | 可作为 30-50 分钟单文件训练候选；仍需人工确认权利边界 |
| `C:\Users\ASUS\Desktop\归不了岸的船.mp3` | `shared_data/material_library/cover_source_candidates/user/归不了岸的船.mp3` | 翻唱源候选 | 只作本地回归备份；不得进入 RVC 训练；人工确认后才可用于翻唱源 |

## 已登记的公开/合成测试素材

| 项目内路径 | 用途分类 | 权利/来源边界 |
| --- | --- | --- |
| `shared_data/material_library/authorized_dry_vocals/public_domain_voice/jimmy_wales_voice_cc0.ogg` | 小体积语音 smoke | Wikimedia Commons CC0 |
| `shared_data/material_library/authorized_dry_vocals/public_domain_voice/librivox_abou_hunt_py_public_domain.mp3` | 小体积语音 smoke | LibriVox Public Domain |
| `shared_data/material_library/separation_benchmarks/public_domain/acoustic_guitar_sample_public_domain.ogg` | 分离评测/波形 smoke | Wikimedia Commons Public Domain |
| `shared_data/material_library/separation_benchmarks/synthetic/synthetic_vowel_tone_mix_8s.wav` | 合成分离评测 smoke | 内部生成，无第三方音源 |

## 未搬运内容

- `D:\测试音乐\*.wav/*.mp3/*.flac`：历史分离评测材料，当前 Stage52/Stage53 策略已经禁止默认扫描，避免 DJ/成品/混音素材污染基准。
- `D:\RVC\RVCv2`、`C:\Users\ASUS\AudioPipeline`、`ffmpeg`、`ffprobe`、Python 环境：属于外部运行依赖，不应搬进项目仓库；后续应通过环境检查和路径配置管理。
- 历史 89 个 cover master：当前只做非破坏性质量分流，70 个为归档候选，不做物理删除。

## 本轮代码/契约修正

- `backend/services/material_library_service.py`
  - 新增 `cover_source_candidates/user` 素材库扫描规格。
  - 新增 `cover_source` 分类，路由为 `cover_source_manual_review_only`。
  - 汇总新增 `cover_source_count`，避免源歌候选被误算成干声训练素材。
- `backend/verify_stage26_real_audio_training.py`
  - 改为优先读取项目内朱朱干声备份。
  - 桌面路径只作为兼容回退。
- `frontend/js/factory/main.js`
  - 素材库 UI 增加“翻唱源候选”分类与统计，防止总数与分项对不上。
- `shared_data/material_library/README.md`
  - 更新为当前真实目录规则。
- `shared_data/material_library/manifests/material_manifest.json`
  - 补充项目内备份路径、翻唱源候选与权利风险说明。

## 当前素材库扫描结果

```json
{
  "library_count": 8,
  "item_count": 7,
  "dry_vocal_count": 4,
  "cover_source_count": 1,
  "separation_benchmark_count": 2,
  "quarantined_count": 0,
  "total_duration_minutes": 66.64
}
```

## 数据卫生结果

```json
{
  "cover_master_total": 89,
  "cover_master_keep_reviewable": 19,
  "cover_master_manual_quality_check": 0,
  "cover_master_archive_candidates": 70,
  "voice_model_total": 128,
  "voice_model_protected": 2
}
```

## 验收

- `python -m py_compile backend/verify_stage26_real_audio_training.py`：通过。
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\factory\main.js','rb').read())"" | node --input-type=module --check"`：通过。
- `python -m pytest -q tests/api/test_stage53_material_library_api.py`：`5 passed`。
- `python -m pytest -q`：`92 passed`。
- `python -m backend.self_check`：`SELF_CHECK_SUMMARY PASS`。

## 注意

- 当前 `127.0.0.1:8000` 已有后端进程在线，但它仍是旧代码进程。若要在浏览器看到新增的 `cover_source_count` 与“翻唱源候选”统计，需要重启 FeiShark 后端服务。
- `shared_data/` 和音频扩展名已在 `.gitignore` 中，归档素材不会推送到 GitHub。
