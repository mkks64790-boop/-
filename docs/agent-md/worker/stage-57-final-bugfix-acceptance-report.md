# Stage57 最终 Bug 查验修复验收报告

日期：2026-06-03

项目根目录：`D:\FeiSharkStudio-v2`

## 总结

Stage57 按“大查错 + 最小修复 + 回归验收”收口。四个子 agent 已分别完成后端/API/DB、音频管线、前端 UI 状态、QA 回归审计；主控补了 SQLite sidecar 忽略规则，并修复 Stage47 Playwright smoke 的 Factory 异步加载等待问题。

当前验收结论：核心代码回归通过，可以进入下一阶段；但不能把它理解成“产品已干净”。当前数据库仍有大量历史 smoke/stage 记录，RVC 7866 当前离线，UI 仍需要继续做用户态清理和真实素材质量验收。

## 本轮实际修复

1. 后端/API/DB

- `/api/health`、`/api/diagnostics/summary` 增加运行时源码/路由签名，便于判断 live 8000 是否加载旧代码。
- jobs/tasks 状态规范化，兼容 `完成/completed`、`失败/failed`、`已取消/cancelled`、`pending/queued` 等历史状态。
- 终态同步 `current_stage`，减少完成/失败任务仍显示 pending 或中间阶段的问题。
- `register_job_artifact()` 命中重复 artifact 时更新 `file_size/is_final/metadata_json`，避免 final artifact 丢失。
- Studio/review URL 改为 URL 编码，避免特殊字符参数出错。

2. 音频管线

- 收窄 Stage56 已知 pitch fallback，只允许已确认的短帧 broadcast bug 走复制兜底。
- cover split/pitch/voice/mix 阶段增加 artifact 契约检查，完成日志带 artifact id。
- `final_master.wav` 写出后增加 WAV 探测，校验存在、时长、采样率。
- 音频模块改成 package-safe DB import，避免孤立测试或包导入时读错 DB 状态。

3. 前端/UI

- 训练观察器注入的 pending 模型不再被模型库刷新静默切走。
- pending registry 模型禁止直接发起 cover，避免“前端看起来能用、后端还没登记”的误导。
- Factory 批次抽屉保留用户收纳状态。
- Studio 直链增加 contract unavailable / backend restart 降级提示。
- 长路径、长 ID、日志文本增加 overflow 防护。

4. QA/主控收口

- `.gitignore` 增加 `*.db-shm`、`*.db-wal`，避免 SQLite runtime sidecar 被误提交。
- `frontend/playwright_stage47_e2e_acceptance_dashboard_smoke.cjs` 增加 Factory Stage47 模型资产显式等待，修复“数据慢加载导致误判失败”的 flaky 验收。

## 验证结果

- `python -m pytest -q`：`107 passed, 2 warnings`
- 后端关键文件 `py_compile`：通过
- 前端核心 JS module syntax check：通过
- `node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs`：通过
- 隔离临时 DB 版 `backend.self_check.main()`：`CODE_STRUCTURE_SUMMARY PASS`、`RUNTIME_ENVIRONMENT_SUMMARY PASS`、`SELF_CHECK_SUMMARY PASS`
- Live `/api/health`：8000 在线，RVC 7866 离线

Stage47 浏览器验收读取到的真实闭环：

- 训练 job：`train_7f4d6b4e611e`
- 模型：`v_d4d7e1c1 / 朱朱_stage47_single_long`
- cover job：`task_b2272d133fff`
- artifact：`art_f99f7e4afb10`
- Studio：可进入，可播放/下载

## 仍需保留的风险

1. RVC WebUI `http://127.0.0.1:7866` 当前离线。本轮未启动 GPU/RVC，不代表 fresh RVC cover smoke 通过。

2. DB 中历史 smoke/stage 记录仍多，用户界面必须默认过滤或折叠这些测试噪声，否则页面会继续显得“乱糟糟”。

3. Stage56/Stage47 证明的是链路能通，不证明音质已可商用。下一步必须用更合适的真实素材做分离/cover/试听质量验收。

4. 当前工作树仍是大脏树，包含 Stage37-57 大量未提交文件。进入提交前需要做一次“可提交清单 vs 本地数据/垃圾”分离。

5. `backend.self_check` 原生命令会写 synthetic smoke job；验收时应继续使用临时 DB 隔离方式，或后续开发正式的 `--readonly-temp-db` 模式。

## 建议下一阶段

Stage58 不建议继续盲目大改功能。优先做“用户态干净化 + 真实素材质量验收”：

- 默认隐藏 smoke/stage/test 记录，并提供“显示测试记录”开关。
- Dashboard / Factory / Studio 只保留用户当前真正需要的入口，把技术日志、产物库、批次历史继续抽屉化。
- 建立真实素材验收集：公共可用人声/歌声、用户本地素材、朱朱干声参考分开归档。
- RVC 7866 明确为受控引擎：未启动时 UI 显示“引擎离线，不可 fresh 推理”，不要让用户误以为正在跑。
- 等 UI 和数据噪声收住后，再开 fresh RVC cover smoke 和音质问题专项。

