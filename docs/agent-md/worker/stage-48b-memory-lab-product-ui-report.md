# Stage 48B Memory Lab 产品 UI 报告

## 是否完成

产品侧已完成。

- Dashboard 顶部导航新增 `Memory Lab` 入口。
- Dashboard 主区新增 `Memory Lab · 本地工程记忆` 面板。
- 面板已接真实 `/api/memory*`，支持 summary、搜索、category/tag 过滤、pinned 优先区、阶段时间线、Stage47 关键卡、详情展开、source_path 截断/展开、pin/unpin、rescan。
- 后端未开放时显示真实空态，不 mock 成功。

## Memory Lab 入口位置

- 顶部导航：`Memory Lab` 锚点入口。
- Dashboard 主区：Stage47 闭环验收卡下方的 `#memoryLabPanel`。

## 真实 memory 数量

当前真实 API 状态：

- `GET /api/memory/summary`：404
- `GET /api/memory?limit=100&offset=0`：404
- memory 数量：不可读，UI 显示 `-`

结论：Stage48A 后端 API 当前尚未接入运行中的服务，产品侧没有伪造数量。

## Stage47 memory 是否显示

否。

原因：真实 `/api/memory*` 当前 404，无法读取 Stage47 memory。UI 显示：

```text
Memory API 未开放，不能伪造 Stage47 memory。
```

Smoke 已验证没有把 `v_d4d7e1c1 / 朱朱_stage47_single_long / task_b2272d133fff / BLOCK_TRAINING=false` mock 到页面里。

## pin/unpin 是否可用

产品交互已实现，真实 API 可用时会调用：

```text
PATCH /api/memory/{memory_id}
```

当前由于 memory API 404，smoke 未执行真实 pin/unpin 数据变更；页面不会卡死，也不会显示假成功。

## 真实 API smoke 结果

已通过：

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage48b_memory_lab_smoke.cjs
node frontend\playwright_stage48b_memory_lab_smoke.cjs
```

Smoke 摘要：

- memoryApiAvailable：`false`
- summaryStatus：`404`
- memoryStatus：`404`
- Stage47 count：`0`
- Memory Lab 入口：存在
- Memory Lab 面板：存在
- desktop/mobile 横向溢出：无
- pageErrors：`[]`
- unsafeCalls：`[]`

截图：

```text
output/playwright/stage48b_memory_lab.png
```

## 是否触发训练/RVC

否。

Smoke 监听到的危险请求为：

```text
unsafeCalls=[]
```

未触发 `/api/train`、`/api/process/*`、`/cover-jobs`、`/api/cover`、`/rvc/infer` 或 `/infer`。

## 下一步

等待地基 Stage48A 把 `/api/memory*` 接入运行服务。接入后同一个 smoke 会继续验证真实 memory 数量、Stage47 关键 memory、搜索过滤、pin/unpin。
