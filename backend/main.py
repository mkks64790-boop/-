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
import json
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
    from .voice_changer import get_engine_summary, get_rvc_service_status
    from .services.asset_service import get_final_job_artifact, get_job_artifact, list_job_artifacts, register_audio_asset
    from .services.audit_service import list_audit_events
    from .services.batch_service import create_batch, get_batch, import_tracks_to_batch, list_batches
    from .services.dataset_service import (
        create_dataset_record,
        discard_job_workspace,
        get_job_root,
        list_datasets,
        save_cover_upload,
        save_train_uploads,
    )
    from .services.audio_material_service import (
        build_material_rejection_detail,
        decide_train_material_route,
        profile_train_saved_uploads,
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
        get_voice_model_by_source_job,
        get_voice_model_detail,
        import_voice_model,
        list_models,
        rescan_voice_models,
        resolve_voice_model_file,
    )
    from .services.lyric_service import (
        align_lyrics,
        create_lyric_document,
        get_lyric_versions,
        extract_lyrics,
        promote_lyric_timeline,
    )
    from .services.track_service import get_track, get_track_current_master, get_track_job_entry, list_track_jobs, list_track_studio_versions, list_tracks, set_track_current_master, update_track
    from .services.preflight_service import run_cover_preflight, run_train_preflight
    from .services.stage_log_service import list_stage_logs, log_stage
    from .services.studio_effect_service import StudioEffectExportError, export_effect_rack_draft, get_effect_rack_capabilities
    from .strategies.strategy_registry import resolve_train_strategy
except ImportError:
    from db import (
        init_db, get_connection, update_task_status, recover_stale_compute_state,
    )
    from voice_changer import get_engine_summary, get_rvc_service_status
    from services.asset_service import get_final_job_artifact, get_job_artifact, list_job_artifacts, register_audio_asset
    from services.audit_service import list_audit_events
    from services.batch_service import create_batch, get_batch, import_tracks_to_batch, list_batches
    from services.dataset_service import (
        create_dataset_record,
        discard_job_workspace,
        get_job_root,
        list_datasets,
        save_cover_upload,
        save_train_uploads,
    )
    from services.audio_material_service import (
        build_material_rejection_detail,
        decide_train_material_route,
        profile_train_saved_uploads,
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
        get_voice_model_by_source_job,
        get_voice_model_detail,
        import_voice_model,
        list_models,
        rescan_voice_models,
        resolve_voice_model_file,
    )
    from services.lyric_service import (
        align_lyrics,
        create_lyric_document,
        get_lyric_versions,
        extract_lyrics,
        promote_lyric_timeline,
    )
    from services.track_service import get_track, get_track_current_master, get_track_job_entry, list_track_jobs, list_track_studio_versions, list_tracks, set_track_current_master, update_track
    from services.preflight_service import run_cover_preflight, run_train_preflight
    from services.stage_log_service import list_stage_logs, log_stage
    from services.studio_effect_service import StudioEffectExportError, export_effect_rack_draft, get_effect_rack_capabilities
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
FRONTEND_FACTORY_PATH = os.path.join(FRONTEND_DIR, "factory.html")
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


@app.get("/factory", summary="Release Factory 前端页面", include_in_schema=False)
async def serve_factory_frontend():
    if os.path.exists(FRONTEND_FACTORY_PATH):
        return FileResponse(FRONTEND_FACTORY_PATH)
    raise HTTPException(status_code=404, detail="factory_frontend_not_found")


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
    index_path: str = ""
    resolved_index_path: str = ""
    origin_kind: str = ""
    source_job_id: str = ""
    source_strategy_key: str = ""
    source_dataset_id: str = ""
    source_material_profile: str = ""
    source_file_count: int | None = None
    source_duration_label: str = ""
    source_summary: str = ""
    created_at: str = ""
    updated_at: str = ""


