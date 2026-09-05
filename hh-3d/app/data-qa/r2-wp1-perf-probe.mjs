/**
 * R2-WP1 evidence probe — read existing 4175, do not start a preview.
 * NOT_PLAN_PASS. GATE-U1 still open. Chrome CDP / rAF only.
 */
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9235);
const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const VIEW_W = 1280;
const VIEW_H = 720;
const SAMPLE_N = 240;
const WARMUP_SKIP = 12;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function stats(values) {
  const s = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  const n = s.length;
  if (n === 0) {
    return { n: 0, min: null, median: null, p1: null, max: null, mean: null };
  }
  const q = (p) => {
    const idx = (n - 1) * p;
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    if (lo === hi) return s[lo];
    return s[lo] + (s[hi] - s[lo]) * (idx - lo);
  };
  return {
    n,
    min: s[0],
    median: q(0.5),
    p1: q(0.01),
    max: s[n - 1],
    mean: s.reduce((a, b) => a + b, 0) / n,
  };
}

function fpsFromDts(dts) {
  return dts.map((dt) => (dt > 0 ? 1000 / dt : 0));
}

async function cdp(ws, id, method, params) {
  return new Promise((resolve, reject) => {
    const onMsg = (event) => {
      const raw = typeof event.data === "string" ? event.data : String(event.data);
      const msg = JSON.parse(raw);
      if (msg.id === id) {
        ws.removeEventListener("message", onMsg);
        if (msg.error) reject(new Error(`${method}: ${JSON.stringify(msg.error)}`));
        else resolve(msg.result);
      }
    };
    ws.addEventListener("message", onMsg);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

function attachEvents(ws, bag) {
  ws.addEventListener("message", (event) => {
    const raw = typeof event.data === "string" ? event.data : String(event.data);
    const msg = JSON.parse(raw);
    if (!msg.method) return;
    if (msg.method === "Network.requestWillBeSent") {
      bag.requests.push({
        url: msg.params.request.url,
        method: msg.params.request.method,
        ts: msg.params.wallTime,
      });
    }
    if (msg.method === "Network.responseReceived") {
      bag.responses.push({
        url: msg.params.response.url,
        status: msg.params.response.status,
        mime: msg.params.response.mimeType,
        encoded: msg.params.response.encodedDataLength,
      });
    }
  });
}

async function connectPage() {
  const deadline = Date.now() + 20000;
  let targets;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
      targets = await res.json();
      const page = targets.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) {
        const ws = new WebSocket(page.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => {
          ws.addEventListener("open", resolve);
          ws.addEventListener("error", reject);
        });
        return { ws, page, targets };
      }
    } catch {
      /* retry */
    }
    await sleep(200);
  }
  throw new Error(`no CDP page on ${DEBUG_PORT}: ${JSON.stringify(targets)}`);
}

async function evalExpr(ws, id, expression, awaitPromise = false) {
  const result = await cdp(ws, id, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise,
  });
  if (result.exceptionDetails) {
    throw new Error(JSON.stringify(result.exceptionDetails));
  }
  return result.result.value;
}

const SAMPLE_FRAMES_FN = `(() => {
  const n = ${SAMPLE_N + WARMUP_SKIP};
  return new Promise((resolve) => {
    const dts = [];
    let last = performance.now();
    let i = 0;
    const tick = (now) => {
      dts.push(now - last);
      last = now;
      i += 1;
      if (i >= n) resolve(dts.slice(${WARMUP_SKIP}));
      else requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
})()`;

const SNAP_FN = `(() => {
  const canvas = document.querySelector(".maplibregl-canvas");
  const markers = [...document.querySelectorAll(".map-marker")].map((el) => el.textContent);
  const list = [...document.querySelectorAll('[data-testid="place-list"] button')].map((el) => el.textContent.trim());
  const toggle = document.querySelector(".layer-toggle input");
  const fallback = document.querySelector('[data-testid="webgl-fallback"]');
  const card = document.querySelector('[data-testid="place-card"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const nav = performance.getEntriesByType("navigation")[0];
  let glInfo = null;
  try {
    const gl = canvas?.getContext("webgl2") || canvas?.getContext("webgl") || document.createElement("canvas").getContext("webgl");
    if (gl) {
      const ext = gl.getExtension("WEBGL_debug_renderer_info");
      glInfo = {
        vendor: ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
        renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
        version: gl.getParameter(gl.VERSION),
      };
    }
  } catch (err) {
    glInfo = { error: String(err) };
  }
  return {
    title: document.title,
    href: location.href,
    canvas: canvas
      ? { w: canvas.width, h: canvas.height, cssW: canvas.clientWidth, cssH: canvas.clientHeight }
      : null,
    markerCount: markers.length,
    markers,
    list,
    extrusionChecked: toggle ? toggle.checked : null,
    fallbackText: fallback ? fallback.textContent.trim() : null,
    honesty: honesty ? honesty.textContent.replace(/\\s+/g, " ").trim() : null,
    cardText: card ? card.textContent.replace(/\\s+/g, " ").trim().slice(0, 400) : null,
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    nav: nav
      ? {
          startTime: nav.startTime,
          duration: nav.duration,
          domContentLoaded: nav.domContentLoadedEventEnd,
          loadEvent: nav.loadEventEnd,
          transferSize: nav.transferSize,
          encodedBodySize: nav.encodedBodySize,
        }
      : null,
    glInfo,
    now: performance.now(),
  };
})()`;

