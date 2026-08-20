import { createHash } from "node:crypto";
import net from "node:net";

import type { SessionLog } from "../session/log.js";
import { evaluateHello, parseHello, type HelloErr, type HelloOk } from "./handshake.js";
import { listenLoopback } from "./loopback.js";

const WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
const OP_TEXT = 0x1;
const OP_CLOSE = 0x8;
const OP_PING = 0x9;
const OP_PONG = 0xa;

export interface PluginTransport {
  host: "127.0.0.1";
  port: number;
  close: () => Promise<void>;
}

export interface PluginTransportOpts {
  protocol: string;
  projectId: string;
  token: string;
  sessionId: string;
  log: SessionLog;
  heartbeatMs?: number;
}

interface SockState {
  socket: net.Socket;
  buf: Buffer;
  authed: boolean;
  closed: boolean;
}

function headerValue(head: string, name: string): string | undefined {
  const re = new RegExp(`^${name}:\\s*(.+)$`, "im");
  const match = head.match(re);
  return match?.[1]?.trim();
}

function acceptKey(key: string): string {
  return createHash("sha1").update(key + WS_GUID, "binary").digest("base64");
}

function sendFrame(socket: net.Socket, opcode: number, payload: Buffer): void {
  const ln = payload.length;
  let header: Buffer;
  if (ln < 126) {
    header = Buffer.alloc(2);
    header[0] = 0x80 | opcode;
    header[1] = ln;
  } else if (ln < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(ln, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeUInt32BE(0, 2);
    header.writeUInt32BE(ln, 6);
  }
  socket.write(Buffer.concat([header, payload]));
}

function sendText(socket: net.Socket, text: string): void {
  sendFrame(socket, OP_TEXT, Buffer.from(text, "utf8"));
}

function unmask(payload: Buffer, mask: Buffer): Buffer {
  const out = Buffer.alloc(payload.length);
  for (let i = 0; i < payload.length; i++) {
    const m = mask[i % 4];
    const p = payload[i];
    out[i] = (p ?? 0) ^ (m ?? 0);
  }
  return out;
}

function originAllowed(origin: string | undefined): boolean {
  if (origin === undefined || origin === "" || origin.toLowerCase() === "null") {
    return true;
  }
  try {
    const url = new URL(origin);
    if (url.protocol === "file:") {
      return true;
    }
    const host = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
    return host === "127.0.0.1" || host === "localhost" || host === "::1";
  } catch {
    return false;
  }
}

function takeFrame(
  buf: Buffer,
): { frame: { opcode: number; payload: Buffer } | null; rest: Buffer; reject?: boolean } {
  if (buf.length < 2) {
    return { frame: null, rest: buf };
  }
  const b0 = buf[0] ?? 0;
  const b1 = buf[1] ?? 0;
  const opcode = b0 & 0x0f;
  const masked = (b1 & 0x80) !== 0;
  if (!masked) {
    return { frame: null, rest: Buffer.alloc(0), reject: true };
  }
  let ln = b1 & 0x7f;
  let off = 2;
  if (ln === 126) {
    if (buf.length < 4) {
      return { frame: null, rest: buf };
    }
    ln = buf.readUInt16BE(2);
    off = 4;
  } else if (ln === 127) {
    if (buf.length < 10) {
      return { frame: null, rest: buf };
    }
    const hi = buf.readUInt32BE(2);
    const lo = buf.readUInt32BE(6);
    if (hi !== 0 || lo > 1_000_000) {
      return { frame: null, rest: Buffer.alloc(0) };
    }
    ln = lo;
    off = 10;
  }
  const maskLen = 4;
  if (buf.length < off + maskLen + ln) {
    return { frame: null, rest: buf };
  }
  const mask = buf.subarray(off, off + 4);
  const raw = buf.subarray(off + maskLen, off + maskLen + ln);
  const payload = unmask(raw, mask);
  return { frame: { opcode, payload }, rest: buf.subarray(off + maskLen + ln) };
}

function readHttpHead(socket: net.Socket): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    let buf = Buffer.alloc(0);
    const onData = (chunk: Buffer): void => {
      buf = Buffer.concat([buf, chunk]);
      if (buf.length > 16_384) {
        cleanup();
        reject(new Error("upgrade head too large"));
        return;
      }
      const idx = buf.indexOf("\r\n\r\n");
      if (idx >= 0) {
        cleanup();
        const head = buf.subarray(0, idx + 4);
        const rest = buf.subarray(idx + 4);
        if (rest.length > 0) {
          socket.unshift(rest);
        }
        resolve(head);
      }
    };
    const onErr = (err: Error): void => {
      cleanup();
      reject(err);
    };
    const cleanup = (): void => {
      socket.off("data", onData);
      socket.off("error", onErr);
    };
    socket.on("data", onData);
    socket.on("error", onErr);
  });
}

