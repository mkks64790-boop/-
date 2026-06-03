# Stage 43：Studio 入口契约 + Engine Manager 收口 + 训练调教台 v0 计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## Stage 42 验收结论

Stage 42 已完成 Local AI Engine Manager 和三页面产品壳：

```text
pytest：52 passed
self_check：PASS
/api/engines：PASS
RVC WebUI：online，D:\RVC\RVCv2，模型扫描上限 400，已登记 120
UVR：online，C:\Users\ASUS\AudioPipeline，模型 1
SVC/SVT：not_configured，占位契约正常
Stage42B Playwright smoke：PASS
```

主要遗留：

```text
task_stage41_ce1b32f2 已完成 cover，但 /api/jobs/{job_id} 未返回 can_open_studio / final_artifact_download_url。
Stage42B smoke 因此没有强验 Stage41 cover -> Studio 入口。
/api/engines/rvc/models 当前最多返回 400 条，后续需要分页、搜索或缓存。
Factory 已有 Engine Manager 壳，但还缺“把外部 RVC 模型登记到 FeiShark”的安全操作入口。
训练调教仍停留在创建入口，没有参数预设、GPU 风险提示、训练策略说明。
```

## Stage 43 总目标

本阶段采用“中等大步”：不接 VST，不跑长训练，但把 Studio 入口、第三方 RVC 模型登记、训练调教台 v0 一起推进。

目标闭环：

```text
已完成 cover job -> API 明确返回 Studio 可打开 -> Dashboard/Factory/Studio 都能进入对应成品
第三方 RVC 模型扫描 -> 可搜索/分页 -> 可安全登记到 FeiShark 模型库
训练创建入口 -> 训练调教台 v0 -> 用户能理解 epochs/batch/GPU/质量预设，不再盲点训练
```

## 双 Agent 分工

### Stage 43A：地基 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-43a-studio-entry-engine-cache-training-contract-prompt.md
```

重点：

```text
修复 completed cover job 的 Studio 入口契约。
为 RVC models API 增加分页、搜索、registered 过滤。
增加安全的外部 RVC 模型登记入口，只登记数据库，不改 D:\RVC\RVCv2。
增加训练调教预设/估算契约，不直接启动训练。
```

### Stage 43B：产品 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-43b-factory-training-tuning-product-prompt.md
```

重点：

```text
Factory 做训练调教台 v0。
Engine Manager 做模型搜索、分页/筛选、登记入口。
Dashboard/Factory/Studio 修好 completed cover 的 Studio 入口。
继续收纳 UI，不让测试痕迹重新铺满页面。
```

## Stage 43 后的路线

```text
Stage 44：真实训练参数接管，把调教台参数安全传入 RVC 训练命令。
Stage 45：Studio 修音室 WebAudio v1，做可听的 EQ/压缩/响度/导出。
Stage 46：SVC/SVT 备用引擎真实适配，按需要接入而不是强行堆功能。
Stage 47：再评估 VST 桥，优先考虑本地插件宿主或 WebAudio 替代链。
```
