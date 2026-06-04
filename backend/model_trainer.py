from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from random import shuffle

try:
    from .engine_paths import PROJECT_ROOT as ENGINE_PROJECT_ROOT, RVC_PYTHON, RVC_WEBUI_DIR
    from .services.training_tuning_service import build_rvc_train_runtime_options
except ImportError:
    from engine_paths import PROJECT_ROOT as ENGINE_PROJECT_ROOT, RVC_PYTHON, RVC_WEBUI_DIR
    from services.training_tuning_service import build_rvc_train_runtime_options


def _pick_first_existing(*paths: str) -> str:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return paths[0] if paths else ""


PROJECT_ROOT = str(ENGINE_PROJECT_ROOT)
DATASET_DIR = os.path.join(PROJECT_ROOT, "shared_data", "datasets")
WEIGHTS_DIR = os.path.join(PROJECT_ROOT, "shared_data", "weights")

_LEGACY_RVC_WEBUI_DIR_CANDIDATES = (
    os.path.join(PROJECT_ROOT, "external", "rvc-webui"),
    os.path.join(PROJECT_ROOT, "external", "rvc"),
    r"D:\RVC\RVCv2",
    r"D:\RVC\RVC",
    r"C:\Users\ASUS\WorkBuddy\20260427153731\RVC-WebUI",
)
RVC_CONFIGS_DIR = os.path.join(RVC_WEBUI_DIR, "configs", "inuse")
RVC_LOGS_DIR = os.path.join(RVC_WEBUI_DIR, "logs")
RVC_MUTE_DIR = os.path.join(RVC_WEBUI_DIR, "logs", "mute")

_LEGACY_RVC_PYTHON_CANDIDATES = (
    os.path.join(RVC_WEBUI_DIR, "runtime", "python.exe"),
    os.path.join(RVC_WEBUI_DIR, "venv", "Scripts", "python.exe"),
    os.path.join(PROJECT_ROOT, "external", "rvc-webui", "runtime", "python.exe"),
    r"D:\Miniconda3\envs\rvc\python.exe",
    sys.executable,
)

RVC_FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

