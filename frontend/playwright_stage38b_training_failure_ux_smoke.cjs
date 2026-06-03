const { chromium } = require("playwright");
const fs = require("fs");

const TARGET_JOB_ID = "train_010253ec08f0";
const SCREENSHOT_PATH = "output/playwright/stage38b_training_failure_ux.png";
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

(async () => {
  const browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const pageErrors = [];
  page.on("pageerror", error => pageErrors.push(error.message));

  await page.goto("http://127.0.0.1:8000/", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
  await page.evaluate(jobId => {
    document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId } }));
  }, TARGET_JOB_ID);
  await page.waitForTimeout(2500);

  const result = await page.evaluate(() => ({
    title: document.title,
    detailTitle: document.querySelector("#jobDetailTitle")?.innerText || "",
    diagnosis: Boolean(document.querySelector(".training-failure-card")),
    diagnosisText: document.querySelector(".training-failure-card")?.innerText || "",
    digestText: document.querySelector(".train-stage-log-digest")?.innerText || "",
    rawDrawer: Boolean(document.querySelector(".stage-log-raw-drawer")),
    rawMaxHeight: getComputedStyle(document.querySelector(".stage-log-raw") || document.body).maxHeight,
    guardedRetry: Boolean(document.querySelector("#jobActionBar button[disabled][aria-disabled=true]")),
    actionText: document.querySelector("#jobActionBar")?.innerText || "",
  }));

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
  await browser.close();

  const failures = [];
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (!result.diagnosis) failures.push("missing training failure diagnosis card");
  if (!/训练超时|重复派发|进程中断|RVC 脚本异常|未知失败/.test(result.diagnosisText)) {
    failures.push("diagnosis card did not classify the failure");
  }
  if (!result.rawDrawer) failures.push("stage log raw drawer is missing");
  if (!/220px/.test(result.rawMaxHeight)) failures.push(`raw log max-height unexpected: ${result.rawMaxHeight}`);
  if (!result.guardedRetry) failures.push("high-risk failed train retry is not guarded");

  console.log(JSON.stringify({ result, pageErrors, screenshot: SCREENSHOT_PATH }, null, 2));
  if (failures.length) {
    throw new Error(failures.join("; "));
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
