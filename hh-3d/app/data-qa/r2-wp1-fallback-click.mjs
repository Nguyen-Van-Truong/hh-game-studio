const DEBUG_PORT = Number(process.env.HH_CDP_PORT || 9236);
const PLAYER = process.env.HH_PLAYER_URL || "http://127.0.0.1:4175/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
const targets = await res.json();
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve);
  ws.addEventListener("error", reject);
});
await cdp(ws, 1, "Runtime.enable");
await cdp(ws, 2, "Page.enable");
await cdp(ws, 3, "Emulation.setDeviceMetricsOverride", {
  width: 1280,
  height: 720,
  deviceScaleFactor: 1,
  mobile: false,
});
await cdp(ws, 4, "Page.navigate", { url: `${PLAYER}?place=place-market-hall` });
await sleep(1500);
const deep = await evalExpr(
  ws,
  5,
  `({
    href: location.href,
    fallback: document.querySelector('[data-testid="webgl-fallback"]')?.textContent?.trim() ?? null,
    canvas: Boolean(document.querySelector(".maplibregl-canvas")),
    list: [...document.querySelectorAll('[data-testid="place-list"] button')].map((el) => el.textContent.trim()),
    card: document.querySelector('[data-testid="place-card"]')?.textContent?.replace(/\\s+/g, " ").trim() ?? null,
    empty: document.querySelector('[data-testid="place-card-empty"]')?.textContent?.trim() ?? null,
    honesty: Boolean(document.querySelector('[data-testid="honesty-banner"]')),
    webgl: (() => {
      const c = document.createElement("canvas");
      return Boolean(c.getContext("webgl2") || c.getContext("webgl"));
    })(),
  })`,
);
await evalExpr(
  ws,
  6,
  `(() => { const close = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Close"); close?.click(); return Boolean(close); })()`,
);
await sleep(200);
const afterClose = await evalExpr(
  ws,
  7,
  `({
    card: document.querySelector('[data-testid="place-card"]')?.textContent ?? null,
    empty: Boolean(document.querySelector('[data-testid="place-card-empty"]')),
  })`,
);
const clicked = await evalExpr(
  ws,
  8,
  `(() => {
    const btn = [...document.querySelectorAll('[data-testid="place-list"] button')].find((el) =>
      el.textContent.includes("Clock Garden"),
    );
    btn?.click();
    return Boolean(btn);
  })()`,
);
await sleep(300);
const afterClick = await evalExpr(
  ws,
  9,
  `({
    href: location.href,
    card: document.querySelector('[data-testid="place-card"]')?.textContent?.replace(/\\s+/g, " ").trim() ?? null,
    empty: Boolean(document.querySelector('[data-testid="place-card-empty"]')),
    active: [...document.querySelectorAll('[data-testid="place-list"] button.active')].map((el) => el.textContent.trim()),
  })`,
);
ws.close();
console.log(JSON.stringify({ deep, afterClose, clicked, afterClick }, null, 2));