TRAIN_SR = os.environ.get("FEISHARK_RVC_TRAIN_SR", "40k")
TRAIN_VERSION = os.environ.get("FEISHARK_RVC_TRAIN_VERSION", "v2")
TRAIN_EPOCHS = int(os.environ.get("FEISHARK_RVC_TRAIN_EPOCHS", "150"))
TRAIN_BATCH_SIZE = int(os.environ.get("FEISHARK_RVC_TRAIN_BATCH_SIZE", "8"))
TRAIN_GPUS = os.environ.get("FEISHARK_RVC_GPUS", "0")
TRAIN_PREPROCESS_THREADS = int(
    os.environ.get(
        "FEISHARK_RVC_PREPROCESS_THREADS",
        str(max(1, min((os.cpu_count() or 4), 8))),
    )
)
TRAIN_PREPROCESS_PER = os.environ.get("FEISHARK_RVC_PREPROCESS_PER", "3.7")
TRAIN_PITCH_GUIDE = os.environ.get("FEISHARK_RVC_TRAIN_PITCH_GUIDE", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SAVE_EVERY_EPOCH = int(os.environ.get("FEISHARK_RVC_SAVE_EVERY_EPOCH", "10"))
SAVE_EVERY_WEIGHTS = os.environ.get("FEISHARK_RVC_SAVE_EVERY_WEIGHTS", "1")
TRAIN_TIMEOUT = int(os.environ.get("FEISHARK_RVC_TRAIN_TIMEOUT", "21600"))
TRAIN_INDEX_TIMEOUT = int(os.environ.get("FEISHARK_RVC_INDEX_TIMEOUT", "1800"))
RVC_IS_HALF = os.environ.get("FEISHARK_RVC_IS_HALF", "False")
TRAIN_FP16_OVERRIDE = os.environ.get("FEISHARK_RVC_TRAIN_FP16", "").strip().lower()

SUPPORTED_AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

STATUS_SLICING = "切片中"
STATUS_TRAINING = "训练中"
STATUS_DONE = "完成"
STATUS_FAILED = "失败"


def start_voice_training(task_id: str, voice_name: str, input_audio_path: str) -> dict:
    try:
        from .db import create_train_task
    except ImportError:
        from db import create_train_task

    dataset_folder = os.path.join(DATASET_DIR, f"train_{uuid.uuid4().hex[:12]}")
    os.makedirs(dataset_folder, exist_ok=True)

    src_name = os.path.basename(input_audio_path)
    ext = os.path.splitext(src_name)[1].lower() or ".wav"
    if ext not in SUPPORTED_AUDIO_EXT:
        return {"success": False, "error": f"unsupported audio extension: {ext}"}

    dest_path = os.path.join(dataset_folder, f"0000_{Path(src_name).stem}{ext}")
    shutil.copy2(input_audio_path, dest_path)
    create_train_task(task_id, voice_name, os.path.relpath(dataset_folder, PROJECT_ROOT))
    return start_single_long_preprocess_training(task_id, voice_name, dataset_folder)


def start_single_long_preprocess_training(task_id: str, voice_name: str, dataset_folder: str) -> dict:
    return _run_dataset_training(task_id, voice_name, dataset_folder, strategy_mode="single_long_preprocess")


def start_multi_clean_direct_training(task_id: str, voice_name: str, dataset_folder: str) -> dict:
    return _run_dataset_training(task_id, voice_name, dataset_folder, strategy_mode="multi_clean_direct")


def start_voice_training_from_dataset(task_id: str, voice_name: str, dataset_folder: str) -> dict:
    source_files = _collect_audio_files(dataset_folder)
    if len(source_files) <= 1:
        return start_single_long_preprocess_training(task_id, voice_name, dataset_folder)
    return start_multi_clean_direct_training(task_id, voice_name, dataset_folder)


def _run_dataset_training(task_id: str, voice_name: str, dataset_folder: str, strategy_mode: str) -> dict:
    try:
        from .db import update_task_status
    except ImportError:
        from db import update_task_status

    t0 = time.time()
    model_id = f"v_{uuid.uuid4().hex[:8]}"

    if not os.path.isdir(dataset_folder):
        err = f"dataset directory missing: {dataset_folder}"
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    source_files = _collect_audio_files(dataset_folder)
    if not source_files:
        err = "dataset directory has no supported audio files"
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    exp_name = f"feishark_{model_id}"
    os.makedirs(os.path.join(RVC_LOGS_DIR, exp_name), exist_ok=True)
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    _ensure_rvc_training_support_files()

    update_task_status(task_id, STATUS_SLICING)
    try:
        if strategy_mode == "single_long_preprocess":
            slice_count = prepare_single_long_preprocess_dataset(dataset_folder, exp_name)
        elif strategy_mode == "multi_clean_direct":
            slice_count = prepare_multi_clean_direct_dataset(dataset_folder, exp_name)
        else:
            raise ValueError(f"unknown strategy_mode: {strategy_mode}")

        if slice_count <= 0:
            raise RuntimeError("training dataset is empty after preparation")

        update_task_status(task_id, STATUS_TRAINING)
        run_training_pitch_extract(exp_name)
        run_training_feature_extract(exp_name)
        run_training_core(exp_name)
        run_training_index(exp_name)
        pth_final, index_final = register_trained_model(exp_name, model_id, voice_name)
        update_task_status(task_id, STATUS_DONE)

        return {
            "success": True,
            "model_id": model_id,
            "model_name": voice_name,
            "elapsed": time.time() - t0,
            "slice_count": slice_count,
            "mode": strategy_mode,
            "pth_path": pth_final,
            "index_path": index_final,
        }
    except Exception as exc:
        err = str(exc)
        update_task_status(task_id, STATUS_FAILED, err[:500])
        return {"success": False, "error": err}


def prepare_single_long_preprocess_dataset(dataset_folder: str, exp_name: str, training_config: dict | None = None) -> int:
    _ensure_rvc_training_support_files()
    _run_native_preprocess(dataset_folder, exp_name, training_config=training_config)
    return _count_training_samples(exp_name)


def prepare_multi_clean_direct_dataset(dataset_folder: str, exp_name: str, training_config: dict | None = None) -> int:
    _ensure_rvc_training_support_files()
    source_files = _collect_audio_files(dataset_folder)
    if not source_files:
        raise RuntimeError("dataset directory has no supported audio files")
    _prepare_direct_trainset(source_files, exp_name, training_config=training_config)
    return _count_training_samples(exp_name)


def run_training_pitch_extract(exp_name: str, training_config: dict | None = None) -> None:
    _run_pitch_extraction(exp_name, training_config=training_config)


def run_training_feature_extract(exp_name: str, training_config: dict | None = None) -> None:
    _run_feature_extraction(exp_name)


def run_training_core(exp_name: str, training_config: dict | None = None) -> None:
    _prepare_rvc_experiment(exp_name, training_config=training_config)
    _run_training_script(exp_name, training_config=training_config)


def run_training_index(exp_name: str, training_config: dict | None = None) -> None:
    options = _runtime_options(training_config)
    if not options["index_enabled"]:
        return
    _run_index_extraction(exp_name)


def register_trained_model(
    exp_name: str,
    model_id: str,
    voice_name: str,
    source_job_id: str = "",
    *,
    training_config: dict | None = None,
) -> tuple[str, str]:
    try:
        from .db import add_voice_asset
        from .services.model_service import build_trained_model_metadata
    except ImportError:
        from db import add_voice_asset
        from services.model_service import build_trained_model_metadata

    options = _runtime_options(training_config)
    pth_final, index_final = _move_train_artifacts(
        exp_name,
        model_id,
        voice_name,
        require_index=options["index_enabled"],
    )
    add_voice_asset(
        model_id=model_id,
        model_name=voice_name,
        pth_path=pth_final,
        index_path=index_final,
        default_pitch=0,
        source_job_id=source_job_id,
        metadata=build_trained_model_metadata(source_job_id),
    )
    return pth_final, index_final


def _collect_audio_files(dataset_folder: str) -> list[str]:
    files = [
        os.path.join(dataset_folder, name)
        for name in sorted(os.listdir(dataset_folder))
        if os.path.splitext(name)[1].lower() in SUPPORTED_AUDIO_EXT
    ]
    return [path for path in files if os.path.isfile(path)]


def _run_native_preprocess(dataset_folder: str, exp_name: str, training_config: dict | None = None) -> None:
    options = _runtime_options(training_config)
    preprocess_script = os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "preprocess.py")
    if not os.path.exists(preprocess_script):
        raise FileNotFoundError(f"RVC preprocess script missing: {preprocess_script}")

    exp_dir = os.path.join(RVC_LOGS_DIR, exp_name)
    os.makedirs(exp_dir, exist_ok=True)
    cmd = [
        RVC_PYTHON,
        preprocess_script,
        dataset_folder,
        _sample_rate_hz(options),
        str(TRAIN_PREPROCESS_THREADS),
        exp_dir,
        "True",
        TRAIN_PREPROCESS_PER,
    ]
    _run_rvc_command(cmd, timeout=900, label="train/preprocess")


