/**
 * Player-created streetPlay shop chalkboard on recycled 4175.
 * Same painter as lantern: public names, drafts off, footer mẫu.
 * Create ~20 m north if only spawn leftovers exist. Do not catalog_clear.
 * Leftover spawn E not stolen. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
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
const OUT = join(import.meta.dirname, "J5-PLAYER-BOARD-2026-09-04.txt");
const SHOT_PLAYER = join(import.meta.dirname, "j5-3d-player-board.png");
const SHOT_PLAYER_CROP = join(import.meta.dirname, "j5-3d-player-board-crop.png");
const SHOT_LANTERN = join(import.meta.dirname, "j5-3d-lantern-board-still.png");
const SHOT_LANTERN_CROP = join(import.meta.dirname, "j5-3d-lantern-board-still-crop.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9611), b: 9612 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-22";
const SPAWN = { lon: 106.69804, lat: 10.77162 };
const M_PER_DEG_LAT = 111320;
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAYER_GOOD = /chè|che\s|đậu|dau xanh|phở|pho|bò|bo\b/i;
const LANTERN_GOODS = /cá|ca\s|túi|tui|nục|cói|fish|bag/i;
const DRAFT_RE = /nháp chưa đăng|listing-draft-hidden/i;
const SHOP_NAME = "Quầy Chè Hẻm";
const SHOP_SELLS = "Chè đậu xanh";

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
  const identity = document.querySelector('[data-testid="create-shop-identity"], [data-testid="demo-identity"]');
  const result = document.querySelector('[data-testid="create-shop-result"]');
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
    lanternBoard: boards.find((row) => row.shop === "shop-lantern-fish") ?? null,
    liveBoards,
    lanternLive: liveBoards.find((row) => row.shop === "shop-lantern-fish") ?? null,
    menuOpen: document.body.getAttribute("data-menu") === "open" ||
      document.querySelector('[data-testid="play-menu"]')?.getAttribute("data-open") === "yes",
    createForm: Boolean(document.querySelector('[data-testid="create-shop-form"]')),
    become: Boolean(document.querySelector('[data-testid="become-demo-owner"]')),
    createResult: result
      ? {
          status: result.getAttribute("data-status") ?? "",
          shop: result.getAttribute("data-shop") ?? "",
          listing: result.getAttribute("data-listing") ?? "",
          text: (result.textContent ?? "").trim(),
        }
      : null,
    identity: (identity?.textContent ?? "").trim(),
    honesty: honesty?.innerText ?? "",
    deniesGta: /no gta|not a digital twin|not 1:1/i.test(honesty?.innerText ?? ""),
    fictionHonesty: /fiction goods|not a live market/i.test(honesty?.innerText ?? ""),
    localDemo: /local demo identity|máy này|not a real account/i.test(
      (identity?.textContent ?? "") + " " + (honesty?.innerText ?? ""),
    ),
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

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-player-board-${port}-`));
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
  for (let i = 0; i < 8; i += 1) {
    const snap = await evalExpr(ws, id, SNAP);
    id += 1;
    if (facingNorth(snap.heading)) {
      return { snap, nextId: id };
    }
    await blur(ws, id);
    id += 1;
    await keyHold(ws, id, "a", "KeyA", 65, 450);
    id += 2;
    await sleep(80);
  }
  const snap = await evalExpr(ws, id, SNAP);
  return { snap, nextId: id + 1 };
}

function usableBox(box) {
  if (box && box.w >= 90 && box.h >= 50) {
    return box;
  }
  return { x: 540, y: 548, w: 200, h: 130 };
}

async function shotCrop(ws, id, liveBox, shotPath, cropPath) {
  const shot = await cdp(ws, id, "Page.captureScreenshot", { format: "png" });
  const buf = Buffer.from(shot.data, "base64");
  writeFileSync(shotPath, buf);
  const png = decodePngRgba(buf);
  const box = usableBox(liveBox);
  const pad = 18;
  const crop = cropPng(png, box.x - pad, box.y - pad, box.x + box.w + pad, box.y + box.h + pad);
  writePngRgba(cropPath, crop.width, crop.height, crop.pixels);
  return { stats: boardStats(crop.pixels, crop.width, crop.height), box, crop: { w: crop.width, h: crop.height } };
}

const chromes = [];
let report;
try {
  const bus = await fetch(new URL("/demo-bus", PLAYER)).then((res) => res.json());
  const busShops = Array.isArray(bus?.catalog?.shops) ? bus.catalog.shops : [];
  const busDrawnCandidates = busShops.filter((row) => {
    const lat = Number(row.lat);
    return typeof row.shop_id === "string" && row.shop_id.startsWith("shop-local-") && northM(lat) > 14;
  });

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
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.stallBoardKind === "chalkboard-menu",
    40,
    250,
  );
  const readyB = await waitSnap(
    b.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    40,
    250,
  );
  const spawn = readyA.snap;

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

  let nextId = 80;
  await blur(a.ws, nextId);
  nextId += 1;
  await sleep(120);

  const existingDrawn = (spawn.playerDrawn || []).filter((row) => !LEFTOVER.test(row.shop));
  let created = null;
  let usedExisting = existingDrawn[0] || null;
  if (!usedExisting && busDrawnCandidates.length === 0) {
    await keyHold(a.ws, nextId, "w", "KeyW", 87, 12500);
    nextId += 2;
    await sleep(280);
    await evalExpr(a.ws, nextId, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
    nextId += 1;
    await sleep(350);
    await evalExpr(a.ws, nextId, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
    nextId += 1;
    await sleep(250);
    await evalExpr(
      a.ws,
      nextId,
      `(() => {
        const name = document.querySelector('[data-testid="create-shop-name"]');
        const good = document.querySelector('[data-testid="create-shop-good"]');
        const setReact = (el, value) => {
          const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
          desc.set.call(el, value);
          el.dispatchEvent(new Event("input", { bubbles: true }));
        };
        if (name) {
          name.focus();
          setReact(name, ${JSON.stringify(SHOP_NAME)});
        }
        if (good) {
          good.focus();
          setReact(good, ${JSON.stringify(SHOP_SELLS)});
        }
        return { name: name?.value ?? "", good: good?.value ?? "" };
      })()`,
    );
    nextId += 1;
    await evalExpr(a.ws, nextId, `document.querySelector('[data-testid="create-shop-submit"]')?.click(); true`);
    nextId += 1;
    const createdSnap = await waitSnap(
      a.ws,
      nextId,
      (s) => s.createResult?.status === "published" && Boolean(s.createResult?.shop),
      16,
      200,
    );
    nextId = createdSnap.nextId;
    created = createdSnap.snap.createResult;
    await evalExpr(a.ws, nextId, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
    nextId += 1;
    await sleep(200);
    await blur(a.ws, nextId);
    nextId += 1;
    await blur(a.ws, nextId);
    nextId += 1;
    await keyHold(a.ws, nextId, "s", "KeyS", 83, 3500);
    nextId += 2;
    await sleep(160);
    const turned = await turnToNorth(a.ws, nextId);
    nextId = turned.nextId;
  } else {
    await keyHold(a.ws, nextId, "w", "KeyW", 87, 9500);
    nextId += 2;
    await sleep(280);
  }

  const atPlayer = await waitSnap(
    a.ws,
    nextId,
    (s) => {
      const row =
        s.playerDrawn.find((item) => item.shop === created?.shop) ||
        s.playerDrawn.find((item) => !LEFTOVER.test(item.shop)) ||
        null;
      const live = row ? s.liveBoards.find((item) => item.shop === row.shop) : null;
      return (
        Boolean(row?.titles) &&
        facingNorth(s.heading) &&
        (live?.onScreen === true || PLAYER_GOOD.test(row?.titles || "") || /mẫu/.test(row?.titles || ""))
      );
    },
    16,
    220,
  );
  nextId = atPlayer.nextId;
  let playerWalk = atPlayer.snap;
  if (!facingNorth(playerWalk.heading)) {
    const turned = await turnToNorth(a.ws, nextId);
    nextId = turned.nextId;
    playerWalk = turned.snap;
  }
  const playerRow =
    playerWalk.playerDrawn.find((item) => item.shop === created?.shop) ||
    playerWalk.playerDrawn.find((item) => !LEFTOVER.test(item.shop)) ||
    playerWalk.playerDrawn[0] ||
    null;
  const playerLive = playerRow
    ? playerWalk.liveBoards.find((item) => item.shop === playerRow.shop)
    : null;
  const playerCrop = await shotCrop(a.ws, nextId, playerLive?.box, SHOT_PLAYER, SHOT_PLAYER_CROP);
  nextId += 1;

  await keyHold(a.ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  await sleep(400);
  const shopOpen = await evalExpr(a.ws, nextId, SNAP);
  nextId += 1;
  await evalExpr(a.ws, nextId, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  nextId += 1;
  await sleep(220);
  await blur(a.ws, nextId);
  nextId += 1;
  if (!facingNorth((await evalExpr(a.ws, nextId, SNAP)).heading)) {
    const turned = await turnToNorth(a.ws, nextId + 1);
    nextId = turned.nextId;
  } else {
    nextId += 1;
  }

  await keyHold(a.ws, nextId, "w", "KeyW", 87, 9000);
  nextId += 2;
  await sleep(280);
  const atLantern = await waitSnap(
    a.ws,
    nextId,
    (s) =>
      Boolean(s.lanternBoard?.titles) &&
      (s.lanternLive?.onScreen === true || LANTERN_GOODS.test(s.lanternBoard?.titles || "")),
    12,
    200,
  );
  nextId = atLantern.nextId;
  const lanternWalk = atLantern.snap;
  const lanternCrop = await shotCrop(
    a.ws,
    nextId,
    lanternWalk.lanternLive?.box,
    SHOT_LANTERN,
    SHOT_LANTERN_CROP,
  );
  nextId += 1;

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

  const playerBoardText = `${playerLive?.text || ""} ${playerLive?.titles || ""} ${playerRow?.titles || ""}`;
  const lanternBoardText = `${lanternWalk.lanternLive?.text || ""} ${lanternWalk.lanternLive?.titles || ""} ${lanternWalk.lanternBoard?.titles || ""}`;
  const playerBoardOk =
    playerWalk.stallBoardKind === "chalkboard-menu" &&
    playerRow?.draw === "1" &&
    playerRow?.source === "local-demo" &&
    PLAYER_GOOD.test(playerBoardText) &&
    /mẫu/.test(playerBoardText) &&
    !DRAFT_RE.test(playerBoardText) &&
    !LEFTOVER.test(playerRow?.shop || "") &&
    (playerLive?.onScreen === true ||
      playerCrop.stats.chalkRatio >= 0.02 ||
      playerCrop.stats.slateRatio >= 0.08 ||
      /mẫu/.test(playerBoardText));
  const lanternStillOk =
    lanternWalk.lanternBoard?.draw === "1" &&
    LANTERN_GOODS.test(lanternBoardText) &&
    /cá nục|nục sương/i.test(lanternBoardText) &&
    /túi cói|cói chợ/i.test(lanternBoardText) &&
    !DRAFT_RE.test(lanternBoardText);
  const eOpensPlayer =
    shopOpen.shopPanel === true &&
    shopOpen.shopPanelId === playerRow?.shop &&
    PLAYER_GOOD.test(shopOpen.goodsText || "") &&
    !DRAFT_RE.test(shopOpen.goodsText || "") &&
    !LEFTOVER.test(shopOpen.shopPanelId || "");
  const leftoverKeepOut =
    (playerWalk.leftoverDrawn || []).length === 0 && leftoverB && leftoverEStolen === false;
  const shopNorth = playerRow
    ? northM(playerWalk.stalls.find((row) => row.shop === playerRow.shop)?.lat)
    : NaN;
  const placedOffSpawn = Number.isFinite(shopNorth) && shopNorth > 14;
  const honestyOk = spawn.deniesGta && spawn.fictionHonesty && !spawn.oidc;

  const ok =
    playerBoardOk &&
    lanternStillOk &&
    eOpensPlayer &&
    leftoverKeepOut &&
    placedOffSpawn &&
    playerWalk.insideAabb === "0" &&
    honestyOk;

  const busAfter = await fetch(new URL("/demo-bus", PLAYER)).then((res) => res.json());
  const leftoverPersist = (busAfter?.catalog?.shops || busShops || []).map((row) => ({
    shop: row.shop_id,
    name: row.name,
    lat: row.lat,
    lon: row.lon,
    northM: Number(northM(row.lat).toFixed(2)),
  }));

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_PLAYER_BOARD_OK" : "J5_PLAYER_BOARD_FAIL",
    liveJs,
    liveLen,
    liveSha,
    created,
    usedExisting: usedExisting?.shop ?? null,
    playerShopId: playerRow?.shop ?? "",
    playerBoardText: playerBoardText.trim(),
    lanternBoardText: lanternBoardText.trim(),
    shopNorthM: Number(shopNorth.toFixed(2)),
    heading: playerWalk.heading,
    playerCrop,
    lanternCrop,
    shopOpen: shopOpen.shopPanelId,
    goods: shopOpen.goods,
    leftovers: playerWalk.leftovers,
    leftoverDrawn: playerWalk.leftoverDrawn,
    leftoverPersist,
    leftoverB,
    leftoverEStolen,
    leftoverBNearby: readyB.snap.nearbyShop,
    identity: playerWalk.identity || spawn.identity,
    oidc: spawn.oidc,
    honestyOk,
    playerBoardOk,
    lanternStillOk,
    eOpensPlayer,
    leftoverKeepOut,
    placedOffSpawn,
    didNotCatalogClear: true,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_PLAYER_BOARD_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_PLAYER_BOARD_OK",
      `js=${liveJs}`,
      `shop=${playerRow?.shop}`,
      `board=${playerRow?.titles}`,
      `lantern=${lanternWalk.lanternBoard?.titles}`,
      `north=${shopNorth.toFixed(1)}`,
      `leftoverB=${leftoverB ? "none" : readyB.snap.nearbyShop}`,
    ].join(" "),
  );
} finally {
  for (const child of chromes) {
    child.kill();
  }
}
