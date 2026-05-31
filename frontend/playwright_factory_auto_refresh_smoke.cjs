const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const FACTORY_URL = `${BASE_URL}/factory`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9238;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage22_factory_auto_refresh.png");
const AUDIO_A = path.join(__dirname, "..", "shared_data", "uploads", "suno_test.wav");
const AUDIO_B = path.join(__dirname, "..", "shared_data", "uploads", "task_49e0a0c6b29b.wav");

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage22-factory-"));
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
    height: 1100,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

async function pickUsableModel() {
  const models = await fetchJson(`${BASE_URL}/api/models`);
  const usable = Array.isArray(models) ? models.find(item => item && item.model_id) : null;
  if (!usable?.model_id) {
    throw new Error("No usable cover model available for Stage 22 smoke");
  }
  return usable;
}

async function createBatch() {
  return fetchJson(`${BASE_URL}/api/batches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      batch_name: `stage22_factory_auto_refresh_${Date.now()}`,
      target_platforms: ["factory-auto-refresh"],
      metadata: { smoke: true, source: "playwright_factory_auto_refresh_smoke" },
    }),
  });
}

async function importTracks(batchId) {
  const formData = new FormData();
  formData.append("files", new Blob([fs.readFileSync(AUDIO_A)], { type: "audio/wav" }), "stage22-auto-a.wav");
  formData.append("files", new Blob([fs.readFileSync(AUDIO_B)], { type: "audio/wav" }), "stage22-auto-b.wav");
  formData.append("titles_json", JSON.stringify(["stage22_auto_track_a", "stage22_auto_track_b"]));
  formData.append("artist", "stage22_auto_artist");
  formData.append("notes", "playwright auto refresh smoke");
  formData.append("metadata_json", JSON.stringify({ smoke: true, source: "playwright_factory_auto_refresh_smoke" }));

  return fetchJson(`${BASE_URL}/api/batches/${batchId}/tracks/import`, {
    method: "POST",
    body: formData,
  });
}

async function fetchTrackJobs(trackId) {
  return fetchJson(`${BASE_URL}/api/tracks/${trackId}/jobs?limit=10&offset=0`);
}

async function ensureFactoryPage(client) {
  await client.navigate(FACTORY_URL);
  await client.waitFor("Boolean(document.querySelector('#factoryBatchesList'))", 20000, "factoryBatchesList");
  await client.waitFor("Boolean(document.querySelector('#factoryTracksList'))", 20000, "factoryTracksList");
  await client.waitFor("Boolean(document.querySelector('#factoryCoverModelSelect'))", 20000, "factoryCoverModelSelect");
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
    `document.getElementById("factoryTrackTitle")?.textContent?.includes(${JSON.stringify(trackId)}) || document.getElementById("factoryTrackSubtitle")?.textContent?.includes("stage22_auto_track_b")`,
    20000,
    "selected track detail",
  );
}

async function triggerCoverJob(client, modelId) {
  await client.waitFor(
    `(() => {
      const select = document.getElementById("factoryCoverModelSelect");
      return Boolean(select && select.options.length > 0 && !select.disabled);
    })()`,
    20000,
    "cover model select ready",
  );

  await client.evaluate(`
    (() => {
      const select = document.getElementById("factoryCoverModelSelect");
      if (!select) return false;
      select.value = ${JSON.stringify(modelId)};
      select.dispatchEvent(new Event("change", { bubbles: true }));
      return select.value;
    })()
  `);

  await client.evaluate(`document.getElementById("factoryCreateCoverJobBtn")?.click();`);
  await client.waitFor(
    "document.querySelectorAll('#factoryTrackJobsList [data-track-job-id]').length >= 1",
    30000,
    "track jobs rendered after create",
  );
}

async function waitForTrackJob(trackId, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() < deadline) {
    latest = await fetchTrackJobs(trackId);
    const item = latest.items?.[0];
    if (item?.job_id) return item;
    await delay(1000);
  }
  throw new Error(`Timed out waiting for track job: ${JSON.stringify(latest)}`);
}

async function waitForCompletedOrStableJob(trackId, timeoutMs = 150000) {
  const deadline = Date.now() + timeoutMs;
  let latestJob = null;
  while (Date.now() < deadline) {
    const latest = await fetchTrackJobs(trackId);
    const item = latest.items?.[0];
    if (item?.job_id) {
      latestJob = item;
      if (item.can_open_studio || item.final_artifact_download_url || item.status === "失败") {
        return item;
      }
    }
    await delay(3000);
  }
  return latestJob;
}

async function verifyAutoRefreshUi(client, job) {
  if (!job?.job_id) {
    throw new Error("No job available for auto refresh verification");
  }

  await client.waitFor(
    `Boolean(document.querySelector('#factoryTrackJobsList [data-track-job-id="${job.job_id}"]'))`,
    30000,
    "track job row visible without manual track reload",
  );

  const hasCompletedActions = Boolean(job.can_open_studio || job.final_artifact_download_url);
  if (!hasCompletedActions) {
    await client.waitFor(
      `document.getElementById("factoryTrackJobsSummary")?.textContent?.includes("自动刷新中") || Boolean(document.querySelector('#factoryTrackOutcomeCard:not([hidden])'))`,
      30000,
      "active auto refresh state visible",
    );
    return;
  }

  await client.waitFor(
    `Boolean(document.querySelector('#factoryTrackOutcomeCard [data-studio-url], #factoryTrackJobsList [data-track-job-id="${job.job_id}"] [data-studio-url]'))`,
    45000,
    "Studio action appeared via auto refresh",
  );
  await client.waitFor(
    `Boolean(document.querySelector('#factoryTrackOutcomeCard [data-download-url], #factoryTrackJobsList [data-track-job-id="${job.job_id}"] [data-download-url]'))`,
    45000,
    "download action appeared via auto refresh",
  );
}

async function verifyDrawerStatePreserved(client) {
  await client.waitFor(
    `document.getElementById("factoryStatusText")?.textContent?.includes("自动观察中") || document.getElementById("factoryTrackJobsSummary")?.textContent?.includes("自动刷新中")`,
    30000,
    "factory auto refresh active",
  );
  await client.evaluate(`
    (() => {
      document.getElementById("factoryLyricsToggleBtn")?.click();
      return true;
    })()
  `);
  await client.waitFor(
    `document.getElementById("factoryLyricsBody")?.hidden === true`,
    5000,
    "lyrics drawer collapsed",
  );
  await delay(5000);
  await client.waitFor(
    `document.getElementById("factoryLyricsBody")?.hidden === true`,
    5000,
    "lyrics drawer remained collapsed after auto refresh interval",
  );
}

async function main() {
  let chromeHandle = null;
  let client = null;

  try {
    if (!fs.existsSync(AUDIO_A) || !fs.existsSync(AUDIO_B)) {
      throw new Error(`Stage 22 audio fixtures missing: ${AUDIO_A} / ${AUDIO_B}`);
    }

    const model = await pickUsableModel();
    const batch = await createBatch();
    const imported = await importTracks(batch.batch_id);
    const trackId = imported.imported_tracks?.[1]?.track_id || imported.imported_tracks?.[0]?.track_id;
    if (!trackId) {
      throw new Error("Track import did not return a usable track id");
    }

    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureFactoryPage(client);
    await selectBatchAndTrack(client, batch.batch_id, trackId);
    await triggerCoverJob(client, model.model_id);

    const relatedJob = await waitForTrackJob(trackId);
    await client.waitFor(
      `Boolean(document.querySelector('#factoryTrackJobsList [data-track-job-id="${relatedJob.job_id}"]'))`,
      30000,
      "related job initially rendered",
    );
    await verifyDrawerStatePreserved(client);

    const completedOrStable = await waitForCompletedOrStableJob(trackId);
    await verifyAutoRefreshUi(client, completedOrStable || relatedJob);

    await client.screenshot(SCREENSHOT_PATH);
    console.log("FACTORY_AUTO_REFRESH_PLAYWRIGHT_SMOKE PASS");
    console.log(`Screenshot: ${SCREENSHOT_PATH}`);
    console.log(`Track: ${trackId}`);
    console.log(`Job: ${(completedOrStable || relatedJob).job_id}`);
    console.log(`Status: ${(completedOrStable || relatedJob).status || "pending"}`);
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
  console.error("FACTORY_AUTO_REFRESH_PLAYWRIGHT_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
