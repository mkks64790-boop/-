const os = require("os");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9257;

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`);
  }
  return payload;
}

function isActiveTrain(job) {
  return job.job_type === "train" && job.current_stage === "train_core" && ["running", "processing", "训练中", "进行中", "处理中"].includes(job.status || "");
}

async function pickTrainJob() {
  const payload = await fetchJson(`${BASE_URL}/api/jobs?job_type=train&limit=100&offset=0`);
  const jobs = (payload.items || []).filter(item => item.job_type === "train" && item.job_id);
  const job = jobs.find(isActiveTrain) || jobs.find(item => item.current_stage === "train_core") || jobs[0];
  if (!job) throw new Error("No train job available for Stage 37A roadmap smoke");
  return job;
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
          const { resolve: resolvePending, reject: rejectPending } = this.pending.get(payload.id);
          this.pending.delete(payload.id);
          payload.error ? rejectPending(new Error(payload.error.message || JSON.stringify(payload.error))) : resolvePending(payload.result || {});
        }
      });
      socket.addEventListener("error", onError);
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression, { awaitPromise = true } = {}) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
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

  close() {
    try {
      this.ws?.close();
    } catch {
      // Ignore close errors during shutdown.
    }
  }
}

function launchChrome() {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage37a-roadmap-"));
  const chrome = spawn(
    CHROME_PATH,
    [
      "--headless=new",
      "--disable-gpu",
      "--mute-audio",
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
  const targets = await fetchJson(`http://127.0.0.1:${REMOTE_DEBUG_PORT}/json/list`);
  const pageTarget = targets.find(target => target.type === "page");
  if (!pageTarget?.webSocketDebuggerUrl) throw new Error("No Chrome page target available");
  const client = new CDPClient(pageTarget.webSocketDebuggerUrl);
  await client.connect();
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    const job = await pickTrainJob();
    chromeHandle = launchChrome();
    client = await prepareClient();
    await client.navigate(`${BASE_URL}/`);
    await client.waitFor("Boolean(document.getElementById('jobDetailPanel'))", 20000, "job detail panel");
    await client.evaluate(`document.dispatchEvent(new CustomEvent('feishark:focus-job', { detail: { jobId: ${JSON.stringify(job.job_id)} } }))`);
    await client.waitFor("document.getElementById('jobDetailTitle')?.innerText.includes(" + JSON.stringify(job.voice_name || job.job_id) + ")", 20000, "train job focused");
    await client.waitFor("Boolean(document.querySelector('.train-stage-roadmap'))", 20000, "train roadmap visible");

    const result = await client.evaluate(`(() => ({
      route: document.querySelector('.train-stage-roadmap')?.dataset.route || '',
      stepCount: document.querySelectorAll('.train-stage-step').length,
      text: document.querySelector('#jobSummaryCard')?.innerText || '',
      hasOldFallback: (document.querySelector('#jobSummaryCard')?.innerText || '').includes('等待当前阶段完成。'),
      hasTechnicalPanel: Boolean(document.getElementById('jobTechnicalDrawer')),
      hasStageLogsPanel: Boolean(document.getElementById('jobStageLogsDrawer')),
    }))()`);

    if (result.stepCount !== 9) throw new Error(`Expected 9 train roadmap steps, got ${JSON.stringify(result)}`);
    if (!result.text.includes("训练阶段路线图")) throw new Error(`Missing roadmap title: ${JSON.stringify(result)}`);
    if (!result.text.includes("索引训练") || !result.text.includes("模型登记")) throw new Error(`Missing downstream stages: ${JSON.stringify(result)}`);
    if (result.hasOldFallback && job.job_type === "train" && job.current_stage) {
      throw new Error(`Train next-step still uses generic fallback: ${JSON.stringify(result)}`);
    }
    if (!result.hasTechnicalPanel || !result.hasStageLogsPanel) throw new Error(`Old detail structure missing: ${JSON.stringify(result)}`);
    if (job.current_stage === "train_core" && isActiveTrain(job) && !result.text.includes("核心训练是最长阶段")) {
      throw new Error(`Missing core-training guard: ${JSON.stringify(result)}`);
    }

    console.log("STAGE37A_TRAINING_PROGRESS_ROADMAP_SMOKE PASS");
    console.log(`job_id=${job.job_id}`);
    console.log(`current_stage=${job.current_stage || ""}`);
    console.log(`status=${job.status || ""}`);
    console.log(`route=${result.route}`);
    console.log(`step_count=${result.stepCount}`);
  } finally {
    client?.close();
    if (chromeHandle?.chrome && !chromeHandle.chrome.killed) chromeHandle.chrome.kill("SIGKILL");
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
  console.error("STAGE37A_TRAINING_PROGRESS_ROADMAP_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
