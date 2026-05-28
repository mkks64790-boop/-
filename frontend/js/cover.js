import { postForm, request, toErrorMessage } from "./api.js";
import { $, formatBytes, showToast } from "./ui.js";
import { summarizeCoverIssue } from "./diagnostics.js";

let coverFile = null;
let availability = {
  usableModelCount: 0,
  coverPreflightOk: false,
  reason: "正在等待诊断结果...",
};

function refreshCoverState() {
  const selectedModelId = $("coverModelSelect").value;
  const ready = Boolean(coverFile) && Boolean(selectedModelId) && availability.usableModelCount > 0 && availability.coverPreflightOk;
  const button = $("coverCreateBtn");
  const note = $("coverAvailabilityNote");

  button.disabled = !ready;
  note.textContent = availability.reason;
  note.className = `availability-note ${ready ? "success" : availability.usableModelCount > 0 ? "warn" : "danger"}`;
}

export function initCoverCreate(onJobCreated) {
  $("coverFileInput").addEventListener("change", event => {
    coverFile = event.target.files?.[0] || null;
    $("coverFileHint").textContent = coverFile
      ? `${coverFile.name} · ${formatBytes(coverFile.size)}`
      : "尚未选择歌曲文件。";
    refreshCoverState();
  });

  $("coverModelSelect").addEventListener("change", refreshCoverState);

  $("coverCreateForm").addEventListener("submit", async event => {
    event.preventDefault();

    if (!coverFile) {
      showToast("请先选择歌曲文件。", "error");
      return;
    }

    try {
      const upload = new FormData();
      upload.append("file", coverFile);
      const created = await postForm("/api/upload_task", upload);
      const modelId = $("coverModelSelect").value;
      await request(`/api/process/${created.task_id}?model_id=${encodeURIComponent(modelId)}`, { method: "POST" });
      showToast(`Cover 任务已创建：${created.task_id}`, "success");
      onJobCreated?.(created.task_id);
    } catch (error) {
      showToast(`Cover 任务创建失败：${toErrorMessage(error)}`, "error");
    }
  });
}

export function syncCoverAvailability(diagnosticsState, modelsState) {
  const usableModelCount = modelsState?.usableCount ?? 0;
  const coverPreflight = diagnosticsState?.cover_preflight;
  const hasFile = Boolean(coverFile);

  let reason = "先选择模型和歌曲文件，再创建翻唱任务。";
  if (!hasFile) {
    reason = "先上传歌曲文件，系统会结合模型与诊断状态判断翻唱入口是否可用。";
  } else if (usableModelCount === 0) {
    reason = "当前不可创建：没有可用模型。请先导入模型或重新扫描模型目录。";
  } else if (coverPreflight && !coverPreflight.ok) {
    const first = coverPreflight.errors?.[0];
    reason = `当前不可创建：${summarizeCoverIssue(diagnosticsState)}。${first?.next_step || "请先查看右侧诊断面板。"}`;
  } else {
    reason = `预检通过，可以创建翻唱任务。当前可用模型 ${usableModelCount} 个。`;
  }

  availability = {
    usableModelCount,
    coverPreflightOk: coverPreflight ? Boolean(coverPreflight.ok) : usableModelCount > 0,
    reason,
  };

  refreshCoverState();
}
