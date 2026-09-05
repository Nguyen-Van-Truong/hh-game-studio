/**
 * Authored stall chalkboard (published listing names) on recycled 4175.
 * Walk-up crop shows Cá / Túi (or live public names) before E.
 * E still opens shop-lantern-fish. Leftover spawn E not stolen.
 * Harbor×Steps stripes stay. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN.
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
const OUT = join(import.meta.dirname, "J5-STALL-BOARD-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-stall-board.png");
const SHOT_CROP = join(import.meta.dirname, "j5-3d-stall-board-crop.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9591), b: 9592 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-21";
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const GOODS_RE = /cá|ca\s|túi|tui|fish|bag|nục|cói/i;
const DRAFT_RE = /nháp chưa đăng|listing-draft-hidden/i;

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
  const chunks = [
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0)),
  ];
  writeFileSync(path, Buffer.concat(chunks));
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
  let white = 0;
  let cream = 0;
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
        cream += 1;
      }
      if (lum > 145 && r > 150 && g > 145 && b > 120 && r - b < 55) {
        white += 1;
      }
    }
  }
  return {
    samples: n,
    slateRatio: Number((slate / Math.max(1, n)).toFixed(3)),
    chalkRatio: Number((chalk / Math.max(1, n)).toFixed(3)),
    creamRatio: Number((cream / Math.max(1, n)).toFixed(3)),
    whiteRatio: Number((white / Math.max(1, n)).toFixed(3)),
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
  const goods = [...document.querySelectorAll('[data-testid="shop-listings"] li')].map((el) => ({
    id: el.getAttribute("data-listing") ?? "",
    kind: el.getAttribute("data-kind") ?? "",
    status: el.getAttribute("data-status") ?? "",
    text: (el.textContent ?? "").trim(),
  }));
  const boards = [...document.querySelectorAll('[data-testid="play-stall-boards"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    keepOut: el.getAttribute("data-keep-out") ?? "",
    titles: el.getAttribute("data-titles") ?? el.textContent ?? "",
    count: Number(el.getAttribute("data-count") ?? "0"),
  }));
  const liveBoard = document.querySelector('[data-testid="shop-menu-board-shop-lantern-fish"]');
  const liveBox = liveBoard ? liveBoard.getBoundingClientRect() : null;
  const crosswalks = [...document.querySelectorAll('[data-testid="play-street-props"] li[data-kind="crosswalk"]')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    corner: el.getAttribute("data-corner") ?? "",
    stripes: Number(el.getAttribute("data-stripes") ?? "0"),
  }));
  const leftovers = boards.filter((row) => /local-sharedpc|mtl8ulddihjpre|j6/i.test(row.shop));
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    insideRing: proof?.getAttribute("data-inside-ring") ?? "",
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
    boards,
    lanternBoard: boards.find((row) => row.shop === "shop-lantern-fish") ?? null,
    liveBoardText: (liveBoard?.textContent ?? "").trim(),
    liveBoardTitles: liveBoard?.getAttribute("data-titles") ?? "",
    liveBoardOnScreen: Boolean(
      liveBox && liveBox.width > 20 && liveBox.height > 12 && liveBox.x > -40 && liveBox.x < 1320 && liveBox.y > -40 && liveBox.y < 760,
    ),
    liveBoardBox: liveBox
      ? { x: Math.round(liveBox.x), y: Math.round(liveBox.y), w: Math.round(liveBox.width), h: Math.round(liveBox.height) }
      : null,
    leftovers,
    leftoverDrawn: leftovers.filter((row) => row.draw === "1").map((row) => row.shop),
    honesty: honesty?.innerText ?? "",
    crosswalks: Number(play?.getAttribute("data-crosswalks") ?? proof?.getAttribute("data-crosswalks") ?? "0"),
    stopLines: Number(play?.getAttribute("data-stop-lines") ?? proof?.getAttribute("data-stop-lines") ?? "0"),
    curbReturns: Number(play?.getAttribute("data-curb-returns") ?? proof?.getAttribute("data-curb-returns") ?? "0"),
    cornerKind: play?.getAttribute("data-corner-crossing") ?? proof?.getAttribute("data-corner-crossing") ?? "",
    lanternZebra: Boolean(crosswalks.some((row) => row.id === "crosswalk-harbor-lantern")),
    cornerZebra: Boolean(crosswalks.some((row) => row.id === "crosswalk-harbor-steps-east" && row.corner === "1")),
    cornerStripes: crosswalks.find((row) => row.id === "crosswalk-harbor-steps-east")?.stripes ?? 0,
    deniesGta: /no gta|not a digital twin|not 1:1/i.test(honesty?.innerText ?? ""),
    fictionHonesty: /fiction goods|not a live market/i.test(honesty?.innerText ?? ""),
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-board-${port}-`));
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
  await keyHold(a.ws, 90, "w", "KeyW", 87, 4500);
  await sleep(160);
  await keyHold(a.ws, 110, "w", "KeyW", 87, 9500);
  await sleep(280);
  const atLantern = await waitSnap(
    a.ws,
    130,
    (s) =>
      Boolean(s.lanternBoard?.titles) &&
      (s.liveBoardOnScreen === true || /cá|túi|fish|bag/i.test(s.lanternBoard?.titles || "")),
    12,
    200,
  );
  const walk = atLantern.snap;
  const shot = await cdp(a.ws, atLantern.nextId, "Page.captureScreenshot", { format: "png" });
  const buf = Buffer.from(shot.data, "base64");
  writeFileSync(SHOT, buf);
  const png = decodePngRgba(buf);
  const box = walk.liveBoardBox ?? { x: 430, y: 210, w: 420, h: 220 };
  const pad = 18;
  const crop = cropPng(png, box.x - pad, box.y - pad, box.x + box.w + pad, box.y + box.h + pad);
  writePngRgba(SHOT_CROP, crop.width, crop.height, crop.pixels);
  const cropBand = boardStats(crop.pixels, crop.width, crop.height);
  const midBand = boardStats(png.pixels, png.width, png.height);

  await keyHold(a.ws, 200, "e", "KeyE", 69, 180);
  await sleep(400);
  const shopOpen = await evalExpr(a.ws, 210, SNAP);
  await evalExpr(a.ws, 211, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(220);
  const shopClosed = await evalExpr(a.ws, 220, SNAP);

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

  const boardText = `${walk.liveBoardText} ${walk.liveBoardTitles} ${walk.lanternBoard?.titles || ""}`;
  const boardShowsGoods = GOODS_RE.test(boardText);
  const boardHidesDraft = !DRAFT_RE.test(boardText);
  const shelfText = shopOpen.goodsText || "";
  const shelfShowsGoods =
    shopOpen.shopPanel === true &&
    /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "") &&
    GOODS_RE.test(shelfText) &&
    shopOpen.goods.some((row) => row.kind === "fish") &&
    shopOpen.goods.some((row) => row.kind === "bag");
  const shelfHidesDraft =
    !DRAFT_RE.test(shelfText) &&
    !shopOpen.goods.some((row) => row.id === "listing-draft-hidden");
  const stripesOk =
    spawn.crosswalks >= 2 &&
    spawn.cornerKind === "zebra-stopline-curb" &&
    spawn.lanternZebra &&
    spawn.cornerZebra &&
    spawn.cornerStripes >= 7;
  const boardVisible =
    walk.stallBoardKind === "chalkboard-menu" &&
    walk.lanternBoard?.draw === "1" &&
    boardShowsGoods &&
    boardHidesDraft &&
    (walk.liveBoardOnScreen === true || cropBand.chalkRatio >= 0.02 || cropBand.slateRatio >= 0.08);
  const leftoverKeepOut =
    (walk.leftoverDrawn || []).length === 0 && leftoverB && leftoverEStolen === false;

  const ok =
    boardVisible &&
    shelfShowsGoods &&
    shelfHidesDraft &&
    leftoverKeepOut &&
    stripesOk &&
    walk.insideAabb === "0" &&
    spawn.deniesGta &&
    spawn.fictionHonesty;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_STALL_BOARD_OK" : "J5_STALL_BOARD_FAIL",
    liveJs,
    liveLen,
    liveSha,
    stallBoardKind: walk.stallBoardKind,
    boardText: boardText.trim(),
    lanternTitles: walk.lanternBoard?.titles ?? "",
    liveBoardOnScreen: walk.liveBoardOnScreen,
    liveBoardBox: walk.liveBoardBox,
    crop: cropBand,
    mid: midBand,
    shopOpen: shopOpen.shopPanelId,
    goods: shopOpen.goods,
    leftovers: walk.leftovers,
    leftoverDrawn: walk.leftoverDrawn,
    leftoverB,
    leftoverEStolen,
    leftoverBNearby: readyB.snap.nearbyShop,
    stripes: {
      crosswalks: spawn.crosswalks,
      cornerKind: spawn.cornerKind,
      lanternZebra: spawn.lanternZebra,
      cornerZebra: spawn.cornerZebra,
      cornerStripes: spawn.cornerStripes,
      stopLines: spawn.stopLines,
      curbReturns: spawn.curbReturns,
    },
    nearbyShop: walk.nearbyShop,
    insideAabb: walk.insideAabb,
    shopClosed: shopClosed.shopPanel === false,
    honestyOk: spawn.deniesGta && spawn.fictionHonesty,
    boardVisible,
    shelfShowsGoods,
    shelfHidesDraft,
    leftoverKeepOut,
    stripesOk,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_STALL_BOARD_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_STALL_BOARD_OK",
      `js=${liveJs}`,
      `board=${walk.lanternBoard?.titles || walk.liveBoardTitles}`,
      `shop=${shopOpen.shopPanelId}`,
      `leftoverB=${leftoverB ? "none" : readyB.snap.nearbyShop}`,
      `stripes=${spawn.cornerStripes}`,
    ].join(" "),
  );
} finally {
  for (const child of chromes) {
    child.kill();
  }
}
