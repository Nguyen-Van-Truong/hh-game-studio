/**
 * Isolated guest B on already-up 4175. Empty profile, no add-friend,
 * Offline. Walk to Quầy Chè Vỉa sidewalk kiosk. Crop must read the
 * published listing (Chè đậu) on the cheap chalkboard before E.
 * E opens shop-local-mtmrbdjffjdkg8. Kem board only if that stall
 * is drawn. Leftover Shared PC / J6 stay draw=0. Asphalt old-style
 * E none. Does not catalog_clear. Does not remint. NOT_PLAN_PASS.
 */
import { deflateSync, inflateSync } from "node:zlib";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-CHE-BOARD-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-che-board.png");
const SHOT_CROP = join(import.meta.dirname, "j5-3d-che-board-crop.png");
const SHOT_KEM = join(import.meta.dirname, "j5-3d-kem-board.png");
const SHOT_KEM_CROP = join(import.meta.dirname, "j5-3d-kem-board-crop.png");
const PORT = Number(process.env.HH_CDP_PORT_B || 9733);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-37";
const SPAWN = { lon: 106.69804, lat: 10.77162 };
const ORIGIN = { lon: 106.698, lat: 10.7725 };
const M_PER_DEG_LAT = 111320;
const CHE = "shop-local-mtmrbdjffjdkg8";
const KEM = "shop-local-mtmrq33hoq4phb";
const PHO = "shop-local-mtmh45qxehxhvb";
const LANTERN = "shop-lantern-fish";
const SHARED = "shop-local-sharedpc";
const J6 = "shop-local-mtl8ulddihjpre";
const LEFTOVER_IDS = new Set([SHARED, J6]);
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const CHE_GOOD = /chè|che\s|đậu|dau/i;
const KEM_GOOD = /kem/i;
const PHO_GOOD = /phở|pho|bò|bo\b/i;
const LANTERN_GOODS = /cá|nục|túi|cói|mackerel|tote/i;
const NAMED_SHOP_RANGE = /đèn lồng|phở|chè|quầy|kem/i;
const METERS_AWAY = /\d+(\.\d+)?\s*m away/i;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

function toWorld(lon, lat) {
  return {
    x: (lon - ORIGIN.lon) * metersPerDegLon(ORIGIN.lat),
    z: (lat - ORIGIN.lat) * M_PER_DEG_LAT,
  };
}

function toLngLat(x, z) {
  return {
    lon: ORIGIN.lon + x / metersPerDegLon(ORIGIN.lat),
    lat: ORIGIN.lat + z / M_PER_DEG_LAT,
  };
}

function distLL(a, b) {
  const midLat = (a.lat + b.lat) / 2;
  const east = (b.lon - a.lon) * metersPerDegLon(midLat);
  const north = (b.lat - a.lat) * M_PER_DEG_LAT;
  return Math.hypot(east, north);
}

function offsetLngLat(lon, lat, eastM, northM) {
  return {
    lon: lon + eastM / metersPerDegLon(lat),
    lat: lat + northM / M_PER_DEG_LAT,
  };
}

function nearestOn(points, x, z) {
  let best = null;
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    const vx = b[0] - a[0];
    const vz = b[1] - a[1];
    const seg = Math.hypot(vx, vz);
    if (seg < 0.2) {
      continue;
    }
    const t = Math.max(0, Math.min(1, ((x - a[0]) * vx + (z - a[1]) * vz) / (seg * seg)));
    const px = a[0] + vx * t;
    const pz = a[1] + vz * t;
    const dist = Math.hypot(x - px, z - pz);
    if (!best || dist < best.dist) {
      best = { x: px, z: pz, dist };
    }
  }
  return best;
}