class TrainResponse(BaseModel):
    task_id: str
    voice_name: str
    file_count: int
    strategy_key: str
    queue_state: str
    material_profile: str = ""
    duration_seconds: float | None = None
    duration_label: str = ""
    sample_rate: int | None = None
    channels: int | None = None
    codec: str = ""
    container: str = ""
    bit_rate: int | None = None
    recommended_route: str = ""
    single_long_eligible: bool | None = None
    reason: str = ""
    next_step: str = ""
    material_decision: dict | None = None
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
    track_id: str = ""
    track_title: str = ""
    track_artist: str = ""
    batch_id: str = ""
    batch_name: str = ""
    factory_url: str = ""
    input_path: str
    output_root: str
    generated_model_id: str = ""
    generated_model_name: str = ""
    generated_model_usable: bool | None = None
    generated_model_origin_kind: str = ""
    generated_model_summary: str = ""
    voice_model_origin_kind: str = ""
    voice_model_source_job_id: str = ""
    voice_model_source_summary: str = ""
    voice_model_source_strategy_key: str = ""
    voice_model_source_material_profile: str = ""
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
    environment_ok: bool | None = None
    material_ok: bool | None = None
    submission_allowed: bool | None = None
    material_profile: str = ""
    duration_seconds: float | None = None
    duration_label: str = ""
    sample_rate: int | None = None
    channels: int | None = None
    codec: str = ""
    container: str = ""
    bit_rate: int | None = None
    recommended_route: str = ""
    single_long_eligible: bool | None = None
    reason: str = ""
    next_step: str = ""
    material_decision: dict | None = None
    checks: list
    errors: list


class ModelImportRequest(BaseModel):
    model_name: str
    pth_path: str
    index_path: str = ""
    default_pitch: int = 0


class BatchCreateRequest(BaseModel):
    batch_name: str
    target_platforms: list[str] = []
    output_root: str = ""
    metadata: dict = {}


class TrackUpdateRequest(BaseModel):
    title: str | None = None
    artist: str | None = None
    source_type: str | None = None
    status: str | None = None
    notes: str | None = None


class TrackCoverJobRequest(BaseModel):
    model_id: str


class TrackMasterRequest(BaseModel):
    job_id: str
    artifact_id: str = ""


class LyricExtractRequest(BaseModel):
    lyric_text: str = ""
    source: str = "stub_extract_v1"
    language: str = "zh-CN"
    title: str = ""
    metadata: dict = {}


class LyricAlignRequest(BaseModel):
    lyric_document_id: str = ""
    lyric_text: str = ""
    engine: str = "stub_align_v1"
    align_mode: str = "balanced_lines"
    line_split_mode: str = "balanced"
    append_outro_card: bool = True
    metadata: dict = {}


class StudioEffectExportRequest(BaseModel):
    track_id: str
    source_job_id: str
    source_artifact_id: str = ""
    effect_rack: list[dict] = []
    export_profile: str = "studio_balanced"
    note: str = ""
    render_engine: str = "copy_only"


