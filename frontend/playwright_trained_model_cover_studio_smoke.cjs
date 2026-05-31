const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const FACTORY_URL = `${BASE_URL}/factory`;
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9248;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage28_trained_model_cover_studio.png");

const PREFERRED_MODEL_ID = "v_b5c8427a";
const PREFERRED_SOURCE_JOB_ID = "train_d8cd4ed377ca";
const PREFERRED_SOURCE_AUDIO = "C:/Users/ASUS/Desktop/归不了岸的船.mp3";
const FALLBACK_SOURCE_AUDIO = "C:/Users/ASUS/Desktop/晚风失约.mp3";
const COVER_TIMEOUT_MS = 20 * 60 * 1000;

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`);
  }
  return payload;
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage28-cover-"));
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
    height: 1180,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

function isCompletedStatus(status = "") {
  return status === "completed" || status === "完成" || status === "已完成";
}

function isFailedStatus(status = "") {
  return status === "failed" || status === "失败";
}

function pickSourceAudio() {
  if (fs.existsSync(PREFERRED_SOURCE_AUDIO)) {
    return PREFERRED_SOURCE_AUDIO;
  }
  if (fs.existsSync(FALLBACK_SOURCE_AUDIO)) {
    return FALLBACK_SOURCE_AUDIO;
  }
  throw new Error(`No Stage 28 real source audio found. Tried: ${PREFERRED_SOURCE_AUDIO} / ${FALLBACK_SOURCE_AUDIO}`);
}

async function pickTrainedModel() {
  const models = await fetchJson(`${BASE_URL}/api/models?include_unavailable=true`);
  const items = Array.isArray(models) ? models : [];
  const usable = items.filter(item => item?.usable && item?.origin_kind === "trained_local");
  if (!usable.length) {
    throw new Error("No usable trained_local model available for Stage 28 smoke");
  }

  return (
    usable.find(item => item.model_id === PREFERRED_MODEL_ID)
    || usable.find(item => item.source_job_id === PREFERRED_SOURCE_JOB_ID)
    || usable[0]
  );
}

async function createBatch() {
  return fetchJson(`${BASE_URL}/api/batches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      batch_name: `stage28_trained_model_closure_${Date.now()}`,
      target_platforms: ["stage28-real-cover"],
      metadata: { source: "playwright_trained_model_cover_studio_smoke" },
    }),
  });
}

async function importTrack(batchId, audioPath) {
  const formData = new FormData();
  const fileName = path.basename(audioPath);
  formData.append("files", new Blob([fs.readFileSync(audioPath)], { type: "audio/mpeg" }), fileName);
  formData.append("titles_json", JSON.stringify([`stage28_real_cover_${path.parse(fileName).name}`]));
  formData.append("artist", "Stage28 Real Acceptance");
  formData.append("notes", "trained model -> cover -> factory -> studio closure");
  formData.append("metadata_json", JSON.stringify({ source: "playwright_trained_model_cover_studio_smoke" }));
  return fetchJson(`${BASE_URL}/api/batches/${batchId}/tracks/import`, {
    method: "POST",
    body: formData,
  });
}

