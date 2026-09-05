/**
 * J4 create shop + listing, second context still sees it, walk+E opens it.
 * Recycled 4175 only. Isolated Chrome A/B. NOT_PLAN_PASS. GATE-U1 still open.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J4-CREATE-SHOP-2026-09-03.txt");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9254), b: 9255 };

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

async function keyEvent(ws, id, type, key, code, vk) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type,
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
  });
}

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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j4-${port}-`));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      "--disable-gpu",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--window-size=1280,720",
      url,
    ],
    { stdio: "ignore" },
  );
  return chrome;
}

const SNAP = `(() => {
  const markers = [...document.querySelectorAll('[data-testid^="shop-marker-"]')].map((el) => ({
    id: el.getAttribute("data-testid"),
    shop: el.getAttribute("data-shop-id"),
    source: el.getAttribute("data-source"),
    name: el.textContent.replace(/\\s+/g, " ").trim(),
    lon: el.getAttribute("data-lon"),
    lat: el.getAttribute("data-lat"),
  }));
  const names = [...document.querySelectorAll('[data-testid="public-shop-names"] [data-shop]')].map((el) => ({
    shop: el.getAttribute("data-shop"),
    source: el.getAttribute("data-source"),
    text: el.textContent.replace(/\\s+/g, " ").trim(),
  }));
  const listings = [...document.querySelectorAll('[data-testid="shop-listings"] [data-listing]')].map((el) => ({
    id: el.getAttribute("data-listing"),
    kind: el.getAttribute("data-kind"),
    status: el.getAttribute("data-status"),
    source: el.getAttribute("data-source"),
    text: el.textContent.replace(/\\s+/g, " ").trim(),
  }));
  const result = document.querySelector('[data-testid="create-shop-result"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  return {
    title: document.title,
    href: location.href,
    identitySigned: document.querySelector('[data-testid="demo-identity"]')?.getAttribute("data-signed-in") ?? "",
    identity: document.querySelector('[data-testid="demo-identity"]')?.textContent ?? "",
    publicCount: Number(document.querySelector('[data-testid="public-shop-count"]')?.getAttribute("data-count") ?? "-1"),
    shopRange: document.querySelector('[data-testid="shop-range"]')?.textContent ?? "",
    stallHint: document.querySelector('[data-testid="stall-hint"]')?.textContent ?? "",
    markers,
    names,
    listings,
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? null,
    createForm: Boolean(document.querySelector('[data-testid="create-shop-form"]')),
    become: Boolean(document.querySelector('[data-testid="become-demo-owner"]')),
    leave: Boolean(document.querySelector('[data-testid="leave-demo-owner"]')),
    result: result
      ? {
          status: result.getAttribute("data-status"),
          shop: result.getAttribute("data-shop"),
          listing: result.getAttribute("data-listing"),
          text: result.textContent.replace(/\\s+/g, " ").trim(),
        }
      : null,
    goods: [...document.querySelectorAll('[data-testid="goods-list"] button')].map((el) =>
      el.textContent.replace(/\\s+/g, " ").trim(),
    ),
    daDang: /đã đăng/i.test(document.body.innerText),
    googleOidc: /sign in with google|oidc login/i.test(document.body.innerText),
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.textContent ?? "",
    notPlanPass: /NOT_PLAN_PASS/.test(document.body.innerText),
  };
})()`;

async function waitSnap(ws, startId, pred, tries = 24, delay = 300) {
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

async function resetBus() {
  const origin = PLAYER.replace(/\/$/, "");
  await fetch(`${origin}/demo-bus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      v: 1,
      kind: "local-demo-bus",
      not_presence_server: true,
      not_plan_pass: true,
      catalog_clear: true,
      catalog: {
        v: 1,
        kind: "local-demo-shops",
        shops: [],
        listings: [],
        updated_at: Date.now(),
        not_plan_pass: true,
      },
    }),
  });
}

async function blur(ws, id) {
  await evalExpr(
    ws,
    id,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.querySelector(".maplibregl-canvas")?.focus();
      document.body.click();
      return true;
    })()`,
  );
}

const chromes = [];
let report;
try {
  await resetBus();
  chromes.push(launchChrome(PORTS.a, `${PLAYER}?seat=a`));
  chromes.push(launchChrome(PORTS.b, `${PLAYER}?seat=b`));
  const a = await connectPage(PORTS.a);
  const b = await connectPage(PORTS.b);
  await cdp(a.ws, 1, "Runtime.enable");
  await cdp(a.ws, 2, "Page.enable");
  await cdp(b.ws, 1, "Runtime.enable");
  await cdp(b.ws, 2, "Page.enable");
  await cdp(a.ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(b.ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(a.ws, 4, "Page.navigate", { url: `${PLAYER}?seat=a` });
  await cdp(b.ws, 4, "Page.navigate", { url: `${PLAYER}?seat=b` });
  await sleep(2400);

  const homeA = await evalExpr(a.ws, 10, SNAP);
  await evalExpr(a.ws, 9, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(a.ws, 11, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
  await sleep(250);
  const asOwner = await evalExpr(a.ws, 12, SNAP);
  await evalExpr(a.ws, 13, `document.querySelector('[data-testid="create-shop-submit"]')?.click(); true`);
  await sleep(400);
  const created = await evalExpr(a.ws, 14, SNAP);

  await evalExpr(a.ws, 15, `document.querySelector('[data-testid="leave-demo-owner"]')?.click(); true`);
  await sleep(250);
  const left = await evalExpr(a.ws, 16, SNAP);

  await blur(a.ws, 17);
  await sleep(150);
  await keyEvent(a.ws, 18, "keyDown", "e", "KeyE", 69);
  await keyEvent(a.ws, 19, "keyUp", "e", "KeyE", 69);
  await sleep(450);
  const aOpened = await evalExpr(a.ws, 20, SNAP);

  const { snap: guestB, nextId: bId } = await waitSnap(
    b.ws,
    10,
    (snap) =>
      snap.markers.length >= 2 &&
      snap.names.some((row) => row.shop === "shop-lantern-fish") &&
      snap.names.some((row) => row.shop?.startsWith("shop-local-")),
  );
  await blur(b.ws, bId);
  await sleep(150);
  await keyEvent(b.ws, bId + 1, "keyDown", "e", "KeyE", 69);
  await keyEvent(b.ws, bId + 2, "keyUp", "e", "KeyE", 69);
  await sleep(450);
  const bOpened = await evalExpr(b.ws, bId + 3, SNAP);

  await evalExpr(a.ws, 21, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(250);
  await blur(a.ws, 22);
  await keyEvent(a.ws, 23, "keyDown", "w", "KeyW", 87);
  let walkSeq = 30;
  let walking = left;
  const walkDeadline = Date.now() + 20000;
  while (Date.now() < walkDeadline) {
    await sleep(400);
    walking = await evalExpr(a.ws, walkSeq, SNAP);
    walkSeq += 1;
    if (/Quầy Cá Đèn Lồng/.test(walking.stallHint) && /Press E/.test(walking.stallHint)) {
      break;
    }
    await keyEvent(a.ws, walkSeq, "keyDown", "w", "KeyW", 87);
    walkSeq += 1;
  }
  await keyEvent(a.ws, walkSeq, "keyUp", "w", "KeyW", 87);
  walkSeq += 1;
  await sleep(200);
  await keyEvent(a.ws, walkSeq, "keyDown", "e", "KeyE", 69);
  walkSeq += 1;
  await keyEvent(a.ws, walkSeq, "keyUp", "e", "KeyE", 69);
  walkSeq += 1;
  await sleep(450);
  const lanternOpen = await evalExpr(a.ws, walkSeq, SNAP);

  await evalExpr(a.ws, walkSeq + 1, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(200);
  await evalExpr(a.ws, walkSeq + 2, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
  await sleep(200);
  await evalExpr(a.ws, walkSeq + 3, `document.querySelector('[data-testid="network-cut-sim"]')?.click(); true`);
  await sleep(150);
  await evalExpr(
    a.ws,
    walkSeq + 4,
    `(() => {
      const name = document.querySelector('[data-testid="create-shop-name"]');
      const good = document.querySelector('[data-testid="create-shop-good"]');
      if (name) { name.focus(); name.value = "Quầy Nháp"; name.dispatchEvent(new Event("input", { bubbles: true })); }
      if (good) { good.focus(); good.value = "Sách nháp"; good.dispatchEvent(new Event("input", { bubbles: true })); }
      return true;
    })()`,
  );
  await sleep(150);
  await evalExpr(a.ws, walkSeq + 5, `document.querySelector('[data-testid="create-shop-submit"]')?.click(); true`);
  await sleep(350);
  const queued = await evalExpr(a.ws, walkSeq + 6, SNAP);

  const playerShopId = created.result?.shop ?? left.names.find((row) => row.shop?.startsWith("shop-local-"))?.shop;
  const createOk =
    created.result?.status === "published" &&
    Boolean(playerShopId) &&
    created.markers.length >= 2 &&
    created.names.some((row) => row.shop === "shop-lantern-fish") &&
    created.names.some((row) => row.shop === playerShopId) &&
    created.goods.some((text) => /Phở bò/.test(text));
  const persistOk =
    left.identitySigned === "no" &&
    left.become === true &&
    left.markers.length >= 2 &&
    left.names.some((row) => row.shop === playerShopId) &&
    left.publicCount >= 2;
  const aWalkOk =
    aOpened.shopPanel &&
    aOpened.shopPanelId === playerShopId &&
    aOpened.listings.some((row) => /Phở bò/.test(row.text) && row.status === "published");
  const secondCtxOk =
    guestB.markers.length >= 2 &&
    guestB.names.some((row) => row.shop === "shop-lantern-fish") &&
    guestB.names.some((row) => row.shop === playerShopId) &&
    bOpened.shopPanel &&
    bOpened.shopPanelId === playerShopId &&
    bOpened.listings.some((row) => /Phở bò/.test(row.text));
  const twoShopsOk =
    lanternOpen.shopPanel &&
    lanternOpen.shopPanelId === "shop-lantern-fish" &&
    lanternOpen.listings.some((row) => /Cá nục/.test(row.text));
  const queueOk =
    queued.result?.status === "draft" &&
    /Chưa đăng/.test(queued.result?.text ?? "") &&
    queued.daDang === false &&
    queued.markers.filter((row) => row.shop !== playerShopId && row.source === "local-demo").length === 0;
  const honestyOk =
    /Chủ quầy \(máy này\)/.test(asOwner.identity + (asOwner.createForm ? " form" : "")) &&
    homeA.googleOidc === false &&
    created.notPlanPass === true &&
    /not a city shop server/i.test(homeA.honesty + created.honesty);

  report = {
    run_id: "HH3D-J4-20260903-ASIA-SAIGON-01",
    player: PLAYER,
    verdict:
      createOk && persistOk && aWalkOk && secondCtxOk && twoShopsOk && queueOk && honestyOk
        ? "J4_OBSERVED"
        : "J4_REWORK",
    not_plan_pass: true,
    not_m1_tick: true,
    createOk,
    persistOk,
    aWalkOk,
    secondCtxOk,
    twoShopsOk,
    queueOk,
    honestyOk,
    playerShopId: playerShopId ?? null,
    homeA: { publicCount: homeA.publicCount, markers: homeA.markers.map((row) => row.shop) },
    created: {
      status: created.result?.status ?? null,
      shop: created.result?.shop ?? null,
      markers: created.markers.map((row) => row.shop),
    },
    left: { identitySigned: left.identitySigned, markers: left.markers.map((row) => row.shop) },
    aOpened: { shop: aOpened.shopPanelId, listings: aOpened.listings.map((row) => row.text) },
    guestB: { publicCount: guestB.publicCount, markers: guestB.markers.map((row) => row.shop) },
    bOpened: { shop: bOpened.shopPanelId, listings: bOpened.listings.map((row) => row.text) },
    lanternOpen: { shop: lanternOpen.shopPanelId },
    queued: queued.result,
  };
  a.ws.close();
  b.ws.close();
} finally {
  for (const chrome of chromes) {
    chrome.kill();
  }
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
if (!report || report.verdict !== "J4_OBSERVED") {
  process.exitCode = 1;
}