def _parse_json_object(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_cover_model_snapshot(model_id: str) -> dict:
    detail = get_voice_model_detail(model_id, PROJECT_ROOT, WEIGHTS_DIR) or {}
    origin_kind = str(detail.get("origin_kind") or "").strip()
    source_job_id = str(detail.get("source_job_id") or "").strip()
    source_summary = str(detail.get("source_summary") or "").strip()
    source_strategy_key = str(detail.get("source_strategy_key") or "").strip()
    source_material_profile = str(detail.get("source_material_profile") or "").strip()
    return {
        "voice_model_origin_kind": origin_kind,
        "voice_model_source_job_id": source_job_id,
        "voice_model_source_summary": source_summary,
        "voice_model_source_strategy_key": source_strategy_key,
        "voice_model_source_material_profile": source_material_profile,
    }


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


def _resolve_cover_model_name(model_id: str) -> str:
    detail = get_voice_model_detail(model_id, PROJECT_ROOT, WEIGHTS_DIR)
    if not detail:
        return ""
    return detail.get("model_name") or ""


def _activate_and_dispatch_cover_job(
    job_id: str,
    model_id: str,
    background_tasks: BackgroundTasks,
    *,
    voice_name: str = "",
):
    job = activate_cover_job(job_id, model_id, voice_name=voice_name) or get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"job_not_found: {job_id}")

    reserved = reserve_job(job, PIPELINE_START_STATUS)
    if not reserved:
        set_job_pending(job_id, "")
        return job, False

    background_tasks.add_task(_run_job, job_id)
    return job, True


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
    metadata = _parse_json_object(job.get("metadata_json"))
    track_id = job.get("track_id") or ""
    track = get_track(track_id) if track_id else None
    batch_id = track.get("batch_id") if track else ""
    factory_url = ""
    if track_id:
        params = [f"track_id={track_id}"]
        if batch_id:
            params.insert(0, f"batch_id={batch_id}")
        factory_url = f"/factory?{'&'.join(params)}"
    generated_model = get_voice_model_by_source_job(job["job_id"], PROJECT_ROOT, WEIGHTS_DIR) if job.get("job_type") == "train" else None
    return JobResponse(
        job_id=job["job_id"],
        job_type=job["job_type"],
        strategy_key=job["strategy_key"],
        status=job["status"],
        current_stage=canonical_current_stage(job, stage_logs),
        voice_name=job.get("voice_name") or "",
        voice_model_id=job.get("voice_model_id") or "",
        track_id=track_id,
        track_title=(track.get("title") or "") if track else "",
        track_artist=(track.get("artist") or "") if track else "",
        batch_id=batch_id or "",
        batch_name=(track.get("batch_name") or "") if track else "",
        factory_url=factory_url,
        input_path=job.get("input_path") or "",
        output_root=job.get("output_root") or "",
        generated_model_id=(generated_model.get("model_id") or "") if generated_model else "",
        generated_model_name=(generated_model.get("model_name") or "") if generated_model else "",
        generated_model_usable=generated_model.get("usable") if generated_model else None,
        generated_model_origin_kind=(generated_model.get("origin_kind") or "") if generated_model else "",
        generated_model_summary=(generated_model.get("source_summary") or "") if generated_model else "",
        voice_model_origin_kind=str(metadata.get("voice_model_origin_kind") or ""),
        voice_model_source_job_id=str(metadata.get("voice_model_source_job_id") or ""),
        voice_model_source_summary=str(metadata.get("voice_model_source_summary") or ""),
        voice_model_source_strategy_key=str(metadata.get("voice_model_source_strategy_key") or ""),
        voice_model_source_material_profile=str(metadata.get("voice_model_source_material_profile") or ""),
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
async def get_train_preflight(
    file_count: int = 1,
    duration_seconds: float | None = None,
    file_name: str = "",
    file_size: int | None = None,
    mime_type: str = "",
):
    material_decision = decide_train_material_route(
        file_count,
        duration_seconds=duration_seconds,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
    )
    strategy_key = material_decision.get("recommended_route") or resolve_train_strategy(
        file_count,
        material_decision.get("single_long_eligible"),
    )
    if file_count == 1 and duration_seconds is None:
        return run_train_preflight(strategy_key)
    return run_train_preflight(strategy_key, material_decision)


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
        "rvc": get_engine_summary(),
        "train_preflight": train_preflight,
        "cover_preflight": cover_preflight,
        "usable_model_count": sum(1 for model in models if model["usable"]),
        "missing_dependencies": missing,
        "last_failed_jobs": failed_jobs,
    }


