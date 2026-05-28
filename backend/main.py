"""
FeiShark Studio - FastAPI 核心路由桥接层
轻量解耦方案：为前端界面铺设核心神经通路

路由清单:
  GET  /api/models                → 获取全部音色资产（磁盘真实性验证）
  POST /api/upload_task           → 上传音频文件，创建任务（返回 task_id）
  POST /api/process/{task_id}     → 异步启动 4 步流水线（含模型前置拦截器）
  GET  /api/task_status/{task_id} → 查询任务当前状态（前端轮询驱动）
  POST /api/train                 → 上传多段干声 + 创建训练任务（多文件支持）
  GET  /api/download/{task_id}    → 下载最终成品
  GET  /api/health                → 健康检查

v2.2 变更:
  [NEW] CORSMiddleware            - 全源跨域，允许所有前端直连
  [FIX] /api/upload_task         - 流式分块写入（1 MB/chunk），根治大文件超时崩溃
  [FIX] /api/train               - 多文件均改为流式分块写入
  [FIX] /api/models              - try-except 金刚罩，磁盘异常降级返回 DB 原始记录
"""

import os
import mimetypes
import uuid
import time
import traceback
import sys
import threading
from typing import List

# 兼容模块内部继续使用 `from db import ...` 这类旧导入方式
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── 本地模块导入 ──────────────────────────────────────
# 同时兼容两种启动方式：
# 1) 从项目根目录: uvicorn backend.main:app
# 2) 从 backend 目录: python -m uvicorn main:app
try:
    from .db import (
        init_db, get_connection, update_task_status, recover_stale_compute_state,
    )
    from .voice_changer import get_rvc_service_status
    from .services.asset_service import get_final_job_artifact, get_job_artifact, list_job_artifacts, register_audio_asset
    from .services.dataset_service import (
        create_dataset_record,
        get_job_root,
        list_datasets,
        save_cover_upload,
        save_train_uploads,
    )
    from .services.job_service import (
        canonical_current_stage,
        activate_cover_job,
        activate_train_job,
        create_cover_job,
        create_train_job,
        execute_job,
        get_job,
        get_job_row,
        get_next_pending_job,
        job_summary,
        list_jobs,
        reserve_job,
        release_job,
        retry_job,
        requeue_job,
        cancel_job,
        set_job_pending,
        has_active_compute_jobs,
    )
    from .services.model_service import (
        get_voice_model_detail,
        import_voice_model,
        list_models,
        rescan_voice_models,
        resolve_voice_model_file,
    )
    from .services.preflight_service import run_cover_preflight, run_train_preflight
    from .services.stage_log_service import list_stage_logs, log_stage
    from .strategies.strategy_registry import resolve_train_strategy
except ImportError:
    from db import (
        init_db, get_connection, update_task_status, recover_stale_compute_state,
    )
    from voice_changer import get_rvc_service_status
    from services.asset_service import get_final_job_artifact, get_job_artifact, list_job_artifacts, register_audio_asset
    from services.dataset_service import (
        create_dataset_record,
        get_job_root,
        list_datasets,
        save_cover_upload,
        save_train_uploads,
    )
    from services.job_service import (
        canonical_current_stage,
        activate_cover_job,
        activate_train_job,
        create_cover_job,
        create_train_job,
        execute_job,
        get_job,
        get_job_row,
        get_next_pending_job,
        job_summary,
        list_jobs,
        reserve_job,
        release_job,
        retry_job,
        requeue_job,
        cancel_job,
        set_job_pending,
        has_active_compute_jobs,
    )
    from services.model_service import (
        get_voice_model_detail,
        import_voice_model,
        list_models,
        rescan_voice_models,
        resolve_voice_model_file,
    )
    from services.preflight_service import run_cover_preflight, run_train_preflight
    from services.stage_log_service import list_stage_logs, log_stage
    from strategies.strategy_registry import resolve_train_strategy


# ── 应用初始化 ────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR   = os.path.join(PROJECT_ROOT, "shared_data", "uploads")
OUTPUT_ROOT  = os.path.join(PROJECT_ROOT, "shared_data", "outputs")
DATASET_DIR  = os.path.join(PROJECT_ROOT, "shared_data", "datasets")
WEIGHTS_DIR  = os.path.join(PROJECT_ROOT, "shared_data", "weights")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
FRONTEND_INDEX_PATH = os.path.join(FRONTEND_DIR, "index.html")
FRONTEND_STUDIO_PATH = os.path.join(FRONTEND_DIR, "studio.html")
QUEUE_DISPATCH_LOCK = threading.Lock()
PIPELINE_START_STATUS = "分离中"
TRAIN_START_STATUS = "切片中"

