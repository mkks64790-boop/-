# Stage 50B Review Routing Product Report

## 是否完成

已完成。

## Dashboard 试听验收队列

位置：

```text
frontend/index.html
frontend/js/jobs.js
```

已增加并接通真实 `/api/reviews/artifacts`：

```text
未验收数量
需返工数量
候选成品数量
最近 3 个待处理成品
进入 Studio A/B
下载
```

不会 mock 成功；接口不可用时显示真实空状态/错误状态。

截图：

```text
output/playwright/stage50_review_routing_dashboard.png
```

## Studio 下一步动作区域

位置：

```text
frontend/studio.html
frontend/js/studio.js
```

`试听验收 A/B` 面板下方已渲染“下一步动作”：

```text
needs_human_review        -> 继续人工试听
route_to_rework           -> 回 Factory 调分离 / 重跑 cover
route_to_candidate_pool   -> 保留为可用候选
route_to_release_candidate -> 送入 Factory 候选成品
route_to_archive_or_rerun -> 标记废弃，建议重跑
```

动作只做导航或提示，不会自动触发训练/RVC/UVR/cover。

如果检测到：

```text
stage49 browser smoke only - not a human quality verdict
```

会提示“浏览器 smoke 记录，不是人工验收”。

截图：

```text
output/playwright/stage50_review_routing_studio.png
```

## Factory 候选 / 返工折叠区

位置：

```text
frontend/factory.html
frontend/js/factory/main.js
frontend/css/app.css
```

已接通真实 `/api/reviews/artifacts`，按以下分组：

```text
候选成品：release_candidate + usable
需返工：needs_work
未验收：unreviewed
```

列表默认收起，展开后最多展示 10 条，避免 Factory 主屏再次变成长蛇阵。

每条支持：

```text
进入 Studio
下载
查看来源 job
```

截图：

```text
output/playwright/stage50_review_routing_factory.png
```

## 主屏减负处理清单

已保持或补齐：

```text
Dashboard 试听验收队列只显示最近 3 条。
Dashboard Memory Lab 完整列表仍默认折叠。
Dashboard 任务详情产物、技术详情、训练配置、阶段日志仍默认折叠。
Factory 验收路由列表默认收起，展开体有 max-height 滚动。
Factory 模型资产/RVC 模型仍默认折叠。
Studio 试听品库和技术详情仍默认折叠。
```

## 真实浏览器 smoke 结果

命令：

```powershell
node frontend\playwright_stage50_review_routing_product_smoke.cjs
```

结果：

```text
PASS
queueSummary.total = 89
unreviewed = 89
needs_work = 0
usable = 0
release_candidate = 0
rejected = 0
pageErrors = []
unsafeCalls = []
desktop/mobile horizontal overflow = false
```

## 其它测试

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage50_review_routing_product_smoke.cjs
python -m pytest -q
python -m backend.self_check
```

结果：

```text
JS syntax PASS
Playwright Stage50B PASS
pytest: 81 passed, 2 warnings
SELF_CHECK_SUMMARY PASS
```

## 是否触发训练/RVC/UVR/cover

否。

## 是否覆盖真实人工验收结论

否。本轮产品 smoke 只读 `/api/reviews/artifacts`、Dashboard、Studio、Factory，不 PATCH review。

## 是否存在中文乱码

否。本报告和新增前端文案均为正常 UTF-8 中文。

