const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "output/playwright";
const SCREENSHOT_PATH = `${SCREENSHOT_DIR}/stage45rb_separation_quality_lab_real_api.png`;
const PREFERRED_RUN_ID = "stage45r_20260602_171704_201ec7ff";
const BROWSER_FALLBACKS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const executablePath = BROWSER_FALLBACKS.find(candidate => fs.existsSync(candidate));
    if (!executablePath) throw error;
    return chromium.launch({ headless: true, executablePath });
  }
}

async function fetchJson(path) {
  const response = await fetch(`${BASE_URL}${path}`);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${text.slice(0, 500)}`);
  }
  return JSON.parse(text);
}

async function fetchStatus(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, options);
  return response.status;
}

async function gotoPage(page, pathName) {
  await page.goto(`${BASE_URL}${pathName}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
}

function latestRunId(runsPayload) {
  const runs = Array.isArray(runsPayload?.runs)
    ? runsPayload.runs
    : Array.isArray(runsPayload?.items)
      ? runsPayload.items
      : [];
  const preferred = runs.find(item => (item?.run_id || item?.id || "") === PREFERRED_RUN_ID);
  if (preferred) return PREFERRED_RUN_ID;
  return runs[0]?.run_id || runs[0]?.id || "";
}

function firstRunItem(detail) {
  const items = Array.isArray(detail?.manifest?.items)
    ? detail.manifest.items
    : Array.isArray(detail?.items)
      ? detail.items
      : [];
  if (items[0]) return items[0];
  const report = Array.isArray(detail?.reports) ? detail.reports[0] : null;
  return report ? { report } : null;
}