app = FastAPI(
    title="FeiShark Studio API",
    description="肥鲨音频工作站 - AI 翻唱异步流水线 v2.2",
    version="2.2.0",
)

# ── CORS 跨域中间件（允许所有源，支持前端直连）──────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],       # 允许所有方法（GET/POST/OPTIONS…）
    allow_headers=["*"],       # 允许所有请求头
)


@app.on_event("startup")
async def startup():
    """应用启动时初始化数据库和必要目录"""
    init_db()
    for d in (UPLOAD_DIR, OUTPUT_ROOT, DATASET_DIR, WEIGHTS_DIR):
        os.makedirs(d, exist_ok=True)
    print(f"[Server] 上传目录:   {UPLOAD_DIR}")
    print(f"[Server] 输出目录:   {OUTPUT_ROOT}")
    print(f"[Server] 数据集目录: {DATASET_DIR}")
    print(f"[Server] 权重目录:   {WEIGHTS_DIR}")
    print(f"[Server] 前端目录:   {FRONTEND_DIR}")
    if os.path.exists(FRONTEND_INDEX_PATH):
        print(f"[Server] 前端入口:   {FRONTEND_INDEX_PATH}")
    else:
        print(f"[Server] 警告: 前端入口不存在 -> {FRONTEND_INDEX_PATH}")
    recover_stale_compute_state()
    _dispatch_pending_compute_task()


# ── 静态文件 & 前端 SPA ──────────────────────────────


def _dispatch_pending_compute_task():
    """从数据库队列中取出下一个待执行任务并启动。"""
    if not QUEUE_DISPATCH_LOCK.acquire(blocking=False):
        return

    try:
        job = get_next_pending_job()
        if not job:
            return

        start_status = TRAIN_START_STATUS if job.job_type == "train" else PIPELINE_START_STATUS
        reserved = reserve_job(job, start_status)
        if not reserved:
            return

        print(f"[Queue] 自动启动排队任务: {job.job_id} [{job.job_type}]")
        threading.Thread(target=_run_job, args=(job.job_id,), daemon=True).start()
    finally:
        QUEUE_DISPATCH_LOCK.release()


def _safe_dispatch_pending_compute_task() -> bool:
    if has_active_compute_jobs():
        return False
    _dispatch_pending_compute_task()
    return True


def _finalize_job_control_response(result: dict) -> dict:
    dispatch_triggered = _safe_dispatch_pending_compute_task()
    response = dict(result)
    response["dispatch_triggered"] = dispatch_triggered
    if response.get("status") == "pending":
        response["queue_state"] = "dispatch_requested" if dispatch_triggered else "waiting_for_compute_slot"
    else:
        response["queue_state"] = "not_pending"
    return response


def _finalize_compute_task(task_id: str):
    """释放算力槽并尝试启动队列中的下一项任务。"""
    try:
        release_job(task_id)
    finally:
        _dispatch_pending_compute_task()


def _run_job(job_id: str):
    try:
        execute_job(job_id)
    finally:
        _finalize_compute_task(job_id)

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", summary="前端单页控制台", include_in_schema=False)
async def serve_frontend():
    if os.path.exists(FRONTEND_INDEX_PATH):
        return FileResponse(FRONTEND_INDEX_PATH)
    return JSONResponse({
        "message": "FeiShark Studio API 运行中，请访问 /docs 查看接口文档",
        "docs": "/docs",
    })


@app.get("/studio", summary="Studio 前端页面", include_in_schema=False)
async def serve_studio_frontend():
    if os.path.exists(FRONTEND_STUDIO_PATH):
        return FileResponse(FRONTEND_STUDIO_PATH)
    raise HTTPException(status_code=404, detail="studio_frontend_not_found")


# ── Pydantic 模型 ────────────────────────────────────


class UploadResponse(BaseModel):
    task_id: str
    filename: str
    status: str
    message: str


class ProcessResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    current_stage: str
    error_log: str
    created_at: str
    output_files: list


class VoiceAssetResponse(BaseModel):
    exists: bool
    model_id: str
    model_name: str
    default_pitch: int
    pth_exists: bool
    usable: bool
    resolved_pth_path: str
    resolved_source: str