def _prepare_direct_trainset(source_files: list[str], exp_name: str, training_config: dict | None = None) -> None:
    options = _runtime_options(training_config)
    gt_dir, wav16k_dir = _ensure_train_dirs(exp_name)
    for index, src in enumerate(source_files):
        stem = f"{index:04d}_0"
        gt_path = os.path.join(gt_dir, f"{stem}.wav")
        wav16k_path = os.path.join(wav16k_dir, f"{stem}.wav")
        _run_rvc_command(
            [
                RVC_FFMPEG,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                src,
                "-ac",
                "1",
                "-ar",
                _sample_rate_hz(options),
                gt_path,
            ],
            timeout=600,
            label=f"train/direct40k/{index:04d}",
        )
        _run_rvc_command(
            [
                RVC_FFMPEG,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                src,
                "-ac",
                "1",
                "-ar",
                "16000",
                wav16k_path,
            ],
            timeout=600,
            label=f"train/direct16k/{index:04d}",
        )


def _ensure_train_dirs(exp_name: str) -> tuple[str, str]:
    exp_dir = os.path.join(RVC_LOGS_DIR, exp_name)
    gt_dir = os.path.join(exp_dir, "0_gt_wavs")
    wav16k_dir = os.path.join(exp_dir, "1_16k_wavs")
    os.makedirs(exp_dir, exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)
    os.makedirs(wav16k_dir, exist_ok=True)
    return gt_dir, wav16k_dir


