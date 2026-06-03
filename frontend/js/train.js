import { getJSON, postForm, toErrorMessage } from "./api.js";
import { $, formatBytes, showToast } from "./ui.js";
import { summarizeTrainIssue } from "./diagnostics.js";

const TRAINING_PRESET_STORAGE_KEY = "feishark.training-preset-key";
const TRAINING_PRESET_ORDER = ["fast_preview", "balanced", "quality"];
const TRAINING_PRESET_FALLBACKS = {
  fast_preview: {
    preset_key: "fast_preview",
    label: "快速预览",
    epochs: 30,
    batch_size: 6,
    sample_rate: "40k",
    f0_enabled: true,
    index_enabled: true,
    gpu_risk_label: "低",
    estimated_runtime_label: "较短，适合先确认音色方向",
  },
  balanced: {
    preset_key: "balanced",
    label: "均衡推荐",
    epochs: 90,
    batch_size: 8,
    sample_rate: "40k",
    f0_enabled: true,
    index_enabled: true,
    gpu_risk_label: "中",
    estimated_runtime_label: "中等，适合大多数本地训练",
  },
  quality: {
    preset_key: "quality",
    label: "高质量慢速",
    epochs: 150,
    batch_size: 6,
    sample_rate: "40k",
    f0_enabled: true,
    index_enabled: true,
    gpu_risk_label: "高",
    estimated_runtime_label: "较长，请确认 GPU 空闲和散热稳定",
  },
};

const FORM_CONFIGS = {
  single: {
    defaultFileCount: 1,
    formId: "singleTrainCreateForm",
    voiceId: "singleTrainVoiceNameInput",
    fileId: "singleTrainFileInput",
    hintId: "singleTrainFileHint",
    modeId: "singleTrainModeChip",
    noteId: "singleTrainAvailabilityNote",
    buttonId: "singleTrainCreateBtn",
    entryLabel: "单文件快速训练",
    strategyLabel: "single_long_preprocess",
  },
  multi: {
    defaultFileCount: 2,
    formId: "multiTrainCreateForm",
    voiceId: "multiTrainVoiceNameInput",
    fileId: "multiTrainFilesInput",
    hintId: "multiTrainFilesHint",
    modeId: "multiTrainModeChip",
    noteId: "multiTrainAvailabilityNote",
    buttonId: "multiTrainCreateBtn",
    entryLabel: "多文件精训",
    strategyLabel: "multi_clean_direct",
  },
};

const state = {
  single: { files: [], preflight: null, preview: null, loading: false },
  multi: { files: [], preflight: null, preview: null, loading: false },
  presets: Object.values(TRAINING_PRESET_FALLBACKS),
  selectedPresetKey: "balanced",
  presetsUnavailable: "",
};

function normalizePreset(raw = {}) {
  const key = raw.preset_key || raw.key || raw.name || "";
  return {
    ...raw,
    preset_key: key,
    label: raw.label || TRAINING_PRESET_FALLBACKS[key]?.label || key || "训练预设",
    epochs: raw.epochs ?? TRAINING_PRESET_FALLBACKS[key]?.epochs ?? 90,
    batch_size: raw.batch_size ?? TRAINING_PRESET_FALLBACKS[key]?.batch_size ?? 8,
    sample_rate: raw.sample_rate ?? TRAINING_PRESET_FALLBACKS[key]?.sample_rate ?? "40k",
    f0_enabled: raw.f0_enabled ?? raw.f0 ?? TRAINING_PRESET_FALLBACKS[key]?.f0_enabled ?? true,
    index_enabled: raw.index_enabled ?? raw.index ?? TRAINING_PRESET_FALLBACKS[key]?.index_enabled ?? true,
    gpu_risk_label: raw.gpu_risk_label || raw.gpu_risk || TRAINING_PRESET_FALLBACKS[key]?.gpu_risk_label || "中",
    estimated_runtime_label: raw.estimated_runtime_label || raw.estimated_runtime || TRAINING_PRESET_FALLBACKS[key]?.estimated_runtime_label || "中等",
  };
}

