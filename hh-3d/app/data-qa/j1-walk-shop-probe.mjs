/**
 * J1 stroll → at-the-stall (10 m) → E opens Quầy Cá Đèn Lồng on existing 4175.
 * Walks past the old 20 m bubble. Far E stays closed. Near E opens.
 * After E, shop name + fish + bag bbox must sit in the 1280×720 viewport
 * (top < 720, visible) without scrolling the sidebar.
 * Close keeps/restores camera follow so the avatar stays on screen.
 * NOT_PLAN_PASS. GATE-U1 still open. Does not start a second preview.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9242);
const CHROME =
  process.env.HH_CHROME ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "J1-WALK-SHOP-2026-09-03.txt");
const M_PER_DEG_LAT = 111320;
const NEARBY_SHOP_M = 10;
const STREET_BUBBLE_M = 20;

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
  const avatar = document.querySelector('[data-testid="self-avatar"]');
  const remote = document.querySelectorAll('[data-remote-avatar]');
  const listings = [...document.querySelectorAll('[data-testid="shop-listings"] [data-listing]')].map((el) => ({
    id: el.getAttribute("data-listing"),
    kind: el.getAttribute("data-kind"),
    text: el.textContent.replace(/\\s+/g, " ").trim(),
  }));
  const rangeEl = document.querySelector('[data-testid="shop-range"]');
  return {
    title: document.title,
    href: location.href,
    honesty: document.querySelector('[data-testid="honesty-banner"]')?.innerText ?? "",
    mode: document.querySelector('[data-testid="presence-mode"]')?.textContent ?? "",
    people: document.querySelector('[data-testid="people-layer"]')?.textContent ?? "",
    onlineDisabled: document.querySelector('[data-testid="online-btn"]')?.disabled ?? null,
    avatar: avatar
      ? {
          pose: avatar.dataset.pose,
          heading: avatar.dataset.heading,
          lon: avatar.dataset.lon,
          lat: avatar.dataset.lat,
        }
      : null,
    avatarStatus: document.querySelector('[data-testid="avatar-status"]')?.textContent ?? "",
    remoteCount: remote.length,
    shopMarker: Boolean(document.querySelector('[data-testid="shop-marker-shop-lantern-fish"]')),
    shopPanel: Boolean(document.querySelector('[data-testid="shop-panel"]')),
    owner: document.querySelector('[data-testid="owner-presence"]')?.textContent ?? "",
    ownerSimCopy: document.querySelector(".owner-sim")?.textContent ?? "",
    listings,
    shopSeat: (() => {
      const boxOf = (el) => {
        if (!el) {
          return null;
        }
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        const vh = window.innerHeight;
        const visible =
          r.width > 0 &&
          r.height > 0 &&
          cs.display !== "none" &&
          cs.visibility !== "hidden" &&
          Number(cs.opacity) > 0;
        return {
          top: Number(r.top.toFixed(1)),
          bottom: Number(r.bottom.toFixed(1)),
          left: Number(r.left.toFixed(1)),
          width: Number(r.width.toFixed(1)),
          height: Number(r.height.toFixed(1)),
          display: cs.display,
          visibility: cs.visibility,
          opacity: Number(cs.opacity),
          visible,
          inViewport: visible && r.top >= 0 && r.top < 720 && r.top < vh && r.bottom > 0,
        };
      };
      return {
        vh: window.innerHeight,
        panel: boxOf(document.querySelector('[data-testid="shop-panel"]')),
        listings: boxOf(document.querySelector('[data-testid="shop-listings"]')),
        fish: boxOf(document.querySelector('[data-testid="shop-listings"] [data-kind="fish"]')),
        bag: boxOf(document.querySelector('[data-testid="shop-listings"] [data-kind="bag"]')),
      };
    })(),
    draftShown: /Nháp chưa đăng/.test(document.body.innerText),
    goods: [...document.querySelectorAll('[data-testid="goods-list"] button')].map((el) =>
      el.textContent.replace(/\\s+/g, " ").trim(),
    ),
    nearby: document.querySelector('[data-testid="open-nearby-shop"]')?.textContent ?? null,
    stallHint: document.querySelector('[data-testid="stall-hint"]')?.textContent ?? "",
    shopRange: rangeEl?.textContent ?? "",
    shopRangeM: rangeEl?.getAttribute("data-range") ? Number(rangeEl.getAttribute("data-range")) : null,
    interactDisabled: document.querySelector('[data-testid="walk-interact"]')?.disabled ?? null,
    followOn: document.querySelector('[data-testid="recenter-avatar"]')?.getAttribute("data-follow") === "on",
    followLabel: document.querySelector('[data-testid="recenter-avatar"]')?.textContent ?? "",
    avatarOnScreen: (() => {
      if (!avatar) {
        return false;
      }
      const r = avatar.getBoundingClientRect();
      return (
        r.width > 0 &&
        r.height > 0 &&
        r.right > 0 &&
        r.bottom > 0 &&
        r.left < window.innerWidth &&
        r.top < window.innerHeight
      );
    })(),
    canvas: Boolean(document.querySelector(".maplibregl-canvas")),
  };
})()`;

function walkMeters(from, to) {
  if (!from || !to) {
    return null;
  }
  const midLat = (Number(from.lat) + Number(to.lat)) / 2;
  const east = (Number(to.lon) - Number(from.lon)) * (M_PER_DEG_LAT * Math.cos((midLat * Math.PI) / 180));
  const north = (Number(to.lat) - Number(from.lat)) * M_PER_DEG_LAT;
  return Math.hypot(east, north);
}

const profile = mkdtempSync(join(tmpdir(), "hh-world-j1-"));
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
  await evalExpr(
    ws,
    5,
    `document.querySelector(".maplibregl-canvas")?.focus(); document.body.click(); true`,
  );
  const home = await evalExpr(ws, 10, SNAP);

  await keyEvent(ws, 11, "keyDown", "e", "KeyE", 69);
  await keyEvent(ws, 12, "keyUp", "e", "KeyE", 69);
  await sleep(250);
  const farE = await evalExpr(ws, 13, SNAP);

  await keyEvent(ws, 14, "keyDown", "w", "KeyW", 87);
  const walkStarted = Date.now();
  let walking = home;
  let streetE = null;
  let walkSeq = 20;
  const walkDeadline = Date.now() + 28000;
  while (Date.now() < walkDeadline) {
    await sleep(400);
    walking = await evalExpr(ws, walkSeq, SNAP);
    walkSeq += 1;
    if (
      !streetE &&
      typeof walking.shopRangeM === "number" &&
      walking.shopRangeM <= STREET_BUBBLE_M + 1 &&
      walking.shopRangeM > NEARBY_SHOP_M &&
      walking.nearby === null
    ) {
      await keyEvent(ws, walkSeq, "keyDown", "e", "KeyE", 69);
      walkSeq += 1;
      await keyEvent(ws, walkSeq, "keyUp", "e", "KeyE", 69);
      walkSeq += 1;
      await sleep(200);
      streetE = await evalExpr(ws, walkSeq, SNAP);
      walkSeq += 1;
    }
    if (walking.nearby) {
      break;
    }
    await keyEvent(ws, walkSeq, "keyDown", "w", "KeyW", 87);
    walkSeq += 1;
  }
  const walkMs = Date.now() - walkStarted;
  await keyEvent(ws, walkSeq, "keyUp", "w", "KeyW", 87);
  walkSeq += 1;
  await sleep(250);
  const atStall = await evalExpr(ws, walkSeq, SNAP);
  walkSeq += 1;

  await keyEvent(ws, walkSeq, "keyDown", "e", "KeyE", 69);
  walkSeq += 1;
  await keyEvent(ws, walkSeq, "keyUp", "e", "KeyE", 69);
  walkSeq += 1;
  await sleep(450);
  const shopOpen = await evalExpr(ws, walkSeq, SNAP);
  walkSeq += 1;

  const ownerWasOn = await evalExpr(
    ws,
    walkSeq,
    `(() => {
      const box = document.querySelector('[data-testid="owner-offline-sim"]');
      const before = box?.checked ?? null;
      if (box && box.checked) box.click();
      return before;
    })()`,
  );
  walkSeq += 1;
  await sleep(150);
  const ownerLabelOff = await evalExpr(ws, walkSeq, SNAP);
  walkSeq += 1;
  await evalExpr(
    ws,
    walkSeq,
    `(() => {
      const box = document.querySelector('[data-testid="owner-offline-sim"]');
      if (box && !box.checked) box.click();
      return true;
    })()`,
  );
  walkSeq += 1;
  await sleep(150);
  const ownerOff = await evalExpr(ws, walkSeq, SNAP);
  walkSeq += 1;

  await evalExpr(
    ws,
    walkSeq,
    `document.querySelector('[data-testid="close-shop"]')?.click(); true`,
  );
  await sleep(450);
  const afterClose = await evalExpr(ws, walkSeq + 1, SNAP);

  const moved = home.avatar && atStall.avatar
    ? {
        dLon: Number(atStall.avatar.lon) - Number(home.avatar.lon),
        dLat: Number(atStall.avatar.lat) - Number(home.avatar.lat),
        meters: walkMeters(home.avatar, atStall.avatar),
      }
    : null;
  const walkOk =
    Boolean(home.avatar) &&
    Boolean(moved) &&
    moved.meters > 16 &&
    walkMs > 8000 &&
    walking.avatar?.pose === "walk";
  const farEOk =
    farE.shopPanel === false &&
    farE.nearby === null &&
    streetE !== null &&
    streetE.shopPanel === false &&
    streetE.nearby === null &&
    typeof streetE.shopRangeM === "number" &&
    streetE.shopRangeM > NEARBY_SHOP_M &&
    streetE.shopRangeM <= STREET_BUBBLE_M + 1.5;
  const nearbyOk =
    Boolean(atStall.nearby) &&
    /Press E/i.test(atStall.stallHint) &&
    /at the stall/i.test(home.stallHint) &&
    typeof atStall.shopRangeM === "number" &&
    atStall.shopRangeM <= NEARBY_SHOP_M &&
    atStall.interactDisabled === false;
  const shopOk =
    shopOpen.shopPanel &&
    shopOpen.listings.some((row) => row.kind === "fish") &&
    shopOpen.listings.some((row) => row.kind === "bag") &&
    shopOpen.listings.every((row) => row.id !== "listing-draft-hidden") &&
    shopOpen.draftShown === false &&
    /stay open|still public/i.test(`${shopOpen.owner} ${ownerLabelOff.owner} ${ownerOff.owner}`) &&
    ownerLabelOff.shopPanel &&
    ownerLabelOff.listings.some((row) => row.kind === "fish") &&
    /does not take the public shelf down/i.test(ownerOff.ownerSimCopy);
  const modeOk =
    /Offline/.test(home.mode) &&
    home.onlineDisabled === true &&
    home.remoteCount === 0 &&
    /none/.test(home.people);
  const honestyOk =
    /Authored approximation/.test(home.honesty) &&
    /Map data as of/.test(home.honesty) &&
    /not a stranger crowd|no stranger crowd/i.test(home.honesty);
  const viaE = shopOpen.shopPanel && farE.shopPanel === false && Boolean(atStall.nearby);
  const seat = shopOpen.shopSeat;
  const shopSeatOk =
    Boolean(seat?.listings?.inViewport) &&
    Boolean(seat?.fish?.inViewport) &&
    Boolean(seat?.bag?.inViewport) &&
    seat.listings.top < 720 &&
    seat.fish.top < 720 &&
    seat.bag.top < 720 &&
    seat.listings.visible &&
    seat.fish.visible &&
    seat.bag.visible;
  const followOk =
    shopOpen.followOn === true &&
    shopOpen.avatarOnScreen === true &&
    afterClose.shopPanel === false &&
    afterClose.followOn === true &&
    afterClose.avatarOnScreen === true &&
    afterClose.followLabel.includes("Following you");

  report = {
    run_id: "HH3D-J1-20260903-ASIA-SAIGON-04",
    player: PLAYER,
    nearby_shop_m: NEARBY_SHOP_M,
    verdict: walkOk && farEOk && nearbyOk && shopOk && shopSeatOk && modeOk && honestyOk && viaE && followOk
      ? "J1_OBSERVED"
      : "J1_REWORK",
    not_plan_pass: true,
    opened: { via: viaE ? "e" : "none" },
    walkOk,
    farEOk,
    nearbyOk,
    shopOk,
    shopSeatOk,
    modeOk,
    honestyOk,
    followOk,
    walkMs,
    ownerWasOn,
    moved,
    home,
    farE: { shopPanel: farE.shopPanel, nearby: farE.nearby, stallHint: farE.stallHint },
    streetE: streetE
      ? {
          shopPanel: streetE.shopPanel,
          nearby: streetE.nearby,
          shopRangeM: streetE.shopRangeM,
        }
      : null,
    walking: {
      pose: walking.avatar?.pose,
      nearby: walking.nearby,
      shopRangeM: walking.shopRangeM,
    },
    atStall,
    shopOpen,
    ownerLabelOff: {
      shopPanel: ownerLabelOff.shopPanel,
      owner: ownerLabelOff.owner,
      listings: ownerLabelOff.listings.map((row) => row.id),
    },
    ownerOff,
    afterClose: {
      shopPanel: afterClose.shopPanel,
      avatar: afterClose.avatar,
      followOn: afterClose.followOn,
      followLabel: afterClose.followLabel,
      avatarOnScreen: afterClose.avatarOnScreen,
    },
    shopOpenFollow: {
      followOn: shopOpen.followOn,
      avatarOnScreen: shopOpen.avatarOnScreen,
    },
    shopOpenSeat: shopOpen.shopSeat,
  };
  ws.close();
} finally {
  chrome.kill();
}

writeFileSync(OUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
if (!report || report.verdict !== "J1_OBSERVED") {
  process.exitCode = 1;
}
