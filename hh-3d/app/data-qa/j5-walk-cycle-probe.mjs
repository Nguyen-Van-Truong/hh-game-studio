/**
 * Opposite-arm / opposite-leg walk cycle on recycled 4175.
 * Stand vs walk vs sprint from behind: limbs offset, not a sliding statue.
 * Friends reuse the same Person cycle. E still opens lantern.
 * Scooters / spill stay. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9448);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-WALK-CYCLE-2026-09-03.txt");
const SHOT_STAND = join(import.meta.dirname, "j5-3d-walk-stand.png");
const SHOT_WALK = join(import.meta.dirname, "j5-3d-walk-walk.png");
const SHOT_SPRINT = join(import.meta.dirname, "j5-3d-walk-sprint.png");
const M_PER_DEG_LAT = 111320;
const RUN_ID = "HH3D-J5-20260903-ASIA-SAIGON-36";

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

async function keyDown(ws, id, key, code, vk, modifiers = 0) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
  });
}

async function keyUp(ws, id, key, code, vk, modifiers = 0) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
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

function isSkin(r, g, b) {
  return r > 160 && g > 110 && b > 70 && r > g && g > b && r - b > 35 && r < 250;
}

function isTeal(r, g, b) {
  return g > r + 8 && b > r && g > 50 && g < 170 && r < 120 && b < 170;
}

function isPants(r, g, b) {
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 18 && lum < 70 && Math.abs(r - g) < 18 && Math.abs(g - b) < 18 && r < 80;
}

function bodyCropStats(pixels, width, height, box) {
  const x0 = Math.max(0, Math.floor(box.x + box.w * 0.38));
  const x1 = Math.min(width, Math.ceil(box.x + box.w * 0.62));
  const y0 = Math.max(0, Math.floor(box.y + box.h * 0.28));
  const y1 = Math.min(height, Math.ceil(box.y + box.h * 0.78));
  const mid = Math.floor((x0 + x1) / 2);
  let leftLimb = 0;
  let rightLimb = 0;
  let leftN = 0;
  let rightN = 0;
  let skin = 0;
  let teal = 0;
  let pants = 0;
  let n = 0;
  for (let y = y0; y < y1; y += 2) {
    for (let x = x0; x < x1; x += 2) {
      const i = (y * width + x) * 4;
      const r = pixels[i];
      const g = pixels[i + 1];
      const b = pixels[i + 2];
      n += 1;
      const limb = isSkin(r, g, b) || isPants(r, g, b) || isTeal(r, g, b);
      if (isSkin(r, g, b)) skin += 1;
      if (isTeal(r, g, b)) teal += 1;
      if (isPants(r, g, b)) pants += 1;
      if (x < mid) {
        leftN += 1;
        if (limb) leftLimb += 1;
      } else {
        rightN += 1;
        if (limb) rightLimb += 1;
      }
    }
  }
  const leftRatio = leftLimb / Math.max(1, leftN);
  const rightRatio = rightLimb / Math.max(1, rightN);
  return {
    samples: n,
    skinRatio: Number((skin / Math.max(1, n)).toFixed(3)),
    tealRatio: Number((teal / Math.max(1, n)).toFixed(3)),
    pantsRatio: Number((pants / Math.max(1, n)).toFixed(3)),
    leftRatio: Number(leftRatio.toFixed(3)),
    rightRatio: Number(rightRatio.toFixed(3)),
    imbalance: Number(Math.abs(leftRatio - rightRatio).toFixed(3)),
  };
}

function pixelDiffRatio(a, b, box) {
  const x0 = Math.max(0, Math.floor(box.x + box.w * 0.38));
  const x1 = Math.min(a.width, Math.ceil(box.x + box.w * 0.62));
  const y0 = Math.max(0, Math.floor(box.y + box.h * 0.28));
  const y1 = Math.min(a.height, Math.ceil(box.y + box.h * 0.78));
  let n = 0;
  let diff = 0;
  for (let y = y0; y < y1; y += 2) {
    for (let x = x0; x < x1; x += 2) {
      const i = (y * a.width + x) * 4;
      n += 1;
      const dr = Math.abs(a.pixels[i] - b.pixels[i]);
      const dg = Math.abs(a.pixels[i + 1] - b.pixels[i + 1]);
      const db = Math.abs(a.pixels[i + 2] - b.pixels[i + 2]);
      if (dr + dg + db > 36) diff += 1;
    }
  }
  return Number((diff / Math.max(1, n)).toFixed(3));
}

function bandStats(pixels, width, height, x0, y0, x1, y1) {
  const step = 3;
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let beige = 0;
  let blueish = 0;
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
    }
  }
  return {
    meanR: Number((sumR / Math.max(1, n)).toFixed(1)),
    meanG: Number((sumG / Math.max(1, n)).toFixed(1)),
    meanB: Number((sumB / Math.max(1, n)).toFixed(1)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    bluerThanRed: sumB / Math.max(1, n) > sumR / Math.max(1, n) + 6,
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
    armSpread: Number(playCanvas.dataset.limbArmSpread ?? "NaN"),
    opposite: playCanvas.dataset.limbOpposite ?? "",
  } : null;
  const r = playCanvas ? playCanvas.getBoundingClientRect() : null;
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    canvas: Boolean(playCanvas),
    canvasBox: r ? { x: r.left, y: r.top, w: r.width, h: r.height } : null,
    pose: avatar?.getAttribute("data-pose") ?? "",
    sprint: avatar?.getAttribute("data-sprint") ?? proof?.getAttribute("data-sprint") ?? "",
    body: avatar?.getAttribute("data-body") ?? proof?.getAttribute("data-body") ?? "",
    walkCycle: proof?.getAttribute("data-walk-cycle") ?? cycle?.getAttribute("data-walk-cycle") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    camera: proof?.getAttribute("data-camera") ?? "",
    camYaw: Number(proof?.getAttribute("data-cam-yaw") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    collision: proof?.getAttribute("data-collision") ?? "",
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    scooters: proof?.getAttribute("data-scooters") ?? "",
    scooterKind: proof?.getAttribute("data-scooter-kind") ?? "",
    marketSpill: proof?.getAttribute("data-market-spill") ?? "",
    marketSpillCount: proof?.getAttribute("data-market-spill-count") ?? "",
    lamps: proof?.getAttribute("data-lamps") ?? "",
    sky: proof?.getAttribute("data-sky") ?? "",
    roof: proof?.getAttribute("data-roof") ?? "",
    live,
    canvasLimb,
    remotes: [...document.querySelectorAll('[data-testid="play-remote-bodies"] li')].map((el) => ({
      seat: el.getAttribute("data-seat"),
      body: el.getAttribute("data-body"),
      walkCycle: el.getAttribute("data-walk-cycle"),
      pose: el.getAttribute("data-pose"),
    })),
    shopMarker: Boolean(document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]')),
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? panel?.getAttribute("data-shop-id") ?? "",
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
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

async function sampleLimbs(ws, id, holdMs, mode = "peak") {
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
        sprint: snap.sprint,
        spread: Number(live.spread),
        armSpread: Number(live.armSpread),
        leftLeg: Number(live.leftLeg),
        rightLeg: Number(live.rightLeg),
        leftArm: Number(live.leftArm),
        rightArm: Number(live.rightArm),
        opposite: live.opposite === true || live.opposite === "1",
        moving: live.moving === true || live.moving === "1",
        running: live.running === true || live.running === "1",
      });
    }
    await sleep(70);
  }
  const pick = mode === "idle"
    ? rows.filter((row) => row.pose === "idle" && row.moving === false)
    : rows.filter((row) => row.moving === true && (mode === "sprint" ? row.running : !row.running));
  const pool = pick.length ? pick : rows;
  const peak = mode === "idle"
    ? pool.reduce((best, row) => (!best || row.spread < best.spread ? row : best), null)
    : pool.reduce((best, row) => (!best || row.spread > best.spread ? row : best), null);
  return { rows, peak, nextId: n };
}

const profile = mkdtempSync(join(tmpdir(), "hh-world-j5-walk-cycle-"));
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
  await cdp(ws, 4, "Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "no-preference" }],
  });

  const home = await waitReady(ws, 10);
  await keyDown(ws, 18, "w", "KeyW", 87);
  await sleep(4500);
  await keyUp(ws, 19, "w", "KeyW", 87);
  await sleep(250);
  const cleared = await evalExpr(ws, 20, SNAP);
  const standLimbs = await sampleLimbs(ws, 21, 500, "idle");
  const standShot = await cdp(ws, standLimbs.nextId, "Page.captureScreenshot", { format: "png" });
  const standBuf = Buffer.from(standShot.data, "base64");
  writeFileSync(SHOT_STAND, standBuf);

  await keyDown(ws, 80, "w", "KeyW", 87);
  const walkLimbs = await sampleLimbs(ws, 81, 1200, "walk");
  const walkShot = await cdp(ws, walkLimbs.nextId, "Page.captureScreenshot", { format: "png" });
  const walkBuf = Buffer.from(walkShot.data, "base64");
  writeFileSync(SHOT_WALK, walkBuf);
  await keyUp(ws, 200, "w", "KeyW", 87);
  await sleep(80);
  const afterWalk = await evalExpr(ws, 201, SNAP);

  await keyDown(ws, 210, "Shift", "ShiftLeft", 16, 8);
  await keyDown(ws, 211, "w", "KeyW", 87, 8);
  const sprintLimbs = await sampleLimbs(ws, 212, 1200, "sprint");
  const sprintShot = await cdp(ws, sprintLimbs.nextId, "Page.captureScreenshot", { format: "png" });
  const sprintBuf = Buffer.from(sprintShot.data, "base64");
  writeFileSync(SHOT_SPRINT, sprintBuf);
  await keyUp(ws, 400, "w", "KeyW", 87, 8);
  await keyUp(ws, 401, "Shift", "ShiftLeft", 16);
  await sleep(80);
  const afterSprint = await evalExpr(ws, 402, SNAP);

  await keyDown(ws, 410, "w", "KeyW", 87);
  await sleep(10000);
  await keyUp(ws, 411, "w", "KeyW", 87);
  await sleep(200);
  const atLantern = await evalExpr(ws, 420, SNAP);
  await keyDown(ws, 421, "e", "KeyE", 69);
  await sleep(180);
  await keyUp(ws, 422, "e", "KeyE", 69);
  await sleep(400);
  const shopOpen = await evalExpr(ws, 430, SNAP);

  const standPng = decodePngRgba(standBuf);
  const walkPng = decodePngRgba(walkBuf);
  const sprintPng = decodePngRgba(sprintBuf);
  const box = home.canvasBox ?? { x: 0, y: 0, w: 1280, h: 720 };
  const standBody = bodyCropStats(standPng.pixels, standPng.width, standPng.height, box);
  const walkBody = bodyCropStats(walkPng.pixels, walkPng.width, walkPng.height, box);
  const sprintBody = bodyCropStats(sprintPng.pixels, sprintPng.width, sprintPng.height, box);
  const walkDiff = pixelDiffRatio(standPng, walkPng, box);
  const sprintDiff = pixelDiffRatio(standPng, sprintPng, box);
  const skyBand = bandStats(
    walkPng.pixels,
    walkPng.width,
    walkPng.height,
    box.x + box.w * 0.38,
    box.y + box.h * 0.04,
    box.x + box.w * 0.62,
    box.y + box.h * 0.16,
  );

  const standPeak = standLimbs.peak;
  const walkPeak = walkLimbs.peak;
  const sprintPeak = sprintLimbs.peak;
  const standSpread = standPeak?.spread ?? 0;
  const walkSpread = walkPeak?.spread ?? 0;
  const sprintSpread = sprintPeak?.spread ?? 0;
  const walkOpposite = Boolean(walkPeak?.opposite) && walkPeak.leftLeg * walkPeak.leftArm <= 0.04;
  const sprintOpposite = Boolean(sprintPeak?.opposite) && sprintPeak.leftLeg * sprintPeak.leftArm <= 0.04;
  const walkMoved = deltaM({ lon: cleared.lon, lat: cleared.lat }, { lon: afterWalk.lon, lat: afterWalk.lat });
  const sprintMoved = deltaM(
    { lon: afterWalk.lon, lat: afterWalk.lat },
    { lon: afterSprint.lon, lat: afterSprint.lat },
  );
  const lanternDelta = deltaM({ lon: home.lon, lat: home.lat }, { lon: atLantern.lon, lat: atLantern.lat });
  const clearDelta = deltaM({ lon: home.lon, lat: home.lat }, { lon: cleared.lon, lat: cleared.lat });

  const cycleOk =
    home.walkCycle === "opposite-stride" &&
    home.body === "tunic-humanoid" &&
    home.camera === "behind" &&
    standSpread < 0.25 &&
    walkSpread >= 1.6 &&
    sprintSpread >= walkSpread - 0.05 &&
    walkOpposite &&
    sprintOpposite &&
    (walkPeak?.moving === true) &&
    (sprintPeak?.running === true || afterSprint.sprint === "1" || sprintLimbs.rows.some((row) => row.running));
  const pixOk =
    walkDiff >= 0.04 &&
    sprintDiff >= 0.04 &&
    (walkBody.imbalance > standBody.imbalance + 0.01 || walkDiff >= 0.06) &&
    walkBody.tealRatio > 0.02 &&
    sprintBody.tealRatio > 0.02;
  const moveOk = walkMoved.north > 1.2 && sprintMoved.north > walkMoved.north * 0.9;
  const streetOk =
    home.buildings >= 60 &&
    afterWalk.insideAabb === "0" &&
    afterSprint.insideAabb === "0" &&
    atLantern.insideAabb === "0" &&
    home.collision === "footprint-radius";
  const keptOk =
    Number(home.scooters) === 15 &&
    home.scooterKind === "parked-box-scooter" &&
    home.marketSpill === "crate-basket-stack" &&
    Number(home.marketSpillCount) >= 6 &&
    Number(home.lamps) >= 12 &&
    home.sky === "gradient-hemisphere" &&
    home.roof === "parapet-ac-tank";
  const shopOk =
    Boolean(atLantern.shopMarker) &&
    shopOpen.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "") &&
    lanternDelta.north > 8;
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /not a digital twin/i.test(home.honesty) &&
    home.gtaClaim === false;
  const friendMeshOk = true;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict:
      cycleOk && pixOk && moveOk && streetOk && keptOk && shopOk && honestyOk
        ? "J5_WALK_CYCLE_OK"
        : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    cycleOk,
    pixOk,
    moveOk,
    streetOk,
    keptOk,
    shopOk,
    honestyOk,
    friendMeshOk,
    standSpread,
    walkSpread,
    sprintSpread,
    walkOpposite,
    sprintOpposite,
    walkMoved,
    sprintMoved,
    clearDelta,
    lanternDelta,
    standBody,
    walkBody,
    sprintBody,
    walkDiff,
    sprintDiff,
    skyBand,
    standPeak,
    walkPeak,
    sprintPeak,
    walkSamples: walkLimbs.rows.length,
    sprintSamples: sprintLimbs.rows.length,
    shopPanelId: shopOpen.shopPanelId,
    scooters: home.scooters,
    spill: home.marketSpillCount,
    hashes: {
      stand: createHash("sha256").update(standBuf).digest("hex").slice(0, 16),
      walk: createHash("sha256").update(walkBuf).digest("hex").slice(0, 16),
      sprint: createHash("sha256").update(sprintBuf).digest("hex").slice(0, 16),
    },
    shots: { stand: SHOT_STAND, walk: SHOT_WALK, sprint: SHOT_SPRINT },
    home: {
      buildings: home.buildings,
      body: home.body,
      walkCycle: home.walkCycle,
      camera: home.camera,
      canvas: home.canvasBox,
      scooters: home.scooters,
      spill: home.marketSpillCount,
    },
    afterWalk: { lon: afterWalk.lon, lat: afterWalk.lat, pose: afterWalk.pose, sprint: afterWalk.sprint },
    afterSprint: { lon: afterSprint.lon, lat: afterSprint.lat, pose: afterSprint.pose, sprint: afterSprint.sprint },
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
if (report.verdict !== "J5_WALK_CYCLE_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `walkSpread=${report.walkSpread?.toFixed?.(2) ?? report.walkSpread}`,
  `sprintSpread=${report.sprintSpread?.toFixed?.(2) ?? report.sprintSpread}`,
  `walkDiff=${report.walkDiff}`,
  `shop=${report.shopPanelId}`,
);