def _count_training_samples(exp_name: str) -> int:
    gt_dir = os.path.join(RVC_LOGS_DIR, exp_name, "0_gt_wavs")
    if not os.path.isdir(gt_dir):
        return 0
    return sum(1 for name in os.listdir(gt_dir) if name.lower().endswith(".wav"))


def _run_pitch_extraction(exp_name: str, training_config: dict | None = None) -> None:
    options = _runtime_options(training_config)
    if not options["f0_enabled"]:
        return

    exp_dir = os.path.join(RVC_LOGS_DIR, exp_name)
    _run_rvc_command(
        [
            RVC_PYTHON,
            os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "extract", "extract_f0_rmvpe.py"),
            "1",
            "0",
            _pick_gpu_id(),
            exp_dir,
            RVC_IS_HALF,
        ],
        timeout=1200,
        label="train/pitch",
    )


def _run_feature_extraction(exp_name: str) -> None:
    exp_dir = os.path.join(RVC_LOGS_DIR, exp_name)
    _run_rvc_command(
        [
            RVC_PYTHON,
            os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "extract_feature_print.py"),
            "cuda" if _has_cuda() else "cpu",
            "1",
            "0",
            _pick_gpu_id(),
            exp_dir,
            TRAIN_VERSION,
            RVC_IS_HALF,
        ],
        timeout=1200,
        label="train/feature",
    )