const WAIT_MAP_FN = `(() => {
  const t0 = performance.now();
  return new Promise((resolve) => {
    const check = () => {
      const canvas = document.querySelector(".maplibregl-canvas");
      const markers = document.querySelectorAll(".map-marker");
      const honesty = document.querySelector('[data-testid="honesty-banner"]');
      const listBtns = document.querySelectorAll('[data-testid="place-list"] button');
      const ready =
        canvas &&
        canvas.width > 0 &&
        markers.length >= 4 &&
        honesty &&
        listBtns.length >= 4;
      if (ready) {
        resolve({
          ok: true,
          firstMapMsFromNav: performance.now(),
          pollMs: performance.now() - t0,
          canvas: { w: canvas.width, h: canvas.height },
          markers: markers.length,
          list: listBtns.length,
        });
        return;
      }
      if (performance.now() - t0 > 20000) {
        resolve({
          ok: false,
          timeout: true,
          pollMs: performance.now() - t0,
          hasCanvas: Boolean(canvas),
          markers: markers.length,
          list: listBtns.length,
        });
        return;
      }
      requestAnimationFrame(check);
    };
    check();
  });
})()`;

const CANVAS_HASH_FN = `(() => {
  const canvas = document.querySelector(".maplibregl-canvas");
  if (!canvas) return null;
  const w = Math.min(canvas.width, 320);
  const h = Math.min(canvas.height, 180);
  const tmp = document.createElement("canvas");
  tmp.width = w;
  tmp.height = h;
  const ctx = tmp.getContext("2d");
  ctx.drawImage(canvas, 0, 0, w, h);
  const data = ctx.getImageData(0, 0, w, h).data;
  let h1 = 2166136261;
  for (let i = 0; i < data.length; i += 7) {
    h1 ^= data[i];
    h1 = Math.imul(h1, 16777619);
  }
  let sum = 0;
  for (let i = 0; i < data.length; i += 4) sum += data[i] + data[i + 1] + data[i + 2];
  return { w, h, fnv: (h1 >>> 0).toString(16), lumaSum: sum, nonzero: data.some((v) => v !== 0) };
})()`;

const SELECT_AND_WATCH_FN = `(() => {
  const btn = [...document.querySelectorAll('[data-testid="place-list"] button')].find((el) =>
    el.textContent.includes("Clock Garden"),
  );
  if (!btn) return Promise.resolve({ error: "no Clock Garden row" });
  const canvas = document.querySelector(".maplibregl-canvas");
  const samples = [];
  const t0 = performance.now();
  btn.click();
  return new Promise((resolve) => {
    const grab = () => {
      if (!canvas) {
        resolve({ error: "no canvas" });
        return;
      }
      const ctx = document.createElement("canvas");
      ctx.width = 80;
      ctx.height = 45;
      const g = ctx.getContext("2d");
      g.drawImage(canvas, 0, 0, 80, 45);
      const d = g.getImageData(0, 0, 80, 45).data;
      let s = 0;
      for (let i = 0; i < d.length; i += 16) s += d[i];
      samples.push({ t: performance.now() - t0, luma: s });
      if (performance.now() - t0 >= 700) {
        const unique = new Set(samples.map((x) => x.luma)).size;
        resolve({
          samples: samples.length,
          uniqueLuma: unique,
          first: samples[0],
          last: samples[samples.length - 1],
          moved: unique > 2,
          reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        });
      } else requestAnimationFrame(grab);
    };
    requestAnimationFrame(grab);
  });
})()`;

async function setupPage(ws, bag) {
  attachEvents(ws, bag);
  await cdp(ws, 1, "Network.enable");
  await cdp(ws, 2, "Runtime.enable");
  await cdp(ws, 3, "Page.enable");
  await cdp(ws, 4, "Emulation.setDeviceMetricsOverride", {
    width: VIEW_W,
    height: VIEW_H,
    deviceScaleFactor: 1,
    mobile: false,
    screenWidth: VIEW_W,
    screenHeight: VIEW_H,
  });
  try {
    await cdp(ws, 5, "Page.setWebLifecycleState", { state: "active" });
  } catch {
    /* optional */
  }
}