function emptyRangeOk(text) {
  const copy = String(text ?? "").trim();
  return copy === "Walk to a stall." && !NAMED_SHOP_RANGE.test(copy) && !METERS_AWAY.test(copy);
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

function crc32(buf) {
  let c = ~0;
  for (let i = 0; i < buf.length; i += 1) {
    c ^= buf[i];
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
  }
  return ~c >>> 0;
}

function pngChunk(type, data) {
  const typeBuf = Buffer.from(type, "ascii");
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const body = Buffer.concat([typeBuf, data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([len, body, crc]);
}

function writePngRgba(path, width, height, pixels) {
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y += 1) {
    raw[y * (stride + 1)] = 0;
    pixels.copy(raw, y * (stride + 1) + 1, y * stride, y * stride + stride);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  writeFileSync(
    path,
    Buffer.concat([
      Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
      pngChunk("IHDR", ihdr),
      pngChunk("IDAT", deflateSync(raw)),
      pngChunk("IEND", Buffer.alloc(0)),
    ]),
  );
}

function cropPng(png, x0, y0, x1, y1) {
  const xa = Math.max(0, Math.floor(x0));
  const ya = Math.max(0, Math.floor(y0));
  const xb = Math.min(png.width, Math.ceil(x1));
  const yb = Math.min(png.height, Math.ceil(y1));
  const w = Math.max(1, xb - xa);
  const h = Math.max(1, yb - ya);
  const pixels = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y += 1) {
    const src = ((ya + y) * png.width + xa) * 4;
    png.pixels.copy(pixels, y * w * 4, src, src + w * 4);
  }
  return { width: w, height: h, pixels };
}

function boardStats(pixels, width, height) {
  const step = 2;
  let n = 0;
  let slate = 0;
  let chalk = 0;
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * 4;
      const r = pixels[i];
      const g = pixels[i + 1];
      const b = pixels[i + 2];
      n += 1;
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (lum < 85 && g >= r - 4 && g > 22 && r < 90 && b < 90 && g - r < 40) {
        slate += 1;
      }
      if (lum > 145 && r > 170 && g > 145 && b > 95 && r - b > 12 && r - g < 45) {
        chalk += 1;
      }
    }
  }
  return {
    samples: n,
    slateRatio: Number((slate / Math.max(1, n)).toFixed(3)),
    chalkRatio: Number((chalk / Math.max(1, n)).toFixed(3)),
  };
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
  const hint = document.querySelector('[data-testid="stall-hint"]');
  const range = document.querySelector('[data-testid="shop-range"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const banner = document.querySelector('[data-testid="shop-leftover-banner"]');
  const kind = document.querySelector('[data-testid="shop-panel-kind"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const identity = document.querySelector('[data-testid="demo-identity"]');
  const mode = document.querySelector('[data-testid="presence-mode"]');
  const friendA = document.querySelector('[data-testid="friend-row-a"]');
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const goods = [...document.querySelectorAll('[data-testid="shop-listings"] li')].map((el) => ({
    id: el.getAttribute("data-listing") ?? "",
    kind: el.getAttribute("data-kind") ?? "",
    status: el.getAttribute("data-status") ?? "",
    text: (el.textContent ?? "").trim(),
  }));
  const boards = [...document.querySelectorAll('[data-testid="play-stall-boards"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    source: el.getAttribute("data-source") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    keepOut: el.getAttribute("data-keep-out") ?? "",
    titles: el.getAttribute("data-titles") ?? el.textContent ?? "",
    count: Number(el.getAttribute("data-count") ?? "0"),
  }));
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    collide: el.getAttribute("data-collide") ?? "",
    name: el.getAttribute("data-name") ?? "",
    lon: Number(el.getAttribute("data-lon") ?? "NaN"),
    lat: Number(el.getAttribute("data-lat") ?? "NaN"),
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
    laneM: Number(el.getAttribute("data-lane-m") ?? "NaN"),
    street: el.getAttribute("data-street") ?? "",
  }));
  const liveBoards = [...document.querySelectorAll('[data-testid^="shop-menu-board-"]')].map((el) => {
    const box = el.getBoundingClientRect();
    return {
      shop: el.getAttribute("data-shop-id") ?? "",
      source: el.getAttribute("data-source") ?? "",
      titles: el.getAttribute("data-titles") ?? "",
      text: (el.textContent ?? "").trim(),
      honesty: el.getAttribute("data-honesty") ?? "",
      onScreen: box.width > 20 && box.height > 12 && box.x > -40 && box.x < 1320 && box.y > -40 && box.y < 760,
      box: { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) },
    };
  });
  const leftovers = boards.filter((row) => /local-sharedpc|mtl8ulddihjpre|j6/i.test(row.shop));
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    blocked: proof?.getAttribute("data-blocked") ?? "",
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    shopLeftover: panel?.getAttribute("data-leftover") ?? "",
    shopStreet: panel?.getAttribute("data-street") ?? "",
    shopKeepOut: panel?.getAttribute("data-keep-out") ?? "",
    bannerPresent: Boolean(banner),
    kind: (kind?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    goods,
    goodsText: goods.map((row) => row.text).join(" | "),
    stallBoardKind: play?.getAttribute("data-stall-board") ?? proof?.getAttribute("data-stall-board") ?? "",
    boards,
    stalls,
    leftovers,
    leftoverDrawn: leftovers.filter((row) => row.draw === "1").map((row) => row.shop),
    leftoverStallDrawn: stalls.filter((row) => ${JSON.stringify([...LEFTOVER_IDS])}.includes(row.shop) && row.draw === "1").map((row) => row.shop),
    liveBoards,
    cheLive: liveBoards.find((row) => row.shop === ${JSON.stringify(CHE)}) ?? null,
    kemLive: liveBoards.find((row) => row.shop === ${JSON.stringify(KEM)}) ?? null,
    phoLive: liveBoards.find((row) => row.shop === ${JSON.stringify(PHO)}) ?? null,
    lanternLive: liveBoards.find((row) => row.shop === ${JSON.stringify(LANTERN)}) ?? null,
    cheBoard: boards.find((row) => row.shop === ${JSON.stringify(CHE)}) ?? null,
    kemBoard: boards.find((row) => row.shop === ${JSON.stringify(KEM)}) ?? null,
    phoBoard: boards.find((row) => row.shop === ${JSON.stringify(PHO)}) ?? null,
    lanternBoard: boards.find((row) => row.shop === ${JSON.stringify(LANTERN)}) ?? null,
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    presenceMode: (mode?.textContent ?? "").trim(),
    friendA: friendA?.getAttribute("data-relation") ?? "",
    chip: (chip?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    honesty: honesty?.innerText ?? "",
    deniesGta: /no gta|not a digital twin|not 1:1/i.test(honesty?.innerText ?? ""),
    oidc: /sign in with google|oidc login/i.test(document.body.innerText),
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

function launchChrome(port) {
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-che-board-${port}-`));
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
      "about:blank",
    ],
    { stdio: "ignore" },
  );
}

async function waitSnap(ws, startId, pred, tries = 40, delay = 250) {
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

function wrapHeading(heading) {
  return ((Number(heading) % 360) + 360) % 360;
}

function metersHeadingTo(from, to) {
  const midLat = (from.lat + to.lat) / 2;
  const east = (to.lon - from.lon) * metersPerDegLon(midLat);
  const north = (to.lat - from.lat) * M_PER_DEG_LAT;
  if (east === 0 && north === 0) {
    return 0;
  }
  return wrapHeading((Math.atan2(east, north) * 180) / Math.PI);
}

function headingDelta(from, to) {
  return ((to - from + 540) % 360) - 180;
}

function facingToward(heading, target, slack = 18) {
  return Math.abs(headingDelta(wrapHeading(heading), wrapHeading(target))) <= slack;
}

async function blur(ws, id) {
  return evalExpr(
    ws,
    id,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
      if (canvas) {
        canvas.click();
        canvas.focus?.();
      } else {
        document.body.click();
      }
      return true;
    })()`,
  );
}

async function turnToHeading(ws, startId, targetHeading) {
  let id = startId;
  for (let i = 0; i < 10; i += 1) {
    const snap = await evalExpr(ws, id, SNAP);
    id += 1;
    if (facingToward(snap.heading, targetHeading)) {
      return { snap, nextId: id };
    }
    await blur(ws, id);
    id += 1;
    const delta = headingDelta(wrapHeading(snap.heading), wrapHeading(targetHeading));
    const holdMs = Math.min(1600, Math.max(220, Math.round((Math.abs(delta) / 110) * 1000) + 80));
    if (delta >= 0) {
      await keyHold(ws, id, "d", "KeyD", 68, holdMs);
    } else {
      await keyHold(ws, id, "a", "KeyA", 65, holdMs);
    }
    id += 2;
    await sleep(80);
  }
  const snap = await evalExpr(ws, id, SNAP);
  return { snap, nextId: id + 1 };
}

async function walkToward(ws, nextId, target, withinM, chunks = 16) {
  let snap = await evalExpr(ws, nextId, SNAP);
  nextId += 1;
  const log = [];
  for (let i = 0; i < chunks; i += 1) {
    const d = distLL(snap, target);
    if (d <= withinM) {
      return { snap, nextId, log, reached: true };
    }
    const bear = metersHeadingTo(snap, target);
    if (!facingToward(snap.heading, bear, 14)) {
      const turned = await turnToHeading(ws, nextId, bear);
      nextId = turned.nextId;
      snap = turned.snap;
    }
    const hold = d > 8 ? 1600 : d > 3 ? 900 : 420;
    await keyHold(ws, nextId, "w", "KeyW", 87, hold);
    nextId += 2;
    await sleep(70);
    snap = await evalExpr(ws, nextId, SNAP);
    nextId += 1;
    log.push({
      i,
      lon: snap.lon,
      lat: snap.lat,
      d: Number(distLL(snap, target).toFixed(2)),
      nearby: snap.nearbyShop,
      range: snap.shopRange,
      chip: snap.chip,
      blocked: snap.blocked,
    });
  }
  return { snap, nextId, log, reached: distLL(snap, target) <= withinM + 0.8 };
}

async function closeShop(ws, nextId) {
  const closed = await evalExpr(
    ws,
    nextId,
    `(() => {
      const btn = document.querySelector('[data-testid="close-shop"]');
      if (btn) btn.click();
      return Boolean(btn);
    })()`,
  );
  nextId += 1;
  if (!closed) {
    await keyHold(ws, nextId, "Escape", "Escape", 27, 80);
    nextId += 2;
  }
  const gone = await waitSnap(ws, nextId, (s) => s.shopPanel === false, 16, 160);
  return gone.nextId;
}

async function pressE(ws, nextId) {
  await blur(ws, nextId);
  nextId += 1;
  await keyHold(ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  const after = await waitSnap(ws, nextId, (s) => s.shopPanel === true, 10, 140);
  return after;
}

function usableBox(box) {
  if (box && box.w >= 70 && box.h >= 28) {
    return box;
  }
  return null;
}

function captureCrop(png, box, dest) {
  const pad = 16;
  const crop = cropPng(png, box.x - pad, box.y - pad, box.x + box.w + pad, box.y + box.h + pad);
  writePngRgba(dest, crop.width, crop.height, crop.pixels);
  return {
    crop,
    stats: boardStats(crop.pixels, crop.width, crop.height),
  };
}

async function busGet() {
  const res = await fetch(new URL("/demo-bus", PLAYER));
  return res.json();
}

async function busUnfriendAB() {
  await fetch(new URL("/demo-bus", PLAYER), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      v: 1,
      kind: "local-demo-bus",
      not_presence_server: true,
      not_plan_pass: true,
      graph_op: { op: "unfriend", from: "b", to: "a" },
    }),
  });
}

