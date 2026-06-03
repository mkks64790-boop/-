const { chromium } = require("playwright");
const fs = require("fs");

const BASE_URL = process.env.FEISHARK_BASE_URL || "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "output/playwright";
const BROWSER_FALLBACKS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

const USER_JOB_ID = "user_cover_clean_001";
const NOISE_JOB_ID = "stage58_playwright_smoke_job";
const USER_MODEL_ID = "voice_clean_user_model";
const NOISE_MODEL_ID = "stage58_smoke_test_model";
const USER_BATCH_ID = "batch_user_clean_001";
const NOISE_BATCH_ID = "stage58_playwright_test_batch";
const TEST_RECORDS_VISIBLE_KEY = "feishark_ui_show_test_records";

function isIncludeTestUrl(url) {
  return /[?&](include_test_data|include_smoke)=true/i.test(url);
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    const executablePath = BROWSER_FALLBACKS.find(candidate => fs.existsSync(candidate));
    if (!executablePath) throw error;
    return chromium.launch({ headless: true, executablePath });
  }
}

async function fulfillJson(route, payload, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

function userJob() {
  return {
    job_id: USER_JOB_ID,
    job_type: "cover",
    job_kind: "cover",
    status: "completed",
    current_stage: "cover_mix",
    strategy_key: "cover_strategy",
    voice_name: "Clean User Voice",
    voice_model_id: USER_MODEL_ID,
    created_at: "2026-06-03 08:00:00",
    updated_at: "2026-06-03 08:05:00",
    can_open_studio: true,
    final_artifact_download_url: `/api/jobs/${USER_JOB_ID}/artifacts/art_user_master/download`,
    track_id: "track_user_clean_001",
  };
}

function noiseJob() {
  return {
    job_id: NOISE_JOB_ID,
    job_type: "cover",
    job_kind: "cover",
    status: "completed",
    current_stage: "stage58_playwright_smoke",
    strategy_key: "cover_strategy",
    voice_name: "Stage58 playwright smoke",
    voice_model_id: NOISE_MODEL_ID,
    created_at: "2026-06-03 09:00:00",
    updated_at: "2026-06-03 09:05:00",
    can_open_studio: true,
    final_artifact_download_url: `/api/jobs/${NOISE_JOB_ID}/artifacts/art_stage58_smoke/download`,
    track_id: "stage58_playwright_track",
  };
}

function userModel() {
  return {
    model_id: USER_MODEL_ID,
    model_name: "Clean User Voice",
    usable: true,
    exists: true,
    origin_kind: "trained_local",
    source_job_id: "train_user_clean_001",
    source_summary: "user model",
    updated_at: "2026-06-03 08:05:00",
  };
}

function noiseModel() {
  return {
    model_id: NOISE_MODEL_ID,
    model_name: "Stage58 smoke test model",
    usable: true,
    exists: true,
    origin_kind: "trained_local",
    source_job_id: "stage58_playwright_train",
    source_summary: "playwright smoke test model",
    updated_at: "2026-06-03 09:05:00",
  };
}

function userBatch() {
  return {
    batch_id: USER_BATCH_ID,
    batch_name: "Clean user batch",
    status: "draft",
    created_at: "2026-06-03 08:00:00",
    track_count: 1,
    tracks: [
      {
        track_id: "track_user_clean_001",
        title: "Clean User Song",
        artist: "User Artist",
        status: "cover_ready",
        source_audio_path: "shared_data/user_song.wav",
      },
    ],
  };
}

function noiseBatch() {
  return {
    batch_id: NOISE_BATCH_ID,
    batch_name: "stage58 playwright test batch",
    status: "draft",
    created_at: "2026-06-03 09:00:00",
    track_count: 1,
    tracks: [
      {
        track_id: "stage58_playwright_track",
        title: "stage58 smoke track",
        artist: "Playwright",
        status: "cover_ready",
        source_audio_path: "shared_data/stage58_smoke.wav",
      },
    ],
  };
}

async function installMockApi(page, unsafeCalls, seenUrls) {
  await page.route("**/api/**", async route => {
    const request = route.request();
    const url = request.url();
    const parsed = new URL(url);
    const path = parsed.pathname;
    seenUrls.push(url);

    if (request.method() !== "GET") {
      unsafeCalls.push(`${request.method()} ${url}`);
      return fulfillJson(route, { ok: false, blocked_by_smoke: true }, 405);
    }

    const includeTest = isIncludeTestUrl(url);
    const jobs = includeTest ? [noiseJob(), userJob()] : [noiseJob(), userJob()];
    const models = includeTest ? [noiseModel(), userModel()] : [noiseModel(), userModel()];
    const batches = includeTest ? [noiseBatch(), userBatch()] : [noiseBatch(), userBatch()];

    if (path === "/api/jobs/summary") {
      return fulfillJson(route, { pending_count: 0, processing_count: 0, failed_count: 0, completed_count: jobs.length });
    }
    if (path === "/api/jobs") {
      const jobType = parsed.searchParams.get("job_type");
      const items = jobType ? jobs.filter(job => job.job_type === jobType) : jobs;
      return fulfillJson(route, { items, limit: 100, offset: 0, total_count: items.length });
    }
    if (path === `/api/jobs/${USER_JOB_ID}`) return fulfillJson(route, userJob());
    if (path === `/api/jobs/${NOISE_JOB_ID}`) return fulfillJson(route, noiseJob());
    if (/\/api\/jobs\/[^/]+\/artifacts$/.test(path)) {
      const isNoise = path.includes(NOISE_JOB_ID);
      return fulfillJson(route, {
        artifacts: [
          {
            artifact_id: isNoise ? "art_stage58_smoke" : "art_user_master",
            artifact_type: "cover_master",
            stage_name: isNoise ? "stage58_playwright_smoke" : "cover_mix",
            file_path: isNoise ? "shared_data/stage58_smoke/final_master.wav" : "shared_data/user/final_master.wav",
            download_url: isNoise ? `/api/jobs/${NOISE_JOB_ID}/artifacts/art_stage58_smoke/download` : `/api/jobs/${USER_JOB_ID}/artifacts/art_user_master/download`,
            is_final: true,
          },
        ],
      });
    }
    if (/\/api\/jobs\/[^/]+\/stage-logs$/.test(path)) {
      return fulfillJson(route, {
        stage_logs: [
          { stage_name: "cover_mix", status: "completed", message: "clean user stage", created_at: "2026-06-03 08:05:00" },
          { stage_name: "stage58_playwright_smoke", status: "completed", message: "playwright smoke test log", created_at: "2026-06-03 09:05:00" },
        ],
      });
    }
    if (path === "/api/datasets") return fulfillJson(route, { items: [] });
    if (path === "/api/models") return fulfillJson(route, models);
    if (path === `/api/models/${USER_MODEL_ID}`) return fulfillJson(route, userModel());
    if (path === `/api/models/${NOISE_MODEL_ID}`) return fulfillJson(route, noiseModel());
    if (path === "/api/factory/summary") return fulfillJson(route, { batch_count: batches.length, track_count: 2, timeline_count: 0 });
    if (path === "/api/batches") return fulfillJson(route, { items: batches, limit: 100, offset: 0, total_count: batches.length });
    if (path === `/api/batches/${USER_BATCH_ID}/tracks`) return fulfillJson(route, { items: userBatch().tracks });
    if (path === `/api/batches/${NOISE_BATCH_ID}/tracks`) return fulfillJson(route, { items: noiseBatch().tracks });
    if (path === `/api/batches/${USER_BATCH_ID}`) return fulfillJson(route, userBatch());
    if (path === `/api/batches/${NOISE_BATCH_ID}`) return fulfillJson(route, noiseBatch());
    if (/\/api\/tracks\/[^/]+\/jobs$/.test(path)) return fulfillJson(route, { items: jobs, limit: 10, offset: 0 });
    if (/\/api\/tracks\/[^/]+\/studio-versions$/.test(path)) return fulfillJson(route, { items: jobs, current_master: userJob(), current_master_job_id: USER_JOB_ID });
    if (/\/api\/tracks\/[^/]+$/.test(path)) return fulfillJson(route, userBatch().tracks[0]);
    if (path === "/api/engines") return fulfillJson(route, { engines: [{ engine_key: "rvc", online: false, status: "offline" }] });
    if (path === "/api/engines/rvc/models") return fulfillJson(route, { items: models, total_count: models.length });
    if (path === "/api/reviews/artifacts") return fulfillJson(route, { artifacts: [], summary: {} });
    if (path === "/api/material-library/summary") return fulfillJson(route, {});
    if (path === "/api/material-library/items") return fulfillJson(route, { items: [] });
    if (path === "/api/training/presets") return fulfillJson(route, { presets: [] });
    if (path === "/api/separation/eval/sources") return fulfillJson(route, { items: [] });
    if (path === "/api/separation/eval/runs") return fulfillJson(route, { items: [] });
    if (path === "/api/studio/effect-rack/capabilities") return fulfillJson(route, { render_engines: [{ key: "copy_only", available: true }] });
    if (/\/api\/jobs\/[^/]+\/artifacts\/[^/]+\/review$/.test(path)) return fulfillJson(route, { review: {} });

    return fulfillJson(route, { ok: true, items: [] });
  });
}

async function gotoPage(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: "commit", timeout: 60000 });
  await page.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1200);
}

