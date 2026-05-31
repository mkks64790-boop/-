# 第20阶段执行汇报：Engine Center 最小落地 + Factory 验收补洞

## 完成情况

- 已完成：
  - `/api/health` 扩展为可描述引擎用途的 engine summary。
  - Dashboard 顶部 `RVC 在线` 区域升级为最小引擎入口，支持 `打开引擎 / 复制地址 / 查看用途`。
  - `launcher` 护栏检查接入 `self_check`，覆盖 `--noautoopen` 与 `8000` 主入口。
  - `Factory` 浏览器 smoke 落地。
  - `track_service` 单测补齐。
- 部分完成：
  - 引擎中心目前仍是单引擎可视化入口，不包含第二套真实引擎实现。
- 未完成：
  - 暂无。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\self_check.py`
- `D:\FeiSharkStudio-v2\backend\voice_changer.py`
- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\js\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\ui.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_smoke.cjs`
- `D:\FeiSharkStudio-v2\tests\unit\test_track_service.py`

## 功能结果

### 引擎状态区

- `/api/health` 现在返回 engine summary，可描述：
  - `engine_kind`
  - `base_url`
  - `online`
  - `rvc_root`
  - `cover_inference_mode`
  - `train_backend_mode`
- 前端会明确显示：
  - 翻唱推理走 `RVC WebUI API / 本地兼容入口`
  - 训练走 `本地 RVC 脚本`
  - `RVC` 安装目录可能在仓库外

### Dashboard / 顶部入口

- `RVC 在线` 不再只是状态灯。
- 顶部新增：
  - `打开引擎`
  - `复制地址`
  - `查看用途`
- `查看用途` 会展开用途说明与关键引擎信息。

### Launcher 护栏

- 保持 `feishark-launcher.ps1` 的既有行为：
  - 启动 RVC 时仍带 `--noautoopen`
  - 浏览器最终打开 `http://127.0.0.1:8000/`
- `self_check` 已补充 launcher 护栏检查。

### Factory 验收补洞

- 新增 `tests/unit/test_track_service.py`
- 新增 `frontend/playwright_factory_smoke.cjs`
- `Factory` 浏览器 smoke 已覆盖：
  - 打开 `/factory`
  - 创建 batch
  - 导入曲目
  - 选中曲目
  - 生成歌词草稿
  - 生成时间轴版本
  - 晋级当前歌词版本

## 验证结果

```text
python -m pytest -q
结果：
7 passed, 2 warnings

python -X utf8 backend/self_check.py
结果：
PASS

python -X utf8 backend/smoke_stage9.py
结果：
PASS

node frontend/playwright_stage17_smoke.cjs
结果：
PASS

node frontend/playwright_stage18_smoke.cjs
结果：
PASS

node frontend/playwright_stage19_smoke.cjs
结果：
PASS

node frontend/playwright_factory_smoke.cjs
结果：
PASS
```

## 已知限制

- 当前仍只有一套真实底层引擎：本地 RVC。
- `RVC` 仍是仓库外依赖，当前阶段只做健康可视化与入口说明，不做仓库内整合。
- Dashboard 的引擎入口不提供浏览器内重启能力，这是刻意保留的安全边界。
- `Factory` 目前完成到 `batch / track / lyrics`，尚未把 track 与实际 cover job 做链路打通。

## 交接说明

- 下一阶段优先把 `Factory` 数据层与现有 `job` 系统打通。
- 建议从 `track -> cover job` 桥接开始，而不是继续堆新页面。
- 后续所有阶段继续沿用：
  - `docs/agent-md/architect/*.md`
  - `docs/agent-md/worker/*.md`