def _parse_json_form_field(raw: str, fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid_json_form_field: {exc.msg}") from exc


@app.get("/api/factory/summary", summary="Release Factory summary")
async def get_factory_summary():
    conn = get_connection()
    try:
        batch_count = conn.execute("SELECT COUNT(*) FROM release_batches").fetchone()[0]
        track_count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        lyric_doc_count = conn.execute("SELECT COUNT(*) FROM lyric_documents").fetchone()[0]
        timeline_count = conn.execute("SELECT COUNT(*) FROM lyric_timeline_versions").fetchone()[0]
    finally:
        conn.close()

    return {
        "batch_count": batch_count,
        "track_count": track_count,
        "lyric_document_count": lyric_doc_count,
        "timeline_count": timeline_count,
        "recent_batches": list_batches(limit=5, offset=0),
        "recent_audit_events": list_audit_events(limit=10, offset=0),
    }


@app.post("/api/batches", summary="create release batch")
async def post_batch(payload: BatchCreateRequest):
    if not payload.batch_name.strip():
        raise HTTPException(status_code=400, detail="batch_name_required")
    return create_batch(
        batch_name=payload.batch_name.strip(),
        target_platforms=payload.target_platforms,
        output_root=payload.output_root.strip(),
        metadata=payload.metadata,
    )


@app.get("/api/batches", summary="list release batches")
async def get_batches(limit: int = 50, offset: int = 0):
    return {"items": list_batches(limit=limit, offset=offset), "limit": limit, "offset": offset}


@app.get("/api/batches/{batch_id}", summary="release batch detail")
async def get_batch_detail_route(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch_not_found")
    return batch


@app.get("/api/batches/{batch_id}/tracks", summary="list tracks in batch")
async def get_batch_tracks_route(batch_id: str, limit: int = 200, offset: int = 0):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch_not_found")
    return {"batch_id": batch_id, "items": list_tracks(batch_id=batch_id, limit=limit, offset=offset), "limit": limit, "offset": offset}


@app.post("/api/batches/{batch_id}/tracks/import", summary="import tracks into batch")
async def post_batch_track_import(
    batch_id: str,
    files: List[UploadFile] = File(...),
    titles_json: str = Form(default="[]"),
    artist: str = Form(default=""),
    source_type: str = Form(default="upload"),
    notes: str = Form(default=""),
    metadata_json: str = Form(default="{}"),
):
    titles = _parse_json_form_field(titles_json, [])
    if not isinstance(titles, list):
        raise HTTPException(status_code=400, detail="titles_json_must_be_array")
    metadata = _parse_json_form_field(metadata_json, {})
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata_json_must_be_object")

    try:
        imported = await import_tracks_to_batch(
            batch_id,
            files,
            titles=[str(item) for item in titles],
            artist=artist,
            source_type=source_type,
            notes=notes,
            metadata=metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "batch_not_found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return {
        "batch_id": batch_id,
        "imported_count": len(imported),
        "imported_tracks": imported,
        "batch": get_batch(batch_id),
    }


@app.get("/api/tracks/{track_id}", summary="track detail")
async def get_track_detail_route(track_id: str):
    track = get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="track_not_found")
    lyrics = get_lyric_versions(track_id)
    current_master = get_track_current_master(track_id)
    return {
        **track,
        "current_master": current_master,
        "lyrics": lyrics,
        "audit_events": list_audit_events(entity_type="track", entity_id=track_id, limit=20, offset=0),
    }


@app.get("/api/tracks/{track_id}/jobs", summary="track related jobs")
async def get_track_jobs_route(track_id: str, limit: int = 20, offset: int = 0):
    track = get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="track_not_found")
    return {
        "track_id": track_id,
        "current_master_job_id": track.get("current_master_job_id") or "",
        "current_master_artifact_id": track.get("current_master_artifact_id") or "",
        "current_master": get_track_current_master(track_id),
        "items": list_track_jobs(track_id, limit=limit, offset=offset),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/tracks/{track_id}/studio-versions", summary="track Studio version ledger")
async def get_track_studio_versions_route(track_id: str, limit: int = 50, offset: int = 0):
    payload = list_track_studio_versions(track_id, limit=limit, offset=offset)
    if payload is None:
        raise HTTPException(status_code=404, detail="track_not_found")
    return payload


@app.post("/api/tracks/{track_id}/master", summary="set current master for track")
async def post_track_master_route(track_id: str, payload: TrackMasterRequest):
    track = get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="track_not_found")

    job_id = (payload.job_id or "").strip()
    artifact_id = (payload.artifact_id or "").strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id_required")

    candidate = get_track_job_entry(track_id, job_id, preferred_artifact_id=artifact_id)
    if not candidate:
        raise HTTPException(status_code=422, detail="master_job_not_found_for_track")
    if not (candidate.get("job_kind") == "cover" or candidate.get("job_type") == "cover"):
        raise HTTPException(status_code=422, detail="master_job_must_be_cover")
    if (candidate.get("status") or "") not in {"完成", "completed", "已完成"}:
        raise HTTPException(status_code=422, detail="master_job_not_completed")
    if not candidate.get("has_final_artifact") or not candidate.get("final_artifact_id"):
        raise HTTPException(status_code=422, detail="master_job_missing_final_artifact")
    if artifact_id and candidate.get("final_artifact_id") != artifact_id:
        raise HTTPException(status_code=422, detail="master_artifact_not_found_for_job")
    if candidate.get("final_artifact_type") not in {"cover_master", "studio_effect_draft_master", "studio_effect_render_master"}:
        raise HTTPException(status_code=422, detail="master_artifact_type_not_allowed")
    artifact_path = candidate.get("final_artifact_path") or ""
    if not artifact_path or not os.path.exists(artifact_path):
        raise HTTPException(status_code=422, detail="master_artifact_file_not_found")
    if os.path.splitext(artifact_path)[1].lower() not in {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}:
        raise HTTPException(status_code=422, detail="master_artifact_must_be_audio")

    current_master = set_track_current_master(
        track_id,
        job_id,
        artifact_id=candidate.get("final_artifact_id") or artifact_id,
    )
    return {
        "ok": True,
        "track_id": track_id,
        "current_master_job_id": current_master.get("job_id") if current_master else "",
        "current_master_artifact_id": current_master.get("final_artifact_id") if current_master else "",
        "current_master_artifact_type": current_master.get("final_artifact_type") if current_master else "",
        "current_master_processing_mode": current_master.get("final_artifact_processing_mode") if current_master else "",
        "current_master": current_master,
    }


