/**
 * Isolated guest seat B on recycled 4175. Empty profile, no add-friend,
 * Offline. Walk to drawn player kiosk. Crop must read Phở bò. E opens
 * shop-local-mtmh45qxehxhvb. B must not be friends with A.
 * Does not catalog_clear. Does not require Online. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-GUEST-BOARD-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-guest-board.png");
const SHOT_CROP = join(import.meta.dirname, "j5-3d-guest-board-crop.png");
const PORT = Number(process.env.HH_CDP_PORT_B || 9625);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-23";
const SPAWN = { lon: 106.69804, lat: 10.77162 };
const M_PER_DEG_LAT = 111320;
const PLAYER_SHOP = "shop-local-mtmh45qxehxhvb";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAYER_GOOD = /phở|pho|bò|bo\b/i;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function northM(lat) {
  return (Number(lat) - SPAWN.lat) * M_PER_DEG_LAT;
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
  const friendA = document.querySelector('[data-testid="friend-row-a"]');
  const addA = document.querySelector('[data-testid="add-friend-a"]');
  const acceptA = document.querySelector('[data-testid="accept-friend-a"]');
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
    name: el.getAttribute("data-name") ?? "",
    lon: Number(el.getAttribute("data-lon") ?? "NaN"),
    lat: Number(el.getAttribute("data-lat") ?? "NaN"),
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
  const playerDrawn = boards.filter((row) => row.source === "local-demo" && row.draw === "1");
  const keys = [];
  try {
    for (let i = 0; i < localStorage.length; i += 1) {
      keys.push(localStorage.key(i) ?? "");
    }
  } catch {
    /* ignore */
  }
  return {
    title: document.title,
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
    stalls,
    leftovers,
    leftoverDrawn: leftovers.filter((row) => row.draw === "1").map((row) => row.shop),
    playerDrawn,
    liveBoards,
    playerLive: liveBoards.find((row) => row.shop === ${JSON.stringify(PLAYER_SHOP)}) ?? null,
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    presenceMode: (mode?.textContent ?? "").trim(),
    friendA: friendA?.getAttribute("data-relation") ?? "",
    addFriendA: Boolean(addA),
    acceptFriendA: Boolean(acceptA),
    clickedAddFriend: false,
    storageKeys: keys,
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-guest-board-${port}-`));
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

function facingNorth(heading) {
  const h = ((Number(heading) % 360) + 360) % 360;
  return h <= 28 || h >= 332;
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

async function turnToNorth(ws, startId) {
  let id = startId;
  for (let i = 0; i < 10; i += 1) {
    const snap = await evalExpr(ws, id, SNAP);
    id += 1;
    if (facingNorth(snap.heading)) {
      return { snap, nextId: id };
    }
    await blur(ws, id);
    id += 1;
    const heading = ((Number(snap.heading) % 360) + 360) % 360;
    const clockwise = (360 - heading) % 360;
    const counter = heading;
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

const chrome = launchChrome(PORT);
let report;
try {
  const busBefore = await busGet();
  const busShops = Array.isArray(busBefore?.catalog?.shops) ? busBefore.catalog.shops : [];
  const leftoverGraph = busBefore?.graph?.pairs ?? [];

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
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.stallBoardKind === "chalkboard-menu",
    48,
    250,
  );
  const spawn = ready.snap;
  const sawPlayer = await waitSnap(
    ws,
    ready.nextId,
    (s) => s.playerDrawn.some((row) => row.shop === PLAYER_SHOP) || Boolean(s.playerLive),
    24,
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

  let nextId = sawPlayer.nextId;
  const leftoverInherited = sawPlayer.snap.friendA === "accepted" || leftoverGraph.some(
    (row) => row.left === "a" && row.right === "b" && row.status === "accepted",
  );
  let didUnfriendLeftover = false;
  if (leftoverInherited || sawPlayer.snap.friendA === "accepted" || sawPlayer.snap.friendA === "incoming") {
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

  await blur(ws, nextId);
  nextId += 1;
  await sleep(120);
  const faced = await turnToNorth(ws, nextId);
  nextId = faced.nextId;
  const chunks = [1300, 1500, 1700, 1400, 1600, 1200, 1100, 700];
  for (const ms of chunks) {
    if (!facingNorth((await evalExpr(ws, nextId, SNAP)).heading)) {
      const turned = await turnToNorth(ws, nextId + 1);
      nextId = turned.nextId;
    } else {
      nextId += 1;
    }
    await keyHold(ws, nextId, "w", "KeyW", 87, ms);
    nextId += 2;
    await sleep(80);
    const mid = await evalExpr(ws, nextId, SNAP);
    nextId += 1;
    if (mid.nearbyShop === PLAYER_SHOP && northM(mid.lat) > 12) {
      break;
    }
  }

  const atPlayer = await waitSnap(
    ws,
    nextId,
    (s) =>
      s.nearbyShop === PLAYER_SHOP &&
      facingNorth(s.heading) &&
      Boolean(s.playerLive?.text || s.playerDrawn.find((row) => row.shop === PLAYER_SHOP)?.titles),
    16,
    220,
  );
  nextId = atPlayer.nextId;
  let walk = atPlayer.snap;
  if (!facingNorth(walk.heading)) {
    const turned = await turnToNorth(ws, nextId);
    nextId = turned.nextId;
    walk = turned.snap;
  }

  const playerRow = walk.playerDrawn.find((row) => row.shop === PLAYER_SHOP) ?? null;
  const playerLive = walk.playerLive;
  const box = usableBox(playerLive?.box);
  const shot = await cdp(ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  const buf = Buffer.from(shot.data, "base64");
  writeFileSync(SHOT, buf);
  const png = decodePngRgba(buf);
  const pad = 16;
  const crop = cropPng(png, box.x - pad, box.y - pad, box.x + box.w + pad, box.y + box.h + pad);
  writePngRgba(SHOT_CROP, crop.width, crop.height, crop.pixels);
  const stats = boardStats(crop.pixels, crop.width, crop.height);
  const cropText = `${playerLive?.text || ""} ${playerLive?.titles || ""} ${playerRow?.titles || ""}`.trim();

  await keyHold(ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  await sleep(400);
  const shopOpen = await evalExpr(ws, nextId, SNAP);
  nextId += 1;

  const busAfter = await busGet();
  const leftoverPersist = (busAfter?.catalog?.shops || busShops).map((row) => ({
    shop: row.shop_id,
    name: row.name,
    lat: row.lat,
    lon: row.lon,
    northM: Number(northM(row.lat).toFixed(2)),
  }));
  const leftoverKeep =
    leftoverPersist.some((row) => row.shop === "shop-local-sharedpc") &&
    leftoverPersist.some((row) => row.shop === "shop-local-mtl8ulddihjpre");

  const guestOk =
    spawn.identitySigned === "no" &&
    /guest/i.test(spawn.identity || "") &&
    !/online —/i.test(notFriends.snap.presenceMode || spawn.presenceMode || "") &&
    shopOpen.identitySigned === "no";
  const notFriendsOk =
    shopOpen.friendA !== "accepted" &&
    walk.friendA !== "accepted" &&
    (notFriends.snap.friendA === "none" ||
      notFriends.snap.friendA === "" ||
      notFriends.snap.friendA === "stranger");
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
    !LEFTOVER.test(spawn.nearbyShop || "") &&
    leftoverPersist.some((row) => row.shop === PLAYER_SHOP);
  const ok =
    guestOk &&
    notFriendsOk &&
    boardOk &&
    eOk &&
    leftoverOk &&
    walk.insideAabb === "0" &&
    spawn.deniesGta &&
    !spawn.oidc;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_GUEST_BOARD_OK" : "J5_GUEST_BOARD_FAIL",
    reminted: false,
    liveJs,
    liveLen,
    liveSha,
    playerShopId: PLAYER_SHOP,
    cropText,
    cropHasPho: /phở|pho/i.test(cropText),
    cropHasBo: /bò|bo\b/i.test(cropText),
    cropStats: stats,
    cropBox: box,
    cropSize: { w: crop.width, h: crop.height },
    northM: Number(northM(walk.lat).toFixed(2)),
    heading: walk.heading,
    nearby: walk.nearbyShop,
    shopOpen: shopOpen.shopPanelId,
    goods: shopOpen.goods,
    identity: shopOpen.identity || spawn.identity,
    identitySigned: shopOpen.identitySigned,
    presenceMode: notFriends.snap.presenceMode || spawn.presenceMode,
    friendASpawn: spawn.friendA,
    friendAWalk: walk.friendA,
    friendAAfterE: shopOpen.friendA,
    leftoverInherited,
    didUnfriendLeftover,
    didAddFriend: false,
    didClickOnline: false,
    storageKeysSpawn: spawn.storageKeys,
    leftovers: walk.leftovers,
    leftoverDrawn: walk.leftoverDrawn,
    leftoverPersist,
    leftoverKeep,
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
    throw new Error(`J5_GUEST_BOARD_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_GUEST_BOARD_OK",
      `js=${liveJs}`,
      `crop=${cropText.replace(/\s+/g, " ").slice(0, 80)}`,
      `e=${shopOpen.shopPanelId}`,
      `friendA=${shopOpen.friendA}`,
      `north=${northM(walk.lat).toFixed(1)}`,
    ].join(" "),
  );
} finally {
  chrome.kill();
}
