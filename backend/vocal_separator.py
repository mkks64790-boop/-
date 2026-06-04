"""
FeiShark Studio - UVR5 人声分离包装模块
轻量解耦方案：通过 subprocess 调用 AudioPipeline 的 UVR5 引擎
"""

import subprocess
import os
import sys
import time
import re

try:
    from .engine_paths import (
        AUDIO_PIPELINE_DIR,
        AUDIO_PIPELINE_VENV,
        PROJECT_ROOT as ENGINE_PROJECT_ROOT,
        UVR5_MODEL_PATH,
    )
except ImportError:
    from engine_paths import (
        AUDIO_PIPELINE_DIR,
        AUDIO_PIPELINE_VENV,
        PROJECT_ROOT as ENGINE_PROJECT_ROOT,
        UVR5_MODEL_PATH,
    )

# 路径发现：优先环境变量，其次常见安装目录
def _pick_first_existing(*paths: str) -> str:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return paths[0] if paths else ""

# ── 配置 ──────────────────────────────────────────────

PROJECT_ROOT = str(ENGINE_PROJECT_ROOT)
_LEGACY_AUDIO_PIPELINE_DIR_CANDIDATES = (
    os.path.join(PROJECT_ROOT, "external", "audio-pipeline"),
    r"D:\AudioPipeline",
    r"C:\Users\ASUS\AudioPipeline",
)
AUDIO_PIPELINE_VENV = AUDIO_PIPELINE_VENV
UVR5_MODEL_PATH = UVR5_MODEL_PATH
# Workspace-bundled fallbacks (for self-contained training stability)
# Prefer external/audio-pipeline/ inside project for no external install fragility

OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "outputs")

# 任务状态常量
STATUS_SEPARATING = "分离中"
STATUS_PITCH_READY = "修音中"
STATUS_FAILED = "失败"


# ── 核心函数 ──────────────────────────────────────────


