# Stage 48B：Memory Lab 产品页面与真实 API smoke

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本轮目标是把 Memory Lab 做成可用的本地工程记忆页面/面板，不能只摆一个空壳。

## 前置依赖

地基 Stage48A 应提供：

```text
GET  /api/memory
GET  /api/memory/summary
POST /api/memory/rescan
POST /api/memory
PATCH /api/memory/{memory_id}
```

如果后端未完成，页面必须显示真实空态，不允许 mock 成功。

## 必须实现

### 1. 增加 Memory Lab 入口

在现有三页结构中加入入口，优先：

```text
Dashboard 顶部导航 / 或 Dashboard 主区卡片
```

不要破坏 Dashboard / Factory / Studio 现有布局。

### 2. Memory Lab 面板内容

至少包含：

- 总览：memory 总数、pinned 数、最新阶段。
- 搜索框。
- category/tag 过滤。
- pinned 优先区。
- 阶段时间线。
- Stage47 关键卡：
  - `v_d4d7e1c1 / 朱朱_stage47_single_long`
  - `task_b2272d133fff`
  - `BLOCK_TRAINING=false`
  - `Stage47 Studio scope 仍需产品修复` 如果存在。

### 3. 交互

- 点击 memory 可展开详情。
- source_path 可显示但要截断，hover 或展开显示完整路径。
- 支持 pin/unpin。
- 支持手动触发 rescan。
- rescan 过程中不能卡死页面。

### 4. 真实 API smoke

新增：

```text
frontend\playwright_stage48b_memory_lab_smoke.cjs
```

要求：

- 使用真实 `127.0.0.1:8000`。
- 禁止 mock `/api/memory*` 作为最终通过。
- 必须验证：
  - Memory Lab 入口存在。
  - summary 有真实数量。
  - Stage47 关键 memory 可见。
  - 搜索可过滤。
  - pin/unpin 不报错。
  - desktop/mobile 无横向溢出。

## 禁止事项

```text
禁止 mock Memory Lab 成功。
禁止触发训练/RVC/cover。
禁止把长报告全文铺满页面。
禁止破坏 Stage47 看板。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage48b_memory_lab_smoke.cjs
node frontend\playwright_stage48b_memory_lab_smoke.cjs
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-48b-memory-lab-product-ui-report.md
```

报告必须包含：

```text
是否完成
Memory Lab 入口位置
真实 memory 数量
Stage47 memory 是否显示
pin/unpin 是否可用
真实 API smoke 结果
是否触发训练/RVC：必须为否
测试结果
```