function normalizePresetPayload(payload = null) {
  const items = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.presets)
        ? payload.presets
        : [];
  const normalized = items.map(normalizePreset).filter(item => item.preset_key);
  const byKey = new Map(Object.values(TRAINING_PRESET_FALLBACKS).map(item => [item.preset_key, normalizePreset(item)]));
  normalized.forEach(item => byKey.set(item.preset_key, item));
  return TRAINING_PRESET_ORDER.map(key => byKey.get(key)).filter(Boolean);
}

function getStoredPresetKey() {
  try {
    const value = window.localStorage.getItem(TRAINING_PRESET_STORAGE_KEY);
    return TRAINING_PRESET_ORDER.includes(value) ? value : "balanced";
  } catch {
    return "balanced";
  }
}

function savePresetKey(key) {
  state.selectedPresetKey = TRAINING_PRESET_ORDER.includes(key) ? key : "balanced";
  try {
    window.localStorage.setItem(TRAINING_PRESET_STORAGE_KEY, state.selectedPresetKey);
  } catch {
    // Ignore storage failures.
  }
}

function getSelectedPreset() {
  return state.presets.find(item => item.preset_key === state.selectedPresetKey)
    || TRAINING_PRESET_FALLBACKS.balanced;
}

function buildTrainingConfig(kind) {
  const preset = getSelectedPreset();
  return {
    preset_key: preset.preset_key,
    epochs: Number(preset.epochs),
    batch_size: Number(preset.batch_size),
    sample_rate: String(preset.sample_rate || "40k"),
    f0_enabled: Boolean(preset.f0_enabled),
    index_enabled: Boolean(preset.index_enabled),
    gpu_risk_label: preset.gpu_risk_label || "中",
    estimated_runtime_label: preset.estimated_runtime_label || "中等",
    source: "product_ui",
    entry_kind: kind,
  };
}

function gpuStatusLabel(preflight = null) {
  const status = preflight?.gpu_status || preflight || null;
  if (!status) return "GPU 加速: 等待训练预检";
  const available = status.gpu_acceleration_available ?? status.acceleration_available ?? preflight?.gpu_acceleration_available;
  const deviceMode = status.device_mode || preflight?.device_mode || "";
  const devices = status.torch_cuda?.devices || status.nvidia_smi?.gpus?.map(item => item.name) || [];
  if (available) {
    return `GPU 加速: 可用 (${deviceMode || "cuda"}${devices.length ? ` · ${devices[0]}` : ""})`;
  }
  const firstError = (status.errors || preflight?.errors || []).find(item => item.check?.startsWith?.("train_gpu"))
    || (status.errors || preflight?.errors || [])[0]
    || null;
  return `GPU 加速: 未就绪${firstError?.detail ? ` · ${firstError.detail}` : ""}`;
}

function trainingConfigSummary(config, preflight = null) {
  return [
    `Preset: ${config.preset_key}`,
    `Epochs: ${config.epochs}`,
    `Batch: ${config.batch_size}`,
    `Sample Rate: ${config.sample_rate}`,
    `F0: ${config.f0_enabled ? "on" : "off"}`,
    `Index: ${config.index_enabled ? "on" : "off"}`,
    `GPU 风险: ${config.gpu_risk_label}`,
    gpuStatusLabel(preflight),
    `预计耗时: ${config.estimated_runtime_label}`,
  ].join("\n");
}

function renderDashboardTrainingPresetSummary() {
  const root = $("dashboardTrainingPresetSummary");
  if (!root) return;
  const config = buildTrainingConfig("dashboard");
  root.innerHTML = `
    <div class="training-config-summary-compact">
      <div>
        <strong>${config.preset_key}</strong>
        <span>${config.epochs} epochs · batch ${config.batch_size} · ${config.sample_rate} · GPU ${config.gpu_risk_label}</span>
      </div>
      <a class="ghost-btn drawer-toggle-btn" href="/factory#factoryTrainingTuningPanel">去 Factory 调参</a>
    </div>
    ${state.presetsUnavailable ? `<div class="training-config-note">${state.presetsUnavailable}</div>` : ""}
  `;
}