def _prepare_rvc_experiment(exp_name: str, training_config: dict | None = None) -> None:
    options = _runtime_options(training_config)
    exp_dir = os.path.join(RVC_LOGS_DIR, exp_name)
    gt_wavs_dir = os.path.join(exp_dir, "0_gt_wavs")
    feature_dir = os.path.join(exp_dir, "3_feature768" if TRAIN_VERSION == "v2" else "3_feature256")
    f0_dir = os.path.join(exp_dir, "2a_f0")
    f0nsf_dir = os.path.join(exp_dir, "2b-f0nsf")
    filelist_path = os.path.join(exp_dir, "filelist.txt")

    if not os.path.isdir(gt_wavs_dir):
        raise FileNotFoundError(f"ground truth wav directory missing: {gt_wavs_dir}")
    if not os.path.isdir(feature_dir):
        raise FileNotFoundError(f"feature directory missing: {feature_dir}")

    entries: list[str] = []
    for wav_name in sorted(os.listdir(gt_wavs_dir)):
        if not wav_name.lower().endswith(".wav"):
            continue
        stem = os.path.splitext(wav_name)[0]
        wav_path = os.path.join(gt_wavs_dir, wav_name).replace("\\", "\\\\")
        feature_path = os.path.join(feature_dir, f"{stem}.npy").replace("\\", "\\\\")
        if options["f0_enabled"]:
            f0_path = os.path.join(f0_dir, f"{wav_name}.npy").replace("\\", "\\\\")
            f0nsf_path = os.path.join(f0nsf_dir, f"{wav_name}.npy").replace("\\", "\\\\")
            if not (os.path.exists(f0_path.replace("\\\\", "\\")) and os.path.exists(f0nsf_path.replace("\\\\", "\\"))):
                continue
            entries.append(f"{wav_path}|{feature_path}|{f0_path}|{f0nsf_path}|0")
        else:
            entries.append(f"{wav_path}|{feature_path}|0")

    if not entries:
        raise RuntimeError("training filelist is empty after preprocess/feature extraction")

    mute_sr = options["sample_rate"]
    mute_feature_dir = "3_feature768" if TRAIN_VERSION == "v2" else "3_feature256"
    for _ in range(2):
        if options["f0_enabled"]:
            entries.append(
                f"{os.path.join(RVC_MUTE_DIR, '0_gt_wavs', f'mute{mute_sr}.wav').replace('\\', '\\\\')}"
                f"|{os.path.join(RVC_MUTE_DIR, mute_feature_dir, 'mute.npy').replace('\\', '\\\\')}"
                f"|{os.path.join(RVC_MUTE_DIR, '2a_f0', 'mute.wav.npy').replace('\\', '\\\\')}"
                f"|{os.path.join(RVC_MUTE_DIR, '2b-f0nsf', 'mute.wav.npy').replace('\\', '\\\\')}"
                f"|0"
            )
        else:
            entries.append(
                f"{os.path.join(RVC_MUTE_DIR, '0_gt_wavs', f'mute{mute_sr}.wav').replace('\\', '\\\\')}"
                f"|{os.path.join(RVC_MUTE_DIR, mute_feature_dir, 'mute.npy').replace('\\', '\\\\')}"
                f"|0"
            )

    shuffle(entries)
    with open(filelist_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(entries))

    config_key = "v1/40k.json" if options["sample_rate"] == "40k" else f"{TRAIN_VERSION}/{options['sample_rate']}.json"
    config_src = os.path.join(RVC_CONFIGS_DIR, config_key.replace("/", os.sep))
    config_dest = os.path.join(exp_dir, "config.json")
    if not os.path.exists(config_src):
        raise FileNotFoundError(f"RVC config missing: {config_src}")
    if not os.path.exists(config_dest):
        with open(config_src, "r", encoding="utf-8") as src_handle:
            config_data = json.load(src_handle)
        if TRAIN_FP16_OVERRIDE in {"0", "false", "no", "off"}:
            config_data.setdefault("train", {})["fp16_run"] = False
        elif TRAIN_FP16_OVERRIDE in {"1", "true", "yes", "on"}:
            config_data.setdefault("train", {})["fp16_run"] = True
        with open(config_dest, "w", encoding="utf-8") as dst_handle:
            json.dump(config_data, dst_handle, ensure_ascii=False, indent=4, sort_keys=True)
            dst_handle.write("\n")


def _run_training_script(exp_name: str, training_config: dict | None = None) -> None:
    options = _runtime_options(training_config)
    train_script = os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "train.py")
    if not os.path.exists(train_script):
        raise FileNotFoundError(f"RVC train.py missing: {train_script}")

    cmd = [
        RVC_PYTHON,
        train_script,
        "-se",
        str(SAVE_EVERY_EPOCH),
        "-te",
        str(options["epochs"]),
        "-bs",
        str(options["batch_size"]),
        "-e",
        exp_name,
        "-sr",
        options["sample_rate"],
        "-v",
        TRAIN_VERSION,
        "-f0",
        "1" if options["f0_enabled"] else "0",
        "-l",
        "1",
        "-c",
        "0",
        "-sw",
        SAVE_EVERY_WEIGHTS,
    ]
    pretrain_g, pretrain_d = _get_pretrained_models(training_config=training_config)
    if pretrain_g:
        cmd.extend(["-pg", pretrain_g])
    if pretrain_d:
        cmd.extend(["-pd", pretrain_d])
    if TRAIN_GPUS:
        cmd.extend(["-g", TRAIN_GPUS])
    _run_rvc_command(
        cmd,
        timeout=TRAIN_TIMEOUT,
        label="train/core",
        success_codes={0, 2333333},
        exp_name=exp_name,
    )