class TrainResponse(BaseModel):
    task_id: str
    voice_name: str
    file_count: int
    status: str
    message: str


class JobResponse(BaseModel):
    job_id: str
    job_type: str
    strategy_key: str
    status: str
    current_stage: str
    voice_name: str
    voice_model_id: str
    input_path: str
    output_root: str
    created_at: str
    updated_at: str


class DatasetResponse(BaseModel):
    dataset_id: str
    job_id: str
    dataset_name: str
    strategy_key: str
    root_path: str
    file_count: int
    total_bytes: int
    created_at: str
    updated_at: str


class PreflightResponse(BaseModel):
    ok: bool
    job_type: str
    strategy_key: str | None = None
    model_id: str | None = None
    checks: list
    errors: list


class ModelImportRequest(BaseModel):
    model_name: str
    pth_path: str
    index_path: str = ""
    default_pitch: int = 0


# ══════════════════════════════════════════════════════
#  路由 1: 模型资产获取（含磁盘真实性验证）
# ══════════════════════════════════════════════════════


@app.get(
    "/api/models",
    response_model=list[VoiceAssetResponse],
    summary="获取全部音色资产（磁盘验证版）",
    description=(
        "查询 voice_assets 表，同时验证 shared_data/weights/<model_name>.pth 是否真实存在于磁盘。"
        "只返回 pth_exists=True 的音色，确保前端下拉菜单中每个音色都是活的、可用的。"
        "磁盘扫描异常时自动降级，返回数据库中的原始记录（不崩服务进程）。"
    ),
)
async def get_models(include_unavailable: bool = False, include_smoke: bool = False):
    try:
        result = list_models(
            PROJECT_ROOT,
            WEIGHTS_DIR,
            include_unavailable=include_unavailable,
            include_smoke=include_smoke,
        )
        print(f"[Models] 返回 {len(result)} 个音色 include_unavailable={include_unavailable}")
        return result
    except Exception as e:
        print(f"[Models] ⚠️  音色加载异常，降级返回空列表: {e}")
        return []


# ══════════════════════════════════════════════════════
#  路由 2: 创建任务（上传音频）
# ══════════════════════════════════════════════════════


@app.post(
    "/api/upload_task",
    response_model=UploadResponse,
    summary="上传音频并创建任务",
    description="接收音频文件，生成 task_id，写入数据库（状态 pending），返回 task_id",
)
async def upload_task(file: UploadFile = File(...), smoke: bool = Form(default=False)):
    allowed_ext = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，允许: {', '.join(sorted(allowed_ext))}",
        )

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    saved = await save_cover_upload(task_id, file)
    job_root = get_job_root(task_id)
    create_cover_job(
        task_id,
        saved["rel_path"],
        os.path.join("shared_data", "jobs", task_id),
        metadata={
            "original_filename": file.filename or "",
            "job_root": job_root,
            "file_size": saved["file_size"],
            "smoke": bool(smoke),
        },
    )
    register_audio_asset(
        task_id,
        "cover_input",
        saved["rel_path"],
        dataset_id="",
        file_name=saved["file_name"],
        file_ext=ext,
        file_size=saved["file_size"],
        metadata={"original_filename": file.filename or ""},
    )
    log_stage(task_id, "upload", "completed", f"上传完成: {file.filename or saved['file_name']}", {"file_size": saved["file_size"]})
    print(f"[Upload] task_id={task_id}, file={saved['file_name']}, size={saved['file_size']:,} bytes (chunked)")

    return UploadResponse(
        task_id=task_id,
        filename=saved["file_name"],
        status="pending",
        message="任务创建成功，等待处理",
    )


# ══════════════════════════════════════════════════════
#  路由 3: 异步流水线总调度（含前置模型拦截器）
# ══════════════════════════════════════════════════════


