# Stage 52 Report: Authorized Material Gate + Separation Source Cleanup

项目根目录：`D:\FeiSharkStudio-v2`

## 结论

- 本轮没有继续使用 `D:\测试音乐` 里的 DJ/成品混音作为默认分离评测素材。
- 后端素材发现已改为授权门禁：优先读取 `FEISHARK_SONOVOX_DEMO_DATASET_ROOT`、`FEISHARK_AUTHORIZED_DRY_VOCAL_ROOTS`、项目内 `shared_data/separation_eval/input`。
- 历史测试音乐目录只有在显式设置 `FEISHARK_INCLUDE_LEGACY_TEST_MUSIC=1` 后才会进入扫描。
- Sonovox/授权干声会被识别为训练/调音基准，不会自动进入 UVR 分离评测。
- DJ、remix、master、final、成品、混音、母带等风险文件会进入 `excluded_candidates`，不进入默认候选。

## 修改文件

- `backend/services/separation_eval_service.py`
- `tests/api/test_stage45r_separation_eval_api.py`
- `frontend/js/factory/main.js`
- `frontend/factory.html`

## 后端变化

- `/api/separation/eval/sources` 现在返回素材用途字段：
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
- 新增返回分组：
  - `candidates`
  - `separation_eval_candidates`
  - `excluded_candidates`
  - `material_libraries`
  - `authorized_root_config`
- `execute_separation_audit()` 已改为只使用 `separation_eval_candidates`，不会把干声数据集或 DJ 成品误丢进 UVR runner。
- 当没有合法分离素材时，执行入口会返回 `status=blocked` 和明确 blocker，而不是乱跑一个历史文件。

## 本机素材发现

- 没有找到明确的 `Sonovox AI Demo Dataset` 本地根目录。
- 找到一个可临时作为授权干声根的本机目录：`C:\Users\ASUS\Desktop\干声文件`。
- 临时设置 `FEISHARK_AUTHORIZED_DRY_VOCAL_ROOTS=C:\Users\ASUS\Desktop\干声文件` 后，发现 2 个素材：
  - `朱朱干声.mp3`: `authorized_dry_vocal / dry_vocal / clean_dry_vocal / separation_eval_allowed=False / training_candidate_allowed=True`
  - `朱朱干声唱.mp3`: `authorized_dry_vocal / dry_vocal / clean_dry_vocal / separation_eval_allowed=False / training_candidate_allowed=True`
- 未下载网络素材，未复制 Sonovox 原始 stems 到仓库，未运行 UVR/RVC/训练。

## 前端变化

- Factory 的“候选测试音乐”改为“授权/质检素材”。
- 候选卡片新增展示：
  - 素材来源：Sonovox 干声库、授权干声库、项目输入、历史测试音乐等。
  - 素材用途：干声、伴奏、干净歌曲、成品混音、DJ/混音。
  - 操作资格：可跑 UVR 短片段、不跑分离、训练/调音基准。
  - 风险标签：DJ/remix/master/final 等。
- 空状态文案明确说明：不会默认扫描历史 D 盘测试音乐。

## 验证命令

- `python -m py_compile backend\services\separation_eval_service.py`
- `python -m pytest tests\api\test_stage45r_separation_eval_api.py -q`
- `python -m pytest tests\api\test_stage45r_separation_eval_api.py tests\api\test_stage51_artifact_quality_gate_api.py -q`
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\factory\main.js','rb').read())"" | node --input-type=module --check"`
- `python -m pytest -q`
- `python -m backend.self_check`
- `node frontend\playwright_stage50_review_routing_product_smoke.cjs`

## 验证结果

- `tests/api/test_stage45r_separation_eval_api.py`: 7 passed
- Stage45r + Stage51 目标测试：11 passed
- 全量测试：87 passed
- `backend.self_check`: PASS
- Factory JS syntax check: PASS
- Playwright Stage50 smoke: PASS

## 下一步建议

- 先把 Sonovox 或其它授权干声数据集放到固定本地目录，不要提交进 git。
- 对自己的桌面干声可先用 `FEISHARK_AUTHORIZED_DRY_VOCAL_ROOTS`，不要冒充 Sonovox 根目录。
- 下一阶段应做“授权素材库接入训练链路”：让训练创建入口能读取授权干声库，显示素材数量、总时长、采样率和训练路线建议，但仍不自动启动训练。
- 分离评测需要另备干净的授权混音歌曲或自己合成的干声+伴奏短片段，不能用 DJ 版、成品母带、来路不明网络歌。