async function loadTrainingPresets() {
  state.selectedPresetKey = getStoredPresetKey();
  try {
    const payload = await getJSON("/api/training/presets");
    state.presets = normalizePresetPayload(payload);
    state.presetsUnavailable = "";
  } catch (error) {
    state.presets = Object.values(TRAINING_PRESET_FALLBACKS).map(normalizePreset);
    state.presetsUnavailable = "训练预设接口暂不可用，当前使用产品侧默认配置。";
  }
  if (!state.presets.some(item => item.preset_key === state.selectedPresetKey)) {
    savePresetKey("balanced");
  }
  renderDashboardTrainingPresetSummary();
}

function getFormState(kind) {
  return state[kind];
}

function getVoiceValue(kind) {
  return $(FORM_CONFIGS[kind].voiceId).value.trim();
}

function getFiles(kind) {
  return getFormState(kind).files;
}

function formatDurationLabel(seconds) {
  if (!Number.isFinite(seconds)) return "";
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) return `${hours}小时${minutes}分${secs}秒`;
  if (minutes > 0) return `${minutes}分${secs}秒`;
  return `${secs}秒`;
}

function readAudioDuration(file) {
  return new Promise((resolve, reject) => {
    const audio = document.createElement("audio");
    const objectUrl = URL.createObjectURL(file);
    const cleanup = () => {
      audio.removeAttribute("src");
      audio.load();
      URL.revokeObjectURL(objectUrl);
    };

    audio.preload = "metadata";
    audio.onloadedmetadata = () => {
      const duration = Number.isFinite(audio.duration) ? audio.duration : null;
      cleanup();
      resolve(duration);
    };
    audio.onerror = () => {
      cleanup();
      reject(new Error("音频时长读取失败"));
    };
    audio.src = objectUrl;
  });
}

async function buildSinglePreview(file) {
  let durationSeconds = null;
  try {
    durationSeconds = await readAudioDuration(file);
  } catch {
    durationSeconds = null;
  }
  return {
    fileName: file.name,
    fileSize: file.size,
    mimeType: file.type || "",
    durationSeconds,
    durationLabel: formatDurationLabel(durationSeconds),
  };
}

function buildMultiPreview(files) {
  return {
    fileCount: files.length,
    totalBytes: files.reduce((sum, file) => sum + file.size, 0),
  };
}

function updateFileHint(kind) {
  const config = FORM_CONFIGS[kind];
  const formState = getFormState(kind);
  const files = formState.files;
  const hint = $(config.hintId);

  if (!files.length) {
    hint.textContent = "尚未选择训练文件。";
    return;
  }

  if (kind === "single") {
    const [file] = files;
    const preview = formState.preview;
    const parts = [file.name, formatBytes(file.size)];
    if (preview?.durationLabel) {
      parts.push(preview.durationLabel);
    } else if (formState.loading) {
      parts.push("正在识别时长");
    } else {
      parts.push("时长待识别");
    }
    hint.textContent = parts.join(" · ");
    return;
  }

  const total = files.reduce((sum, file) => sum + file.size, 0);
  hint.textContent = `已选择 ${files.length} 个文件 · ${formatBytes(total)}`;
}

function updateModeChip(kind) {
  const config = FORM_CONFIGS[kind];
  const files = getFiles(kind);
  const preflight = getFormState(kind).preflight;
  const chip = $(config.modeId);

  if (!files.length) {
    chip.textContent = "等待选择文件";
    return;
  }

  const route = preflight?.recommended_route || config.strategyLabel;
  if (kind === "single" && preflight?.single_long_eligible === false) {
    chip.textContent = `建议改走：${route}`;
    return;
  }

  chip.textContent = `建议链路：${route}`;
}

