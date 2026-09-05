import type { Listing, Shop, ShopCatalog } from "./types";

const SHOP_ID = /^shop-[a-z0-9-]+$/;
const LISTING_ID = /^listing-[a-z0-9-]+$/;
const SHOP_STATUSES = new Set(["draft", "published", "hidden", "closed"]);
const LISTING_STATUSES = new Set(["draft", "published", "sold_out", "hidden", "deleted"]);
const KINDS = new Set(["fish", "bag", "other"]);

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function readShop(value: unknown): Shop | null {
  const rec = asRecord(value);
  if (!rec) {
    return null;
  }
  const shop_id = rec["shop_id"];
  const owner_id = rec["owner_id"];
  const name = rec["name"];
  const description = rec["description"];
  const place_id = rec["place_id"];
  const lon = rec["lon"];
  const lat = rec["lat"];
  const status = rec["status"];
  const owner_presence = rec["owner_presence"];
  const updated_at = rec["updated_at"];
  const version = rec["version"];
  const world_id = rec["world_id"];
  if (typeof shop_id !== "string" || !SHOP_ID.test(shop_id)) {
    return null;
  }
  if (typeof owner_id !== "string" || typeof name !== "string") {
    return null;
  }
  if (typeof description !== "string" || typeof place_id !== "string") {
    return null;
  }
  if (typeof lon !== "number" || typeof lat !== "number") {
    return null;
  }
  if (typeof status !== "string" || !SHOP_STATUSES.has(status)) {
    return null;
  }
  if (owner_presence !== "offline" && owner_presence !== "online") {
    return null;
  }
  if (typeof updated_at !== "string" || typeof world_id !== "string") {
    return null;
  }
  if (typeof version !== "number") {
    return null;
  }
  return {
    shop_id,
    owner_id,
    name,
    description,
    place_id,
    lon,
    lat,
    status: status as Shop["status"],
    owner_presence,
    updated_at,
    version,
    world_id,
  };
}

function readListing(value: unknown): Listing | null {
  const rec = asRecord(value);
  if (!rec) {
    return null;
  }
  const listing_id = rec["listing_id"];
  const shop_id = rec["shop_id"];
  const title = rec["title"];
  const description = rec["description"];
  const kind = rec["kind"];
  const price_label = rec["price_label"];
  const status = rec["status"];
  const updated_at = rec["updated_at"];
  const version = rec["version"];
  if (typeof listing_id !== "string" || !LISTING_ID.test(listing_id)) {
    return null;
  }
  if (typeof shop_id !== "string" || !SHOP_ID.test(shop_id)) {
    return null;
  }
  if (typeof title !== "string" || typeof description !== "string") {
    return null;
  }
  if (typeof kind !== "string" || !KINDS.has(kind)) {
    return null;
  }
  if (typeof price_label !== "string" || typeof updated_at !== "string") {
    return null;
  }
  if (typeof status !== "string" || !LISTING_STATUSES.has(status)) {
    return null;
  }
  if (typeof version !== "number") {
    return null;
  }
  return {
    listing_id,
    shop_id,
    title,
    description,
    kind: kind as Listing["kind"],
    price_label,
    status: status as Listing["status"],
    updated_at,
    version,
  };
}

export function parseShopCatalog(raw: unknown): ShopCatalog | null {
  const rec = asRecord(raw);
  if (!rec || rec["schema"] !== "hh-world-shop-catalog/v0") {
    return null;
  }
  if (!Array.isArray(rec["shops"]) || !Array.isArray(rec["listings"])) {
    return null;
  }
  const shops = rec["shops"].map(readShop).filter((row): row is Shop => row !== null);
  const listings = rec["listings"]
    .map(readListing)
    .filter((row): row is Listing => row !== null);
  const honesty = Array.isArray(rec["honesty"])
    ? rec["honesty"].filter((row): row is string => typeof row === "string")
    : [];
  const world_id = typeof rec["world_id"] === "string" ? rec["world_id"] : "hh-world-ben-thanh-400m";
  const published_at =
    typeof rec["published_at"] === "string" ? rec["published_at"] : "2026-09-03T08:40:00+07:00";
  const updated_at =
    typeof rec["updated_at"] === "string" ? rec["updated_at"] : published_at;
  return {
    schema: "hh-world-shop-catalog/v0",
    world_id,
    authored_or_source: "authored",
    accuracy_class: typeof rec["accuracy_class"] === "string" ? rec["accuracy_class"] : "authored",
    published_at,
    updated_at,
    honesty,
    shops,
    listings,
  };
}