const chrome = launchChrome(PORT);
let report;
try {
  const busBefore = await busGet();
  const busShops = Array.isArray(busBefore?.catalog?.shops) ? busBefore.catalog.shops : [];
  const busListings = Array.isArray(busBefore?.catalog?.listings) ? busBefore.catalog.listings : [];
  const leftoverGraph = busBefore?.graph?.pairs ?? [];
  const cheListing = busListings.find((row) => row.shop_id === CHE);
  const kemListing = busListings.find((row) => row.shop_id === KEM);
  const geo = await fetch(new URL("data/ben-thanh-400m.authored.geojson", PLAYER)).then((res) => res.json());
  const harborFeat = (geo.features ?? []).find((row) => row.properties?.id === "street-harbor-walk");
  const harbor = (harborFeat?.geometry?.coordinates ?? []).map(([lon, lat]) => {
    const p = toWorld(lon, lat);
    return [p.x, p.z];
  });

  const { ws } = await connectPage(PORT);
  await cdp(ws, 1, "Runtime.enable");
  await cdp(ws, 2, "Page.enable");
  await cdp(ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(ws, 4, "Page.navigate", { url: `${PLAYER}?seat=b` });

  const ready = await waitSnap(
    ws,
    10,
    (s) =>
      s.playReady === "yes" &&
      s.canvas &&
      s.buildings >= 20 &&
      s.stallBoardKind === "chalkboard-menu" &&
      Boolean(s.cheBoard),
    48,
    250,
  );
  const spawn = ready.snap;
  const sawChe = await waitSnap(
    ws,
    ready.nextId,
    (s) => s.cheBoard?.draw === "1" && CHE_GOOD.test(s.cheBoard?.titles || ""),
    28,
    250,
  );

  const liveHtml = await fetch(PLAYER).then((res) => res.text());
  const jsMatch = liveHtml.match(/\/assets\/index-[^"]+\.js/);
  const liveJs = jsMatch ? jsMatch[0] : "";
  let liveLen = 0;
  let liveSha = "";
  if (liveJs) {
    const jsRes = await fetch(new URL(liveJs, PLAYER));
    const buf = Buffer.from(await jsRes.arrayBuffer());
    liveLen = buf.length;
    liveSha = createHash("sha256").update(buf).digest("hex");
  }

  let nextId = sawChe.nextId;
  const leftoverInherited =
    sawChe.snap.friendA === "accepted" ||
    leftoverGraph.some((row) => row.left === "a" && row.right === "b" && row.status === "accepted");
  let didUnfriendLeftover = false;
  if (leftoverInherited || sawChe.snap.friendA === "accepted" || sawChe.snap.friendA === "incoming") {
    await busUnfriendAB();
    didUnfriendLeftover = true;
  }
  const notFriends = await waitSnap(
    ws,
    nextId,
    (s) => s.friendA === "none" || s.friendA === "" || s.friendA === "stranger",
    16,
    250,
  );
  nextId = notFriends.nextId;

  const spawnEStolen = Boolean(spawn.nearbyShop && LEFTOVER_IDS.has(spawn.nearbyShop));
  const cheStall = (sawChe.snap.stalls || []).find((row) => row.shop === CHE);
  const kemStall = (sawChe.snap.stalls || []).find((row) => row.shop === KEM);
  const kemDrawn = kemStall?.draw === "1";
  const chePlant = cheStall ? toLngLat(cheStall.x, cheStall.z) : { lon: 106.6981047, lat: 10.7719818 };
  const kemPlant = kemStall ? toLngLat(kemStall.x, kemStall.z) : null;
  const chePersist = cheStall ? { lon: cheStall.lon, lat: cheStall.lat } : { lon: 106.6981047, lat: 10.7719753 };
  const chePersistWorld = toWorld(chePersist.lon, chePersist.lat);
  const asphaltHit = nearestOn(harbor, chePersistWorld.x, chePersistWorld.z);
  const asphalt = asphaltHit ? toLngLat(asphaltHit.x, asphaltHit.z) : { lon: 106.698044, lat: 10.771968 };
  // Harbor-side of the kiosk (~2 m west of plant). Plant-hug sits on
  // Steps East (laneM ≲ 3) and Nearby/E go empty by design.
  const cheSidewalk = offsetLngLat(chePlant.lon, chePlant.lat, -2.05, -1.35);

  await blur(ws, nextId);
  nextId += 1;

  const toChe = await walkToward(ws, nextId, cheSidewalk, 1.3, 18);
  nextId = toChe.nextId;
  const faceChe = await turnToHeading(ws, nextId, metersHeadingTo(toChe.snap, chePlant));
  nextId = faceChe.nextId;
  let atCheWait = await waitSnap(
    ws,
    nextId,
    (s) =>
      s.nearbyShop === CHE &&
      Boolean(s.cheLive?.text || s.cheBoard?.titles) &&
      (s.cheLive?.onScreen === true || CHE_GOOD.test(s.cheBoard?.titles || "")),
    16,
    220,
  );
  nextId = atCheWait.nextId;
  let atChe = atCheWait.snap;
  if (atChe.nearbyShop !== CHE) {
    const retry = await walkToward(ws, nextId, { lon: 106.6980928, lat: 10.7719689 }, 1.1, 8);
    nextId = retry.nextId;
    const faceRetry = await turnToHeading(ws, nextId, metersHeadingTo(retry.snap, chePlant));
    nextId = faceRetry.nextId;
    atCheWait = await waitSnap(ws, nextId, (s) => s.nearbyShop === CHE, 12, 200);
    nextId = atCheWait.nextId;
    atChe = atCheWait.snap;
  }

  if (atChe.nearbyShop !== CHE) {
    const westTries = [
      offsetLngLat(chePlant.lon, chePlant.lat, -2.6, -0.6),
      offsetLngLat(chePlant.lon, chePlant.lat, -1.7, -1.8),
      { lon: 106.6980928, lat: 10.7719689 },
    ];
    for (const dest of westTries) {
      const hop = await walkToward(ws, nextId, dest, 1.0, 6);
      nextId = hop.nextId;
      const faced = await turnToHeading(ws, nextId, metersHeadingTo(hop.snap, chePlant));
      nextId = faced.nextId;
      const hunt = await waitSnap(ws, nextId, (s) => s.nearbyShop === CHE, 8, 160);
      nextId = hunt.nextId;
      atChe = hunt.snap;
      if (atChe.nearbyShop === CHE) {
        break;
      }
    }
  }

  const cheBox = usableBox(atChe.cheLive?.box) || { x: 520, y: 240, w: 260, h: 110 };
  const shot = await cdp(ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  const buf = Buffer.from(shot.data, "base64");
  writeFileSync(SHOT, buf);
  const png = decodePngRgba(buf);
  const cheCrop = captureCrop(png, cheBox, SHOT_CROP);
  const cheCropText = `${atChe.cheLive?.text || ""} ${atChe.cheLive?.titles || ""} ${atChe.cheBoard?.titles || ""}`.trim();

  const readyE = await waitSnap(ws, nextId, (s) => s.nearbyShop === CHE, 10, 180);
  nextId = readyE.nextId;
  atChe = { ...atChe, ...readyE.snap, cheLive: readyE.snap.cheLive || atChe.cheLive };
  const eChe = await pressE(ws, nextId);
  nextId = eChe.nextId;
  const cheOpen = eChe.snap;
  if (cheOpen.shopPanel) {
    nextId = await closeShop(ws, nextId);
  }

  let atKem = null;
  let kemCropText = "";
  let kemStats = null;
  let kemBox = null;
  if (kemDrawn && kemPlant) {
    const toKem = await walkToward(ws, nextId, kemPlant, 2.2, 14);
    nextId = toKem.nextId;
    const faceKem = await turnToHeading(ws, nextId, metersHeadingTo(toKem.snap, kemPlant));
    nextId = faceKem.nextId;
    const kemWait = await waitSnap(
      ws,
      nextId,
      (s) => s.kemBoard?.draw === "1" && (s.kemLive?.onScreen === true || KEM_GOOD.test(s.kemBoard?.titles || "")),
      16,
      200,
    );
    nextId = kemWait.nextId;
    atKem = kemWait.snap;
    kemBox = usableBox(atKem.kemLive?.box);
    const kemShot = await cdp(ws, nextId, "Page.captureScreenshot", { format: "png" });
    nextId += 1;
    const kemBuf = Buffer.from(kemShot.data, "base64");
    writeFileSync(SHOT_KEM, kemBuf);
    if (kemBox) {
      const kemPng = decodePngRgba(kemBuf);
      const cropped = captureCrop(kemPng, kemBox, SHOT_KEM_CROP);
      kemStats = cropped.stats;
    }
    kemCropText = `${atKem.kemLive?.text || ""} ${atKem.kemLive?.titles || ""} ${atKem.kemBoard?.titles || ""}`.trim();
  }

  const toAsphalt = await walkToward(ws, nextId, asphalt, 1.4, 14);
  nextId = toAsphalt.nextId;
  const atAsphalt = toAsphalt.snap;
  const eAsphalt = await pressE(ws, nextId);
  nextId = eAsphalt.nextId;
  const asphaltOpened = eAsphalt.snap.shopPanel ? eAsphalt.snap.shopPanelId : "";
  if (eAsphalt.snap.shopPanel) {
    nextId = await closeShop(ws, nextId);
  }

  const asphaltWorld = toWorld(atAsphalt.lon, atAsphalt.lat);
  const asphaltLane = nearestOn(harbor, asphaltWorld.x, asphaltWorld.z);

  const guestOk =
    spawn.identitySigned === "no" &&
    /guest/i.test(spawn.identity || "") &&
    !/online —/i.test(notFriends.snap.presenceMode || spawn.presenceMode || "") &&
    cheOpen.identitySigned === "no";
  const notFriendsOk =
    cheOpen.friendA !== "accepted" &&
    atChe.friendA !== "accepted" &&
    (notFriends.snap.friendA === "none" ||
      notFriends.snap.friendA === "" ||
      notFriends.snap.friendA === "stranger");
  const cheTitles = atChe.cheBoard?.titles || sawChe.snap.cheBoard?.titles || "";
  const boardOk =
    atChe.stallBoardKind === "chalkboard-menu" &&
    atChe.cheBoard?.draw === "1" &&
    CHE_GOOD.test(cheCropText) &&
    /mẫu/.test(cheCropText) &&
    CHE_GOOD.test(cheTitles) &&
    cheCrop.stats.slateRatio >= 0.08 &&
    cheCrop.stats.chalkRatio >= 0.01;
  const eOk =
    cheOpen.shopPanel === true &&
    cheOpen.shopPanelId === CHE &&
    CHE_GOOD.test(cheOpen.goodsText || cheListing?.title || "");
  const leftoverOk =
    (atChe.leftoverDrawn || []).length === 0 &&
    (atChe.leftoverStallDrawn || []).length === 0 &&
    !spawnEStolen &&
    (atChe.cheBoard?.keepOut === "0");
  const lanternOk = LANTERN_GOODS.test(atChe.lanternBoard?.titles || sawChe.snap.lanternBoard?.titles || "");
  const phoOk = PHO_GOOD.test(atChe.phoBoard?.titles || sawChe.snap.phoBoard?.titles || "");
  const kemSkipped = !kemDrawn;
  const kemOk =
    kemSkipped ||
    (atKem?.kemBoard?.draw === "1" && KEM_GOOD.test(kemCropText || atKem?.kemBoard?.titles || kemListing?.title || ""));
  const asphaltOk =
    !atAsphalt.nearbyShop &&
    emptyRangeOk(atAsphalt.shopRange) &&
    !asphaltOpened;
  const ok =
    guestOk &&
    notFriendsOk &&
    boardOk &&
    eOk &&
    leftoverOk &&
    lanternOk &&
    phoOk &&
    kemOk &&
    asphaltOk &&
    spawn.deniesGta &&
    !spawn.oidc;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_CHE_BOARD_OK" : "J5_CHE_BOARD_FAIL",
    reminted: false,
    liveJs,
    liveLen,
    liveSha,
    cheShop: CHE,
    kemShop: KEM,
    cheListing: cheListing?.title ?? null,
    kemListing: kemListing?.title ?? null,
    cropText: cheCropText,
    cropStats: cheCrop.stats,
    cropBox: cheBox,
    cropSize: { w: cheCrop.crop.width, h: cheCrop.crop.height },
    kemDrawn,
    kemSkipped,
    kemCropText,
    kemStats,
    kemBox,
    nearby: atChe.nearbyShop,
    shopOpen: cheOpen.shopPanelId,
    goods: cheOpen.goods,
    identity: cheOpen.identity || spawn.identity,
    identitySigned: cheOpen.identitySigned,
    presenceMode: notFriends.snap.presenceMode || spawn.presenceMode,
    friendASpawn: spawn.friendA,
    friendAWalk: atChe.friendA,
    friendAAfterE: cheOpen.friendA,
    leftoverInherited,
    didUnfriendLeftover,
    leftoverDrawn: atChe.leftoverDrawn,
    leftoverStallDrawn: atChe.leftoverStallDrawn,
    leftoverEStolen: spawnEStolen,
    cheBoard: atChe.cheBoard,
    kemBoard: (atKem || sawChe.snap).kemBoard,
    phoBoard: atChe.phoBoard,
    lanternBoard: atChe.lanternBoard,
    cheStand: {
      lon: atChe.lon,
      lat: atChe.lat,
      nearby: atChe.nearbyShop,
      range: atChe.shopRange,
      hint: atChe.stallHint,
      chip: atChe.chip,
      dPlant: Number(distLL(atChe, chePlant).toFixed(2)),
    },
    asphaltStand: {
      lon: atAsphalt.lon,
      lat: atAsphalt.lat,
      nearby: atAsphalt.nearbyShop || "",
      range: atAsphalt.shopRange,
      hint: atAsphalt.stallHint,
      laneM: asphaltLane ? Number(asphaltLane.dist.toFixed(2)) : null,
      e: asphaltOpened || "none",
    },
    cheWalk: toChe.log,
    guestOk,
    notFriendsOk,
    boardOk,
    eOk,
    leftoverOk,
    lanternOk,
    phoOk,
    kemOk,
    asphaltOk,
    didNotCatalogClear: true,
    didNotRemint: true,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_CHE_BOARD_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_CHE_BOARD_OK",
      `js=${liveJs}`,
      `crop=${cheCropText.replace(/\s+/g, " ").slice(0, 80)}`,
      `e=${cheOpen.shopPanelId}`,
      `kem=${kemSkipped ? "skip-not-drawn" : kemCropText.replace(/\s+/g, " ").slice(0, 40)}`,
      `asphaltE=${asphaltOpened || "none"}`,
    ].join(" "),
  );
} catch (err) {
  if (!report) {
    report = {
      run_id: RUN_ID,
      verdict: "J5_CHE_BOARD_FAIL",
      reminted: false,
      error: err instanceof Error ? err.message : String(err),
    };
    writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  }
  console.error(report?.verdict || "J5_CHE_BOARD_FAIL", err instanceof Error ? err.message : err);
  process.exitCode = 1;
} finally {
  chrome.kill();
}