function renderAvailability(kind) {
  const config = FORM_CONFIGS[kind];
  const formState = getFormState(kind);
  const files = formState.files;
  const voiceName = getVoiceValue(kind);
  const preflight = formState.preflight;
  const note = $(config.noteId);
  const button = $(config.buttonId);

  let canSubmit = Boolean(voiceName && files.length);
  if (formState.loading) canSubmit = false;

  if (preflight && (preflight.submission_allowed === false || preflight.ok === false)) {
    canSubmit = false;
  }
  button.disabled = !canSubmit;

  if (!files.length) {
    if (preflight?.ok) {
      note.textContent = "训练环境已就绪，先选择文件和音色名称。";
      note.className = "availability-note train";
      return;
    }
    if (preflight) {
      note.textContent = `训练环境未通过：${summarizeTrainIssue({ train_preflight: preflight })}。`;
      note.className = "availability-note warn";
      return;
    }
    note.textContent = "先选择训练文件，再查看素材分流结果。";
    note.className = "availability-note";
    return;
  }

  if (!voiceName) {
    note.textContent = "先填写音色名称，再创建训练任务。";
    note.className = "availability-note warn";
    return;
  }

  if (formState.loading) {
    note.textContent = "正在识别音频时长与训练路线，请稍候。";
    note.className = "availability-note";
    return;
  }

  if (!preflight) {
    note.textContent = "正在检查训练环境，请稍候。";
    note.className = "availability-note";
    return;
  }

  if (preflight.submission_allowed === false) {
    note.textContent = `${preflight.reason || "当前素材不适合这个训练入口。"} ${preflight.next_step || ""}`.trim();
    note.className = "availability-note warn";
    return;
  }

  if (!preflight.ok) {
    note.textContent = `训练环境未通过：${summarizeTrainIssue({ train_preflight: preflight })}。${gpuStatusLabel(preflight)}。${preflight.next_step || ""}`;
    note.className = "availability-note warn";
    return;
  }

  note.textContent = `${preflight.reason || "训练素材验收通过。"} ${gpuStatusLabel(preflight)}。将进入 ${preflight.recommended_route || config.strategyLabel}。`;
  note.className = "availability-note success";
}

async function refreshPreflight(kind) {
  const config = FORM_CONFIGS[kind];
  const formState = getFormState(kind);
  const files = formState.files;
  const preview = formState.preview;
  const params = new URLSearchParams();

  params.set("file_count", String(files.length || config.defaultFileCount));
  if (kind === "single" && preview?.durationSeconds != null) {
    params.set("duration_seconds", String(preview.durationSeconds));
    params.set("file_name", preview.fileName || "");
    params.set("file_size", String(preview.fileSize || 0));
    params.set("mime_type", preview.mimeType || "");
  }

  try {
    formState.preflight = await getJSON(`/api/preflight/train?${params.toString()}`);
  } catch (error) {
    formState.preflight = {
      ok: false,
      submission_allowed: false,
      recommended_route: config.strategyLabel,
      reason: "训练预检请求失败。",
      next_step: "请稍后重试，或查看诊断面板。",
      errors: [{ check: "network", detail: toErrorMessage(error), next_step: "请稍后重试。" }],
    };
  }

  updateModeChip(kind);
  renderAvailability(kind);
}

