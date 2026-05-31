const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REMOTE_DEBUG_PORT = 9255;
const SCREENSHOT_PATH = path.join(__dirname, "..", "stage35b_studio_version_ux.png");

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

async function ensureVersionContext() {
  const payload = await fetchJson(`${BASE_URL}/api/jobs?job_type=cover&limit=100&offset=0`);
  const jobs = (payload.items || []).filter(job => isCompletedStatus(job.status) && job.track_id);

  for (const job of jobs) {
    const ledger = await fetchJson(`${BASE_URL}/api/tracks/${encodeURIComponent(job.track_id)}/studio-versions?limit=50&offset=0`);
    let items = ledger.items || [];
    let cover = items.find(item => item.artifact_type === "cover_master" && item.download_url);
    if (!cover) continue;

    let draft = items.find(item => item.artifact_type === "studio_effect_draft_master" && item.download_url);
    if (!draft) {
      const exported = await fetchJson(`${BASE_URL}/api/studio/effect-rack/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          track_id: job.track_id,
          source_job_id: cover.job_id,
          source_artifact_id: cover.artifact_id,
          effect_rack: [
            { id: "eq", enabled: true, status: "draft", params: { low: 2, mid: 0, high: 0 } },
          ],
          export_profile: "studio_balanced",
          note: "stage35b version ux smoke",
        }),
      });
      const refreshed = await fetchJson(`${BASE_URL}/api/tracks/${encodeURIComponent(job.track_id)}/studio-versions?limit=50&offset=0`);
      items = refreshed.items || [];
      draft = items.find(item => item.artifact_id === exported.artifact_id) || items.find(item => item.artifact_type === "studio_effect_draft_master");
    }

    if (!draft) continue;
    const params = new URLSearchParams();
    if (job.batch_id) params.set("batch_id", job.batch_id);
    params.set("track_id", job.track_id);
    params.set("job_id", cover.job_id);
    params.set("artifact_id", cover.artifact_id);
    return {
      trackId: job.track_id,
      jobId: cover.job_id,
      coverArtifactId: cover.artifact_id,
      draftArtifactId: draft.artifact_id,
      studioUrl: `${BASE_URL}/studio?${params.toString()}`,
    };
  }

  throw new Error("No completed cover track with cover_master and draft version available for Stage 35B smoke");
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
        // Ignore transient runtime errors while the page settles.
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
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "feishark-stage35b-version-ux-"));
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

async function assertNoHorizontalScroll(client, label) {
  const result = await client.evaluate(`(() => ({
    ok: document.documentElement.scrollWidth <= window.innerWidth + 8,
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth
  }))()`);
  if (!result?.ok) {
    throw new Error(`${label} has horizontal scroll: ${JSON.stringify(result)}`);
  }
}

async function verifyVersionUx(client, context) {
  await client.navigate(context.studioUrl);
  await client.waitFor("Boolean(document.getElementById('studioCurrentMasterCard'))", 20000, "current master card");
  await client.waitFor("Boolean(document.getElementById('studioTrackHistoryPanel')) && document.getElementById('studioTrackHistoryPanel').hidden === false", 20000, "version drawer panel visible");
  await client.waitFor("document.getElementById('studioTrackHistoryBody')?.hidden === true", 20000, "version drawer default collapsed");
  await client.waitFor("Boolean(document.querySelector('#studioEffectRackExportBtn:not(:disabled)'))", 20000, "effect rack export still enabled");

  await client.evaluate("document.getElementById('studioTrackHistoryToggleBtn').click()");
  await client.waitFor("document.getElementById('studioTrackHistoryBody')?.hidden === false", 20000, "version drawer expanded");
  await client.waitFor("document.body.innerText.includes('原始翻唱成品')", 20000, "cover master label visible");
  await client.waitFor("document.body.innerText.includes('处理版草稿') && document.body.innerText.includes('未执行真实 DSP/VST')", 20000, "draft no-DSP label visible");
  await client.evaluate("document.getElementById('studioTrackHistoryToggleBtn').click()");
  await client.waitFor("document.getElementById('studioTrackHistoryBody')?.hidden === true", 20000, "version drawer collapsed again");
  await client.evaluate("document.getElementById('studioTrackHistoryToggleBtn').click()");
  await client.waitFor("document.getElementById('studioTrackHistoryBody')?.hidden === false", 20000, "version drawer expanded for master action");

  const clicked = await client.evaluate(`
    (() => {
      const buttons = Array.from(document.querySelectorAll('#studioTrackHistoryList [data-set-track-master-job-id]'));
      const draftButton = buttons.find(button => button.dataset.artifactId === ${JSON.stringify(context.draftArtifactId)});
      const button = draftButton || buttons[0];
      if (!button) return false;
      button.click();
      return true;
    })()
  `);
  if (!clicked) {
    throw new Error("No set-current-master button was available in version drawer");
  }

  await client.waitFor(
    `document.querySelector('#studioCurrentMasterCard')?.innerText.includes(${JSON.stringify(context.draftArtifactId)}) || document.body.innerText.includes('当前主成品已切换')`,
    20000,
    "current master badge or toast updated after master action",
  );
  await assertNoHorizontalScroll(client, "Studio");

  return client.evaluate(`
    (() => ({
      currentMasterText: document.getElementById('studioCurrentMasterCard')?.innerText || '',
      versionSummary: document.getElementById('studioTrackHistorySummary')?.innerText || '',
      bodyTextIncludesFallback: document.body.innerText.includes('版本账本暂不可用'),
    }))()
  `);
}

async function main() {
  let chromeHandle = null;
  let client = null;
  try {
    await fetchJson(`${BASE_URL}/api/health`);
    const context = await ensureVersionContext();
    chromeHandle = launchChrome();
    client = await prepareClient();
    const result = await verifyVersionUx(client, context);
    await client.screenshot(SCREENSHOT_PATH);

    console.log("STAGE35B_STUDIO_VERSION_UX_SMOKE PASS");
    console.log(`studio_url=${context.studioUrl}`);
    console.log(`track_id=${context.trackId}`);
    console.log(`job_id=${context.jobId}`);
    console.log(`cover_artifact_id=${context.coverArtifactId}`);
    console.log(`draft_artifact_id=${context.draftArtifactId}`);
    console.log(`current_master_text=${result.currentMasterText.replace(/\\s+/g, " ").slice(0, 220)}`);
    console.log(`version_summary=${result.versionSummary}`);
    console.log(`fallback_visible=${result.bodyTextIncludesFallback ? "yes" : "no"}`);
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
  console.error("STAGE35B_STUDIO_VERSION_UX_SMOKE FAIL");
  console.error(error.stack || error.message || error);
  process.exit(1);
});
