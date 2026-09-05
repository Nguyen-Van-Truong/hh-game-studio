import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export type SeatId = "a" | "b" | "c";

export type GraphOp = {
  op: "request" | "accept" | "unfriend";
  from: SeatId;
  to: SeatId;
};

export type SharedSnapshot = {
  v: 1;
  kind: "local-demo-bus";
  presence: Partial<Record<SeatId, unknown>>;
  graph: {
    v: 1;
    kind: "local-demo-friends";
    pairs: unknown[];
    updated_at: number;
    not_presence_server: true;
    not_plan_pass: true;
  };
  catalog: {
    v: 1;
    kind: "local-demo-shops";
    shops: unknown[];
    listings: unknown[];
    updated_at: number;
    not_plan_pass: true;
  };
  this_pc: true;
  bind: "127.0.0.1";
  not_wan: true;
  persist: "catalog+graph";
  presence_ephemeral: true;
  not_presence_server: true;
  not_plan_pass: true;
};

const SEATS: SeatId[] = ["a", "b", "c"];
const PRESENCE_TTL_MS = 10000;

function isSeatId(value: unknown): value is SeatId {
  return value === "a" || value === "b" || value === "c";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function rowId(row: unknown, key: string): string | null {
  const rec = asRecord(row);
  const id = rec?.[key];
  return typeof id === "string" && id.length > 0 ? id : null;
}

function isPublished(row: unknown): boolean {
  return asRecord(row)?.["status"] === "published";
}

function emptyGraph(updatedAt = 0) {
  return {
    v: 1 as const,
    kind: "local-demo-friends" as const,
    pairs: [] as unknown[],
    updated_at: updatedAt,
    not_presence_server: true as const,
    not_plan_pass: true as const,
  };
}

function emptyCatalog(updatedAt = 0) {
  return {
    v: 1 as const,
    kind: "local-demo-shops" as const,
    shops: [] as unknown[],
    listings: [] as unknown[],
    updated_at: updatedAt,
    not_plan_pass: true as const,
  };
}

function orderedPair(a: SeatId, b: SeatId): { left: SeatId; right: SeatId } | null {
  if (a === b) {
    return null;
  }
  if (!((a === "a" && b === "b") || (a === "b" && b === "a"))) {
    return null;
  }
  return a < b ? { left: a, right: b } : { left: b, right: a };
}

function pairKey(left: unknown, right: unknown): string {
  return `${String(left)}:${String(right)}`;
}

export function publishedOnly(shops: unknown[], listings: unknown[]): {
  shops: unknown[];
  listings: unknown[];
} {
  return {
    shops: shops.filter(isPublished),
    listings: listings.filter(isPublished),
  };
}

export function mergePublished(
  current: unknown[],
  incoming: unknown[],
  idKey: string,
): unknown[] {
  const map = new Map<string, unknown>();
  for (const row of current) {
    if (!isPublished(row)) {
      continue;
    }
    const id = rowId(row, idKey);
    if (id) {
      map.set(id, row);
    }
  }
  for (const row of incoming) {
    if (!isPublished(row)) {
      continue;
    }
    const id = rowId(row, idKey);
    if (!id) {
      continue;
    }
    const prev = asRecord(map.get(id));
    const next = asRecord(row);
    if (!prev) {
      map.set(id, row);
      continue;
    }
    const prevV = typeof prev["version"] === "number" ? prev["version"] : 0;
    const nextV = typeof next?.["version"] === "number" ? next["version"] : 0;
    const prevAt = typeof prev["updated_at"] === "string" ? prev["updated_at"] : "";
    const nextAt = typeof next?.["updated_at"] === "string" ? next["updated_at"] : "";
    if (nextV > prevV || (nextV === prevV && nextAt >= prevAt)) {
      map.set(id, row);
    }
  }
  return [...map.values()];
}

/** Stale/unsigned leave must not wipe a newer visible publisher session. */
export function shouldApplyStreetLeave(current: unknown, leaveSession: unknown): boolean {
  const rec = asRecord(current);
  const liveSession = rec?.["presence_session"];
  if (typeof liveSession !== "string" || liveSession.length === 0) {
    return true;
  }
  return leaveSession === liveSession;
}

function findPair(pairs: unknown[], left: SeatId, right: SeatId): Record<string, unknown> | null {
  for (const row of pairs) {
    const rec = asRecord(row);
    if (rec && rec["left"] === left && rec["right"] === right) {
      return rec;
    }
  }
  return null;
}

export function applyGraphOpToPairs(pairs: unknown[], op: GraphOp): unknown[] {
  const ordered = orderedPair(op.from, op.to);
  if (!ordered) {
    return pairs;
  }
  const existing = findPair(pairs, ordered.left, ordered.right);
  if (op.op === "unfriend") {
    return pairs.filter((row) => {
      const rec = asRecord(row);
      return !(rec && rec["left"] === ordered.left && rec["right"] === ordered.right);
    });
  }
  if (op.op === "request") {
    if (existing?.["status"] === "accepted") {
      return pairs;
    }
    if (existing?.["status"] === "pending" && existing["requested_by"] !== op.from) {
      return pairs.map((row) => {
        const rec = asRecord(row);
        if (rec && rec["left"] === ordered.left && rec["right"] === ordered.right) {
          return { ...rec, status: "accepted" };
        }
        return row;
      });
    }
    if (existing) {
      return pairs;
    }
    return [
      ...pairs,
      {
        left: ordered.left,
        right: ordered.right,
        status: "pending",
        requested_by: op.from,
      },
    ];
  }
  if (op.op === "accept") {
    if (!existing || existing["status"] !== "pending" || existing["requested_by"] === op.from) {
      return pairs;
    }
    return pairs.map((row) => {
      const rec = asRecord(row);
      if (rec && rec["left"] === ordered.left && rec["right"] === ordered.right) {
        return { ...rec, status: "accepted" };
      }
      return row;
    });
  }
  return pairs;
}

function mergeGraphPairs(current: unknown[], incoming: unknown[]): unknown[] {
  const map = new Map<string, unknown>();
  for (const row of [...current, ...incoming]) {
    const rec = asRecord(row);
    if (!rec || !isSeatId(rec["left"]) || !isSeatId(rec["right"])) {
      continue;
    }
    const key = pairKey(rec["left"], rec["right"]);
    const prev = asRecord(map.get(key));
    if (!prev) {
      map.set(key, rec);
      continue;
    }
    if (prev["status"] === "accepted" || rec["status"] === "accepted") {
      map.set(key, rec["status"] === "accepted" ? rec : prev);
    }
  }
  return [...map.values()];
}

function persistPath(): string {
  return join(dirname(fileURLToPath(import.meta.url)), ".data", "this-pc-shared.json");
}

export function createThisPcStore(file = persistPath()) {
  let presence: Partial<Record<SeatId, unknown>> = {};
  let graph = emptyGraph();
  let catalog = emptyCatalog();

  const load = () => {
    try {
      const raw = JSON.parse(readFileSync(file, "utf8")) as unknown;
      const rec = asRecord(raw);
      if (!rec) {
        return;
      }
      const g = asRecord(rec["graph"]);
      if (g && Array.isArray(g["pairs"])) {
        graph = {
          ...emptyGraph(typeof g["updated_at"] === "number" ? g["updated_at"] : 0),
          pairs: g["pairs"],
        };
      }
      const c = asRecord(rec["catalog"]);
      if (c) {
        const shops = Array.isArray(c["shops"]) ? c["shops"] : [];
        const listings = Array.isArray(c["listings"]) ? c["listings"] : [];
        const published = publishedOnly(shops, listings);
        catalog = {
          ...emptyCatalog(typeof c["updated_at"] === "number" ? c["updated_at"] : 0),
          shops: published.shops,
          listings: published.listings,
        };
      }
    } catch {
      /* first run or unreadable file */
    }
  };

  const save = () => {
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(
      file,
      JSON.stringify(
        {
          v: 1,
          kind: "this-pc-shared",
          graph,
          catalog,
          this_pc: true,
          not_wan: true,
          not_plan_pass: true,
        },
        null,
        2,
      ),
    );
  };

  const sweepPresence = (now = Date.now()) => {
    for (const seat of SEATS) {
      const rec = asRecord(presence[seat]);
      const ts = rec?.["ts"];
      if (typeof ts !== "number" || now - ts > PRESENCE_TTL_MS) {
        delete presence[seat];
      }
    }
  };

  load();

  return {
    snapshot(now = Date.now()): SharedSnapshot {
      sweepPresence(now);
      return {
        v: 1,
        kind: "local-demo-bus",
        presence: { ...presence },
        graph: { ...graph, pairs: [...graph.pairs] },
        catalog: {
          ...catalog,
          shops: [...catalog.shops],
          listings: [...catalog.listings],
        },
        this_pc: true,
        bind: "127.0.0.1",
        not_wan: true,
        persist: "catalog+graph",
        presence_ephemeral: true,
        not_presence_server: true,
        not_plan_pass: true,
      };
    },

    apply(body: Record<string, unknown>, now = Date.now()): SharedSnapshot {
      if (body["leave"] && isSeatId(body["leave"])) {
        if (shouldApplyStreetLeave(presence[body["leave"]], body["leave_session"])) {
          delete presence[body["leave"]];
        }
      }
      const packet = body["presence"];
      if (packet && typeof packet === "object") {
        const seat = (packet as { seat_id?: unknown }).seat_id;
        if (isSeatId(seat)) {
          presence[seat] = packet;
        }
      }
      if (body["graph_clear"] === true) {
        graph = emptyGraph(now);
        save();
      }
      const opRaw = asRecord(body["graph_op"]);
      if (opRaw && (opRaw["op"] === "request" || opRaw["op"] === "accept" || opRaw["op"] === "unfriend")) {
        if (isSeatId(opRaw["from"]) && isSeatId(opRaw["to"])) {
          graph = {
            ...graph,
            pairs: applyGraphOpToPairs(graph.pairs, {
              op: opRaw["op"],
              from: opRaw["from"],
              to: opRaw["to"],
            }),
            updated_at: now,
          };
          save();
        }
      }
      const incomingGraph = asRecord(body["graph"]);
      if (incomingGraph && Array.isArray(incomingGraph["pairs"])) {
        const nextAt = typeof incomingGraph["updated_at"] === "number" ? incomingGraph["updated_at"] : now;
        if (incomingGraph["pairs"].length === 0 && nextAt >= graph.updated_at) {
          graph = emptyGraph(nextAt);
        } else {
          graph = {
            ...graph,
            pairs: mergeGraphPairs(graph.pairs, incomingGraph["pairs"]),
            updated_at: Math.max(graph.updated_at, nextAt),
          };
        }
        save();
      }
      if (body["catalog_clear"] === true) {
        catalog = emptyCatalog(now);
        save();
      }
      const incomingCatalog = asRecord(body["catalog"]);
      if (incomingCatalog) {
        const shops = Array.isArray(incomingCatalog["shops"]) ? incomingCatalog["shops"] : [];
        const listings = Array.isArray(incomingCatalog["listings"]) ? incomingCatalog["listings"] : [];
        const nextAt =
          typeof incomingCatalog["updated_at"] === "number" ? incomingCatalog["updated_at"] : now;
        if (body["catalog_clear"] === true) {
          const published = publishedOnly(shops, listings);
          catalog = {
            ...emptyCatalog(nextAt),
            shops: published.shops,
            listings: published.listings,
          };
        } else {
          catalog = {
            ...catalog,
            shops: mergePublished(catalog.shops, shops, "shop_id"),
            listings: mergePublished(catalog.listings, listings, "listing_id"),
            updated_at: Math.max(catalog.updated_at, nextAt),
          };
        }
        save();
      }
      return this.snapshot(now);
    },
  };
}

export function isLoopbackHost(hostHeader: string | undefined): boolean {
  const host = (hostHeader ?? "").split(":")[0]?.replace(/^\[|\]$/g, "") ?? "";
  return host === "127.0.0.1" || host === "localhost" || host === "::1";
}