@app.post(
    "/api/process/{task_id}",
    response_model=ProcessResponse,
    summary="启动 AI 翻唱流水线",
    description=(
        "异步启动 4 步处理链（分离→修音→变声→混音），立即返回，不阻塞前端。\n\n"
        "**前置拦截器**：在启动 UVR5 之前检查选定音色的 .pth 文件是否存在于磁盘，"
        "不存在则立即失败并返回中文错误，禁止消耗算力。"
    ),
)
async def process_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    model_id: str = "v_001",
):
    # ── 1. 验证任务存在 ──
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    # ── 2. 状态保护 ──
    if job.status not in ("pending", "失败"):
        raise HTTPException(
            status_code=409,
            detail=f"任务状态为 '{job.status}'，不允许重复启动",
        )

    # ── 3. 前置拦截器：模型 .pth 文件存在性检查 ──────────
    _check_model_pth_or_fail(task_id, model_id)

    # ── 4. 激活 Job ──
    job = activate_cover_job(task_id, model_id) or job
    input_file = job.input_path
    if not os.path.isabs(input_file):
        input_file = os.path.join(PROJECT_ROOT, input_file)
    if not os.path.exists(input_file):
        update_task_status(task_id, "失败", f"输入文件不存在: {input_file}")
        raise HTTPException(status_code=400, detail="输入文件不存在")

    preflight = run_cover_preflight(model_id)
    if not preflight["ok"]:
        log_stage(task_id, "cover_preflight", "failed", "cover preflight failed", preflight)
        update_task_status(task_id, "失败", "cover preflight failed")
        raise HTTPException(status_code=422, detail=preflight)

    log_stage(task_id, "cover_preflight", "completed", "cover preflight ok", preflight)

    # ── 5. 全局唯一算力锁：空闲则立即启动，繁忙则保持 pending 排队 ──
    reserved = reserve_job(job, PIPELINE_START_STATUS)
    if not reserved:
        set_job_pending(task_id, "")
        print(f"[Process] 算力繁忙，任务进入队列: {task_id}, model_id={model_id}")
        return ProcessResponse(
            task_id=task_id,
            status="pending",
            message="当前有任务正在占用 GPU 算力，本任务已进入队列等待执行",
        )

    background_tasks.add_task(_run_job, task_id)
    print(f"[Process] 后台任务已启动: {task_id}, model_id={model_id}")

    return ProcessResponse(
        task_id=task_id,
        status="processing",
        message="AI 翻唱流水线已启动，当前独占 GPU 算力处理中",
    )


def _check_model_pth_or_fail(task_id: str, model_id: str):
    """
    前置拦截器：检查 model_id 对应的 .pth 权重文件是否真实存在于磁盘。

    如果不存在，立即将任务标记为"失败"并抛出 HTTP 422 异常，
    拦截后续一切算力消耗（UVR5 / RMVPE / RVC）。
    """
    ERROR_MSG = "错误：选定的音色模型尚未训练完成，请先在右侧工坊完成训练！"

    # 先从数据库查 pth_path
    resolved = resolve_voice_model_file(model_id, PROJECT_ROOT, WEIGHTS_DIR)
    va = resolved["model"]
    if not va:
        update_task_status(task_id, "失败", ERROR_MSG)
        raise HTTPException(status_code=422, detail=ERROR_MSG)

    if not resolved["ok"]:
        update_task_status(task_id, "失败", ERROR_MSG)
        print(f"[Interceptor] 模型文件不存在: {resolved['resolved_path']}")
        raise HTTPException(status_code=422, detail=ERROR_MSG)

    print(f"[Interceptor] 模型文件验证通过: {va['model_name']}")


# ── 后台流水线执行器 ──────────────────────────────────


def _run_pipeline(task_id: str, input_file: str, model_id: str = "v_001"):
    _run_job(task_id)


class PipelineError(Exception):
    """流水线阶段错误"""
    def __init__(self, stage: str, error: str):
        self.stage = stage
        self.error = error
        super().__init__(f"[{stage}] {error}")


# ══════════════════════════════════════════════════════
#  路由 4: 状态轮询
# ══════════════════════════════════════════════════════


