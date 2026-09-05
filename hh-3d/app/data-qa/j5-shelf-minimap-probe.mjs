/**
 * Isolated guest B on recycled 4175. After first walk the deferred
 * corner map is live. Opening a street shop (lantern E) or a leftover
 * Menu shelf must leave that widget uncovered — player-visible dots,
 * not a hidden <ol> under the sheet. Leftover Shared PC / J6 stay off
 * the 2D marks. Nearby/E, leftover banners, spawn E hold.
 * Does not catalog_clear. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-SHELF-MINIMAP-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-shelf-minimap.png");
const PORT = Number(process.env.HH_CDP_PORT_B || 9773);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-42";
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
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return {
      x: r.x, y: r.y, w: r.width, h: r.height,
      t: r.top, r: r.right, b: r.bottom, l: r.left,
      vis: style.visibility, op: Number(style.opacity),
      display: style.display,
    };
  };
  const overlap = (a, b) => {
    if (!a || !b) return 0;
    const w = Math.max(0, Math.min(a.r, b.r) - Math.max(a.l, b.l));
    const h = Math.max(0, Math.min(a.b, b.b) - Math.max(a.t, b.t));
    return Math.round(w * h);
  };
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
  const wrap = document.querySelector('[data-testid="hh-world-minimap-wrap"], .minimap-wrap');
  const mini = document.querySelector('[data-testid="hh-world-minimap"]');
  const attrib = wrap?.querySelector(".maplibregl-ctrl-attrib");
  const attribStyle = attrib ? window.getComputedStyle(attrib) : null;
  const worldMap = document.querySelector('[data-testid="hh-world-map"]');
  const friendA = document.querySelector('[data-testid="friend-row-a"]');
  const wrapBox = box(wrap);
  const panelBox = box(panel);
  const menuBox = menu && !menu.hidden ? box(menu) : null;
  const shopProof = [...document.querySelectorAll('[data-testid="hh-world-minimap-shops"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    name: el.getAttribute("data-name") ?? (el.textContent ?? "").trim(),
    draw: el.getAttribute("data-draw") ?? "",
  }));
  const shopMarks = [...document.querySelectorAll(".minimap-shop-mark")].map((el) => {
    const r = box(el);
    return {
      shop: el.getAttribute("data-shop-id") ?? "",
      name: el.getAttribute("data-name") ?? "",
      w: r?.w ?? 0,
      h: r?.h ?? 0,
      vis: r?.vis ?? "",
      op: r?.op ?? 0,
      inWrap: wrap && r ? overlap(r, wrapBox) > 0 : false,
    };
  });
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    leftover: el.getAttribute("data-leftover") ?? "",
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
  }));
  const boards = [...document.querySelectorAll('[data-testid="play-stall-boards"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    titles: el.getAttribute("data-titles") ?? el.textContent ?? "",
  }));
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
    laneM: Number(el.getAttribute("data-lane-m") ?? "NaN"),
  }));
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
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    shopLeftover: panel?.getAttribute("data-leftover") ?? "",
    shopClear: panel?.getAttribute("data-minimap-clear") ?? "",
    bannerPresent: Boolean(banner),
    leftoverCopy: /không trên phố|leftover máy này/i.test((panel?.innerText ?? "") + (banner?.textContent ?? "")),
    kind: (kind?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    streetName: chip?.getAttribute("data-street-name") ?? "",
    chipText: (chip?.textContent ?? "").trim(),
    worldMapPresent: Boolean(worldMap),
    menuOpen: menu?.getAttribute("data-open") === "yes" && menu?.hidden !== true,
    leftoverCount: Number(names?.getAttribute("data-leftover-count") ?? "0"),
    rows,
    boards,
    stalls,
    honesty: honesty?.innerText ?? "",
    minimapDefer: wrap?.getAttribute("data-minimap-defer") ?? "",
    wrapClear: wrap?.getAttribute("data-minimap-clear") ?? "",
    wrapBox,
    panelBox,
    menuBox,
    overlapPanel: overlap(wrapBox, panelBox),
    overlapMenu: overlap(wrapBox, menuBox),
    wrapVisible: Boolean(wrapBox && wrapBox.w > 80 && wrapBox.h > 80 && wrapBox.op > 0 && wrapBox.vis !== "hidden"),
    wrapAttrib: wrap?.getAttribute("data-minimap-attrib") ?? "",
    attribPresent: Boolean(attrib),
    attribDisplay: attribStyle?.display ?? "none",
    attribVisible: Boolean(
      attrib &&
        attribStyle &&
        attribStyle.display !== "none" &&
        attribStyle.visibility !== "hidden" &&
        Number(attribStyle.opacity) > 0,
    ),
    marksVisible: shopMarks.filter((row) => row.inWrap && row.w >= 6 && row.h >= 6 && row.op > 0 && row.vis !== "hidden").map((row) => row.shop),
    minimap: {
      present: Boolean(mini),
      shops: mini?.getAttribute("data-minimap-shops") ?? "",
      shopCount: Number(mini?.getAttribute("data-minimap-shop-count") ?? "0"),
      shopIds: mini?.getAttribute("data-minimap-shop-ids") ?? "",
      active: mini?.getAttribute("data-minimap-active") ?? "",
    },
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-shelf-minimap-${port}-`));
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
  const west = await turnToHeading(b.ws, nextId, 270);
  nextId = west.nextId;
  await keyHold(b.ws, nextId, "w", "KeyW", 87, 1400);
  nextId += 2;
  await sleep(80);
  for (let i = 0; i < 16; i += 1) {
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
    await keyHold(b.ws, nextId, "w", "KeyW", 87, 700);
    nextId += 2;
    await sleep(80);
    const mid = await evalExpr(b.ws, nextId, SNAP);
    nextId += 1;
    atLantern = { snap: mid, nextId };
    if (mid.nearbyShop === LANTERN) {
      break;
    }
    if (i === 7 && mid.nearbyShop !== LANTERN) {
      const sidewalk = await turnToHeading(b.ws, nextId, 270);
      nextId = sidewalk.nextId;
      await keyHold(b.ws, nextId, "w", "KeyW", 87, 900);
      nextId += 2;
      await sleep(80);
    }
  }
  if (atLantern.snap.nearbyShop !== LANTERN) {
    const waited = await waitSnap(b.ws, nextId, (s) => s.nearbyShop === LANTERN, 10, 220);
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

  const shot = await cdp(b.ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));

  const js = await liveJsInfo();
  const leftoverOnMap = (liveMini.shopProof || []).filter((row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop));
  const leftoverMarks = (liveMini.shopMarks || []).filter((row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop));
  const kemDrawn = (liveMini.boards || []).some((row) => row.shop === KEM && row.draw === "1");
  const streetWanted = [LANTERN, PHO, CHE].concat(kemDrawn ? [KEM] : []);
  const lanternClear =
    Boolean(lanternOpen.shopPanel) &&
    lanternOpen.shopPanelId === LANTERN &&
    lanternOpen.shopLeftover !== "1" &&
    lanternOpen.shopClear === "1" &&
    lanternOpen.wrapClear === "1" &&
    lanternOpen.wrapVisible === true &&
    lanternOpen.overlapPanel === 0 &&
    lanternOpen.minimap?.present === true &&
    lanternOpen.attribVisible !== true &&
    lanternOpen.wrapAttrib === "caption";
  const leftoverClear =
    leftoverPanel &&
    leftoverPanel.shopLeftover === "1" &&
    leftoverPanel.bannerPresent === true &&
    leftoverPanel.leftoverCopy === true &&
    leftoverPanel.shopClear === "1" &&
    leftoverPanel.wrapVisible === true &&
    leftoverPanel.overlapPanel === 0;
  const marksHoldOpen =
    streetWanted.every((id) => (lanternOpen.marksVisible || []).includes(id)) ||
    streetWanted.every((id) => (lanternOpen.shopMarks || []).some((row) => row.shop === id && row.inWrap));
  const leftoverMenuOk =
    (menuSnap.leftoverCount || 0) >= 1 &&
    (menuSnap.rows || []).some((row) => LEFTOVER_IDS.has(row.shop) && row.leftover === "1" && row.labeled);
  const spawnEStolen =
    Boolean(spawnE.shopPanel) && (LEFTOVER.test(spawnE.shopPanelId || "") || LEFTOVER_IDS.has(spawnE.shopPanelId));
  const deferLive =
    liveMini.minimapDefer === "live" &&
    liveMini.minimap?.present === true;
  const guestOk =
    /guest/i.test(liveMini.identity || spawn.identity || "") &&
    liveMini.identitySigned !== "yes";
  const ok =
    guestOk &&
    deferLive &&
    leftoverOnMap.length === 0 &&
    leftoverMarks.length === 0 &&
    !spawnEStolen &&
    leftoverMenuOk &&
    leftoverClear &&
    lanternClear &&
    marksHoldOpen &&
    liveMini.worldMapPresent === false;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_SHELF_MINIMAP_OK" : "J5_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
    reminted: true,
    liveJs: js.path,
    liveJsLen: js.len,
    liveJsSha256: js.sha256,
    guestOk,
    deferLive,
    leftoverOnMap: leftoverOnMap.map((row) => row.shop),
    leftoverMarks: leftoverMarks.map((row) => row.shop || row.name),
    leftoverMenuOk,
    leftoverClear: Boolean(leftoverClear),
    leftoverOverlap: leftoverPanel?.overlapPanel ?? null,
    leftoverWrap: leftoverPanel?.wrapBox ?? null,
    leftoverPanelBox: leftoverPanel?.panelBox ?? null,
    lanternClear: Boolean(lanternClear),
    lanternOverlap: lanternOpen.overlapPanel ?? null,
    lanternWrap: lanternOpen.wrapBox ?? null,
    lanternPanelBox: lanternOpen.panelBox ?? null,
    lanternMarks: lanternOpen.marksVisible ?? [],
    lanternAttribVisible: lanternOpen.attribVisible ?? null,
    lanternAttrib: lanternOpen.wrapAttrib ?? "",
    marksHoldOpen,
    streetWanted,
    spawnEStolen,
    lanternOk: lanternOpen.shopPanelId === LANTERN,
    lanternNearby: atLantern.snap.nearbyShop,
    lanternRange: atLantern.snap.shopRange,
    leftoverBanner: leftoverPanel?.kind ?? "",
    honestyDenies: /not a digital twin|not osm|not a live/i.test(liveMini.honesty || lanternOpen.honesty || ""),
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
        `lanternOverlap=${lanternOpen.overlapPanel}`,
        `leftoverOverlap=${leftoverPanel?.overlapPanel}`,
        `marks=${(lanternOpen.marksVisible || []).join(",")}`,
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