@app.post("/api/tracks/{track_id}/cover-jobs", summary="create cover job from track")
async def post_track_cover_job_route(track_id: str, payload: TrackCoverJobRequest, background_tasks: BackgroundTasks):
    track = get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="track_not_found")

    model_id = (payload.model_id or "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id_required")

    source_rel = (track.get("source_audio_path") or "").strip()
    if not source_rel:
        raise HTTPException(status_code=422, detail="track_source_audio_missing")

    source_abs = source_rel if os.path.isabs(source_rel) else os.path.join(PROJECT_ROOT, source_rel)
    if not os.path.exists(source_abs):
        raise HTTPException(status_code=422, detail="track_source_audio_not_found")

    preflight = run_cover_preflight(model_id)
    if not preflight.get("ok"):
        raise HTTPException(status_code=422, detail=preflight)

    model_snapshot = _build_cover_model_snapshot(model_id)
    model_name = _resolve_cover_model_name(model_id)
    job_id = f"task_{uuid.uuid4().hex[:12]}"
    depends_on = [
        value
        for value in [
            track.get("current_timeline_version_id") or "",
            track.get("current_lyric_document_id") or "",
        ]
        if value
    ]
    track_metadata = track.get("metadata") if isinstance(track.get("metadata"), dict) else {}
    job_metadata = {
        "source": "factory_track_cover_job",
        "track_id": track_id,
        "track_title": track.get("title") or track_id,
        "batch_id": track.get("batch_id") or "",
        "smoke": bool(track_metadata.get("smoke")),
        "job_root": get_job_root(job_id),
        **model_snapshot,
    }
    job = create_cover_job(
        job_id,
        source_rel,
        os.path.join("shared_data", "jobs", job_id),
        metadata=job_metadata,
        track_id=track_id,
        voice_model_id=model_id,
        voice_name=model_name,
        depends_on=depends_on,
    )

    register_audio_asset(
        job_id,
        "cover_input",
        source_rel,
        file_name=os.path.basename(source_abs),
        file_ext=os.path.splitext(source_abs)[1].lower() or ".wav",
        file_size=os.path.getsize(source_abs),
        metadata={
            "original_filename": os.path.basename(source_abs),
            "source": "factory_track_cover_job",
            "track_id": track_id,
        },
    )

    log_stage(job_id, "cover_preflight", "completed", "cover preflight ok", preflight)
    job, reserved = _activate_and_dispatch_cover_job(
        job_id,
        model_id,
        background_tasks,
        voice_name=model_name,
    )
    current_stage = canonical_current_stage(get_job_row(job_id), list_stage_logs(job_id))
    if reserved:
        status_text = "processing"
        message = "翻唱任务已创建，正在占用算力处理中"
        queue_state = "processing"
    else:
        status_text = "pending"
        message = "翻唱任务已进入队列，等待算力释放后自动执行"
        queue_state = "waiting_for_compute_slot"

    return {
        "ok": True,
        "track_id": track_id,
        "job_id": job_id,
        "status": status_text,
        "current_stage": current_stage,
        "queue_state": queue_state,
        "message": message,
        "model_id": model_id,
        "voice_name": model_name,
        **model_snapshot,
    }


