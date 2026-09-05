/**
 * This-PC shared store on recycled 4175 loopback.
 * Two isolated browsers share published shops / friends / presence
 * without one tab's localStorage as the source of truth.
 * Draft ≠ posted. Offline hides bodies; shops stay.
 * NOT_PLAN_PASS. Not GATE-U1. Not WAN / other-PC.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J6-SHARED-SERVER-2026-09-03.txt");
const PORTS = { a: Number(process.env.HH_CDP_PORT_A || 9266), b: 9267 };
const ORIGIN = PLAYER.replace(/\/$/, "");
const SHOP_ID = "shop-local-sharedpc";
const LISTING_ID = "listing-local-sharedpc";

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
  const profile = mkdtempSync(join(tmpdir(), `hh-world-j6-${port}-`));
  return spawn(
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
}

const SNAP = `(() => {
  const markers = [...document.querySelectorAll('[data-testid^="shop-marker-"]')].map((el) => ({
    shop: el.getAttribute("data-shop-id"),
    source: el.getAttribute("data-source"),
    name: el.textContent.replace(/\\s+/g, " ").trim(),
  }));
  const people = [...document.querySelectorAll('[data-testid^="people-row-"]')].map((el) => ({
    seat: el.getAttribute("data-seat"),
    lon: el.getAttribute("data-lon"),
    lat: el.getAttribute("data-lat"),
  }));
  const remotes = [...document.querySelectorAll('[data-testid^="remote-avatar-"]')].map((el) => ({
    seat: el.getAttribute("data-seat"),
    lon: el.getAttribute("data-lon"),
    lat: el.getAttribute("data-lat"),
  }));
  const self = document.querySelector('[data-testid="self-avatar"]');
  const panel = document.querySelector('[data-testid="shop-panel"]');
  return {
    title: document.title,
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    remoteCount: Number(document.querySelector('[data-testid="people-layer"]')?.getAttribute("data-remote-count") ?? "-1"),
    publicCount: Number(document.querySelector('[data-testid="public-shop-count"]')?.getAttribute("data-count") ?? "-1"),
    markers,
    people,
    remotes,
    shopPanel: Boolean(panel),
    shopPanelId: panel?.getAttribute("data-shop") ?? null,
    listings: [...document.querySelectorAll('[data-testid="shop-listings"] [data-listing]')].map((el) => ({
      id: el.getAttribute("data-listing"),
      status: el.getAttribute("data-status"),
      text: el.textContent.replace(/\\s+/g, " ").trim(),
    })),
    result: document.querySelector('[data-testid="create-shop-result"]')
      ? {
          status: document.querySelector('[data-testid="create-shop-result"]').getAttribute("data-status"),
          shop: document.querySelector('[data-testid="create-shop-result"]').getAttribute("data-shop"),
          text: document.querySelector('[data-testid="create-shop-result"]').textContent.replace(/\\s+/g, " ").trim(),
        }
      : null,
    self: self
      ? { lon: self.getAttribute("data-lon"), lat: self.getAttribute("data-lat") }
      : null,
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.textContent ?? "",
    friendsHonesty: document.querySelector('[data-testid="friends-honesty"]')?.textContent ?? "",
    daDang: /đã đăng/i.test(document.body.innerText),
    notPlanPass: /NOT_PLAN_PASS/.test(document.body.innerText),
    acceptA: Boolean(document.querySelector('[data-testid="accept-friend-a"]')),
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

async function busGet() {
  const res = await fetch(`${ORIGIN}/demo-bus`, { cache: "no-store" });
  return { ok: res.ok, status: res.status, body: await res.json() };
}

async function busPost(body) {
  return fetch(`${ORIGIN}/demo-bus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      v: 1,
      kind: "local-demo-bus",
      not_presence_server: true,
      not_plan_pass: true,
      ...body,
    }),
  });
}

const chromes = [];
let report;
try {
  await busPost({
    catalog_clear: true,
    graph_clear: true,
    leave: "a",
  });
  await busPost({ leave: "b" });
  await busPost({ leave: "c" });

  const before = await busGet();
  await busPost({
    catalog: {
      v: 1,
      kind: "local-demo-shops",
      shops: [
        {
          v: 1,
          shop_id: SHOP_ID,
          owner_id: "owner-local-demo-machine",
          name: "Quầy Shared PC",
          description: "Player-opened shop on this machine. Sells Phở bò. Not a real storefront. NOT_PLAN_PASS.",
          place_id: "place-local-sharedpc",
          lon: 106.69804,
          lat: 10.77162,
          status: "published",
          owner_presence: "offline",
          updated_at: new Date().toISOString(),
          version: 1,
          world_id: "hh-world-ben-thanh-400m",
          source: "local-demo",
          sells: "Phở bò",
          not_plan_pass: true,
        },
        {
          v: 1,
          shop_id: "shop-local-draftleak",
          owner_id: "owner-local-demo-machine",
          name: "Quầy Nháp Leak",
          description: "Should not post. NOT_PLAN_PASS.",
          place_id: "place-local-draftleak",
          lon: 106.6982,
          lat: 10.7718,
          status: "draft",
          owner_presence: "offline",
          updated_at: new Date().toISOString(),
          version: 1,
          world_id: "hh-world-ben-thanh-400m",
          source: "local-demo",
          sells: "Sách nháp",
          not_plan_pass: true,
        },
      ],
      listings: [
        {
          v: 1,
          listing_id: LISTING_ID,
          shop_id: SHOP_ID,
          title: "Phở bò",
          description: "Local demo listing. Free-text sample. Not a real product.",
          kind: "other",
          price_label: "Liên hệ",
          status: "published",
          queued: false,
          idempotency_key: LISTING_ID,
          updated_at: new Date().toISOString(),
          version: 1,
          source: "local-demo",
          owner_id: "owner-local-demo-machine",
        },
        {
          v: 1,
          listing_id: "listing-local-draftleak",
          shop_id: "shop-local-draftleak",
          title: "Sách nháp",
          description: "Draft must not post.",
          kind: "other",
          price_label: "Liên hệ",
          status: "draft",
          queued: true,
          idempotency_key: "listing-local-draftleak",
          updated_at: new Date().toISOString(),
          version: 1,
          source: "local-demo",
          owner_id: "owner-local-demo-machine",
        },
      ],
      updated_at: Date.now(),
      not_plan_pass: true,
    },
  });
  const afterInject = await busGet();
  const shopIds = (afterInject.body.catalog?.shops ?? []).map((row) => row.shop_id);
  const listingIds = (afterInject.body.catalog?.listings ?? []).map((row) => row.listing_id);

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
  await sleep(600);
  for (const [ws, seat, base] of [
    [a.ws, "a", 10],
    [b.ws, "b", 10],
  ]) {
    await cdp(ws, base, "Storage.clearDataForOrigin", {
      origin: ORIGIN,
      storageTypes: "local_storage",
    });
    await cdp(ws, base + 1, "Page.navigate", { url: `${PLAYER}?seat=${seat}` });
  }
  await sleep(2600);

  const sawA = await waitSnap(a.ws, 20, (s) => s.markers.some((row) => row.shop === SHOP_ID));
  const sawB = await waitSnap(b.ws, 20, (s) => s.markers.some((row) => row.shop === SHOP_ID));

  await evalExpr(a.ws, 40, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await evalExpr(b.ws, 40, `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`);
  await sleep(200);
  await evalExpr(a.ws, 41, `document.querySelector('[data-testid="add-friend-b"]')?.click(); true`);
  await waitSnap(b.ws, 41, (s) => s.acceptA === true, 16, 250);
  await evalExpr(b.ws, 50, `document.querySelector('[data-testid="accept-friend-a"]')?.click(); true`);
  await evalExpr(a.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  await evalExpr(b.ws, 51, `document.querySelector('[data-testid="online-btn"]')?.click(); true`);
  const friendsA = await waitSnap(a.ws, 60, (s) => s.remoteCount === 1 && s.remotes.some((row) => row.seat === "b"));
  const friendsB = await waitSnap(b.ws, 60, (s) => s.remoteCount === 1 && s.remotes.some((row) => row.seat === "a"));

  const beforeWalk = friendsB.snap;
  await evalExpr(
    a.ws,
    80,
    `(() => {
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
      document.body.click();
      return true;
    })()`,
  );
  await sleep(150);
  await keyHold(a.ws, 81, "w", "KeyW", 87, 4000);
  const walkedB = await waitSnap(
    b.ws,
    80,
    (s) => {
      const remote = s.remotes.find((row) => row.seat === "a") ?? s.people.find((row) => row.seat === "a");
      const prev =
        beforeWalk?.remotes.find((row) => row.seat === "a") ?? beforeWalk?.people.find((row) => row.seat === "a");
      return remote && prev && Number(remote.lat) > Number(prev.lat) + 0.000008;
    },
    20,
    250,
  );

  await evalExpr(a.ws, 91, `document.querySelector('[data-testid="offline-btn"]')?.click(); true`);
  const offlineB = await waitSnap(b.ws, 91, (s) => s.remoteCount === 0, 16, 250);
  const shopsAfterOffline = await busGet();

  await evalExpr(a.ws, 100, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
  await sleep(150);
  await evalExpr(a.ws, 101, `document.querySelector('[data-testid="network-cut-sim"]')?.click(); true`);
  await sleep(100);
  await evalExpr(
    a.ws,
    102,
    `(() => {
      const name = document.querySelector('[data-testid="create-shop-name"]');
      const good = document.querySelector('[data-testid="create-shop-good"]');
      if (name) { name.focus(); name.value = "Quầy Nháp PC"; name.dispatchEvent(new Event("input", { bubbles: true })); }
      if (good) { good.focus(); good.value = "Sách nháp"; good.dispatchEvent(new Event("input", { bubbles: true })); }
      return true;
    })()`,
  );
  await evalExpr(a.ws, 103, `document.querySelector('[data-testid="create-shop-submit"]')?.click(); true`);
  await sleep(350);
  const drafted = await evalExpr(a.ws, 104, SNAP);
  const afterDraft = await busGet();
  const draftOnBus = (afterDraft.body.catalog?.shops ?? []).some((row) => row.shop_id === drafted.result?.shop);

  const busOk =
    before.ok &&
    before.body.this_pc === true &&
    before.body.bind === "127.0.0.1" &&
    before.body.not_wan === true &&
    before.body.persist === "catalog+graph" &&
    shopIds.includes(SHOP_ID) &&
    !shopIds.includes("shop-local-draftleak") &&
    listingIds.includes(LISTING_ID) &&
    !listingIds.includes("listing-local-draftleak");
  const twoBrowsersOk =
    sawA.snap.markers.some((row) => row.shop === SHOP_ID) &&
    sawB.snap.markers.some((row) => row.shop === SHOP_ID) &&
    !sawA.snap.markers.some((row) => row.shop === "shop-local-draftleak") &&
    !sawB.snap.markers.some((row) => row.shop === "shop-local-draftleak");
  const walkedRemote =
    walkedB.snap.remotes.find((row) => row.seat === "a") ?? walkedB.snap.people.find((row) => row.seat === "a");
  const startRemote =
    beforeWalk?.remotes.find((row) => row.seat === "a") ?? beforeWalk?.people.find((row) => row.seat === "a");
  const friendOk =
    friendsA.snap.remoteCount === 1 &&
    friendsB.snap.remoteCount === 1 &&
    Boolean(walkedRemote) &&
    Boolean(startRemote) &&
    Number(walkedRemote.lat) > Number(startRemote.lat);
  const offlineOk =
    offlineB.snap.remoteCount === 0 &&
    (shopsAfterOffline.body.catalog?.shops ?? []).some((row) => row.shop_id === SHOP_ID);
  const draftOk =
    drafted.result?.status === "draft" &&
    /Chưa đăng/.test(drafted.result?.text ?? "") &&
    drafted.daDang === false &&
    draftOnBus === false;
  const honestyOk =
    /4175|loopback|this PC/i.test(sawA.snap.honesty + (sawA.snap.friendsHonesty ?? "")) &&
    /NOT_PLAN_PASS/.test(sawA.snap.honesty) &&
    /not wan/i.test(`${sawA.snap.honesty} ${sawA.snap.friendsHonesty}`);

  report = {
    run_id: "HH3D-J6-20260903-ASIA-SAIGON-02",
    player: PLAYER,
    verdict:
      busOk && twoBrowsersOk && friendOk && offlineOk && draftOk && honestyOk
        ? "J6_SHARED_OK"
        : "J6_REWORK",
    not_plan_pass: true,
    not_gate_u1: true,
    not_wan: true,
    not_other_pc: true,
    busOk,
    twoBrowsersOk,
    friendOk,
    offlineOk,
    draftOk,
    honestyOk,
    bind: afterInject.body.bind,
    this_pc: afterInject.body.this_pc,
    shopIds,
    listingIds,
    sawA: sawA.snap.markers.map((row) => row.shop),
    sawB: sawB.snap.markers.map((row) => row.shop),
    friends: {
      a: friendsA.snap.remoteCount,
      b: friendsB.snap.remoteCount,
      walkedLat: walkedRemote?.lat ?? null,
      startLat: startRemote?.lat ?? null,
    },
    offlineB: offlineB.snap.remoteCount,
    drafted: drafted.result,
    draftOnBus,
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
if (!report || report.verdict !== "J6_SHARED_OK") {
  process.exitCode = 1;
}
