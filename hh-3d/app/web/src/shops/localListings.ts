import { sanitizePublicText } from "./moderation";
import type { Listing, ListingKind } from "./types";

export const LOCAL_LISTINGS_KEY = "hh-world.local-listings.v1";
export const LOCAL_LISTING_PREFIX = "listing-local-";

const LISTING_ID = /^listing-local-[a-z0-9-]+$/;
const SHOP_ID = /^shop-[a-z0-9-]+$/;
const KINDS = new Set(["fish", "bag", "other"]);

export type LocalListing = {
  v: 1;
  listing_id: string;
  shop_id: string;
  title: string;
  description: string;
  kind: ListingKind;
  price_label: string;
  status: "draft" | "published";
  queued: boolean;
  idempotency_key: string;
  updated_at: string;
  version: number;
  source: "local-demo";
  owner_id: "owner-local-demo-machine";
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

export function networkAllowsPublish(
  browserOnline: boolean,
  networkCutSim: boolean,
): boolean {
  return browserOnline && !networkCutSim;
}

export function sanitizeTitle(raw: string): string | null {
  return sanitizePublicText(raw);
}

export function inferKind(title: string): ListingKind {
  const t = title.toLowerCase();
  if (/(?:cá|fish|mackerel|nục|cá\s*thu)/i.test(t)) {
    return "fish";
  }
  if (/(?:túi|tui\b|bag|tote|cói)/i.test(t)) {
    return "bag";
  }
  return "other";
}

export function presetForKind(kind: ListingKind): { title: string; description: string } {
  if (kind === "bag") {
    return {
      title: "Túi bố thêm (máy này)",
      description: "Local demo listing. Extra bag sample. Not a real product.",
    };
  }
  if (kind === "fish") {
    return {
      title: "Cá thu thêm (máy này)",
      description: "Local demo listing. Extra fish sample. Not a real product.",
    };
  }
  return {
    title: "Phở bò (máy này)",
    description: "Local demo listing. Free-text sample. Not a real product.",
  };
}

export function sanitizeLocalListing(value: unknown): LocalListing | null {
  const rec = asRecord(value);
  if (!rec || rec["v"] !== 1 || rec["source"] !== "local-demo") {
    return null;
  }
  if (rec["owner_id"] !== "owner-local-demo-machine") {
    return null;
  }
  const listing_id = rec["listing_id"];
  const shop_id = rec["shop_id"];
  const title = typeof rec["title"] === "string" ? sanitizeTitle(rec["title"]) : null;
  const description = rec["description"];
  const kind = rec["kind"];
  const price_label = rec["price_label"];
  const status = rec["status"];
  const queued = rec["queued"];
  const idempotency_key = rec["idempotency_key"];
  const updated_at = rec["updated_at"];
  const version = rec["version"];
  if (typeof listing_id !== "string" || !LISTING_ID.test(listing_id)) {
    return null;
  }
  if (typeof shop_id !== "string" || !SHOP_ID.test(shop_id)) {
    return null;
  }
  if (!title || typeof description !== "string") {
    return null;
  }
  if (typeof kind !== "string" || !KINDS.has(kind)) {
    return null;
  }
  if (typeof price_label !== "string" || typeof updated_at !== "string") {
    return null;
  }
  if (status !== "draft" && status !== "published") {
    return null;
  }
  if (typeof queued !== "boolean" || typeof version !== "number") {
    return null;
  }
  if (typeof idempotency_key !== "string" || idempotency_key.length < 8) {
    return null;
  }
  if (status === "published" && queued) {
    return null;
  }
  return {
    v: 1,
    listing_id,
    shop_id,
    title,
    description,
    kind: kind as ListingKind,
    price_label,
    status,
    queued,
    idempotency_key,
    updated_at,
    version,
    source: "local-demo",
    owner_id: "owner-local-demo-machine",
  };
}

export function toCatalogListing(row: LocalListing): Listing {
  return {
    listing_id: row.listing_id,
    shop_id: row.shop_id,
    title: row.title,
    description: row.description,
    kind: row.kind,
    price_label: row.price_label,
    status: row.status,
    updated_at: row.updated_at,
    version: row.version,
  };
}

export function toCatalogListings(rows: LocalListing[]): Listing[] {
  return rows.map(toCatalogListing);
}

export function createLocalListing(input: {
  shopId: string;
  title: string;
  kind: ListingKind;
  canPublish: boolean;
  now?: string;
  listingId?: string;
}): LocalListing | null {
  if (!SHOP_ID.test(input.shopId)) {
    return null;
  }
  const title = sanitizeTitle(input.title);
  if (!title) {
    return null;
  }
  const kind: ListingKind = KINDS.has(input.kind) ? input.kind : inferKind(title);
  const preset = presetForKind(kind);
  const listing_id =
    input.listingId && LISTING_ID.test(input.listingId)
      ? input.listingId
      : `${LOCAL_LISTING_PREFIX}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  const updated_at = input.now ?? new Date().toISOString();
  return {
    v: 1,
    listing_id,
    shop_id: input.shopId,
    title,
    description: preset.description,
    kind,
    price_label: "Liên hệ",
    status: input.canPublish ? "published" : "draft",
    queued: !input.canPublish,
    idempotency_key: listing_id,
    updated_at,
    version: 1,
    source: "local-demo",
    owner_id: "owner-local-demo-machine",
  };
}

export function retryQueuedListing(
  rows: LocalListing[],
  listingId: string,
  canPublish: boolean,
  now = new Date().toISOString(),
): LocalListing[] {
  return rows.map((row) => {
    if (row.listing_id !== listingId || !row.queued || row.status !== "draft") {
      return row;
    }
    if (!canPublish) {
      return row;
    }
    return {
      ...row,
      status: "published",
      queued: false,
      updated_at: now,
      version: row.version + 1,
    };
  });
}

export function loadLocalListings(): LocalListing[] {
  if (typeof localStorage === "undefined") {
    return [];
  }
  try {
    const raw = localStorage.getItem(LOCAL_LISTINGS_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map((row) => sanitizeLocalListing(row))
      .filter((row): row is LocalListing => row !== null);
  } catch {
    return [];
  }
}

export function saveLocalListings(rows: LocalListing[]): LocalListing[] {
  const clean = rows
    .map((row) => sanitizeLocalListing(row))
    .filter((row): row is LocalListing => row !== null);
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(LOCAL_LISTINGS_KEY, JSON.stringify(clean));
  }
  return clean;
}

export function mergeLocalListings(local: LocalListing[], incoming: LocalListing[]): LocalListing[] {
  const map = new Map<string, LocalListing>();
  for (const row of [...local, ...incoming]) {
    const prev = map.get(row.listing_id);
    if (!prev || row.version > prev.version || row.updated_at > prev.updated_at) {
      map.set(row.listing_id, row);
    }
  }
  return [...map.values()];
}

export function isLocalListingId(id: string): boolean {
  return id.startsWith(LOCAL_LISTING_PREFIX);
}