def _run_index_extraction(exp_name: str) -> None:
    exp_dir = os.path.join(RVC_LOGS_DIR, exp_name)
    feature_dir = os.path.join(exp_dir, "3_feature768" if TRAIN_VERSION == "v2" else "3_feature256")
    if not os.path.isdir(feature_dir):
        raise FileNotFoundError(f"feature directory missing: {feature_dir}")

    script = """
import os
import shutil
import traceback

import faiss
import numpy as np
from sklearn.cluster import MiniBatchKMeans

exp_name = {exp_name}
exp_dir = {exp_dir}
feature_dir = {feature_dir}
version = {version}
dimension = 256 if version == "v1" else 768
outside_index_root = {outside_index_root}
os.makedirs(outside_index_root, exist_ok=True)

feature_files = [name for name in sorted(os.listdir(feature_dir)) if name.endswith(".npy")]
if not feature_files:
    raise RuntimeError("feature directory is empty")

npys = []
for name in feature_files:
    npys.append(np.load(os.path.join(feature_dir, name)))

big_npy = np.concatenate(npys, 0)
big_npy_idx = np.arange(big_npy.shape[0])
np.random.shuffle(big_npy_idx)
big_npy = big_npy[big_npy_idx]

if big_npy.shape[0] > 200000:
    try:
        big_npy = (
            MiniBatchKMeans(
                n_clusters=10000,
                verbose=False,
                batch_size=256 * (os.cpu_count() or 1),
                compute_labels=False,
                init="random",
            )
            .fit(big_npy)
            .cluster_centers_
        )
    except Exception:
        traceback.print_exc()

np.save(os.path.join(exp_dir, "total_fea.npy"), big_npy)
n_ivf = min(int(16 * np.sqrt(big_npy.shape[0])), big_npy.shape[0] // 39)
if n_ivf <= 0:
    raise RuntimeError("not enough features for index build: %s" % (big_npy.shape[0],))

index = faiss.index_factory(dimension, "IVF%s,Flat" % n_ivf)
index_ivf = faiss.extract_index_ivf(index)
index_ivf.nprobe = 1
index.train(big_npy)

trained_index_path = os.path.join(
    exp_dir,
    "trained_IVF%s_Flat_nprobe_%s_%s_%s.index" % (n_ivf, index_ivf.nprobe, exp_name, version),
)
added_index_path = os.path.join(
    exp_dir,
    "added_IVF%s_Flat_nprobe_%s_%s_%s.index" % (n_ivf, index_ivf.nprobe, exp_name, version),
)
faiss.write_index(index, trained_index_path)

batch_size_add = 8192
for i in range(0, big_npy.shape[0], batch_size_add):
    index.add(big_npy[i : i + batch_size_add])
faiss.write_index(index, added_index_path)

runtime_index_path = os.path.join(outside_index_root, "%s.index" % exp_name)
shutil.copy2(added_index_path, runtime_index_path)
print(added_index_path)
""".format(
        exp_name=json.dumps(exp_name),
        exp_dir=json.dumps(exp_dir),
        feature_dir=json.dumps(feature_dir),
        version=json.dumps(TRAIN_VERSION),
        outside_index_root=json.dumps(os.path.join(RVC_WEBUI_DIR, "assets", "indices")),
    )
    _run_rvc_command([RVC_PYTHON, "-c", script], timeout=TRAIN_INDEX_TIMEOUT, label="train/index")


