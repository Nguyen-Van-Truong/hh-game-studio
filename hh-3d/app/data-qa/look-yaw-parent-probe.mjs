/**
 * Parent visual check. Does not recycle 4175. Not a critic TICK.
 * Ports 10022 (A) and 10024 (B).
 */
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PLAYER = "http://127.0.0.1:4175/";
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "look-yaw-parent-shots");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdp(ws, id, method, params) {
  return new Promise((resolve, reject) => {
    const onMsg = (event) => {
      const msg = JSON.parse(typeof event.data === "string" ? event.data : String(event.data));
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

async function evalExpr(ws, id, expression) {
  const result = await cdp(ws, id, "Runtime.evaluate", { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

const SNAP = `(() => {
  const play = document.querySelector('[data-testid="play-view"]');
  const help = document.querySelector('[data-testid="avatar-status"]');
  const conn = document.querySelector('[data-testid="hud-connection"], [data-connection]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  if (menu && menu.getAttribute("data-open") === "yes") {
    const close = document.querySelector('[data-testid="menu-close"], [data-testid="play-menu"] button');
    close?.click();
  }
  return {
    ready: play?.getAttribute("data-play-ready") ?? "",
    heading: play?.getAttribute("data-heading") ?? proof?.getAttribute("data-heading") ?? "",
    camYaw: play?.getAttribute("data-cam-yaw") ?? proof?.getAttribute("data-cam-yaw") ?? "",
    look: play?.getAttribute("data-look") ?? proof?.getAttribute("data-look") ?? "",
    connection: conn?.textContent?.trim() ?? "",
    help: (help?.textContent ?? "").replace(/\\s+/g, " ").trim(),
  };
})()`;

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-look-parent-${port}-`));
  return spawn(
    CHROME,
    [
      "--headless=new",
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

async function connectPage(port) {
  const deadline = Date.now() + 25000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await res.json();
      const page = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) {
        const ws = new WebSocket(page.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => {
          ws.addEventListener("open", resolve);
          ws.addEventListener("error", reject);
        });
        return ws;
      }
    } catch {
      /* retry */
    }
    await sleep(200);
  }
  throw new Error(`no CDP page on ${port}`);
}

async function shot(ws, id, path) {
  const raw = await cdp(ws, id, "Page.captureScreenshot", { format: "png" });
  writeFileSync(path, Buffer.from(raw.data, "base64"));
}

async function holdA(ws, id, ms) {
  await cdp(ws, id, "Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "a",
    code: "KeyA",
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65,
  });
  await cdp(ws, id + 1, "Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key: "a",
    code: "KeyA",
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65,
  });
  await sleep(ms);
  await cdp(ws, id + 2, "Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "a",
    code: "KeyA",
    windowsVirtualKeyCode: 65,
    nativeVirtualKeyCode: 65,
  });
}

async function dragLeft(ws, id) {
  const box = await evalExpr(
    ws,
    id,
    `(() => {
      const c = document.querySelector("canvas");
      const r = c.getBoundingClientRect();
      return { x: r.left + r.width * 0.55, y: r.top + r.height * 0.45 };
    })()`,
  );
  await cdp(ws, id + 1, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: box.x,
    y: box.y,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
  await sleep(40);
  await cdp(ws, id + 2, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: box.x - 140,
    y: box.y,
    button: "right",
    buttons: 2,
  });
  await sleep(40);
  await cdp(ws, id + 3, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: box.x - 140,
    y: box.y,
    button: "right",
    clickCount: 1,
  });
}

async function runSeat(seat, port) {
  mkdirSync(OUT, { recursive: true });
  const chrome = launchChrome(port, `${PLAYER}?seat=${seat}`);
  const ws = await connectPage(port);
  await cdp(ws, 1, "Runtime.enable");
  await cdp(ws, 2, "Page.enable");
  let snap = null;
  for (let i = 0; i < 40; i += 1) {
    snap = await evalExpr(ws, 10 + i, SNAP);
    if (snap?.ready === "1" || snap?.heading) break;
    await sleep(250);
  }
  const before = snap;
  await shot(ws, 80, join(OUT, `${seat}-before.png`));
  await holdA(ws, 90, 500);
  await sleep(200);
  const afterA = await evalExpr(ws, 100, SNAP);
  await shot(ws, 101, join(OUT, `${seat}-after-A.png`));
  await dragLeft(ws, 110);
  await sleep(200);
  const afterMouse = await evalExpr(ws, 120, SNAP);
  await shot(ws, 121, join(OUT, `${seat}-after-mouse-left.png`));
  ws.close();
  chrome.kill();
  return { seat, before, afterA, afterMouse };
}

const a = await runSeat("a", 10022);
const b = await runSeat("b", 10024);
writeFileSync(join(OUT, "result.json"), JSON.stringify({ a, b }, null, 2));
console.log(JSON.stringify({ a, b }, null, 2));
