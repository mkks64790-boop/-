const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const FACTORY_URL = `${BASE_URL}/factory`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9245;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage25_track_master_registry.png");
const AUDIO_A = path.join(__dirname, "..", "shared_data", "uploads", "suno_test.wav");
const AUDIO_B = path.join(__dirname, "..", "shared_data", "uploads", "task_49e0a0c6b29b.wav");

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`HTTP ${response.status} for ${url}: ${body}`);
  }
  return response.json();
}

async function waitForDebugger(timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const version = await fetchJson(`http://127.0.0.1:${REMOTE_DEBUG_PORT}/json/version`);
      if (version.webSocketDebuggerUrl) return version;
    } catch {
      // Chrome may still be booting.
    }
    await delay(250);
  }
  throw new Error("Chrome remote debugger did not become ready in time");
}

async function listTargets() {
  return fetchJson(`http://127.0.0.1:${REMOTE_DEBUG_PORT}/json/list`);
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    await new Promise((resolve, reject) => {
      const socket = new WebSocket(this.wsUrl);
      const onError = event => reject(new Error(`CDP websocket error: ${event?.message || "unknown"}`));

      socket.addEventListener("open", () => {
        socket.removeEventListener("error", onError);
        this.ws = socket;
        resolve();
      });

      socket.addEventListener("message", event => {
        const payload = JSON.parse(event.data);
        if (payload.id && this.pending.has(payload.id)) {
          const { resolve, reject } = this.pending.get(payload.id);
          this.pending.delete(payload.id);
          if (payload.error) {
            reject(new Error(payload.error.message || JSON.stringify(payload.error)));
          } else {
            resolve(payload.result || {});
          }
        }
      });

      socket.addEventListener("error", onError);
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const message = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(message);
    });
  }

  async evaluate(expression, { awaitPromise = true } = {}) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise,
      returnByValue: true,
    });
    return result.result?.value;
  }

  async waitFor(expression, timeoutMs = 20000, label = expression) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const value = await this.evaluate(expression);
        if (value) return value;
      } catch {
        // Ignore transient navigation/runtime errors while waiting.
      }
      await delay(250);
    }
    throw new Error(`Timed out waiting for: ${label}`);
  }

  async navigate(url) {
    await this.send("Page.navigate", { url });
    await this.waitFor("document.readyState === 'complete'", 20000, `readyState complete for ${url}`);
  }

  async screenshot(targetPath) {
    const data = await this.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    fs.writeFileSync(targetPath, Buffer.from(data.data, "base64"));
  }

  close() {
    try {
      this.ws?.close();
    } catch {
      // Ignore close errors during shutdown.
    }
  }
}

function launchChrome() {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage25-master-"));
  const chrome = spawn(
    CHROME_PATH,
    [
      "--headless=new",
      "--disable-gpu",
      "--mute-audio",
      "--autoplay-policy=no-user-gesture-required",
      `--remote-debugging-port=${REMOTE_DEBUG_PORT}`,
      `--user-data-dir=${userDataDir}`,
      "about:blank",
    ],
    { stdio: "ignore", windowsHide: true },
  );
  return { chrome, userDataDir };
}

async function prepareClient() {
  await waitForDebugger();
  const targets = await listTargets();
  const pageTarget = targets.find(target => target.type === "page");
  if (!pageTarget?.webSocketDebuggerUrl) {
    throw new Error("No Chrome page target available for CDP connection");
  }

  const client = new CDPClient(pageTarget.webSocketDebuggerUrl);
  await client.connect();
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 1600,
    height: 1200,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

async function pickUsableModel() {
  const models = await fetchJson(`${BASE_URL}/api/models`);
  const usable = Array.isArray(models) ? models.find(item => item && item.model_id) : null;
  if (!usable?.model_id) {
    throw new Error("No usable cover model available for Stage 25 smoke");
  }
  return usable;
}

async function createBatch() {
  return fetchJson(`${BASE_URL}/api/batches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      batch_name: `stage25_track_master_registry_${Date.now()}`,
      target_platforms: ["track-master-registry"],
      metadata: { smoke: true, source: "playwright_track_master_registry_smoke" },
    }),
  });
}

async function importTracks(batchId) {
  const formData = new FormData();
  formData.append("files", new Blob([fs.readFileSync(AUDIO_A)], { type: "audio/wav" }), "stage25-a.wav");
  formData.append("files", new Blob([fs.readFileSync(AUDIO_B)], { type: "audio/wav" }), "stage25-b.wav");
  formData.append("titles_json", JSON.stringify(["stage25_master_track_a", "stage25_master_track_b"]));
  formData.append("artist", "stage25_master_artist");
  formData.append("notes", "playwright track master registry smoke");
  formData.append("metadata_json", JSON.stringify({ smoke: true, source: "playwright_track_master_registry_smoke" }));

  return fetchJson(`${BASE_URL}/api/batches/${batchId}/tracks/import`, {
    method: "POST",
    body: formData,
  });
}

async function createCoverJob(trackId, modelId) {
  const payload = await fetchJson(`${BASE_URL}/api/tracks/${trackId}/cover-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_id: modelId }),
  });
  if (!payload.job_id) {
    throw new Error(`Cover job did not return job_id: ${JSON.stringify(payload)}`);
  }
  return payload.job_id;
}