export function publicShops(catalog: ShopCatalog): Shop[] {
  return catalog.shops.filter((shop) => shop.status === "published");
}

export function publicListings(catalog: ShopCatalog, shopId?: string): Listing[] {
  return catalog.listings.filter((row) => {
    if (row.status !== "published") {
      return false;
    }
    if (shopId && row.shop_id !== shopId) {
      return false;
    }
    return true;
  });
}

/** 1–3 public titles for a stall chalkboard. Drafts stay off the board. */
export const STALL_BOARD_MAX_TITLES = 3;
export const STALL_BOARD_SAMPLE_MARK = "(mẫu)";

export function stallBoardTitles(
  listings: readonly Listing[],
  shopId: string,
  max = STALL_BOARD_MAX_TITLES,
): string[] {
  const out: string[] = [];
  for (const row of listings) {
    if (row.status !== "published" || row.shop_id !== shopId) {
      continue;
    }
    const title = row.title.trim();
    if (!title) {
      continue;
    }
    out.push(title);
    if (out.length >= max) {
      break;
    }
  }
  return out;
}

/** Chalk lines match lantern language: public name + mẫu. Do not double-mark. */
export function stallBoardPaintTitle(title: string): string {
  const trimmed = title.trim();
  if (!trimmed) {
    return "";
  }
  if (/\(\s*mẫu\s*\)/i.test(trimmed)) {
    return trimmed;
  }
  return `${trimmed} ${STALL_BOARD_SAMPLE_MARK}`;
}

export function stallBoardPaintTitles(titles: readonly string[]): string[] {
  return titles.map(stallBoardPaintTitle).filter((row) => row.length > 0);
}

export function mergeCatalogListings(catalog: ShopCatalog, extras: Listing[]): ShopCatalog {
  const seen = new Set(catalog.listings.map((row) => row.listing_id));
  const add = extras.filter((row) => !seen.has(row.listing_id));
  if (add.length === 0) {
    return catalog;
  }
  return {
    ...catalog,
    listings: [...catalog.listings, ...add],
  };
}

export function mergeCatalogShops(catalog: ShopCatalog, extras: Shop[]): ShopCatalog {
  const seen = new Set(catalog.shops.map((row) => row.shop_id));
  const add = extras.filter((row) => !seen.has(row.shop_id));
  if (add.length === 0) {
    return catalog;
  }
  return {
    ...catalog,
    shops: [...catalog.shops, ...add],
  };
}

export function findShop(shops: Shop[], id: string | null): Shop | null {
  if (!id) {
    return null;
  }
  return shops.find((shop) => shop.shop_id === id) ?? null;
}

export function shopByPlace(shops: Shop[], placeId: string | null): Shop | null {
  if (!placeId) {
    return null;
  }
  return shops.find((shop) => shop.place_id === placeId) ?? null;
}

export function listingMatchesQuery(listing: Listing, needle: string): boolean {
  if (!needle) {
    return true;
  }
  return (
    listing.title.toLowerCase().includes(needle) ||
    listing.description.toLowerCase().includes(needle) ||
    listing.kind.toLowerCase().includes(needle) ||
    kindAliases(listing.kind).some((alias) => alias.includes(needle))
  );
}

function kindAliases(kind: Listing["kind"]): string[] {
  if (kind === "fish") {
    return ["cá", "ca", "fish"];
  }
  if (kind === "bag") {
    return ["túi", "tui", "bag"];
  }
  return [kind, "khác", "other", "phở", "pho", "sách", "sach"];
}

export function shopMatchesQuery(shop: Shop, listings: Listing[], needle: string): boolean {
  if (!needle) {
    return true;
  }
  if (
    shop.name.toLowerCase().includes(needle) ||
    shop.description.toLowerCase().includes(needle) ||
    shop.shop_id.toLowerCase().includes(needle)
  ) {
    return true;
  }
  return listings.some(
    (row) => row.shop_id === shop.shop_id && listingMatchesQuery(row, needle),
  );
}

export function kindLabel(kind: Listing["kind"]): string {
  if (kind === "fish") {
    return "Cá / fish";
  }
  if (kind === "bag") {
    return "Túi / bag";
  }
  return "Khác / other";
}