function hasRealReport(item) {
  const report = item?.report || {};
  return Boolean(report.noise_risk && report.suspected_causes && report.next_step && report.metrics);
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const sources = await fetchJson("/api/separation/eval/sources");
  const runs = await fetchJson("/api/separation/eval/runs");
  const runId = latestRunId(runs);
  if (!runId) throw new Error("real API returned no eval runs");
  const detail = await fetchJson(`/api/separation/eval/runs/${encodeURIComponent(runId)}`);
  const item = firstRunItem(detail);
  const postProbeStatus = await fetchStatus("/api/separation/eval/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit: 1, clip_seconds: 45 }),
  });

  const browser = await launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();
  const pageErrors = [];
  const unsafeCalls = [];
  const postPayloads = [];

  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    if (/\/api\/train\b|\/api\/process\/|\/cover-jobs\b|\/api\/cover\b|\/api\/upload_task\b|\/rvc\/infer\b|\/infer\b/i.test(url)) {
      unsafeCalls.push(`${request.method()} ${url}`);
    }
    if (/\/api\/separation\/eval\/run$/.test(url) && request.method() === "POST") {
      postPayloads.push(request.postData() || "");
    }
  });
  page.on("dialog", dialog => dialog.accept());

  await gotoPage(page, "/factory#factorySeparationLabPanel");
  await page.waitForSelector("#factorySeparationLabPanel", { timeout: 15000 });
  await page.waitForSelector("#factorySeparationRunsList", { timeout: 15000 });
  await page.waitForFunction(
    id => document.querySelector("#factorySeparationRunsList")?.innerText.includes(id),
    runId,
    { timeout: 15000 },
  );

  const desktop = await page.evaluate(() => ({
    hasLab: Boolean(document.querySelector("#factorySeparationLabPanel")),
    candidateText: document.querySelector("#factorySeparationCandidatesList")?.innerText || "",
    runsText: document.querySelector("#factorySeparationRunsList")?.innerText || "",
    itemsText: document.querySelector("#factorySeparationItemsList")?.innerText || "",
    playerAudioCount: document.querySelectorAll("#factorySeparationPlayersGrid audio").length,
    missingUrlCount: document.querySelectorAll("#factorySeparationPlayersGrid .separation-url-missing").length,
    playerText: document.querySelector("#factorySeparationPlayersGrid")?.innerText || "",
    unlockText: document.querySelector("#factorySeparationUnlockPanel")?.innerText || "",
    durationText: document.querySelector(".separation-duration-panel")?.innerText || "",
    durationRiskRows: document.querySelectorAll("#factorySeparationDurationTable tr.is-risk").length,
    metricsText: document.querySelector("#factorySeparationMetrics")?.innerText || "",
    runButtonText: document.querySelector("#factorySeparationRunBtn")?.innerText || "",
    runButtonDisabled: Boolean(document.querySelector("#factorySeparationRunBtn")?.disabled),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));

  if (!desktop.runButtonDisabled && [200, 202].includes(postProbeStatus)) {
    await page.click("#factorySeparationRunBtn", { timeout: 15000 });
    await page.waitForTimeout(1000);
  }

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });

  await page.setViewportSize({ width: 900, height: 1050 });
  await gotoPage(page, "/factory#factorySeparationLabPanel");
  const mobile = await page.evaluate(() => ({
    hasLab: Boolean(document.querySelector("#factorySeparationLabPanel")),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));

  await browser.close();

  const sourceCount = Array.isArray(sources?.candidates) ? sources.candidates.length : Array.isArray(sources?.items) ? sources.items.length : 0;
  const runCount = Array.isArray(runs?.runs) ? runs.runs.length : Array.isArray(runs?.items) ? runs.items.length : 0;
  const report = item?.report || {};
  const failures = [];

  if (sourceCount <= 0) failures.push("real sources API returned no candidates");
  if (runCount <= 0) failures.push("real runs API returned no runs");
  if (!hasRealReport(item)) failures.push("real run detail does not contain manifest.items[].report metrics/noise_risk/suspected_causes/next_step");
  if (!desktop.hasLab) failures.push("separation lab missing");
  if (!desktop.candidateText.trim()) failures.push("real candidate area empty");
  if (!desktop.runsText.includes(runId)) failures.push(`real run_id not rendered in UI: ${runId}`);
  if (desktop.playerAudioCount < 3 && desktop.missingUrlCount < 3) {
    failures.push("players are neither real audio elements nor explicit backend-missing-URL states");
  }
  if (desktop.playerAudioCount < 3 && !/后端缺少播放 URL/.test(desktop.playerText)) {
    failures.push("missing artifact URLs are not clearly labeled as backend missing playback URLs");
  }
  for (const key of ["noise_risk", "suspected_causes", "next_step"]) {
    if (!desktop.metricsText.includes(key)) failures.push(`real metric label missing in UI: ${key}`);
  }
  if (/等待数据\s*等待数据\s*等待数据/.test(desktop.metricsText)) failures.push("metrics still look like placeholder waiting data");
  if (report.noise_risk && !desktop.metricsText.includes(String(report.noise_risk))) {
    failures.push(`UI does not show real noise_risk value: ${report.noise_risk}`);
  }
  if (!/训练锁定|BLOCK_TRAINING|duration_ratio/.test(desktop.unlockText)) {
    failures.push("training unlock card does not show locked state, duration_ratio, and BLOCK_TRAINING");
  }
  for (const clip of ["15", "30", "45"]) {
    if (!desktop.durationText.includes(`${clip}s`)) failures.push(`duration comparison table missing ${clip}s run`);
  }
  if (!/0\.59|high|duration/i.test(desktop.durationText)) failures.push("duration comparison table missing ratio/risk evidence");
  if (desktop.durationRiskRows <= 0) failures.push("duration comparison table does not mark risky ratio rows");
  if ([405, 501, 503].includes(postProbeStatus)) {
    if (!desktop.runButtonDisabled) failures.push(`POST run is ${postProbeStatus} but button is enabled`);
    if (!/后端未开放浏览器执行分离|CLI/.test(desktop.runButtonText)) failures.push(`${postProbeStatus} button copy is not explicit`);
    if (postPayloads.length) failures.push(`POST run was called from the page even though real backend returned ${postProbeStatus}`);
  } else if ([200, 202].includes(postProbeStatus)) {
    if (desktop.runButtonDisabled) failures.push(`POST run returned ${postProbeStatus} but button is disabled`);
    if (!postPayloads.length) failures.push(`POST run returned ${postProbeStatus} but button did not submit`);
  }
  if (postPayloads.length) {
    const payload = postPayloads[0] || "";
    if (!/"limit"\s*:\s*1/.test(payload) || !/"clip_seconds"\s*:\s*45/.test(payload)) {
      failures.push(`unsafe POST payload: ${payload}`);
    }
  }
  if (desktop.overflow) failures.push("desktop Factory viewport overflows horizontally");
  if (!mobile.hasLab) failures.push("mobile separation lab missing");
  if (mobile.overflow) failures.push("mobile Factory viewport overflows horizontally");
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unsafe train/RVC calls: ${unsafeCalls.join(" | ")}`);

  console.log(JSON.stringify({
    realApi: {
      sourceCount,
      runCount,
      runId,
      itemHasReport: hasRealReport(item),
      noiseRisk: report.noise_risk || "",
      suspectedCauses: report.suspected_causes || [],
      nextStep: report.next_step || "",
      postStatus: postProbeStatus,
    },
    desktop,
    mobile,
    postPayloads,
    pageErrors,
    unsafeCalls,
    screenshot: SCREENSHOT_PATH,
  }, null, 2));

  if (failures.length) {
    throw new Error(failures.join("; "));
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
