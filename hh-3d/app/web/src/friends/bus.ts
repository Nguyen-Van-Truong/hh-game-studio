import {
  mergeLocalListings,
  sanitizeLocalListing,
  type LocalListing,
} from "../shops/localListings";
import { mergeLocalShops, sanitizeLocalShop, type LocalShop } from "../shops/localShops";
import { emptyGraph, sanitizeGraph, type FriendGraph } from "./graph";
import { sanitizePresence, type PresencePacket } from "./presence";
import { SEAT_IDS, type SeatId } from "./seats";

export const PRESENCE_CHANNEL = "hh-world.demo-presence.v1";
export const GRAPH_CHANNEL = "hh-world.demo-friends.v1";
export const SHOP_CHANNEL = "hh-world.demo-shops.v1";
export const DEMO_BUS_PATH = "/demo-bus";

export function presenceStorageKey(seat: SeatId): string {
  return `hh-world.demo-presence.seat.${seat}`;
}

export type DemoShopCatalog = {
  v: 1;
  kind: "local-demo-shops";
  shops: LocalShop[];
  listings: LocalListing[];
  updated_at: number;
  not_plan_pass: true;
};

export type BusEvent =
  | { type: "presence"; packet: PresencePacket }
  | { type: "leave"; seat_id: SeatId }
  | { type: "graph"; graph: FriendGraph }
  | { type: "catalog"; catalog: DemoShopCatalog };

export type DemoBusSnapshot = {
  v: 1;
  kind: "local-demo-bus";
  presence: Partial<Record<SeatId, PresencePacket>>;
  graph: FriendGraph;
  catalog: DemoShopCatalog;
  not_presence_server: true;
  not_plan_pass: true;
};

export function emptyShopCatalog(updatedAt = 0): DemoShopCatalog {
  return {
    v: 1,
    kind: "local-demo-shops",
    shops: [],
    listings: [],
    updated_at: updatedAt,
    not_plan_pass: true,
  };
}

