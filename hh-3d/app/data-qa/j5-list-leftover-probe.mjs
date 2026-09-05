/**
 * Isolated guest B Menu/Tab shop list on recycled 4175.
 * Spawn-keep-out leftovers must be labeled leftover (or absent as
 * unlabeled street rows). Lantern + drawn Phở stay street rows.
 * Nearby E still not stolen. Does not catalog_clear. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-LIST-LEFTOVER-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT_B || 9691);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-29";
const LEFTOVER_IDS = new Set(["shop-local-sharedpc", "shop-local-mtl8ulddihjpre"]);
const LEFTOVER = /sharedpc|j6|mtl8ulddihjpre|critic j6/i;
const PLAYER_SHOP = "shop-local-mtmh45qxehxhvb";
const LANTERN = "shop-lantern-fish";

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
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const identity = document.querySelector('[data-testid="demo-identity"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  const names = document.querySelector('[data-testid="public-shop-names"]');
  const rows = [...document.querySelectorAll('[data-testid="public-shop-names"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    name: (el.querySelector(".menu-shop-name")?.textContent ?? el.textContent ?? "").trim().split("\\n")[0],
    text: (el.textContent ?? "").replace(/\\s+/g, " ").trim(),
    leftover: el.getAttribute("data-leftover") ?? "",
    keepOut: el.getAttribute("data-keep-out") ?? "",
    street: el.getAttribute("data-street") ?? "",
    source: el.getAttribute("data-source") ?? "",
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
  }));
  const goods = [...document.querySelectorAll('[data-testid="public-goods-rows"] li')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    leftover: el.getAttribute("data-leftover") ?? "",
    text: (el.textContent ?? "").replace(/\\s+/g, " ").trim(),
    labeled: /không trên phố|leftover máy này/i.test(el.textContent ?? ""),
  }));
  const stalls = [...document.querySelectorAll('[data-testid="play-shop-stalls"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    name: el.getAttribute("data-name") ?? "",
  }));
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    lon: Number(avatar?.getAttribute("data-lon") ?? "NaN"),
    lat: Number(avatar?.getAttribute("data-lat") ?? "NaN"),
    canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    nearbyShop: hint?.getAttribute("data-nearby-shop") ?? "",
    stallHint: hint?.textContent ?? "",
    shopRange: range?.textContent ?? "",
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    menuOpen: menu?.getAttribute("data-open") === "yes" && menu?.hidden !== true,
    menuHidden: menu?.hidden === true,
    listCount: Number(names?.getAttribute("data-count") ?? "0"),
    streetCount: Number(names?.getAttribute("data-street-count") ?? "0"),
    leftoverCount: Number(names?.getAttribute("data-leftover-count") ?? "0"),
    rows,
    goods,
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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j5-list-leftover-${port}-`));
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
  await sleep(120);
  await keyHold(ws, nextId, "Tab", "Tab", 9, 80);
  nextId += 2;
  const menu = await waitSnap(
    ws,
    nextId,
    (s) =>
      s.menuOpen === true &&
      s.rows.some((row) => row.shop === LANTERN) &&
      s.leftoverCount >= 2 &&
      s.rows.some((row) => row.shop === PLAYER_SHOP || (/phở|pho/i.test(row.name) && row.street === "1")),
    32,
    250,
  );
  nextId = menu.nextId;
  const list = menu.snap;

  const leftoverRows = list.rows.filter((row) => LEFTOVER_IDS.has(row.shop) || LEFTOVER.test(row.shop) || LEFTOVER.test(row.name));
  const unlabeledLeftover = leftoverRows.filter((row) => row.leftover !== "1" || row.street === "1" || !row.labeled);
  const lanternRow = list.rows.find((row) => row.shop === LANTERN);
  const phoRow =
    list.rows.find((row) => row.shop === PLAYER_SHOP) ||
    list.rows.find((row) => /phở|pho/i.test(row.name) && row.street === "1");
  const streetIds = list.rows.filter((row) => row.street === "1").map((row) => row.shop);
  const leftoverAfterStreet = list.rows.every((row, index, rows) => {
    if (row.leftover !== "1") {
      return true;
    }
    return rows.slice(0, index).every((prev) => prev.leftover === "1" || prev.street === "1");
  }) && list.rows.findIndex((row) => row.leftover === "1") >= list.rows.findIndex((row) => row.street === "1");
  const leftoverLast =
    leftoverRows.length === 0 ||
    list.rows.slice(list.rows.length - leftoverRows.length).every((row) => row.leftover === "1");

  await keyHold(ws, nextId, "Escape", "Escape", 27, 80);
  nextId += 2;
  await sleep(200);
  await keyHold(ws, nextId, "e", "KeyE", 69, 180);
  nextId += 2;
  await sleep(280);
  const afterE = await evalLoad(ws, nextId, SNAP);
  nextId += 1;
  const leftoverEStolen = Boolean(afterE.shopPanel) && LEFTOVER.test(afterE.shopPanelId || "");

  const leftoverPersist = busShops
    .filter((row) => LEFTOVER_IDS.has(row.shop_id))
    .map((row) => ({ shop: row.shop_id, name: row.name, lon: row.lon, lat: row.lat, status: row.status }));
  const leftoverKeep =
    leftoverPersist.some((row) => row.shop === "shop-local-sharedpc") &&
    leftoverPersist.some((row) => row.shop === "shop-local-mtl8ulddihjpre");

  const guestOk = spawn.identitySigned === "no" || /guest/i.test(spawn.identity || "");
  const streetOk =
    lanternRow?.street === "1" &&
    lanternRow?.leftover === "0" &&
    lanternRow?.labeled === false &&
    phoRow?.street === "1" &&
    phoRow?.leftover === "0" &&
    phoRow?.labeled === false;
  const leftoverListOk =
    leftoverKeep &&
    leftoverRows.length >= 2 &&
    unlabeledLeftover.length === 0 &&
    leftoverLast &&
    leftoverAfterStreet;
  const nearbyOk =
    !LEFTOVER.test(spawn.nearbyShop || "") &&
    !LEFTOVER.test(list.nearbyShop || "") &&
    !LEFTOVER.test(afterE.nearbyShop || "") &&
    (spawn.leftoverDrawn || []).length === 0;
  const leftoverEOk = !leftoverEStolen && !afterE.shopPanel;
  const ok =
    guestOk &&
    list.menuOpen &&
    streetOk &&
    leftoverListOk &&
    nearbyOk &&
    leftoverEOk &&
    leftoverKeep &&
    spawn.deniesGta;

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_LIST_LEFTOVER_OK" : "J5_LIST_LEFTOVER_FAIL",
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
    liveJs,
    liveLen,
    liveSha,
    guestOk,
    streetOk,
    leftoverListOk,
    leftoverLast,
    leftoverAfterStreet,
    nearbyOk,
    leftoverEOk,
    leftoverKeep,
    leftoverEStolen,
    unlabeledLeftover,
    lantern: lanternRow,
    pho: phoRow,
    streetIds,
    leftoverRows,
    rows: list.rows,
    goods: list.goods,
    streetCount: list.streetCount,
    leftoverCount: list.leftoverCount,
    nearbySpawn: spawn.nearbyShop,
    nearbyAfterE: afterE.nearbyShop,
    shopAfterE: afterE.shopPanelId,
    leftoverDrawn: spawn.leftoverDrawn,
    leftoverPersist,
    identity: spawn.identity,
    honesty: spawn.honesty?.slice(0, 220),
    didNotCatalogClear: true,
  };
} catch (err) {
  report = {
    run_id: RUN_ID,
    verdict: "J5_LIST_LEFTOVER_FAIL",
    error: err instanceof Error ? err.message : String(err),
    not_plan_pass: true,
    not_gate_u1: true,
    not_m1: true,
  };
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
if (report.verdict !== "J5_LIST_LEFTOVER_OK") {
  console.error(report);
  process.exit(1);
}
console.log(
  [
    report.verdict,
    report.run_id,
    `js=${report.liveJs}`,
    `street=${report.streetIds?.join(",")}`,
    `leftover=${report.leftoverRows?.map((row) => row.shop).join(",")}`,
    `e=${report.shopAfterE || "none"}`,
  ].join(" "),
);
