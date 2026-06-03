# Stage 47：真实端到端音色训练与翻唱闭环跨越计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 当前已满足的前置条件

Stage46B/46C 已完成并通过架构师复验：

```text
最新 UVR fixed run: stage45r_20260602_193728_d0f83e7c
duration_ratio: 1.0
duration_mismatch: false
BLOCK_TRAINING: false
pytest: 67 passed
self_check: PASS
real browser smoke: PASS
```

桌面干声文件已确认：

```text
C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3      duration=932.702s 约 15.5 分钟
C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3   duration=2709.995s 约 45.2 分钟
```

`朱朱干声唱.mp3` 符合最初定义的“单文件快速训练：30-50 分钟超长单干声文件”输入范围。

## Stage47 总目标

从“分离层修复”跨越到“真实业务闭环”：

```text
干声训练 -> 模型登记 -> 用训练模型翻唱测试音乐 -> 混音成品 -> Studio 可试听 -> UI 可验收
```

## 分工

地基 Agent：

```text
stage-47a-real-single-long-training-cover-closure-prompt.md
```

负责真实后端闭环、训练、模型登记、cover smoke、产物校验。

产品 Agent：

```text
stage-47b-e2e-product-acceptance-dashboard-prompt.md
```

负责把真实训练/模型/翻唱/Studio 状态做成可理解的验收看板和浏览器 smoke。

## 无人值守熔断原则

```text
禁止删除/移动用户桌面干声文件。
禁止覆盖历史模型。
禁止绕过 FeiShark job/service 直接野跑。
禁止并发训练和 cover 抢 GPU。
如果 GPU/磁盘/依赖/预检失败，立即停止并报告。
如果训练超过约定墙钟上限仍无进展，停止或标记 blocked，不要无限跑。
```

## 成功标准

最低成功标准：

```text
生成一个新模型登记记录。
模型 pth/index 可定位。
用新模型跑一次短 cover smoke。
最终音频 artifact 可下载/可在 Studio 试听。
训练和 cover job 状态链路可在 UI 看到。
```

如果真实训练失败，也必须形成可复盘报告：

```text
失败阶段
失败命令/API
GPU/磁盘/依赖状态
日志路径
下一步修复建议
```