export function sanitizeShopCatalog(value: unknown): DemoShopCatalog | null {
  const rec = asRecord(value);
  if (!rec || rec["v"] !== 1 || rec["kind"] !== "local-demo-shops") {
    return null;
  }
  if (rec["not_plan_pass"] !== true) {
    return null;
  }
  const updated_at = rec["updated_at"];
  if (typeof updated_at !== "number") {
    return null;
  }
  const shops = Array.isArray(rec["shops"])
    ? rec["shops"].map((row) => sanitizeLocalShop(row)).filter((row): row is LocalShop => row !== null)
    : [];
  const listings = Array.isArray(rec["listings"])
    ? rec["listings"]
        .map((row) => sanitizeLocalListing(row))
        .filter((row): row is LocalListing => row !== null)
    : [];
  return {
    v: 1,
    kind: "local-demo-shops",
    shops,
    listings,
    updated_at,
    not_plan_pass: true,
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

export function readStoredPresence(seat: SeatId): PresencePacket | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  try {
    const raw = localStorage.getItem(presenceStorageKey(seat));
    if (!raw) {
      return null;
    }
    return sanitizePresence(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function writeStoredPresence(packet: PresencePacket): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  localStorage.setItem(presenceStorageKey(packet.seat_id), JSON.stringify(packet));
}

export function clearStoredPresence(seat: SeatId): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  localStorage.removeItem(presenceStorageKey(seat));
}

export function readAllStoredPresence(): PresencePacket[] {
  return SEAT_IDS.map(readStoredPresence).filter((row): row is PresencePacket => row !== null);
}

export function sanitizeBusSnapshot(value: unknown): DemoBusSnapshot | null {
  const rec = asRecord(value);
  if (!rec || rec["v"] !== 1 || rec["kind"] !== "local-demo-bus") {
    return null;
  }
  if (rec["not_presence_server"] !== true || rec["not_plan_pass"] !== true) {
    return null;
  }
  const presenceRaw = asRecord(rec["presence"]) ?? {};
  const presence: DemoBusSnapshot["presence"] = {};
  for (const seat of SEAT_IDS) {
    const packet = sanitizePresence(presenceRaw[seat]);
    if (packet) {
      presence[seat] = packet;
    }
  }
  return {
    v: 1,
    kind: "local-demo-bus",
    presence,
    graph: sanitizeGraph(rec["graph"]) ?? emptyGraph(),
    catalog: sanitizeShopCatalog(rec["catalog"]) ?? emptyShopCatalog(),
    not_presence_server: true,
    not_plan_pass: true,
  };
}

export async function pullDemoBus(): Promise<DemoBusSnapshot | null> {
  try {
    const res = await fetch(DEMO_BUS_PATH, { cache: "no-store" });
    if (!res.ok) {
      return null;
    }
    return sanitizeBusSnapshot(await res.json());
  } catch {
    return null;
  }
}

export function publishedShopCatalog(catalog: DemoShopCatalog): DemoShopCatalog {
  return {
    ...catalog,
    shops: catalog.shops.filter((row) => row.status === "published"),
    listings: catalog.listings.filter((row) => row.status === "published"),
  };
}

export function keepLocalDrafts<T extends { status: string }>(
  local: T[],
  incomingPublished: T[],
  idOf: (row: T) => string,
): T[] {
  const drafts = local.filter((row) => row.status !== "published");
  const seen = new Set(incomingPublished.map(idOf));
  return [...drafts.filter((row) => !seen.has(idOf(row))), ...incomingPublished];
}

export async function pushDemoBus(body: {
  presence?: PresencePacket;
  leave?: SeatId;
  leave_session?: string;
  graph?: FriendGraph;
  graph_op?: { op: "request" | "accept" | "unfriend"; from: SeatId; to: SeatId };
  graph_clear?: boolean;
  catalog?: DemoShopCatalog;
  catalog_clear?: boolean;
}): Promise<void> {
  try {
    await fetch(DEMO_BUS_PATH, {
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
  } catch {
    /* preview bus is optional; BroadcastChannel still works in one profile */
  }
}

export function subscribeLocalBus(onEvent: (event: BusEvent) => void): () => void {
  const presenceCh =
    typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(PRESENCE_CHANNEL);
  const graphCh =
    typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(GRAPH_CHANNEL);
  const shopCh =
    typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(SHOP_CHANNEL);
  if (presenceCh) {
    presenceCh.onmessage = (event) => {
      const rec = asRecord(event.data);
      if (!rec) {
        return;
      }
      if (rec["type"] === "leave" && typeof rec["seat_id"] === "string") {
        const seat = rec["seat_id"];
        if (seat === "a" || seat === "b" || seat === "c") {
          onEvent({ type: "leave", seat_id: seat });
        }
        return;
      }
      const packet = sanitizePresence(rec["packet"] ?? event.data);
      if (packet) {
        onEvent({ type: "presence", packet });
      }
    };
  }
  if (graphCh) {
    graphCh.onmessage = (event) => {
      const graph = sanitizeGraph(event.data);
      if (graph) {
        onEvent({ type: "graph", graph });
      }
    };
  }
  if (shopCh) {
    shopCh.onmessage = (event) => {
      const catalog = sanitizeShopCatalog(event.data);
      if (catalog) {
        onEvent({ type: "catalog", catalog });
      }
    };
  }
  const onStorage = (event: StorageEvent) => {
    if (!event.key) {
      return;
    }
    if (event.key.startsWith("hh-world.demo-presence.seat.")) {
      const seat = event.key.slice("hh-world.demo-presence.seat.".length);
      if (seat !== "a" && seat !== "b" && seat !== "c") {
        return;
      }
      if (!event.newValue) {
        onEvent({ type: "leave", seat_id: seat });
        return;
      }
      try {
        const packet = sanitizePresence(JSON.parse(event.newValue));
        if (packet) {
          onEvent({ type: "presence", packet });
        }
      } catch {
        /* ignore */
      }
      return;
    }
    if (event.key === "hh-world.demo-friends.v1" && event.newValue) {
      try {
        const graph = sanitizeGraph(JSON.parse(event.newValue));
        if (graph) {
          onEvent({ type: "graph", graph });
        }
      } catch {
        /* ignore */
      }
    }
    if (
      (event.key === "hh-world.local-shops.v1" || event.key === "hh-world.local-listings.v1") &&
      event.newValue
    ) {
      try {
        const parsed: unknown = JSON.parse(event.newValue);
        if (event.key === "hh-world.local-shops.v1" && Array.isArray(parsed)) {
          const shops = parsed
            .map((row) => sanitizeLocalShop(row))
            .filter((row): row is LocalShop => row !== null);
          onEvent({
            type: "catalog",
            catalog: { ...emptyShopCatalog(Date.now()), shops },
          });
        }
        if (event.key === "hh-world.local-listings.v1" && Array.isArray(parsed)) {
          const listings = parsed
            .map((row) => sanitizeLocalListing(row))
            .filter((row): row is LocalListing => row !== null);
          onEvent({
            type: "catalog",
            catalog: { ...emptyShopCatalog(Date.now()), listings },
          });
        }
      } catch {
        /* ignore */
      }
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    presenceCh?.close();
    graphCh?.close();
    shopCh?.close();
    window.removeEventListener("storage", onStorage);
  };
}

export function mergeShopCatalog(local: DemoShopCatalog, incoming: DemoShopCatalog): DemoShopCatalog {
  return {
    v: 1,
    kind: "local-demo-shops",
    shops: mergeLocalShops(local.shops, incoming.shops),
    listings: mergeLocalListings(local.listings, incoming.listings),
    updated_at: Math.max(local.updated_at, incoming.updated_at),
    not_plan_pass: true,
  };
}

export function publishLocalCatalog(catalog: DemoShopCatalog): void {
  if (typeof BroadcastChannel !== "undefined") {
    const ch = new BroadcastChannel(SHOP_CHANNEL);
    ch.postMessage(catalog);
    ch.close();
  }
}

export function publishLocalPresence(packet: PresencePacket): void {
  writeStoredPresence(packet);
  if (typeof BroadcastChannel !== "undefined") {
    const ch = new BroadcastChannel(PRESENCE_CHANNEL);
    ch.postMessage({ type: "presence", packet });
    ch.close();
  }
}

export function publishLocalLeave(seat: SeatId): void {
  clearStoredPresence(seat);
  if (typeof BroadcastChannel !== "undefined") {
    const ch = new BroadcastChannel(PRESENCE_CHANNEL);
    ch.postMessage({ type: "leave", seat_id: seat });
    ch.close();
  }
}

export function publishLocalGraph(graph: FriendGraph): void {
  if (typeof BroadcastChannel !== "undefined") {
    const ch = new BroadcastChannel(GRAPH_CHANNEL);
    ch.postMessage(graph);
    ch.close();
  }
}