def split_audio(task_id: str, input_file_path: str) -> dict:
    """
    对指定音频执行 UVR5 人声分离

    流程:
      1. 更新数据库状态 → "分离中"
      2. subprocess 调用 UVR5 引擎
      3. 将输出文件重命名到标准路径
      4. 更新数据库状态 → "修音中" 或 "失败"

    Returns:
        {"success": True/False, "vocal": path, "instrumental": path, "duration": sec, "error": str}
    """
    try:
        from .db import update_task_status
    except ImportError:
        from db import update_task_status

    out_dir = os.path.join(OUTPUT_ROOT, task_id)
    vocal_path = os.path.join(out_dir, "vocal.wav")
    instrumental_path = os.path.join(out_dir, "instrumental.wav")

    # 1. 状态 → 分离中
    print(f"[分离] 启动任务 {task_id}")
    update_task_status(task_id, STATUS_SEPARATING)

    # 前置检查
    for label, path in [("输入文件", input_file_path), ("UVR5 模型", UVR5_MODEL_PATH),
                         ("AudioPipeline venv", AUDIO_PIPELINE_VENV)]:
        if not os.path.exists(path):
            err = f"{label}不存在: {path}"
            print(f"[分离] {err}")
            update_task_status(task_id, STATUS_FAILED, err)
            return {"success": False, "error": err}

    os.makedirs(out_dir, exist_ok=True)

    # 2. 生成/更新 runner 脚本
    uvr5_runner = os.path.join(AUDIO_PIPELINE_DIR, "run_uvr5_split.py")
    _ensure_runner_script(uvr5_runner)

    # 3. subprocess 调用
    print(f"[分离] 调用引擎: {AUDIO_PIPELINE_VENV}")
    print(f"[分离] 输入: {input_file_path}")
    print(f"[分离] 输出: {out_dir}")

    try:
        t0 = time.time()

        result = subprocess.run(
            [AUDIO_PIPELINE_VENV, uvr5_runner,
             "--input", input_file_path,
             "--model", UVR5_MODEL_PATH,
             "--output", out_dir],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            cwd=AUDIO_PIPELINE_DIR,
        )

        elapsed = time.time() - t0
        print(f"[分离] 引擎耗时: {elapsed:.1f}s")

        if result.returncode != 0:
            err = _extract_error(result.stderr)
            print(f"[分离] 引擎报错: {err}")
            update_task_status(task_id, STATUS_FAILED, err)
            return {"success": False, "error": err}

        # 4. 规范化输出文件名
        _normalize_output(out_dir, vocal_path, instrumental_path)

        # 验证输出文件
        if not os.path.exists(vocal_path) or not os.path.exists(instrumental_path):
            err = "输出文件缺失，分离可能不完整"
            print(f"[分离] {err}")
            update_task_status(task_id, STATUS_FAILED, err)
            return {"success": False, "error": err}

        # 5. 状态 → 修音中
        update_task_status(task_id, STATUS_PITCH_READY)

        duration_error = _validate_duration_preservation(input_file_path, vocal_path, instrumental_path)
        if duration_error:
            print(f"[鍒嗙] {duration_error}")
            update_task_status(task_id, STATUS_FAILED, duration_error)
            return {"success": False, "error": duration_error}

        duration = _get_audio_duration(vocal_path)
        print(f"[分离] 完成: vocal={vocal_path}, instrumental={instrumental_path}")
        print(f"[分离] 人声时长: {duration:.2f}s")

        return {
            "success": True,
            "vocal": vocal_path,
            "instrumental": instrumental_path,
            "duration": duration,
            "elapsed": elapsed,
        }

    except subprocess.TimeoutExpired:
        err = "UVR5 分离超时（>300s）"
        print(f"[分离] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    except Exception as e:
        err = str(e)
        print(f"[分离] 异常: {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}


# ── 内部工具 ──────────────────────────────────────────

# Runner 脚本模板（独立完整的分离逻辑，修复原始引擎 ISTFT bug）
_RUNNER_SCRIPT = r'''"""
FeiShark UVR5 分离 CLI（自动生成，含 ISTFT 修复补丁）
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import librosa
import soundfile as sf
import onnxruntime as ort

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # 加载音频
    audio, sr = librosa.load(args.input, sr=44100, mono=True)
    duration = len(audio) / sr

    # 加载模型
    providers = ort.get_available_providers()
    if 'CUDAExecutionProvider' in providers:
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
    else:
        providers = ['CPUExecutionProvider']
    session = ort.InferenceSession(args.model, providers=providers)
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    n_fft = 6144
    hop_length = 512
    model_freq = 3072
    model_frames = 256

    # STFT
    stft = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length,
                         win_length=n_fft, window='hann', center=True)
    n_total_frames = stft.shape[1]

    # 分块推理: the model accepts 256 time frames. Do not crop larger 5s chunks.
    frames_per_chunk = model_frames
    n_chunks = max(1, (n_total_frames + frames_per_chunk - 1) // frames_per_chunk)

    vocal_chunks = []
    instr_chunks = []

    for i in range(n_chunks):
        start_f = i * frames_per_chunk
        end_f = min((i + 1) * frames_per_chunk, n_total_frames)
        actual_frames = end_f - start_f
        chunk_stft = stft[:, start_f:end_f]

        real = np.real(chunk_stft).astype(np.float32)
        imag = np.imag(chunk_stft).astype(np.float32)

        # Pad/crop 到模型输入尺寸
        if real.shape[0] > model_freq:
            real = real[:model_freq, :]
            imag = imag[:model_freq, :]
        elif real.shape[0] < model_freq:
            pad_f = model_freq - real.shape[0]
            real = np.pad(real, ((0, pad_f), (0, 0)))
            imag = np.pad(imag, ((0, pad_f), (0, 0)))

        if real.shape[1] > model_frames:
            raise RuntimeError("time chunk exceeds model_frames; chunking contract broken")
        elif real.shape[1] < model_frames:
            pad_t = model_frames - real.shape[1]
            real = np.pad(real, ((0, 0), (0, pad_t)))
            imag = np.pad(imag, ((0, 0), (0, pad_t)))

        inp = np.stack([real, imag, real, imag])[np.newaxis].astype(np.float32)
        out = session.run([output_name], {input_name: inp})[0][0]

        # 提取 vocal (ch 0,1) 和 instrumental (ch 2,3)
        v_spec = (out[0] + 1j * out[1])[:, :actual_frames]
        i_spec = (out[2] + 1j * out[3])[:, :actual_frames]

        vocal_chunks.append(v_spec)
        instr_chunks.append(i_spec)

    # 合并
    vocal_spec = np.concatenate(vocal_chunks, axis=1)
    instr_spec = np.concatenate(instr_chunks, axis=1)

    # ISTFT - pad 回原始 STFT 的 freq 维度以确保兼容
    orig_n_freq = stft.shape[0]  # 通常 3073 (n_fft//2+1)
    if vocal_spec.shape[0] < orig_n_freq:
        pad_f = orig_n_freq - vocal_spec.shape[0]
        vocal_spec = np.pad(vocal_spec, ((0, pad_f), (0, 0)))
        instr_spec = np.pad(instr_spec, ((0, pad_f), (0, 0)))

    vocal_audio = librosa.istft(vocal_spec, hop_length=hop_length,
                                 win_length=n_fft, window='hann', center=True,
                                 length=len(audio))
    instr_audio = librosa.istft(instr_spec, hop_length=hop_length,
                                 win_length=n_fft, window='hann', center=True,
                                 length=len(audio))

    vocal_path = os.path.join(args.output, "vocal.wav")
    instr_path = os.path.join(args.output, "instrumental.wav")
    sf.write(vocal_path, vocal_audio, sr)
    sf.write(instr_path, instr_audio, sr)

    print(f"RESULT:vocal={vocal_path}")
    print(f"RESULT:instrumental={instr_path}")
    print(f"RESULT:duration={duration}")
    sys.exit(0)

if __name__ == "__main__":
    main()
'''


def _ensure_runner_script(path: str):
    """生成 UVR5 runner 脚本（每次覆盖以保持补丁最新）"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(_RUNNER_SCRIPT)


def _extract_error(stderr: str) -> str:
    """从 stderr 中提取有意义的错误信息，过滤 ANSI 转义码和噪音"""
    if not stderr:
        return "引擎异常退出（无错误详情）"

    # 移除 ANSI 转义码
    clean = re.sub(r'\x1b\[[0-9;]*m', '', stderr)

    # 查找 Python Traceback 中的实际错误
    for line in clean.splitlines():
        line = line.strip()
        if not line:
            continue
        # 跳过 ONNX CUDA 加载警告（非致命）
        if 'CUDAExecutionProvider' in line or 'cublasLt64' in line or 'cuDNN' in line:
            continue
        # 跳过 Traceback 行号信息
        if line.startswith('Traceback') or line.startswith('File ') or line.strip() == '^':
            continue
        # 第一个有意义的错误行
        if any(kw in line for kw in ['Error', 'Exception', 'FAIL', 'failed', 'error']):
            return line[:200]  # 截断过长内容

    # 回退：取最后几行
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    return lines[-1][:200] if lines else "未知引擎错误"


def _normalize_output(out_dir: str, vocal_target: str, instrumental_target: str):
    """将 UVR5 输出文件重命名为标准名称"""
    for f in os.listdir(out_dir):
        if not f.lower().endswith(".wav"):
            continue
        src = os.path.join(out_dir, f)
        if "vocal" in f.lower() and not os.path.exists(vocal_target):
            os.rename(src, vocal_target)
        elif "instrumental" in f.lower() and not os.path.exists(instrumental_target):
            os.rename(src, instrumental_target)


def _validate_duration_preservation(input_path: str, vocal_path: str, instrumental_path: str, tolerance: float = 0.05) -> str:
    input_duration = _get_audio_duration(input_path)
    vocal_duration = _get_audio_duration(vocal_path)
    instrumental_duration = _get_audio_duration(instrumental_path)
    if input_duration <= 0 or vocal_duration <= 0 or instrumental_duration <= 0:
        return ""

    vocal_delta = abs(vocal_duration - input_duration) / input_duration
    instrumental_delta = abs(instrumental_duration - input_duration) / input_duration
    if vocal_delta <= tolerance and instrumental_delta <= tolerance:
        return ""

    return (
        "duration mismatch: "
        f"input={input_duration:.3f}s "
        f"vocal={vocal_duration:.3f}s "
        f"instrumental={instrumental_duration:.3f}s "
        f"tolerance={tolerance:.0%}"
    )


def _get_audio_duration(path: str) -> float:
    wav_duration = _get_wav_duration(path)
    if wav_duration > 0:
        return wav_duration

    try:
        import soundfile as sf
        info = sf.info(path)
        return float(info.frames / info.samplerate) if info.samplerate else 0.0
    except Exception:
        pass

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        return 0.0
    return 0.0


def _get_wav_duration(path: str) -> float:
    """读取 WAV 时长"""
    try:
        import wave
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate if rate else 0.0
    except Exception:
        return 0.0


# ── 冒烟测试 ──────────────────────────────────────────


def smoke_test():
    """
    第三轮冒烟测试：UVR5 人声分离模块
    生成合成音频 → 创建任务 → 执行分离 → 验证状态流转
    """
    import struct
    import wave
    import math

    from db import init_db, create_task

    print("=" * 50)
    print("第三轮冒烟测试: UVR5 人声分离模块")
    print("=" * 50)

    init_db()

    task_id = "test_sep_001"
    test_input = os.path.join(PROJECT_ROOT, "shared_data", "uploads", "suno_test.wav")
    os.makedirs(os.path.dirname(test_input), exist_ok=True)

    # 生成 5 秒 440Hz 正弦波
    sr = 44100
    duration = 5.0
    frames = int(sr * duration)
    with wave.open(test_input, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(frames):
            val = int(12000 * math.sin(2 * math.pi * 440 * i / sr))
            wf.writeframes(struct.pack("<h", val))

    print(f"\n[测试] 已生成测试音频: {test_input}")

    create_task(task_id, "shared_data/uploads/suno_test.wav")

    print(f"\n[测试] --- 分离前 ---")
    _print_task_status(task_id)

    print(f"\n[测试] --- 开始分离 ---")
    result = split_audio(task_id, test_input)

    print(f"\n[测试] --- 分离后 ---")
    _print_task_status(task_id)

    print(f"\n[测试] 分离结果:")
    for k in ["success", "vocal", "instrumental", "duration", "elapsed"]:
        print(f"  {k:15s}: {result.get(k, 'N/A')}")
    if result.get("error"):
        print(f"  {'error':15s}: {result['error']}")

    out_dir = os.path.join(OUTPUT_ROOT, task_id)
    if os.path.exists(out_dir):
        print(f"\n[测试] 输出目录内容:")
        for f in os.listdir(out_dir):
            size = os.path.getsize(os.path.join(out_dir, f))
            print(f"  {f} ({size:,} bytes)")

    print(f"\n{'=' * 50}")
    if result.get("success"):
        print("[OK] 冒烟测试通过")
    else:
        print(f"[FAIL] 冒烟测试失败: {result.get('error')}")
    print("=" * 50)


def _print_task_status(task_id: str):
    """打印任务当前数据库状态"""
    from db import get_connection
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row:
            print(f"  task_id:    {row['task_id']}")
            print(f"  input_file: {row['input_file']}")
            print(f"  status:     {row['status']}")
            print(f"  error_log:  {row['error_log'] or '(空)'}")
            print(f"  created_at: {row['created_at']}")
        else:
            print(f"  任务 {task_id} 不存在")
    finally:
        conn.close()


if __name__ == "__main__":
    smoke_test()