def _move_train_artifacts(exp_name: str, model_id: str, voice_name: str, *, require_index: bool = True) -> tuple[str, str]:
    del model_id

    logs_dir = os.path.join(RVC_LOGS_DIR, exp_name)
    assets_weights_dir = os.path.join(RVC_WEBUI_DIR, "assets", "weights")
    assets_indices_dir = os.path.join(RVC_WEBUI_DIR, "assets", "indices")

    pth_candidates = [
        os.path.join(assets_weights_dir, f"{exp_name}.pth"),
        os.path.join(assets_weights_dir, f"{voice_name}.pth"),
        _find_first_artifact(logs_dir, ".pth", excluded_prefixes=("G_", "D_")),
    ]
    index_candidates = [
        os.path.join(assets_indices_dir, f"{exp_name}.index"),
        os.path.join(assets_indices_dir, f"{voice_name}.index"),
        _find_first_artifact(logs_dir, ".index"),
    ]

    pth_src = next((path for path in pth_candidates if path and os.path.exists(path)), None)
    index_src = next((path for path in index_candidates if path and os.path.exists(path)), None)

    if not pth_src:
        raise FileNotFoundError(f"trained .pth not found for experiment: {exp_name}")
    if require_index and not index_src:
        raise FileNotFoundError(f"trained .index not found for experiment: {exp_name}")
    if require_index and os.path.getsize(index_src) <= 12:
        raise RuntimeError(f"index artifact is still an empty shell: {index_src}")

    pth_dest = os.path.join(WEIGHTS_DIR, f"{voice_name}.pth")
    index_dest = os.path.join(WEIGHTS_DIR, f"{voice_name}.index")
    shutil.copy2(pth_src, pth_dest)
    if index_src:
        shutil.copy2(index_src, index_dest)

    _sync_artifact_to_rvc_runtime(pth_dest, os.path.join(RVC_WEBUI_DIR, "assets", "weights"))
    if index_src:
        _sync_artifact_to_rvc_runtime(index_dest, os.path.join(RVC_WEBUI_DIR, "assets", "indices"))

    return (
        f"shared_data/weights/{voice_name}.pth",
        f"shared_data/weights/{voice_name}.index" if index_src else "",
    )


def _find_first_artifact(root: str, suffix: str, excluded_prefixes: tuple[str, ...] = ()) -> str | None:
    if not os.path.isdir(root):
        return None
    for name in os.listdir(root):
        if not name.endswith(suffix):
            continue
        if any(name.startswith(prefix) for prefix in excluded_prefixes):
            continue
        return os.path.join(root, name)
    for base, _, files in os.walk(root):
        for name in files:
            if not name.endswith(suffix):
                continue
            if any(name.startswith(prefix) for prefix in excluded_prefixes):
                continue
            return os.path.join(base, name)
    return None


def _get_pretrained_models(training_config: dict | None = None) -> tuple[str, str]:
    options = _runtime_options(training_config)
    path_suffix = "" if TRAIN_VERSION == "v1" else "_v2"
    f0_prefix = "f0" if options["f0_enabled"] else ""
    g_path = os.path.join(RVC_WEBUI_DIR, "assets", f"pretrained{path_suffix}", f"{f0_prefix}G{options['sample_rate']}.pth")
    d_path = os.path.join(RVC_WEBUI_DIR, "assets", f"pretrained{path_suffix}", f"{f0_prefix}D{options['sample_rate']}.pth")
    return (g_path if os.path.exists(g_path) else "", d_path if os.path.exists(d_path) else "")


def build_training_command_preview(exp_name: str, training_config: dict | None = None) -> dict:
    options = _runtime_options(training_config)
    train_script = os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "train.py")
    cmd = [
        RVC_PYTHON,
        train_script,
        "-se",
        str(SAVE_EVERY_EPOCH),
        "-te",
        str(options["epochs"]),
        "-bs",
        str(options["batch_size"]),
        "-e",
        exp_name,
        "-sr",
        options["sample_rate"],
        "-v",
        TRAIN_VERSION,
        "-f0",
        "1" if options["f0_enabled"] else "0",
        "-l",
        "1",
        "-c",
        "0",
        "-sw",
        SAVE_EVERY_WEIGHTS,
    ]
    pretrain_g, pretrain_d = _get_pretrained_models(training_config=training_config)
    if pretrain_g:
        cmd.extend(["-pg", pretrain_g])
    if pretrain_d:
        cmd.extend(["-pd", pretrain_d])
    if TRAIN_GPUS:
        cmd.extend(["-g", TRAIN_GPUS])
    return {
        "exp_name": exp_name,
        "cmd": cmd,
        "training_config": options["training_config"],
        "epochs": options["epochs"],
        "batch_size": options["batch_size"],
        "sample_rate": options["sample_rate"],
        "f0_enabled": options["f0_enabled"],
        "index_enabled": options["index_enabled"],
        "starts_train_py": False,
    }


