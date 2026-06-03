const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9256;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage36b_studio_render_mode.png");

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

function engineAvailable(capabilities, engineId) {
  return Boolean((capabilities.engines || []).find(engine => engine.id === engineId && engine.available));
}

async function ensureRenderModeContext() {
  const capabilities = await fetchJson(`${BASE_URL}/api/studio/effect-rack/capabilities`);
  const payload = await fetchJson(`${BASE_URL}/api/jobs?job_type=cover&limit=100&offset=0`);
  const jobs = (payload.items || []).filter(job => isCompletedStatus(job.status) && job.track_id);

  for (const job of jobs) {
    const artifacts = await fetchJson(`${BASE_URL}/api/jobs/${encodeURIComponent(job.job_id)}/artifacts`);
    const artifact = (artifacts.artifacts || []).find(item => item.artifact_type === "cover_master" && item.artifact_id && item.download_url)
      || (artifacts.artifacts || []).find(item => item.is_final && item.artifact_id && item.download_url)
      || (artifacts.artifacts || []).find(item => item.artifact_id && item.download_url);
    if (!artifact) continue;

    const params = new URLSearchParams();
    if (job.batch_id) params.set("batch_id", job.batch_id);
    params.set("track_id", job.track_id);
    params.set("job_id", job.job_id);
    params.set("artifact_id", artifact.artifact_id);
    return {
      capabilities,
      trackId: job.track_id,
      jobId: job.job_id,
      sourceArtifactId: artifact.artifact_id,
      studioUrl: `${BASE_URL}/studio?${params.toString()}`,
    };
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage36b-render-mode-"));
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

async function enableRenderTestEffects(client) {
  await client.evaluate(`
    (() => {
      for (const id of ['eq', 'compressor', 'limiter', 'reverb']) {
        const toggle = document.querySelector(\`#studioEffectRackList [data-effect-slot-toggle="\${id}"]\`);
        if (toggle && !toggle.checked) toggle.click();
      }
      const low = document.querySelector('#studioEffectRackList [data-effect-slot-param="eq"][data-effect-param-key="low"]');
      if (low) {
        low.value = '3';
        low.dispatchEvent(new Event('input', { bubbles: true }));
        low.dispatchEvent(new Event('change', { bubbles: true }));
      }
      return true;
    })()
  `);
}

async function currentArtifactId(client) {
  return client.evaluate(`new URLSearchParams(window.location.search).get('artifact_id') || ''`);
}

async function verifyRenderModeUx(client, context) {
  await client.navigate(context.studioUrl);
  await client.waitFor("Boolean(document.getElementById('studioRenderModeControl'))", 20000, "render mode control visible");
  await client.waitFor("document.body.innerText.includes('输出模式') && document.body.innerText.includes('登记草稿') && document.body.innerText.includes('真实渲染 v0')", 20000, "render mode labels visible");
  await client.waitFor("document.getElementById('studioRenderModeCopyBtn')?.classList.contains('is-active')", 20000, "copy-only mode selected by default");
  await client.waitFor("document.getElementById('studioEffectRackExportBtn')?.innerText.includes('导出处理版草稿')", 20000, "copy-only export label");
  try {
    await client.waitFor("Boolean(document.querySelector('#studioEffectRackExportBtn:not(:disabled)'))", 20000, "copy-only export enabled");
  } catch (error) {
    const diagnostic = await client.evaluate(`(() => ({
      url: window.location.href,
      exportText: document.getElementById('studioEffectRackExportBtn')?.innerText || '',
      exportDisabled: document.getElementById('studioEffectRackExportBtn')?.disabled ?? null,
      exportHint: document.getElementById('studioEffectRackExportHint')?.innerText || '',
      renderHint: document.getElementById('studioRenderModeHint')?.innerText || '',
      studioStatus: document.getElementById('studioStatus')?.innerText || '',
      toastText: document.querySelector('.toast-root')?.innerText || '',
      sourceText: document.getElementById('studioSourceMetaGrid')?.innerText || '',
      artifactText: document.getElementById('studioArtifactMetaGrid')?.innerText || '',
    }))()`);
    throw new Error(`${error.message}; diagnostic=${JSON.stringify(diagnostic)}`);
  }
  await enableRenderTestEffects(client);

  const beforeCopyArtifactId = await currentArtifactId(client);
  await client.evaluate("document.getElementById('studioEffectRackExportBtn').click()");
  await client.waitFor(
    `new URLSearchParams(window.location.search).get('artifact_id') && new URLSearchParams(window.location.search).get('artifact_id') !== ${JSON.stringify(beforeCopyArtifactId)}`,
    30000,
    "copy-only export navigated to new artifact",
  );
  await client.waitFor("Boolean(document.querySelector('#studioSummaryDownloadBtn:not(.is-disabled)'))", 20000, "download enabled after copy-only export");
  await client.waitFor("Boolean(document.getElementById('studioTrackHistoryPanel')) && document.getElementById('studioTrackHistoryPanel').hidden === false", 20000, "version drawer visible after copy-only export");
  await client.evaluate(`
    (() => {
      const body = document.getElementById('studioTrackHistoryBody');
      if (body?.hidden) document.getElementById('studioTrackHistoryToggleBtn')?.click();
      return true;
    })()
  `);
  await client.waitFor("document.getElementById('studioTrackHistoryBody')?.hidden === false", 20000, "version drawer expanded after copy-only export");
  await client.waitFor("document.body.innerText.includes('处理版草稿') && document.body.innerText.includes('未执行真实 DSP/VST')", 20000, "copy-only draft visible");

  const ffmpegAvailable = engineAvailable(context.capabilities, "ffmpeg_dsp_v0");
  if (!ffmpegAvailable) {
    await client.waitFor("document.getElementById('studioRenderModeFfmpegBtn')?.disabled === true", 20000, "ffmpeg mode disabled");
    return { ffmpegAvailable, copyArtifactId: await currentArtifactId(client), renderArtifactId: "" };
  }

  await client.waitFor("document.getElementById('studioRenderModeFfmpegBtn')?.disabled === false", 20000, "ffmpeg mode enabled");
  await client.evaluate("document.getElementById('studioRenderModeFfmpegBtn').click()");
  await client.waitFor("document.getElementById('studioRenderModeFfmpegBtn')?.classList.contains('is-active')", 10000, "ffmpeg mode selected");
  await client.waitFor("document.getElementById('studioEffectRackExportBtn')?.innerText.includes('渲染处理版 v0')", 10000, "ffmpeg export label");
  await enableRenderTestEffects(client);

  const beforeRenderArtifactId = await currentArtifactId(client);
  await client.evaluate("document.getElementById('studioEffectRackExportBtn').click()");
  await client.waitFor(
    `new URLSearchParams(window.location.search).get('artifact_id') && new URLSearchParams(window.location.search).get('artifact_id') !== ${JSON.stringify(beforeRenderArtifactId)}`,
    45000,
    "ffmpeg render navigated to new artifact",
  );
  await client.waitFor("Boolean(document.getElementById('studioTrackHistoryPanel')) && document.getElementById('studioTrackHistoryPanel').hidden === false", 20000, "version drawer visible");
  await client.evaluate(`
    (() => {
      const body = document.getElementById('studioTrackHistoryBody');
      if (body?.hidden) document.getElementById('studioTrackHistoryToggleBtn')?.click();
      return true;
    })()
  `);
  await client.waitFor("document.getElementById('studioTrackHistoryBody')?.hidden === false", 20000, "version drawer expanded");
  await client.waitFor("document.body.innerText.includes('已渲染处理版')", 20000, "render artifact label visible");
  await client.waitFor("document.body.innerText.includes('ffmpeg v0 已应用')", 20000, "ffmpeg processing mode visible");

  return {
    ffmpegAvailable,
    copyArtifactId: beforeRenderArtifactId,
    renderArtifactId: await currentArtifactId(client),
  };
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    const context = await ensureRenderModeContext();
    chromeHandle = launchChrome();
    client = await prepareClient();
    const result = await verifyRenderModeUx(client, context);
    await client.screenshot(SCREENSHOT_PATH);

    console.log("STAGE36B_STUDIO_RENDER_MODE_SMOKE PASS");
    console.log(`studio_url=${context.studioUrl}`);
    console.log(`track_id=${context.trackId}`);
    console.log(`job_id=${context.jobId}`);
    console.log(`source_artifact_id=${context.sourceArtifactId}`);
    console.log(`copy_artifact_id=${result.copyArtifactId}`);
    console.log(`ffmpeg_available=${result.ffmpegAvailable ? "yes" : "no"}`);
    console.log(`render_artifact_id=${result.renderArtifactId}`);
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
  console.error("STAGE36B_STUDIO_RENDER_MODE_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
