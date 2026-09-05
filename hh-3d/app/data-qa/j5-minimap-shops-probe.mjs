/**
 * Isolated guest B on recycled 4175. After first walk so the deferred
 * corner minimap is live, DOM/proof must list street-play published
 * shops (lantern, drawn Phở, Chè, Kem if drawn) at the sidewalk plant.
 * Leftover Shared PC / J6 stay off the 2D marks. Chip still agrees.
 * Nearby/E, chalkboards, leftover Menu + panel banners still hold.
 * Spawn E not stolen. Does not catalog_clear. NOT_PLAN_PASS.
 */
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J5-MINIMAP-SHOPS-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-minimap-shops.png");
const PORT = Number(process.env.HH_CDP_PORT_B || 9771);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-41";
const CHE = "shop-local-mtmrbdjffjdkg8";
const KEM = "shop-local-mtmrq33hoq4phb";
const PHO = "shop-local-mtmh45qxehxhvb";
const LANTERN = "shop-lantern-fish";
const LANTERN_POS = { lon: 106.6980366, lat: 10.7718712 };
const ORIGIN = { lon: 106.698, lat: 10.7725 };
const SHARED = "shop-local-sharedpc";
const J6 = "shop-local-mtl8ulddihjpre";
const LEFTOVER_IDS = new Set([SHARED, J6]);
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const LEFTOVER_COPY = /không trên phố|leftover máy này/i;
const M_PER_DEG_LAT = 111320;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

