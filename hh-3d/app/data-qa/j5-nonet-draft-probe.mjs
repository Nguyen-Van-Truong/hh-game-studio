/**
 * Isolated seat on already-up 4175. Lost network is not social Offline.
 * CDP Network.emulateNetworkConditions → navigator.onLine=false.
 * New listing on Quầy Phở Nhà stays Chưa đăng / off the chalkboard.
 * Public Phở cache stays. Does not remint / recycle / catalog_clear.
 * Does not click the no-network checkbox. Deletes the test draft after.
 * NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-NONET-DRAFT-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT || 9651);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-25";
const PLAYER_SHOP = "shop-local-mtmh45qxehxhvb";
const DRAFT_TITLE = "Bun Nonet Probe 0904";
const DRAFT_MARK = /bun\s*nonet\s*probe\s*0904/i;

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

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const identity = document.querySelector('[data-testid="demo-identity"]');
  const mode = document.querySelector('[data-testid="presence-mode"]');
  const online = document.querySelector('[data-testid="online-btn"]');
  const offline = document.querySelector('[data-testid="offline-btn"]');
  const conn = document.querySelector('[data-testid="connection-label"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  const form = document.querySelector('[data-testid="list-product-form"]');
  const result = document.querySelector('[data-testid="list-result"]');
  const loadedAt = document.querySelector('[data-testid="goods-loaded-at"]');
  const cutBar = document.querySelector('[data-testid="network-cut-sim"]');
  const cutShop = document.querySelector('[data-testid="shop-network-cut"]');
  const listings = [...document.querySelectorAll('[data-testid="shop-listings"] [data-listing]')].map((el) => ({
    id: el.getAttribute("data-listing") ?? "",
    status: el.getAttribute("data-status") ?? "",
    text: (el.textContent ?? "").replace(/\\s+/g, " ").trim(),
  }));
  const drafts = [...document.querySelectorAll('[data-testid="owner-drafts"] [data-draft]')].map((el) => ({
    id: el.getAttribute("data-draft") ?? "",
    status: el.getAttribute("data-status") ?? "",
    queued: el.getAttribute("data-queued") ?? "",
    text: (el.textContent ?? "").replace(/\\s+/g, " ").trim(),
  }));
  const boards = [...document.querySelectorAll('[data-testid="play-stall-boards"] li')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    draw: el.getAttribute("data-draw") ?? "",
    titles: el.getAttribute("data-titles") ?? "",
  }));
  const liveBoards = [...document.querySelectorAll('[data-testid^="shop-menu-board-"]')].map((el) => ({
    shop: el.getAttribute("data-shop-id") ?? "",
    titles: el.getAttribute("data-titles") ?? "",
    text: (el.textContent ?? "").replace(/\\s+/g, " ").trim(),
  }));
  const phoBoard = boards.find((row) => row.shop === ${JSON.stringify(PLAYER_SHOP)}) ?? null;
  const phoLive = liveBoards.find((row) => row.shop === ${JSON.stringify(PLAYER_SHOP)}) ?? null;
  const publicNames = [...document.querySelectorAll('[data-testid="public-shop-names"] [data-shop]')].map((el) => ({
    shop: el.getAttribute("data-shop") ?? "",
    text: (el.textContent ?? "").replace(/\\s+/g, " ").trim(),
  }));
  const body = document.body.innerText || "";
  return {
    playReady: play?.getAttribute("data-play-ready") ?? "",
    buildings: Number(document.querySelector('[data-testid="play-proof"]')?.getAttribute("data-buildings") ?? "0"),
    identity: (identity?.textContent ?? "").trim(),
    identitySigned: identity?.getAttribute("data-signed-in") ?? "",
    presenceMode: (mode?.textContent ?? "").trim(),
    onlineActive: online?.getAttribute("data-active") ?? "",
    offlineActive: offline?.getAttribute("data-active") ?? "",
    connection: (conn?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? "",
    form: Boolean(form),
    formNetwork: form?.getAttribute("data-network") ?? null,
    become: Boolean(document.querySelector('[data-testid="become-demo-owner"]')),
    leave: Boolean(document.querySelector('[data-testid="leave-demo-owner"]')),
    retry: Boolean(document.querySelector('[data-testid="retry-publish"]')),
    retryDisabled: document.querySelector('[data-testid="retry-publish"]')?.disabled ?? null,
    retryText: (document.querySelector('[data-testid="retry-publish"]')?.textContent ?? "").trim(),
    listings,
    drafts,
    result: result
      ? {
          status: result.getAttribute("data-status") ?? "",
          id: result.getAttribute("data-listing") ?? "",
          text: (result.textContent ?? "").replace(/\\s+/g, " ").trim(),
        }
      : null,
    phoBoard,
    phoLive,
    boards,
    publicNames,
    phoPublic: publicNames.some((row) => row.shop === ${JSON.stringify(PLAYER_SHOP)}),
    goodsLoadedAt: (loadedAt?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    listingUpdated: /Listing updated/i.test(body),
    daDang: /đã đăng/i.test(body),
    chuaDang: /Chưa đăng/.test(body),
    networkCutBar: Boolean(cutBar?.checked),
    networkCutShop: Boolean(cutShop?.checked),
    navOnline: navigator.onLine,
    menuOpen: document.querySelector('[data-testid="play-menu"]')?.getAttribute("data-open") ?? "",
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

async function busGet() {
  const res = await fetch(new URL("/demo-bus", PLAYER));
  return res.json();
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

function boardHasDraft(snap) {
  const titles = `${snap?.phoBoard?.titles || ""} ${snap?.phoLive?.titles || ""} ${snap?.phoLive?.text || ""}`;
  return DRAFT_MARK.test(titles);
}

function shelfHasDraft(snap) {
  return (snap?.listings || []).some(
    (row) => DRAFT_MARK.test(row.text || "") || DRAFT_MARK.test(row.id || ""),
  );
}

function busHasDraft(bus) {
  const listings = Array.isArray(bus?.catalog?.listings) ? bus.catalog.listings : [];
  return listings.some((row) => DRAFT_MARK.test(row.title || "") || DRAFT_MARK.test(row.listing_id || ""));
}

const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${mkdtempSync(join(tmpdir(), "hh-world-j5-nonet-"))}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--autoplay-policy=no-user-gesture-required",
    "--window-size=1280,720",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let report;
try {
  const busBefore = await busGet();
  const phoShop = (busBefore?.catalog?.shops || []).find((row) => row.shop_id === PLAYER_SHOP) ?? null;
  if (!phoShop) {
    throw new Error(`missing ${PLAYER_SHOP} on /demo-bus; will not remint or catalog_clear`);
  }

  const { ws } = await connectPage(PORT);
  await cdp(ws, 1, "Runtime.enable");
  await cdp(ws, 2, "Page.enable");
  await cdp(ws, 3, "Network.enable");
  await cdp(ws, 4, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(ws, 5, "Page.navigate", { url: `${PLAYER}?seat=a` });

  const ready = await waitSnap(
    ws,
    20,
    (s) => s.playReady === "yes" && s.buildings >= 20,
    48,
    250,
  );
  let nextId = ready.nextId;

  await evalExpr(
    ws,
    nextId,
    `(() => {
      const menu = document.querySelector('[data-testid="play-menu"]');
      if (menu?.getAttribute("data-open") !== "yes") {
        document.querySelector('[data-testid="play-menu-toggle"]')?.click();
      }
      return true;
    })()`,
  );
  nextId += 1;
  const menuOpen = await waitSnap(ws, nextId, (s) => s.menuOpen === "yes" && s.phoPublic, 20, 200);
  nextId = menuOpen.nextId;
  const cached = menuOpen.snap;

  await evalExpr(
    ws,
    nextId,
    `document.querySelector(${JSON.stringify(`[data-testid="open-shop-${PLAYER_SHOP}"]`)})?.click(); true`,
  );
  nextId += 1;
  const opened = await waitSnap(ws, nextId, (s) => s.shopPanelId === PLAYER_SHOP, 20, 200);
  nextId = opened.nextId;

  await evalExpr(ws, nextId, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
  nextId += 1;
  const owner = await waitSnap(
    ws,
    nextId,
    (s) => s.identitySigned === "yes" && s.form === true,
    20,
    200,
  );
  nextId = owner.nextId;
  const beforeTitles = owner.snap.phoBoard?.titles || "";

  await cdp(ws, nextId, "Network.emulateNetworkConditions", {
    offline: true,
    latency: 0,
    downloadThroughput: 0,
    uploadThroughput: 0,
    connectionType: "none",
  });
  nextId += 1;
  await evalExpr(
    ws,
    nextId,
    `(() => {
      if (navigator.onLine) {
        return { nav: navigator.onLine, dispatched: false };
      }
      window.dispatchEvent(new Event("offline"));
      return { nav: navigator.onLine, dispatched: true };
    })()`,
  );
  nextId += 1;
  const offline = await waitSnap(
    ws,
    nextId,
    (s) => s.navOnline === false && s.formNetwork === "off",
    24,
    200,
  );
  nextId = offline.nextId;

  if (offline.snap.networkCutBar || offline.snap.networkCutShop) {
    throw new Error("checkbox sim was on; this slice must use navigator.onLine=false only");
  }
  if (offline.snap.navOnline !== false || offline.snap.formNetwork !== "off") {
    throw new Error(`CDP offline did not flip publish gate ${JSON.stringify(offline.snap)}`);
  }

  await evalExpr(
    ws,
    nextId,
    `(() => {
      const input = document.querySelector('[data-testid="list-title"]');
      if (!input) return false;
      const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
      desc.set.call(input, ${JSON.stringify(DRAFT_TITLE)});
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return input.value;
    })()`,
  );
  nextId += 1;
  await evalExpr(ws, nextId, `document.querySelector('[data-testid="list-submit"]')?.click(); true`);
  nextId += 1;
  const listed = await waitSnap(
    ws,
    nextId,
    (s) => Boolean(s.result) && (s.drafts || []).some((row) => DRAFT_MARK.test(row.text)),
    24,
    200,
  );
  nextId = listed.nextId;

  const afterOfflineTitles = listed.snap.phoBoard?.titles || "";
  const draftOnBoardOffline = boardHasDraft(listed.snap) || shelfHasDraft(listed.snap);
  const busMid = await busGet();

  await cdp(ws, nextId, "Network.emulateNetworkConditions", {
    offline: false,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
  });
  nextId += 1;
  await evalExpr(ws, nextId, `window.dispatchEvent(new Event("online")); navigator.onLine`);
  nextId += 1;
  const restored = await waitSnap(
    ws,
    nextId,
    (s) => s.navOnline === true && s.formNetwork === "on" && s.retry === true && s.retryDisabled === false,
    24,
    200,
  );
  nextId = restored.nextId;

  const stillDraftAfterOnline = (restored.snap.drafts || []).some(
    (row) => DRAFT_MARK.test(row.text) && row.status === "draft",
  );
  const draftOnBoardAfterOnline = boardHasDraft(restored.snap) || shelfHasDraft(restored.snap);

  await evalExpr(
    ws,
    nextId,
    `(() => {
      const key = "hh-world.local-listings.v1";
      const raw = localStorage.getItem(key);
      if (!raw) return 0;
      const next = JSON.parse(raw).filter((row) => !${DRAFT_MARK}.test(row.title || "") && !${DRAFT_MARK}.test(row.listing_id || ""));
      localStorage.setItem(key, JSON.stringify(next));
      return next.length;
    })()`,
  );
  nextId += 1;
  await evalExpr(ws, nextId, `document.querySelector('[data-testid="leave-demo-owner"]')?.click(); true`);
  nextId += 1;
  const left = await waitSnap(ws, nextId, (s) => s.identitySigned === "no", 12, 150);
  nextId = left.nextId;

  const js = await liveJsInfo();
  const busAfter = await busGet();
  const leftoverPersist = (busAfter?.catalog?.shops || []).map((row) => ({
    shop: row.shop_id,
    name: row.name,
    status: row.status ?? "",
    owner_presence: row.owner_presence ?? "",
  }));

  const socialOffline =
    /offline/i.test(owner.snap.presenceMode || "") &&
    /offline/i.test(listed.snap.presenceMode || "") &&
    listed.snap.onlineActive !== "yes";
  const cacheStayed =
    cached.phoPublic &&
    listed.snap.phoPublic &&
    /phở|pho/i.test(listed.snap.phoBoard?.titles || beforeTitles) &&
    listed.snap.listingUpdated &&
    /Bản lưu lúc/i.test(listed.snap.goodsLoadedAt || cached.goodsLoadedAt || "");
  const draftOk =
    listed.snap.result?.status === "draft" &&
    /Chưa đăng/.test(listed.snap.result?.text || "") &&
    listed.snap.chuaDang === true &&
    listed.snap.daDang === false &&
    !draftOnBoardOffline &&
    stillDraftAfterOnline &&
    !draftOnBoardAfterOnline &&
    restored.snap.retry === true &&
    restored.snap.retryDisabled === false &&
    !busHasDraft(busMid) &&
    !busHasDraft(busAfter);
  const checkboxUnused = !listed.snap.networkCutBar && !listed.snap.networkCutShop;
  const ok =
    socialOffline &&
    cacheStayed &&
    draftOk &&
    checkboxUnused &&
    offline.snap.navOnline === false &&
    js.liveJs === "/assets/index-D4Sc2h68.js";

  report = {
    run_id: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_NONET_DRAFT_OK" : "J5_NONET_DRAFT_FAIL",
    reminted: false,
    didNotRecycle: true,
    didNotRebuild: true,
    didNotCatalogClear: true,
    didNotClickCheckbox: true,
    didNotClickRetry: true,
    deletedTestDraft: true,
    ...js,
    playerShopId: PLAYER_SHOP,
    draftTitle: DRAFT_TITLE,
    navOnlineOffline: offline.snap.navOnline,
    formNetworkOffline: offline.snap.formNetwork,
    connectionOffline: offline.snap.connection,
    presenceListed: listed.snap.presenceMode,
    result: listed.snap.result,
    draftsOffline: listed.snap.drafts,
    draftsRestored: restored.snap.drafts,
    beforeTitles,
    afterOfflineTitles,
    afterOnlineTitles: restored.snap.phoBoard?.titles || "",
    draftOnBoard: draftOnBoardOffline || draftOnBoardAfterOnline,
    daDang: listed.snap.daDang,
    cacheStayed,
    goodsLoadedAt: listed.snap.goodsLoadedAt || cached.goodsLoadedAt,
    listingUpdated: listed.snap.listingUpdated,
    retryEnabled: restored.snap.retry === true && restored.snap.retryDisabled === false,
    retryText: restored.snap.retryText,
    busDraft: busHasDraft(busAfter),
    leftoverPersist,
    socialOffline,
    draftOk,
    checkboxUnused,
    didNotRemint: true,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_NONET_DRAFT_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_NONET_DRAFT_OK",
      `js=${js.liveJs}`,
      `nav=${offline.snap.navOnline}`,
      `status=${listed.snap.result?.status}`,
      `boardDraft=${draftOnBoardOffline}`,
      `daDang=${listed.snap.daDang}`,
      `retry=${restored.snap.retryDisabled === false}`,
    ].join(" "),
  );
} finally {
  chrome.kill();
}
