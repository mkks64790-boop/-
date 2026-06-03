const { chromium } = require("playwright");
const fs = require("fs");

const TARGET_JOB_ID = "train_010253ec08f0";
const SCREENSHOT_PATH = "output/playwright/stage39b_checkpoint_recovery_ux.png";
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
  const page = await browser.newPage({ viewport: { width: 1440, height: 1120 } });
  const pageErrors = [];
  const calls = { get: 0, post: 0 };
  let confirmSeen = false;
  let confirmMessage = "";

  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("dialog", async dialog => {
    confirmSeen = true;
    confirmMessage = dialog.message();
    await dialog.accept();
  });

  await page.route(`**/api/jobs/${TARGET_JOB_ID}/training-recovery`, async route => {
    calls.get += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        can_recover: true,
        candidates: [
          { exp_name: "feishark_v_2860bda4", highest_epoch: 10, feature_count: 120, index_feasible: true },
          {
            exp_name: "feishark_v_62f76886",
            highest_epoch: 90,
            feature_count: 552,
            index_feasible: true,
            weight_path: "D:\\RVC\\RVCv2\\assets\\weights\\feishark_v_62f76886_e90_s6300.pth",
          },
        ],
      }),
    });
  });

  await page.route(`**/api/jobs/${TARGET_JOB_ID}/training-recovery/register`, async route => {
    calls.post += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        model_id: "v_recovered_stage39b",
        message: "registered from checkpoint",
      }),
    });
  });

  await page.goto("http://127.0.0.1:8000/", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
  await page.evaluate(jobId => {
    document.dispatchEvent(new CustomEvent("feishark:focus-job", { detail: { jobId } }));
  }, TARGET_JOB_ID);
  await page.waitForSelector(".checkpoint-recovery-card.ready", { timeout: 10000 });

  const beforeClick = await page.evaluate(() => ({
    cardText: document.querySelector(".checkpoint-recovery-card")?.innerText || "",
    buttonText: document.querySelector('[data-action="checkpoint-register"]')?.innerText || "",
  }));

  await page.click('[data-action="checkpoint-register"]');
  await page.waitForSelector(".checkpoint-recovery-card.success", { timeout: 10000 });

  const afterClick = await page.evaluate(() => ({
    cardText: document.querySelector(".checkpoint-recovery-card")?.innerText || "",
    hasModelCta: Boolean(document.querySelector("[data-open-recovered-model]")),
    hasCoverCta: Boolean(document.querySelector("[data-send-recovered-model-cover]")),
  }));

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
  await browser.close();

  const failures = [];
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (calls.get < 1) failures.push("training-recovery GET was not called");
  if (!/feishark_v_62f76886/.test(beforeClick.cardText)) failures.push("recommended exp is not feishark_v_62f76886");
  if (/feishark_v_2860bda4/.test(beforeClick.cardText.split("查看其它候选")[0] || "")) {
    failures.push("duplicate e10 experiment was highlighted before the e90 recommendation");
  }
  if (!/e90/.test(beforeClick.buttonText)) failures.push("recovery button does not mention e90");
  if (!confirmSeen || !/不会重新训练/.test(confirmMessage)) failures.push("second confirmation dialog was not shown");
  if (calls.post !== 1) failures.push(`register POST count unexpected: ${calls.post}`);
  if (!/模型已从 checkpoint 恢复登记/.test(afterClick.cardText)) failures.push("success recovery card is missing");
  if (!afterClick.hasModelCta || !afterClick.hasCoverCta) failures.push("success CTAs are missing");

  console.log(JSON.stringify({ beforeClick, afterClick, calls, confirmMessage, pageErrors, screenshot: SCREENSHOT_PATH }, null, 2));
  if (failures.length) {
    throw new Error(failures.join("; "));
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