async function fetchTrackJobs(trackId) {
  return fetchJson(`${BASE_URL}/api/tracks/${trackId}/jobs?limit=20&offset=0`);
}

async function waitForCompletedJob(trackId, jobId, timeoutMs = 160000) {
  const deadline = Date.now() + timeoutMs;
  let latestItem = null;
  while (Date.now() < deadline) {
    const latest = await fetchTrackJobs(trackId);
    const item = latest.items?.find(candidate => candidate.job_id === jobId);
    if (item) {
      latestItem = item;
      if (item.can_open_studio && item.studio_url) return item;
    }
    await delay(3000);
  }
  throw new Error(`Timed out waiting for completed job ${jobId}: ${JSON.stringify(latestItem)}`);
}

async function ensureFactoryPage(client) {
  await client.navigate(FACTORY_URL);
  await client.waitFor("Boolean(document.querySelector('#factoryBatchesList'))", 20000, "factoryBatchesList");
  await client.waitFor("Boolean(document.querySelector('#factoryTracksList'))", 20000, "factoryTracksList");
  await client.waitFor("Boolean(document.querySelector('#factoryTrackJobsList'))", 20000, "factoryTrackJobsList");
}

async function selectBatchAndTrack(client, batchId, trackId) {
  await client.evaluate(`document.getElementById("factoryRefreshBtn")?.click();`);
  await client.waitFor(
    `Boolean(document.querySelector('#factoryBatchesList [data-batch-id="${batchId}"]'))`,
    20000,
    `batch ${batchId} visible`,
  );
  await client.evaluate(`
    (() => {
      const batch = document.querySelector('#factoryBatchesList [data-batch-id="${batchId}"]');
      batch?.click();
      return Boolean(batch);
    })()
  `);
  await client.waitFor(
    `Boolean(document.querySelector('#factoryTracksList [data-track-id="${trackId}"]'))`,
    20000,
    `track ${trackId} visible`,
  );
  await client.evaluate(`
    (() => {
      const track = document.querySelector('#factoryTracksList [data-track-id="${trackId}"]');
      track?.click();
      return Boolean(track);
    })()
  `);
  await client.waitFor(
    `document.getElementById("factoryTrackSubtitle")?.textContent?.includes("stage25_master_track_b") || document.getElementById("factoryTrackTitle")?.textContent?.includes(${JSON.stringify(trackId)})`,
    20000,
    "selected stage25 track detail",
  );
}

async function clickLatestOpenStudio(client, latestJobId) {
  await client.evaluate(`document.getElementById("factoryReloadTrackBtn")?.click();`);
  await client.waitFor(
    `Boolean(document.querySelector('#factoryTrackJobsList [data-track-job-id="${latestJobId}"] [data-studio-url], #factoryTrackOutcomeCard [data-studio-url]'))`,
    45000,
    "latest Studio action visible",
  );
  await client.evaluate(`
    (() => {
      const button =
        document.querySelector('#factoryTrackJobsList [data-track-job-id="${latestJobId}"] [data-studio-url]') ||
        document.querySelector('#factoryTrackOutcomeCard [data-studio-url]');
      button?.click();
      return Boolean(button);
    })()
  `);
}

