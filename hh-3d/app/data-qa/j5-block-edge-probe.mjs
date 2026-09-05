/**
 * Authored 400 m fixture edge on recycled 4175.
 * Walk toward a bound; fog or edge mesh in shot; no void fall.
 * Lantern E still shop-lantern-fish. data-footsteps=1 while W.
 * Seat B leftover E not stolen. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
 */
import { inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-BLOCK-EDGE-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-block-edge.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9531), b: 9532 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-05";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const AOI = {
  west: 106.6961711,
  south: 10.7707034,
  east: 106.6998289,
  north: 10.7742966,
};
const M_PER_DEG_LAT = 111320;
const WALL_HEX = "#7a7268";
const LOT_HEX = "#3d7a88";
const COPE_HEX = "#c4b8a4";
const FOG_HEX = "#8ec4e8";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

function hexRgb(hex) {
  return {
    r: Number.parseInt(hex.slice(1, 3), 16),
    g: Number.parseInt(hex.slice(3, 5), 16),
    b: Number.parseInt(hex.slice(5, 7), 16),
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

async function keyHold(ws, id, key, code, vk, ms) {
  await keyDown(ws, id, key, code, vk);
  await sleep(ms);
  await keyUp(ws, id + 1, key, code, vk);
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
  const wall = hexRgb(WALL_HEX);
  const lot = hexRgb(LOT_HEX);
  const fog = hexRgb(FOG_HEX);
  const step = 3;
  let n = 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let beige = 0;
  let blueish = 0;
  let wallN = 0;
  let lotN = 0;
  let fogN = 0;
  let black = 0;
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
      const lum = (r + g + b) / 3;
      if (lum < 16) black += 1;
      if (r > 170 && g > 140 && b < 180 && r - b > 20) beige += 1;
      if (b > r + 8 && b > 90) blueish += 1;
      if (Math.hypot(r - wall.r, g - wall.g, b - wall.b) < 38) wallN += 1;
      if (Math.hypot(r - lot.r, g - lot.g, b - lot.b) < 42) lotN += 1;
      if (Math.hypot(r - hexRgb(COPE_HEX).r, g - hexRgb(COPE_HEX).g, b - hexRgb(COPE_HEX).b) < 36) wallN += 1;
      if (Math.hypot(r - fog.r, g - fog.g, b - fog.b) < 42) fogN += 1;
    }
  }
  return {
    samples: n,
    meanR: Number((sumR / Math.max(1, n)).toFixed(1)),
    meanG: Number((sumG / Math.max(1, n)).toFixed(1)),
    meanB: Number((sumB / Math.max(1, n)).toFixed(1)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
    wallRatio: Number((wallN / Math.max(1, n)).toFixed(3)),
    lotRatio: Number((lotN / Math.max(1, n)).toFixed(3)),
    fogRatio: Number((fogN / Math.max(1, n)).toFixed(3)),
    blackRatio: Number((black / Math.max(1, n)).toFixed(3)),
    bluerThanRed: sumB / Math.max(1, n) > sumR / Math.max(1, n) + 4,
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const steps = document.querySelector('[data-testid="footstep-proof"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const range = document.querySelector('[data-testid="shop-range"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const edge = document.querySelector('[data-testid="play-block-edge"]');
  const live = window.__hhFootsteps || null;
  const readFoot = (el) => ({
    footsteps: el?.getAttribute("data-footsteps") ?? "",
    kind: el?.getAttribute("data-footstep-kind") ?? "",
    ticks: el?.getAttribute("data-footstep-ticks") ?? "",
  });
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    sprint: avatar?.getAttribute("data-sprint") ?? proof?.getAttribute("data-sprint") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    alt: Number(avatar?.getAttribute("data-alt") ?? proof?.getAttribute("data-alt") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    atBound: avatar?.getAttribute("data-at-bound") ?? proof?.getAttribute("data-at-bound") ?? "",
    blocked: avatar?.getAttribute("data-blocked") ?? proof?.getAttribute("data-blocked") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    sky: proof?.getAttribute("data-sky") ?? "",
    fog: proof?.getAttribute("data-fog") ?? play?.getAttribute("data-fog") ?? "",
    fogNear: proof?.getAttribute("data-fog-near") ?? "",
    fogFar: proof?.getAttribute("data-fog-far") ?? "",
    blockEdge: proof?.getAttribute("data-block-edge") ?? play?.getAttribute("data-block-edge") ?? "",
    blockBound: proof?.getAttribute("data-block-bound") ?? "",
    walls: proof?.getAttribute("data-block-edge-walls") ?? edge?.getAttribute("data-walls") ?? "",
    lots: proof?.getAttribute("data-block-edge-lots") ?? edge?.getAttribute("data-lots") ?? "",
    walkCycle: proof?.getAttribute("data-walk-cycle") ?? "",
    collision: proof?.getAttribute("data-collision") ?? "",
    scooters: proof?.getAttribute("data-scooters") ?? "",
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    play: readFoot(play),
    proof: readFoot(proof),
    steps: readFoot(steps),
    live,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    honesty: honesty?.innerText ?? "",
    gtaClaim:
      /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
  };
})()`;

async function connectPage(port) {
  const deadline = Date.now() + 25000;
  let last = null;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
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
  throw new Error(`no CDP page on ${port}: ${JSON.stringify(last)}`);
}

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-edge-${port}-`));
  return spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--autoplay-policy=no-user-gesture-required",
      "--window-size=1280,720",
      url,
    ],
    { stdio: "ignore" },
  );
}

