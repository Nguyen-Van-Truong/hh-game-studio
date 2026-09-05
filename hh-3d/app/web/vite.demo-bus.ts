import type { IncomingMessage, ServerResponse } from "node:http";
import type { Connect, Plugin } from "vite";
import { createThisPcStore, isLoopbackHost } from "./vite.this-pc-store.ts";

const store = createThisPcStore();

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk) => {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

async function handleDemoBus(req: IncomingMessage, res: ServerResponse, next: Connect.NextFunction) {
  const url = req.url ?? "";
  if (!url.startsWith("/demo-bus")) {
    next();
    return;
  }
  if (!isLoopbackHost(req.headers.host)) {
    res.statusCode = 403;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "loopback-only", bind: "127.0.0.1", not_wan: true }));
    return;
  }
  res.setHeader("Cache-Control", "no-store");
  if (req.method === "GET") {
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(store.snapshot()));
    return;
  }
  if (req.method === "POST") {
    try {
      const raw = await readBody(req);
      const body = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
      store.apply(body);
      res.statusCode = 204;
      res.end();
    } catch {
      res.statusCode = 400;
      res.end();
    }
    return;
  }
  next();
}

export function hhWorldDemoBus(): Plugin {
  return {
    name: "hh-world-demo-bus",
    configureServer(server) {
      server.middlewares.use(handleDemoBus);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handleDemoBus);
    },
  };
}
