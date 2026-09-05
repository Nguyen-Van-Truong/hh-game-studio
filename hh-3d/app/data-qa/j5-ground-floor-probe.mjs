/**
 * Street-facing ground floor (door + display glass + thin awning) on recycled 4175.
 * Harbor Walk sides occupied; sky blue; lamps/zebra/lantern stall kept; E still
 * opens shop-lantern-fish. Facade window/door/band counts stay honest.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9402);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-GROUND-FLOOR-2026-09-03.txt");
const SHOT_WALK = join(import.meta.dirname, "j5-3d-ground-floor.png");
const SHOT_STALL = join(import.meta.dirname, "j5-3d-ground-floor-stall.png");

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

function parseHex(hex) {
  const raw = String(hex || "").replace("#", "");
  const full =
    raw.length === 3
      ? raw
          .split("")
          .map((ch) => ch + ch)
          .join("")
      : raw;
  const n = Number.parseInt(full, 16);
  if (!Number.isFinite(n)) {
    return [30, 138, 124];
  }
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function bandStats(pixels, width, height, x0, y0, x1, y1, targetHex) {
  const step = 3;
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let beige = 0;
  let grayish = 0;
  let blueish = 0;
  let teal = 0;
  let dark = 0;
  let light = 0;
  let white = 0;
  let warm = 0;
  let awning = 0;
  let glass = 0;
  let door = 0;
  const [tr, tg, tb] = parseHex(targetHex);
  const buckets = new Set();
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
      const spread = Math.max(r, g, b) - Math.min(r, g, b);
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (spread < 14 && r > 140 && r < 230 && g > 140 && g < 230 && b > 140 && b < 230) {
        grayish += 1;
      }
      if (r > 170 && g > 140 && b < 180 && r - b > 20) {
        beige += 1;
      }
      if (b > r + 8 && b > 90) {
        blueish += 1;
      }
      if (g > r + 6 && g > 55 && b > 40 && r < 150 && g < 200) {
        teal += 1;
      }
      if (lum < 70) {
        dark += 1;
      }
      if (lum > 110) {
        light += 1;
      }
      if (lum > 145 && r > 150 && g > 145 && b > 120 && r - b < 55) {
        white += 1;
      }
      if (r > 150 && g > 110 && b < 120 && r > b + 25) {
        warm += 1;
      }
      const dist = Math.abs(r - tr) + Math.abs(g - tg) + Math.abs(b - tb);
      if (dist < 95 && spread > 18) {
        awning += 1;
      }
      if (lum < 88 && b >= r - 4 && b > 16 && r < 95 && g < 100 && r - b < 18) {
        glass += 1;
      }
      if (lum < 48 && r >= g - 4 && r > b + 2 && r < 72 && b < 50) {
        door += 1;
      }
      buckets.add(`${r >> 4}:${g >> 4}:${b >> 4}`);
    }
  }
  const meanR = n ? sumR / n : 0;
  const meanG = n ? sumG / n : 0;
  const meanB = n ? sumB / n : 0;
  const lum = 0.2126 * meanR + 0.7152 * meanG + 0.0722 * meanB;
  return {
    samples: n,
    meanR: Number(meanR.toFixed(1)),
    meanG: Number(meanG.toFixed(1)),
    meanB: Number(meanB.toFixed(1)),
    lum: Number(lum.toFixed(1)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    grayRatio: Number((grayish / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    tealRatio: Number((teal / Math.max(1, n)).toFixed(3)),
    darkRatio: Number((dark / Math.max(1, n)).toFixed(3)),
    lightRatio: Number((light / Math.max(1, n)).toFixed(3)),
    whiteRatio: Number((white / Math.max(1, n)).toFixed(3)),
    warmRatio: Number((warm / Math.max(1, n)).toFixed(3)),
    awningRatio: Number((awning / Math.max(1, n)).toFixed(3)),
    glassRatio: Number((glass / Math.max(1, n)).toFixed(3)),
    doorRatio: Number((door / Math.max(1, n)).toFixed(3)),
    uniqueQ16: buckets.size,
    bluerThanRed: meanB > meanR + 6,
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const proof = document.querySelector('[data-testid="play-proof"]');
  const self = document.querySelector('[data-testid="self-avatar"]');
  const floors = [...document.querySelectorAll('[data-testid="play-ground-floors"] li')].map((el) => ({
    testid: el.getAttribute("data-testid"),
    building: el.getAttribute("data-building-id"),
    street: el.getAttribute("data-street"),
    displays: Number(el.getAttribute("data-displays") ?? "0"),
    storefronts: Number(el.getAttribute("data-storefronts") ?? "0"),
    awnings: Number(el.getAttribute("data-awnings") ?? "0"),
  }));
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    testid: el.getAttribute("data-testid"),
    shop: el.getAttribute("data-shop-id"),
    kind: el.getAttribute("data-kind"),
    awning: el.getAttribute("data-awning"),
  }));
  const props = [...document.querySelectorAll('[data-testid="play-street-props"] li')].map((el) => ({
    testid: el.getAttribute("data-testid"),
    kind: el.getAttribute("data-kind"),
  }));
  const marker = document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]');
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
    sky: proof?.getAttribute("data-sky") ?? "",
    sun: proof?.getAttribute("data-sun") ?? "",
    light: proof?.getAttribute("data-light") ?? "",
    ground: proof?.getAttribute("data-ground") ?? "",
    streetProps: proof?.getAttribute("data-street-props") ?? "",
    lamps: proof?.getAttribute("data-lamps") ?? "",
    crosswalks: proof?.getAttribute("data-crosswalks") ?? "",
    planters: proof?.getAttribute("data-planters") ?? "",
    buildings: proof?.getAttribute("data-buildings") ?? "",
    facade: proof?.getAttribute("data-facade") ?? "",
    windows: proof?.getAttribute("data-facade-windows") ?? "",
    doors: proof?.getAttribute("data-facade-doors") ?? "",
    bands: proof?.getAttribute("data-facade-bands") ?? "",
    facadeTotal: proof?.getAttribute("data-facade-total") ?? "",
    groundFloor: proof?.getAttribute("data-ground-floor") ?? "",
    gfBuildings: proof?.getAttribute("data-ground-floor-buildings") ?? "",
    gfFaces: proof?.getAttribute("data-ground-floor-faces") ?? "",
    gfDisplays: proof?.getAttribute("data-ground-floor-displays") ?? "",
    gfStorefronts: proof?.getAttribute("data-ground-floor-storefronts") ?? "",
    gfAwnings: proof?.getAttribute("data-ground-floor-awnings") ?? "",
    shops: proof?.getAttribute("data-shops") ?? "",
    shopStalls: proof?.getAttribute("data-shop-stalls") ?? "",
    shopStallKind: proof?.getAttribute("data-shop-stall-kind") ?? "",
    shopSignKind: proof?.getAttribute("data-shop-sign-kind") ?? "",
    heading: proof?.getAttribute("data-heading") ?? "",
    lon: self?.getAttribute("data-lon") ?? "",
    lat: self?.getAttribute("data-lat") ?? "",
    insideAabb: self?.getAttribute("data-inside-aabb") ?? "",
    shopMarker: Boolean(marker),
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? panel?.getAttribute("data-shop-id") ?? "",
    lanternAwning: marker?.getAttribute("data-awning") ?? "",
    floors,
    stalls,
    props,
    honesty: text.includes("NOT_PLAN_PASS"),
    deniesGta: /no gta|not gta|không.*gta/i.test(text),
    deniesTwin: /not a digital twin|not 1:1|không.*1:1/i.test(text),
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

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-gf-"));
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
  let dom = null;
  const readyDeadline = Date.now() + 12000;
  while (Date.now() < readyDeadline) {
    dom = await evalExpr(ws, 10, SNAP);
    if (dom.playReady === "yes" && dom.canvas && dom.canvas.w >= 200 && Number(dom.gfFaces) >= 1) {
      break;
    }
    await sleep(150);
  }
  const spawnDom = dom;
  await keyHold(ws, 20, "w", "KeyW", 87, 4500);
  await sleep(250);
  const walkDom = await evalExpr(ws, 25, SNAP);
  const walkShot = await cdp(ws, 26, "Page.captureScreenshot", { format: "png" });
  const walkBuf = Buffer.from(walkShot.data, "base64");
  writeFileSync(SHOT_WALK, walkBuf);
  await keyHold(ws, 30, "w", "KeyW", 87, 9500);
  await sleep(400);
  const stallDom = await evalExpr(ws, 35, SNAP);
  const stallShot = await cdp(ws, 36, "Page.captureScreenshot", { format: "png" });
  const stallBuf = Buffer.from(stallShot.data, "base64");
  writeFileSync(SHOT_STALL, stallBuf);
  await keyHold(ws, 40, "e", "KeyE", 69, 180);
  await sleep(450);
  const shopDom = await evalExpr(ws, 50, SNAP);
  const png = decodePngRgba(walkBuf);
  const stallPng = decodePngRgba(stallBuf);
  const canvasBox = walkDom.canvas?.box ?? { left: 0, top: 48, w: 1280, h: 672 };
  const awningHex =
    stallDom.stalls.find((row) => row.shop === "shop-lantern-fish")?.awning ||
    stallDom.lanternAwning ||
    "#6e3d9a";
  const skyBand = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.left + canvasBox.w * 0.4,
    canvasBox.top + canvasBox.h * 0.07,
    canvasBox.left + canvasBox.w * 0.6,
    canvasBox.top + canvasBox.h * 0.14,
    awningHex,
  );
  const leftFloor = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.left + canvasBox.w * 0.04,
    canvasBox.top + canvasBox.h * 0.3,
    canvasBox.left + canvasBox.w * 0.26,
    canvasBox.top + canvasBox.h * 0.68,
    awningHex,
  );
  const rightFloor = bandStats(
    png.pixels,
    png.width,
    png.height,
    canvasBox.left + canvasBox.w * 0.74,
    canvasBox.top + canvasBox.h * 0.3,
    canvasBox.left + canvasBox.w * 0.96,
    canvasBox.top + canvasBox.h * 0.68,
    awningHex,
  );
  const stallAwning = bandStats(
    stallPng.pixels,
    stallPng.width,
    stallPng.height,
    canvasBox.left + canvasBox.w * 0.28,
    canvasBox.top + canvasBox.h * 0.22,
    canvasBox.left + canvasBox.w * 0.72,
    canvasBox.top + canvasBox.h * 0.52,
    awningHex,
  );
  const zebraBand = bandStats(
    stallPng.pixels,
    stallPng.width,
    stallPng.height,
    canvasBox.left + canvasBox.w * 0.32,
    canvasBox.top + canvasBox.h * 0.5,
    canvasBox.left + canvasBox.w * 0.68,
    canvasBox.top + canvasBox.h * 0.78,
    awningHex,
  );
  const sideGlass = leftFloor.glassRatio + rightFloor.glassRatio;
  const sideDoor = leftFloor.doorRatio + rightFloor.doorRatio;
  const facadeOk =
    walkDom.facade === "inset" &&
    Number(walkDom.windows) === 2141 &&
    Number(walkDom.doors) === 60 &&
    Number(walkDom.bands) === 472;
  const groundOk =
    walkDom.groundFloor === "door-glass-awning" &&
    Number(walkDom.gfFaces) >= 24 &&
    Number(walkDom.gfDisplays) >= 20 &&
    Number(walkDom.gfStorefronts) >= 20 &&
    Number(walkDom.gfAwnings) >= 20 &&
    walkDom.floors.some((row) => /harbor-walk/.test(row.street) && row.storefronts >= 1 && row.displays >= 1) &&
    walkDom.floors.some((row) => /tram-approach/.test(row.street) && row.storefronts >= 1) &&
    (leftFloor.glassRatio >= 0.02 || rightFloor.glassRatio >= 0.02) &&
    sideGlass >= 0.03 &&
    sideDoor >= 0.008;
  const skyOk =
    walkDom.sky === "gradient-hemisphere" &&
    walkDom.sun === "disc" &&
    skyBand.beigeRatio < 0.22 &&
    (skyBand.bluerThanRed || skyBand.blueRatio > 0.22) &&
    skyBand.meanB > skyBand.meanR;
  const propsOk =
    walkDom.streetProps === "lamps-crosswalk-planters" &&
    Number(walkDom.lamps) >= 12 &&
    Number(walkDom.crosswalks) === 1 &&
    walkDom.props.some((row) => row.kind === "crosswalk") &&
    zebraBand.whiteRatio >= 0.03;
  const stallOk =
    stallDom.shopStallKind === "awning-kiosk" &&
    Number(stallDom.shopStalls) >= 1 &&
    stallDom.shopSignKind === "pole-board" &&
    stallDom.stalls.some((row) => row.shop === "shop-lantern-fish" && row.kind === "awning-kiosk") &&
    stallAwning.awningRatio >= 0.03;
  const shopOk =
    Boolean(stallDom.shopMarker) &&
    shopDom.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopDom.shopPanelId || "") &&
    walkDom.insideAabb === "0";
  const honestyOk = Boolean(walkDom.honesty) && Boolean(walkDom.deniesGta);
  const hash = createHash("sha256").update(walkBuf).digest("hex").slice(0, 16);
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-24",
    player: PLAYER,
    verdict:
      facadeOk && groundOk && skyOk && propsOk && stallOk && shopOk && honestyOk
        ? "J5_GROUND_FLOOR_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    facadeOk,
    groundOk,
    skyOk,
    propsOk,
    stallOk,
    shopOk,
    honestyOk,
    awningHex,
    skyBand,
    leftFloor,
    rightFloor,
    sideGlass,
    sideDoor,
    stallAwning,
    zebraBand,
    hash,
    bytes: walkBuf.length,
    shotWalk: SHOT_WALK,
    shotStall: SHOT_STALL,
    spawnDom,
    walkDom,
    stallDom,
    shopDom,
  };
  ws.close();
} catch (err) {
  report = {
    run_id: "HH3D-J5-20260903-ASIA-SAIGON-24",
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_GROUND_FLOOR_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `faces=${report.walkDom?.gfFaces}`,
  `displays=${report.walkDom?.gfDisplays}`,
  `storefronts=${report.walkDom?.gfStorefronts}`,
  `windows=${report.walkDom?.windows}`,
  `doors=${report.walkDom?.doors}`,
  `bands=${report.walkDom?.bands}`,
  `blue=${report.skyBand?.blueRatio}`,
  `glass=${report.sideGlass?.toFixed?.(3)}`,
  `shop=${report.shopDom?.shopPanelId}`,
);