@app.get(
    "/api/task_status/{task_id}",
    response_model=TaskStatusResponse,
    summary="查询任务状态",
    description="返回任务当前状态和输出文件列表，前端进度条轮询数据源",
)
async def get_task_status(task_id: str):
    job_row = get_job_row(task_id)
    task_row = None
    if not job_row:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        finally:
            conn.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        task_row = dict(row)

    output_files: list[dict] = []
    seen: set[str] = set()

    if job_row:
        for art in list_job_artifacts(task_id):
            rel_path = os.path.relpath(art["file_path"], PROJECT_ROOT).replace("\\", "/")
            if rel_path in seen:
                continue
            seen.add(rel_path)
            output_files.append({
                "filename": os.path.basename(art["file_path"]),
                "size": art["file_size"],
                "path": rel_path,
            })

    if not output_files:
        output_dir = os.path.join(OUTPUT_ROOT, task_id)
        if os.path.exists(output_dir):
            for f in sorted(os.listdir(output_dir)):
                if not f.endswith(".wav"):
                    continue
                rel_path = f"shared_data/outputs/{task_id}/{f}"
                if rel_path in seen:
                    continue
                seen.add(rel_path)
                fpath = os.path.join(output_dir, f)
                output_files.append({
                    "filename": f,
                    "size": os.path.getsize(fpath),
                    "path": rel_path,
                })

    if job_row:
        stage_logs = list_stage_logs(task_id)
        current_stage = canonical_current_stage(job_row, stage_logs)
        return TaskStatusResponse(
            task_id=job_row["job_id"],
            status=job_row["status"],
            current_stage=current_stage,
            error_log=job_row.get("error_log") or "",
            created_at=str(job_row.get("created_at") or ""),
            output_files=output_files,
        )

    return TaskStatusResponse(
        task_id=task_row["task_id"],
        status=task_row["status"],
        current_stage="",
        error_log=task_row.get("error_log") or "",
        created_at=str(task_row.get("created_at") or ""),
        output_files=output_files,
    )


# ══════════════════════════════════════════════════════
#  路由 5: 下载最终成品
# ══════════════════════════════════════════════════════


@app.get(
    "/api/download/{task_id}",
    summary="下载最终成品",
    description="下载任务的 final_master.wav 文件",
)
async def download_result(task_id: str):
    artifact = get_final_job_artifact(task_id)
    if artifact and os.path.exists(artifact["file_path"]):
        filename = os.path.basename(artifact["file_path"])
        media_type = "audio/wav" if filename.lower().endswith(".wav") else "application/octet-stream"
        return FileResponse(path=artifact["file_path"], filename=filename, media_type=media_type)

    legacy_final = os.path.join(OUTPUT_ROOT, task_id, "final_master.wav")
    if os.path.exists(legacy_final):
        return FileResponse(
            path=legacy_final,
            filename=os.path.basename(legacy_final),
            media_type="audio/wav",
        )
    raise HTTPException(status_code=404, detail="最终成品尚未生成")


@app.get("/api/jobs", summary="查询 Job 列表")
async def get_jobs(
    job_type: str | None = None,
    status: str | None = None,
    strategy_key: str | None = None,
    voice_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_smoke: bool = False,
):
    jobs = list_jobs(
        job_type=job_type,
        status=status,
        strategy_key=strategy_key,
        voice_name=voice_name,
        limit=limit,
        offset=offset,
        include_smoke=include_smoke,
    )
    for job in jobs:
        job["current_stage"] = canonical_current_stage(job, None)
    return {"items": jobs, "limit": limit, "offset": offset}


@app.get("/api/datasets", summary="查询 Dataset 列表")
async def get_datasets(
    job_id: str | None = None,
    strategy_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_smoke: bool = False,
):
    items = list_datasets(
        job_id=job_id,
        strategy_key=strategy_key,
        limit=limit,
        offset=offset,
        include_smoke=include_smoke,
    )
    return {"items": items, "limit": limit, "offset": offset}


@app.get("/api/jobs/summary", summary="查询 Job 汇总")
async def get_jobs_summary(include_smoke: bool = False):
    return job_summary(include_smoke=include_smoke)


