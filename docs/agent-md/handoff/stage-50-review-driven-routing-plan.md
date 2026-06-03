# Stage 50：试听验收驱动路由 + 主屏减负总计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 架构判断

Stage49 已经把 Studio 的 A/B 试听验收写入 `job_artifacts.metadata_json.listening_review`，但它现在只是“能保存评分”。下一阶段不能继续盲目加功能，而要把验收结论变成产品路由：

```text
未验收 -> 进入 Studio A/B 人工试听
需返工 -> 回 Factory / 分离质检 / 重跑 cover
可用 -> 保留为候选试听品
候选成品 -> 进入 Factory 发布候选
废弃 -> 降权展示，不再挤占主屏
```

## 为什么这轮先做这个

- 当前功能链路已经能训练、登记模型、生成 cover、进入 Studio、保存试听验收。
- 用户现在最大痛点不是接口不存在，而是页面一打开像工程日志堆场，不知道下一步该做什么。
- 试听验收是从“开发验证”进入“产品决策”的第一道闸门。
- 这轮不启动 UVR / RVC / 训练 / 大音频任务，避免机器卡爆。

## 分工

### 地基 Agent：Stage50A

负责把 `listening_review` 变成稳定后端契约：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-50a-review-routing-backend-prompt.md
```

### 产品 Agent：Stage50B

负责让 Dashboard / Factory / Studio 根据验收结论给出清晰下一步，并继续折叠长列表：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-50b-review-routing-product-prompt.md
```

## 执行顺序

推荐顺序：

```text
先跑 Stage50A 地基 -> 再跑 Stage50B 产品
```

如果两个 agent 同时跑，产品 agent 必须兼容后端契约未完成的空状态，不能 mock 成功。

## 本轮验收核心

- `python -m backend.self_check` 仍然 PASS。
- Stage49 review API 不回退。
- Dashboard / Factory / Studio 不再默认铺满长日志、长路径、长模型列表。
- Studio 保存验收后，页面明确显示下一步 CTA，但不能自动触发重任务。
- worker 报告必须无中文乱码。

## 架构师调度记录

本轮拆成两个 worker 方向：

```text
地基 Agent：Stage50A 后端 review routing 契约、API、测试、worker 报告。
产品 Agent：Stage50B 前端 review routing UI、主屏减负、Playwright smoke、worker 报告。
```

注意：架构师曾短暂启动过一组测试 sub-agent，但它们不会显示在用户桌面的可见 agent 窗口中，已立即关闭，不作为正式执行者。

本轮正式改用架构师内部 sub-agent 执行，由架构师统一派活、等待、验收：

```text
地基 sub-agent：Gibbs / 019e88ea-753e-75a1-b469-e3b8040f0542
产品 sub-agent：Descartes / 019e88ea-75f9-7663-92be-3a1e7ca61cb3
```

写入边界：

```text
地基 Agent 不碰前端文件。
产品 Agent 不碰后端文件。
双方都不得回滚或覆盖他人改动。
```

## 收口状态

Stage50 已由架构师主线程接管完成：

```text
Stage50A 后端：已完成，worker 报告见 docs\agent-md\worker\stage-50a-review-routing-backend-report.md
Stage50B 产品：已完成，worker 报告见 docs\agent-md\worker\stage-50b-review-routing-product-report.md
FastAPI：已重启，/api/reviews/artifacts 已在线
```

最终验证：

```text
python -m pytest tests\api\test_stage49_listening_review_api.py tests\api\test_stage50_review_routing_api.py -q -> 10 passed
python -m pytest tests\api\test_track_studio_versions_api.py -q -> 6 passed
python -m backend.self_check -> SELF_CHECK_SUMMARY PASS
node frontend\playwright_stage50_review_routing_product_smoke.cjs -> PASS
python -m pytest -q -> 81 passed, 2 warnings
```

本轮未触发训练/RVC/UVR/cover，也未覆盖真实人工试听结论。
