/**
 * Isolated guest B: drawn Phở / lantern kiosks sit on Harbor sidewalk,
 * not the driving lane. Walk Harbor Walk north past Phở without a
 * centerline hit. Chip stays Harbor Walk. E at lantern still
 * shop-lantern-fish. Leftover Menu + leftover panel banners hold.
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
const OUT = join(import.meta.dirname, "J5-STALL-SIDEWALK-2026-09-04.txt");
const SHOT = join(import.meta.dirname, "j5-3d-stall-sidewalk.png");
const PORT = Number(process.env.HH_CDP_PORT_B || 9698);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-32";
const LEFTOVER_IDS = new Set(["shop-local-sharedpc", "shop-local-mtl8ulddihjpre"]);
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAYER_SHOP = "shop-local-mtmh45qxehxhvb";
const LANTERN = "shop-lantern-fish";
const LANTERN_POS = { lon: 106.6980366, lat: 10.7718712 };
const SHARED = "shop-local-sharedpc";
const J6 = "shop-local-mtl8ulddihjpre";
const M_PER_DEG_LAT = 111320;
const ORIGIN = { lon: 106.698, lat: 10.7725 };
const STREET_HALF = 4.3;
const LEFTOVER_COPY = /không trên phố|leftover máy này/i;
const STREET_LOCAL = /public shop · opened on this machine/i;
const STREET_AUTHORED = /public shop · authored example among many/i;

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
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    name: (el.querySelector(".menu-shop-name")?.textContent ?? el.textContent ?? "").trim().split("\\n")[0],
    leftover: el.getAttribute("data-leftover") ?? "",
    street: el.getAttribute("data-street") ?? "",
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
  }));
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    name: el.getAttribute("data-name") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    collide: el.getAttribute("data-collide") ?? "",
    lon: Number(el.getAttribute("data-lon") ?? "NaN"),
    lat: Number(el.getAttribute("data-lat") ?? "NaN"),
    x: Number(el.getAttribute("data-x") ?? "NaN"),
    z: Number(el.getAttribute("data-z") ?? "NaN"),
    laneM: Number(el.getAttribute("data-lane-m") ?? "NaN"),
    street: el.getAttribute("data-street") ?? "",
  }));
  const panelText = (panel?.innerText ?? "").replace(/\\s+/g, " ").trim();
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    heading: Number(avatar?.getAttribute("data-heading") ?? "NaN"),
    blocked: proof?.getAttribute("data-blocked") ?? "",
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
    chip: (chip?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    rows,
    stalls,
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-stall-sidewalk-${port}-`));
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
  const gone = await waitSnap(ws, nextId, (s) => s.shopPanel === false, 16, 160);
  return gone.nextId;
}

function leftoverPanelOk(snap, shopId) {
  return (
    snap.shopPanelId === shopId &&
    snap.shopLeftover === "1" &&
    snap.shopStreet === "0" &&
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
    (s) => s.playReady === "yes" && s.canvas && s.buildings >= 20 && s.stalls.length >= 2,
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

  const phoRow = (spawn.stalls || []).find((row) => row.shop === PLAYER_SHOP);
  const lanternRow = (spawn.stalls || []).find((row) => row.shop === LANTERN);
  const leftoverRowsDrawn = (spawn.stalls || []).filter((row) => LEFTOVER_IDS.has(row.shop));
  const phoHit = phoRow ? nearestOn(harbor, phoRow.x, phoRow.z) : null;
  const lanternHit = lanternRow ? nearestOn(harbor, lanternRow.x, lanternRow.z) : null;
  const phoPersist = phoRow ? toWorld(phoRow.lon, phoRow.lat) : null;
  const phoPersistHit = phoPersist ? nearestOn(harbor, phoPersist.x, phoPersist.z + 0.72) : null;
  const phoOffLane = Boolean(phoHit && phoHit.dist >= STREET_HALF + 1.2);
  const lanternOffLane = Boolean(lanternHit && lanternHit.dist >= STREET_HALF + 1.2);
  const phoDrawn = phoRow?.draw === "1";
  const lanternDrawn = lanternRow?.draw === "1";
  const leftoversHidden = leftoverRowsDrawn.every((row) => row.draw === "0");

  const sharedOpen = await openMenuShop(ws, nextId, SHARED);
  nextId = sharedOpen.nextId;
  const sharedPanel = sharedOpen.snap;
  const list = sharedOpen.list.rows?.length ? sharedOpen.list : sharedPanel;
  nextId = await closeShop(ws, nextId);

  const j6Open = await openMenuShop(ws, nextId, J6);
  nextId = j6Open.nextId;
  const j6Panel = j6Open.snap;
  nextId = await closeShop(ws, nextId);

  const leftoverMenuRows = (list.rows || []).filter(
    (row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop) || LEFTOVER.test(row.name),
  );
  const leftoverLast =
    leftoverMenuRows.length === 0 ||
    (list.rows || [])
      .slice((list.rows || []).length - leftoverMenuRows.length)
      .every((row) => row.leftover === "1");

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
  const north = await turnToHeading(ws, nextId, 0);
  nextId = north.nextId;

  const walkLog = [];
  let pastPho = { snap: north.snap, nextId };
  const phoLat = phoRow?.lat ?? 10.771797;
  for (let chunk = 0; chunk < 8; chunk += 1) {
    const before = pastPho.snap;
    await keyHold(ws, nextId, "w", "KeyW", 87, 2800);
    nextId += 2;
    await sleep(80);
    const now = await evalLoad(ws, nextId, SNAP);
    nextId += 1;
    const gained = (now.lat - before.lat) * M_PER_DEG_LAT;
    const body = toWorld(now.lon, now.lat);
    const onHarbor = nearestOn(harbor, body.x, body.z);
    walkLog.push({
      chunk,
      lat: now.lat,
      lon: now.lon,
      chip: now.chip,
      heading: now.heading,
      blocked: now.blocked,
      gained: Number(gained.toFixed(2)),
      laneM: onHarbor ? Number(onHarbor.dist.toFixed(2)) : null,
    });
    pastPho = { snap: now, nextId };
    if (now.lat > phoLat + 0.00004) {
      break;
    }
    if (gained < 1.2) {
      await keyHold(ws, nextId, "d", "KeyD", 68, 220);
      nextId += 2;
      await keyHold(ws, nextId, "w", "KeyW", 87, 900);
      nextId += 2;
      await keyHold(ws, nextId, "a", "KeyA", 65, 220);
      nextId += 2;
    }
  }

  const walkBody = toWorld(pastPho.snap.lon, pastPho.snap.lat);
  const walkHarbor = nearestOn(harbor, walkBody.x, walkBody.z);
  const walkedPastPho = pastPho.snap.lat > phoLat;
  const walkNotBlocked = walkLog.some((row) => row.gained > 2.4) && walkedPastPho;
  const chipHarbor = walkLog.every((row) => !row.chip || row.chip === "Harbor Walk" || row.chip === "—")
    ? walkLog.some((row) => row.chip === "Harbor Walk")
    : pastPho.snap.chip === "Harbor Walk";
  const chipOnStretch = pastPho.snap.chip === "Harbor Walk" || walkLog.some((row) => row.chip === "Harbor Walk");

  await turnToHeading(ws, nextId, phoHit && phoRow && phoRow.x < walkBody.x ? 270 : 90);
  nextId = (await turnToHeading(ws, nextId, phoHit && phoRow && phoRow.x < walkBody.x ? 270 : 90)).nextId;
  await sleep(200);
  const lookStall = await evalLoad(ws, nextId, SNAP);
  nextId += 1;
  const shot = await cdp(ws, nextId, "Page.captureScreenshot", { format: "png" });
  nextId += 1;
  writeFileSync(SHOT, Buffer.from(shot.data, "base64"));

  await blurCanvas(ws, nextId);
  nextId += 1;
  const toLantern = await turnToHeading(ws, nextId, metersHeadingTo(lookStall, LANTERN_POS));
  nextId = toLantern.nextId;
  let atLantern = { snap: toLantern.snap, nextId };
  for (let i = 0; i < 10; i += 1) {
    const now = await evalLoad(ws, nextId, SNAP);
    nextId += 1;
    if (now.nearbyShop === LANTERN) {
      atLantern = { snap: now, nextId };
      break;
    }
    const bear = metersHeadingTo(now, LANTERN_POS);
    if (!facingToward(now.heading, bear, 14)) {
      const turned = await turnToHeading(ws, nextId, bear);
      nextId = turned.nextId;
    }
    await keyHold(ws, nextId, "w", "KeyW", 87, 1400);
    nextId += 2;
    await sleep(80);
    const mid = await evalLoad(ws, nextId, SNAP);
    nextId += 1;
    atLantern = { snap: mid, nextId };
    if (mid.nearbyShop === LANTERN) {
      break;
    }
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
  const streetEOk = streetE.snap.nearbyShop === LANTERN && streetPanelOk(streetE.snap, LANTERN, true);
  const nearbyOk = (spawn.leftoverDrawn || []).length === 0 && leftoversHidden;
  const listOk = leftoverKeep && leftoverMenuRows.length >= 2 && leftoverLast;
  const poseOk = phoDrawn && lanternDrawn && phoOffLane && lanternOffLane && leftoversHidden;
  const walkOk = walkNotBlocked && chipOnStretch && walkedPastPho;
  const ok =
    guestOk &&
    leftoverOk &&
    streetEOk &&
    nearbyOk &&
    listOk &&
    leftoverKeep &&
    poseOk &&
    walkOk &&
    spawn.deniesGta;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_STALL_SIDEWALK_OK" : "J5_STALL_SIDEWALK_FAIL",
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
    liveJs,
    liveLen,
    liveSha,
    guestOk,
    leftoverOk,
    streetEOk,
    nearbyOk,
    listOk,
    leftoverLast,
    leftoverKeep,
    poseOk,
    walkOk,
    phoOffLane,
    lanternOffLane,
    phoDrawn,
    lanternDrawn,
    leftoversHidden,
    walkedPastPho,
    chipOnStretch,
    chipAtPho: pastPho.snap.chip,
    walkHarborDist: walkHarbor ? Number(walkHarbor.dist.toFixed(2)) : null,
    pho: phoRow
      ? {
          ...phoRow,
          persistLane: phoPersistHit ? Number(phoPersistHit.dist.toFixed(2)) : null,
          plantLane: phoHit ? Number(phoHit.dist.toFixed(2)) : null,
        }
      : null,
    lantern: lanternRow
      ? {
          ...lanternRow,
          plantLane: lanternHit ? Number(lanternHit.dist.toFixed(2)) : null,
        }
      : null,
    leftoverDrawn: spawn.leftoverDrawn,
    leftoverPersist,
    leftoverMenuRows,
    walkLog,
    walkEnd: { lon: pastPho.snap.lon, lat: pastPho.snap.lat, chip: pastPho.snap.chip, heading: pastPho.snap.heading },
    lookStall: { lon: lookStall.lon, lat: lookStall.lat, heading: lookStall.heading, chip: lookStall.chip },
    shot: SHOT,
    identity: spawn.identity,
    mode: spawn.mode || sharedPanel.mode,
    shared: { id: sharedPanel.shopPanelId, leftover: sharedPanel.shopLeftover, banner: sharedPanel.banner, kind: sharedPanel.kind },
    j6: { id: j6Panel.shopPanelId, leftover: j6Panel.shopLeftover, banner: j6Panel.banner, kind: j6Panel.kind },
    streetE: {
      id: streetE.snap.shopPanelId,
      leftover: streetE.snap.shopLeftover,
      kind: streetE.snap.kind,
      leftoverCopy: streetE.snap.leftoverCopy,
      nearby: streetE.snap.nearbyShop,
      lon: streetE.snap.lon,
      lat: streetE.snap.lat,
    },
    honesty: spawn.honesty?.slice(0, 220),
    didNotCatalogClear: true,
  };
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_STALL_SIDEWALK_FAIL",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_STALL_SIDEWALK_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  [
    report.verdict,
    report.run_id,
    `js=${report.liveJs}`,
    `phoLane=${report.pho?.plantLane}`,
    `lanternLane=${report.lantern?.plantLane}`,
    `chip=${report.chipAtPho}`,
    `e=${report.streetE?.id || "none"}`,
  ].join(" "),
);