@app.get("/api/jobs/{job_id}", response_model=JobResponse, summary="查询 Job 详情")
async def get_job_detail(job_id: str):
    job = get_job_row(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job 不存在: {job_id}")
    stage_logs = list_stage_logs(job_id)
    return JobResponse(
        job_id=job["job_id"],
        job_type=job["job_type"],
        strategy_key=job["strategy_key"],
        status=job["status"],
        current_stage=canonical_current_stage(job, stage_logs),
        voice_name=job.get("voice_name") or "",
        voice_model_id=job.get("voice_model_id") or "",
        input_path=job.get("input_path") or "",
        output_root=job.get("output_root") or "",
        created_at=str(job.get("created_at") or ""),
        updated_at=str(job.get("updated_at") or ""),
    )


@app.get("/api/jobs/{job_id}/artifacts", summary="查询 Job 产物")
async def get_job_artifacts(job_id: str):
    job = get_job_row(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job 不存在: {job_id}")
    artifacts = list_job_artifacts(job_id)
    for artifact in artifacts:
        artifact["download_url"] = f"/api/jobs/{job_id}/artifacts/{artifact['artifact_id']}/download"
    return {"job_id": job_id, "artifacts": artifacts}


@app.get("/api/jobs/{job_id}/stage-logs", summary="查询 Job 阶段日志")
async def get_job_stage_logs_route(job_id: str):
    job = get_job_row(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"job_id": job_id, "stage_logs": list_stage_logs(job_id)}


@app.get("/api/jobs/{job_id}/artifacts/{artifact_id}/download", summary="download job artifact")
async def download_job_artifact(job_id: str, artifact_id: str):
    artifact = get_job_artifact(job_id, artifact_id)
    if not artifact or not os.path.exists(artifact["file_path"]):
        raise HTTPException(status_code=404, detail="artifact_not_found")
    filename = os.path.basename(artifact["file_path"])
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path=artifact["file_path"], filename=filename, media_type=media_type)


async def _get_job_stage_logs_impl(job_id: str):
    job = get_job_row(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job 不存在: {job_id}")
    return {"job_id": job_id, "stage_logs": list_stage_logs(job_id)}


@app.post("/api/models/import", summary="导入已有模型")
async def post_model_import(payload: ModelImportRequest):
    if not payload.model_name.strip():
        raise HTTPException(status_code=400, detail="model_name 不能为空")
    if not payload.pth_path.strip():
        raise HTTPException(status_code=400, detail="pth_path 不能为空")
    model = import_voice_model(
        model_name=payload.model_name.strip(),
        pth_path=payload.pth_path.strip(),
        index_path=payload.index_path.strip(),
        default_pitch=payload.default_pitch,
        project_root=PROJECT_ROOT,
        weights_dir=WEIGHTS_DIR,
    )
    return model


@app.post("/api/models/rescan", summary="重新扫描模型")
async def post_models_rescan():
    return rescan_voice_models(PROJECT_ROOT, WEIGHTS_DIR)


@app.get("/api/models/{model_id}", summary="查询 Voice Model 详情")
async def get_model_detail(model_id: str):
    model = get_voice_model_detail(model_id, PROJECT_ROOT, WEIGHTS_DIR)
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
    return model


@app.get("/api/preflight/train", response_model=PreflightResponse, summary="训练预检")
async def get_train_preflight(file_count: int = 1):
    strategy_key = resolve_train_strategy(file_count)
    return run_train_preflight(strategy_key)


@app.get("/api/preflight/cover", response_model=PreflightResponse, summary="翻唱预检")
async def get_cover_preflight(model_id: str = "v_001"):
    return run_cover_preflight(model_id)


@app.post("/api/jobs/{job_id}/retry", summary="重试失败 Job")
async def post_job_retry(job_id: str):
    result = retry_job(job_id)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result)
    return _finalize_job_control_response(result)


@app.post("/api/jobs/{job_id}/requeue", summary="重新入队 Job")
async def post_job_requeue(job_id: str):
    result = requeue_job(job_id)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result)
    return _finalize_job_control_response(result)


@app.post("/api/jobs/{job_id}/cancel", summary="取消 Job")
async def post_job_cancel(job_id: str):
    result = cancel_job(job_id)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result)
    return _finalize_job_control_response(result)


@app.get("/api/diagnostics/summary", summary="统一诊断摘要")
async def get_diagnostics_summary(model_id: str = "v_001"):
    models = list_models(PROJECT_ROOT, WEIGHTS_DIR, include_unavailable=True)
    train_preflight = run_train_preflight("single_long_preprocess")
    cover_preflight = run_cover_preflight(model_id)
    missing = []
    for item in train_preflight["errors"]:
        missing.append(item["check"])
    for item in cover_preflight["errors"]:
        if item["check"] not in missing:
            missing.append(item["check"])

    failed_jobs = list_jobs(status="失败", limit=5, offset=0)
    for job in failed_jobs:
        job["current_stage"] = canonical_current_stage(job, None)

    return {
        "rvc": get_rvc_service_status(),
        "train_preflight": train_preflight,
        "cover_preflight": cover_preflight,
        "usable_model_count": sum(1 for model in models if model["usable"]),
        "missing_dependencies": missing,
        "last_failed_jobs": failed_jobs,
    }


# ══════════════════════════════════════════════════════
#  路由 6: 上传多段干声 + 创建训练任务（多文件版）
# ══════════════════════════════════════════════════════


