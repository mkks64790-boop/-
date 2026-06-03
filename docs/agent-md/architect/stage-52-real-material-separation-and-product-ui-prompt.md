# FeiShark Stage 52: Authorized Material Gate for Separation/RVC Baseline

项目根目录：`D:\FeiSharkStudio-v2`

你是肥鲨工作室的工作 agent。本阶段目标是修正素材来源，不允许继续用 DJ 版、成品母带、来路不明网络歌作为默认评测输入。完成后把报告写入：

`docs\agent-md\worker\stage-52-real-material-separation-and-product-ui-report.md`

## 禁止事项

- 不跑训练。
- 不跑 RVC 推理。
- 不启动长时间 UVR 分离。
- 不下载来路不明歌曲。
- 不把 Sonovox 或其它数据集原始 stems 复制进 git 仓库。
- 不默认扫描 `D:\测试音乐`、`D:\测试音频`、`D:\MusicTest`。
- 不把 DJ、remix、master、final、成品、混音、母带文件作为默认候选。

## 目标 A：授权素材来源契约

后端 `backend/services/separation_eval_service.py` 必须按以下优先级发现素材：

- `FEISHARK_SONOVOX_DEMO_DATASET_ROOT`：用户本地解压的 Sonovox Demo Dataset。
- `FEISHARK_AUTHORIZED_DRY_VOCAL_ROOTS`：用户本地授权干声目录，多个目录用分号分隔。
- `shared_data/separation_eval/input`：项目内人工放入的分离评测输入。
- 历史测试音乐目录只允许在 `FEISHARK_INCLUDE_LEGACY_TEST_MUSIC=1` 时扫描。

每个素材必须返回：

- `source_group`
- `library_key`
- `license_tag`
- `license_status`
- `material_role`
- `material_profile`
- `training_route_hint`
- `separation_eval_allowed`
- `training_candidate_allowed`
- `risk_flags`
- `default_candidate`

## 目标 B：用途分流

- Sonovox/授权干声：`material_role=dry_vocal`，允许作为训练/调音基准，禁止自动跑 UVR 分离。
- 项目内人工放入的干净混音短素材：允许进入 UVR 短片段分离质检。
- 历史测试音乐：必须显式 opt-in，且风险文件仍要排除。
- 风险文件：进入 `excluded_candidates`，不得进入 `separation_eval_candidates`。

## 目标 C：执行保护

`execute_separation_audit()` 必须只读取 `separation_eval_candidates`。

如果没有合法分离素材，返回 `status=blocked` 和 blocker，不允许随机挑历史目录文件硬跑。

## 目标 D：Factory 最小 UI 修正

不要大改 UI。本阶段只做最小展示：

- “候选测试音乐”改成“授权/质检素材”。
- 候选卡片显示来源、用途、风险、是否可跑 UVR、是否可做训练基准。
- 空状态说明不会默认扫描历史 D 盘测试音乐。

## 验证命令

必须至少执行：

- `python -m py_compile backend\services\separation_eval_service.py`
- `python -m pytest tests\api\test_stage45r_separation_eval_api.py -q`
- `python -m pytest tests\api\test_stage51_artifact_quality_gate_api.py -q`
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\factory\main.js','rb').read())"" | node --input-type=module --check"`
- `python -m pytest -q`
- `python -m backend.self_check`

如果触碰前端，还要执行：

- `node frontend\playwright_stage50_review_routing_product_smoke.cjs`

## 报告要求

报告必须写清：

- 修改文件清单。
- 当前本机是否发现 Sonovox 根目录。
- 当前本机是否发现授权干声目录。
- 是否执行了 UVR/RVC/训练。
- 默认素材发现是否还会使用 `D:\测试音乐`。
- 验证命令和结果。
- 下一阶段建议。
