/**
 * Isolated guest B leftover shop panel on recycled 4175.
 * Menu leftover Shared PC / J6 must open a leftover banner, not
 * "public shop · opened on this machine". Lantern + drawn Phở stay
 * street/public copy. Nearby / spawn E not stolen. Street E at
 * lantern still opens shop-lantern-fish. Menu leftover list last.
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
const OUT = join(import.meta.dirname, "J5-LEFTOVER-PANEL-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT_B || 9696);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-31";
const LEFTOVER_IDS = new Set(["shop-local-sharedpc", "shop-local-mtl8ulddihjpre"]);
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAYER_SHOP = "shop-local-mtmh45qxehxhvb";
const LANTERN = "shop-lantern-fish";
const LANTERN_POS = { lon: 106.6980366, lat: 10.7718712 };
const SHARED = "shop-local-sharedpc";
const J6 = "shop-local-mtl8ulddihjpre";
const M_PER_DEG_LAT = 111320;
const LEFTOVER_COPY = /không trên phố|leftover máy này/i;
const STREET_LOCAL = /public shop · opened on this machine/i;
const STREET_AUTHORED = /public shop · authored example among many/i;

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

async function evalLoad(ws, id, expression, awaitPromise = false) {
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
  const mode = document.querySelector('[data-testid="mode-status"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const names = document.querySelector('[data-testid="public-shop-names"]');
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    name: (el.querySelector(".menu-shop-name")?.textContent ?? el.textContent ?? "").trim().split("\\n")[0],
    leftover: el.getAttribute("data-leftover") ?? "",
    street: el.getAttribute("data-street") ?? "",
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
  }));
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    name: el.getAttribute("data-name") ?? "",
  }));
  const panelText = (panel?.innerText ?? "").replace(/\\s+/g, " ").trim();
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    shopLeftover: panel?.getAttribute("data-leftover") ?? "",
    shopStreet: panel?.getAttribute("data-street") ?? "",
    shopKeepOut: panel?.getAttribute("data-keep-out") ?? "",
    shopClass: panel?.className ?? "",
    banner: (banner?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    bannerPresent: Boolean(banner),
    kind: (kind?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    panelText,
    leftoverCopy: /không trên phố|leftover máy này/i.test(panelText),
    streetLocalCopy: /public shop · opened on this machine/i.test(panelText),
    streetAuthoredCopy: /public shop · authored example among many/i.test(panelText),
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    mode: (mode?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    menuOpen: menu?.getAttribute("data-open") === "yes" && menu?.hidden !== true,
    listCount: Number(names?.getAttribute("data-count") ?? "0"),
    leftoverCount: Number(names?.getAttribute("data-leftover-count") ?? "0"),
    rows,
    leftoverDrawn: stalls.filter((row) => /sharedpc|mtl8ulddihjpre/i.test(row.shop) && row.draw === "1").map((row) => row.shop),
    honesty: honesty?.innerText ?? "",
    deniesGta: /no gta|not a digital twin|not 1:1/i.test(honesty?.innerText ?? ""),
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-leftover-panel-${port}-`));
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
    last = await evalLoad(ws, id, SNAP);
    id += 1;
    if (pred(last)) {
      return { snap: last, nextId: id };
    }
    await sleep(delay);
  }
  return { snap: last, nextId: id };
}

async function busGet() {
  const res = await fetch(new URL("/demo-bus", PLAYER));
  return res.json();
}

async function ensureMenu(ws, nextId) {
  const now = await evalLoad(ws, nextId, SNAP);
  nextId += 1;
  if (now.menuOpen) {
    return { snap: now, nextId };
  }
  await evalLoad(
    ws,
    nextId,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  nextId += 1;
  await sleep(80);
  await keyHold(ws, nextId, "Tab", "Tab", 9, 80);
  nextId += 2;
  return waitSnap(ws, nextId, (s) => s.menuOpen === true, 24, 200);
}

async function openMenuShop(ws, nextId, shopId) {
  const menu = await ensureMenu(ws, nextId);
  nextId = menu.nextId;
  const clicked = await evalLoad(
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

function wrapHeading(heading) {
  return ((Number(heading) % 360) + 360) % 360;
}

function facingNorth(heading) {
  const h = wrapHeading(heading);
  return h <= 28 || h >= 332;
}

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
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

async function blurCanvas(ws, id) {
  return evalLoad(
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
    const snap = await evalLoad(ws, id, SNAP);
    id += 1;
    if (facingToward(snap.heading, targetHeading)) {
      return { snap, nextId: id };
    }
    await blurCanvas(ws, id);
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
  const snap = await evalLoad(ws, id, SNAP);
  return { snap, nextId: id + 1 };
}

async function turnToNorth(ws, startId) {
  return turnToHeading(ws, startId, 0);
}

async function closeShop(ws, nextId) {
  const closed = await evalLoad(
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
  const gone = await waitSnap(ws, nextId, (s) => s.shopPanel === false, 20, 150);
  return gone.nextId;
}

function leftoverPanelOk(snap, shopId) {
  return (
    snap.shopPanelId === shopId &&
    snap.shopLeftover === "1" &&
    snap.shopStreet === "0" &&
    snap.shopKeepOut === "1" &&
    snap.bannerPresent === true &&
    LEFTOVER_COPY.test(snap.banner) &&
    LEFTOVER_COPY.test(snap.kind) &&
    snap.leftoverCopy === true &&
    snap.streetLocalCopy === false &&
    snap.streetAuthoredCopy === false
  );
}

function streetPanelOk(snap, shopId, authored) {
  return (
    snap.shopPanelId === shopId &&
    snap.shopLeftover === "0" &&
    snap.shopStreet === "1" &&
    snap.shopKeepOut === "0" &&
    snap.bannerPresent === false &&
    snap.leftoverCopy === false &&
    (authored ? snap.streetAuthoredCopy && STREET_AUTHORED.test(snap.kind) : snap.streetLocalCopy && STREET_LOCAL.test(snap.kind))
  );
}

const chrome = launchChrome(PORT);
let report;
try {
  const bus = await busGet();
  const busShops = Array.isArray(bus?.catalog?.shops) ? bus.catalog.shops : [];

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
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20,
    48,
    250,
  );
  let nextId = ready.nextId;
  const spawn = ready.snap;

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

  const sharedOpen = await openMenuShop(ws, nextId, SHARED);
  nextId = sharedOpen.nextId;
  const sharedPanel = sharedOpen.snap;
  const list = sharedOpen.list.rows?.length ? sharedOpen.list : sharedPanel;
  nextId = await closeShop(ws, nextId);

  const j6Open = await openMenuShop(ws, nextId, J6);
  nextId = j6Open.nextId;
  const j6Panel = j6Open.snap;
  nextId = await closeShop(ws, nextId);

  const lanternMenu = await openMenuShop(ws, nextId, LANTERN);
  nextId = lanternMenu.nextId;
  const lanternPanel = lanternMenu.snap;
  nextId = await closeShop(ws, nextId);

  const phoMenu = await openMenuShop(ws, nextId, PLAYER_SHOP);
  nextId = phoMenu.nextId;
  const phoPanel = phoMenu.snap;
  nextId = await closeShop(ws, nextId);

  const leftoverRows = (list.rows || sharedPanel.rows || []).filter(
    (row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop) || LEFTOVER.test(row.name),
  );
  const leftoverLast =
    leftoverRows.length === 0 ||
    (list.rows || sharedPanel.rows)
      .slice((list.rows || sharedPanel.rows).length - leftoverRows.length)
      .every((row) => row.leftover === "1");
  const unlabeledLeftover = leftoverRows.filter((row) => row.leftover !== "1" || row.street === "1" || !row.labeled);

  await blurCanvas(ws, nextId);
  nextId += 1;
  await sleep(80);
  const menuNow = await evalLoad(ws, nextId, SNAP);
  nextId += 1;
  if (menuNow.menuOpen) {
    await keyHold(ws, nextId, "Escape", "Escape", 27, 80);
    nextId += 2;
    await sleep(120);
  }
  await blurCanvas(ws, nextId);
  nextId += 1;
  await keyHold(ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  await sleep(280);
  const spawnE = await evalLoad(ws, nextId, SNAP);
  nextId += 1;
  if (spawnE.shopPanel) {
    nextId = await closeShop(ws, nextId);
  }

  await blurCanvas(ws, nextId);
  nextId += 1;
  const west = await turnToHeading(ws, nextId, 270);
  nextId = west.nextId;
  await keyHold(ws, nextId, "w", "KeyW", 87, 7000);
  nextId += 2;
  await sleep(80);
  const north = await turnToHeading(ws, nextId, 0);
  nextId = north.nextId;
  await keyHold(ws, nextId, "w", "KeyW", 87, 16000);
  nextId += 2;
  await sleep(80);
  let atLantern = { snap: north.snap, nextId };
  for (let i = 0; i < 10; i += 1) {
    const now = await evalLoad(ws, nextId, SNAP);
    nextId += 1;
    if (now.nearbyShop === LANTERN) {
      atLantern = { snap: now, nextId };
      break;
    }
    const bear = headingTo(now, LANTERN_POS);
    if (!facingToward(now.heading, bear, 14)) {
      const turned = await turnToHeading(ws, nextId, bear);
      nextId = turned.nextId;
    }
    await keyHold(ws, nextId, "w", "KeyW", 87, 1200);
    nextId += 2;
    await sleep(80);
    const mid = await evalLoad(ws, nextId, SNAP);
    nextId += 1;
    atLantern = { snap: mid, nextId };
    if (mid.nearbyShop === LANTERN) {
      break;
    }
  }
  if (atLantern.snap.nearbyShop !== LANTERN) {
    const waited = await waitSnap(ws, nextId, (s) => s.nearbyShop === LANTERN, 8, 220);
    nextId = waited.nextId;
    atLantern = waited;
  }
  let streetE = { snap: atLantern.snap, nextId };
  if (atLantern.snap.nearbyShop === LANTERN) {
    await keyHold(ws, nextId, "e", "KeyE", 69, 180);
    nextId += 2;
    streetE = await waitSnap(
      ws,
      nextId,
      (s) => s.shopPanel === true && s.shopPanelId === LANTERN,
      24,
      180,
    );
    nextId = streetE.nextId;
  }

  const leftoverPersist = busShops
    .filter((row) => LEFTOVER_IDS.has(row.shop_id))
    .map((row) => ({ shop: row.shop_id, name: row.name, lon: row.lon, lat: row.lat, status: row.status }));
  const leftoverKeep =
    leftoverPersist.some((row) => row.shop === SHARED) && leftoverPersist.some((row) => row.shop === J6);

  const guestOk =
    (spawn.identitySigned === "no" || /guest/i.test(spawn.identity || "")) &&
    /offline/i.test(spawn.mode || sharedPanel.mode || "");
  const leftoverOk = leftoverPanelOk(sharedPanel, SHARED) && leftoverPanelOk(j6Panel, J6);
  const streetOk = streetPanelOk(lanternPanel, LANTERN, true) && streetPanelOk(phoPanel, PLAYER_SHOP, false);
  const streetEOk =
    streetE.snap.nearbyShop === LANTERN &&
    streetPanelOk(streetE.snap, LANTERN, true);
  const nearbyOk =
    !LEFTOVER.test(spawn.nearbyShop || "") &&
    !LEFTOVER.test(spawnE.nearbyShop || "") &&
    (spawn.leftoverDrawn || []).length === 0 &&
    !spawnE.shopPanel &&
    !LEFTOVER.test(spawnE.shopPanelId || "");
  const listOk = leftoverKeep && leftoverRows.length >= 2 && unlabeledLeftover.length === 0 && leftoverLast;
  const ok =
    guestOk &&
    leftoverOk &&
    streetOk &&
    streetEOk &&
    nearbyOk &&
    listOk &&
    leftoverKeep &&
    spawn.deniesGta;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_LEFTOVER_PANEL_OK" : "J5_LEFTOVER_PANEL_FAIL",
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
    liveJs,
    liveLen,
    liveSha,
    guestOk,
    leftoverOk,
    streetOk,
    streetEOk,
    nearbyOk,
    listOk,
    leftoverLast,
    leftoverKeep,
    unlabeledLeftover,
    leftoverRows,
    nearbySpawn: spawn.nearbyShop,
    nearbySpawnE: spawnE.nearbyShop,
    shopSpawnE: spawnE.shopPanelId,
    nearbyLantern: atLantern.snap.nearbyShop,
    leftoverDrawn: spawn.leftoverDrawn,
    leftoverPersist,
    identity: spawn.identity,
    mode: spawn.mode || sharedPanel.mode,
    shared: {
      id: sharedPanel.shopPanelId,
      leftover: sharedPanel.shopLeftover,
      street: sharedPanel.shopStreet,
      banner: sharedPanel.banner,
      kind: sharedPanel.kind,
      leftoverCopy: sharedPanel.leftoverCopy,
      streetLocalCopy: sharedPanel.streetLocalCopy,
    },
    j6: {
      id: j6Panel.shopPanelId,
      leftover: j6Panel.shopLeftover,
      street: j6Panel.shopStreet,
      banner: j6Panel.banner,
      kind: j6Panel.kind,
      leftoverCopy: j6Panel.leftoverCopy,
      streetLocalCopy: j6Panel.streetLocalCopy,
    },
    lantern: {
      id: lanternPanel.shopPanelId,
      leftover: lanternPanel.shopLeftover,
      street: lanternPanel.shopStreet,
      banner: lanternPanel.banner,
      kind: lanternPanel.kind,
      leftoverCopy: lanternPanel.leftoverCopy,
      streetAuthoredCopy: lanternPanel.streetAuthoredCopy,
    },
    pho: {
      id: phoPanel.shopPanelId,
      leftover: phoPanel.shopLeftover,
      street: phoPanel.shopStreet,
      banner: phoPanel.banner,
      kind: phoPanel.kind,
      leftoverCopy: phoPanel.leftoverCopy,
      streetLocalCopy: phoPanel.streetLocalCopy,
    },
    streetE: {
      id: streetE.snap.shopPanelId,
      leftover: streetE.snap.shopLeftover,
      kind: streetE.snap.kind,
      leftoverCopy: streetE.snap.leftoverCopy,
      nearby: streetE.snap.nearbyShop,
      lon: streetE.snap.lon,
      lat: streetE.snap.lat,
      heading: streetE.snap.heading,
    },
    walkHeading: atLantern.snap.heading,
    walkLon: atLantern.snap.lon,
    walkLat: atLantern.snap.lat,
    honesty: spawn.honesty?.slice(0, 220),
    didNotCatalogClear: true,
  };
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_LEFTOVER_PANEL_FAIL",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_LEFTOVER_PANEL_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  [
    report.verdict,
    report.run_id,
    `js=${report.liveJs}`,
    `leftover=${report.shared?.kind}|${report.j6?.kind}`,
    `street=${report.lantern?.kind}|${report.pho?.kind}`,
    `e=${report.streetE?.id || "none"}`,
  ].join(" "),
);
