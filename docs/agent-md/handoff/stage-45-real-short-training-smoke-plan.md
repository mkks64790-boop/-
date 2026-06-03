# Stage 45：真实短样本训练 smoke 验收计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 当前状态

Stage 44 已完成训练调参台接管训练契约：

```text
pytest：59 passed
self_check：PASS
Stage44 dry-run：PASS
Stage44B browser smoke：PASS
training_config 可保存到 job metadata
RVC train.py 命令预览可映射 epochs / batch / sample_rate / f0 / index
默认没有启动 train.py
```

## Stage 45 总目标

用一个可控短样本验证真实训练链路：

```text
training_config -> train job -> RVC preprocess -> feature/pitch -> train.py -> index/register 或失败分类
```

本阶段不是追求模型质量，而是验证“真实训练是否被正确调度、可观察、可中断、可收口”。

## 安全原则

```text
默认不启动 train.py。
只有显式 --execute-smoke 才允许真实训练。
禁止使用 45 分钟长素材。
禁止使用用户未确认的大素材。
真实 smoke 只允许 fast_preview 派生配置，epochs 建议 1-3。
训练超时必须短，建议 10-15 分钟内。
任何失败必须分类：环境失败 / 数据集不足 / RVC 脚本失败 / GPU 忙 / 超时。
```

## 双 Agent 分工

### Stage 45A：地基 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-45a-real-short-training-runtime-backend-prompt.md
```

重点：

```text
新增真实短训练 smoke 验证脚本。
默认 dry-run。
可选 --execute-smoke 受安全闸限制。
验证 training_config 真正进入 RVC train.py。
失败也要能明确分类，不许糊成“失败”。
```

### Stage 45B：产品 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-45b-training-runtime-observability-product-prompt.md
```

重点：

```text
训练运行中 UI 可观察。
显示 preset、epochs、batch、当前阶段、预计状态。
明确提示：训练中不要关闭后端/RVC。
失败后给下一步，而不是只显示红色失败。
```

## Stage 45 后路线

```text
Stage 46：如果短训练成功，跑一次用户指定短干声训练并做模型登记验收。
Stage 47：长样本训练稳定性，恢复/断点/超时策略。
Stage 48：Studio WebAudio 修音室 v1。
Stage 49：再评估 VST 或 SVC/SVT 真实接入。
```
