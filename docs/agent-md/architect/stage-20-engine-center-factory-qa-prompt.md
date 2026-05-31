# 第20阶段：Engine Center 最小落地 + Factory 验收补洞

你现在是 FeiShark Studio 的实施 agent。

这轮不要重写架构，不要碰 `cover/train` 主链路，不要把 RVC 搬进仓库，不要做第二套真实引擎实现。

本阶段目标是：

1. 把 `RVC 在线` 从纯状态灯升级成可理解、可操作的引擎入口
2. 补齐 `factory` 的测试与验收缺口
3. 给启动器增加明确护栏，避免误跳 `7866`

## 必读文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\voice_changer.py`
- `D:\FeiSharkStudio-v2\backend\model_trainer.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\js\ui.js`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\feishark-launcher.ps1`
- `D:\FeiSharkStudio-v2\tests\api\test_batches_api.py`
- `D:\FeiSharkStudio-v2\tests\api\test_tracks_api.py`
- `D:\FeiSharkStudio-v2\tests\api\test_lyrics_api.py`

## 任务范围

### 允许修改

- `/api/health` 及相关引擎状态结构
- Dashboard 顶部引擎状态区
- `factory` 的测试与页面验收
- 启动器文本护栏检查
- 文档与 `.md` 交接文件

### 禁止事项

- 不要把浏览器主入口改成 `7866`
- 不要把 RVC 整合包复制进仓库
- 不要直接做浏览器里的“重启引擎”
- 不要重做 `Dashboard / Studio`
- 不要破坏现有训练与翻唱主链路

## 具体任务

### 1. 引擎状态产品化

基于现有 `/api/health`，补充或扩展出更清晰的引擎状态信息，至少包含：

- `engine_kind`
- `base_url`
- `online`
- `rvc_root`
- `cover_inference_mode`
- `train_backend_mode`

前端必须明确告诉用户：

- 翻唱推理当前通过 RVC WebUI API / 本地兼容入口执行
- 训练当前通过本地 RVC 脚本执行
- 当前 RVC 安装目录可能在工作室仓库外，这是 `v1` 的设计现状，不是 bug

### 2. Dashboard 顶部引擎入口

在现有状态 chip 附近加入最小操作区：

- `打开引擎`
- `复制地址`
- `查看用途`

规则：

- `打开引擎` 只在 `online=true` 时可点击，并新标签页打开当前 `base_url`
- `复制地址` 复制当前 `base_url`
- `查看用途` 弹出或展开说明：
  - 训练用本地脚本
  - 翻唱推理用 WebUI API
  - 工作室前端始终以 `8000` 为主入口

### 3. Launcher 护栏

保持 `feishark-launcher.ps1` 当前行为不退化：

- RVC 启动必须带 `--noautoopen`
- 浏览器最终只能打开 `http://127.0.0.1:8000/`

请补一条轻量检查：

- 检查 launcher 文本中仍存在 `--noautoopen`
- 检查 launcher 打开的目标仍然是 `8000` 前端，而不是 `7866`

### 4. Factory 验收补洞

新增 `tests/unit/test_track_service.py`，至少覆盖：

- `get_track`
- `list_tracks`
- `update_track`
- `set_track_current_lyrics`

新增 `frontend/playwright_factory_smoke.cjs`，至少覆盖：

1. 打开 `/factory`
2. 创建一个 batch
3. 导入至少 2 个曲目
4. 选中一个曲目
5. 生成歌词草稿
6. 生成时间轴版本
7. 晋级当前歌词版本
8. 校验页面状态变化

### 5. 文档编码顺手修正

如果本轮触及的里程碑文档在控制台显示乱码，请统一成 UTF-8 正常中文，但不要改语义。

## 交付要求

完成后必须输出：

1. 改了哪些文件
2. 新增了哪些 engine 字段和前端交互
3. 补了哪些测试
4. 还有哪些已知限制
5. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-20-engine-center-factory-qa-report.md`

## 验证要求

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- `python -X utf8 backend/smoke_stage9.py`
- `node frontend/playwright_stage17_smoke.cjs`
- `node frontend/playwright_stage18_smoke.cjs`
- `node frontend/playwright_stage19_smoke.cjs`
- `node frontend/playwright_factory_smoke.cjs`

## 完成标准

- `RVC 在线` 不再只是纯状态灯
- 用户能理解训练和翻唱分别依赖什么引擎路径
- 启动器不会误跳 `7866`
- `factory` 有独立浏览器 smoke
- `track_service` 单测补齐
- 现有 `Dashboard / Studio / cover / train` 回归不坏

