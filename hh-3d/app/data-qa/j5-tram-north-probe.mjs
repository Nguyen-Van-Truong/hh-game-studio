/**
 * Isolated guest B on already-up 4175. Empty profile, Offline.
 * Walk Harbor×Tram zebra then along Tram Approach ~40–80 m on the
 * north sidewalk (Tram is E–W; due-north from the zebra is Harbor).
 * Chip + minimap stay Tram Approach. Shot must show dark asphalt +
 * lighter walk edge + lamp or planter. Chè sidewalk E + leftover
 * banners still hold. Does not catalog_clear. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-TRAM-NORTH-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-tram-north.png");
const SHOT_LOOK = join(import.meta.dirname, "j5-3d-tram-north-lookdown.png");
const PORT = Number(process.env.HH_CDP_PORT_B || 9741);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-38";
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
const LEFTOVER_COPY = /không trên phố|leftover máy này/i;
const CHE_GOOD = /chè|che\s|đậu|dau/i;
const KEM_GOOD = /kem/i;
const PHO_GOOD = /phở|pho|bò|bo\b/i;
const LANTERN_GOODS = /cá|nục|túi|cói|mackerel|tote/i;

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

function nearestOn(points, x, z) {
  let best = null;
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    const vx = b[0] - a[0];
    const vz = b[1] - a[1];
    const seg = Math.hypot(vx, vz);
    if (seg < 0.2) continue;
    const t = Math.max(0, Math.min(1, ((x - a[0]) * vx + (z - a[1]) * vz) / (seg * seg)));
    const px = a[0] + vx * t;
    const pz = a[1] + vz * t;
    const dist = Math.hypot(x - px, z - pz);
    if (!best || dist < best.dist) best = { x: px, z: pz, dist, dx: vx / seg, dz: vz / seg };
  }
  return best;
}

function polyLen(points) {
  let n = 0;
  for (let i = 0; i < points.length - 1; i += 1) {
    n += Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]);
  }
  return n;
}

function atDist(points, dist) {
  let left = dist;
  for (let i = 0; i < points.length - 1; i += 1) {
    const dx = points[i + 1][0] - points[i][0];
    const dz = points[i + 1][1] - points[i][1];
    const seg = Math.hypot(dx, dz);
    if (seg < 0.2) continue;
    if (left <= seg) {
      return {
        x: points[i][0] + (dx / seg) * left,
        z: points[i][1] + (dz / seg) * left,
        dx: dx / seg,
        dz: dz / seg,
      };
    }
    left -= seg;
  }
  return null;
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
  let white = 0;
  let curb = 0;
  let dark = 0;
  let walk = 0;
  let green = 0;
  let lampMetal = 0;
  let yellow = 0;
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
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (lum > 145 && r > 150 && g > 145 && b > 120 && r - b < 55) white += 1;
      if (lum > 70 && lum < 160 && r > g - 8 && g > b && r - b > 8 && r - b < 55 && Math.abs(r - g) < 28) {
        curb += 1;
      }
      if (lum < 55 && Math.abs(r - g) < 18 && Math.abs(g - b) < 18) dark += 1;
      if (lum > 130 && r > 160 && g > 150 && b > 140 && r - b < 40 && Math.abs(r - g) < 25) walk += 1;
      if (g > r + 8 && g > b + 4 && g > 55 && g < 160 && r < 120) green += 1;
      if (lum < 80 && Math.abs(r - g) < 16 && Math.abs(g - b) < 16 && r < 70) lampMetal += 1;
      if (r > 180 && g > 150 && b < 130 && r - b > 50) yellow += 1;
    }
  }
  return {
    samples: n,
    whiteRatio: Number((white / Math.max(1, n)).toFixed(3)),
    curbRatio: Number((curb / Math.max(1, n)).toFixed(3)),
    darkRatio: Number((dark / Math.max(1, n)).toFixed(3)),
    walkRatio: Number((walk / Math.max(1, n)).toFixed(3)),
    greenRatio: Number((green / Math.max(1, n)).toFixed(3)),
    lampRatio: Number((lampMetal / Math.max(1, n)).toFixed(3)),
    yellowRatio: Number((yellow / Math.max(1, n)).toFixed(3)),
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
  const menu = document.querySelector('[data-testid="play-menu"]');
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const wrap = document.querySelector(".minimap-wrap");
  const names = document.querySelector('[data-testid="public-shop-names"]');
  const props = document.querySelector('[data-testid="play-street-props"]');
  const chipBox = chip ? chip.getBoundingClientRect() : null;
  const panelText = (panel?.innerText ?? "").replace(/\\s+/g, " ").trim();
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    name: (el.querySelector(".menu-shop-name")?.textContent ?? el.textContent ?? "").trim().split("\\n")[0],
    leftover: el.getAttribute("data-leftover") ?? "",
    street: el.getAttribute("data-street") ?? "",
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
  }));
  const lamps = [...document.querySelectorAll('[data-testid="play-street-props"] li[data-kind="lamp"]')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    street: el.getAttribute("data-street") ?? "",
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
  }));
  const planters = [...document.querySelectorAll('[data-testid="play-street-props"] li[data-kind="planter"]')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
  }));
  const boards = [...document.querySelectorAll('[data-testid="play-stall-boards"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    keepOut: el.getAttribute("data-keep-out") ?? "",
    titles: el.getAttribute("data-titles") ?? el.textContent ?? "",
  }));
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    name: el.getAttribute("data-name") ?? "",
    lon: Number(el.getAttribute("data-lon") ?? "NaN"),
    lat: Number(el.getAttribute("data-lat") ?? "NaN"),
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
  }));
  const leftovers = boards.filter((row) => /local-sharedpc|mtl8ulddihjpre|j6/i.test(row.shop));
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    blocked: proof?.getAttribute("data-blocked") ?? "",
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    insideRing: proof?.getAttribute("data-inside-ring") ?? "",
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
    banner: (banner?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    bannerPresent: Boolean(banner),
    kind: (kind?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    leftoverCopy: /không trên phố|leftover máy này/i.test(panelText),
    streetHud: play?.getAttribute("data-street-hud") ?? proof?.getAttribute("data-street-hud") ?? "",
    streetName:
      chip?.getAttribute("data-street-name") ??
      play?.getAttribute("data-street-name") ??
      proof?.getAttribute("data-street-name") ??
      "",
    chipText: (chip?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    chipOnScreen: Boolean(
      chipBox && chipBox.width > 8 && chipBox.height > 8 && chipBox.x > -8 && chipBox.x < 1288 && chipBox.y > -8 && chipBox.y < 728,
    ),
    menuOpen: menu?.getAttribute("data-open") === "yes" && menu?.hidden !== true,
    leftoverCount: Number(names?.getAttribute("data-leftover-count") ?? "0"),
    rows,
    lamps,
    planters,
    lampCount: Number(props?.getAttribute("data-lamps") ?? play?.getAttribute("data-lamps") ?? "0"),
    planterCount: Number(props?.getAttribute("data-planters") ?? play?.getAttribute("data-planters") ?? "0"),
    boards,
    stalls,
    leftovers,
    leftoverDrawn: leftovers.filter((row) => row.draw === "1").map((row) => row.shop),
    leftoverStallDrawn: stalls.filter((row) => ${JSON.stringify([...LEFTOVER_IDS])}.includes(row.shop) && row.draw === "1").map((row) => row.shop),
    cheBoard: boards.find((row) => row.shop === ${JSON.stringify(CHE)}) ?? null,
    kemBoard: boards.find((row) => row.shop === ${JSON.stringify(KEM)}) ?? null,
    phoBoard: boards.find((row) => row.shop === ${JSON.stringify(PHO)}) ?? null,
    lanternBoard: boards.find((row) => row.shop === ${JSON.stringify(LANTERN)}) ?? null,
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    presenceMode: (mode?.textContent ?? "").trim(),
    friendA: friendA?.getAttribute("data-relation") ?? "",
    honesty: honesty?.innerText ?? "",
    deniesGta: /no gta|not a digital twin|not 1:1/i.test(honesty?.innerText ?? ""),
    oidc: /sign in with google|oidc login/i.test(document.body.innerText),
    engine: play?.getAttribute("data-engine") ?? "",
    minimapDefer: wrap?.getAttribute("data-minimap-defer") ?? "",
    minimap: {
      present: Boolean(mini),
      kind: mini?.getAttribute("data-minimap-lanes") ?? "",
      official: Number(mini?.getAttribute("data-minimap-official") ?? "0"),
      inner: Number(mini?.getAttribute("data-minimap-inner") ?? "0"),
      extra: Number(mini?.getAttribute("data-minimap-extra") ?? "0"),
      names: mini?.getAttribute("data-minimap-names") ?? "",
      active: mini?.getAttribute("data-minimap-active") ?? "",
      highlight: mini?.getAttribute("data-minimap-highlight") ?? "",
      activeRole: mini?.getAttribute("data-minimap-active-role") ?? "",
    },
    gpsClaim: /\\bgps\\b/i.test(chip?.textContent ?? "") || /\\bgps\\b/i.test(chip?.getAttribute("data-street-name") ?? ""),
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-tram-north-${port}-`));
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
  if (east === 0 && north === 0) return 0;
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

async function walkToward(ws, nextId, target, withinM, chunks = 18) {
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
    const hold = d > 12 ? 1800 : d > 6 ? 1100 : d > 3 ? 700 : 380;
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
      chip: snap.chipText,
      mini: snap.minimap?.active,
      blocked: snap.blocked,
    });
    if (log.length >= 2 && Math.abs(log[log.length - 1].d - log[log.length - 2].d) < 0.25) {
      if (snap.chipText === "Steps East") {
        await keyHold(ws, nextId, "a", "KeyA", 65, 700);
        nextId += 2;
      } else if (snap.chipText === "Steps West") {
        await keyHold(ws, nextId, "d", "KeyD", 68, 700);
        nextId += 2;
      } else {
        await keyHold(ws, nextId, "a", "KeyA", 65, 380);
        nextId += 2;
      }
      await keyHold(ws, nextId, "w", "KeyW", 87, 900);
      nextId += 2;
      snap = await evalExpr(ws, nextId, SNAP);
      nextId += 1;
    }
  }
  return { snap, nextId, log, reached: distLL(snap, target) <= withinM + 1.2 };
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
  return waitSnap(ws, nextId, (s) => s.shopPanel === true, 10, 140);
}

async function ensureMenu(ws, nextId) {
  const now = await evalExpr(ws, nextId, SNAP);
  nextId += 1;
  if (now.menuOpen) {
    return { snap: now, nextId };
  }
  await blur(ws, nextId);
  nextId += 1;
  await sleep(80);
  await keyHold(ws, nextId, "Tab", "Tab", 9, 80);
  nextId += 2;
  return waitSnap(ws, nextId, (s) => s.menuOpen === true, 24, 200);
}

async function openMenuShop(ws, nextId, shopId) {
  const menu = await ensureMenu(ws, nextId);
  nextId = menu.nextId;
  const clicked = await evalExpr(
    ws,
    nextId,
    `(() => {
      const btn = document.querySelector('[data-testid="open-shop-${shopId}"]');
      if (!btn) return { ok: false };
      btn.click();
      return { ok: true };
    })()`,
  );
  nextId += 1;
  if (!clicked?.ok) {
    throw new Error(`missing open-shop-${shopId}`);
  }
  const opened = await waitSnap(
    ws,
    nextId,
    (s) => s.shopPanel === true && s.shopPanelId === shopId,
    28,
    180,
  );
  return { snap: opened.snap, nextId: opened.nextId, list: menu.snap };
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

function leftoverPanelOk(snap, shopId) {
  return (
    snap.shopPanelId === shopId &&
    snap.shopLeftover === "1" &&
    snap.shopStreet === "0" &&
    snap.shopKeepOut === "1" &&
    snap.bannerPresent === true &&
    LEFTOVER_COPY.test(snap.banner || "") &&
    snap.leftoverCopy === true
  );
}

const chrome = launchChrome(PORT);
let report;
try {
  const busBefore = await busGet();
  const leftoverGraph = busBefore?.graph?.pairs ?? [];
  const geo = await fetch(new URL("data/ben-thanh-400m.authored.geojson", PLAYER)).then((res) => res.json());
  const geoStreets = (geo.features ?? []).filter((row) => row.properties?.kind === "street");
  const tramFeat = (geo.features ?? []).find((row) => row.properties?.id === "street-tram-approach");
  const harborFeat = (geo.features ?? []).find((row) => row.properties?.id === "street-harbor-walk");
  const tram = (tramFeat?.geometry?.coordinates ?? []).map(([lon, lat]) => {
    const p = toWorld(lon, lat);
    return [p.x, p.z];
  });
  const harbor = (harborFeat?.geometry?.coordinates ?? []).map(([lon, lat]) => {
    const p = toWorld(lon, lat);
    return [p.x, p.z];
  });
  const tramLen = polyLen(tram);
  const harborLen = polyLen(harbor);
  let join = null;
  for (let d = 0; d <= harborLen + 0.01; d += 3) {
    const at = atDist(harbor, d);
    if (!at) continue;
    const near = nearestOn(tram, at.x, at.z);
    if (near && (!join || near.dist < join.dist)) join = { ...near, hx: at.x, hz: at.z };
  }
  const east = join.dx >= 0 ? 1 : -1;
  const zebra = {
    x: join.x + join.dx * east * 5.55,
    z: join.z + join.dz * east * 5.55,
  };
  const zebraLL = toLngLat(zebra.x, zebra.z);
  const planterAt = atDist(tram, 0.64 * tramLen);
  const rot = Math.atan2(planterAt.dx, planterAt.dz);
  const planter = {
    x: planterAt.x + Math.cos(rot) * -1 * 7.4,
    z: planterAt.z - Math.sin(rot) * -1 * 7.4,
  };
  const stand = toLngLat(planter.x, planterAt.z + 1.6);
  const planterLL = toLngLat(planter.x, planter.z);

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
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.chipText,
    48,
    250,
  );
  const spawn = ready.snap;
  let nextId = ready.nextId;

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

  const leftoverInherited =
    spawn.friendA === "accepted" ||
    leftoverGraph.some((row) => row.left === "a" && row.right === "b" && row.status === "accepted");
  if (leftoverInherited || spawn.friendA === "accepted" || spawn.friendA === "incoming") {
    await busUnfriendAB();
  }
  const notFriends = await waitSnap(
    ws,
    nextId,
    (s) => s.friendA === "none" || s.friendA === "" || s.friendA === "stranger",
    16,
    250,
  );
  nextId = notFriends.nextId;

  await blur(ws, nextId);
  nextId += 1;
  await keyHold(ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  await sleep(220);
  const spawnE = await evalExpr(ws, nextId, SNAP);
  nextId += 1;
  const spawnEStolen = Boolean(spawnE.shopPanel) && LEFTOVER.test(spawnE.shopPanelId || "");
  if (spawnE.shopPanel) {
    nextId = await closeShop(ws, nextId);
  }

  const sharedOpen = await openMenuShop(ws, nextId, SHARED);
  nextId = sharedOpen.nextId;
  const sharedPanel = sharedOpen.snap;
  nextId = await closeShop(ws, nextId);
  const j6Open = await openMenuShop(ws, nextId, J6);
  nextId = j6Open.nextId;
  const j6Panel = j6Open.snap;
  const leftoverRows = (sharedOpen.list.rows || []).filter(
    (row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop) || LEFTOVER.test(row.name),
  );
  const leftoverLast =
    leftoverRows.length === 0 ||
    (sharedOpen.list.rows || []).slice((sharedOpen.list.rows || []).length - leftoverRows.length).every((row) => row.leftover === "1");
  nextId = await closeShop(ws, nextId);
  const menuNow = await evalExpr(ws, nextId, SNAP);
  nextId += 1;
  if (menuNow.menuOpen) {
    await keyHold(ws, nextId, "Escape", "Escape", 27, 80);
    nextId += 2;
    await sleep(120);
  }

  await blur(ws, nextId);
  nextId += 1;
  const harborNorth = { lon: 106.69802, lat: 10.77242 };
  const toHarbor = await walkToward(ws, nextId, harborNorth, 2.6, 22);
  nextId = toHarbor.nextId;
  const toZebra = await walkToward(ws, nextId, zebraLL, 2.2, 12);
  nextId = toZebra.nextId;
  const atZebra = toZebra.snap;

  const toStand = await walkToward(ws, nextId, stand, 1.8, 16);
  nextId = toStand.nextId;
  const facePlant = await turnToHeading(ws, nextId, metersHeadingTo(toStand.snap, planterLL));
  nextId = facePlant.nextId;
  let atNorth = await waitSnap(
    ws,
    nextId,
    (s) =>
      (s.chipText === "Tram Approach" || s.streetName === "Tram Approach") &&
      (s.minimap?.present === true || s.minimapDefer === "live"),
    16,
    220,
  );
  nextId = atNorth.nextId;
  if (atNorth.snap.chipText !== "Tram Approach" && atNorth.snap.streetName !== "Tram Approach") {
    const retry = await walkToward(ws, nextId, stand, 1.4, 8);
    nextId = retry.nextId;
    atNorth = await waitSnap(
      ws,
      nextId,
      (s) => s.chipText === "Tram Approach" || s.streetName === "Tram Approach",
      10,
      200,
    );
    nextId = atNorth.nextId;
  }

  const northWorld = toWorld(atNorth.snap.lon, atNorth.snap.lat);
  const tramHit = nearestOn(tram, northWorld.x, northWorld.z);
  const zebraDist = Math.hypot(northWorld.x - zebra.x, northWorld.z - zebra.z);
  const tramLamps = (atNorth.snap.lamps || []).filter((row) => row.street === "street-tram-approach");
  const northLamps = tramLamps.filter((row) => {
    const d = Math.hypot(row.x - zebra.x, row.z - zebra.z);
    return d >= 20 && d <= 90 && row.z > zebra.z - 1;
  });
  const northPlanters = (atNorth.snap.planters || []).filter((row) => {
    const d = Math.hypot(row.x - zebra.x, row.z - zebra.z);
    return d >= 20 && d <= 90 && row.z > zebra.z - 1;
  });

  const northShot = await cdp(ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  const northBuf = Buffer.from(northShot.data, "base64");
  writeFileSync(SHOT, northBuf);
  const northPng = decodePngRgba(northBuf);
  const northFloor = bandStats(northPng.pixels, northPng.width, northPng.height, 220, 340, 1060, 700);
  const northMid = bandStats(northPng.pixels, northPng.width, northPng.height, 300, 220, 980, 560);

  await keyHold(ws, nextId, "s", "KeyS", 83, 900);
  nextId += 2;
  await sleep(140);
  const lookSnap = await evalExpr(ws, nextId, SNAP);
  nextId += 1;
  const lookShot = await cdp(ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  const lookBuf = Buffer.from(lookShot.data, "base64");
  writeFileSync(SHOT_LOOK, lookBuf);
  const lookPng = decodePngRgba(lookBuf);
  const lookFloor = bandStats(lookPng.pixels, lookPng.width, lookPng.height, 220, 340, 1060, 700);
  const lookMid = bandStats(lookPng.pixels, lookPng.width, lookPng.height, 300, 220, 980, 580);

  const cheStall = (atNorth.snap.stalls || []).find((row) => row.shop === CHE);
  const chePlant = cheStall ? toLngLat(cheStall.x, cheStall.z) : { lon: 106.6981047, lat: 10.7719818 };
  const cheSidewalk = {
    lon: chePlant.lon - 2.05 / metersPerDegLon(chePlant.lat),
    lat: chePlant.lat - 1.35 / M_PER_DEG_LAT,
  };
  const backHarbor = { lon: 106.69802, lat: 10.77236 };
  const toBack = await walkToward(ws, nextId, backHarbor, 2.8, 18);
  nextId = toBack.nextId;
  const toChe = await walkToward(ws, nextId, cheSidewalk, 1.4, 22);
  nextId = toChe.nextId;
  const faceChe = await turnToHeading(ws, nextId, metersHeadingTo(toChe.snap, chePlant));
  nextId = faceChe.nextId;
  let atChe = await waitSnap(ws, nextId, (s) => s.nearbyShop === CHE, 14, 200);
  nextId = atChe.nextId;
  if (atChe.snap.nearbyShop !== CHE) {
    const hop = await walkToward(ws, nextId, { lon: 106.6980928, lat: 10.7719689 }, 1.1, 10);
    nextId = hop.nextId;
    const faced = await turnToHeading(ws, nextId, metersHeadingTo(hop.snap, chePlant));
    nextId = faced.nextId;
    atChe = await waitSnap(ws, nextId, (s) => s.nearbyShop === CHE, 10, 180);
    nextId = atChe.nextId;
  }
  const eChe = await pressE(ws, nextId);
  nextId = eChe.nextId;
  const cheOpen = eChe.snap;
  if (cheOpen.shopPanel) {
    nextId = await closeShop(ws, nextId);
  }

  const guestOk =
    spawn.identitySigned === "no" &&
    /guest/i.test(spawn.identity || "") &&
    !/online —/i.test(notFriends.snap.presenceMode || spawn.presenceMode || "");
  const chipOk =
    (atNorth.snap.chipText === "Tram Approach" || atNorth.snap.streetName === "Tram Approach") &&
    atNorth.snap.chipOnScreen &&
    atNorth.snap.chipText !== "Harbor Walk";
  const miniOk =
    (atNorth.snap.minimap?.present === true || atNorth.snap.minimapDefer === "live") &&
    atNorth.snap.minimap?.official === 2 &&
    atNorth.snap.minimap?.active === "Tram Approach" &&
    atNorth.snap.minimap?.highlight === "1" &&
    atNorth.snap.minimap?.activeRole === "official" &&
    atNorth.snap.chipText === atNorth.snap.minimap?.active;
  const alongOk = zebraDist >= 28 && zebraDist <= 90 && tramHit && tramHit.dist < 8.4;
  const furnitureDom =
    northLamps.length >= 1 ||
    northPlanters.length >= 1 ||
    (atNorth.snap.planters || []).some((row) => row.id === "planter-tram-east-s");
  const streetPix =
    (northFloor.darkRatio >= 0.06 || lookFloor.darkRatio >= 0.06 || northMid.darkRatio >= 0.05) &&
    (northFloor.walkRatio >= 0.03 ||
      lookFloor.walkRatio >= 0.03 ||
      northMid.walkRatio >= 0.03 ||
      northFloor.curbRatio >= 0.012 ||
      lookFloor.curbRatio >= 0.012);
  const furniturePix =
    northFloor.greenRatio >= 0.004 ||
    northMid.greenRatio >= 0.004 ||
    lookFloor.greenRatio >= 0.004 ||
    lookMid.greenRatio >= 0.004 ||
    northFloor.yellowRatio >= 0.004 ||
    lookFloor.yellowRatio >= 0.004;
  const leftoverOk =
    leftoverPanelOk(sharedPanel, SHARED) &&
    leftoverPanelOk(j6Panel, J6) &&
    leftoverLast &&
    leftoverRows.length >= 2 &&
    (atNorth.snap.leftoverDrawn || []).length === 0 &&
    (atNorth.snap.leftoverStallDrawn || []).length === 0 &&
    !spawnEStolen &&
    !spawnE.shopPanel;
  const cheOk = cheOpen.shopPanel === true && cheOpen.shopPanelId === CHE;
  const stallsOk =
    atNorth.snap.cheBoard?.draw === "1" &&
    atNorth.snap.lanternBoard?.draw === "1" &&
    LANTERN_GOODS.test(atNorth.snap.lanternBoard?.titles || "") &&
    PHO_GOOD.test(atNorth.snap.phoBoard?.titles || "") &&
    (atNorth.snap.kemBoard?.draw !== "1" || KEM_GOOD.test(atNorth.snap.kemBoard?.titles || ""));
  const geoOk =
    geoStreets.length === 2 &&
    geoStreets.map((row) => row.properties?.display_name ?? row.properties?.name).sort().join(",") ===
      "Harbor Walk,Tram Approach";
  const honestyOk =
    /two official named streets/.test(spawn.honesty || "") &&
    /not OSM/i.test(spawn.honesty || "") &&
    spawn.deniesGta &&
    atNorth.snap.gpsClaim === false &&
    !spawn.oidc;
  const ok =
    guestOk &&
    chipOk &&
    miniOk &&
    alongOk &&
    furnitureDom &&
    streetPix &&
    furniturePix &&
    leftoverOk &&
    cheOk &&
    stallsOk &&
    geoOk &&
    honestyOk;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_TRAM_NORTH_OK" : "J5_TRAM_NORTH_FAIL",
    reminted: false,
    liveJs,
    liveLen,
    liveSha,
    chip: atNorth.snap.chipText,
    streetName: atNorth.snap.streetName,
    mini: atNorth.snap.minimap,
    zebraDist: Number(zebraDist.toFixed(2)),
    tramLaneM: tramHit ? Number(tramHit.dist.toFixed(2)) : null,
    northLamps: northLamps.map((row) => row.id),
    northPlanters: northPlanters.map((row) => row.id),
    furnitureDom,
    streetPix,
    furniturePix,
    northFloor,
    northMid,
    lookFloor,
    lookMid,
    geoStreets: geoStreets.map((row) => row.properties?.display_name ?? row.properties?.name),
    cheE: cheOpen.shopPanelId || "none",
    leftoverBanners: {
      shared: leftoverPanelOk(sharedPanel, SHARED),
      j6: leftoverPanelOk(j6Panel, J6),
      leftoverLast,
      draw: atNorth.snap.leftoverDrawn,
      stallDraw: atNorth.snap.leftoverStallDrawn,
    },
    spawnE: spawnE.shopPanelId || "none",
    spawnEStolen,
    stalls: {
      che: atNorth.snap.cheBoard,
      kem: atNorth.snap.kemBoard,
      pho: atNorth.snap.phoBoard,
      lantern: atNorth.snap.lanternBoard,
    },
    zebra: { ...zebra, ...zebraLL },
    stand,
    atZebra: { lon: atZebra.lon, lat: atZebra.lat, chip: atZebra.chipText },
    atNorth: {
      lon: atNorth.snap.lon,
      lat: atNorth.snap.lat,
      chip: atNorth.snap.chipText,
      heading: atNorth.snap.heading,
    },
    harborWalk: toHarbor.log,
    zebraWalk: toZebra.log,
    standWalk: toStand.log,
    backWalk: toBack.log,
    cheWalk: toChe.log,
    cheNearby: atChe.snap.nearbyShop,
    guestOk,
    chipOk,
    miniOk,
    alongOk,
    leftoverOk,
    cheOk,
    stallsOk,
    geoOk,
    honestyOk,
    didNotCatalogClear: true,
    didNotRemint: true,
    shots: { north: SHOT, look: SHOT_LOOK },
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_TRAM_NORTH_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_TRAM_NORTH_OK",
      `js=${liveJs}`,
      `chip=${atNorth.snap.chipText}`,
      `mini=${atNorth.snap.minimap?.active}`,
      `dZebra=${zebraDist.toFixed(1)}`,
      `lamps=${northLamps.length}`,
      `planters=${northPlanters.length}`,
      `cheE=${cheOpen.shopPanelId}`,
      `leftoverDraw=${(atNorth.snap.leftoverDrawn || []).join(",") || "0"}`,
    ].join(" "),
  );
} catch (err) {
  if (!report) {
    report = {
      run_id: RUN_ID,
      verdict: "J5_TRAM_NORTH_FAIL",
      reminted: false,
      error: err instanceof Error ? err.message : String(err),
    };
    writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  }
  console.error(report?.verdict || "J5_TRAM_NORTH_FAIL", err instanceof Error ? err.message : err);
  process.exitCode = 1;
} finally {
  chrome.kill();
}
