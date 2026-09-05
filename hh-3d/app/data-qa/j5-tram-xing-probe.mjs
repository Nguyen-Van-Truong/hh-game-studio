/**
 * Authored Harbor Walk / Tram Approach crossing: zebra + stop-line + curb
 * return. Walk Harbor then east onto Tram; chip→Tram Approach; minimap
 * agrees after mount; lantern / east / west zebras kept; leftover Menu
 * labels last. NOT_PLAN_PASS. Not GATE-U1. Not OSM / WAN. Not a fifth street.
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
const OUT = join(import.meta.dirname, "J5-TRAM-XING-2026-09-04.txt");
const SHOT_TRAM = join(import.meta.dirname, "j5-3d-tram-xing-tram.png");
const SHOT_LOOK = join(import.meta.dirname, "j5-3d-tram-xing-lookdown.png");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9693), b: 9694 };
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-30";
const LEFTOVER_IDS = new Set(["shop-local-sharedpc", "shop-local-mtl8ulddihjpre"]);
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAYER_SHOP = "shop-local-mtmh45qxehxhvb";
const LANTERN = "shop-lantern-fish";
const M_PER_DEG_LAT = 111320;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
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

async function sprintHold(ws, id, ms) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Shift",
    code: "ShiftLeft",
    windowsVirtualKeyCode: 16,
    nativeVirtualKeyCode: 16,
  });
  await cdp(ws, id + 1, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "w",
    code: "KeyW",
    windowsVirtualKeyCode: 87,
    nativeVirtualKeyCode: 87,
  });
  await sleep(ms);
  await cdp(ws, id + 2, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "w",
    code: "KeyW",
    windowsVirtualKeyCode: 87,
    nativeVirtualKeyCode: 87,
  });
  await cdp(ws, id + 3, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Shift",
    code: "ShiftLeft",
    windowsVirtualKeyCode: 16,
    nativeVirtualKeyCode: 16,
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
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (lum > 145 && r > 150 && g > 145 && b > 120 && r - b < 55) white += 1;
      if (lum > 70 && lum < 160 && r > g - 8 && g > b && r - b > 8 && r - b < 55 && Math.abs(r - g) < 28) {
        curb += 1;
      }
      if (lum < 70) dark += 1;
      if (r > 170 && g > 140 && b < 180 && r - b > 20) beige += 1;
      if (b > r + 8 && b > 90) blueish += 1;
    }
  }
  return {
    samples: n,
    whiteRatio: Number((white / Math.max(1, n)).toFixed(3)),
    curbRatio: Number((curb / Math.max(1, n)).toFixed(3)),
    darkRatio: Number((dark / Math.max(1, n)).toFixed(3)),
    beigeRatio: Number((beige / Math.max(1, n)).toFixed(3)),
    blueRatio: Number((blueish / Math.max(1, n)).toFixed(3)),
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
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const wrap = document.querySelector(".minimap-wrap");
  const worldMap = document.querySelector('[data-testid="hh-world-map"]');
  const corner = document.querySelector('[data-testid="play-corner-crossing"]');
  const props = document.querySelector('[data-testid="play-street-props"]');
  const names = document.querySelector('[data-testid="public-shop-names"]');
  const identity = document.querySelector('[data-testid="demo-identity"]');
  const plaques = [...document.querySelectorAll('[data-testid="play-street-plaques"] li')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    name: el.getAttribute("data-name") ?? el.textContent ?? "",
  }));
  const crosswalks = [...document.querySelectorAll('[data-testid="play-street-props"] li[data-kind="crosswalk"]')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    corner: el.getAttribute("data-corner") ?? "",
    mouth: el.getAttribute("data-mouth") ?? "",
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
    stripes: Number(el.getAttribute("data-stripes") ?? "0"),
  }));
  const stopLines = [...document.querySelectorAll('[data-kind="stop-line"]')].map((el) => el.getAttribute("data-testid") ?? "");
  const curbReturns = [...document.querySelectorAll('[data-kind="curb-return"]')].map((el) => el.getAttribute("data-testid") ?? "");
  const chipBox = chip ? chip.getBoundingClientRect() : null;
  const miniItems = [...document.querySelectorAll('[data-testid="hh-world-minimap-lanes"] li')].map((el) => ({
    name: el.getAttribute("data-name") ?? el.textContent ?? "",
    role: el.getAttribute("data-role") ?? "",
    active: el.getAttribute("data-active") ?? "",
  }));
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    name: (el.querySelector(".menu-shop-name")?.textContent ?? el.textContent ?? "").trim().split("\\n")[0],
    leftover: el.getAttribute("data-leftover") ?? "",
    street: el.getAttribute("data-street") ?? "",
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
  }));
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    alt: Number(avatar?.getAttribute("data-alt") ?? proof?.getAttribute("data-alt") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    atBound: avatar?.getAttribute("data-at-bound") ?? proof?.getAttribute("data-at-bound") ?? "",
    insideAabb: proof?.getAttribute("data-inside-aabb") ?? "",
    insideRing: proof?.getAttribute("data-inside-ring") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    sky: proof?.getAttribute("data-sky") ?? "",
    fog: proof?.getAttribute("data-fog") ?? "",
    blockEdge: proof?.getAttribute("data-block-edge") ?? "",
    groundFloor: proof?.getAttribute("data-ground-floor") ?? "",
    innerLane: proof?.getAttribute("data-inner-lane") ?? play?.getAttribute("data-inner-lane") ?? "",
    streetPlaques: Number(proof?.getAttribute("data-street-plaques") ?? play?.getAttribute("data-street-plaques") ?? "0"),
    streetHud: play?.getAttribute("data-street-hud") ?? proof?.getAttribute("data-street-hud") ?? "",
    streetName:
      chip?.getAttribute("data-street-name") ??
      play?.getAttribute("data-street-name") ??
      proof?.getAttribute("data-street-name") ??
      "",
    chipText: (chip?.textContent ?? "").trim(),
    chipOnScreen: Boolean(
      chipBox && chipBox.width > 8 && chipBox.height > 8 && chipBox.x > -8 && chipBox.x < 1288 && chipBox.y > -8 && chipBox.y < 728,
    ),
    menuHidden: Boolean(menu?.hidden) || menu?.getAttribute("data-open") === "no",
    menuOpen: menu?.getAttribute("data-open") === "yes" && menu?.hidden !== true,
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    leftoverCount: Number(names?.getAttribute("data-leftover-count") ?? "0"),
    streetCount: Number(names?.getAttribute("data-street-count") ?? "0"),
    rows,
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    honesty: honesty?.innerText ?? "",
    plaques,
    plaqueNames: plaques.map((row) => row.name),
    cornerKind: play?.getAttribute("data-corner-crossing") ?? proof?.getAttribute("data-corner-crossing") ?? corner?.getAttribute("data-kind") ?? "",
    crosswalks: Number(play?.getAttribute("data-crosswalks") ?? proof?.getAttribute("data-crosswalks") ?? props?.getAttribute("data-crosswalks") ?? "0"),
    stopLines: Number(play?.getAttribute("data-stop-lines") ?? proof?.getAttribute("data-stop-lines") ?? "0"),
    curbReturns: Number(play?.getAttribute("data-curb-returns") ?? proof?.getAttribute("data-curb-returns") ?? "0"),
    crosswalkRows: crosswalks,
    stopLineIds: [...new Set(stopLines.filter(Boolean))],
    curbReturnIds: [...new Set(curbReturns.filter(Boolean))],
    lanternZebra: Boolean(crosswalks.some((row) => row.id === "crosswalk-harbor-lantern")),
    eastZebra: Boolean(crosswalks.some((row) => row.id === "crosswalk-harbor-steps-east" && row.stripes === 7)),
    westZebra: Boolean(crosswalks.some((row) => row.id === "crosswalk-harbor-steps-west" && row.stripes === 7)),
    tramZebra: Boolean(crosswalks.some((row) => row.id === "crosswalk-harbor-tram" && row.stripes === 7 && row.mouth === "tram")),
    worldMapPresent: Boolean(worldMap),
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
    miniActiveItem: miniItems.find((row) => row.active === "1") ?? null,
    gtaClaim:
      /gta\\s*6|rockstar|1:1 city|digital twin/i.test(document.body.innerText) &&
      !/no gta|not a digital twin|not 1:1/i.test(document.body.innerText),
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

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-tram-xing-${port}-`));
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

async function waitSnap(ws, startId, pred, tries = 36, delay = 250) {
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
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.chipText,
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
  const spawn = readyA.snap;

  const geo = await fetch(`${PLAYER}data/ben-thanh-400m.authored.geojson`).then((res) => res.json());
  const geoStreets = (geo.features ?? []).filter((row) => row.properties?.kind === "street");
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
    b.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(80);
  await keyHold(b.ws, 82, "Tab", "Tab", 9, 80);
  const menuB = await waitSnap(
    b.ws,
    90,
    (s) => s.menuOpen === true && s.rows.some((row) => row.shop === LANTERN) && s.leftoverCount >= 2,
    28,
    220,
  );
  const leftoverRows = menuB.snap.rows.filter(
    (row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop) || LEFTOVER.test(row.name),
  );
  const leftoverLast =
    leftoverRows.length === 0 ||
    menuB.snap.rows.slice(menuB.snap.rows.length - leftoverRows.length).every((row) => row.leftover === "1");
  const leftoverLabeled = leftoverRows.length >= 2 && leftoverRows.every((row) => row.leftover === "1" && row.labeled);
  await keyHold(b.ws, 130, "Escape", "Escape", 27, 80);
  await sleep(180);
  await keyHold(b.ws, 134, "e", "KeyE", 69, 180);
  await sleep(280);
  const bAfterE = await evalExpr(b.ws, 140, SNAP);
  const leftoverEStolen = Boolean(bAfterE.shopPanel) && LEFTOVER.test(bAfterE.shopPanelId || "");
  const leftoverB =
    !LEFTOVER.test(readyB.snap.nearbyShop || "") &&
    !LEFTOVER.test(readyB.snap.stallHint || "") &&
    !LEFTOVER.test(readyB.snap.shopRange || "") &&
    readyB.snap.nearbyShop !== "shop-local-sharedpc" &&
    readyB.snap.nearbyShop !== "shop-local-mtl8ulddihjpre";

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
  await keyHold(a.ws, 90, "w", "KeyW", 87, 2400);
  await sleep(160);
  const onHarbor = await evalExpr(a.ws, 100, SNAP);

  let walkId = 110;
  let atJoin = { snap: onHarbor, nextId: walkId };
  const walkLog = [];
  for (let chunk = 0; chunk < 12; chunk += 1) {
    if (atJoin.snap.chipText === "Steps East") {
      await keyHold(a.ws, walkId, "a", "KeyA", 65, 850);
      walkId += 2;
      await keyHold(a.ws, walkId, "w", "KeyW", 87, 2200);
      walkId += 2;
      await keyHold(a.ws, walkId, "d", "KeyD", 68, 850);
      walkId += 2;
    } else if (atJoin.snap.chipText === "Steps West") {
      await keyHold(a.ws, walkId, "d", "KeyD", 68, 850);
      walkId += 2;
      await keyHold(a.ws, walkId, "w", "KeyW", 87, 2200);
      walkId += 2;
      await keyHold(a.ws, walkId, "a", "KeyA", 65, 850);
      walkId += 2;
    }
    const beforeLat = atJoin.snap.lat;
    await keyHold(a.ws, walkId, "w", "KeyW", 87, 7000);
    walkId += 2;
    await sleep(120);
    atJoin = { snap: await evalExpr(a.ws, walkId, SNAP), nextId: walkId + 1 };
    walkId += 1;
    const gained = (atJoin.snap.lat - beforeLat) * M_PER_DEG_LAT;
    walkLog.push({
      chunk,
      lat: atJoin.snap.lat,
      lon: atJoin.snap.lon,
      chip: atJoin.snap.chipText,
      heading: atJoin.snap.heading,
      gained: Number(gained.toFixed(2)),
    });
    if (atJoin.snap.lat > 10.77242 && (atJoin.snap.chipText === "Harbor Walk" || atJoin.snap.chipText === "Tram Approach")) {
      break;
    }
    if (gained < 3.2) {
      await keyHold(a.ws, walkId, "a", "KeyA", 65, 300);
      walkId += 2;
      await keyHold(a.ws, walkId, "w", "KeyW", 87, 2600);
      walkId += 2;
      await keyHold(a.ws, walkId, "d", "KeyD", 68, 300);
      walkId += 2;
      await sleep(80);
      atJoin = { snap: await evalExpr(a.ws, walkId, SNAP), nextId: walkId + 1 };
      walkId += 1;
    }
  }

  await keyHold(a.ws, walkId, "d", "KeyD", 68, 850);
  walkId += 2;
  await sleep(80);
  await keyHold(a.ws, walkId, "w", "KeyW", 87, 4200);
  walkId += 2;
  await sleep(200);
  let onTram = await waitSnap(
    a.ws,
    walkId,
    (s) =>
      (s.chipText === "Tram Approach" || s.streetName === "Tram Approach") &&
      (s.minimap?.present === true || s.minimapDefer === "live"),
    12,
    220,
  );
  walkId = onTram.nextId;
  if (onTram.snap.chipText !== "Tram Approach" && onTram.snap.streetName !== "Tram Approach") {
    await keyHold(a.ws, walkId, "w", "KeyW", 87, 2800);
    walkId += 2;
    await sleep(200);
    onTram = await waitSnap(
      a.ws,
      walkId,
      (s) => s.chipText === "Tram Approach" || s.streetName === "Tram Approach",
      10,
      220,
    );
    walkId = onTram.nextId;
  }
  const tramSnap = onTram.snap;
  const tramShot = await cdp(a.ws, walkId, "Page.captureScreenshot", { format: "png" });
  walkId += 1;
  const tramBuf = Buffer.from(tramShot.data, "base64");
  writeFileSync(SHOT_TRAM, tramBuf);
  const tramPng = decodePngRgba(tramBuf);
  const tramFloor = bandStats(tramPng.pixels, tramPng.width, tramPng.height, 280, 360, 1000, 700);
  const tramMid = bandStats(tramPng.pixels, tramPng.width, tramPng.height, 360, 280, 920, 580);

  await keyHold(a.ws, walkId, "s", "KeyS", 83, 1200);
  walkId += 2;
  await sleep(160);
  const lookSnap = await evalExpr(a.ws, walkId, SNAP);
  walkId += 1;
  const lookShot = await cdp(a.ws, walkId, "Page.captureScreenshot", { format: "png" });
  walkId += 1;
  const lookBuf = Buffer.from(lookShot.data, "base64");
  writeFileSync(SHOT_LOOK, lookBuf);
  const lookPng = decodePngRgba(lookBuf);
  const lookFloor = bandStats(lookPng.pixels, lookPng.width, lookPng.height, 280, 360, 1000, 700);
  const lookMid = bandStats(lookPng.pixels, lookPng.width, lookPng.height, 360, 260, 920, 600);

  await keyHold(a.ws, walkId, "a", "KeyA", 65, 850);
  walkId += 2;
  await keyHold(a.ws, walkId, "a", "KeyA", 65, 850);
  walkId += 2;
  await keyHold(a.ws, walkId, "w", "KeyW", 87, 4000);
  walkId += 2;
  await keyHold(a.ws, walkId, "a", "KeyA", 65, 850);
  walkId += 2;
  await keyHold(a.ws, walkId, "w", "KeyW", 87, 20000);
  walkId += 2;
  await keyHold(a.ws, walkId, "w", "KeyW", 87, 20000);
  walkId += 2;
  await sleep(180);
  let atLantern = await waitSnap(
    a.ws,
    walkId,
    (s) => s.nearbyShop === LANTERN || /lantern/i.test(s.nearbyShop || ""),
    8,
    200,
  );
  walkId = atLantern.nextId;
  for (let hunt = 0; hunt < 4 && atLantern.snap.nearbyShop !== LANTERN; hunt += 1) {
    if (atLantern.snap.chipText === "Steps East") {
      await keyHold(a.ws, walkId, "a", "KeyA", 65, 850);
      walkId += 2;
      await keyHold(a.ws, walkId, "w", "KeyW", 87, 3200);
      walkId += 2;
    } else if (atLantern.snap.chipText === "Steps West") {
      await keyHold(a.ws, walkId, "d", "KeyD", 68, 850);
      walkId += 2;
      await keyHold(a.ws, walkId, "w", "KeyW", 87, 3200);
      walkId += 2;
    } else {
      await keyHold(a.ws, walkId, "w", "KeyW", 87, 4000);
      walkId += 2;
    }
    await sleep(140);
    atLantern = await waitSnap(
      a.ws,
      walkId,
      (s) => s.nearbyShop === LANTERN || /lantern/i.test(s.nearbyShop || ""),
      6,
      180,
    );
    walkId = atLantern.nextId;
  }
  await keyHold(a.ws, walkId, "e", "KeyE", 69, 180);
  walkId += 2;
  await sleep(350);
  const shopOpen = await evalExpr(a.ws, walkId, SNAP);
  walkId += 1;
  await evalExpr(a.ws, walkId, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  walkId += 1;
  await sleep(250);
  const shopClosed = await evalExpr(a.ws, walkId, SNAP);
  walkId += 1;

  const tramM = (tramSnap.lon - spawn.lon) * metersPerDegLon((tramSnap.lat + spawn.lat) / 2);
  const northM = (tramSnap.lat - spawn.lat) * M_PER_DEG_LAT;
  const cornerDom =
    spawn.cornerKind === "zebra-stopline-curb" &&
    spawn.crosswalks >= 4 &&
    spawn.stopLines >= 3 &&
    spawn.curbReturns >= 12 &&
    spawn.lanternZebra &&
    spawn.eastZebra &&
    spawn.westZebra &&
    spawn.tramZebra &&
    spawn.stopLineIds.some((id) => /stopline-harbor-steps-east/.test(id)) &&
    spawn.stopLineIds.some((id) => /stopline-harbor-steps-west/.test(id)) &&
    spawn.stopLineIds.some((id) => /stopline-harbor-tram/.test(id)) &&
    spawn.curbReturnIds.some((id) => /curb-return-harbor-tram/.test(id)) &&
    spawn.curbReturnIds.some((id) => /curb-return-tram-approach/.test(id));
  const harborChip =
    (onHarbor.chipText === "Harbor Walk" || onHarbor.streetName === "Harbor Walk") &&
    onHarbor.chipOnScreen &&
    onHarbor.streetHud === "named-chip";
  const tramChip =
    (tramSnap.chipText === "Tram Approach" || tramSnap.streetName === "Tram Approach") &&
    tramSnap.chipOnScreen &&
    tramSnap.chipText !== onHarbor.chipText;
  const walkedOff =
    northM > 70 &&
    (tramM > 1.2 || tramSnap.chipText === "Tram Approach" || tramSnap.streetName === "Tram Approach") &&
    tramSnap.insideRing === "0" &&
    tramSnap.insideAabb === "0";
  const miniAfter =
    tramSnap.minimap?.present === true &&
    tramSnap.minimap?.kind === "authored-hud-lanes" &&
    tramSnap.minimap?.official === 2 &&
    tramSnap.minimap?.inner >= 2 &&
    tramSnap.minimap?.active === "Tram Approach" &&
    tramSnap.minimap?.highlight === "1" &&
    tramSnap.minimap?.activeRole === "official" &&
    tramSnap.chipText === tramSnap.minimap?.active &&
    tramSnap.engine === "r3f" &&
    tramSnap.worldMapPresent === false;
  const tramStripesOk =
    tramFloor.whiteRatio >= 0.04 ||
    tramMid.whiteRatio >= 0.04 ||
    lookFloor.whiteRatio >= 0.04 ||
    lookMid.whiteRatio >= 0.04;
  const tramCurbOk =
    tramFloor.curbRatio >= 0.012 ||
    tramMid.curbRatio >= 0.012 ||
    lookFloor.curbRatio >= 0.012 ||
    tramFloor.darkRatio >= 0.08;
  const keptZebras = tramSnap.lanternZebra && tramSnap.eastZebra && tramSnap.westZebra && tramSnap.tramZebra;
  const lanternOk =
    Boolean(shopOpen.shopPanel) && /lantern|shop-lantern-fish/i.test(shopOpen.shopPanelId || "");
  const leftoverOk =
    leftoverB &&
    !leftoverEStolen &&
    !bAfterE.shopPanel &&
    leftoverLast &&
    leftoverLabeled;
  const honestyOk =
    /Authored approximation/.test(spawn.honesty) &&
    /not a digital twin/i.test(spawn.honesty) &&
    /Authored 400 m/.test(spawn.honesty) &&
    /inner parcel lanes/.test(spawn.honesty) &&
    /two official named streets/.test(spawn.honesty) &&
    /NOT_PLAN_PASS/.test(spawn.honesty) &&
    /not OSM/i.test(spawn.honesty) &&
    spawn.gtaClaim === false &&
    onHarbor.gpsClaim === false &&
    tramSnap.gpsClaim === false;
  const geoOk = geoStreets.length === 2;
  const keptOk =
    spawn.sky === "gradient-hemisphere" &&
    spawn.blockEdge === "curb-wall-lot" &&
    spawn.fog === "distance-haze" &&
    spawn.groundFloor === "door-glass-awning" &&
    spawn.innerLane === "asphalt-walk-edge" &&
    spawn.streetPlaques >= 4 &&
    spawn.menuHidden &&
    spawn.atBound === "0";

  const ok =
    cornerDom &&
    tramStripesOk &&
    tramCurbOk &&
    harborChip &&
    tramChip &&
    miniAfter &&
    walkedOff &&
    keptZebras &&
    lanternOk &&
    leftoverOk &&
    shopClosed.shopPanel === false &&
    honestyOk &&
    geoOk &&
    keptOk &&
    onHarbor.alt === 0 &&
    tramSnap.alt === 0 &&
    tramSnap.atBound === "0";

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_TRAM_XING_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_osm: true,
    not_wan: true,
    not_gps: true,
    liveJs,
    liveLen,
    liveSha,
    cornerDom,
    tramStripesOk,
    tramCurbOk,
    keptZebras,
    harborChip,
    tramChip,
    miniAfter,
    walkedOff,
    lanternOk,
    leftoverOk,
    leftoverLast,
    leftoverLabeled,
    honestyOk,
    geoOk,
    keptOk,
    chipHarbor: onHarbor.chipText,
    chipTram: tramSnap.chipText,
    miniTram: tramSnap.minimap?.active,
    miniHl: tramSnap.minimap?.highlight,
    miniRole: tramSnap.minimap?.activeRole,
    cornerKind: spawn.cornerKind,
    crosswalks: spawn.crosswalks,
    stopLines: spawn.stopLines,
    curbReturns: spawn.curbReturns,
    tramFloor,
    tramMid,
    lookFloor,
    lookMid,
    geoStreets: geoStreets.map((row) => row.properties?.display_name ?? row.properties?.name),
    tramM: Number(tramM.toFixed(2)),
    northM: Number(northM.toFixed(2)),
    headingTram: tramSnap.heading,
    spawn,
    onHarbor,
    atLantern: atLantern.snap,
    atJoin: atJoin.snap,
    walkLog,
    onTram: tramSnap,
    look: lookSnap,
    lantern: { nearby: atLantern.snap?.nearbyShop, panel: shopOpen.shopPanelId },
    seatB: {
      nearbyShop: readyB.snap.nearbyShop,
      stallHint: readyB.snap.stallHint,
      shopRange: readyB.snap.shopRange,
      afterE: bAfterE.shopPanelId,
      panel: bAfterE.shopPanel,
      leftoverLast,
      leftoverLabeled,
      leftoverShops: leftoverRows.map((row) => row.shop),
      streetShops: menuB.snap.rows.filter((row) => row.street === "1").map((row) => row.shop),
    },
    honesty: spawn.honesty?.slice(0, 280),
    shots: { tram: SHOT_TRAM, look: SHOT_LOOK },
    hashTram: createHash("sha256").update(tramBuf).digest("hex").slice(0, 16),
    hashLook: createHash("sha256").update(lookBuf).digest("hex").slice(0, 16),
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
if (report.verdict !== "J5_TRAM_XING_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  report.verdict,
  report.run_id,
  `js=${report.liveJs}`,
  `chipHarbor=${report.chipHarbor}`,
  `chipTram=${report.chipTram}`,
  `mini=${report.miniTram}`,
  `white=${report.tramFloor?.whiteRatio}`,
  `east=${report.tramM}`,
  `lantern=${report.lantern?.panel}`,
);
