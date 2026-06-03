# Stage 42：Local AI Engine Manager + 三页面正式产品骨架计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 当前验收结论

Stage 41 已经把训练恢复链路推进到真实翻唱闭环：

```text
恢复模型：v_2c1603c7 / 朱朱_recovered_e90
来源训练：train_010253ec08f0
真实短 cover：task_stage41_ce1b32f2
最终产物：shared_data/jobs/task_stage41_ce1b32f2/artifacts/cover_mix/final_master.wav
pytest：49 passed
self_check：PASS
Stage41 dry-run：PASS
Stage41B browser smoke：PASS
```

注意：如果浏览器上的 `127.0.0.1:8000` 仍返回旧字段，例如 `current_stage=train_checkpoint_recover`，优先判断为后端 uvicorn 进程未重启。新代码通过 TestClient 已返回 `train_register_model`。

## Stage 42 总目标

把项目从“任务能跑”推进到“产品架构清楚、引擎可管理”：

```text
Dashboard：只负责创建任务、查看任务、看当前进度。
Factory：负责模型库、训练入口、RVC/UVR/SVC 引擎管理、第三方 RVC 读取。
Studio：负责试听、版本、音轨、后续修音和导出。
```

本阶段不做 VST，不做长训练，不做大规模真实 cover 压测。先把引擎层和产品骨架做稳。

## 为什么现在做这个阶段

1. Stage 41 已证明恢复模型能真实跑通 RVC cover，说明主链路不是空壳。
2. 现在 UI 混乱的根因是调试区、模型区、任务区、诊断区混在一起，必须先重排信息架构。
3. 第三方 RVC 不能继续只当“在线状态提示”，要升级成 Local AI Engine 的一个可检测、可读取、可诊断的引擎适配器。
4. UVR、RVC、SVC/SVT 以后都应该走统一 Engine Adapter，不要每个页面自己硬编码路径和状态。

## 双 Agent 分工

### Stage 42A：地基 Agent

目标：新增 Local AI Engine Manager 后端契约，读取第三方 RVC / UVR / SVC 状态，不破坏现有 cover/train 主链路。

交付文件：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-42a-local-ai-engine-manager-backend-prompt.md
```

### Stage 42B：产品 Agent

目标：三页面正式产品骨架重排，新增 Factory 引擎管理区，收起调试痕迹，让页面看起来像正式工作站。

交付文件：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-42b-three-page-product-shell-ui-prompt.md
```

## Stage 42 后的路线

```text
Stage 43：训练调教工作台，训练参数模板、epoch/batch/GPU 配置、恢复/导出策略。
Stage 44：RVC/UVR/SVC 真实适配增强，外部引擎启动控制、模型扫描、路径修复。
Stage 45：Studio 修音室，WebAudio 双轨、基础 EQ/压缩/音量/导出链路。
Stage 46：VST 或 VST 替代桥接方案评估，先做可控 WebAudio，不急着接原生 VST。
```
