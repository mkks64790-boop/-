const { chromium } = require("playwright");
const fs = require("fs");

const JOB_ID = "train_010253ec08f0";
const MODEL_ID = "v_2c1603c7";
const SCREENSHOT_PATH = "output/playwright/stage40b_recovered_model_product_loop.png";
const BROWSER_FALLBACKS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const executablePath = BROWSER_FALLBACKS.find(path => fs.existsSync(path));
    if (!executablePath) throw error;
    return chromium.launch({ headless: true, executablePath });
  }
}

async function inspectViewport(page, width, height) {
  await page.setViewportSize({ width, height });
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
  await page.evaluate(jobId => {
    document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId } }));
  }, JOB_ID);
  await page.waitForSelector(".checkpoint-recovery-card.success", { timeout: 10000 });

  const dashboard = await page.evaluate(() => ({
    cardText: document.querySelector(".checkpoint-recovery-card")?.innerText || "",
    actionText: document.querySelector("#jobActionBar")?.innerText || "",
    overflow: (() => {
      const card = document.querySelector(".checkpoint-recovery-card");
      return card ? card.scrollWidth > card.clientWidth + 2 : false;
    })(),
  }));

  await page.click("[data-send-recovered-model-cover]");
  await page.waitForTimeout(500);
  const cover = await page.evaluate(() => ({
    selectedModelId: document.querySelector("#coverModelSelect")?.value || "",
    activeTab: document.body.dataset.mobileTab || "",
    createButtonDisabled: Boolean(document.querySelector("#coverCreateBtn")?.disabled),
  }));

  await page.evaluate(modelId => {
    document.dispatchEvent(new CustomEvent("feishark:focus-model", { detail: { modelId } }));
  }, MODEL_ID);
  await page.waitForTimeout(1000);
  const models = await page.evaluate(() => ({
    detailText: document.querySelector("#modelDetailCard")?.innerText || "",
    selectedCardText: document.querySelector(`[data-model-id="${CSS.escape("v_2c1603c7")}"]`)?.innerText || "",
    selectedModelId: document.querySelector("#coverModelSelect")?.value || "",
  }));

  return { dashboard, cover, models };
}

(async () => {
  const browser = await launchBrowser();
  const page = await browser.newPage();
  const pageErrors = [];
  const processCalls = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    if (/\/api\/process\//.test(request.url())) processCalls.push(request.url());
  });

  const desktop = await inspectViewport(page, 1440, 1120);
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
  const mobile = await inspectViewport(page, 900, 1050);

  await browser.close();

  const failures = [];
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (!/已从 checkpoint 恢复/.test(desktop.dashboard.cardText)) failures.push("Dashboard recovered success card missing");
  if (!/feishark_v_62f76886/.test(desktop.dashboard.cardText)) failures.push("Dashboard source exp missing");
  if (!/e90/.test(desktop.dashboard.cardText)) failures.push("Dashboard recovered epoch missing");
  if (!/去模型库查看/.test(desktop.dashboard.cardText) || !/送入 AI 翻唱/.test(desktop.dashboard.cardText)) {
    failures.push("Dashboard recovered CTAs missing");
  }
  if (desktop.cover.selectedModelId !== MODEL_ID) failures.push(`cover select did not choose recovered model: ${desktop.cover.selectedModelId}`);
  if (!/checkpoint 恢复/.test(desktop.models.detailText)) failures.push("model detail checkpoint tag missing");
  if (!/train_010253ec08f0/.test(desktop.models.detailText)) failures.push("model detail source job missing");
  if (!/feishark_v_62f76886/.test(desktop.models.detailText)) failures.push("model detail recovered exp missing");
  if (desktop.cover.createButtonDisabled === false) failures.push("cover job create became enabled without song upload");
  if (processCalls.length) failures.push(`unexpected cover process call: ${processCalls.join(" | ")}`);
  if (mobile.dashboard.overflow) failures.push("mobile recovery card overflows horizontally");

  console.log(JSON.stringify({ desktop, mobile, pageErrors, processCalls, screenshot: SCREENSHOT_PATH }, null, 2));
  if (failures.length) {
    throw new Error(failures.join("; "));
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
