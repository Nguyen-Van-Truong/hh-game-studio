/**
 * First-paint remint: CDP screenshot immediately after load must not be
 * empty gray. Labeled boot/loading or the authored street both count.
 * Recycled 4175 only. NOT_PLAN_PASS. Not GATE-U1.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9341);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-FIRST-PAINT-2026-09-03.txt");
const SHOT = join(import.meta.dirname, "j5-first-paint.png");
const SHOT_READY = join(import.meta.dirname, "j5-first-paint-ready.png");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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

function waitEvent(ws, method, timeoutMs) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      ws.removeEventListener("message", onMsg);
      reject(new Error(`timeout waiting ${method}`));
    }, timeoutMs);
    const onMsg = (event) => {
      const raw = typeof event.data === "string" ? event.data : String(event.data);
      const msg = JSON.parse(raw);
      if (msg.method === method) {
        clearTimeout(timer);
        ws.removeEventListener("message", onMsg);
        resolve(msg.params);
      }
    };
    ws.addEventListener("message", onMsg);
  });
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

function decodePngRgba(buf) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (buf.length < 24 || !buf.subarray(0, 8).equals(sig)) {
    throw new Error("not a PNG");
  }
  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idats = [];
  while (offset + 12 <= buf.length) {
    const len = buf.readUInt32BE(offset);
    const type = buf.toString("ascii", offset + 4, offset + 8);
    const data = buf.subarray(offset + 8, offset + 8 + len);
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === "IDAT") {
      idats.push(data);
    } else if (type === "IEND") {
      break;
    }
    offset += 12 + len;
  }
  if (bitDepth !== 8 || (colorType !== 2 && colorType !== 6)) {
    throw new Error(`unsupported PNG ${bitDepth}/${colorType}`);
  }
  const bpp = colorType === 6 ? 4 : 3;
  const raw = inflateSync(Buffer.concat(idats));
  const stride = width * bpp;
  const pixels = Buffer.alloc(width * height * 4);
  let src = 0;
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[src];
    src += 1;
    const row = raw.subarray(src, src + stride);
    src += stride;
    const out = Buffer.alloc(stride);
    for (let i = 0; i < stride; i += 1) {
      const left = i >= bpp ? out[i - bpp] : 0;
      const up = prev[i];
      const upLeft = i >= bpp ? prev[i - bpp] : 0;
      const x = row[i];
      if (filter === 0) out[i] = x;
      else if (filter === 1) out[i] = (x + left) & 255;
      else if (filter === 2) out[i] = (x + up) & 255;
      else if (filter === 3) out[i] = (x + Math.floor((left + up) / 2)) & 255;
      else if (filter === 4) {
        const p = left + up - upLeft;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - up);
        const pc = Math.abs(p - upLeft);
        const pr = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft;
        out[i] = (x + pr) & 255;
      } else {
        throw new Error(`bad PNG filter ${filter}`);
      }
    }
    for (let x = 0; x < width; x += 1) {
      const di = (y * width + x) * 4;
      const si = x * bpp;
      pixels[di] = out[si];
      pixels[di + 1] = out[si + 1];
      pixels[di + 2] = out[si + 2];
      pixels[di + 3] = bpp === 4 ? out[si + 3] : 255;
    }
    prev = out;
  }
  return { width, height, pixels };
}

function analyzePixels(pixels, width, height) {
  const step = Math.max(4, Math.floor(Math.min(width, height) / 80));
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let sumR2 = 0;
  let sumG2 = 0;
  let sumB2 = 0;
  let beige = 0;
  let dark = 0;
  let grayish = 0;
  const buckets = new Set();
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * 4;
      const r = pixels[i];
      const g = pixels[i + 1];
      const b = pixels[i + 2];
      n += 1;
      sumR += r;
      sumG += g;
      sumB += b;
      sumR2 += r * r;
      sumG2 += g * g;
      sumB2 += b * b;
      const spread = Math.max(r, g, b) - Math.min(r, g, b);
      if (spread < 14 && r > 140 && r < 230 && g > 140 && g < 230 && b > 140 && b < 230) {
        grayish += 1;
      }
      if (r > 170 && g > 140 && b < 180 && r - b > 20) {
        beige += 1;
      }
      if (r < 90 && g < 90 && b < 95) {
        dark += 1;
      }
      buckets.add(`${r >> 4}:${g >> 4}:${b >> 4}`);
    }
  }
  const meanR = sumR / n;
  const meanG = sumG / n;
  const meanB = sumB / n;
  const std = Math.sqrt(
    (sumR2 / n - meanR * meanR + (sumG2 / n - meanG * meanG) + (sumB2 / n - meanB * meanB)) / 3,
  );
  const channelSpread = Math.max(meanR, meanG, meanB) - Math.min(meanR, meanG, meanB);
  const emptyGray = std < 14 && channelSpread < 18 && buckets.size < 10 && beige / n < 0.08 && dark / n < 0.04;
  return {
    width,
    height,
    samples: n,
    meanR: Number(meanR.toFixed(1)),
    meanG: Number(meanG.toFixed(1)),
    meanB: Number(meanB.toFixed(1)),
    std: Number(std.toFixed(2)),
    channelSpread: Number(channelSpread.toFixed(2)),
    uniqueQ16: buckets.size,
    beigeRatio: Number((beige / n).toFixed(3)),
    darkRatio: Number((dark / n).toFixed(3)),
    grayRatio: Number((grayish / n).toFixed(3)),
    emptyGray,
  };
}

const SNAP = `(() => {
  const boot = document.querySelector('[data-testid="play-boot"]');
  const loading = document.querySelector('[data-testid="play-loading"]');
  const play = document.querySelector('[data-testid="play-view"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const vis = (el) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden") return null;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return null;
    return { w: Math.round(r.width), h: Math.round(r.height), text: (el.innerText || "").slice(0, 240) };
  };
  return {
    title: document.title,
    href: location.href,
    boot: vis(boot),
    loading: vis(loading),
    playReady: play?.getAttribute("data-play-ready") ?? "",
    canvas: canvas
      ? { w: canvas.width, h: canvas.height, cw: canvas.clientWidth, ch: canvas.clientHeight }
      : null,
    labeled: /authored 400 m block/i.test(document.body.innerText),
    bodySample: (document.body.innerText || "").slice(0, 280),
  };
})()`;

async function connectPage() {
  const deadline = Date.now() + 20000;
  let last = null;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
      const targets = await res.json();
      last = targets;
      const page = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) {
        const ws = new WebSocket(page.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => {
          ws.addEventListener("open", resolve);
          ws.addEventListener("error", reject);
        });
        return { ws, page };
      }
    } catch {
      /* retry */
    }
    await sleep(200);
  }
  throw new Error(`no CDP page: ${JSON.stringify(last)}`);
}

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-paint-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,720",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let report;
try {
  const { ws } = await connectPage();
  await cdp(ws, 1, "Runtime.enable");
  await cdp(ws, 2, "Page.enable");
  await cdp(ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  const loaded = waitEvent(ws, "Page.loadEventFired", 20000);
  await cdp(ws, 4, "Page.navigate", { url: PLAYER });
  await loaded;
  const firstDom = await evalExpr(ws, 10, SNAP);
  const firstShot = await cdp(ws, 11, "Page.captureScreenshot", { format: "png" });
  const firstBuf = Buffer.from(firstShot.data, "base64");
  writeFileSync(SHOT, firstBuf);
  const firstPng = decodePngRgba(firstBuf);
  const firstPx = analyzePixels(firstPng.pixels, firstPng.width, firstPng.height);
  const firstHash = createHash("sha256").update(firstBuf).digest("hex").slice(0, 16);

  let readyDom = null;
  let readyPx = null;
  let readyHash = null;
  const readyDeadline = Date.now() + 8000;
  while (Date.now() < readyDeadline) {
    readyDom = await evalExpr(ws, 20, SNAP);
    if (readyDom.playReady === "yes" && readyDom.canvas && readyDom.canvas.w >= 200) {
      break;
    }
    await sleep(120);
  }
  const readyShot = await cdp(ws, 21, "Page.captureScreenshot", { format: "png" });
  const readyBuf = Buffer.from(readyShot.data, "base64");
  writeFileSync(SHOT_READY, readyBuf);
  const readyPng = decodePngRgba(readyBuf);
  readyPx = analyzePixels(readyPng.pixels, readyPng.width, readyPng.height);
  readyHash = createHash("sha256").update(readyBuf).digest("hex").slice(0, 16);

  const labeled =
    Boolean(firstDom.boot || firstDom.loading) && firstDom.labeled && !firstPx.emptyGray;
  const street =
    !firstPx.emptyGray && firstPx.darkRatio > 0.04 && firstPx.uniqueQ16 > 40;
  const firstOk = !firstPx.emptyGray && (labeled || street);
  const readyOk =
    readyDom?.playReady === "yes" &&
    Boolean(readyDom?.canvas && readyDom.canvas.w >= 200 && readyDom.canvas.h >= 200) &&
    readyPx &&
    !readyPx.emptyGray &&
    readyPx.darkRatio > 0.04 &&
    readyPx.uniqueQ16 > 40;

  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-06",
    player: PLAYER,
    verdict: firstOk && readyOk ? "J5_FIRST_PAINT_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    firstOk,
    readyOk,
    emptyGrayFirst: firstPx.emptyGray,
    labeled,
    street,
    firstBytes: firstBuf.length,
    firstHash,
    firstPx,
    firstDom,
    readyHash,
    readyPx,
    readyDom,
    shot: SHOT,
    shotReady: SHOT_READY,
  };
  ws.close();
} catch (err) {
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-06",
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_FIRST_PAINT_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `firstGray=${report.emptyGrayFirst}`,
  `labeled=${report.labeled}`,
  `readyBeige=${report.readyPx?.beigeRatio}`,
);