async function waitSnap(ws, startId, pred, tries = 28, delay = 250) {
  let last = null;
  let id = startId;
  for (let i = 0; i < tries; i += 1) {
    last = await evalExpr(ws, id, SNAP);
    id += 1;
    if (pred(last)) {
      return { snap: last, nextId: id };
    }
    await sleep(delay);
  }
  return { snap: last, nextId: id };
}

function footLive(snap) {
  const row = snap?.steps?.footsteps || snap?.play?.footsteps || snap?.live?.live;
  if (row === true || row === 1) return "1";
  if (row === false || row === 0) return "0";
  return String(row ?? "");
}

const chromes = [];
let report;
try {
  chromes.push(launchChrome(PORTS.a, `${PLAYER}?seat=a`));
  chromes.push(launchChrome(PORTS.b, `${PLAYER}?seat=b`));
  const a = await connectPage(PORTS.a);
  const b = await connectPage(PORTS.b);
  for (const [ws, base] of [
    [a.ws, 1],
    [b.ws, 1],
  ]) {
    await cdp(ws, base, "Runtime.enable");
    await cdp(ws, base + 1, "Page.enable");
    await cdp(ws, base + 2, "Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 720,
      deviceScaleFactor: 1,
      mobile: false,
    });
  }

  const readyA = await waitSnap(
    a.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    36,
    250,
  );
  const readyB = await waitSnap(
    b.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    36,
    250,
  );

  await evalExpr(
    a.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(120);
  await keyDown(a.ws, 82, "w", "KeyW", 87);
  const walking = await waitSnap(a.ws, 83, (s) => footLive(s) === "1" && s.pose === "walk", 24, 80);
  await keyHold(a.ws, 120, "w", "KeyW", 87, 18000);
  await sleep(200);
  const atLantern = await evalExpr(a.ws, 160, SNAP);
  await keyHold(a.ws, 161, "e", "KeyE", 69, 180);
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, 170, SNAP);
  await evalExpr(a.ws, 171, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(250);
  const shopClosed = await evalExpr(a.ws, 172, SNAP);

  await keyHold(a.ws, 180, "a", "KeyA", 65, 1700);
  await sleep(80);
  await keyDown(a.ws, 200, "Shift", "ShiftLeft", 16, 8);
  await keyDown(a.ws, 201, "w", "KeyW", 87, 8);
  const toward = await waitSnap(
    a.ws,
    202,
    (s) => s.atBound === "1",
    100,
    550,
  );
  const atEdge = toward.snap;
  const latAtHit = atEdge.lat;
  await sleep(2200);
  const extra = await evalExpr(a.ws, 300, SNAP);
  const edgeShot = await cdp(a.ws, 302, "Page.captureScreenshot", { format: "png" });
  const edgeBuf = Buffer.from(edgeShot.data, "base64");
  writeFileSync(SHOT, edgeBuf);
  await keyUp(a.ws, 303, "w", "KeyW", 87, 8);
  await keyUp(a.ws, 304, "Shift", "ShiftLeft", 16);

  const leftoverB =
    !LEFTOVER.test(readyB.snap.nearbyShop || "") &&
    !LEFTOVER.test(readyB.snap.stallHint || "") &&
    !LEFTOVER.test(readyB.snap.shopRange || "") &&
    readyB.snap.nearbyShop !== "shop-local-sharedpc" &&
    readyB.snap.nearbyShop !== "shop-local-mtl8ulddihjpre";
  await keyHold(b.ws, 80, "e", "KeyE", 69, 180);
  await sleep(250);
  const bAfterE = await evalExpr(b.ws, 90, SNAP);
  const leftoverEStolen = Boolean(bAfterE.shopPanel) && LEFTOVER.test(bAfterE.shopPanelId || "");

  const png = decodePngRgba(edgeBuf);
  const mid = bandStats(png.pixels, png.width, png.height, 200, 430, 1080, 700);
  const far = bandStats(png.pixels, png.width, png.height, 200, 260, 1080, 430);
  const sky = bandStats(png.pixels, png.width, png.height, 200, 40, 1080, 220);
  const southLimit = AOI.south + 2 / M_PER_DEG_LAT;
  const extraSouthM = (latAtHit - extra.lat) * M_PER_DEG_LAT;
  const insideAoi =
    extra.lon >= AOI.west &&
    extra.lon <= AOI.east &&
    extra.lat >= southLimit - 0.00002 &&
    extra.lat <= AOI.north;
  const walkOn = footLive(walking.snap) === "1" && walking.snap.pose === "walk";
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const shopClosedOk = shopClosed.shopPanel === false && extra.shopPanel === false;
  const leftoverOk = leftoverB && !leftoverEStolen && !bAfterE.shopPanel;
  const edgeDomOk =
    readyA.snap.fog === "distance-haze" &&
    readyA.snap.blockEdge === "curb-wall-lot" &&
    Number(readyA.snap.walls) === 4 &&
    Number(readyA.snap.lots) === 4 &&
    Number(readyA.snap.fogNear) === 58 &&
    Number(readyA.snap.fogFar) === 155;
  const atBoundOk = extra.atBound === "1" || extra.blocked === "1";
  const noVoid =
    extra.alt === 0 &&
    insideAoi &&
    extraSouthM < 0.35 &&
    mid.blackRatio < 0.08;
  const edgeVisible =
    mid.wallRatio > 0.015 ||
    mid.lotRatio > 0.015 ||
    far.fogRatio > 0.03 ||
    far.blueRatio > 0.28 ||
    (sky.blueRatio > 0.4 && mid.meanB > 80);
  const honestyOk =
    /Authored approximation/.test(readyA.snap.honesty) &&
    /not a digital twin/i.test(readyA.snap.honesty) &&
    /NOT_PLAN_PASS/.test(readyA.snap.honesty) &&
    /fixture edge, not a city/i.test(readyA.snap.honesty) &&
    readyA.snap.gtaClaim === false;
  const keptOk =
    readyA.snap.sky === "gradient-hemisphere" &&
    readyA.snap.collision === "footprint-radius" &&
    Number(readyA.snap.scooters) === 15 &&
    readyA.snap.walkCycle === "opposite-stride";

  const ok =
    walkOn &&
    lanternOk &&
    shopClosedOk &&
    leftoverOk &&
    edgeDomOk &&
    atBoundOk &&
    noVoid &&
    edgeVisible &&
    honestyOk &&
    keptOk;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_BLOCK_EDGE_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    walkOn,
    lanternOk,
    shopClosedOk,
    leftoverOk,
    edgeDomOk,
    atBoundOk,
    noVoid,
    edgeVisible,
    honestyOk,
    keptOk,
    extraSouthM: Number(extraSouthM.toFixed(3)),
    insideAoi,
    toward: { lat: toward.snap?.lat, atBound: toward.snap?.atBound },
    atEdge,
    extra,
    lantern: { nearby: atLantern.nearbyShop, panel: shopOpen.shopPanelId },
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      afterE: bAfterE.shopPanelId,
      panel: bAfterE.shopPanel,
    },
    mid,
    far,
    sky,
    honesty: readyA.snap.honesty?.slice(0, 220),
    shot: SHOT,
    hash: createHash("sha256").update(edgeBuf).digest("hex").slice(0, 16),
  };
  a.ws.close();
  b.ws.close();
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_REWORK",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
  };
} finally {
  for (const chrome of chromes) {
    chrome.kill();
  }
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_BLOCK_EDGE_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `walk=${report.walkOn}`,
  `bound=${report.atBoundOk}`,
  `void=${!report.noVoid}`,
  `edge=${report.edgeVisible}`,
  `lantern=${report.lantern?.panel}`,
  `leftoverB=${report.seatB?.nearbyShop || "none"}`,
);
