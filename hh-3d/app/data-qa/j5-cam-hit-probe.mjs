/**
 * Follow-camera pull-in vs footprint rings on recycled 4175.
 * Walk into Steps East, turn so the behind-camera would enter the box,
 * distance shrinks, shot stays street/sky. E + opposite-stride kept.
 * NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9472);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-CAM-HIT-2026-09-03.txt");
const SHOT_OPEN = join(import.meta.dirname, "j5-3d-cam-open.png");
const SHOT_HIT = join(import.meta.dirname, "j5-3d-cam-hit.png");
const M_PER_DEG_LAT = 111320;
const RUN_ID = "HH3D-J5-20260903-ASIA-SAIGON-37";

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

function ringAabb(ring) {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const pt of ring) {
    if (!Array.isArray(pt) || pt.length < 2) continue;
    west = Math.min(west, pt[0]);
    east = Math.max(east, pt[0]);
    south = Math.min(south, pt[1]);
    north = Math.max(north, pt[1]);
  }
  return { west, south, east, north };
}

function pointInAabb(lon, lat, box) {
  return lon >= box.west && lon <= box.east && lat >= box.south && lat <= box.north;
}

function pointInRing(lon, lat, ring) {
  let inside = false;
  const n = ring.length;
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const pi = ring[i];
    const pj = ring[j];
    if (!pi || !pj || pj[1] === pi[1]) continue;
    if (pi[1] > lat !== pj[1] > lat && lon < ((pj[0] - pi[0]) * (lat - pi[1])) / (pj[1] - pi[1]) + pi[0]) {
      inside = !inside;
    }
  }
  return inside;
}

function distToAabb(lon, lat, box) {
  const closestLon = Math.min(box.east, Math.max(box.west, lon));
  const closestLat = Math.min(box.north, Math.max(box.south, lat));
  return distanceM({ lon, lat }, { lon: closestLon, lat: closestLat });
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

async function keyHold(ws, id, key, code, vk, ms, modifiers = 0) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
  });
  await sleep(ms);
  await cdp(ws, id + 1, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
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
  let darkGray = 0;
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
      const maxc = Math.max(r, g, b);
      const minc = Math.min(r, g, b);
      if (maxc < 72 && maxc - minc < 18) darkGray += 1;
    }
  }
  const meanR = sumR / Math.max(1, n);
  const meanG = sumG / Math.max(1, n);
  const meanB = sumB / Math.max(1, n);
  return {
    meanR: Number(meanR.toFixed(1)),
    meanG: Number(meanG.toFixed(1)),
    meanB: Number(meanB.toFixed(1)),
    lum: Number(((0.2126 * meanR + 0.7152 * meanG + 0.0722 * meanB) / 255).toFixed(3)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    darkGrayRatio: Number((darkGray / Math.max(1, n)).toFixed(3)),
    bluerThanRed: meanB > meanR + 6,
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const playCanvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const cycle = document.querySelector('[data-testid="walk-cycle-proof"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const live = window.__hhWalkCycle || null;
  const canvasLimb = playCanvas instanceof HTMLElement ? {
    kind: playCanvas.dataset.walkCycle ?? "",
    moving: playCanvas.dataset.limbMoving ?? "",
    running: playCanvas.dataset.limbRunning ?? "",
    leftLeg: Number(playCanvas.dataset.limbLeftLeg ?? "NaN"),
    rightLeg: Number(playCanvas.dataset.limbRightLeg ?? "NaN"),
    leftArm: Number(playCanvas.dataset.limbLeftArm ?? "NaN"),
    rightArm: Number(playCanvas.dataset.limbRightArm ?? "NaN"),
    spread: Number(playCanvas.dataset.limbSpread ?? "NaN"),
    opposite: playCanvas.dataset.limbOpposite ?? "",
  } : null;
  const r = playCanvas ? playCanvas.getBoundingClientRect() : null;
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    playEngine: play?.getAttribute("data-engine") ?? "",
    playCanvas: Boolean(playCanvas),
    canvasBox: r ? { x: r.left, y: r.top, w: r.width, h: r.height } : null,
    pose: avatar?.getAttribute("data-pose") ?? "",
    body: avatar?.getAttribute("data-body") ?? proof?.getAttribute("data-body") ?? "",
    walkCycle: proof?.getAttribute("data-walk-cycle") ?? cycle?.getAttribute("data-walk-cycle") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? proof?.getAttribute("data-heading") ?? "NaN"),
    camera: proof?.getAttribute("data-camera") ?? "",
    follow: proof?.getAttribute("data-follow") ?? "",
    camYaw: Number(proof?.getAttribute("data-cam-yaw") ?? "NaN"),
    camPitch: Number(proof?.getAttribute("data-cam-pitch") ?? "NaN"),
    camKind: proof?.getAttribute("data-cam-kind") ?? "",
    camHit: proof?.getAttribute("data-cam-hit") ?? "",
    camHitId: proof?.getAttribute("data-cam-hit-id") ?? "",
    camDist: Number(proof?.getAttribute("data-cam-dist") ?? "NaN"),
    camDesired: Number(proof?.getAttribute("data-cam-desired") ?? "NaN"),
    camX: Number(proof?.getAttribute("data-cam-x") ?? "NaN"),
    camY: Number(proof?.getAttribute("data-cam-y") ?? "NaN"),
    camZ: Number(proof?.getAttribute("data-cam-z") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    collision: proof?.getAttribute("data-collision") ?? "",
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    insideRing: proof?.getAttribute("data-inside-ring") ?? "",
    scooters: proof?.getAttribute("data-scooters") ?? "",
    marketSpill: proof?.getAttribute("data-market-spill") ?? "",
    marketSpillCount: proof?.getAttribute("data-market-spill-count") ?? "",
    lamps: proof?.getAttribute("data-lamps") ?? "",
    sky: proof?.getAttribute("data-sky") ?? "",
    roof: proof?.getAttribute("data-roof") ?? "",
    live,
    canvasLimb,
    shopMarker: Boolean(document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]')),
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? panel?.getAttribute("data-shop-id") ?? "",
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.innerText ??
      document.body.innerText.slice(0, 400),
    gtaClaim: /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
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

async function waitReady(ws, id) {
  let snap = null;
  const deadline = Date.now() + 14000;
  while (Date.now() < deadline) {
    snap = await evalExpr(ws, id, SNAP);
    if (snap.playReady === "yes" && Number.isFinite(snap.lon) && snap.buildings >= 20) {
      return snap;
    }
    await sleep(150);
  }
  return snap;
}

function headingError(from, to) {
  return ((to - from + 540) % 360) - 180;
}

async function turnTo(ws, id, target, tol = 4) {
  let snap = await evalExpr(ws, id, SNAP);
  for (let i = 0; i < 18; i += 1) {
    const err = headingError(Number(snap.heading ?? 0), target);
    if (Math.abs(err) <= tol) {
      return { snap, id };
    }
    const ms = Math.min(420, Math.max(50, (Math.abs(err) / 110) * 1000 * 0.72));
    if (err > 0) {
      await keyHold(ws, id + 1, "d", "KeyD", 68, ms);
    } else {
      await keyHold(ws, id + 1, "a", "KeyA", 65, ms);
    }
    id += 3;
    await sleep(90);
    snap = await evalExpr(ws, id, SNAP);
  }
  return { snap, id };
}

async function sampleWalk(ws, id, holdMs) {
  const rows = [];
  const deadline = Date.now() + holdMs;
  let n = id;
  while (Date.now() < deadline) {
    const snap = await evalExpr(ws, n, SNAP);
    n += 1;
    const live = snap.live || snap.canvasLimb;
    if (live && Number.isFinite(Number(live.leftLeg ?? live.spread))) {
      rows.push({
        pose: snap.pose,
        spread: Number(live.spread),
        leftLeg: Number(live.leftLeg),
        rightLeg: Number(live.rightLeg),
        leftArm: Number(live.leftArm),
        rightArm: Number(live.rightArm),
        opposite: live.opposite === true || live.opposite === "1",
        moving: live.moving === true || live.moving === "1",
      });
    }
    await sleep(70);
  }
  const moving = rows.filter((row) => row.moving);
  const pool = moving.length ? moving : rows;
  const peak = pool.reduce((best, row) => (!best || row.spread > best.spread ? row : best), null);
  return { rows, peak, nextId: n };
}

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-cam-hit-"));
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
  await cdp(ws, 4, "Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "no-preference" }],
  });
  await cdp(ws, 5, "Page.navigate", { url: `${PLAYER}?seat=a` });

  const geoRes = await fetch(new URL("/data/ben-thanh-400m.authored.geojson", PLAYER));
  const geo = await geoRes.json();
  const liveBuildings = geo.features
    .filter((feature) => feature.properties?.kind === "building")
    .map((feature) => ({
      id: String(feature.id ?? feature.properties.id),
      ring: feature.geometry.coordinates[0],
      ...ringAabb(feature.geometry.coordinates[0]),
    }));

  const home = await waitReady(ws, 10);
  const openShot = await cdp(ws, 11, "Page.captureScreenshot", { format: "png" });
  const openBuf = Buffer.from(openShot.data, "base64");
  writeFileSync(SHOT_OPEN, openBuf);

  await keyHold(ws, 20, "w", "KeyW", 87, 3500);
  await sleep(150);
  const upStreet = await evalExpr(ws, 30, SNAP);
  const walkSample = await (async () => {
    await cdp(ws, 31, "Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "w",
      code: "KeyW",
      windowsVirtualKeyCode: 87,
      nativeVirtualKeyCode: 87,
    });
    const sampled = await sampleWalk(ws, 32, 1100);
    await cdp(ws, sampled.nextId, "Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "w",
      code: "KeyW",
      windowsVirtualKeyCode: 87,
      nativeVirtualKeyCode: 87,
    });
    return sampled;
  })();

  const eastFace = await turnTo(ws, 80, 90, 4);
  await keyHold(ws, eastFace.id + 5, "w", "KeyW", 87, 10000);
  await sleep(200);
  const atWall = await evalExpr(ws, 120, SNAP);
  await keyHold(ws, 121, "w", "KeyW", 87, 2500);
  await sleep(150);
  const wallStill = await evalExpr(ws, 130, SNAP);

  const westFace = await turnTo(ws, 140, 270, 4);
  await sleep(180);
  const pulled = await evalExpr(ws, westFace.id + 8, SNAP);
  const hitShot = await cdp(ws, 200, "Page.captureScreenshot", { format: "png" });
  const hitBuf = Buffer.from(hitShot.data, "base64");
  writeFileSync(SHOT_HIT, hitBuf);

  await cdp(ws, 210, "Page.navigate", { url: `${PLAYER}?seat=a` });
  const shopHome = await waitReady(ws, 220);
  await keyHold(ws, 230, "w", "KeyW", 87, 16000);
  await sleep(250);
  const atLantern = await evalExpr(ws, 240, SNAP);
  await keyHold(ws, 250, "e", "KeyE", 69, 180);
  await sleep(450);
  const shopOpen = await evalExpr(ws, 260, SNAP);

  const openPng = decodePngRgba(openBuf);
  const hitPng = decodePngRgba(hitBuf);
  const box = pulled.canvasBox ?? home.canvasBox ?? { x: 0, y: 0, w: 1280, h: 720 };
  const skyOpen = bandStats(
    openPng.pixels,
    openPng.width,
    openPng.height,
    box.x + box.w * 0.34,
    box.y + box.h * 0.03,
    box.x + box.w * 0.66,
    box.y + box.h * 0.18,
  );
  const skyHit = bandStats(
    hitPng.pixels,
    hitPng.width,
    hitPng.height,
    box.x + box.w * 0.58,
    box.y + box.h * 0.14,
    box.x + box.w * 0.86,
    box.y + box.h * 0.3,
  );
  const midHit = bandStats(
    hitPng.pixels,
    hitPng.width,
    hitPng.height,
    box.x + box.w * 0.28,
    box.y + box.h * 0.28,
    box.x + box.w * 0.72,
    box.y + box.h * 0.72,
  );

  const pos = (snap) => ({ lon: snap.lon, lat: snap.lat });
  const street = deltaM(pos(home), pos(upStreet));
  const toward = deltaM(pos(eastFace.snap), pos(atWall));
  const extra = deltaM(pos(atWall), pos(wallStill));
  const lanternDelta = deltaM(pos(shopHome), pos(atLantern));
  const insideRing = liveBuildings.filter((row) => pointInRing(pulled.lon, pulled.lat, row.ring)).map((row) => row.id);
  const insideAabb = liveBuildings.filter((row) => pointInAabb(pulled.lon, pulled.lat, row)).map((row) => row.id);
  const nearest = liveBuildings
    .map((row) => ({ id: row.id, dist: distToAabb(pulled.lon, pulled.lat, row) }))
    .sort((a, b) => a.dist - b.dist)[0];

  const peak = walkSample.peak;
  const walkOpposite =
    Boolean(peak?.opposite) &&
    Number.isFinite(peak?.leftLeg) &&
    Number.isFinite(peak?.leftArm) &&
    peak.leftLeg * peak.leftArm <= 0.04;
  const openDist = Number(home.camDist);
  const pulledDist = Number(pulled.camDist);
  const desiredDist = Number(pulled.camDesired);

  const playOk =
    home.playReady === "yes" &&
    home.playEngine === "r3f" &&
    home.camera === "behind" &&
    home.camKind === "look-ray-ring" &&
    home.buildings >= 60 &&
    home.collision === "footprint-radius" &&
    home.walkCycle === "opposite-stride" &&
    home.body === "tunic-humanoid";
  const openOk = home.camHit === "0" && openDist > 5.1 && openDist < 6.4;
  const wallOk =
    toward.east > 6 &&
    extra.east < 0.7 &&
    nearest &&
    nearest.dist < 1.3 &&
    /steps-e|harbor/i.test(nearest.id);
  const pulledOk =
    pulled.camHit === "1" &&
    /bldg-steps-e/i.test(pulled.camHitId || "") &&
    Math.abs(headingError(Number(pulled.camYaw), 270)) < 25 &&
    pulledDist + 1.2 < Math.max(openDist, desiredDist) &&
    pulledDist < 3.6 &&
    pulled.insideRing === "0" &&
    insideRing.length === 0;
  const streetShotOk =
    midHit.darkGrayRatio < 0.5 &&
    midHit.lum > 0.16 &&
    (skyHit.blueRatio > 0.06 ||
      skyHit.bluerThanRed ||
      midHit.blueRatio > 0.1 ||
      midHit.beigeRatio > 0.06);
  const cycleOk = home.walkCycle === "opposite-stride" && walkOpposite && (peak?.spread ?? 0) >= 1.4;
  const shopOk =
    Boolean(atLantern.shopMarker) &&
    shopOpen.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "") &&
    lanternDelta.north > 8;
  const keptOk =
    Number(home.scooters) === 15 &&
    home.marketSpill === "crate-basket-stack" &&
    Number(home.lamps) >= 12 &&
    home.sky === "gradient-hemisphere" &&
    home.roof === "parapet-ac-tank";
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict:
      playOk && openOk && wallOk && pulledOk && streetShotOk && cycleOk && shopOk && keptOk && honestyOk
        ? "J5_CAM_HIT_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    playOk,
    openOk,
    wallOk,
    pulledOk,
    streetShotOk,
    cycleOk,
    shopOk,
    keptOk,
    honestyOk,
    openDist,
    pulledDist,
    desiredDist,
    camHitId: pulled.camHitId,
    headingAtPull: pulled.heading,
    camYawAtPull: pulled.camYaw,
    street,
    toward,
    extra,
    lanternDelta,
    nearest,
    insideRing,
    insideAabb,
    skyOpen,
    skyHit,
    midHit,
    walkPeak: peak,
    shopPanelId: shopOpen.shopPanelId,
    hashes: {
      open: createHash("sha256").update(openBuf).digest("hex").slice(0, 16),
      hit: createHash("sha256").update(hitBuf).digest("hex").slice(0, 16),
    },
    shots: { open: SHOT_OPEN, hit: SHOT_HIT },
    home: {
      camKind: home.camKind,
      camHit: home.camHit,
      camDist: home.camDist,
      buildings: home.buildings,
      collision: home.collision,
      walkCycle: home.walkCycle,
    },
    pulled: {
      camHit: pulled.camHit,
      camHitId: pulled.camHitId,
      camDist: pulled.camDist,
      camDesired: pulled.camDesired,
      heading: pulled.heading,
      insideRing: pulled.insideRing,
    },
    shopOpen: { id: shopOpen.shopPanelId, open: shopOpen.shopPanel },
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
if (report.verdict !== "J5_CAM_HIT_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `open=${report.openDist}`,
  `pulled=${report.pulledDist}`,
  `hit=${report.camHitId}`,
  `shop=${report.shopPanelId}`,
);
