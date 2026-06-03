# Stage 47C：Studio Stage47 范围标注返工

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本轮是小返工，不是大改 UI。

## 打回事实

架构师复验 Stage47A 后，地基闭环通过：

```text
training job: train_7f4d6b4e611e
model: v_d4d7e1c1 / 朱朱_stage47_single_long
cover job: task_b2272d133fff
artifact: art_f99f7e4afb10
Studio playable: yes
```

但是真实浏览器 smoke 失败：

```text
node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs

Error: Studio does not mark Stage47 cover scope
```

说明 Studio 能播放，但没有把这个成品明确标注为：

```text
Stage47 短 smoke / 完整 cover
```

这会误导用户以为它是正式完整成品。

## 必须修复

### 1. Studio 页面标注 Stage47 cover scope

当 Studio 打开以下任务时：

```text
job_id=task_b2272d133fff
artifact_id=art_f99f7e4afb10
voice_model_id=v_d4d7e1c1
```

或当 job/model metadata 能识别为 Stage47 时，Studio 必须显示醒目标注：

```text
Stage47 短 smoke
```

并显示解释：

```text
这是 60 秒受控翻唱 smoke，用于验证训练模型、UVR、RVC、混音、Studio 试听闭环；不是正式完整歌曲成品。
```

### 2. Dashboard / Studio 文案一致

Dashboard 当前已经能识别 Stage47 闭环。Studio 进入后也必须保留同样语义，不能只显示普通 `final_master.wav`。

### 3. 修正真实 smoke

修改：

```text
frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

要求：

- 不要降低断言。
- 必须真实确认 Studio 文本包含 `Stage47` 和 `短 smoke` 或等价明确文案。
- 必须继续确认播放器 `audioSrc` 和下载链接可用。

## 禁止事项

```text
禁止 mock Stage47 成功。
禁止触发训练/RVC/cover。
禁止把 60 秒 smoke 标成正式完整成品。
禁止删除或改动地基产物。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-47c-product-studio-stage47-scope-hotfix-report.md
```

报告必须包含：

```text
是否完成
Studio 是否显示 Stage47 短 smoke
播放器是否仍可用
下载链接是否仍可用
是否触发训练/RVC：必须为否
测试结果
```
