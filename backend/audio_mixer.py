"""
FeiShark Studio - 自动化大师混音模块
轻量解耦方案：Pedalboard DSP 混音链

流水线位置: 变声中 → [混音中] → 完成

混音链路:
  1. 读取变声人声 (vocal_transformed.wav) + 原版伴奏 (instrumental.wav)
  2. 采样率统一 → 长度对齐 → 1:1 时间合成
  3. 人声干声 DSP 润色:
     - Reverb 混响 (干湿比 10%，模拟空间感)
     - Compressor 轻量压限 (消除剥离感，让人声融入伴奏)
  4. Limiter 安全限幅 (防削波)
  5. 输出 final_master.wav
"""

import os
import sys
import time
import wave

import numpy as np
import soundfile as sf
from pedalboard import Reverb, Compressor, Limiter, Pedalboard

# ── 配置 ──────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "outputs")

# 混音 DSP 参数
REVERB_ROOM_SIZE = 0.15       # 混响房间大小（0~1，越小越干）
REVERB_DAMPING = 0.7          # 高频衰减（越大越温暖）
REVERB_WET_LEVEL = 0.10       # 混响干湿比 10%（微量空间感）
REVERB_DRY_LEVEL = 1.0        # 干声保持原始音量

COMPRESSOR_THRESHOLD_DB = -18 # 压限阈值（dB）
COMPRESSOR_RATIO = 3.0        # 压缩比（3:1 轻量压限）
COMPRESSOR_ATTACK_MS = 5.0    # 启动时间
COMPRESSOR_RELEASE_MS = 50.0  # 释放时间

LIMITER_THRESHOLD_DB = -1.0   # 限幅阈值（留 1dB headroom）

# 目标采样率和位深
TARGET_SR = 44100
TARGET_SUBTYPE = "PCM_16"

# 任务状态常量
STATUS_MIXING = "混音中"
STATUS_SUCCESS = "完成"
STATUS_FAILED = "失败"


# ── 核心函数 ──────────────────────────────────────────


