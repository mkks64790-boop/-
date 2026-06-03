# Stage 44：训练调参台接管真实训练契约计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## Stage 43 验收结论

Stage 43 已完成：

```text
pytest：55 passed
self_check：PASS
Stage43 Studio 入口契约：PASS
Stage43B Playwright smoke：PASS（重启后端后）
task_stage41_ce1b32f2：can_open_studio=true，可进入 Studio
RVC models：分页/搜索契约可用，total=400，limit 生效
训练调参：/api/training/presets 与 /api/training/estimate 可用，且不创建 job
```

注意：如果产品 smoke 看到接口缺失，优先检查 8000 后端是否重启。当前代码本身已通过。

## 当前遗留

```text
训练调参台 v0 仍只是估算/解释，尚未真正接管 train job。
训练创建表单尚未稳定携带 preset_key / epochs / batch_size / sample_rate / f0_enabled / index_enabled。
RVC train 命令仍需要确认是否能安全接受调参台配置。
Factory 截图里中部 sticky 导航会压住内容，产品侧需要顺手整理。
```

## Stage 44 总目标

让训练调参台从“看得懂”升级到“能安全影响训练任务”。

目标闭环：

```text
用户选择训练 preset -> 前端提交训练配置 -> 后端保存训练配置 -> 训练策略读取配置 -> RVC 命令使用配置
```

本阶段默认不启动长训练。只允许 dry-run / contract smoke。真实训练执行必须显式开关，例如 `--execute-smoke`，并且只能用短样本。

## 双 Agent 分工

### Stage 44A：地基 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-44a-training-preset-runtime-backend-prompt.md
```

重点：

```text
训练 job 保存 training_config。
训练策略读取 training_config。
RVC 命令参数由 preset/config 控制。
新增 dry-run 验证脚本，不默认启动 train.py。
```

### Stage 44B：产品 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-44b-training-preset-runtime-product-prompt.md
```

重点：

```text
训练表单接入 preset。
创建训练前展示最终参数确认。
任务详情展示训练配置。
修复 Factory sticky 导航遮挡和调参台布局。
```

## Stage 44 后路线

```text
Stage 45：真实短样本训练验收，跑 fast_preview 小训练并验证模型登记。
Stage 46：Studio WebAudio 修音室 v1，做 EQ/压缩/响度/导出。
Stage 47：外部 RVC 模型资产治理，批量导入、重名策略、模型分组。
Stage 48：评估 SVC/SVT 或 VST 桥接。
```
