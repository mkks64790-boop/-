const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE_URL = "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "output/playwright";
const SCREENSHOT_PATH = `${SCREENSHOT_DIR}/stage44b_training_preset_runtime.png`;
const TEMP_WAV = path.join(process.cwd(), "output", "playwright", "stage44b_smoke.wav");
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

async function gotoPage(page, pathName) {
  await page.goto(`${BASE_URL}${pathName}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1500);
}

function writeTinyWav() {
  fs.mkdirSync(path.dirname(TEMP_WAV), { recursive: true });
  if (fs.existsSync(TEMP_WAV)) return;
  const header = Buffer.from("524946462400000057415645666d74201000000001000100401f0000803e0000020010006461746100000000", "hex");
  fs.writeFileSync(TEMP_WAV, header);
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  writeTinyWav();

  const browser = await launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();
  const pageErrors = [];
  const unsafeCalls = [];
  const trainPayloads = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = request.url();
    if (/\/api\/process\//.test(url)) unsafeCalls.push(`${request.method()} ${url}`);
  });
  page.on("dialog", dialog => dialog.accept());

  await page.route("**/api/train", async route => {
    const request = route.request();
    trainPayloads.push(request.postData() || "");
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "train_stage44b_intercepted", strategy_key: "single_long_preprocess" }),
    });
  });

  await gotoPage(page, "/factory#factoryTrainingTuningPanel");
  await page.waitForSelector("#factoryTrainingTuningPanel", { timeout: 15000 });
  await page.click('[data-training-preset="quality"]');
  await page.waitForTimeout(500);
  const factoryQuality = await page.evaluate(() => ({
    activePreset: document.querySelector("#factoryTrainingPresetGrid .is-active")?.innerText || "",
    estimateText: document.querySelector("#factoryTrainingEstimateResult")?.innerText || "",
    storedPreset: window.localStorage.getItem("feishark.training-preset-key") || "",
    panelTop: document.querySelector("#factoryTrainingTuningPanel")?.getBoundingClientRect().top || 0,
  }));

  await gotoPage(page, "/");
  await page.waitForSelector("#dashboardTrainingPresetSummary", { timeout: 15000 });
  const dashboardSummary = await page.evaluate(() => ({
    text: document.querySelector("#dashboardTrainingPresetSummary")?.innerText || "",
    hasFactoryLink: Boolean(document.querySelector('#dashboardTrainingPresetSummary a[href="/factory#factoryTrainingTuningPanel"]')),
  }));

  await page.fill("#singleTrainVoiceNameInput", "stage44b_preset_runtime_smoke");
  await page.setInputFiles("#singleTrainFileInput", TEMP_WAV);
  await page.waitForTimeout(2200);
  await page.click("#singleTrainCreateBtn", { timeout: 15000 });
  await page.waitForTimeout(1000);

  await page.evaluate(jobId => {
    document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId } }));
  }, "train_010253ec08f0");
  await page.waitForTimeout(1600);
  const jobDetail = await page.evaluate(() => ({
    hasTrainingConfigDrawer: Boolean(document.querySelector("#jobTrainingConfigDrawer")),
    drawerHidden: Boolean(document.querySelector("#jobTrainingConfigDrawer")?.hidden),
    summary: document.querySelector("#jobTrainingConfigSummary")?.innerText || "",
  }));

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });

  await page.setViewportSize({ width: 900, height: 1050 });
  await gotoPage(page, "/factory#factoryTrainingTuningPanel");
  const mobile = await page.evaluate(() => ({
    viewportOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
    tuningPanelVisible: Boolean(document.querySelector("#factoryTrainingTuningPanel")),
  }));

  await browser.close();

  const trainPayload = trainPayloads[0] || "";
  const failures = [];
  if (!/高质量|quality/.test(factoryQuality.activePreset + factoryQuality.estimateText)) failures.push("Factory quality preset did not become active");
  if (factoryQuality.storedPreset !== "quality") failures.push(`stored preset is not quality: ${factoryQuality.storedPreset}`);
  if (factoryQuality.panelTop < 0) failures.push(`Factory training panel is hidden above viewport: ${factoryQuality.panelTop}`);
  if (!/quality|150|batch 6|GPU/.test(dashboardSummary.text)) failures.push("Dashboard training preset summary did not reflect quality config");
  if (!dashboardSummary.hasFactoryLink) failures.push("Dashboard missing Factory tuning link");
  if (!trainPayloads.length) failures.push("Training form did not attempt intercepted /api/train submission");
  if (!/training_config_json/.test(trainPayload) || !/quality/.test(trainPayload) || !/epochs/.test(trainPayload) || !/batch_size/.test(trainPayload)) {
    failures.push("Intercepted training payload does not include quality training_config");
  }
  if (!jobDetail.hasTrainingConfigDrawer || jobDetail.drawerHidden) failures.push("Training config drawer missing in job detail");
  if (!/旧任务|默认|quality|balanced|fast_preview/.test(jobDetail.summary)) failures.push("Training config drawer summary missing default/config state");
  if (mobile.viewportOverflow) failures.push("Mobile Factory viewport overflows horizontally");
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unexpected process calls: ${unsafeCalls.join(" | ")}`);

  console.log(JSON.stringify({
    factoryQuality,
    dashboardSummary,
    trainPayloadSnippet: trainPayload.slice(0, 1200),
    trainPayloadCount: trainPayloads.length,
    jobDetail,
    mobile,
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
