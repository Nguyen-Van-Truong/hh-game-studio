import type net from "node:net";

import { E, typedError } from "../registry/errors.js";

export const LOOPBACK_HOST = "127.0.0.1" as const;
export const OS_ASSIGNED_PORT = 0 as const;

export type ListenFn = (opts: net.ListenOptions, cb: () => void) => net.Server;

export interface ListenDeps {
  listen?: ListenFn;
}

export function loopbackListenOptions(): net.ListenOptions {
  return { host: LOOPBACK_HOST, port: OS_ASSIGNED_PORT, exclusive: true };
}

export function assertLoopbackHost(host: string): void {
  if (host !== LOOPBACK_HOST) {
    throw typedError(E.E_BIND, "listen host must be loopback", "host");
  }
}

export function assertOsAssignedPort(port: number): void {
  if (port !== OS_ASSIGNED_PORT) {
    throw typedError(E.E_BIND, "listen port must be OS-assigned", "port");
  }
}

function isBusy(err: unknown): boolean {
  return Boolean(err && typeof err === "object" && "code" in err && err.code === "EADDRINUSE");
}

/**
 * Bind an existing net.Server to 127.0.0.1 with an OS-assigned port.
 * EADDRINUSE retries the same listen options (not a port walk).
 */
export async function listenLoopback(
  server: net.Server,
  deps?: ListenDeps,
): Promise<{ host: typeof LOOPBACK_HOST; port: number }> {
  const listenFn =
    deps?.listen ??
    ((opts: net.ListenOptions, cb: () => void) => server.listen(opts, cb));
  const opts = loopbackListenOptions();
  assertLoopbackHost(String(opts.host));
  assertOsAssignedPort(Number(opts.port));

  let lastErr: unknown;
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      await new Promise<void>((resolve, reject) => {
        const onErr = (err: Error): void => {
          server.off("listening", onListening);
          reject(err);
        };
        const onListening = (): void => {
          server.off("error", onErr);
          resolve();
        };
        server.once("error", onErr);
        server.once("listening", onListening);
        listenFn(opts, () => {
          /* 'listening' is the source of truth */
        });
      });
      const raw = server.address();
      if (!raw || typeof raw === "string") {
        server.close();
        throw typedError(E.E_BIND, "listen returned no TCP address", "listen");
      }
      if (raw.address !== LOOPBACK_HOST) {
        server.close();
        throw typedError(E.E_BIND, "listen address is not loopback", "host");
      }
      if (raw.port <= 0) {
        server.close();
        throw typedError(E.E_BIND, "listen port missing", "port");
      }
      return { host: LOOPBACK_HOST, port: raw.port };
    } catch (err) {
      lastErr = err;
      if (isBusy(err)) {
        continue;
      }
      throw err;
    }
  }
  throw typedError(E.E_BIND, "listen failed after EADDRINUSE retry", "listen");
}

/** Test/doctor hook: reject before any listen when the caller names a non-loopback host. */
export async function listenExplicit(
  server: net.Server,
  host: string,
  port: number,
  deps?: ListenDeps,
): Promise<{ host: typeof LOOPBACK_HOST; port: number }> {
  assertLoopbackHost(host);
  assertOsAssignedPort(port);
  return listenLoopback(server, deps);
}
