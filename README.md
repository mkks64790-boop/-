[README.md](https://github.com/user-attachments/files/28349879/README.md)
# FeiShark Studio

本地 AI 翻唱与音色训练工作台，围绕 `RVC` 构建，目标是把「训练自己的声音」和「用训练好的声音替换原唱」收口成一套可持续演进的本地产品。

当前项目方向：

- `Dashboard` 工作台：任务中心、快捷创建、模型资产、系统诊断
- `Studio` 修音室：逐步承接成品试听、后处理、导出
- `Local AI Engine`：本地 `UVR / RVC / 混音 / 导出` 执行链

## 当前能力

- AI 一键翻唱
  - 上传带伴奏歌曲
  - 分离人声和伴奏
  - 用训练好的 RVC 音色替换原唱
  - 混音输出成品

- 单文件快速训练
  - 上传长干声
  - 预处理切片
  - 特征提取
  - 模型训练
  - 生成 `.pth / .index`

- 多文件批量精训
  - 上传已清洗的短干声片段
  - 跳过长音频切片
  - 直接进入提取与训练

- 模型资产与诊断
  - 可用模型列表
  - 模型导入/重扫
  - 翻唱与训练前置诊断

## 技术路线

- 前端：原生 HTML / CSS / JavaScript
- 后端：FastAPI
- 推理/训练：本地 RVC
- 浏览器验收：Playwright
- 运行方式：单机、本地队列、本地文件产物

当前明确不做：

- Redis / Celery / WebSocket / 分布式 worker
- 复杂模型热缓存
- 远程 SaaS 化部署

## 目录结构

```text
backend/          FastAPI、任务编排、训练/翻唱策略、验证脚本
frontend/         工作台页面、样式、交互脚本、浏览器验收脚本
logs/             本地运行日志
shared_data/      运行时数据、任务产物、模型权重、上传文件
feishark-launcher.ps1
                  一键启动脚本
```

## 运行要求

建议环境：

- Windows
- Python 3.x
- 本地可运行的 RVC WebUI
- 可用的 `ffmpeg`

关键环境变量：

- `FEISHARK_RVC_DIR`
- `FEISHARK_RVC_PYTHON`
- `FEISHARK_RVC_PORT`
- `FEISHARK_RVC_API`

如果不手动配置，启动脚本会尝试在本机常见路径下自动探测 RVC。

## 快速启动

推荐直接使用启动脚本：

```powershell
cd D:\FeiSharkStudio-v2
.\feishark-launcher.ps1
```

启动脚本会尝试：

1. 检查 Python 环境
2. 探测并启动本地 RVC
3. 启动 FastAPI 后端
4. 打开浏览器访问工作台

默认地址：

- 前端：`http://127.0.0.1:8000/`
- API：`http://127.0.0.1:8000/api/health`
- Docs：`http://127.0.0.1:8000/docs`
- RVC：`http://127.0.0.1:7866`

## 常用验证

后端主链验证：

```powershell
python -X utf8 backend\self_check.py
python -X utf8 backend\smoke_stage9.py
python -X utf8 backend\verify_stage11_train_flow.py
```

浏览器验收脚本：

```powershell
node frontend\playwright_stage15_smoke.cjs
node frontend\playwright_stage16_smoke.cjs
```

## 开发原则

- 先保证翻唱/训练主链稳定，再做视觉和产品层演进
- 不在首页无限堆功能，逐步拆成 `Dashboard / Studio`
- 所有高风险改动都要保留回归验证
- 中间文件清理必须只作用于当前 job 自己的目录

## Git 更新流程

第一次导入后，后续更新仓库就按这个流程走：

```powershell
cd D:\FeiSharkStudio-v2
git status
git add .
git commit -m "写你的更新说明"
git push
```

常见例子：

```powershell
git add .
git commit -m "Refine dashboard layout and diagnostics panel"
git push
```

如果你只是想先看看改了什么：

```powershell
git status
git diff
```

如果你想拉取 GitHub 上的最新内容到本地：

```powershell
git pull
```

## 当前阶段重点

项目正在从“本地测试台”往“可用产品壳”推进，当前主线是：

1. 稳定 Dashboard 工作台
2. 拆出 Studio 修音室
3. 打通成品进入 Studio 的后处理链
4. 后续再评估更重的本地插件宿主或 VST 路线

## 备注

这是一个本地实验型工程，依赖本机环境、RVC 路径和音频工具链。提交代码时，默认不要把模型权重、数据库、运行时产物、音频素材和日志一起推到仓库。
