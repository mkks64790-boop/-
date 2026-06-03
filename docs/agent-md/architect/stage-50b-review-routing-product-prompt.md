# Stage 50B：试听验收驱动 UI 路由 + 主屏减负

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本轮任务是把 Stage49/Stage50A 的试听验收结果变成用户看得懂的下一步，同时继续解决 Dashboard / Factory / Studio 主屏臃肿问题。

## 前置契约

优先使用 Stage50A 后端契约：

```text
GET /api/reviews/artifacts
GET /api/jobs
GET /api/jobs/{job_id}
GET /api/jobs/{job_id}/artifacts
```

如果 Stage50A 尚未完成，页面必须显示真实空状态或“等待后端契约”，不能 mock 成功。

## 本轮目标

用户打开页面时，不应该先看到一地工程痕迹，而应该看到：

```text
哪些成品没听过
哪些需要返工
哪些可以作为候选成品
现在下一步该去 Studio 听，还是回 Factory 调，还是保留候选
```

## 必须实现

### 1. Dashboard 增加“试听验收队列”轻量卡

在 Dashboard 主区靠上位置增加一个轻量卡片，读取真实 `/api/reviews/artifacts`。

必须展示：

```text
未验收数量
需返工数量
候选成品数量
最近 3 个待处理成品
```

每个 item 必须有：

```text
文件名或 job 名
验收状态 badge
进入 Studio A/B
下载
```

禁止展示超长路径、完整 metadata、长 job id。长 ID 只能截断并 hover 显示。

### 2. Studio 保存验收后显示“下一步动作”

在 `frontend/studio.html` / `frontend/js/studio.js` 中，A/B 验收面板保存后必须根据 `review_route` 显示 CTA：

```text
needs_human_review        -> 继续人工试听
route_to_rework           -> 回 Factory 调分离/重跑 cover
route_to_candidate_pool   -> 保留为可用候选
route_to_release_candidate -> 送入 Factory 候选成品
route_to_archive_or_rerun -> 标记废弃，建议重跑
```

要求：

- CTA 只能导航或提示，不允许自动发起训练、RVC、UVR、cover。
- 如果备注是 `stage49 browser smoke only - not a human quality verdict`，必须显示“浏览器 smoke 记录，不是人工验收”的提醒。
- 保存成功后本面板状态立即刷新，不需要用户重新打开页面。

### 3. Factory 增加“候选成品 / 需返工”折叠区

在 Factory 页面增加或复用一个折叠区，读取 `/api/reviews/artifacts`：

```text
候选成品 release_candidate
需返工 needs_work
未验收 unreviewed
```

默认只展示摘要，列表默认收起。用户展开后才看到最多 10 条。

每条允许：

```text
进入 Studio
下载
查看来源 job
```

禁止自动启动重任务。

### 4. 主屏减负硬约束

继续压缩当前三个页面的工程痕迹：

```text
Dashboard Memory Lab：默认只显示摘要和最近 6 条，完整列表必须折叠并有 max-height 滚动。
Dashboard 阶段日志：默认收起，只保留最近阶段摘要。
Dashboard 任务详情：长字段必须单行截断 + title hover；详情区必须有 max-height 滚动，不许把页面撑成长蛇。
Factory RVC 模型列表：默认收起，只展示数量、可用数量、当前筛选。
Factory 批次列表：默认收起，只显示当前批次摘要。
Studio 试听品库 / 技术详情：保持默认收起，保存验收后不要强行展开。
```

### 5. 新增真实浏览器 smoke

新增：

```text
frontend\playwright_stage50_review_routing_product_smoke.cjs
```

要求：

- 使用真实 `127.0.0.1:8000`。
- 禁止 mock `/api/reviews/artifacts` 作为最终通过。
- 验证 Dashboard 有“试听验收队列”。
- 验证 Studio 有“下一步动作”区域。
- 验证 Factory 有“候选成品 / 需返工”折叠区。
- 验证三个页面 desktop/mobile 无横向溢出。
- 验证 smoke 不触发训练、RVC、UVR、cover。
- 如果需要写 review，只允许写回原值，或使用专用 smoke artifact；禁止覆盖真实人工验收结论。

### 6. 报告质量

worker 报告必须使用正常 UTF-8 中文，不允许出现类似：

```text
璇曞惉
楠屾敹
鎴愬搧
```

一旦报告乱码，本轮不算通过。

## 禁止事项

```text
禁止 mock 成功。
禁止自动触发训练/RVC/UVR/cover。
禁止让长日志、长路径、完整 metadata 默认铺满主屏。
禁止覆盖真实人工试听结论。
禁止删除 Stage49 A/B 面板。
禁止把 Factory / Studio 做成纯工程后台。
```

## 必跑验证

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage50_review_routing_product_smoke.cjs
node frontend\playwright_stage50_review_routing_product_smoke.cjs
python -m backend.self_check
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-50b-review-routing-product-report.md
```

报告必须包含：

```text
是否完成
Dashboard 试听验收队列位置与截图路径
Studio 下一步动作区域说明
Factory 候选/返工折叠区说明
主屏减负处理清单
真实浏览器 smoke 结果
desktop/mobile 是否无横向溢出
是否触发训练/RVC/UVR/cover：必须为否
是否覆盖真实人工验收结论：必须为否
是否存在中文乱码：必须为否
```