async function upgradeSocket(socket: net.Socket): Promise<boolean> {
  let headBuf: Buffer;
  try {
    headBuf = await readHttpHead(socket);
  } catch {
    socket.destroy();
    return false;
  }
  const head = headBuf.toString("utf8");
  const remote = socket.remoteAddress ?? "";
  if (remote !== "127.0.0.1" && remote !== "::1" && remote !== ":ffff:127.0.0.1") {
    socket.write("HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
    socket.destroy();
    return false;
  }
  const upgrade = (headerValue(head, "Upgrade") ?? "").toLowerCase();
  const connection = (headerValue(head, "Connection") ?? "").toLowerCase();
  const key = headerValue(head, "Sec-WebSocket-Key");
  const version = headerValue(head, "Sec-WebSocket-Version");
  const origin = headerValue(head, "Origin");
  if (upgrade !== "websocket" || !connection.includes("upgrade") || !key) {
    socket.write("HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
    socket.destroy();
    return false;
  }
  if (version !== undefined && version !== "13") {
    socket.write("HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
    socket.destroy();
    return false;
  }
  if (!originAllowed(origin)) {
    socket.write("HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
    socket.destroy();
    return false;
  }
  const accept = acceptKey(key);
  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\n" +
      "Upgrade: websocket\r\n" +
      "Connection: Upgrade\r\n" +
      `Sec-WebSocket-Accept: ${accept}\r\n` +
      "\r\n",
  );
  return true;
}

export async function startPluginTransport(opts: PluginTransportOpts): Promise<PluginTransport> {
  const heartbeatMs = opts.heartbeatMs ?? 5_000;
  const sockets = new Set<SockState>();
  let beats: ReturnType<typeof setInterval> | undefined;

  const server = net.createServer((socket) => {
    void handleConn(socket);
  });

  const handleConn = async (socket: net.Socket): Promise<void> => {
    const ok = await upgradeSocket(socket);
    if (!ok) {
      return;
    }
    const state: SockState = { socket, buf: Buffer.alloc(0), authed: false, closed: false };
    sockets.add(state);
    socket.on("data", (chunk) => {
      if (state.closed) {
        return;
      }
      state.buf = Buffer.concat([state.buf, chunk]);
      for (;;) {
        const taken = takeFrame(state.buf);
        state.buf = taken.rest;
        if (taken.reject) {
          state.closed = true;
          state.socket.end();
          sockets.delete(state);
          break;
        }
        if (!taken.frame) {
          break;
        }
        onFrame(state, taken.frame.opcode, taken.frame.payload);
      }
    });
    socket.on("close", () => {
      state.closed = true;
      sockets.delete(state);
    });
    socket.on("error", () => {
      state.closed = true;
      sockets.delete(state);
    });
  };

  const onFrame = (state: SockState, opcode: number, payload: Buffer): void => {
    if (opcode === OP_CLOSE) {
      sendFrame(state.socket, OP_CLOSE, Buffer.alloc(0));
      state.socket.end();
      return;
    }
    if (opcode === OP_PING) {
      sendFrame(state.socket, OP_PONG, payload);
      return;
    }
    if (opcode === OP_PONG) {
      return;
    }
    if (opcode !== OP_TEXT) {
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(payload.toString("utf8"));
    } catch {
      const err: HelloErr = {
        ok: false,
        type: "hello_err",
        error: { code: "E_INVALID_ENVELOPE", message: "hello must be JSON", path: "" },
      };
      sendText(state.socket, JSON.stringify(err));
      state.socket.end();
      return;
    }
    if (!state.authed) {
      const hello = parseHello(parsed);
      if ("ok" in hello && hello.ok === false) {
        sendText(state.socket, JSON.stringify(hello));
        state.socket.end();
        return;
      }
      const result: HelloOk | HelloErr = evaluateHello(hello as Exclude<typeof hello, HelloErr>, {
        protocol: opts.protocol,
        projectId: opts.projectId,
        token: opts.token,
        sessionId: opts.sessionId,
      });
      sendText(state.socket, JSON.stringify(result));
      if (!result.ok) {
        state.socket.end();
        return;
      }
      state.authed = true;
      opts.log.info("plugin session accepted");
      return;
    }
    if (parsed && typeof parsed === "object" && "type" in parsed && parsed.type === "ping") {
      sendText(state.socket, JSON.stringify({ type: "pong" }));
    }
  };

  const addr = await listenLoopback(server);
  beats = setInterval(() => {
    for (const state of sockets) {
      if (state.authed && !state.closed) {
        sendFrame(state.socket, OP_PING, Buffer.alloc(0));
      }
    }
  }, heartbeatMs);
  beats.unref();

  return {
    host: addr.host,
    port: addr.port,
    close: async () => {
      if (beats) {
        clearInterval(beats);
      }
      for (const state of sockets) {
        state.closed = true;
        state.socket.destroy();
      }
      sockets.clear();
      await new Promise<void>((resolve, reject) => {
        server.close((err) => {
          if (err) {
            reject(err);
            return;
          }
          resolve();
        });
      });
    },
  };
}