@app.post(
    "/api/train",
    response_model=TrainResponse,
    summary="上传多段干声并启动音色训练",
    description=(
        "支持同时上传多个 WAV/MP3/FLAC 干声文件。\n\n"
        "后端为该 task_id 创建独立 dataset 文件夹，将所有文件保存其中，"
        "model_trainer 直接以该文件夹为训练数据源（无需再做单文件切片）。"
    ),
)
async def train_voice(
    background_tasks: BackgroundTasks,
    voice_name: str = Form(default=""),
    files: List[UploadFile] = File(...),
    smoke: bool = Form(default=False),
):
    # ── 文件校验 ──
    allowed_ext = {".wav", ".mp3", ".flac"}
    validated_files = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in allowed_ext:
            raise HTTPException(
                status_code=400,
                detail=f"文件 '{f.filename}' 格式不支持（允许 WAV/MP3/FLAC）",
            )
        validated_files.append((f, ext))

    if not validated_files:
        raise HTTPException(status_code=400, detail="请至少上传一个干声文件")

    # ── 生成 task_id 和专属 dataset 文件夹 ──
    task_id = f"train_{uuid.uuid4().hex[:12]}"
    voice_name = voice_name.strip() or os.path.splitext(validated_files[0][0].filename or "自定义音色")[0]

    saved = await save_train_uploads(task_id, [f for f, _ in validated_files])
    strategy_key = resolve_train_strategy(saved["file_count"])
    job = create_train_job(
        task_id,
        voice_name,
        saved["dataset_rel_path"],
        os.path.join("shared_data", "jobs", task_id),
        strategy_key,
        metadata={
            "file_count": saved["file_count"],
            "total_bytes": saved["total_bytes"],
            "smoke": bool(smoke),
        },
    )
    dataset_id = create_dataset_record(
        task_id,
        voice_name,
        saved["dataset_rel_path"],
        strategy_key,
        saved["file_count"],
        saved["total_bytes"],
        metadata={
            "input_mode": "multi_file" if saved["file_count"] > 1 else "single_file",
            "smoke": bool(smoke),
        },
    )

    for item in saved["saved_files"]:
        register_audio_asset(
            task_id,
            "train_input",
            item["rel_path"],
            dataset_id=dataset_id,
            file_name=item["file_name"],
            file_ext=item["file_ext"],
            file_size=item["file_size"],
            metadata={"source": "train_upload"},
        )

    job = activate_train_job(task_id) or job

    log_stage(task_id, "train_upload", "completed", f"训练数据已接收: {saved['file_count']} files", {"strategy_key": strategy_key, "dataset_id": dataset_id})

    preflight = run_train_preflight(strategy_key)
    if not preflight["ok"]:
        log_stage(task_id, "train_preflight", "failed", "train preflight failed", preflight)
        update_task_status(task_id, "失败", "train preflight failed")
        raise HTTPException(status_code=422, detail=preflight)

    log_stage(task_id, "train_preflight", "completed", "train preflight ok", preflight)

    # ── 异步启动训练 ──
    reserved = reserve_job(job, TRAIN_START_STATUS)
    if reserved:
        background_tasks.add_task(_run_job, task_id)
        print(f"[Train] 训练任务已启动: {task_id} -> {voice_name}  ({saved['file_count']} 个文件)")
    else:
        set_job_pending(task_id, "")
        print(f"[Train] 算力繁忙，训练任务进入队列: {task_id} -> {voice_name}")

    return TrainResponse(
        task_id=task_id,
        voice_name=voice_name,
        file_count=saved["file_count"],
        status="processing" if reserved else "pending",
        message=(
            f"训练任务已创建，音色「{voice_name}」共 {saved['file_count']} 个文件，当前独占 GPU 算力处理中"
            if reserved
            else f"训练任务已创建，音色「{voice_name}」共 {saved['file_count']} 个文件，当前算力繁忙，已进入队列"
        ),
    )


def _run_training(task_id: str, voice_name: str, dataset_folder: str):
    _run_job(task_id)


# ── 健康检查 ──────────────────────────────────────────


@app.get("/api/health", summary="健康检查")
async def health():
    rvc_status = get_rvc_service_status()
    return {
        "status":  "ok",
        "service": "FeiShark Studio API",
        "version": "2.2.0",
        "features": {
            "chunked_upload": True,
            "cors_enabled":   True,
            "disk_fallback":  True,
        },
        "rvc": rvc_status,
    }


# ── 启动入口 ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