async function resetShowTestRecords(page) {
  await page.evaluate(key => {
    window.localStorage.setItem(key, "false");
  }, TEST_RECORDS_VISIBLE_KEY).catch(() => {});
}

async function inspectPage(page, rootSelector, requiredTexts = []) {
  await page.waitForSelector(rootSelector, { timeout: 15000 });
  return page.evaluate(({ rootSelector, requiredTexts, noiseNeedles }) => {
    const text = document.body.innerText || "";
    return {
      hasRoot: Boolean(document.querySelector(rootSelector)),
      requiredVisible: requiredTexts.every(item => text.includes(item)),
      noiseVisible: noiseNeedles.some(item => text.includes(item)),
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
      toggleChecked: Boolean(document.querySelector(".test-record-toggle input")?.checked),
      toggleVisible: Boolean(document.querySelector(".test-record-toggle")),
    };
  }, {
    rootSelector,
    requiredTexts,
    noiseNeedles: [NOISE_JOB_ID, NOISE_MODEL_ID, NOISE_BATCH_ID, "stage58 playwright"],
  });
}

async function setShowTestRecords(page, checked) {
  await page.locator(".test-record-toggle input").first().setChecked(checked);
  await page.waitForTimeout(900);
}

(async () => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const browser = await launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1366, height: 980 } });
  const page = await context.newPage();
  const pageErrors = [];
  const unsafeCalls = [];
  const seenUrls = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("dialog", dialog => dialog.dismiss());
  await installMockApi(page, unsafeCalls, seenUrls);

  await gotoPage(page, "/");
  await resetShowTestRecords(page);
  await gotoPage(page, "/");
  const dashboardDefault = await inspectPage(page, "#taskCenter", ["AI 一键翻唱", "单文件快速训练", "多文件批量精训", USER_JOB_ID]);
  await setShowTestRecords(page, true);
  const dashboardWithTests = await inspectPage(page, "#taskCenter", [NOISE_JOB_ID]);

  await resetShowTestRecords(page);
  await gotoPage(page, "/factory");
  const factoryDefault = await inspectPage(page, "#factoryBatchesDrawer", ["Clean user batch"]);
  await setShowTestRecords(page, true);
  if (await page.locator("#factoryBatchesBody").evaluate(node => Boolean(node.hidden)).catch(() => false)) {
    await page.click("#factoryBatchesToggleBtn");
    await page.waitForTimeout(400);
  }
  const factoryWithTests = await inspectPage(page, "#factoryBatchesDrawer", [NOISE_BATCH_ID]);

  await resetShowTestRecords(page);
  await gotoPage(page, "/studio");
  const studioDefault = await inspectPage(page, "#studioLibraryDrawer", ["Clean User Voice"]);
  await setShowTestRecords(page, true);
  const studioWithTests = await inspectPage(page, "#studioLibraryDrawer", [NOISE_JOB_ID]);

  await page.screenshot({ path: `${SCREENSHOT_DIR}/stage58_user_noise_ui_smoke.png`, fullPage: true });
  await browser.close();

  const includeParamSeen = seenUrls.some(url => /include_test_data=false/.test(url)) && seenUrls.some(url => /include_smoke=false/.test(url));
  const includeParamSeenAfterToggle = seenUrls.some(url => /include_test_data=true/.test(url)) && seenUrls.some(url => /include_smoke=true/.test(url));
  const failures = [];
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(" | ")}`);
  if (unsafeCalls.length) failures.push(`unsafe API calls: ${unsafeCalls.join(" | ")}`);
  if (!includeParamSeen || !includeParamSeenAfterToggle) failures.push("include_test_data/include_smoke query params were not observed in both states");
  for (const [name, result] of Object.entries({ dashboardDefault, factoryDefault, studioDefault })) {
    if (!result.hasRoot || !result.toggleVisible) failures.push(`${name}: core shell or test toggle missing`);
    if (!result.requiredVisible) failures.push(`${name}: required user entry/content missing`);
    if (result.noiseVisible) failures.push(`${name}: test noise visible by default`);
    if (result.overflow) failures.push(`${name}: horizontal overflow detected`);
    if (result.toggleChecked) failures.push(`${name}: test toggle should default off`);
  }
  for (const [name, result] of Object.entries({ dashboardWithTests, factoryWithTests, studioWithTests })) {
    if (!result.requiredVisible || !result.noiseVisible) failures.push(`${name}: test records were not visible after enabling toggle`);
    if (result.overflow) failures.push(`${name}: horizontal overflow detected after enabling toggle`);
    if (!result.toggleChecked) failures.push(`${name}: test toggle did not stay on`);
  }

  if (failures.length) {
    console.error(JSON.stringify({ ok: false, failures }, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify({
    ok: true,
    dashboardDefault,
    dashboardWithTests,
    factoryDefault,
    factoryWithTests,
    studioDefault,
    studioWithTests,
    includeParamSeen,
    includeParamSeenAfterToggle,
  }, null, 2));
})().catch(error => {
  console.error(error);
  process.exit(1);
});