async function runMain() {
  const bag = { requests: [], responses: [] };
  const { ws } = await connectPage();
  await setupPage(ws, bag);
  await cdp(ws, 10, "Page.navigate", { url: "about:blank" });
  await sleep(300);
  bag.requests.length = 0;
  bag.responses.length = 0;
  const navStarted = Date.now();
  await cdp(ws, 11, "Page.navigate", { url: PLAYER });
  const firstMap = await evalExpr(ws, 12, WAIT_MAP_FN, true);
  const hostFirstMapMs = Date.now() - navStarted;
  await sleep(800);
  const snap = await evalExpr(ws, 13, SNAP_FN);
  const canvasOn = await evalExpr(ws, 14, CANVAS_HASH_FN);
  const dtsOn = await evalExpr(ws, 15, SAMPLE_FRAMES_FN, true);
  await evalExpr(
    ws,
    16,
    `(() => { const el = document.querySelector(".layer-toggle input"); if (el && el.checked) el.click(); return el ? el.checked : null; })()`,
  );
  await sleep(500);
  const canvasOff = await evalExpr(ws, 17, CANVAS_HASH_FN);
  const dtsOff = await evalExpr(ws, 18, SAMPLE_FRAMES_FN, true);
  const snapOff = await evalExpr(ws, 19, SNAP_FN);
  await evalExpr(
    ws,
    20,
    `(() => { const el = document.querySelector(".layer-toggle input"); if (el && !el.checked) el.click(); return el ? el.checked : null; })()`,
  );
  await sleep(400);
  const motionDefault = await evalExpr(ws, 21, SELECT_AND_WATCH_FN, true);
  try {
    await cdp(ws, 22, "Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    });
  } catch (err) {
    bag.reducedMotionEmulationError = String(err);
  }
  await evalExpr(
    ws,
    23,
    `(() => { const close = document.querySelector('[data-testid="place-card"] button'); close?.click(); return true; })()`,
  );
  await sleep(200);
  const motionReduce = await evalExpr(ws, 24, SELECT_AND_WATCH_FN, true);
  const snapReduce = await evalExpr(ws, 25, SNAP_FN);
  let metrics = null;
  try {
    metrics = await cdp(ws, 26, "Performance.getMetrics");
  } catch {
    try {
      await cdp(ws, 27, "Performance.enable");
      metrics = await cdp(ws, 28, "Performance.getMetrics");
    } catch (err) {
      metrics = { error: String(err) };
    }
  }
  ws.close();

  const fpsOn = fpsFromDts(dtsOn || []);
  const fpsOff = fpsFromDts(dtsOff || []);
  return {
    mode: "webgl_default",
    viewport: { width: VIEW_W, height: VIEW_H, dpr: 1, mobile: false },
    hostFirstMapMs,
    firstMap,
    snap,
    snapOff,
    snapReduce,
    canvasOn,
    canvasOff,
    extrusionVisualChange:
      canvasOn && canvasOff ? canvasOn.fnv !== canvasOff.fnv || canvasOn.lumaSum !== canvasOff.lumaSum : null,
    rAF_extrusionOn_frameMs: stats(dtsOn || []),
    rAF_extrusionOn_fps: stats(fpsOn),
    rAF_extrusionOff_frameMs: stats(dtsOff || []),
    rAF_extrusionOff_fps: stats(fpsOff),
    motionDefault,
    motionReduce,
    metrics,
    network: {
      requestCount: bag.requests.length,
      urls: [...new Set(bag.requests.map((r) => r.url))],
      nonLocal: bag.requests
        .map((r) => r.url)
        .filter((u) => !u.startsWith(PLAYER.replace(/\/$/, "")) && !u.startsWith("blob:") && !u.startsWith("data:")),
    },
  };
}

async function runFallback() {
  const bag = { requests: [], responses: [] };
  const { ws } = await connectPage();
  await setupPage(ws, bag);
  await cdp(ws, 40, "Page.navigate", { url: PLAYER });
  await sleep(2500);
  const snap = await evalExpr(ws, 41, SNAP_FN);
  const listWorks = await evalExpr(
    ws,
    42,
    `(() => {
      const btn = [...document.querySelectorAll('[data-testid="place-list"] button')].find((el) =>
        el.textContent.includes("Market Hall"),
      );
      if (!btn) return { error: "no Market Hall" };
      btn.click();
      const card = document.querySelector('[data-testid="place-card"]');
      return {
        clicked: true,
        card: card ? card.textContent.replace(/\\s+/g, " ").trim().slice(0, 400) : null,
        fallback: document.querySelector('[data-testid="webgl-fallback"]')?.textContent?.trim() ?? null,
        canvas: Boolean(document.querySelector(".maplibregl-canvas")),
      };
    })()`,
  );
  ws.close();
  return { mode: "disable_webgl", snap, listWorks, networkUrls: [...new Set(bag.requests.map((r) => r.url))] };
}

const kind = process.argv[2] || "main";
const out = kind === "fallback" ? await runFallback() : await runMain();
console.log(JSON.stringify(out, null, 2));