@app.patch("/api/tracks/{track_id}", summary="update track")
async def patch_track_route(track_id: str, payload: TrackUpdateRequest):
    track = update_track(track_id, payload.model_dump(exclude_none=True))
    if not track:
        raise HTTPException(status_code=404, detail="track_not_found")
    return track


@app.post("/api/tracks/{track_id}/lyrics/extract", summary="extract lyrics draft")
async def post_track_lyrics_extract(track_id: str, payload: LyricExtractRequest):
    try:
        return extract_lyrics(
            track_id,
            lyric_text=payload.lyric_text,
            source=payload.source,
            language=payload.language,
            title=payload.title,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "track_not_found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.post("/api/tracks/{track_id}/lyrics/align", summary="align lyrics into timeline versions")
async def post_track_lyrics_align(track_id: str, payload: LyricAlignRequest):
    try:
        return align_lyrics(
            track_id,
            lyric_document_id=payload.lyric_document_id,
            lyric_text=payload.lyric_text,
            engine=payload.engine,
            align_mode=payload.align_mode,
            line_split_mode=payload.line_split_mode,
            append_outro_card=payload.append_outro_card,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail in {"track_not_found", "timeline_not_found"} else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.get("/api/tracks/{track_id}/lyrics/versions", summary="list lyric documents and versions")
async def get_track_lyric_versions_route(track_id: str):
    track = get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="track_not_found")
    return get_lyric_versions(track_id)


@app.post("/api/tracks/{track_id}/lyrics/{timeline_id}/promote", summary="promote lyric timeline version")
async def post_track_lyric_promote(track_id: str, timeline_id: str):
    try:
        return promote_lyric_timeline(track_id, timeline_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail in {"track_not_found", "timeline_not_found"} else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


# ══════════════════════════════════════════════════════
#  路由 6: 上传多段干声 + 创建训练任务（多文件版）
# ══════════════════════════════════════════════════════


@app.get("/api/studio/effect-rack/capabilities", summary="Studio Effect Rack render capabilities")
async def get_studio_effect_rack_capabilities():
    return get_effect_rack_capabilities()


@app.post("/api/studio/effect-rack/export", summary="export Studio Effect Rack draft")
async def post_studio_effect_rack_export(payload: StudioEffectExportRequest):
    try:
        return export_effect_rack_draft(
            track_id=payload.track_id,
            source_job_id=payload.source_job_id,
            source_artifact_id=payload.source_artifact_id,
            effect_rack=payload.effect_rack,
            export_profile=payload.export_profile,
            note=payload.note,
            render_engine=payload.render_engine,
        )
    except StudioEffectExportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


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
    try:
        material_decision = profile_train_saved_uploads(saved["saved_files"])
        strategy_key = material_decision.get("recommended_route") or resolve_train_strategy(
            saved["file_count"],
            material_decision.get("single_long_eligible"),
        )
        preflight = run_train_preflight(strategy_key, material_decision)
        if not preflight["ok"]:
            if saved["file_count"] == 1 and material_decision.get("submission_allowed") is False:
                raise HTTPException(status_code=422, detail=build_material_rejection_detail(material_decision))
            raise HTTPException(status_code=422, detail=preflight)

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
                "material_decision": material_decision,
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
                "input_mode": material_decision.get("input_mode") or ("multi_file" if saved["file_count"] > 1 else "single_file"),
                "smoke": bool(smoke),
                "material_decision": material_decision,
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
                metadata={
                    "source": "train_upload",
                    "material_profile": material_decision.get("material_profile") or "",
                },
            )

        job = activate_train_job(task_id) or job
        log_stage(
            task_id,
            "train_upload",
            "completed",
            f"train upload accepted: {saved['file_count']} files",
            {
                "strategy_key": strategy_key,
                "dataset_id": dataset_id,
                "material_decision": material_decision,
            },
        )
        log_stage(task_id, "train_preflight", "completed", "train preflight ok", preflight)

        reserved = reserve_job(job, TRAIN_START_STATUS)
        queue_state = "processing" if reserved else "waiting_for_compute_slot"
        if reserved:
            background_tasks.add_task(_run_job, task_id)
            print(f"[Train] started {task_id} -> {voice_name} ({saved['file_count']} files)")
        else:
            set_job_pending(task_id, "")
            print(f"[Train] queued {task_id} -> {voice_name}")

        message = (
            f"{material_decision.get('reason') or '训练素材验收通过。'} 当前已进入训练执行。"
            if reserved
            else f"{material_decision.get('reason') or '训练素材验收通过。'} 当前算力繁忙，任务已排队等待。"
        )
        return TrainResponse(
            task_id=task_id,
            voice_name=voice_name,
            file_count=saved["file_count"],
            strategy_key=strategy_key,
            queue_state=queue_state,
            material_profile=material_decision.get("material_profile") or "",
            duration_seconds=material_decision.get("duration_seconds"),
            duration_label=material_decision.get("duration_label") or "",
            sample_rate=material_decision.get("sample_rate"),
            channels=material_decision.get("channels"),
            codec=material_decision.get("codec") or "",
            container=material_decision.get("container") or "",
            bit_rate=material_decision.get("bit_rate"),
            recommended_route=material_decision.get("recommended_route") or strategy_key,
            single_long_eligible=material_decision.get("single_long_eligible"),
            reason=material_decision.get("reason") or "",
            next_step=material_decision.get("next_step") or "",
            material_decision=material_decision,
            status="processing" if reserved else "pending",
            message=message,
        )
    except HTTPException:
        discard_job_workspace(task_id)
        raise
    except Exception as exc:
        discard_job_workspace(task_id)
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"训练素材验收失败：{exc}",
                "code": "train_material_profile_failed",
                "reason": str(exc),
                "next_step": "请检查音频文件是否可读，或确认 ffprobe / ffmpeg 环境正常。",
            },
        ) from exc
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
    engine_summary = get_engine_summary()
    return {
        "status":  "ok",
        "service": "FeiShark Studio API",
        "version": "2.2.0",
        "features": {
            "chunked_upload": True,
            "cors_enabled":   True,
            "disk_fallback":  True,
        },
        "engine": engine_summary,
        "rvc": engine_summary,
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
