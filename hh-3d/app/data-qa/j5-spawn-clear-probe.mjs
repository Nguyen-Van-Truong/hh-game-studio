/**
 * Spawn keep-out: leftover kiosks hidden from the 3D scene (not just collide=0).
 * Behind-camera nape is street; first W north free; E still opens lantern.
 * Catalog persist stays. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9488);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-SPAWN-CLEAR-2026-09-04.txt");
const SHOT_SPAWN = join(import.meta.dirname, "j5-3d-spawn-clear.png");
const SHOT_LANTERN = join(import.meta.dirname, "j5-3d-spawn-clear-lantern.png");
const M_PER_DEG_LAT = 111320;
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-01";
const SPAWN = { lon: 106.69804, lat: 10.77162 };

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

function distanceM(a, b) {
  const mid = (a.lat + b.lat) / 2;
  const east = (b.lon - a.lon) * metersPerDegLon(mid);
  const north = (b.lat - a.lat) * M_PER_DEG_LAT;
  return Math.hypot(east, north);
}

function deltaM(a, b) {
  const mid = (a.lat + b.lat) / 2;
  return {
    east: (b.lon - a.lon) * metersPerDegLon(mid),
    north: (b.lat - a.lat) * M_PER_DEG_LAT,
    moved: distanceM(a, b),
  };
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

async function keyHold(ws, id, key, code, vk, ms) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
  await sleep(ms);
  await cdp(ws, id + 1, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
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

function bandStats(pixels, width, height, x0, y0, x1, y1) {
  const step = 3;
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let beige = 0;
  let blueish = 0;
  let warm = 0;
  let orangeBoard = 0;
  const xa = Math.max(0, Math.floor(x0));
  const ya = Math.max(0, Math.floor(y0));
  const xb = Math.min(width, Math.ceil(x1));
  const yb = Math.min(height, Math.ceil(y1));
  for (let y = ya; y < yb; y += step) {
    for (let x = xa; x < xb; x += step) {
      const i = (y * width + x) * 4;
      const r = pixels[i];
      const g = pixels[i + 1];
      const b = pixels[i + 2];
      n += 1;
      sumR += r;
      sumG += g;
      sumB += b;
      if (r > 170 && g > 140 && b < 180 && r - b > 20) beige += 1;
      if (b > r + 8 && b > 90) blueish += 1;
      if (r > 150 && g > 90 && b < 110 && r > b + 40) warm += 1;
      if (r > 120 && r > g + 25 && r > b + 35 && g < 120) orangeBoard += 1;
    }
  }
  const meanR = n ? sumR / n : 0;
  const meanG = n ? sumG / n : 0;
  const meanB = n ? sumB / n : 0;
  return {
    samples: n,
    meanR: Number(meanR.toFixed(1)),
    meanG: Number(meanG.toFixed(1)),
    meanB: Number(meanB.toFixed(1)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    warmRatio: Number((warm / Math.max(1, n)).toFixed(3)),
    orangeBoardRatio: Number((orangeBoard / Math.max(1, n)).toFixed(3)),
    bluerThanRed: meanB > meanR + 6,
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const proof = document.querySelector('[data-testid="play-proof"]');
  const self = document.querySelector('[data-testid="self-avatar"]');
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id"),
    name: el.getAttribute("data-name"),
    draw: el.getAttribute("data-draw"),
    collide: el.getAttribute("data-collide"),
    lon: Number(el.getAttribute("data-lon")),
    lat: Number(el.getAttribute("data-lat")),
    x: Number(el.getAttribute("data-x")),
    z: Number(el.getAttribute("data-z")),
  }));
  const signs = [...document.querySelectorAll('[data-testid="play-shop-signs"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id"),
    draw: el.getAttribute("data-draw"),
    name: el.getAttribute("data-name"),
  }));
  const marker = document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]');
  const leftoverMarker = document.querySelector('[data-testid="shop-marker-shop-local-sharedpc"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const text = document.body.innerText || "";
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left) };
  };
  return {
    title: document.title,
    href: location.href,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    canvas: canvas
      ? { w: canvas.width, h: canvas.height, cw: canvas.clientWidth, ch: canvas.clientHeight, box: box(canvas) }
      : null,
    spawnKeepOut: proof?.getAttribute("data-spawn-keep-out") ?? "",
    shops: proof?.getAttribute("data-shops") ?? "",
    drawnShops: proof?.getAttribute("data-drawn-shops") ?? "",
    shopSigns: proof?.getAttribute("data-shop-signs") ?? "",
    shopStalls: proof?.getAttribute("data-shop-stalls") ?? "",
    heading: proof?.getAttribute("data-heading") ?? "",
    lon: self?.getAttribute("data-lon") ?? "",
    lat: self?.getAttribute("data-lat") ?? "",
    insideAabb: self?.getAttribute("data-inside-aabb") ?? "",
    blocked: self?.getAttribute("data-blocked") ?? "",
    shopMarker: Boolean(marker),
    leftoverMarker: Boolean(leftoverMarker),
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? panel?.getAttribute("data-shop-id") ?? "",
    stalls,
    signs,
    honesty: text.includes("NOT_PLAN_PASS"),
    deniesGta: /no gta|not gta|không.*gta/i.test(text),
  };
})()`;

async function connectPage() {
  const deadline = Date.now() + 25000;
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
  throw new Error(`no CDP page on ${DEBUG_PORT}: ${JSON.stringify(last)}`);
}

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-spawn-clear-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,720",
    PLAYER,
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
  let spawnDom = null;
  const readyDeadline = Date.now() + 14000;
  while (Date.now() < readyDeadline) {
    spawnDom = await evalExpr(ws, 10, SNAP);
    if (spawnDom.playReady === "yes" && spawnDom.canvas && spawnDom.canvas.w >= 200) {
      break;
    }
    await sleep(150);
  }
  const spawnShot = await cdp(ws, 19, "Page.captureScreenshot", { format: "png" });
  const spawnBuf = Buffer.from(spawnShot.data, "base64");
  writeFileSync(SHOT_SPAWN, spawnBuf);
  await keyHold(ws, 20, "w", "KeyW", 87, 2200);
  await sleep(200);
  const walkDom = await evalExpr(ws, 25, SNAP);
  await keyHold(ws, 30, "w", "KeyW", 87, 16000);
  await sleep(350);
  const lanternDom = await evalExpr(ws, 40, SNAP);
  const lanternShot = await cdp(ws, 41, "Page.captureScreenshot", { format: "png" });
  const lanternBuf = Buffer.from(lanternShot.data, "base64");
  writeFileSync(SHOT_LANTERN, lanternBuf);
  await keyHold(ws, 50, "e", "KeyE", 69, 180);
  await sleep(450);
  const shopDom = await evalExpr(ws, 60, SNAP);
  const spawnPng = decodePngRgba(spawnBuf);
  const canvasBox = spawnDom.canvas?.box ?? { left: 0, top: 48, w: 1280, h: 672 };
  const skyBand = bandStats(
    spawnPng.pixels,
    spawnPng.width,
    spawnPng.height,
    canvasBox.left + canvasBox.w * 0.38,
    canvasBox.top + canvasBox.h * 0.06,
    canvasBox.left + canvasBox.w * 0.62,
    canvasBox.top + canvasBox.h * 0.16,
  );
  const napeBand = bandStats(
    spawnPng.pixels,
    spawnPng.width,
    spawnPng.height,
    canvasBox.left + canvasBox.w * 0.32,
    canvasBox.top + canvasBox.h * 0.22,
    canvasBox.left + canvasBox.w * 0.68,
    canvasBox.top + canvasBox.h * 0.48,
  );
  const keepOut = Number(spawnDom.spawnKeepOut || 12);
  const hiddenNearSpawn = (spawnDom.stalls || []).filter((row) => {
    if (!Number.isFinite(row.lon) || !Number.isFinite(row.lat)) return false;
    return distanceM({ lon: row.lon, lat: row.lat }, SPAWN) <= keepOut;
  });
  const lanternStall = (spawnDom.stalls || []).find((row) => row.shop === "shop-lantern-fish");
  const leftoverStall = (spawnDom.stalls || []).find((row) => row.shop === "shop-local-sharedpc");
  const eastStall = (spawnDom.stalls || []).find((row) => row.shop === "shop-local-mtl8ulddihjpre");
  const start = {
    lon: Number(spawnDom.lon),
    lat: Number(spawnDom.lat),
  };
  const afterW = {
    lon: Number(walkDom.lon),
    lat: Number(walkDom.lat),
  };
  const atLantern = {
    lon: Number(lanternDom.lon),
    lat: Number(lanternDom.lat),
  };
  const firstW = deltaM(start, afterW);
  const toLantern = deltaM(start, atLantern);
  const hideOk =
    Number(spawnDom.spawnKeepOut) === 12 &&
    leftoverStall?.draw === "0" &&
    leftoverStall?.collide === "0" &&
    (eastStall ? eastStall.draw === "0" : true) &&
    lanternStall?.draw === "1" &&
    lanternStall?.collide === "1" &&
    spawnDom.leftoverMarker === false &&
    spawnDom.shopMarker === true &&
    hiddenNearSpawn.every((row) => row.shop === "shop-lantern-fish" || row.draw === "0");
  const skyOk =
    skyBand.bluerThanRed &&
    skyBand.blueRatio > 0.22 &&
    skyBand.orangeBoardRatio < 0.08 &&
    napeBand.orangeBoardRatio < 0.12;
  const walkOk =
    firstW.north >= 1.5 &&
    firstW.moved >= 1.5 &&
    walkDom.blocked === "0" &&
    walkDom.insideAabb === "0";
  const shopOk =
    toLantern.north >= 18 &&
    Boolean(lanternDom.shopMarker) &&
    shopDom.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopDom.shopPanelId || "");
  const honestyOk = Boolean(spawnDom.honesty) && Boolean(spawnDom.deniesGta);
  const hash = createHash("sha256").update(spawnBuf).digest("hex").slice(0, 16);
  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict:
      hideOk && skyOk && walkOk && shopOk && honestyOk ? "J5_SPAWN_CLEAR_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    hideOk,
    skyOk,
    walkOk,
    shopOk,
    honestyOk,
    keepOut,
    firstW,
    toLantern,
    spawnDistM: distanceM(start, SPAWN),
    skyBand,
    napeBand,
    hash,
    bytes: spawnBuf.length,
    shotSpawn: SHOT_SPAWN,
    shotLantern: SHOT_LANTERN,
    leftoverStall,
    eastStall,
    lanternStall,
    spawnDom,
    walkDom,
    lanternDom,
    shopDom,
  };
  ws.close();
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_SPAWN_CLEAR_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `keepOut=${report.keepOut}`,
  `walkN=${report.firstW?.north?.toFixed?.(2)}`,
  `lanternN=${report.toLantern?.north?.toFixed?.(2)}`,
  `shop=${report.shopDom?.shopPanelId}`,
  `skyBlue=${report.skyBand?.blueRatio}`,
  `napeOrange=${report.napeBand?.orangeBoardRatio}`,
);
