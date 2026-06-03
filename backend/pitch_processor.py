"""
FeiShark Studio - 独立修音包装模块
轻量解耦方案：通过 subprocess 调用 AudioPipeline 的 RMVPE + PitchCorrector + PitchShifter 引擎

流水线位置: 分离中 → [修音中] → 变声中
"""

import subprocess
import os
import sys
import time
import re
import shutil

# 路径发现：优先环境变量，其次常见安装目录
def _pick_first_existing(*paths: str) -> str:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return paths[0] if paths else ""

# ── 配置 ──────────────────────────────────────────────

AUDIO_PIPELINE_DIR = os.environ.get("FEISHARK_AUDIO_PIPELINE") or _pick_first_existing(
    r"D:\AudioPipeline",
    r"C:\Users\ASUS\AudioPipeline",
)
AUDIO_PIPELINE_VENV = os.path.join(AUDIO_PIPELINE_DIR, "venv", "Scripts", "python.exe")
RMVPE_MODEL_PATH = os.path.join(AUDIO_PIPELINE_DIR, "rmvpe.onnx")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "outputs")

# 任务状态常量
STATUS_PITCH_FIXING = "修音中"
STATUS_VC_READY = "变声中"
STATUS_FAILED = "失败"


# ── 核心函数 ──────────────────────────────────────────


