import { getJSON } from "./api.js";
import { refreshDiagnostics, getDiagnosticsState, initDiagnostics } from "./diagnostics.js";
import { initCoverCreate, syncCoverAvailability } from "./cover.js";
import { initJobs, refreshJobs } from "./jobs.js";
import { getModelsState, getSelectedCoverModelId, initModels, refreshModels } from "./models.js";
import { initTrainCreate, syncTrainAvailability } from "./train.js";
import { setEngineChip } from "./ui.js";

let refreshInFlight = null;
let queuedFocusJobId = null;

const MOBILE_TAB_STORAGE_KEY = "feishark.mobile-tab";
const MOBILE_TABS = new Set(["dashboard", "models", "monitor"]);
let mobileTab = "dashboard";

async function refreshHealth() {
  const data = await getJSON("/api/health");
  setEngineChip(Boolean(data.rvc?.online), data.rvc?.base_url || "");
}

function shouldPauseAutoRefresh() {
  if (document.hidden) return true;
  const active = document.activeElement;
  if (!active) return false;
  if (active.closest?.("form")) return true;
  if (active.closest?.("#jobDetailPanel")) return true;
  if (active.closest?.(".mobile-tabbar")) return true;
  const tagName = String(active.tagName || "").toLowerCase();
  return ["input", "textarea", "select", "button"].includes(tagName) || Boolean(active.closest?.("[contenteditable='true']"));
}

function getStoredMobileTab() {
  try {
    const stored = window.localStorage.getItem(MOBILE_TAB_STORAGE_KEY);
    return MOBILE_TABS.has(stored) ? stored : "dashboard";
  } catch {
    return "dashboard";
  }
}

function setMobileTab(tab, { persist = true } = {}) {
  mobileTab = MOBILE_TABS.has(tab) ? tab : "dashboard";
  document.body.dataset.mobileTab = mobileTab;

  const buttons = document.querySelectorAll("[data-mobile-tab-target]");
  buttons.forEach(button => {
    const active = button.dataset.mobileTabTarget === mobileTab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  if (persist) {
    try {
      window.localStorage.setItem(MOBILE_TAB_STORAGE_KEY, mobileTab);
    } catch {
      // Ignore storage failures in private browsing modes.
    }
  }
}

function initMobileTabs() {
  setMobileTab(getStoredMobileTab(), { persist: false });

  document.querySelectorAll("[data-mobile-tab-target]").forEach(button => {
    button.addEventListener("click", () => setMobileTab(button.dataset.mobileTabTarget));
  });
}

async function runWorkspaceRefresh(focusJobId = null) {
  await refreshModels();
  const currentModelId = getSelectedCoverModelId() || "v_001";
  await Promise.all([
    refreshJobs({ focusJobId }),
    refreshDiagnostics(currentModelId),
    refreshHealth(),
  ]);
  syncCoverAvailability(getDiagnosticsState(), getModelsState());
  await syncTrainAvailability();
}

export async function refreshWorkspace(focusJobId = null) {
  if (refreshInFlight) {
    queuedFocusJobId = focusJobId || queuedFocusJobId;
    return refreshInFlight;
  }

  refreshInFlight = (async () => {
    try {
      await runWorkspaceRefresh(focusJobId);
    } finally {
      refreshInFlight = null;
      if (queuedFocusJobId) {
        const nextFocus = queuedFocusJobId;
        queuedFocusJobId = null;
        await refreshWorkspace(nextFocus);
      }
    }
  })();

  return refreshInFlight;
}

function bindWorkspaceEvents() {
  const onJobCreated = async (jobId) => {
    await refreshWorkspace(jobId);
  };

  initMobileTabs();
  initJobs();
  initModels();
  initDiagnostics(() => getSelectedCoverModelId() || "v_001");
  initCoverCreate(onJobCreated);
  initTrainCreate(onJobCreated);
}

document.addEventListener("DOMContentLoaded", async () => {
  bindWorkspaceEvents();
  document.addEventListener("feishark:models-changed", () => {
    refreshWorkspace().catch(() => {});
  });
  window.addEventListener("storage", event => {
    if (event.key === MOBILE_TAB_STORAGE_KEY && event.newValue && MOBILE_TABS.has(event.newValue)) {
      setMobileTab(event.newValue, { persist: false });
    }
  });
  await refreshWorkspace().catch(() => {});
  window.setInterval(() => {
    if (shouldPauseAutoRefresh()) return;
    refreshWorkspace().catch(() => {});
  }, 15000);
});
