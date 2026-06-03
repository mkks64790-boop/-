# Stage 42A Local AI Engine Manager 后端报告

## 是否完成

已完成 Stage 42A 后端最小落地。

本轮建立了 Local AI Engine Manager 只读服务层，新增 RVC / UVR / SVC(SVT) 统一引擎契约与 API。没有启动 `train.py`，没有执行长训练，没有执行长 cover 压测，没有删除、移动或覆盖 `D:\RVC\RVCv2` 内文件。

## 新增/修改文件

- `backend/services/engine_manager_service.py`
  - 新增只读 Engine Manager 服务。
  - 统一输出 `engine_key / label / status / role / base_url / root_path / detected / read_only / checks / models / warnings / next_step`。
  - RVC：读取 `D:\RVC\RVCv2`、探测 WebUI、检查关键目录与脚本、扫描 `.pth/.index`、按同名/包含关系配对、标注是否已登记到 FeiShark。
  - UVR：读取当前项目使用的 `backend/vocal_separator.py` 配置，检查 AudioPipeline 根目录、venv、UVR 模型和 runner。
  - SVC/SVT：读取 `FEISHARK_SVC_ROOT` 作为占位配置；未配置时返回 `not_configured`，不伪装可用。

- `backend/main.py`
  - 新增 Engine Manager API 路由。
  - 路由保持只读，不改变既有 cover/train/diagnostics/jobs/models API 契约。

- `backend/self_check.py`
  - 新增 `/api/engines` 契约检查，只验证结构和状态枚举，不要求外部 RVC/UVR/SVC 必须在线。
  - 调整 `cover preflight usable model`：当模型文件可用但仅因外部 RVC WebUI 离线失败时，自检不再失败，并在 detail 中明确 `external_rvc_offline=True`。

- `tests/api/test_engines_api.py`
  - 新增 API 测试覆盖未配置 RVC/SVC、RVC 离线不 500、RVC `.pth/.index` 配对、已登记模型标注、单引擎详情与未知 key 404。

## 新增 API 列表

- `GET /api/engines`
  - 返回 RVC / UVR / SVC(SVT) 三类摘要。
  - RVC 摘要保留 `model_count / registered_model_count`，不默认返回 400 条模型明细，避免 Factory 首屏响应臃肿。

- `GET /api/engines/{engine_key}`
  - 支持 `rvc` / `rvc_webui` / `uvr` / `svc` / `svt` / `svc_fallback`。

- `POST /api/engines/scan`
  - 只读扫描，不启动训练、不启动 cover、不启动外部引擎。

- `GET /api/engines/rvc/models`
  - 返回第三方 RVC 可读模型列表，并标注是否已登记到 FeiShark。

## RVC 检测结果

- `engine_key`: `rvc_webui`
- `status`: `offline`
- `root_path`: `D:\RVC\RVCv2`
- `base_url`: `http://127.0.0.1:7866`
- `detected`: `true`
- 关键路径检查：
  - `rvc_root`: PASS
  - `rvc_weights_dir`: PASS
  - `rvc_indices_dir`: PASS
  - `rvc_logs_dir`: PASS
  - `rvc_infer_web`: PASS
  - `rvc_train_script`: PASS
  - `rvc_webui`: FAIL / offline
- 扫描结果：
  - `model_count`: 400（达到只读扫描上限）
  - `registered_model_count`: 120
- `next_step`: 启动本机 RVC WebUI，并确认 Gradio API 地址可访问。

## UVR 检测结果

- `engine_key`: `uvr`
- `status`: `online`
- `root_path`: `C:\Users\ASUS\AudioPipeline`
- 检查结果：
  - `uvr_root`: PASS
  - `uvr_python`: PASS
  - `uvr_model`: PASS
  - `uvr_runner`: PASS
- `model_count`: 1
- `next_step`: UVR 本地分离入口已就绪。

## SVC/SVT 检测结果

- `engine_key`: `svc_fallback`
- `status`: `not_configured`
- `detected`: `false`
- `FEISHARK_SVC_ROOT`: 未配置
- `next_step`: 本阶段仅预留 SVC/SVT 备用引擎契约；如需接入，请先配置 `FEISHARK_SVC_ROOT`。

## 是否启动 train.py

否。

## 是否修改 D:\RVC\RVCv2

否。

本轮只读扫描 `D:\RVC\RVCv2`，未复制、删除、移动、重命名或覆盖其中任何文件。

## 测试结果

- `python -m py_compile backend\services\engine_manager_service.py backend\main.py backend\self_check.py`
  - PASS

- `python -m pytest -q tests\api\test_engines_api.py`
  - PASS，`3 passed`

- `python -m pytest -q`
  - PASS，`52 passed`

- `python -m backend.self_check`
  - PASS
  - `CODE_STRUCTURE_SUMMARY PASS`
  - `RUNTIME_ENVIRONMENT_SUMMARY PASS`
  - `SELF_CHECK_SUMMARY PASS`

- `python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/engines').json())"`
  - PASS
  - 返回 RVC offline / UVR online / SVC not_configured 的稳定结构。

- `python backend\verify_stage41_recovered_model_cover_smoke.py`
  - FAIL，原因是外部 RVC WebUI 当前离线。
  - 失败点为 `rvc_service` 与 `rvc_model_load_probe`。
  - 本轮未按红线擅自启动或重启 RVC，因此保留为外部环境阻塞。

## 遗留风险

- RVC WebUI 当前未在线，`verify_stage41_recovered_model_cover_smoke.py` 无法通过真实 cover preflight；需要在外部启动 `http://127.0.0.1:7866` 后复跑。
- RVC 模型扫描命中上限 400，说明 `D:\RVC\RVCv2` 内历史模型/日志很多；当前摘要 API 已避免默认返回完整列表，但 `/api/engines/rvc/models` 仍会返回扫描上限内的完整列表。
- SVC/SVT 仍是契约占位，未接入真实 runner，后续 Stage 44 再做真实适配更安全。
- `/api/engines` 目前是同步只读扫描；如果未来外部 RVC 模型数量继续膨胀，可以再做缓存或分页，但本阶段刻意不引入 Redis / WebSocket / 分布式组件。