def fix_vocal_pitch(
    task_id: str,
    key: str = "C",
    mode: str = "major",
    strength: float = 0.4,
    deess_strength: float = 0.3,
) -> dict:
    """
    对已分离的人声执行 FeiShark 音准修正

    流程:
      1. 确认数据库状态为 "修音中"
      2. subprocess 调用 AudioPipeline 修音引擎
         - RMVPE 提取 F0
         - PitchCorrector 修正音高
         - PitchShifter 写回波形
         - DeEsser 去齿音
      3. 输出 vocal_fixed.wav（不覆盖原始 vocal.wav）
      4. 更新数据库状态 → "变声中" 或 "失败"

    Args:
        task_id:        任务 ID
        key:            调性根音 (C, D, E, F, G, A, B)
        mode:           调式 (major, minor, 五声音阶, etc.)
        strength:       修正强度 0-1
        deess_strength: 去齿音强度 0-1

    Returns:
        {"success": True/False, "output": path, "duration": sec, "elapsed": sec, "error": str}
    """
    try:
        from .db import get_connection, update_task_status
    except ImportError:
        from db import get_connection, update_task_status

    vocal_path = os.path.join(OUTPUT_ROOT, task_id, "vocal.wav")
    fixed_path = os.path.join(OUTPUT_ROOT, task_id, "vocal_fixed.wav")

    # 1. 确认状态为"修音中"
    print(f"[修音] 启动任务 {task_id}")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        err = f"任务 {task_id} 不存在"
        print(f"[修音] {err}")
        return {"success": False, "error": err}

    if row["status"] != STATUS_PITCH_FIXING:
        print(f"[修音] 当前状态 '{row['status']}' ≠ '{STATUS_PITCH_FIXING}'，强制设置为修音中")
        update_task_status(task_id, STATUS_PITCH_FIXING)

    # 前置检查
    for label, path in [("人声文件", vocal_path), ("RMVPE 模型", RMVPE_MODEL_PATH),
                         ("AudioPipeline venv", AUDIO_PIPELINE_VENV)]:
        if not os.path.exists(path):
            err = f"{label}不存在: {path}"
            print(f"[修音] {err}")
            update_task_status(task_id, STATUS_FAILED, err)
            return {"success": False, "error": err}

    # 2. 生成 runner 脚本
    runner_path = os.path.join(AUDIO_PIPELINE_DIR, "run_feishark_fix.py")
    _ensure_runner_script(runner_path)

    # 3. subprocess 调用
    print(f"[修音] 参数: key={key}, mode={mode}, strength={strength}, deess={deess_strength}")
    print(f"[修音] 输入: {vocal_path}")
    print(f"[修音] 输出: {fixed_path}")
    print(f"[修音] 引擎: {AUDIO_PIPELINE_VENV}")

    try:
        t0 = time.time()

        result = subprocess.run(
            [
                AUDIO_PIPELINE_VENV,
                runner_path,
                "--input", vocal_path,
                "--output", fixed_path,
                "--rmvpe", RMVPE_MODEL_PATH,
                "--key", key,
                "--mode", mode,
                "--strength", str(strength),
                "--deess", str(deess_strength),
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,  # 5 分钟超时
            cwd=AUDIO_PIPELINE_DIR,
        )

        elapsed = time.time() - t0
        print(f"[修音] 引擎耗时: {elapsed:.1f}s")

        if result.returncode != 0:
            err = _extract_error(result.stderr)
            print(f"[修音] 引擎报错: {err}")
            if _is_safe_pitch_fallback_error(err, result.stderr):
                fallback = _copy_vocal_as_fixed(vocal_path, fixed_path)
                if fallback.get("success"):
                    update_task_status(task_id, STATUS_VC_READY)
                    duration = _get_wav_duration(fixed_path)
                    print(f"[修音] 已降级跳过修音: {fixed_path} ({duration:.2f}s)")
                    return {
                        "success": True,
                        "output": fixed_path,
                        "duration": duration,
                        "elapsed": elapsed,
                        "fallback": "copy_original_vocal",
                        "warning": err,
                    }
                err = fallback.get("error") or err
            update_task_status(task_id, STATUS_FAILED, err)
            return {"success": False, "error": err}

        # 4. 验证输出
        if not os.path.exists(fixed_path):
            err = "vocal_fixed.wav 未生成"
            print(f"[修音] {err}")
            update_task_status(task_id, STATUS_FAILED, err)
            return {"success": False, "error": err}

        # 5. 状态 → 变声中
        update_task_status(task_id, STATUS_VC_READY)

        duration = _get_wav_duration(fixed_path)
        print(f"[修音] 完成: {fixed_path} ({duration:.2f}s)")

        return {
            "success": True,
            "output": fixed_path,
            "duration": duration,
            "elapsed": elapsed,
        }

    except subprocess.TimeoutExpired:
        err = "修音超时（>300s）"
        print(f"[修音] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    except Exception as e:
        err = str(e)
        print(f"[修音] 异常: {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}


# ── 内部工具 ──────────────────────────────────────────

# Runner 脚本模板：完整修音流水线
# RMVPE 提取 F0 → PitchCorrector 修正 → PitchShifter 写回 → DeEsser 去齿音
_RUNNER_SCRIPT = r'''"""
FeiShark 修音 CLI（自动生成）
RMVPE F0 提取 → PitchCorrector → PitchShifter → DeEsser
"""
import argparse, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import librosa
import soundfile as sf
from inference_v3 import RMVPEProcessor
from pitch_corrector import PitchCorrector
from pitch_shifter import PitchShifter
from deesser import DeEsser, DeEsserConfig

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rmvpe", required=True)
    parser.add_argument("--key", default="C")
    parser.add_argument("--mode", default="major")
    parser.add_argument("--strength", type=float, default=0.4)
    parser.add_argument("--deess", type=float, default=0.3)
    args = parser.parse_args()

    # 1. 加载音频
    audio, sr = librosa.load(args.input, sr=16000, mono=True)
    duration = len(audio) / sr
    print(f"FIX:loaded duration={duration:.2f}s sr={sr}")

    # 2. RMVPE 提取 F0
    rmvpe = RMVPEProcessor(args.rmvpe)
    f0 = rmvpe.extract_pitch(args.input)
    print(f"FIX:f0 frames={len(f0)} voiced={int(np.sum(f0 > 50))}")

    # 3. PitchCorrector 修正 F0
    corrector = PitchCorrector(key=args.key, mode=args.mode, strength=args.strength)
    f0_corrected = corrector.correct(f0)
    n_changed = int(np.sum((f0 > 50) & (np.abs(f0_corrected - f0) > 1)))
    print(f"FIX:corrected frames_changed={n_changed}/{len(f0)}")

    # 4. PitchShifter 写回波形
    shifter = PitchShifter(sample_rate=sr)
    audio_fixed = shifter.shift(audio, f0, f0_corrected)
    print(f"FIX:shifted samples={len(audio_fixed)}")

    # 5. DeEsser 去齿音
    if args.deess > 0:
        config = DeEsserConfig(strength=args.deess)
        deesser = DeEsser(config)
        audio_fixed = deesser.process(audio_fixed, sr)
        print(f"FIX:deessed strength={args.deess}")

    # 6. 输出
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    sf.write(args.output, audio_fixed, sr, subtype='PCM_16')
    print(f"FIX:output={args.output}")

    sys.exit(0)

if __name__ == "__main__":
    main()
'''


def _ensure_runner_script(path: str):
    """生成修音 runner 脚本（每次覆盖以保持最新）"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(_RUNNER_SCRIPT)


def _extract_error(stderr: str) -> str:
    """从 stderr 中提取有意义的错误信息"""
    if not stderr:
        return "引擎异常退出（无错误详情）"

    clean = re.sub(r'\x1b\[[0-9;]*m', '', stderr)

    for line in clean.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(kw in line for kw in ['CUDAExecutionProvider', 'cublasLt64', 'cuDNN', 'ONNX']):
            continue
        if line.startswith('Traceback') or line.startswith('File ') or line.strip() == '^':
            continue
        if any(kw in line for kw in ['Error', 'Exception', 'FAIL', 'failed', 'error']):
            return line[:200]

    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    return lines[-1][:200] if lines else "未知引擎错误"


def _is_safe_pitch_fallback_error(error: str, stderr: str = "") -> bool:
    """Allow only the known short-frame numpy broadcast failure to bypass pitch fix."""
    text = f"{error}\n{stderr or ''}"
    match = re.search(
        r"operands could not be broadcast together with shapes\s+"
        r"\((?P<frames>\d+),\)\s+\(2048,\)\s+\((?P=frames),\)",
        text,
    )
    if not match:
        return False

    frames = int(match.group("frames"))
    return 0 < frames < 2048


def _copy_vocal_as_fixed(vocal_path: str, fixed_path: str) -> dict:
    try:
        if not os.path.isfile(vocal_path):
            return {"success": False, "error": f"降级失败，人声文件不存在: {vocal_path}"}
        if os.path.abspath(vocal_path) == os.path.abspath(fixed_path):
            return {"success": False, "error": "降级失败，输入输出不能是同一个文件"}
        os.makedirs(os.path.dirname(fixed_path), exist_ok=True)
        shutil.copyfile(vocal_path, fixed_path)
        return {"success": True, "output": fixed_path}
    except Exception as exc:
        return {"success": False, "error": f"降级复制 vocal_fixed.wav 失败: {exc}"}


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
    第四轮冒烟测试：FeiShark 独立修音模块
    使用上一步 UVR5 分离出的 vocal.wav → 修音 → 验证状态流转
    """
    from db import get_connection, init_db, create_task, update_task_status

    print("=" * 50)
    print("第四轮冒烟测试: FeiShark 独立修音模块")
    print("=" * 50)

    init_db()

    task_id = "test_sep_001"  # 复用上一步 UVR5 分离的任务

    # 确认 vocal.wav 存在
    vocal_path = os.path.join(OUTPUT_ROOT, task_id, "vocal.wav")
    if not os.path.exists(vocal_path):
        print(f"\n[测试] 前置条件缺失: {vocal_path}")
        print("[测试] 请先运行 vocal_separator.py 的冒烟测试")
        return

    # 确保任务状态为"修音中"
    conn = get_connection()
    row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    conn.close()
    if not row or row["status"] != STATUS_PITCH_FIXING:
        update_task_status(task_id, STATUS_PITCH_FIXING)

    print(f"\n[测试] --- 修音前 ---")
    _print_task_status(task_id)

    print(f"\n[测试] --- 开始修音 ---")
    result = fix_vocal_pitch(task_id, key="C", mode="major", strength=0.4, deess_strength=0.3)

    print(f"\n[测试] --- 修音后 ---")
    _print_task_status(task_id)

    print(f"\n[测试] 修音结果:")
    for k in ["success", "output", "duration", "elapsed"]:
        print(f"  {k:15s}: {result.get(k, 'N/A')}")
    if result.get("error"):
        print(f"  {'error':15s}: {result['error']}")

    # 对比文件
    out_dir = os.path.join(OUTPUT_ROOT, task_id)
    if os.path.exists(out_dir):
        print(f"\n[测试] 输出目录内容:")
        for f in sorted(os.listdir(out_dir)):
            size = os.path.getsize(os.path.join(out_dir, f))
            print(f"  {f:25s} ({size:,} bytes)")

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
