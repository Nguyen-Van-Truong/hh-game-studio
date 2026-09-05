/**
 * Implementer post-remint CDP. Does not recycle 4175. Not a critic TICK.
 * Ports 10050 (A) and 10052 (B). Not 10014–10036.
 */
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = join(import.meta.dirname, "look-pitch-post-shots");
const EXPECT_JS = "/assets/index-BrVc4bRj.js";
const EXPECT_SHA = "c73e28b6ae16f3009d9af4908a1a05acd2acbbd0f2b350c47884fbe80c8c9df4";
const EXPECT_LEN = 2175994;
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
  const self = document.querySelector('[data-testid="self-avatar"]');
  const proof = document.querySelector('[data-testid="play-proof"]');
  const help = document.querySelector('[data-testid="avatar-status"]');
  const fps = document.querySelector('[data-testid="play-fps"]');
  const conn = document.querySelector('[data-testid="hud-connection"], [data-connection]');
  const menu = document.querySelector('[data-testid="play-menu"]');
  if (menu && menu.getAttribute("data-open") === "yes") {
    document.querySelector('[data-testid="menu-close"]')?.click();
  }
  return {
    ready: play?.getAttribute("data-play-ready") ?? "",
    look: (play ?? proof)?.getAttribute("data-look") ?? "",
    heading: Number(self?.dataset.heading ?? proof?.dataset.heading ?? NaN),
    lon: Number(self?.dataset.lon ?? NaN),
    lat: Number(self?.dataset.lat ?? NaN),
    onCanvas: self?.dataset.onCanvas ?? "",
    screenX: self?.dataset.screenX ?? "",
    screenY: self?.dataset.screenY ?? "",
    camY: Number(proof?.dataset.camY ?? NaN),
    camPitch: Number(proof?.dataset.camPitch ?? NaN),
    camLookY: Number(proof?.dataset.camLookY ?? NaN),
    fpsText: (fps?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    fpsClaim: fps?.dataset.claim ?? "",
    fpsNot60: fps?.dataset.not60 ?? "",
    fpsVal: fps?.dataset.fps ?? "",
    conn: (conn?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    help: (help?.textContent ?? "").replace(/\\s+/g, " ").trim(),
    proofFps: proof?.dataset.fpsClaim ?? "",
  };
})()`;

function launchChrome(port, url) {
  const profile = mkdtempSync(join(tmpdir(), `hh-look-post-${port}-`));
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

async function mouseLeft(ws, id, pixels) {
  const canvas = await evalExpr(
    ws,
    id,
    `(() => {
      const c = document.querySelector("canvas.play-canvas");
      if (!c) return null;
      const r = c.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    })()`,
  );
  await cdp(ws, id + 1, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: canvas.x,
    y: canvas.y,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
  await cdp(ws, id + 2, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: canvas.x - pixels,
    y: canvas.y,
    button: "right",
    buttons: 2,
    movementX: -pixels,
    movementY: 0,
  });
  await sleep(80);
  await cdp(ws, id + 3, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: canvas.x - pixels,
    y: canvas.y,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
}

async function pitchUp(ws, id, pixels) {
  const canvas = await evalExpr(
    ws,
    id,
    `(() => {
      const c = document.querySelector("canvas.play-canvas");
      if (!c) return null;
      const r = c.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    })()`,
  );
  await cdp(ws, id + 1, "Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: canvas.x,
    y: canvas.y,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
  await cdp(ws, id + 2, "Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: canvas.x,
    y: canvas.y - pixels,
    button: "right",
    buttons: 2,
    movementX: 0,
    movementY: -pixels,
  });
  await sleep(80);
  await cdp(ws, id + 3, "Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: canvas.x,
    y: canvas.y - pixels,
    button: "right",
    buttons: 2,
    clickCount: 1,
  });
}

async function runSeat(seat, port) {
  const url = `http://127.0.0.1:4175/?seat=${seat}`;
  const chrome = launchChrome(port, url);
  let ws;
  try {
    ws = await connectPage(port);
    await cdp(ws, 1, "Page.enable");
    await cdp(ws, 2, "Runtime.enable");
    let snap = null;
    for (let i = 0; i < 50; i += 1) {
      snap = await evalExpr(ws, 10 + i, SNAP);
      if (snap?.ready === "yes" && snap.onCanvas === "1") break;
      await sleep(200);
    }
    await shot(ws, 80, join(OUT, `${seat}-before.png`));
    const before = snap;
    await holdA(ws, 90, 900);
    await sleep(150);
    const afterA = await evalExpr(ws, 110, SNAP);
    await shot(ws, 111, join(OUT, `${seat}-after-A.png`));
    const headingBeforeMouse = afterA.heading;
    await mouseLeft(ws, 120, 140);
    await sleep(150);
    const afterMouse = await evalExpr(ws, 130, SNAP);
    await pitchUp(ws, 140, 240);
    await sleep(200);
    const afterPitch = await evalExpr(ws, 150, SNAP);
    await shot(ws, 151, join(OUT, `${seat}-pitch-up.png`));
    return {
      seat,
      before,
      afterA,
      afterMouse,
      afterPitch,
      headingFrozenOnA: before.heading === afterA.heading,
      dLon: afterA.lon - before.lon,
      dHeadingMouse: afterMouse.heading - headingBeforeMouse,
      bodyVisibleBefore: before.onCanvas === "1",
      bodyVisiblePitch: afterPitch.onCanvas === "1",
      lookYSky: afterPitch.camLookY > 6,
    };
  } finally {
    try {
      ws?.close();
    } catch {
      /* ignore */
    }
    chrome.kill();
  }
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const html = await fetch("http://127.0.0.1:4175/").then((r) => r.text());
  const jsName = (html.match(/\/assets\/index-[^"]+\.js/) ?? [""])[0];
  const jsBuf = Buffer.from(await fetch(`http://127.0.0.1:4175${jsName}`).then((r) => r.arrayBuffer()));
  const sha = createHash("sha256").update(jsBuf).digest("hex");
  const a = await runSeat("a", 10050);
  const b = await runSeat("b", 10052);
  const out = {
    hashOk: jsName === EXPECT_JS && sha === EXPECT_SHA && jsBuf.length === EXPECT_LEN,
    jsName,
    sha,
    len: jsBuf.length,
    a,
    b,
  };
  writeFileSync(join(OUT, "result.json"), JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
