import { getJSON, postForm, toErrorMessage } from "./api.js";
import { $, formatBytes, showToast } from "./ui.js";
import { summarizeTrainIssue } from "./diagnostics.js";

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
};

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
    note.textContent = `训练环境未通过：${summarizeTrainIssue({ train_preflight: preflight })}。${preflight.next_step || ""}`;
    note.className = "availability-note warn";
    return;
  }

  note.textContent = `${preflight.reason || "训练素材验收通过。"} 将进入 ${preflight.recommended_route || config.strategyLabel}。`;
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
  form.append("voice_name", voiceName);
  files.forEach(file => form.append("files", file));

  try {
    const created = await postForm("/api/train", form);
    const route = created.recommended_route || created.strategy_key || config.strategyLabel;
    showToast(`${config.entryLabel}任务已创建：${created.task_id} · ${route}`, "success");
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
  bindForm("single", onJobCreated);
  bindForm("multi", onJobCreated);
}

export async function syncTrainAvailability() {
  await Promise.all([refreshPreflight("single"), refreshPreflight("multi")]);
}