async function handleSubmit(kind, onJobCreated) {
  const config = FORM_CONFIGS[kind];
  const formState = getFormState(kind);
  const voiceName = getVoiceValue(kind);
  const files = getFiles(kind);

  if (!voiceName || !files.length) {
    showToast(`请先完成 ${config.entryLabel} 所需的文件和名称选择。`, "error");
    return;
  }
  if (formState.loading) {
    showToast("正在识别素材时长，请稍候再提交。", "error");
    return;
  }
  if (formState.preflight?.submission_allowed === false) {
    showToast(`${formState.preflight.reason || "当前素材不符合训练入口要求。"} ${formState.preflight.next_step || ""}`.trim(), "error");
    return;
  }
  if (formState.preflight && formState.preflight.ok === false) {
    showToast(`训练环境未通过：${summarizeTrainIssue({ train_preflight: formState.preflight })}`, "error");
    return;
  }

  const form = new FormData();
  const trainingConfig = buildTrainingConfig(kind);
  const confirmed = window.confirm(`确认创建训练任务？\n\n${trainingConfigSummary(trainingConfig, formState.preflight)}\n\n这会提交训练 job，但不会自动提交 cover。`);
  if (!confirmed) return;

  form.append("voice_name", voiceName);
  form.append("training_config_json", JSON.stringify(trainingConfig));
  form.append("training_config", JSON.stringify(trainingConfig));
  form.append("preset_key", trainingConfig.preset_key);
  files.forEach(file => form.append("files", file));

  try {
    const created = await postForm("/api/train", form);
    const route = created.recommended_route || created.strategy_key || config.strategyLabel;
    showToast(
      `训练已启动：${created.task_id} · ${route}。核心训练阶段可能较久，请不要关闭 RVC / 后端 / 当前训练进程；可在任务详情查看阶段路线图。`,
      "success",
    );
    onJobCreated?.(created.task_id);
  } catch (error) {
    showToast(`${config.entryLabel}创建失败：${toErrorMessage(error)}`, "error");
  }
}

async function handleFileChange(kind, event) {
  const formState = getFormState(kind);
  const files = Array.from(event.target.files || []);
  formState.files = kind === "single" ? files.slice(0, 1) : files;
  formState.preview = null;
  formState.preflight = null;
  formState.loading = false;

  updateFileHint(kind);
  updateModeChip(kind);
  renderAvailability(kind);

  if (!formState.files.length) {
    await refreshPreflight(kind);
    return;
  }

  if (kind === "single") {
    formState.loading = true;
    updateFileHint(kind);
    renderAvailability(kind);
    formState.preview = await buildSinglePreview(formState.files[0]);
    formState.loading = false;
  } else {
    formState.preview = buildMultiPreview(formState.files);
  }

  updateFileHint(kind);
  await refreshPreflight(kind);
}

function bindForm(kind, onJobCreated) {
  const config = FORM_CONFIGS[kind];

  $(config.voiceId).addEventListener("input", () => renderAvailability(kind));
  $(config.fileId).addEventListener("change", event => {
    void handleFileChange(kind, event);
  });

  $(config.formId).addEventListener("submit", async event => {
    event.preventDefault();
    await handleSubmit(kind, onJobCreated);
  });
}

export function initTrainCreate(onJobCreated) {
  $("singleTrainCreateForm")?.closest(".entry-card")?.querySelector("h3")?.replaceChildren("单文件快速训练");
  $("multiTrainCreateForm")?.closest(".entry-card")?.querySelector("h3")?.replaceChildren("多文件批量精训");
  $("singleTrainCreateBtn").textContent = "创建单文件快速训练";
  $("multiTrainCreateBtn").textContent = "创建多文件批量精训";

  void loadTrainingPresets();
  bindForm("single", onJobCreated);
  bindForm("multi", onJobCreated);
  window.addEventListener("storage", event => {
    if (event.key === TRAINING_PRESET_STORAGE_KEY) {
      state.selectedPresetKey = getStoredPresetKey();
      renderDashboardTrainingPresetSummary();
    }
  });
  document.addEventListener("feishark:training-preset-changed", () => {
    state.selectedPresetKey = getStoredPresetKey();
    renderDashboardTrainingPresetSummary();
  });
}

export async function syncTrainAvailability() {
  await Promise.all([refreshPreflight("single"), refreshPreflight("multi")]);
}
