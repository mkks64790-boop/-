import { getJSON, postForm, toErrorMessage } from "./api.js";
import { $, formatBytes, showToast } from "./ui.js";
import { summarizeTrainIssue } from "./diagnostics.js";

const FORM_CONFIGS = {
  single: {
    fileCount: 1,
    formId: "singleTrainCreateForm",
    voiceId: "singleTrainVoiceNameInput",
    fileId: "singleTrainFileInput",
    hintId: "singleTrainFileHint",
    modeId: "singleTrainModeChip",
    noteId: "singleTrainAvailabilityNote",
    buttonId: "singleTrainCreateBtn",
    entryLabel: "单文件训练",
    strategyLabel: "single_long_preprocess",
  },
  multi: {
    fileCount: 2,
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
  single: { files: [], preflight: null },
  multi: { files: [], preflight: null },
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

function updateFileHint(kind) {
  const config = FORM_CONFIGS[kind];
  const files = getFiles(kind);
  const hint = $(config.hintId);

  if (!files.length) {
    hint.textContent = "尚未选择训练文件。";
    return;
  }

  const total = files.reduce((sum, file) => sum + file.size, 0);
  hint.textContent = `已选择 ${files.length} 个文件 · ${formatBytes(total)}`;
}

function updateModeChip(kind) {
  const config = FORM_CONFIGS[kind];
  const files = getFiles(kind);
  const chip = $(config.modeId);

  if (!files.length) {
    chip.textContent = "等待选择文件";
    return;
  }

  chip.textContent = `当前模式：${config.strategyLabel}`;
}

function renderAvailability(kind) {
  const config = FORM_CONFIGS[kind];
  const files = getFiles(kind);
  const voiceName = getVoiceValue(kind);
  const preflight = getFormState(kind).preflight;
  const note = $(config.noteId);
  const button = $(config.buttonId);

  const missingBasics = !voiceName || !files.length;
  button.disabled = missingBasics;

  if (!files.length) {
    note.textContent = "先选择训练文件，再查看训练预检结果。";
    note.className = "availability-note";
    return;
  }

  if (!voiceName) {
    note.textContent = "先填写音色名称，再创建训练任务。";
    note.className = "availability-note warn";
    return;
  }

  if (!preflight) {
    note.textContent = "正在检查训练环境，请稍候。";
    note.className = "availability-note";
    return;
  }

  if (preflight.ok) {
    note.textContent = `预检通过，创建后将按 ${config.strategyLabel} 进入队列。`;
    note.className = "availability-note success";
    return;
  }

  const first = preflight.errors?.[0];
  note.textContent = `当前可以提交，但大概率会失败：${summarizeTrainIssue({ train_preflight: preflight })}。${first?.next_step || ""}`;
  note.className = "availability-note warn";
}

async function refreshPreflight(kind) {
  const config = FORM_CONFIGS[kind];
  try {
    getFormState(kind).preflight = await getJSON(`/api/preflight/train?file_count=${config.fileCount}`);
  } catch (error) {
    getFormState(kind).preflight = {
      ok: false,
      errors: [{ check: "network", detail: toErrorMessage(error), next_step: "请稍后重试，或查看诊断面板。" }],
    };
  }
  renderAvailability(kind);
}

async function handleSubmit(kind, onJobCreated) {
  const config = FORM_CONFIGS[kind];
  const voiceName = getVoiceValue(kind);
  const files = getFiles(kind);

  if (!voiceName || !files.length) {
    showToast(`请先完成 ${config.entryLabel} 所需的文件和名称选择。`, "error");
    return;
  }

  const form = new FormData();
  form.append("voice_name", voiceName);
  files.forEach(file => form.append("files", file));

  try {
    const created = await postForm("/api/train", form);
    showToast(`${config.entryLabel}任务已创建：${created.task_id}`, "success");
    onJobCreated?.(created.task_id);
  } catch (error) {
    showToast(`${config.entryLabel}创建失败：${toErrorMessage(error)}`, "error");
  }
}

function bindForm(kind, onJobCreated) {
  const config = FORM_CONFIGS[kind];

  $(config.voiceId).addEventListener("input", () => renderAvailability(kind));
  $(config.fileId).addEventListener("change", async event => {
    const files = Array.from(event.target.files || []);
    getFormState(kind).files = kind === "single" ? files.slice(0, 1) : files;
    updateFileHint(kind);
    updateModeChip(kind);
    renderAvailability(kind);
    await refreshPreflight(kind);
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
