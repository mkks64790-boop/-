# Stage XX Prompt Template

## 阶段标题

一句话写清楚这轮要解决的核心问题。

## 背景

- 当前项目已经具备什么
- 这轮为什么要做
- 哪些前置阶段已经完成

## 本阶段目标

- 目标 1
- 目标 2
- 目标 3

## 必读文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\frontend\index.html`

按实际阶段补充，不要写空列表。

## 实施范围

明确这轮允许改什么，不允许改什么。

### 允许修改

- 后端
- 前端
- 测试
- 文档

### 禁止事项

- 不要推倒重来
- 不要破坏现有 `cover/train`
- 不要引入额外复杂中间件

## 具体任务

### 1. 任务一

写清楚要改到什么程度。

### 2. 任务二

写清楚需要交付什么。

### 3. 任务三

写清楚如何验证。

## 交付要求

执行 agent 完成后，必须输出：

1. 改了哪些文件
2. 实现了哪些功能
3. 跑了哪些测试
4. 还有哪些已知限制
5. 将汇报写入 `docs/agent-md/worker/stage-XX-简短主题-report.md`

## 验证要求

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`

按实际阶段补充 smoke / playwright / verify。

## 完成标准

- 标准 1
- 标准 2
- 标准 3

