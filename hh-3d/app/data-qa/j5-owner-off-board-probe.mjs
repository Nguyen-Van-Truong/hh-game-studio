/**
 * Isolated A + B on already-up 4175. A is the labeled demo owner of
 * Quầy Phở Nhà, stays Offline, then leaves identity (not present).
 * B (empty profile, no friends, Offline) walks to the drawn kiosk.
 * Crop must still read Phở bò. E still opens shop-local-mtmh45qxehxhvb.
 * Does not remint / recycle / catalog_clear. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-OWNER-OFF-BOARD-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-owner-off-board.png");
const SHOT_CROP = join(import.meta.dirname, "j5-3d-owner-off-board-crop.png");
const PORTS = {
  a: Number(process.env.HH_CDP_PORT_A || 9631),
  b: Number(process.env.HH_CDP_PORT_B || 9632),
};
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-24";
const SPAWN = { lon: 106.69804, lat: 10.77162 };
const M_PER_DEG_LAT = 111320;
const M_PER_DEG_LON = M_PER_DEG_LAT * Math.cos((SPAWN.lat * Math.PI) / 180);
const PLAYER_SHOP = "shop-local-mtmh45qxehxhvb";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAYER_GOOD = /phở|pho|bò|bo\b/i;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function northM(lat) {
  return (Number(lat) - SPAWN.lat) * M_PER_DEG_LAT;
}

function eastM(lon) {
  return (Number(lon) - SPAWN.lon) * M_PER_DEG_LON;
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
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const identity = document.querySelector('[data-testid="demo-identity"]');
  const mode = document.querySelector('[data-testid="presence-mode"]');
  const offline = document.querySelector('[data-testid="offline-btn"]');
  const online = document.querySelector('[data-testid="online-btn"]');
  const people = document.querySelector('[data-testid="people-layer"]');
  const peopleRows = document.querySelector('[data-testid="people-rows"]');
  const remotes = document.querySelector('[data-testid="play-remote-bodies"]');
  const friendA = document.querySelector('[data-testid="friend-row-a"]');
  const friendB = document.querySelector('[data-testid="friend-row-b"]');
  const addA = document.querySelector('[data-testid="add-friend-a"]');
  const addB = document.querySelector('[data-testid="add-friend-b"]');
  const acceptA = document.querySelector('[data-testid="accept-friend-a"]');
  const acceptB = document.querySelector('[data-testid="accept-friend-b"]');
  const unfriendA = document.querySelector('[data-testid="unfriend-a"]');
  const unfriendB = document.querySelector('[data-testid="unfriend-b"]');
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
  const leftovers = boards.filter((row) => /local-sharedpc|mtl8ulddihjpre|j6/i.test(row.shop));
  const playerDrawn = boards.filter((row) => row.source === "local-demo" && row.draw === "1");
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
  return {
    title: document.title,
    href: location.href,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    goods,
    goodsText: goods.map((row) => row.text).join(" | "),
    stallBoardKind: play?.getAttribute("data-stall-board") ?? proof?.getAttribute("data-stall-board") ?? "",
    stallBoards: Number(play?.getAttribute("data-stall-boards") ?? proof?.getAttribute("data-stall-boards") ?? "0"),
    playerStallBoards: Number(
      play?.getAttribute("data-player-stall-boards") ?? proof?.getAttribute("data-player-stall-boards") ?? "0",
    ),
    boards,
    leftovers,
    leftoverDrawn: leftovers.filter((row) => row.draw === "1").map((row) => row.shop),
    playerDrawn,
    liveBoards,
    playerLive: liveBoards.find((row) => row.shop === ${JSON.stringify(PLAYER_SHOP)}) ?? null,
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    presenceMode: (mode?.textContent ?? "").trim(),
    offlineActive: offline?.getAttribute("data-active") ?? "",
    onlineActive: online?.getAttribute("data-active") ?? "",
    remotesPeople: Number(people?.getAttribute("data-remote-count") ?? "-1"),
    remotesRows: Number(peopleRows?.getAttribute("data-count") ?? "-1"),
    remotesBodies: Number(remotes?.getAttribute("data-count") ?? "-1"),
    friendA: friendA?.getAttribute("data-relation") ?? "",
    friendB: friendB?.getAttribute("data-relation") ?? "",
    addFriendA: Boolean(addA),
    addFriendB: Boolean(addB),
    acceptFriendA: Boolean(acceptA),
    acceptFriendB: Boolean(acceptB),
    unfriendA: Boolean(unfriendA),
    unfriendB: Boolean(unfriendB),
    becomeOwner: Boolean(document.querySelector('[data-testid="become-demo-owner"]')),
    leaveOwner: Boolean(document.querySelector('[data-testid="leave-demo-owner"]')),
    menuOpen: document.querySelector('[data-testid="play-menu"]')?.getAttribute("data-open") ?? "",
    honesty: honesty?.innerText ?? "",
    deniesGta: /no gta|not a digital twin|not 1:1/i.test(honesty?.innerText ?? ""),
    fictionHonesty: /fiction goods|not a live market/i.test(honesty?.innerText ?? ""),
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-owner-off-${port}-`));
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

function facingNorth(heading) {
  const h = wrapHeading(heading);
  return h <= 28 || h >= 332;
}

function facingWest(heading) {
  const h = wrapHeading(heading);
  return h >= 250 && h <= 290;
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

async function turnToward(ws, startId, wantFn) {
  let id = startId;
  for (let i = 0; i < 10; i += 1) {
    const snap = await evalExpr(ws, id, SNAP);
    id += 1;
    if (wantFn(snap.heading)) {
      return { snap, nextId: id };
    }
    await blur(ws, id);
    id += 1;
    const heading = wrapHeading(snap.heading);
    const target = wantFn === facingNorth ? 0 : 270;
    const clockwise = (target - heading + 360) % 360;
    const counter = (heading - target + 360) % 360;
    const useD = clockwise <= counter;
    const deg = Math.min(clockwise, counter);
    const holdMs = Math.min(1600, Math.max(220, Math.round((deg / 110) * 1000) + 80));
    if (useD) {
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

function usableBox(box) {
  if (box && box.w >= 90 && box.h >= 40) {
    return box;
  }
  return { x: 509, y: 642, w: 230, h: 78 };
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

async function liveJsInfo() {
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
  return { liveJs, liveLen, liveSha };
}

async function openMenu(ws, startId) {
  let id = startId;
  const open = await evalExpr(
    ws,
    id,
    `(() => {
      const menu = document.querySelector('[data-testid="play-menu"]');
      if (menu?.getAttribute("data-open") === "yes") {
        return true;
      }
      document.querySelector('[data-testid="play-menu-toggle"]')?.click();
      return true;
    })()`,
  );
  id += 1;
  const ready = await waitSnap(ws, id, (s) => s.menuOpen === "yes" && Boolean(s.identity), 16, 200);
  return { snap: ready.snap, nextId: ready.nextId, opened: open };
}

async function closeMenu(ws, startId) {
  let id = startId;
  await evalExpr(
    ws,
    id,
    `(() => {
      const menu = document.querySelector('[data-testid="play-menu"]');
      if (menu?.getAttribute("data-open") === "yes") {
        document.querySelector('[data-testid="play-menu-toggle"]')?.click();
      }
      return true;
    })()`,
  );
  id += 1;
  const ready = await waitSnap(ws, id, (s) => s.menuOpen !== "yes", 12, 150);
  return { snap: ready.snap, nextId: ready.nextId };
}

const chromes = [];
let report;
try {
  const busBefore = await busGet();
  const busShops = Array.isArray(busBefore?.catalog?.shops) ? busBefore.catalog.shops : [];
  const leftoverGraph = busBefore?.graph?.pairs ?? [];
  const phoShop = busShops.find((row) => row.shop_id === PLAYER_SHOP) ?? null;
  if (!phoShop) {
    throw new Error(`missing ${PLAYER_SHOP} on /demo-bus; will not remint or catalog_clear`);
  }

  const chromeA = launchChrome(PORTS.a);
  chromes.push(chromeA);
  const a = await connectPage(PORTS.a);
  await cdp(a.ws, 1, "Runtime.enable");
  await cdp(a.ws, 2, "Page.enable");
  await cdp(a.ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(a.ws, 4, "Page.navigate", { url: `${PLAYER}?seat=a` });

  const readyA = await waitSnap(
    a.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.stallBoardKind === "chalkboard-menu",
    48,
    250,
  );
  let nextA = readyA.nextId;
  const spawnA = readyA.snap;
  const sawPlayerA = await waitSnap(
    a.ws,
    nextA,
    (s) => s.playerDrawn.some((row) => row.shop === PLAYER_SHOP) || Boolean(s.playerLive),
    24,
    250,
  );
  nextA = sawPlayerA.nextId;

  const menuA = await openMenu(a.ws, nextA);
  nextA = menuA.nextId;
  await evalExpr(a.ws, nextA, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
  nextA += 1;
  const ownerA = await waitSnap(
    a.ws,
    nextA,
    (s) => s.identitySigned === "yes" && /Chủ quầy|Chu quay/i.test(s.identity || ""),
    16,
    200,
  );
  nextA = ownerA.nextId;
  if (!/offline/i.test(ownerA.snap.presenceMode || "") || ownerA.snap.onlineActive === "yes") {
    await evalExpr(a.ws, nextA, `document.querySelector('[data-testid="offline-btn"]')?.click(); true`);
    nextA += 1;
  }
  const ownerOffline = await waitSnap(
    a.ws,
    nextA,
    (s) => /offline/i.test(s.presenceMode || "") && s.onlineActive !== "yes",
    12,
    200,
  );
  nextA = ownerOffline.nextId;

  await evalExpr(a.ws, nextA, `document.querySelector('[data-testid="leave-demo-owner"]')?.click(); true`);
  nextA += 1;
  const leftA = await waitSnap(
    a.ws,
    nextA,
    (s) => s.identitySigned === "no" && /guest/i.test(s.identity || ""),
    16,
    200,
  );
  nextA = leftA.nextId;
  const stillOfflineA = await waitSnap(
    a.ws,
    nextA,
    (s) => /offline/i.test(s.presenceMode || "") && s.identitySigned === "no",
    8,
    150,
  );
  nextA = stillOfflineA.nextId;
  const closedA = await closeMenu(a.ws, nextA);
  nextA = closedA.nextId;
  const aAfterLeave = await waitSnap(
    a.ws,
    nextA,
    (s) =>
      s.playerDrawn.some((row) => row.shop === PLAYER_SHOP) ||
      Boolean(s.boards.find((row) => row.shop === PLAYER_SHOP)),
    12,
    200,
  );
  nextA = aAfterLeave.nextId;

  const chromeB = launchChrome(PORTS.b);
  chromes.push(chromeB);
  const b = await connectPage(PORTS.b);
  await cdp(b.ws, 1, "Runtime.enable");
  await cdp(b.ws, 2, "Page.enable");
  await cdp(b.ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(b.ws, 4, "Page.navigate", { url: `${PLAYER}?seat=b` });

  const readyB = await waitSnap(
    b.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.stallBoardKind === "chalkboard-menu",
    48,
    250,
  );
  let nextB = readyB.nextId;
  const spawnB = readyB.snap;
  const sawPlayerB = await waitSnap(
    b.ws,
    nextB,
    (s) => s.playerDrawn.some((row) => row.shop === PLAYER_SHOP) || Boolean(s.playerLive),
    24,
    250,
  );
  nextB = sawPlayerB.nextId;

  const js = await liveJsInfo();

  const leftoverInherited =
    sawPlayerB.snap.friendA === "accepted" ||
    leftoverGraph.some((row) => row.left === "a" && row.right === "b" && row.status === "accepted");
  let didUnfriendLeftover = false;
  if (
    leftoverInherited ||
    sawPlayerB.snap.friendA === "accepted" ||
    sawPlayerB.snap.friendA === "incoming"
  ) {
    await busUnfriendAB();
    didUnfriendLeftover = true;
  }
  const notFriends = await waitSnap(
    b.ws,
    nextB,
    (s) => s.friendA === "none" || s.friendA === "" || s.friendA === "stranger",
    16,
    250,
  );
  nextB = notFriends.nextId;

  await blur(b.ws, nextB);
  nextB += 1;
  const westFace = await turnToward(b.ws, nextB, facingWest);
  nextB = westFace.nextId;
  for (const ms of [2200, 1800, 1200]) {
    if (eastM((await evalExpr(b.ws, nextB, SNAP)).lon) <= 1.4) {
      nextB += 1;
      break;
    }
    nextB += 1;
    await keyHold(b.ws, nextB, "w", "KeyW", 87, ms);
    nextB += 2;
    await sleep(80);
  }
  const northFace = await turnToward(b.ws, nextB, facingNorth);
  nextB = northFace.nextId;
  const chunks = [1300, 1500, 1700, 1400, 1600, 1200, 1100, 700];
  for (const ms of chunks) {
    if (!facingNorth((await evalExpr(b.ws, nextB, SNAP)).heading)) {
      const turned = await turnToward(b.ws, nextB + 1, facingNorth);
      nextB = turned.nextId;
    } else {
      nextB += 1;
    }
    await keyHold(b.ws, nextB, "w", "KeyW", 87, ms);
    nextB += 2;
    await sleep(80);
    const mid = await evalExpr(b.ws, nextB, SNAP);
    nextB += 1;
    if (mid.nearbyShop === PLAYER_SHOP && northM(mid.lat) > 12) {
      break;
    }
  }

  const atPlayer = await waitSnap(
    b.ws,
    nextB,
    (s) =>
      s.nearbyShop === PLAYER_SHOP &&
      facingNorth(s.heading) &&
      Boolean(s.playerLive?.text || s.playerDrawn.find((row) => row.shop === PLAYER_SHOP)?.titles),
    16,
    220,
  );
  nextB = atPlayer.nextId;
  let walk = atPlayer.snap;
  if (!facingNorth(walk.heading)) {
    const turned = await turnToward(b.ws, nextB, facingNorth);
    nextB = turned.nextId;
    walk = turned.snap;
  }

  const playerRow = walk.playerDrawn.find((row) => row.shop === PLAYER_SHOP) ?? null;
  const playerLive = walk.playerLive;
  const box = usableBox(playerLive?.box);
  const shot = await cdp(b.ws, nextB, "Page.captureScreenshot", { format: "png" });
  nextB += 1;
  const buf = Buffer.from(shot.data, "base64");
  writeFileSync(SHOT, buf);
  const png = decodePngRgba(buf);
  const pad = 16;
  const crop = cropPng(png, box.x - pad, box.y - pad, box.x + box.w + pad, box.y + box.h + pad);
  writePngRgba(SHOT_CROP, crop.width, crop.height, crop.pixels);
  const stats = boardStats(crop.pixels, crop.width, crop.height);
  const cropText = `${playerLive?.text || ""} ${playerLive?.titles || ""} ${playerRow?.titles || ""}`.trim();

  await keyHold(b.ws, nextB, "e", "KeyE", 69, 180);
  nextB += 2;
  await sleep(400);
  const shopOpen = await evalExpr(b.ws, nextB, SNAP);
  nextB += 1;

  const aDuringB = await evalExpr(a.ws, nextA, SNAP);
  nextA += 1;
  const busAfter = await busGet();
  const leftoverPersist = (busAfter?.catalog?.shops || busShops).map((row) => ({
    shop: row.shop_id,
    name: row.name,
    lat: row.lat,
    lon: row.lon,
    northM: Number(northM(row.lat).toFixed(2)),
    owner_presence: row.owner_presence ?? "",
    status: row.status ?? "",
  }));
  const leftoverKeep =
    leftoverPersist.some((row) => row.shop === "shop-local-sharedpc") &&
    leftoverPersist.some((row) => row.shop === "shop-local-mtl8ulddihjpre");
  const phoPersist = leftoverPersist.find((row) => row.shop === PLAYER_SHOP) ?? null;

  const ownerOffOk =
    /offline/i.test(ownerOffline.snap.presenceMode || "") &&
    ownerOffline.snap.identitySigned === "yes" &&
    ownerOffline.snap.onlineActive !== "yes" &&
    /offline/i.test(stillOfflineA.snap.presenceMode || "") &&
    stillOfflineA.snap.identitySigned === "no" &&
    /offline/i.test(aDuringB.presenceMode || "") &&
    aDuringB.identitySigned === "no" &&
    aDuringB.onlineActive !== "yes";
  const aShopStayed =
    (aAfterLeave.snap.playerDrawn || []).some((row) => row.shop === PLAYER_SHOP) ||
    (aAfterLeave.snap.boards || []).some((row) => row.shop === PLAYER_SHOP);
  const guestOk =
    spawnB.identitySigned === "no" &&
    /guest/i.test(spawnB.identity || "") &&
    !/online —/i.test(notFriends.snap.presenceMode || spawnB.presenceMode || "") &&
    shopOpen.identitySigned === "no" &&
    shopOpen.onlineActive !== "yes";
  const notFriendsOk =
    shopOpen.friendA !== "accepted" &&
    walk.friendA !== "accepted" &&
    (notFriends.snap.friendA === "none" ||
      notFriends.snap.friendA === "" ||
      notFriends.snap.friendA === "stranger") &&
    walk.remotesPeople === 0 &&
    walk.remotesBodies === 0 &&
    shopOpen.remotesPeople === 0;
  const atKiosk = walk.nearbyShop === PLAYER_SHOP && northM(walk.lat) > 12;
  const boardOk =
    atKiosk &&
    walk.stallBoardKind === "chalkboard-menu" &&
    playerRow?.draw === "1" &&
    playerLive?.onScreen === true &&
    PLAYER_GOOD.test(cropText) &&
    /mẫu/.test(cropText) &&
    stats.slateRatio >= 0.08 &&
    stats.chalkRatio >= 0.015;
  const eOk =
    shopOpen.shopPanel === true &&
    shopOpen.shopPanelId === PLAYER_SHOP &&
    PLAYER_GOOD.test(shopOpen.goodsText || "");
  const leftoverOk =
    leftoverKeep &&
    (walk.leftoverDrawn || []).length === 0 &&
    !LEFTOVER.test(spawnB.nearbyShop || "") &&
    Boolean(phoPersist) &&
    phoPersist.status === "published";
  const ok =
    ownerOffOk &&
    aShopStayed &&
    guestOk &&
    notFriendsOk &&
    boardOk &&
    eOk &&
    leftoverOk &&
    walk.insideAabb === "0" &&
    spawnB.deniesGta &&
    !spawnB.oidc &&
    js.liveJs === "/assets/index-D4Sc2h68.js";

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_OWNER_OFF_BOARD_OK" : "J5_OWNER_OFF_BOARD_FAIL",
    reminted: false,
    didNotRecycle: true,
    didNotRebuild: true,
    ...js,
    playerShopId: PLAYER_SHOP,
    ownerA: {
      spawnIdentity: spawnA.identity,
      spawnSigned: spawnA.identitySigned,
      spawnMode: spawnA.presenceMode,
      asOwner: ownerA.snap.identity,
      asOwnerSigned: ownerA.snap.identitySigned,
      asOwnerMode: ownerOffline.snap.presenceMode,
      leftIdentity: leftA.snap.identity,
      leftSigned: leftA.snap.identitySigned,
      leftMode: stillOfflineA.snap.presenceMode,
      duringB: {
        identity: aDuringB.identity,
        signed: aDuringB.identitySigned,
        mode: aDuringB.presenceMode,
        onlineActive: aDuringB.onlineActive,
        remotes: aDuringB.remotesPeople,
      },
      shopStayedAfterLeave: aShopStayed,
    },
    cropText,
    cropHasPho: /phở|pho/i.test(cropText),
    cropHasBo: /bò|bo\b/i.test(cropText),
    cropStats: stats,
    cropBox: box,
    cropSize: { w: crop.width, h: crop.height },
    northM: Number(northM(walk.lat).toFixed(2)),
    eastM: Number(eastM(walk.lon).toFixed(2)),
    heading: walk.heading,
    nearby: walk.nearbyShop,
    shopOpen: shopOpen.shopPanelId,
    goods: shopOpen.goods,
    identityB: shopOpen.identity || spawnB.identity,
    identitySignedB: shopOpen.identitySigned,
    presenceModeB: notFriends.snap.presenceMode || spawnB.presenceMode,
    friendASpawn: spawnB.friendA,
    friendAWalk: walk.friendA,
    friendAAfterE: shopOpen.friendA,
    remotesWalk: walk.remotesPeople,
    remotesAfterE: shopOpen.remotesPeople,
    leftoverInherited,
    didUnfriendLeftover,
    didAddFriend: false,
    didClickOnline: false,
    leftovers: walk.leftovers,
    leftoverDrawn: walk.leftoverDrawn,
    leftoverPersist,
    leftoverKeep,
    phoPersist,
    ownerOffOk,
    aShopStayed,
    guestOk,
    notFriendsOk,
    boardOk,
    eOk,
    leftoverOk,
    didNotCatalogClear: true,
    didNotRemint: true,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_OWNER_OFF_BOARD_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_OWNER_OFF_BOARD_OK",
      `js=${js.liveJs}`,
      `crop=${cropText.replace(/\s+/g, " ").slice(0, 80)}`,
      `e=${shopOpen.shopPanelId}`,
      `a=${stillOfflineA.snap.identitySigned}/${stillOfflineA.snap.presenceMode}`,
      `bFriend=${shopOpen.friendA}`,
      `north=${northM(walk.lat).toFixed(1)}`,
    ].join(" "),
  );
} finally {
  for (const chrome of chromes) {
    chrome.kill();
  }
}
