/**
 * J2 open shop → local demo owner → list product → leave, on existing 4175.
 * NOT_PLAN_PASS. GATE-U1 still open. Does not start a second preview.
 * Does not claim R4-WP0B / OIDC. Does not start J3.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9244);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J2-LIST-PRODUCT-2026-09-03.txt");

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

async function connectPage() {
  const deadline = Date.now() + 20000;
  let last = null;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
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
  throw new Error(`no CDP page: ${JSON.stringify(last)}`);
}

const SNAP = `(() => {
  const listings = [...document.querySelectorAll('[data-testid="shop-listings"] [data-listing]')].map((el) => ({
    id: el.getAttribute("data-listing"),
    kind: el.getAttribute("data-kind"),
    status: el.getAttribute("data-status"),
    source: el.getAttribute("data-source"),
    text: el.textContent.replace(/\\s+/g, " ").trim(),
  }));
  const drafts = [...document.querySelectorAll('[data-testid="owner-drafts"] [data-draft]')].map((el) => ({
    id: el.getAttribute("data-draft"),
    status: el.getAttribute("data-status"),
    queued: el.getAttribute("data-queued"),
    text: el.textContent.replace(/\\s+/g, " ").trim(),
  }));
  const result = document.querySelector('[data-testid="list-result"]');
  const fish = document.querySelector('[data-testid="shop-listings"] [data-kind="fish"]');
  const bag = document.querySelector('[data-testid="shop-listings"] [data-kind="bag"]');
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: Number(r.top.toFixed(1)), bottom: Number(r.bottom.toFixed(1)), visible: r.height > 0 && r.top < 720 };
  };
  return {
    title: document.title,
    href: location.href,
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    people: document.querySelector('[data-testid="people-layer"]')?.textContent ?? "",
    identity: document.querySelector('[data-testid="demo-identity"]')?.textContent ?? "",
    identitySigned: document.querySelector('[data-testid="demo-identity"]')?.getAttribute("data-signed-in") ?? "",
    onlineDisabled: document.querySelector('[data-testid="online-btn"]')?.disabled ?? null,
    shopPanel: Boolean(document.querySelector('[data-testid="shop-panel"]')),
    become: Boolean(document.querySelector('[data-testid="become-demo-owner"]')),
    leave: Boolean(document.querySelector('[data-testid="leave-demo-owner"]')),
    form: Boolean(document.querySelector('[data-testid="list-product-form"]')),
    formNetwork: document.querySelector('[data-testid="list-product-form"]')?.getAttribute("data-network") ?? null,
    ownerLabel: document.querySelector('[data-testid="demo-owner-label"]')?.textContent ?? "",
    owner: document.querySelector('[data-testid="owner-presence"]')?.textContent ?? "",
    listings,
    drafts,
    result: result
      ? {
          status: result.getAttribute("data-status"),
          id: result.getAttribute("data-listing"),
          text: result.textContent.replace(/\\s+/g, " ").trim(),
        }
      : null,
    goods: [...document.querySelectorAll('[data-testid="goods-list"] button')].map((el) =>
      el.textContent.replace(/\\s+/g, " ").trim(),
    ),
    authoredDraftShown: /Nháp chưa đăng/.test(document.body.innerText),
    daDang: /đã đăng/i.test(document.body.innerText),
    googleOidc: /sign in with google|oidc login/i.test(document.body.innerText),
    seat: { fish: box(fish), bag: box(bag) },
  };
})()`;

const profile = mkdtempSync(join(tmpdir(), "hh-world-j2-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    "--disable-gpu",
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    `--window-size=1280,720`,
    PLAYER,
  ],
  { stdio: "ignore" },
);

let report;
try {
  const { ws } = await connectPage();
  await cdp(ws, 1, "Runtime.enable");
  await cdp(ws, 2, "Page.enable");
  await cdp(ws, 3, "Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 720,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp(ws, 4, "Page.navigate", { url: PLAYER });
  await sleep(2200);

  const home = await evalExpr(ws, 10, SNAP);
  await evalExpr(
    ws,
    9,
    `document.querySelector('[data-testid="play-menu-toggle"]')?.click(); true`,
  );
  await evalExpr(
    ws,
    11,
    `document.querySelector('[data-testid="goods-listing-morning-mackerel"]')?.click(); true`,
  );
  await sleep(400);
  const opened = await evalExpr(ws, 12, SNAP);

  await evalExpr(ws, 13, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
  await sleep(250);
  const asOwner = await evalExpr(ws, 14, SNAP);

  await evalExpr(ws, 15, `document.querySelector('[data-testid="list-submit"]')?.click(); true`);
  await sleep(350);
  const listed = await evalExpr(ws, 16, SNAP);

  await evalExpr(
    ws,
    17,
    `(() => {
      const box = document.querySelector('[data-testid="owner-offline-sim"]');
      if (box && box.checked) box.click();
      return true;
    })()`,
  );
  await sleep(150);
  const ownerOnlineLabel = await evalExpr(ws, 18, SNAP);
  await evalExpr(
    ws,
    19,
    `(() => {
      const box = document.querySelector('[data-testid="owner-offline-sim"]');
      if (box && !box.checked) box.click();
      return true;
    })()`,
  );
  await sleep(150);
  const ownerOfflineAgain = await evalExpr(ws, 20, SNAP);

  await evalExpr(ws, 21, `document.querySelector('[data-testid="leave-demo-owner"]')?.click(); true`);
  await sleep(250);
  const leftOwner = await evalExpr(ws, 22, SNAP);

  await evalExpr(ws, 23, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(300);
  const afterClose = await evalExpr(ws, 24, SNAP);

  await evalExpr(
    ws,
    25,
    `document.querySelector('[data-testid="goods-listing-morning-mackerel"]')?.click(); true`,
  );
  await sleep(350);
  const guestReopen = await evalExpr(ws, 26, SNAP);

  await evalExpr(ws, 27, `document.querySelector('[data-testid="become-demo-owner"]')?.click(); true`);
  await sleep(200);
  await evalExpr(
    ws,
    28,
    `document.querySelector('[data-testid="network-cut-sim"]')?.click(); true`,
  );
  await sleep(150);
  await evalExpr(ws, 29, `document.querySelector('[data-testid="list-kind-bag"]')?.click(); true`);
  await sleep(150);
  await evalExpr(ws, 30, `document.querySelector('[data-testid="list-submit"]')?.click(); true`);
  await sleep(350);
  const queued = await evalExpr(ws, 31, SNAP);

  await evalExpr(
    ws,
    32,
    `(() => {
      const box = document.querySelector('[data-testid="network-cut-sim"]');
      if (box && box.checked) box.click();
      return true;
    })()`,
  );
  await sleep(150);
  await evalExpr(ws, 33, `document.querySelector('[data-testid="retry-publish"]')?.click(); true`);
  await sleep(350);
  const retried = await evalExpr(ws, 34, SNAP);

  await evalExpr(ws, 35, `document.querySelector('[data-testid="leave-demo-owner"]')?.click(); true`);
  await sleep(200);
  await evalExpr(ws, 36, `document.querySelector('[data-testid="close-shop"]')?.click(); true`);
  await sleep(250);
  await evalExpr(
    ws,
    37,
    `document.querySelector('[data-testid="goods-listing-morning-mackerel"]')?.click(); true`,
  );
  await sleep(350);
  const finalGuest = await evalExpr(ws, 38, SNAP);

  const extraFish = listed.listings.find((row) => row.id?.startsWith("listing-local-") && row.kind === "fish");
  const queuedId = queued.result?.id;
  const queueOk =
    queued.result?.status === "draft" &&
    /Chưa đăng/.test(queued.result?.text ?? "") &&
    !/đã đăng/i.test(queued.result?.text ?? "") &&
    queued.listings.every((row) => row.id !== queuedId) &&
    queued.drafts.some((row) => row.id === queuedId && row.status === "draft");
  const publishOk =
    listed.result?.status === "published" &&
    Boolean(extraFish) &&
    extraFish.status === "published" &&
    /Cá thu thêm/.test(extraFish.text) &&
    /public/.test(extraFish.text) &&
    listed.formNetwork === "on" &&
    /Offline/.test(listed.mode);
  const persistOk =
    leftOwner.shopPanel &&
    leftOwner.become &&
    leftOwner.form === false &&
    leftOwner.listings.some((row) => row.id === extraFish?.id) &&
    afterClose.shopPanel === false &&
    afterClose.goods.some((text) => /Cá thu thêm/.test(text)) &&
    guestReopen.shopPanel &&
    guestReopen.identitySigned === "no" &&
    guestReopen.listings.some((row) => row.id === extraFish?.id) &&
    ownerOnlineLabel.listings.some((row) => row.id === extraFish?.id) &&
    ownerOfflineAgain.listings.some((row) => row.id === extraFish?.id);
  const retryOk =
    retried.listings.some((row) => row.id === queuedId && row.status === "published") &&
    retried.drafts.every((row) => row.id !== queuedId) &&
    finalGuest.listings.some((row) => row.id === queuedId) &&
    finalGuest.listings.some((row) => row.id === extraFish?.id) &&
    finalGuest.become &&
    finalGuest.drafts.length === 0;
  const honestyOk =
    opened.authoredDraftShown === false &&
    /Chủ quầy \(máy này\)/.test(asOwner.ownerLabel) &&
    /NOT a real account/.test(asOwner.ownerLabel) &&
    /NOT_PLAN_PASS/.test(asOwner.ownerLabel) &&
    asOwner.googleOidc === false &&
    /none/.test(home.people) &&
    home.onlineDisabled === true;
  const seatOk =
    Boolean(opened.seat.fish?.visible) &&
    Boolean(opened.seat.bag?.visible) &&
    opened.seat.fish.top < 720 &&
    opened.seat.bag.top < 720;

  report = {
    run_id: "HH3D-J2-20260903-ASIA-SAIGON-01",
    player: PLAYER,
    verdict:
      publishOk && persistOk && queueOk && retryOk && honestyOk && seatOk
        ? "J2_OBSERVED"
        : "J2_REWORK",
    not_plan_pass: true,
    not_r4_wp0b: true,
    publishOk,
    persistOk,
    queueOk,
    retryOk,
    honestyOk,
    seatOk,
    extraFishId: extraFish?.id ?? null,
    queuedId: queuedId ?? null,
    home: { mode: home.mode, identity: home.identity, people: home.people },
    opened,
    asOwner: {
      identitySigned: asOwner.identitySigned,
      ownerLabel: asOwner.ownerLabel,
      form: asOwner.form,
    },
    listed,
    leftOwner: {
      become: leftOwner.become,
      listings: leftOwner.listings.map((row) => row.id),
    },
    afterClose: { shopPanel: afterClose.shopPanel, goods: afterClose.goods },
    guestReopen: {
      identitySigned: guestReopen.identitySigned,
      listings: guestReopen.listings.map((row) => row.id),
    },
    queued,
    retried: {
      listings: retried.listings.map((row) => row.id),
      drafts: retried.drafts.map((row) => row.id),
    },
    finalGuest: {
      listings: finalGuest.listings.map((row) => ({ id: row.id, kind: row.kind })),
      become: finalGuest.become,
    },
  };
  ws.close();
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
if (!report || report.verdict !== "J2_OBSERVED") {
  process.exitCode = 1;
}
