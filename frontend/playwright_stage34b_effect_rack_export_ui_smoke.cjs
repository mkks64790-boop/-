const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9254;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage34b_effect_rack_export_ui.png");

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

async function pickStudioJobWithArtifact() {
  const payload = await fetchJson(`${BASE_URL}/api/jobs?job_type=cover&limit=100&offset=0`);
  const jobs = (payload.items || [])
    .filter(job => isCompletedStatus(job.status))
    .filter(job => job.track_id);

  for (const job of jobs) {
    const artifacts = await fetchJson(`${BASE_URL}/api/jobs/${encodeURIComponent(job.job_id)}/artifacts`);
    const artifact = (artifacts.artifacts || []).find(item => item.artifact_id && item.download_url && item.artifact_type === "cover_master")
      || (artifacts.artifacts || []).find(item => item.artifact_id && item.download_url && item.is_final)
      || (artifacts.artifacts || []).find(item => item.artifact_id && item.download_url);
    if (!artifact) continue;

    const params = new URLSearchParams();
    if (job.batch_id) params.set("batch_id", job.batch_id);
    params.set("track_id", job.track_id);
    params.set("job_id", job.job_id);
    params.set("artifact_id", artifact.artifact_id);
    return { job, artifact, studioUrl: `${BASE_URL}/studio?${params.toString()}` };
  }

  throw new Error("No completed cover Studio job with track_id and downloadable artifact found");
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage34b-effect-export-"));
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

async function verifyExportFlow(client, studioUrl, sourceArtifactId) {
  await client.navigate(studioUrl);
  await client.waitFor("Boolean(document.getElementById('studioEffectRack'))", 20000, "effect rack visible");
  await client.waitFor("Boolean(document.querySelector('#studioEffectRackExportBtn:not(:disabled)'))", 20000, "effect export button enabled");
  await client.waitFor(
    "document.body.innerText.includes('copy-only') && document.body.innerText.includes('暂不执行真实 DSP/VST')",
    20000,
    "copy-only warning visible",
  );

  await client.evaluate(`
    (() => {
      const eq = document.querySelector('#studioEffectRackList [data-effect-slot-toggle="eq"]');
      if (eq && !eq.checked) eq.click();
      const low = document.querySelector('#studioEffectRackList [data-effect-slot-param="eq"][data-effect-param-key="low"]');
      if (low) {
        low.value = '3';
        low.dispatchEvent(new Event('input', { bubbles: true }));
        low.dispatchEvent(new Event('change', { bubbles: true }));
      }
      return true;
    })()
  `);
  await client.waitFor("document.querySelector('#studioEffectRackList [data-effect-slot-toggle=\"eq\"]')?.checked === true", 10000, "EQ enabled");

  await client.evaluate("document.getElementById('studioEffectRackExportBtn').click()");
  await client.waitFor("document.readyState === 'complete'", 30000, "ready after effect export navigation");
  await client.waitFor(
    `(() => {
      const params = new URLSearchParams(window.location.search);
      return params.get('artifact_id') && params.get('artifact_id') !== ${JSON.stringify(sourceArtifactId)};
    })()`,
    30000,
    "new artifact_id in Studio URL",
  );
  await client.waitFor("Boolean(document.querySelector('#studioSummaryDownloadBtn:not(.is-disabled)'))", 20000, "download enabled after export");
  await client.waitFor(
    "document.body.innerText.includes('studio_effect_draft_master') || document.body.innerText.includes('studio_effect_export') || document.body.innerText.includes('处理版草稿')",
    20000,
    "effect draft artifact visible",
  );
  await client.waitFor(
    "document.body.innerText.includes('copy-only') && document.body.innerText.includes('暂不执行真实 DSP/VST')",
    20000,
    "copy-only text still visible after export",
  );

  return client.evaluate(`
    (() => {
      const params = new URLSearchParams(window.location.search);
      return {
        url: window.location.href,
        artifact_id: params.get('artifact_id') || '',
        download_href: document.getElementById('studioSummaryDownloadBtn')?.href || '',
      };
    })()
  `);
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    const picked = await pickStudioJobWithArtifact();

    chromeHandle = launchChrome();
    client = await prepareClient();
    const result = await verifyExportFlow(client, picked.studioUrl, picked.artifact.artifact_id);
    await client.screenshot(SCREENSHOT_PATH);

    console.log("STAGE34B_EFFECT_RACK_EXPORT_UI_SMOKE PASS");
    console.log(`source_studio_url=${picked.studioUrl}`);
    console.log(`source_job_id=${picked.job.job_id}`);
    console.log(`source_track_id=${picked.job.track_id}`);
    console.log(`source_artifact_id=${picked.artifact.artifact_id}`);
    console.log(`exported_studio_url=${result.url}`);
    console.log(`exported_artifact_id=${result.artifact_id}`);
    console.log(`download_href=${result.download_href}`);
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
  console.error("STAGE34B_EFFECT_RACK_EXPORT_UI_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
