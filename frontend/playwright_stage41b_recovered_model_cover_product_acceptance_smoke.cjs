const { chromium } = require("playwright");
const fs = require("fs");

const JOB_ID = "train_010253ec08f0";
const MODEL_ID = "v_2c1603c7";
const SCREENSHOT_PATH = "output/playwright/stage41b_recovered_model_cover_product_acceptance.png";
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

async function openRecoveredDashboard(page) {
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
  await page.evaluate(jobId => {
    document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId } }));
  }, JOB_ID);
  await page.waitForSelector(".checkpoint-recovery-card.success", { timeout: 10000 });
}

(async () => {
  const browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1120 } });
  const pageErrors = [];
  const processCalls = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    if (/\/api\/process\//.test(request.url())) processCalls.push(request.url());
  });

  await openRecoveredDashboard(page);
  const desktop = await page.evaluate(() => ({
    cardText: document.querySelector(".checkpoint-recovery-card")?.innerText || "",
    coverNoteBefore: document.querySelector("#coverRecoveredModelNote")?.innerText || "",
    createDisabledBefore: Boolean(document.querySelector("#coverCreateBtn")?.disabled),
  }));

  await page.click("[data-send-recovered-model-cover]");
  await page.waitForTimeout(500);
  const cover = await page.evaluate(() => ({
    selectedModelId: document.querySelector("#coverModelSelect")?.value || "",
    recoveredNote: document.querySelector("#coverRecoveredModelNote")?.innerText || "",
    recoveredNoteHidden: Boolean(document.querySelector("#coverRecoveredModelNote")?.hidden),
    availabilityText: document.querySelector("#coverAvailabilityNote")?.innerText || "",
    createDisabled: Boolean(document.querySelector("#coverCreateBtn")?.disabled),
  }));

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });

  await page.setViewportSize({ width: 900, height: 1050 });
  await openRecoveredDashboard(page);
  await page.click("[data-open-recovered-model]");
  await page.waitForSelector("#modelDetailCard .tag.checkpoint", { timeout: 10000 });
  const mobile = await page.evaluate(() => ({
    activeTab: document.body.dataset.mobileTab || "",
    detailText: document.querySelector("#modelDetailCard")?.innerText || "",
    selectedCardActive: Boolean(document.querySelector(`[data-model-id="${CSS.escape("v_2c1603c7")}"].is-active`)),
    cardOverflow: (() => {
      const card = document.querySelector(".checkpoint-recovery-card");
      return card ? card.scrollWidth > card.clientWidth + 2 : false;
    })(),
  }));

  await browser.close();

  const failures = [];
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (!/恢复模型验收/.test(desktop.cardText)) failures.push("Dashboard acceptance guide missing");
  if (!/选择歌曲/.test(desktop.cardText) || !/创建 AI 翻唱/.test(desktop.cardText) || !/Studio 试听/.test(desktop.cardText)) {
    failures.push("Dashboard acceptance steps incomplete");
  }
  if (cover.selectedModelId !== MODEL_ID) failures.push(`cover select did not choose recovered model: ${cover.selectedModelId}`);
  if (cover.recoveredNoteHidden || !/checkpoint 恢复模型/.test(cover.recoveredNote)) failures.push("cover recovered model note missing");
  if (!/选择歌曲|上传歌曲/.test(cover.availabilityText)) failures.push("cover availability does not ask for a song");
  if (!cover.createDisabled) failures.push("cover create button enabled without song");
  if (processCalls.length) failures.push(`unexpected cover process call: ${processCalls.join(" | ")}`);
  if (mobile.activeTab !== "models") failures.push(`mobile models tab not active: ${mobile.activeTab}`);
  if (!mobile.selectedCardActive) failures.push("mobile recovered model card not active");
  if (!/v_2c1603c7/.test(mobile.detailText)) failures.push("mobile detail is not recovered model");
  if (!/checkpoint 恢复/.test(mobile.detailText) || !/e90/.test(mobile.detailText) || !/train_010253ec08f0/.test(mobile.detailText)) {
    failures.push("mobile recovered detail lacks checkpoint/e90/source job");
  }
  if (mobile.cardOverflow) failures.push("mobile recovery card overflows horizontally");

  console.log(JSON.stringify({ desktop, cover, mobile, pageErrors, processCalls, screenshot: SCREENSHOT_PATH }, null, 2));
  if (failures.length) {
    throw new Error(failures.join("; "));
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