async function setOlderVersionAsMaster(client, trackId, latestJobId, olderJobId) {
  await client.waitFor("document.readyState === 'complete'", 20000, "studio readyState");
  await client.waitFor(
    `Boolean(document.querySelector('#studioTrackHistoryPanel:not([hidden])'))`,
    20000,
    "track history panel visible",
  );
  await client.waitFor(
    `document.getElementById('studioSourceMetaGrid')?.textContent?.includes(${JSON.stringify(trackId)})`,
    20000,
    "source track id visible",
  );
  await client.waitFor(
    `document.querySelectorAll('#studioTrackHistoryList [data-track-history-job-id]').length >= 2`,
    20000,
    "at least two track history items",
  );
  await client.waitFor(
    `document.querySelector('#studioTrackHistoryList [data-track-history-job-id="${latestJobId}"]')?.innerText?.includes('当前试听') && document.querySelector('#studioTrackHistoryList [data-track-history-job-id="${latestJobId}"]')?.innerText?.includes('最新版本')`,
    20000,
    "latest version badges visible",
  );

  await client.evaluate(`
    (() => {
      const selectButton = document.querySelector('#studioTrackHistoryList [data-track-history-job-id="${olderJobId}"]');
      selectButton?.click();
      return Boolean(selectButton);
    })()
  `);
  await client.waitFor(
    `document.getElementById('studioCurrentJobId')?.textContent?.includes(${JSON.stringify(olderJobId)})`,
    20000,
    "older version selected for listening",
  );
  await client.waitFor(
    `document.getElementById('studioVersionHint')?.textContent?.includes('不是这个 Track 的最新版本')`,
    20000,
    "older version hint visible",
  );

  await client.waitFor(
    `Boolean(document.querySelector('#studioTrackHistoryList [data-set-track-master-job-id="${olderJobId}"]'))`,
    20000,
    "set current master button visible",
  );
  await client.evaluate(`
    (() => {
      const button = document.querySelector('#studioTrackHistoryList [data-set-track-master-job-id="${olderJobId}"]');
      button?.click();
      return Boolean(button);
    })()
  `);
  await client.waitFor(
    `document.querySelector('#studioTrackHistoryList [data-track-history-job-id="${olderJobId}"]')?.innerText?.includes('当前主成品')`,
    20000,
    "older version marked as current master",
  );
  await client.waitFor(
    `document.getElementById('studioVersionHint')?.textContent?.includes('已经被设为当前主成品')`,
    20000,
    "current master hint visible",
  );
  await client.waitFor(
    `document.querySelector('#studioTrackHistoryList [data-track-history-job-id="${latestJobId}"]')?.innerText?.includes('最新版本') && !document.querySelector('#studioTrackHistoryList [data-track-history-job-id="${latestJobId}"]')?.innerText?.includes('当前主成品')`,
    20000,
    "latest version still distinct from current master",
  );
}

async function verifyFactoryMasterCard(client, batchId, trackId, olderJobId) {
  await client.navigate(`${BASE_URL}/factory?batch_id=${encodeURIComponent(batchId)}&track_id=${encodeURIComponent(trackId)}`);
  await client.waitFor("Boolean(document.querySelector('#factoryTrackJobsList'))", 20000, "factoryTrackJobsList after return");
  await client.waitFor(
    `document.getElementById('factoryCurrentMasterCard') && !document.getElementById('factoryCurrentMasterCard').hidden`,
    20000,
    "factory current master card visible",
  );
  await client.waitFor(
    `document.getElementById('factoryCurrentMasterCard')?.textContent?.includes(${JSON.stringify(olderJobId)})`,
    20000,
    "factory current master card points to older job",
  );
  await client.waitFor(
    `document.querySelector('#factoryTrackJobsList [data-track-job-id="${olderJobId}"]')?.innerText?.includes('当前主成品')`,
    20000,
    "factory track job row marks current master",
  );
}

async function main() {
  let chromeHandle = null;
  let client = null;

  try {
    if (!fs.existsSync(AUDIO_A) || !fs.existsSync(AUDIO_B)) {
      throw new Error(`Stage 25 audio fixtures missing: ${AUDIO_A} / ${AUDIO_B}`);
    }

    const model = await pickUsableModel();
    const batch = await createBatch();
    const imported = await importTracks(batch.batch_id);
    const trackId = imported.imported_tracks?.[1]?.track_id || imported.imported_tracks?.[0]?.track_id;
    if (!trackId) {
      throw new Error("Track import did not return a usable track id");
    }

    const olderJobId = await createCoverJob(trackId, model.model_id);
    const olderCompleted = await waitForCompletedJob(trackId, olderJobId);
    await delay(1500);
    const latestJobId = await createCoverJob(trackId, model.model_id);
    const latestCompleted = await waitForCompletedJob(trackId, latestJobId);

    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureFactoryPage(client);
    await selectBatchAndTrack(client, batch.batch_id, trackId);
    await clickLatestOpenStudio(client, latestCompleted.job_id);
    await setOlderVersionAsMaster(client, trackId, latestCompleted.job_id, olderCompleted.job_id);
    await verifyFactoryMasterCard(client, batch.batch_id, trackId, olderCompleted.job_id);

    await client.screenshot(SCREENSHOT_PATH);
    console.log("TRACK_MASTER_REGISTRY_PLAYWRIGHT_SMOKE PASS");
    console.log(`Screenshot: ${SCREENSHOT_PATH}`);
    console.log(`Track: ${trackId}`);
    console.log(`Latest Job: ${latestCompleted.job_id}`);
    console.log(`Current Master Job: ${olderCompleted.job_id}`);
  } finally {
    client?.close();
    if (chromeHandle?.chrome && !chromeHandle.chrome.killed) {
      chromeHandle.chrome.kill("SIGKILL");
    }
    if (chromeHandle?.userDataDir) {
      try {
        fs.rmSync(chromeHandle.userDataDir, { recursive: true, force: true });
      } catch {
        // Ignore temp profile cleanup failures on Windows.
      }
    }
  }
}

main().catch(error => {
  console.error("TRACK_MASTER_REGISTRY_PLAYWRIGHT_SMOKE FAIL");
  console.error(error);
  process.exitCode = 1;
});