def _runtime_options(training_config: dict | None = None) -> dict:
    try:
        return build_rvc_train_runtime_options(training_config or {})
    except ValueError as exc:
        options = build_rvc_train_runtime_options({"preset_key": "balanced"})
        options["training_config"].setdefault("warnings", []).append(f"invalid runtime training_config fallback: {exc}")
        return options


def _sample_rate_hz(options: dict) -> str:
    return str(options["sample_rate"]).replace("k", "000")


def _run_rvc_command(
    cmd: list[str],
    timeout: int,
    label: str,
    success_codes: set[int] | None = None,
    exp_name: str = "",
) -> None:
    print(f"[{label}] {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    python_path_parts = [RVC_WEBUI_DIR]
    if env.get("PYTHONPATH"):
        python_path_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path_parts)

    try:
        proc = subprocess.run(
            cmd,
            cwd=RVC_WEBUI_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        if label == "train/core":
            try:
                from .services.training_runtime_guard import build_train_core_timeout_error, inspect_training_checkpoint
            except ImportError:
                from services.training_runtime_guard import build_train_core_timeout_error, inspect_training_checkpoint

            raw_error = "\n".join(
                part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part or "")
                for part in (exc.stderr, exc.stdout)
                if part
            )
            raise build_train_core_timeout_error(
                exp_name=exp_name,
                timeout_seconds=timeout,
                cmd=cmd,
                raw_error=raw_error,
                checkpoint=inspect_training_checkpoint(
                    exp_name,
                    rvc_logs_dir=RVC_LOGS_DIR,
                    rvc_webui_dir=RVC_WEBUI_DIR,
                    train_version=TRAIN_VERSION,
                ),
            ) from exc
        raise
    allowed = success_codes or {0}
    if proc.returncode not in allowed:
        detail = (proc.stderr or "")[-5000:] or (proc.stdout or "")[-5000:] or f"{label} failed with exit code {proc.returncode}"
        raise RuntimeError(detail)


def _pick_gpu_id() -> str:
    if TRAIN_GPUS:
        return TRAIN_GPUS.split("-")[0]
    return "0"


def _has_cuda() -> bool:
    try:
        from .services.training_gpu_service import get_training_gpu_status
    except ImportError:
        try:
            from services.training_gpu_service import get_training_gpu_status
        except ImportError:
            return shutil.which("nvidia-smi") is not None

    try:
        status = get_training_gpu_status(
            rvc_python=RVC_PYTHON,
            rvc_webui_dir=RVC_WEBUI_DIR,
            train_gpus=TRAIN_GPUS,
            timeout=20,
        )
        return bool(status.get("acceleration_available"))
    except Exception:
        return shutil.which("nvidia-smi") is not None


def _ensure_rvc_training_support_files() -> None:
    _ensure_runtime_file(
        os.path.join(RVC_WEBUI_DIR, "assets", "hubert", "hubert_base.pt"),
        os.path.join(RVC_WEBUI_DIR, "assets", "pretrained", "hubert_base.pt"),
    )
    _ensure_runtime_file(
        os.path.join(RVC_WEBUI_DIR, "assets", "rmvpe", "rmvpe.pt"),
        os.path.join(RVC_WEBUI_DIR, "assets", "pretrained", "rmvpe.pt"),
    )


def _ensure_runtime_file(target_path: str, fallback_path: str) -> None:
    if os.path.exists(target_path):
        return
    if not os.path.exists(fallback_path):
        return
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    shutil.copy2(fallback_path, target_path)


def _sync_artifact_to_rvc_runtime(source_path: str, runtime_dir: str) -> None:
    if not source_path or not os.path.exists(source_path):
        return
    os.makedirs(runtime_dir, exist_ok=True)
    target_path = os.path.join(runtime_dir, os.path.basename(source_path))
    if os.path.abspath(source_path) == os.path.abspath(target_path):
        return
    shutil.copy2(source_path, target_path)


def smoke_test() -> None:
    print("[train] rvc_root =", RVC_WEBUI_DIR)
    print("[train] python =", RVC_PYTHON)


if __name__ == "__main__":
    smoke_test()
