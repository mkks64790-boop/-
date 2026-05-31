const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9250;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage30b_studio_product_shell.png");

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

function isCompletedStatus(status = "") {
  return status === "completed" || status === "完成" || status === "已完成";
}

function toAbsoluteUrl(url = "") {
  if (!url) return "";
  return url.startsWith("http") ? url : `${BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

function buildStudioUrl(job = {}) {
  if (job.studio_url) return job.studio_url;
  if (!job.job_id) return "";
  const params = new URLSearchParams();
  if (job.batch_id) params.set("batch_id", job.batch_id);
  if (job.track_id) params.set("track_id", job.track_id);
  params.set("job_id", job.job_id);
  if (job.final_artifact_id || job.artifact_id) {
    params.set("artifact_id", job.final_artifact_id || job.artifact_id);
  }
  return `/studio?${params.toString()}`;
}

async function pickStudioJob() {
  const payload = await fetchJson(`${BASE_URL}/api/jobs?job_type=cover&limit=100&offset=0`);
  const items = Array.isArray(payload.items) ? payload.items : [];
  const candidates = items
    .filter(job => isCompletedStatus(job.status))
    .filter(job => buildStudioUrl(job));

  if (!candidates.length) {
    throw new Error("No completed cover job found that can be converted to a Studio URL. Stage 30B smoke requires an existing Studio job.");
  }

  return (
    candidates.find(job => job.voice_model_source_summary || job.voice_model_source_job_id)
    || candidates[0]
  );
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
          const { resolve: resolvePending, reject: rejectPending } = this.pending.get(payload.id);
          this.pending.delete(payload.id);
          if (payload.error) {
            rejectPending(new Error(payload.error.message || JSON.stringify(payload.error)));
          } else {
            resolvePending(payload.result || {});
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage30b-studio-"));
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
    width: 1520,
    height: 1120,
    deviceScaleFactor: 1,
    mobile: false,
  });
  return client;
}

async function verifyStudioProductShell(client, studioUrl, job) {
  await client.navigate(studioUrl);
  await client.waitFor("Boolean(document.getElementById('studioSourceContextCard'))", 20000, "studio source context card");
  await client.waitFor("Boolean(document.getElementById('studioSummaryDownloadBtn'))", 20000, "studio summary download button");
  await client.waitFor("Boolean(document.getElementById('studioEffectRackList'))", 20000, "studio effect rack");
  await client.waitFor(
    "Boolean(document.querySelector('#studioSummaryDownloadBtn:not(.is-disabled)'))",
    20000,
    "download button enabled",
  );
  await client.waitFor(
    "document.body.innerText.includes('后处理参数草稿') && document.body.innerText.includes('Effect Rack')",
    20000,
    "effect rack draft copy visible",
  );

  const expectedModelText = job.voice_model_source_job_id || job.voice_model_source_summary || job.voice_model_id || job.voice_name || "";
  if (expectedModelText) {
    await client.waitFor(
      `document.body.innerText.includes(${JSON.stringify(expectedModelText)})`,
      20000,
      "model/source summary visible",
    );
  }

  if (job.track_id) {
    await client.waitFor(
      `document.body.innerText.includes(${JSON.stringify(job.track_id)})`,
      20000,
      "track_id visible",
    );
  }

  await client.waitFor(
    "Boolean(document.querySelector('#studioEffectRackList [data-effect-slot-toggle=\"eq\"]'))",
    20000,
    "EQ slot toggle visible",
  );
  await client.evaluate(`
    (() => {
      const toggle = document.querySelector('#studioEffectRackList [data-effect-slot-toggle="eq"]');
      if (!toggle.checked) toggle.click();
      return toggle.checked;
    })()
  `);
  await client.waitFor(
    "document.querySelector('#studioEffectRackList [data-effect-slot-toggle=\"eq\"]')?.checked === true",
    10000,
    "EQ slot toggled on",
  );

  await client.navigate(studioUrl);
  await client.waitFor(
    "document.querySelector('#studioEffectRackList [data-effect-slot-toggle=\"eq\"]')?.checked === true",
    20000,
    "EQ slot draft restored after refresh",
  );

  await client.evaluate(`
    (() => {
      const button = document.getElementById('studioTechnicalToggleBtn');
      button?.click();
      return button?.getAttribute('aria-expanded') || '';
    })()
  `);
  await client.waitFor(
    "document.getElementById('studioTechnicalToggleBtn')?.getAttribute('aria-expanded') === 'true' && document.getElementById('studioTechnicalBody')?.hidden === false",
    10000,
    "technical drawer opened",
  );
  await client.evaluate("document.getElementById('studioTechnicalToggleBtn')?.click()");
  await client.waitFor(
    "document.getElementById('studioTechnicalToggleBtn')?.getAttribute('aria-expanded') === 'false' && document.getElementById('studioTechnicalBody')?.hidden === true",
    10000,
    "technical drawer closed",
  );
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    const job = await pickStudioJob();
    const studioUrl = toAbsoluteUrl(buildStudioUrl(job));
    if (!studioUrl) {
      throw new Error(`Selected job does not expose studio_url: ${JSON.stringify(job)}`);
    }

    chromeHandle = launchChrome();
    client = await prepareClient();
    await verifyStudioProductShell(client, studioUrl, job);
    await client.screenshot(SCREENSHOT_PATH);

    console.log("STAGE30B_STUDIO_PRODUCT_SHELL_SMOKE PASS");
    console.log(`studio_url=${studioUrl}`);
    console.log(`job_id=${job.job_id || ""}`);
    console.log(`track_id=${job.track_id || ""}`);
    console.log(`artifact_id=${job.final_artifact_id || job.artifact_id || ""}`);
    console.log(`source_job_id=${job.voice_model_source_job_id || ""}`);
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
  console.error("STAGE30B_STUDIO_PRODUCT_SHELL_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
