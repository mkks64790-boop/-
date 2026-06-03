# Stage 42A：Local AI Engine Manager 后端引擎管理层（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段目标是建立本地 AI 引擎管理层，把第三方 RVC、UVR、SVC/SVT 从零散状态提示升级为统一可诊断、可读取、可扩展的 Engine Adapter。禁止重新训练，禁止长音频 cover 压测，禁止删除或移动 `D:\RVC\RVCv2` 里的任何文件。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-42-engine-manager-and-product-shell-plan.md
D:\FeiSharkStudio-v2\backend\main.py
D:\FeiSharkStudio-v2\backend\services\preflight_service.py
D:\FeiSharkStudio-v2\backend\services\model_service.py
D:\FeiSharkStudio-v2\backend\model_trainer.py
D:\FeiSharkStudio-v2\backend\voice_changer.py
```

## 必做任务

### 1. 新增 Local AI Engine Manager 服务层

新增或整理一个后端服务模块，建议命名：

```text
backend/services/engine_manager_service.py
```

要求输出统一结构：

```json
{
  "engine_key": "rvc_webui",
  "label": "RVC WebUI",
  "status": "online | offline | degraded | not_configured",
  "role": "voice_conversion | source_separation | svc_fallback",
  "base_url": "http://127.0.0.1:7866",
  "root_path": "D:\\RVC\\RVCv2",
  "detected": true,
  "read_only": true,
  "checks": [],
  "models": [],
  "warnings": [],
  "next_step": ""
}
```

状态必须真实，不允许假装可用。

### 2. 第三方 RVC 读取适配

读取并诊断本机第三方 RVC：

```text
默认 WebUI：http://127.0.0.1:7866
默认根目录：D:\RVC\RVCv2
重点目录：assets\weights, assets\indices, logs
重点脚本：infer-web.py, infer\modules\train\train.py
```

必须做到：

- 能判断 WebUI 是否在线。
- 能判断 RVC 根目录是否存在。
- 能扫描 `.pth` 与 `.index`，并尝试按同名或包含关系配对。
- 能识别已被 FeiShark 登记的模型和外部未登记模型。
- 只读扫描，不复制、不删除、不重命名。
- 若路径不存在，返回 `not_configured` 或 `degraded`，并给明确 next_step。

### 3. UVR 读取适配

新增 UVR 引擎检查：

```text
engine_key = uvr
role = source_separation
```

要求：

- 读取当前项目里实际使用的 UVR/分离配置或脚本路径。
- 检查 UVR 入口是否存在。
- 检查模型目录或分离模型配置是否可用。
- 如果项目当前没有独立 UVR 配置，不要硬编假路径，返回 `not_configured`，但给出建议字段。

### 4. SVC/SVT 备用引擎占位适配

新增备用声线引擎占位：

```text
engine_key = svc_fallback
role = svc_fallback
```

要求：

- 不强行实现真实 SVC。
- 可从环境变量或配置读取候选路径，例如 `FEISHARK_SVC_ROOT`。
- 未配置时明确返回 `not_configured`。
- API 结构必须和 RVC/UVR 一致，方便产品层后续直接接 UI。

### 5. 新增 API

在不破坏既有接口的前提下新增：

```text
GET /api/engines
GET /api/engines/{engine_key}
POST /api/engines/scan
GET /api/engines/rvc/models
```

要求：

- `/api/engines` 返回 RVC、UVR、SVC/SVT 三类摘要。
- `/api/engines/rvc/models` 返回外部 RVC 可读模型列表，并标注是否已登记到 FeiShark。
- `POST /api/engines/scan` 只触发只读扫描，禁止启动长任务。
- 如果已有 diagnostics 接口能复用，允许内部复用，但不要改坏现有诊断页面。

### 6. 加入自检与测试

新增单元测试或 API 测试覆盖：

- RVC 路径不存在时返回 `not_configured/degraded`。
- RVC WebUI 离线时不影响主服务。
- `.pth/.index` 扫描能返回稳定结构。
- SVC/SVT 未配置时不会报 500。
- `/api/engines` 基本契约稳定。

自检补充：

```text
backend.self_check 可以检查 /api/engines 结构，但不要要求所有外部引擎必须在线。
```

## 禁止事项

```text
禁止启动 train.py。
禁止跑长训练。
禁止跑长 cover 压测。
禁止删除、移动、覆盖 D:\RVC\RVCv2 内文件。
禁止把 SVC/SVT 假装成已可用。
禁止改坏 Stage 41 的恢复模型 cover 验收脚本。
```

## 必测命令

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage41_recovered_model_cover_smoke.py
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/engines').json())"
```

如果需要验证真实 RVC 在线状态，只允许读：

```powershell
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/engines/rvc/models').json())"
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-42a-local-ai-engine-manager-backend-report.md
```

报告必须包含：

```text
是否完成
新增/修改文件
新增 API 列表
RVC 检测结果
UVR 检测结果
SVC/SVT 检测结果
是否启动 train.py：必须为否
是否修改 D:\RVC\RVCv2：必须为否
测试结果
遗留风险
```

## 本阶段好处

```text
把 RVC 在线页从“装饰状态”变成真正的引擎管理入口。
给 UVR、RVC、SVC/SVT 后续整合留出统一接口。
产品层可以基于 /api/engines 做正式 Engine Manager UI，不再到处硬编码路径。
```
