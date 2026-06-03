const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "output/playwright";
const SCREENSHOT_PATH = `${SCREENSHOT_DIR}/stage49_listening_review.png`;
const JOB_ID = "task_b2272d133fff";
const ARTIFACT_ID = "art_f99f7e4afb10";
const SMOKE_NOTE = "stage49 browser smoke only - not a human quality verdict";
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

async function fetchJson(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, options);
  const text = await response.text();
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${text.slice(0, 500)}`);
  return JSON.parse(text);
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const job = await fetchJson(`/api/jobs/${JOB_ID}`);
  if (!job.can_open_studio) throw new Error("Stage49 smoke requires a playable Studio job");

  const sourceResp = await fetch(`${BASE_URL}/api/jobs/${JOB_ID}/source-audio/download`);
  if (!sourceResp.ok) throw new Error(`source audio download failed: ${sourceResp.status}`);
  const sourceBytes = await sourceResp.arrayBuffer();
  if (!sourceBytes.byteLength) throw new Error("source audio download is empty");

  const browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const pageErrors = [];
  const unsafeCalls = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    if (/\/api\/train\b|\/api\/process\/|\/cover-jobs\b|\/api\/cover\b|\/api\/upload_task\b|\/rvc\/infer\b|\/infer\b/i.test(url)) {
      unsafeCalls.push(`${request.method()} ${url}`);
    }
  });

  await page.goto(`${BASE_URL}/studio?job_id=${JOB_ID}&artifact_id=${ARTIFACT_ID}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForSelector("#studioReviewPanel:not([hidden])", { timeout: 20000 });
  await page.waitForFunction(() => {
    const audio = document.querySelector("#studioReviewSourceAudio");
    return Boolean(audio?.src && audio.src.includes("/source-audio/download"));
  }, null, { timeout: 15000 });

  await page.selectOption("#studioReviewVerdict", "unreviewed");
  await page.fill("#studioReviewNotes", SMOKE_NOTE);
  await page.click("#studioReviewSaveBtn");
  await page.waitForFunction(
    note => (document.querySelector("#studioReviewState")?.innerText || "").includes("已保存")
      && (document.querySelector("#studioReviewNotes")?.value || "").includes(note),
    SMOKE_NOTE,
    { timeout: 15000 },
  );

  const reviewPayload = await fetchJson(`/api/jobs/${JOB_ID}/artifacts/${ARTIFACT_ID}/review`);
  const ui = await page.evaluate(() => ({
    hasPanel: Boolean(document.querySelector("#studioReviewPanel:not([hidden])")),
    stateText: document.querySelector("#studioReviewState")?.innerText || "",
    sourceAudio: document.querySelector("#studioReviewSourceAudio")?.src || "",
    notes: document.querySelector("#studioReviewNotes")?.value || "",
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  }));
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
  await browser.close();

  const failures = [];
  if (!ui.hasPanel) failures.push("review panel missing");
  if (!ui.sourceAudio.includes("/source-audio/download")) failures.push("source A/B audio not wired");
  if (!ui.stateText.includes("已保存")) failures.push("review save state not visible");
  if (!reviewPayload.review || reviewPayload.review.notes !== SMOKE_NOTE) failures.push("review metadata not persisted");
  if (ui.overflow) failures.push("Studio viewport overflows horizontally");
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unsafe training/RVC/cover calls: ${unsafeCalls.join(" | ")}`);

  console.log(JSON.stringify({
    jobId: JOB_ID,
    artifactId: ARTIFACT_ID,
    sourceBytes: sourceBytes.byteLength,
    ui,
    review: reviewPayload.review,
    screenshot: SCREENSHOT_PATH,
    pageErrors,
    unsafeCalls,
  }, null, 2));

  if (failures.length) throw new Error(failures.join("; "));
})();
