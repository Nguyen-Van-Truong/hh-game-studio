/**
 * Isolated seat on 4175. Social Offline ≠ internet.
 * HUD/menu show Offline stroll + Đang kết nối / Mất kết nối.
 * CDP Network.emulateNetworkConditions → navigator.onLine=false
 * must change ONLY the connectivity line. Does not click Online
 * or Simulate no-network. Does not catalog_clear. NOT_PLAN_PASS.
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
const OUT = join(import.meta.dirname, "J5-NET-LABEL-2026-09-04.txt");
const PORT = Number(process.env.HH_CDP_PORT || 9661);
const RUN_ID = "HH3D-J5-20260904-ASIA-SAIGON-26";

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
  const proof = document.querySelector('[data-testid="play-proof"]');
  const hudPresence = document.querySelector('[data-testid="hud-presence"]');
  const hudConn = document.querySelector('[data-testid="hud-connection"]');
  const modeStatus = document.querySelector('[data-testid="mode-status"]');
  const chip = document.querySelector('[data-testid="play-street-chip"]');
  const mode = document.querySelector('[data-testid="presence-mode"]');
  const menuConn = document.querySelector('[data-testid="menu-connection"]');
  const conn = document.querySelector('[data-testid="connection-label"]');
  const online = document.querySelector('[data-testid="online-btn"]');
  const offline = document.querySelector('[data-testid="offline-btn"]');
  const cutBar = document.querySelector('[data-testid="network-cut-sim"]');
  const honesty = document.querySelector('[data-testid="honesty-banner"]');
  const hudBox = modeStatus ? modeStatus.getBoundingClientRect() : null;
  const hudConnBox = hudConn ? hudConn.getBoundingClientRect() : null;
  const chipBox = chip ? chip.getBoundingClientRect() : null;
  const onScreen = (box) =>
    Boolean(box && box.width > 8 && box.height > 8 && box.x > -8 && box.x < 1288 && box.y > -8 && box.y < 728);
  return {
    title: document.title,
    playReady: play?.getAttribute("data-play-ready") ?? "",
    buildings: Number(proof?.getAttribute("data-buildings") ?? "0"),
    streetHud: play?.getAttribute("data-street-hud") ?? proof?.getAttribute("data-street-hud") ?? "",
    streetName: chip?.getAttribute("data-street-name") ?? "",
    chipOnScreen: onScreen(chipBox),
    hudPresence: (hudPresence?.textContent ?? "").trim(),
    hudPresenceAttr: hudPresence?.getAttribute("data-presence") ?? "",
    hudConnection: (hudConn?.textContent ?? "").trim(),
    hudConnectionAttr: hudConn?.getAttribute("data-connection") ?? "",
    hudOnScreen: onScreen(hudBox),
    hudConnOnScreen: onScreen(hudConnBox),
    hudBox: hudBox
      ? { x: Number(hudBox.x.toFixed(1)), y: Number(hudBox.y.toFixed(1)), w: Number(hudBox.width.toFixed(1)), h: Number(hudBox.height.toFixed(1)) }
      : null,
    presenceMode: (mode?.textContent ?? "").trim(),
    menuConnection: (menuConn?.textContent ?? "").trim(),
    connectionLabel: (conn?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    connectionAttr: conn?.getAttribute("data-connection") ?? "",
    onlineActive: online?.getAttribute("data-active") ?? "",
    offlineActive: offline?.getAttribute("data-active") ?? "",
    networkCutBar: Boolean(cutBar?.checked),
    navOnline: navigator.onLine,
    menuOpen: document.querySelector('[data-testid="play-menu"]')?.getAttribute("data-open") ?? "",
    honesty: (honesty?.textContent ?? "").replace(/\\s+/g, " ").slice(0, 220),
    browserOfflinePhrase: /browser offline/i.test(document.body.innerText || ""),
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

function socialUnchanged(snap) {
  return (
    snap.hudPresence === "Offline" &&
    snap.hudPresenceAttr === "offline" &&
    /Offline — Stroll alone/.test(snap.presenceMode || "") &&
    snap.offlineActive === "yes" &&
    snap.onlineActive === "no" &&
    snap.networkCutBar === false
  );
}

const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${mkdtempSync(join(tmpdir(), "hh-world-j5-net-label-"))}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,720",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let report;
try {
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
    (s) =>
      s.playReady === "yes" &&
      s.buildings >= 20 &&
      s.hudPresence === "Offline" &&
      s.hudConnection === "Đang kết nối",
    48,
    250,
  );
  let nextId = ready.nextId;
  const onlineSnap = ready.snap;

  if (onlineSnap.menuOpen === "yes") {
    throw new Error("menu should start hidden so HUD labels are the walk chrome");
  }
  if (!onlineSnap.hudOnScreen || !onlineSnap.hudConnOnScreen) {
    throw new Error(`HUD labels not on screen ${JSON.stringify(onlineSnap.hudBox)}`);
  }
  if (!socialUnchanged(onlineSnap) || onlineSnap.navOnline !== true) {
    throw new Error(`spawn labels wrong ${JSON.stringify(onlineSnap)}`);
  }
  if (onlineSnap.browserOfflinePhrase) {
    throw new Error("page still says browser offline");
  }
  if ((onlineSnap.hudBox?.h || 99) > 28) {
    throw new Error(`HUD line too fat ${JSON.stringify(onlineSnap.hudBox)}`);
  }

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
  const lost = await waitSnap(
    ws,
    nextId,
    (s) => s.navOnline === false && s.hudConnection === "Mất kết nối",
    24,
    200,
  );
  nextId = lost.nextId;

  if (!socialUnchanged(lost.snap)) {
    throw new Error(`lost-network flipped social ${JSON.stringify(lost.snap)}`);
  }
  if (lost.snap.hudConnection !== "Mất kết nối" || lost.snap.hudConnectionAttr !== "off") {
    throw new Error(`HUD connectivity did not become Mất kết nối ${JSON.stringify(lost.snap)}`);
  }
  if (lost.snap.networkCutBar) {
    throw new Error("checkbox sim was on; this slice must use navigator.onLine=false only");
  }
  if (lost.snap.menuOpen === "yes") {
    throw new Error("opening the menu is not required to show Mất kết nối");
  }

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
  const menuOpen = await waitSnap(
    ws,
    nextId,
    (s) => s.menuOpen === "yes" && s.menuConnection === "Mất kết nối",
    20,
    200,
  );
  nextId = menuOpen.nextId;
  if (!socialUnchanged(menuOpen.snap)) {
    throw new Error(`opening menu flipped social ${JSON.stringify(menuOpen.snap)}`);
  }
  if (!/Mất kết nối/.test(menuOpen.snap.connectionLabel || "")) {
    throw new Error(`menu connection missing Mất kết nối ${menuOpen.snap.connectionLabel}`);
  }
  if (/browser offline/i.test(menuOpen.snap.connectionLabel || "")) {
    throw new Error("menu still says browser offline");
  }

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
    (s) => s.navOnline === true && s.hudConnection === "Đang kết nối" && s.menuConnection === "Đang kết nối",
    24,
    200,
  );
  nextId = restored.nextId;
  if (!socialUnchanged(restored.snap)) {
    throw new Error(`restore flipped social ${JSON.stringify(restored.snap)}`);
  }

  const live = await liveJsInfo();
  const ok =
    socialUnchanged(onlineSnap) &&
    socialUnchanged(lost.snap) &&
    socialUnchanged(menuOpen.snap) &&
    socialUnchanged(restored.snap) &&
    onlineSnap.hudConnection === "Đang kết nối" &&
    lost.snap.hudConnection === "Mất kết nối" &&
    menuOpen.snap.menuConnection === "Mất kết nối" &&
    restored.snap.hudConnection === "Đang kết nối" &&
    lost.snap.navOnline === false &&
    restored.snap.navOnline === true &&
    !onlineSnap.browserOfflinePhrase;

  report = {
    runId: RUN_ID,
    player: PLAYER,
    verdict: ok ? "J5_NET_LABEL_OK" : "J5_NET_LABEL_FAIL",
    live,
    online: {
      hudPresence: onlineSnap.hudPresence,
      hudConnection: onlineSnap.hudConnection,
      presenceMode: onlineSnap.presenceMode,
      menuOpen: onlineSnap.menuOpen,
      streetName: onlineSnap.streetName,
      hudBox: onlineSnap.hudBox,
      navOnline: onlineSnap.navOnline,
    },
    lost: {
      hudPresence: lost.snap.hudPresence,
      hudConnection: lost.snap.hudConnection,
      presenceMode: lost.snap.presenceMode,
      menuOpen: lost.snap.menuOpen,
      navOnline: lost.snap.navOnline,
      networkCutBar: lost.snap.networkCutBar,
    },
    menu: {
      hudPresence: menuOpen.snap.hudPresence,
      menuConnection: menuOpen.snap.menuConnection,
      presenceMode: menuOpen.snap.presenceMode,
      connectionLabel: menuOpen.snap.connectionLabel,
    },
    restored: {
      hudPresence: restored.snap.hudPresence,
      hudConnection: restored.snap.hudConnection,
      menuConnection: restored.snap.menuConnection,
      presenceMode: restored.snap.presenceMode,
      navOnline: restored.snap.navOnline,
    },
    honesty: onlineSnap.honesty,
  };
  writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`);
  if (!ok) {
    throw new Error(`J5_NET_LABEL_FAIL ${JSON.stringify(report)}`);
  }
  console.log(
    [
      "J5_NET_LABEL_OK",
      `hud=${onlineSnap.hudPresence}+${onlineSnap.hudConnection}`,
      `lost=${lost.snap.hudPresence}+${lost.snap.hudConnection}`,
      `menu=${menuOpen.snap.menuConnection}`,
      `js=${live.liveJs}`,
    ].join(" "),
  );
} finally {
  chrome.kill();
}