function plantLngLat(x, z) {
  return {
    lon: ORIGIN.lon + x / metersPerDegLon(ORIGIN.lat),
    lat: ORIGIN.lat + z / M_PER_DEG_LAT,
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

async function keyDown(ws, id, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
}

async function keyUp(ws, id, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
}

async function keyHold(ws, id, key, code, vk, ms) {
  await keyDown(ws, id, key, code, vk);
  await sleep(ms);
  await keyUp(ws, id + 1, key, code, vk);
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
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const names = document.querySelector('[data-testid="public-shop-names"]');
  const wrap = document.querySelector(".minimap-wrap");
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const worldMap = document.querySelector('[data-testid="hh-world-map"]');
  const friendA = document.querySelector('[data-testid="friend-row-a"]');
  const miniItems = [...document.querySelectorAll('[data-testid="hh-world-minimap-lanes"] li')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    name: el.getAttribute("data-name") ?? el.textContent ?? "",
    role: el.getAttribute("data-role") ?? "",
    active: el.getAttribute("data-active") ?? "",
  }));
  const shopProof = [...document.querySelectorAll('[data-testid="hh-world-minimap-shops"] li')].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    shop: el.getAttribute("data-shop-id") ?? "",
    name: el.getAttribute("data-name") ?? (el.textContent ?? "").trim(),
    draw: el.getAttribute("data-draw") ?? "",
    keepOut: el.getAttribute("data-keep-out") ?? "",
    lon: el.getAttribute("data-lon") ?? "",
    lat: el.getAttribute("data-lat") ?? "",
    persistLon: el.getAttribute("data-persist-lon") ?? "",
    persistLat: el.getAttribute("data-persist-lat") ?? "",
    kind: el.getAttribute("data-kind") ?? "",
  }));
  const shopMarks = [...document.querySelectorAll(".minimap-shop-mark")].map((el) => ({
    id: el.getAttribute("data-testid") ?? "",
    shop: el.getAttribute("data-shop-id") ?? "",
    name: el.getAttribute("data-name") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    keepOut: el.getAttribute("data-keep-out") ?? "",
    lon: el.getAttribute("data-lon") ?? "",
    lat: el.getAttribute("data-lat") ?? "",
  }));
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    leftover: el.getAttribute("data-leftover") ?? "",
    street: el.getAttribute("data-street") ?? "",
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
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
    persistLon: Number(el.getAttribute("data-lon") ?? "NaN"),
    persistLat: Number(el.getAttribute("data-lat") ?? "NaN"),
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
    laneM: Number(el.getAttribute("data-lane-m") ?? "NaN"),
  }));
  const leftoverDrawn = stalls.filter((row) => /sharedpc|mtl8ulddihjpre|j6/i.test(row.shop) && row.draw === "1").map((row) => row.shop);
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    pose: avatar?.getAttribute("data-pose") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    friendA: friendA?.getAttribute("data-status") ?? friendA?.textContent ?? "none",
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    shopLeftover: panel?.getAttribute("data-leftover") ?? "",
    shopStreet: panel?.getAttribute("data-street") ?? "",
    bannerPresent: Boolean(banner),
    banner: (banner?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    kind: (kind?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    leftoverCopy: /không trên phố|leftover máy này/i.test((panel?.innerText ?? "") + (banner?.textContent ?? "")),
    streetName:
      chip?.getAttribute("data-street-name") ??
      play?.getAttribute("data-street-name") ??
      "",
    chipText: (chip?.textContent ?? "").trim(),
    worldMapPresent: Boolean(worldMap),
    menuOpen: menu?.getAttribute("data-open") === "yes" && menu?.hidden !== true,
    leftoverCount: Number(names?.getAttribute("data-leftover-count") ?? "0"),
    rows,
    boards,
    leftoverDrawn,
    stalls,
    honesty: honesty?.innerText ?? "",
    minimapDefer: wrap?.getAttribute("data-minimap-defer") ?? "",
    minimapDeferKind: wrap?.getAttribute("data-minimap-defer-kind") ?? "",
    minimap: {
      present: Boolean(mini),
      kind: mini?.getAttribute("data-minimap-lanes") ?? "",
      shops: mini?.getAttribute("data-minimap-shops") ?? "",
      shopCount: Number(mini?.getAttribute("data-minimap-shop-count") ?? "0"),
      shopIds: mini?.getAttribute("data-minimap-shop-ids") ?? "",
      official: Number(mini?.getAttribute("data-minimap-official") ?? "0"),
      inner: Number(mini?.getAttribute("data-minimap-inner") ?? "0"),
      names: mini?.getAttribute("data-minimap-names") ?? "",
      active: mini?.getAttribute("data-minimap-active") ?? "",
      highlight: mini?.getAttribute("data-minimap-highlight") ?? "",
      activeRole: mini?.getAttribute("data-minimap-active-role") ?? "",
    },
    miniItems,
    shopProof,
    shopMarks,
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-minimap-shops-${port}-`));
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

async function liveJsInfo() {
  const html = await fetch(PLAYER).then((res) => res.text());
  const path = /\/assets\/index-[^"']+\.js/.exec(html)?.[0] ?? "";
  if (!path) {
    return { path: "", len: 0, sha256: "" };
  }
  const buf = Buffer.from(await fetch(new URL(path, PLAYER)).then((res) => res.arrayBuffer()));
  return {
    path,
    len: buf.length,
    sha256: createHash("sha256").update(buf).digest("hex"),
  };
}

async function busGet() {
  const res = await fetch(new URL("/demo-bus", PLAYER));
  return res.json();
}

function hasShop(list, id) {
  return (list || []).some((row) => row.shop === id || row.id === `minimap-shop-${id}`);
}

function wrapHeading(heading) {
  return ((Number(heading) % 360) + 360) % 360;
}

function headingTo(from, to) {
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

async function turnToHeading(ws, startId, targetHeading) {
  let id = startId;
  for (let i = 0; i < 10; i += 1) {
    const snap = await evalExpr(ws, id, SNAP);
    id += 1;
    if (facingToward(snap.heading, targetHeading)) {
      return { snap, nextId: id };
    }
    await evalExpr(
      ws,
      id,
      `(() => {
        document.activeElement && document.activeElement.blur && document.activeElement.blur();
        document.body.click();
        return true;
      })()`,
    );
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

const chrome = launchChrome(PORT, `${PLAYER}?seat=b`);
let report;
try {
  const b = await connectPage(PORT);
  await cdp(b.ws, 1, "Runtime.enable");
  await cdp(b.ws, 2, "Page.enable");
  await cdp(b.ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });

  const ready = await waitSnap(
    b.ws,
    10,
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    40,
    250,
  );
  const spawn = ready.snap;
  let nextId = ready.nextId;

  await evalExpr(
    b.ws,
    nextId,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
      if (canvas instanceof HTMLElement) {
        canvas.focus();
        canvas.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 }));
      }
      document.body.click();
      return true;
    })()`,
  );
  nextId += 1;
  await sleep(220);
  const beforeWalk = await evalExpr(b.ws, nextId, SNAP);
  nextId += 1;

  await keyHold(b.ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  await sleep(280);
  const spawnE = await evalExpr(b.ws, nextId, SNAP);
  nextId += 1;
  if (spawnE.shopPanel) {
    await evalExpr(b.ws, nextId, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
    nextId += 1;
    await sleep(160);
  }

  await keyHold(b.ws, nextId, "w", "KeyW", 87, 1600);
  nextId += 2;
  await sleep(220);
  const afterFirstW = await evalExpr(b.ws, nextId, SNAP);
  nextId += 1;

  const miniReady = await waitSnap(
    b.ws,
    nextId,
    (s) => s.minimap?.present === true && (s.minimapDefer === "" || s.minimapDefer === "live"),
    36,
    200,
  );
  nextId = miniReady.nextId;
  const liveMini = miniReady.snap;

  const shot = await cdp(b.ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));

  await evalExpr(
    b.ws,
    nextId,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  nextId += 1;
  await sleep(80);
  await keyHold(b.ws, nextId, "Tab", "Tab", 9, 80);
  nextId += 2;
  const menuOpen = await waitSnap(b.ws, nextId, (s) => s.menuOpen === true, 20, 180);
  nextId = menuOpen.nextId;
  const menuSnap = menuOpen.snap;

  const leftoverRow = (menuSnap.rows || []).find((row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop));
  let leftoverPanel = null;
  if (leftoverRow?.shop) {
    const clicked = await evalExpr(
      b.ws,
      nextId,
      `(() => {
        const btn = document.querySelector('[data-testid="open-shop-${leftoverRow.shop}"]');
        if (!btn) return { ok: false };
        btn.click();
        return { ok: true, shop: "${leftoverRow.shop}" };
      })()`,
    );
    nextId += 1;
    if (clicked?.ok) {
      const opened = await waitSnap(
        b.ws,
        nextId,
        (s) => s.shopPanel === true && s.shopPanelId === leftoverRow.shop,
        24,
        160,
      );
      nextId = opened.nextId;
      leftoverPanel = opened.snap;
      await evalExpr(b.ws, nextId, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
      nextId += 1;
      await sleep(160);
    }
  }

  await evalExpr(b.ws, nextId, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  nextId += 1;
  await sleep(120);
  await keyHold(b.ws, nextId, "Escape", "Escape", 27, 80);
  nextId += 2;
  await sleep(120);
  await evalExpr(
    b.ws,
    nextId,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      const canvas = document.querySelector("canvas.play-canvas, [data-testid='play-canvas']");
      if (canvas instanceof HTMLElement) {
        canvas.focus();
        canvas.click();
      } else {
        document.body.click();
      }
      return true;
    })()`,
  );
  nextId += 1;
  await sleep(80);
  const north = await turnToHeading(b.ws, nextId, 0);
  nextId = north.nextId;
  await keyHold(b.ws, nextId, "w", "KeyW", 87, 16000);
  nextId += 2;
  await sleep(80);
  const afterNorth = await evalExpr(b.ws, nextId, SNAP);
  nextId += 1;
  const lanternStall = (afterNorth.stalls || []).find((row) => row.shop === LANTERN);
  const lanternPlant =
    lanternStall && Number.isFinite(lanternStall.x) && Number.isFinite(lanternStall.z)
      ? plantLngLat(lanternStall.x, lanternStall.z)
      : LANTERN_POS;
  let atLantern = { snap: afterNorth, nextId };
  for (let i = 0; i < 12; i += 1) {
    const now = await evalExpr(b.ws, nextId, SNAP);
    nextId += 1;
    if (now.nearbyShop === LANTERN) {
      atLantern = { snap: now, nextId };
      break;
    }
    const bear = headingTo(now, lanternPlant);
    if (!facingToward(now.heading, bear, 14)) {
      const turned = await turnToHeading(b.ws, nextId, bear);
      nextId = turned.nextId;
    }
    await keyHold(b.ws, nextId, "w", "KeyW", 87, 900);
    nextId += 2;
    await sleep(80);
    const mid = await evalExpr(b.ws, nextId, SNAP);
    nextId += 1;
    atLantern = { snap: mid, nextId };
    if (mid.nearbyShop === LANTERN) {
      break;
    }
  }
  if (atLantern.snap.nearbyShop !== LANTERN) {
    const waited = await waitSnap(b.ws, nextId, (s) => s.nearbyShop === LANTERN, 8, 220);
    nextId = waited.nextId;
    atLantern = waited;
  }
  let lanternOpen = atLantern.snap;
  if (atLantern.snap.nearbyShop === LANTERN) {
    await keyHold(b.ws, nextId, "e", "KeyE", 69, 180);
    nextId += 2;
    const opened = await waitSnap(
      b.ws,
      nextId,
      (s) => s.shopPanel === true && s.shopPanelId === LANTERN,
      24,
      180,
    );
    nextId = opened.nextId;
    lanternOpen = opened.snap;
  }
  if (lanternOpen.shopPanel) {
    await evalExpr(b.ws, nextId, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
    nextId += 1;
  }

  const js = await liveJsInfo();
  const bus = await busGet();
  const busShops = (bus?.catalog?.shops ?? []).map((row) => ({
    shop_id: row.shop_id,
    name: row.name,
    lon: row.lon,
    lat: row.lat,
    status: row.status,
  }));
  const drawnIds = new Set(
    (liveMini.stalls || liveMini.boards || [])
      .filter((row) => row.draw === "1")
      .map((row) => row.shop),
  );
  const boardIds = new Set((liveMini.boards || []).filter((row) => row.draw === "1").map((row) => row.shop));
  const proofIds = (liveMini.shopProof || []).map((row) => row.shop);
  const markIds = (liveMini.shopMarks || []).map((row) => row.shop);
  const leftoverOnMap = proofIds.filter((id) => LEFTOVER_IDS.has(id) || LEFTOVER.test(id));
  const leftoverMarks = markIds.filter((id) => LEFTOVER_IDS.has(id) || LEFTOVER.test(id));
  const kemDrawn = (liveMini.boards || []).some((row) => row.shop === KEM && row.draw === "1");
  const streetWanted = [LANTERN, PHO, CHE].concat(kemDrawn ? [KEM] : []);
  const streetOnProof = streetWanted.every((id) => hasShop(liveMini.shopProof, id));
  const streetOnMarks = streetWanted.every((id) => hasShop(liveMini.shopMarks, id));
  const deferPendingFirst =
    beforeWalk.minimapDefer === "pending" ||
    afterFirstW.minimapDefer === "pending" ||
    (beforeWalk.minimap?.present === false && liveMini.minimap?.present === true);
  const deferLive =
    liveMini.minimapDefer === "live" &&
    liveMini.minimap?.present === true &&
    liveMini.minimap?.shops === "street-play-plant" &&
    liveMini.minimapDeferKind === "play-idle-or-first-w";
  const deferOk = deferLive && (deferPendingFirst || liveMini.minimapDeferKind === "play-idle-or-first-w");
  const chipAgree =
    (liveMini.chipText === liveMini.minimap?.active || liveMini.streetName === liveMini.minimap?.active) &&
    Boolean(liveMini.minimap?.active);
  const spawnEStolen =
    Boolean(spawnE.shopPanel) && (LEFTOVER.test(spawnE.shopPanelId || "") || LEFTOVER_IDS.has(spawnE.shopPanelId));
  const lanternOk =
    Boolean(lanternOpen.shopPanel) && lanternOpen.shopPanelId === LANTERN && lanternOpen.shopLeftover !== "1";
  const leftoverMenuOk =
    (menuSnap.leftoverCount || 0) >= 1 &&
    (menuSnap.rows || []).some((row) => LEFTOVER_IDS.has(row.shop) && row.leftover === "1" && row.labeled);
  const leftoverBannerOk =
    leftoverPanel &&
    leftoverPanel.shopLeftover === "1" &&
    leftoverPanel.bannerPresent === true &&
    leftoverPanel.leftoverCopy === true;
  const leftoverDrawOk = (liveMini.leftoverDrawn || []).length === 0;
  const boardsHold =
    (liveMini.boards || []).some((row) => row.shop === LANTERN && row.draw === "1") &&
    (liveMini.boards || []).some((row) => row.shop === PHO && row.draw === "1") &&
    (liveMini.boards || []).some((row) => row.shop === CHE && row.draw === "1");
  const guestOk =
    /guest/i.test(liveMini.identity || spawn.identity || "") &&
    liveMini.identitySigned !== "yes" &&
    (liveMini.friendA === "none" || !liveMini.friendA || /none|—/.test(liveMini.friendA));
  const eastM = (liveMini.lon - spawn.lon) * metersPerDegLon((liveMini.lat + spawn.lat) / 2);
  const northM = (liveMini.lat - spawn.lat) * M_PER_DEG_LAT;
  const ok =
    guestOk &&
    deferOk &&
    streetOnProof &&
    streetOnMarks &&
    leftoverOnMap.length === 0 &&
    leftoverMarks.length === 0 &&
    leftoverDrawOk &&
    chipAgree &&
    !spawnEStolen &&
    lanternOk &&
    leftoverMenuOk &&
    leftoverBannerOk &&
    boardsHold &&
    liveMini.worldMapPresent === false;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_MINIMAP_SHOPS_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
    not_osm: true,
    reminted: true,
    liveJs: js.path,
    liveJsLen: js.len,
    liveJsSha256: js.sha256,
    guestOk,
    deferOk,
    deferPendingFirst,
    deferLive,
    deferKind: liveMini.minimapDeferKind || beforeWalk.minimapDeferKind || "",
    beforeWalk: {
      defer: beforeWalk.minimapDefer,
      mini: beforeWalk.minimap?.present ?? false,
      chip: beforeWalk.chipText,
    },
    afterFirstW: {
      defer: afterFirstW.minimapDefer,
      mini: afterFirstW.minimap?.present ?? false,
      chip: afterFirstW.chipText,
      lon: afterFirstW.lon,
      lat: afterFirstW.lat,
    },
    liveMini: {
      defer: liveMini.minimapDefer,
      chip: liveMini.chipText,
      active: liveMini.minimap?.active,
      highlight: liveMini.minimap?.highlight,
      shops: liveMini.minimap?.shops,
      shopCount: liveMini.minimap?.shopCount,
      shopIds: liveMini.minimap?.shopIds,
    },
    streetWanted,
    proofIds,
    markIds,
    leftoverOnMap,
    leftoverMarks,
    kemDrawn,
    streetOnProof,
    streetOnMarks,
    chipAgree,
    spawnEStolen,
    spawnNearby: spawnE.nearbyShop,
    lanternOk,
    lanternPanel: lanternOpen.shopPanelId,
    lanternNearby: atLantern.snap.nearbyShop,
    lanternRange: atLantern.snap.shopRange,
    lanternLon: atLantern.snap.lon,
    lanternLat: atLantern.snap.lat,
    lanternHeading: atLantern.snap.heading,
    lanternChip: atLantern.snap.chipText,
    lanternPlant,
    lanternStallLaneM: lanternStall?.laneM ?? null,
    leftoverMenuOk,
    leftoverBannerOk,
    leftoverDrawOk,
    leftoverPanelId: leftoverPanel?.shopPanelId ?? "",
    leftoverBanner: leftoverPanel?.banner ?? "",
    boardsHold,
    boardShops: (liveMini.boards || []).map((row) => ({ shop: row.shop, draw: row.draw, titles: row.titles })),
    busShops,
    drawnIds: [...drawnIds],
    boardIds: [...boardIds],
    eastM: Number(eastM.toFixed(2)),
    northM: Number(northM.toFixed(2)),
    spawn,
    shot: SHOT,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    console.error(JSON.stringify(report, null, 2));
    process.exitCode = 1;
  } else {
    console.log(
      [
        report.verdict,
        js.path,
        `shops=${proofIds.join(",")}`,
        `leftover=${leftoverOnMap.length}`,
        `chip=${liveMini.chipText}/${liveMini.minimap?.active}`,
        `defer=${beforeWalk.minimapDefer}->${liveMini.minimapDefer}`,
      ].join(" "),
    );
  }
} catch (err) {
  writeFileSync(
    OUT,
    `${JSON.stringify({ run_id: RUN_ID, verdict: "J5_REWORK", error: String(err) }, null, 2)}\n`,
  );
  console.error(err);
  process.exitCode = 1;
} finally {
  chrome.kill();
}