async function createCoverJob(trackId, modelId) {
  return fetchJson(`${BASE_URL}/api/tracks/${trackId}/cover-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_id: modelId }),
  });
}

async function getTrackJobs(trackId) {
  return fetchJson(`${BASE_URL}/api/tracks/${trackId}/jobs?limit=20&offset=0`);
}

async function getJob(jobId) {
  return fetchJson(`${BASE_URL}/api/jobs/${jobId}`);
}

async function getStageLogs(jobId) {
  return fetchJson(`${BASE_URL}/api/jobs/${jobId}/stage-logs`);
}

function businessStages(stageLogs = []) {
  return (stageLogs || [])
    .map(item => item.stage_name)
    .filter(name => name && name !== "job_dispatch" && name !== "job_control");
}

async function waitForCoverCompletion(trackId, jobId, timeoutMs = COVER_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  let lastJob = null;
  let lastLogs = [];

  while (Date.now() < deadline) {
    const [job, logsPayload, trackJobs] = await Promise.all([
      getJob(jobId),
      getStageLogs(jobId),
      getTrackJobs(trackId),
    ]);
    lastJob = job;
    lastLogs = logsPayload.stage_logs || [];

    if (isCompletedStatus(job.status)) {
      const trackItem = (trackJobs.items || []).find(item => item.job_id === jobId) || null;
      return {
        outcome: "completed",
        job,
        stageLogs: lastLogs,
        trackJobs,
        trackItem,
      };
    }

    if (isFailedStatus(job.status) || job.current_stage === "failed") {
      const failureLog = [...lastLogs].reverse().find(item => item.status === "failed" || item.status === "失败");
      return {
        outcome: "failed",
        job,
        stageLogs: lastLogs,
        trackJobs,
        trackItem: (trackJobs.items || []).find(item => item.job_id === jobId) || null,
        failureStage: failureLog?.stage_name || job.current_stage || "",
        failureMessage: failureLog?.message || "",
      };
    }

    await delay(3000);
  }

  return {
    outcome: "timeout",
    job: lastJob,
    stageLogs: lastLogs,
    finalStage: lastJob?.current_stage || "",
  };
}

async function ensureDashboardFactoryContext(client, batchId, trackId, model) {
  await client.navigate(`${FACTORY_URL}?batch_id=${encodeURIComponent(batchId)}&track_id=${encodeURIComponent(trackId)}`);
  await client.waitFor("Boolean(document.querySelector('#factoryTrackOutcomeCard'))", 20000, "factory outcome card");
  await client.waitFor(
    `document.body.innerText.includes(${JSON.stringify(model.model_id)}) || document.body.innerText.includes(${JSON.stringify(model.model_name || model.model_id)})`,
    20000,
    "factory visible model label",
  );
  await client.waitFor(
    `document.body.innerText.includes(${JSON.stringify(model.source_job_id || "")}) || document.body.innerText.includes(${JSON.stringify(model.source_summary || "")})`,
    20000,
    "factory visible source summary",
  );
}

async function openStudioFromFactory(client) {
  await client.waitFor(
    `Boolean(document.querySelector('#factoryTrackOutcomeCard [data-studio-url], #factoryCurrentMasterCard [data-studio-url], #factoryTrackJobsList [data-studio-url]'))`,
    30000,
    "factory studio action visible",
  );
  await client.evaluate(`
    (() => {
      const button =
        document.querySelector('#factoryTrackOutcomeCard [data-studio-url]') ||
        document.querySelector('#factoryCurrentMasterCard [data-studio-url]') ||
        document.querySelector('#factoryTrackJobsList [data-studio-url]');
      button?.click();
      return button?.dataset?.studioUrl || "";
    })()
  `);
  await client.waitFor("document.readyState === 'complete'", 20000, "studio readyState");
}

async function verifyStudioContextAndSetMaster(client, trackId, coverJobId, model) {
  await client.waitFor("Boolean(document.getElementById('studioSourceContextCard'))", 20000, "studio source card");
  await client.waitFor(
    `document.body.innerText.includes(${JSON.stringify(trackId)})`,
    20000,
    "studio visible track id",
  );
  await client.waitFor(
    `document.body.innerText.includes(${JSON.stringify(model.source_job_id || "")}) || document.body.innerText.includes(${JSON.stringify(model.source_summary || "")})`,
    20000,
    "studio visible source summary",
  );
  await client.waitFor(
    `Boolean(document.querySelector('#studioSummaryDownloadBtn:not(.is-disabled)'))`,
    20000,
    "studio download available",
  );

  const currentMasterJobId = await client.evaluate(`
    fetch('/api/tracks/${trackId}/jobs?limit=20&offset=0')
      .then(resp => resp.json())
      .then(data => data.current_master_job_id || '')
  `);

  let masterSet = false;
  if (!currentMasterJobId) {
    await client.waitFor(
      `Boolean(document.querySelector('#studioTrackHistoryList [data-set-track-master-job-id="${coverJobId}"]'))`,
      20000,
      "set current master button",
    );
    await client.evaluate(`
      (() => {
        const button = document.querySelector('#studioTrackHistoryList [data-set-track-master-job-id="${coverJobId}"]');
        button?.click();
        return Boolean(button);
      })()
    `);
    await client.waitFor(
      `document.body.innerText.includes('当前主成品')`,
      20000,
      "studio current master badge",
    );
    masterSet = true;
  }

  return masterSet;
}

async function verifyFactoryMasterSync(client, batchId, trackId, coverJobId, model) {
  await client.navigate(`${FACTORY_URL}?batch_id=${encodeURIComponent(batchId)}&track_id=${encodeURIComponent(trackId)}`);
  await client.waitFor("Boolean(document.querySelector('#factoryCurrentMasterCard'))", 20000, "factory current master card");
  await client.waitFor(
    `document.body.innerText.includes(${JSON.stringify(coverJobId)})`,
    20000,
    "factory current master job visible",
  );
  await client.waitFor(
    `document.body.innerText.includes(${JSON.stringify(model.source_job_id || "")}) || document.body.innerText.includes(${JSON.stringify(model.source_summary || "")})`,
    20000,
    "factory current master source visible",
  );
}

async function main() {
  let chromeHandle = null;
  let client = null;
  let summary = {
    model_id: "",
    source_job_id: "",
    track_id: "",
    cover_job_id: "",
    final_stage: "",
    studio_url: "",
  };

  try {
    const health = await fetchJson(`${BASE_URL}/api/health`);
    if (!health?.engine) {
      throw new Error("Stage 28 smoke requires /api/health engine summary");
    }

    const model = await pickTrainedModel();
    const audioPath = pickSourceAudio();
    summary.model_id = model.model_id || "";
    summary.source_job_id = model.source_job_id || "";

    const batch = await createBatch();
    const imported = await importTrack(batch.batch_id, audioPath);
    const trackId = imported.imported_tracks?.[0]?.track_id;
    if (!trackId) {
      throw new Error(`Track import did not return a track_id: ${JSON.stringify(imported)}`);
    }
    summary.track_id = trackId;

    const created = await createCoverJob(trackId, model.model_id);
    if (!created.job_id) {
      throw new Error(`Cover job did not return job_id: ${JSON.stringify(created)}`);
    }
    summary.cover_job_id = created.job_id;

    const coverResult = await waitForCoverCompletion(trackId, created.job_id);
    summary.final_stage = coverResult.job?.current_stage || businessStages(coverResult.stageLogs || []).slice(-1)[0] || "";

    if (coverResult.outcome !== "completed") {
      const failureStage = coverResult.failureStage || summary.final_stage || "";
      const failureMessage = coverResult.failureMessage || coverResult.job?.generated_model_summary || coverResult.job?.status || "";
      throw new Error(
        [
          "real_cover_not_completed",
          `model_id=${summary.model_id}`,
          `source_job_id=${summary.source_job_id}`,
          `track_id=${summary.track_id}`,
          `cover_job_id=${summary.cover_job_id}`,
          `final_stage=${failureStage}`,
          `failure=${failureMessage}`,
        ].join("\n"),
      );
    }

    const trackItem = coverResult.trackItem;
    if (!trackItem?.can_open_studio || !trackItem?.studio_url) {
      throw new Error(`Completed cover job missing studio_url: ${JSON.stringify(trackItem)}`);
    }
    summary.studio_url = trackItem.studio_url;

    chromeHandle = launchChrome();
    client = await prepareClient();

    await ensureDashboardFactoryContext(client, batch.batch_id, trackId, model);
    await openStudioFromFactory(client);
    const masterSet = await verifyStudioContextAndSetMaster(client, trackId, created.job_id, model);
    await verifyFactoryMasterSync(client, batch.batch_id, trackId, created.job_id, model);

    await client.screenshot(SCREENSHOT_PATH);

    console.log("STAGE28_TRAINED_MODEL_COVER_SMOKE PASS");
    console.log(`model_id=${summary.model_id}`);
    console.log(`source_job_id=${summary.source_job_id}`);
    console.log(`track_id=${summary.track_id}`);
    console.log(`cover_job_id=${summary.cover_job_id}`);
    console.log(`final_stage=${summary.final_stage}`);
    console.log(`studio_url=${summary.studio_url}`);
    console.log(`audio_path=${audioPath}`);
    console.log(`master_set=${masterSet ? "yes" : "already_set"}`);
    console.log(`screenshot=${SCREENSHOT_PATH}`);
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
  console.error("STAGE28_TRAINED_MODEL_COVER_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
