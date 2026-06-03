# Stage 45R：UVR 分离质量审计与电流音排查计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 为什么重写 Stage45

用户反馈：

```text
D 盘有测试音乐，都是主播录音合成好的成品。
这些不是干声，但适合拿来测试人声/伴奏分离效果。
当前分离效果很差，有明显电流音。
```

结论：

```text
先不要进入真实训练。
先验 UVR / 分离层质量。
如果分离层带电流音，后续 RVC 翻唱、训练、混音都会被污染。
```

本阶段替代原 Stage45 训练 smoke。原训练 smoke 先暂停。

## Stage 45R 总目标

建立“分离质量审计”能力：

```text
从 D 盘测试音乐中选 3-5 首短样本
裁剪 30-60 秒片段
调用当前 UVR 分离链路
输出 原曲 / 人声 / 伴奏 三轨
做音量、峰值、高频噪声、削波、静音、采样率等基础检测
让产品侧能 A/B 试听并记录“电流音是否存在”
```

## 安全原则

```text
禁止递归扫完整 D 盘。
禁止删除、移动、覆盖用户 D 盘音乐。
只允许复制或读取短样本。
禁止训练。
禁止 RVC 推理。
禁止自动跑长音频。
默认只做 dry-run / 文件发现。
真实分离必须限制时长，建议 30-60 秒。
```

## 双 Agent 分工

### Stage 45RA：地基 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-45ra-separation-quality-backend-prompt.md
```

重点：

```text
发现 D 盘测试音乐。
新增分离质量审计脚本。
调用当前 UVR 分离链路。
生成分离产物与质量指标。
分类定位电流音来源。
```

### Stage 45RB：产品 Agent

交付：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-45rb-separation-quality-product-prompt.md
```

重点：

```text
做“分离质量实验室”UI。
原曲 / 人声 / 伴奏 A/B 播放。
展示电流音排查指标。
不触发训练或 RVC。
```

## Stage 45R 后路线

```text
如果分离质量过关：回到真实短训练 smoke。
如果分离仍有电流音：Stage46 改做 UVR 配置/模型/采样率/降噪策略优化。
如果只有个别歌曲有问题：建立输入音频预检和修复建议。
```