def merge_master_audio(
    task_id: str,
    vocal_gain_db: float = 0.0,
    instrumental_gain_db: float = 0.0,
    reverb_wet: float = REVERB_WET_LEVEL,
    compressor_threshold: float = COMPRESSOR_THRESHOLD_DB,
    limiter_threshold: float = LIMITER_THRESHOLD_DB,
) -> dict:
    """
    自动化大师混音：将变声人声与原版伴奏合成为最终母带

    流程:
      1. 确认/设置数据库状态为 "混音中"
      2. 读取 vocal_transformed.wav + instrumental.wav
      3. 采样率统一 + 长度对齐
      4. Pedalboard DSP 链: Reverb → Compressor → Limiter
      5. 人声 + 伴奏混音合成
      6. 输出 final_master.wav（44100Hz / 16bit）
      7. 更新状态 → "完成" 或 "失败"

    Args:
        task_id:              任务 ID
        vocal_gain_db:        人声增益 (dB，默认 0)
        instrumental_gain_db: 伴奏增益 (dB，默认 0)
        reverb_wet:           混响干湿比 (0~1，默认 0.10)
        compressor_threshold: 压限阈值 (dB，默认 -18)
        limiter_threshold:    限幅阈值 (dB，默认 -1.0)

    Returns:
        {"success": True/False, "output": path, "duration": sec,
         "elapsed": sec, "error": str, "stats": {...}}
    """
    try:
        from .db import get_connection, update_task_status
    except ImportError:
        from db import get_connection, update_task_status

    out_dir = os.path.join(OUTPUT_ROOT, task_id)
    vocal_path = os.path.join(out_dir, "vocal_transformed.wav")
    instr_path = os.path.join(out_dir, "instrumental.wav")
    master_path = os.path.join(out_dir, "final_master.wav")

    # ── 1. 状态管理 ──
    print(f"[混音] 启动大师混音任务 {task_id}")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        err = f"任务 {task_id} 不存在"
        print(f"[混音] {err}")
        return {"success": False, "error": err}

    if row["status"] != STATUS_MIXING:
        print(f"[混音] 当前状态 '{row['status']}' ≠ '{STATUS_MIXING}'，强制设置")
        update_task_status(task_id, STATUS_MIXING)

    # ── 2. 前置检查 ──
    missing = []
    for label, path in [("变声人声", vocal_path), ("原版伴奏", instr_path)]:
        if not os.path.exists(path):
            missing.append(f"{label}: {path}")

    if missing:
        err = f"输入文件缺失: {'; '.join(missing)}"
        print(f"[混音] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    # ── 3. 读取音频 ──
    print(f"[混音] 读取变声人声: {vocal_path}")
    vocal, sr_vocal = sf.read(vocal_path, always_2d=True)
    print(f"[混音]   采样率={sr_vocal}Hz, 形状={vocal.shape}")

    print(f"[混音] 读取原版伴奏: {instr_path}")
    instr, sr_instr = sf.read(instr_path, always_2d=True)
    print(f"[混音]   采样率={sr_instr}Hz, 形状={instr.shape}")

    try:
        t0 = time.time()

        # ── 4. 采样率统一 ──
        target_sr = TARGET_SR
        if sr_vocal != target_sr or sr_instr != target_sr:
            import librosa
            if sr_vocal != target_sr:
                print(f"[混音] 人声重采样 {sr_vocal} → {target_sr}Hz")
                vocal = librosa.resample(vocal.T, orig_sr=sr_vocal, target_sr=target_sr).T
            if sr_instr != target_sr:
                print(f"[混音] 伴奏重采样 {sr_instr} → {target_sr}Hz")
                instr = librosa.resample(instr.T, orig_sr=sr_instr, target_sr=target_sr).T

        # ── 5. 通道统一 → 单声道混音 → 双声道输出 ──
        # 统一为单声道进行混音处理
        vocal_mono = _to_mono(vocal)
        instr_mono = _to_mono(instr)

        # ── 6. 长度对齐（1:1 绝对时间对齐）──
        max_len = max(len(vocal_mono), len(instr_mono))
        print(f"[混音] 长度对齐: vocal={len(vocal_mono)}, instr={len(instr_mono)}, max={max_len}")

        if len(vocal_mono) < max_len:
            vocal_mono = np.pad(vocal_mono, (0, max_len - len(vocal_mono)))
        if len(instr_mono) < max_len:
            instr_mono = np.pad(instr_mono, (0, max_len - len(instr_mono)))

        # ── 7. 增益调整 ──
        if vocal_gain_db != 0:
            gain = 10 ** (vocal_gain_db / 20)
            vocal_mono = vocal_mono * gain
            print(f"[混音] 人声增益: {vocal_gain_db:+.1f}dB")

        if instrumental_gain_db != 0:
            gain = 10 ** (instrumental_gain_db / 20)
            instr_mono = instr_mono * gain
            print(f"[混音] 伴奏增益: {instrumental_gain_db:+.1f}dB")

        # ── 8. 人声 DSP 润色链 ──
        print(f"[混音] 构建 DSP 链: Reverb(wet={reverb_wet:.0%}) → Compressor(-{abs(compressor_threshold):.0f}dB) → Limiter(-{abs(limiter_threshold):.1f}dB)")

        vocal_float = vocal_mono.astype(np.float32)

        # Reverb 混响 — 模拟空间感，消除剥离感
        board = Pedalboard([
            Reverb(
                room_size=REVERB_ROOM_SIZE,
                damping=REVERB_DAMPING,
                wet_level=reverb_wet,
                dry_level=REVERB_DRY_LEVEL,
            ),
            Compressor(
                threshold_db=compressor_threshold,
                ratio=COMPRESSOR_RATIO,
                attack_ms=COMPRESSOR_ATTACK_MS,
                release_ms=COMPRESSOR_RELEASE_MS,
            ),
            Limiter(threshold_db=limiter_threshold),
        ])

        # pedalboard 期望 (channels, samples) 或 (samples,) 格式
        vocal_processed = board(vocal_float, target_sr)

        print(f"[混音] DSP 处理完成: {len(vocal_processed)} samples")

        # ── 9. 混音合成 ──
        # 限幅保护：确保两轨相加不削波
        master = vocal_processed + instr_mono.astype(np.float32)

        # 全局安全限幅
        peak = np.max(np.abs(master))
        if peak > 0.95:
            scale = 0.95 / peak
            master = master * scale
            print(f"[混音] 峰值 {peak:.3f} 超限，自动缩放至 {peak * scale:.3f}")
        else:
            print(f"[混音] 峰值 {peak:.3f} (安全)")

        # ── 10. 输出最终母带 ──
        os.makedirs(out_dir, exist_ok=True)
        sf.write(master_path, master, target_sr, subtype=TARGET_SUBTYPE)

        elapsed = time.time() - t0
        master_info = _inspect_wav(master_path)
        if not master_info.get("exists") or master_info.get("duration", 0.0) <= 0:
            raise RuntimeError(f"final_master.wav invalid or missing: {master_path}")
        if master_info.get("sample_rate") != target_sr:
            raise RuntimeError(
                f"final_master.wav sample_rate mismatch: "
                f"{master_info.get('sample_rate')} != {target_sr}"
            )
        duration = float(master_info["duration"])

        # ── 11. 状态 → 完成 ──
        update_task_status(task_id, STATUS_SUCCESS)

        print(f"[混音] 母带输出: {master_path}")
        print(f"[混音] 时长: {duration:.2f}s | 耗时: {elapsed:.2f}s")
        print(f"[混音] 格式: {target_sr}Hz / 16bit PCM WAV")

        return {
            "success": True,
            "output": master_path,
            "duration": duration,
            "elapsed": elapsed,
            "stats": {
                "vocal_samples": len(vocal_mono),
                "instr_samples": len(instr_mono),
                "peak_before_limit": float(peak),
                "sample_rate": target_sr,
                "format": TARGET_SUBTYPE,
                "master_info": master_info,
            },
        }

    except Exception as e:
        err = f"混音处理异常: {e}"
        print(f"[混音] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}


# ── 内部工具 ──────────────────────────────────────────


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """将音频统一为单声道"""
    if audio.ndim == 1:
        return audio.astype(np.float32)
    # 多声道 → 平均混合
    return np.mean(audio, axis=1).astype(np.float32)


def _get_wav_duration(path: str) -> float:
    """读取 WAV 时长"""
    try:
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate if rate else 0.0
    except Exception:
        return 0.0


def _inspect_wav(path: str) -> dict:
    """Return the minimal final-master contract used before artifact registration."""
    if not os.path.isfile(path):
        return {"exists": False, "duration": 0.0, "sample_rate": 0}

    with wave.open(path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return {
            "exists": True,
            "duration": frames / rate if rate else 0.0,
            "sample_rate": rate,
            "channels": wf.getnchannels(),
            "sample_width": wf.getsampwidth(),
            "frames": frames,
        }


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


# ── 冒烟测试 ──────────────────────────────────────────


def smoke_test():
    """
    第六轮冒烟测试：自动化大师混音模块

    复用前序任务 test_sep_001（状态应为"混音中"）
    验证:
      - 状态从 "混音中" → "完成"
      - final_master.wav 成功生成
      - DSP 链正常运行（Reverb + Compressor + Limiter）
    """
    from db import init_db, update_task_status

    print("=" * 60)
    print("  第六轮冒烟测试: 自动化大师混音模块")
    print("=" * 60)

    init_db()

    task_id = "test_sep_001"

    # 前置检查：关键文件
    out_dir = os.path.join(OUTPUT_ROOT, task_id)
    vocal_path = os.path.join(out_dir, "vocal_transformed.wav")
    instr_path = os.path.join(out_dir, "instrumental.wav")

    print(f"\n[测试] 输入文件检查:")
    for label, path in [("变声人声", vocal_path), ("原版伴奏", instr_path)]:
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        status = "OK" if exists else "MISSING"
        print(f"  {label}: {status} ({size:,} bytes)" if exists else f"  {label}: {status}")

    if not os.path.exists(vocal_path) or not os.path.exists(instr_path):
        print(f"\n[FAIL] 前置条件不满足，请先运行前序模块冒烟测试")
        return

    # 确保状态为"混音中"
    update_task_status(task_id, STATUS_MIXING)

    print(f"\n[测试] --- 混音前 ---")
    _print_task_status(task_id)

    print(f"\n[测试] ========== 开始大师混音 ==========")
    result = merge_master_audio(
        task_id,
        vocal_gain_db=0.0,
        instrumental_gain_db=0.0,
    )

    print(f"\n[测试] --- 混音后 ---")
    _print_task_status(task_id)

    # 结果报告
    print(f"\n[测试] 混音结果:")
    for k in ["success", "output", "duration", "elapsed"]:
        print(f"  {k:20s}: {result.get(k, 'N/A')}")
    if result.get("error"):
        print(f"  {'error':20s}: {result['error']}")
    if result.get("stats"):
        print(f"  DSP 统计:")
        for k, v in result["stats"].items():
            print(f"    {k:20s}: {v}")

    # 输出目录清单
    if os.path.exists(out_dir):
        print(f"\n[测试] 最终输出目录:")
        for f in sorted(os.listdir(out_dir)):
            fpath = os.path.join(out_dir, f)
            size = os.path.getsize(fpath)
            dur = _get_wav_duration(fpath) if f.endswith(".wav") else 0
            dur_str = f"{dur:.2f}s" if dur > 0 else ""
            marker = ""
            if f == "final_master.wav":
                marker = " <<< 终极母带"
            print(f"  {f:30s} ({size:>10,} bytes) {dur_str:>8s}{marker}")

    # 终极状态流转
    print(f"\n[测试] 完整状态流转:")
    print(f"  pending → 分离中 → 修音中 → 变声中 → 混音中 → 完成")

    # 最终判定
    final_ok = (
        result.get("success")
        and os.path.exists(os.path.join(out_dir, "final_master.wav"))
    )

    print(f"\n{'=' * 60}")
    if final_ok:
        print("  [OK] 第六轮冒烟测试通过 - 终极母带生成成功！")
        print("  [OK] 后台异步流水线全线合龙！")
    else:
        print(f"  [FAIL] 冒烟测试失败: {result.get('error')}")
    print("=" * 60)

    return final_ok


if __name__ == "__main__":
    smoke_test()
