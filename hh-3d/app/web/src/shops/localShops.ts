import { DEMO_OWNER_ID } from "../account/demoIdentity";
import { AVATAR_SPAWN, distanceM, inSpawnKeepOut, offsetLngLat } from "../avatar/walk";
import { persistSidewalkLngLat, type WorldStreet } from "../play/world";
import { sanitizePublicText } from "./moderation";
import type { Shop } from "./types";

export const LOCAL_SHOPS_KEY = "hh-world.local-shops.v1";
export const LOCAL_SHOP_PREFIX = "shop-local-";
export const LOCAL_SHOP_WORLD = "hh-world-ben-thanh-400m";
const SHOP_ID = /^shop-local-[a-z0-9-]+$/;
const PLACE_ID = /^place-local-[a-z0-9-]+$/;
const MIN_SEPARATION_M = 8;
const NUDGE_EAST_M = 12;
/** Create-at-spawn walks this far north of the nape, outside keep-out. */
export const PLAYER_SHOP_NORTH_M = 20;

export type LocalShop = {
  v: 1;
  shop_id: string;
  owner_id: typeof DEMO_OWNER_ID;
  name: string;
  description: string;
  place_id: string;
  lon: number;
  lat: number;
  status: "draft" | "published";
  owner_presence: "offline" | "online";
  updated_at: string;
  version: number;
  world_id: typeof LOCAL_SHOP_WORLD;
  source: "local-demo";
  sells: string;
  not_plan_pass: true;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function finiteCoord(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function isLocalShopId(id: string): boolean {
  return id.startsWith(LOCAL_SHOP_PREFIX);
}

export function sanitizeLocalShop(value: unknown): LocalShop | null {
  const rec = asRecord(value);
  if (!rec || rec["v"] !== 1 || rec["source"] !== "local-demo") {
    return null;
  }
  if (rec["owner_id"] !== DEMO_OWNER_ID || rec["not_plan_pass"] !== true) {
    return null;
  }
  const shop_id = rec["shop_id"];
  const name = typeof rec["name"] === "string" ? sanitizePublicText(rec["name"]) : null;
  const description = rec["description"];
  const place_id = rec["place_id"];
  const lon = finiteCoord(rec["lon"]);
  const lat = finiteCoord(rec["lat"]);
  const status = rec["status"];
  const owner_presence = rec["owner_presence"];
  const updated_at = rec["updated_at"];
  const version = rec["version"];
  const world_id = rec["world_id"];
  const sells = typeof rec["sells"] === "string" ? sanitizePublicText(rec["sells"]) : null;
  if (typeof shop_id !== "string" || !SHOP_ID.test(shop_id)) {
    return null;
  }
  if (!name || typeof description !== "string" || description.length > 240) {
    return null;
  }
  if (typeof place_id !== "string" || !PLACE_ID.test(place_id)) {
    return null;
  }
  if (lon === null || lat === null) {
    return null;
  }
  if (status !== "draft" && status !== "published") {
    return null;
  }
  if (owner_presence !== "offline" && owner_presence !== "online") {
    return null;
  }
  if (typeof updated_at !== "string" || typeof version !== "number") {
    return null;
  }
  if (world_id !== LOCAL_SHOP_WORLD || !sells) {
    return null;
  }
  return {
    v: 1,
    shop_id,
    owner_id: DEMO_OWNER_ID,
    name,
    description,
    place_id,
    lon,
    lat,
    status,
    owner_presence,
    updated_at,
    version,
    world_id: LOCAL_SHOP_WORLD,
    source: "local-demo",
    sells,
    not_plan_pass: true,
  };
}

export function toCatalogShop(row: LocalShop): Shop {
  return {
    shop_id: row.shop_id,
    owner_id: row.owner_id,
    name: row.name,
    description: row.description,
    place_id: row.place_id,
    lon: row.lon,
    lat: row.lat,
    status: row.status,
    owner_presence: row.owner_presence,
    updated_at: row.updated_at,
    version: row.version,
    world_id: row.world_id,
  };
}

export function toCatalogShops(rows: LocalShop[]): Shop[] {
  return rows.map(toCatalogShop);
}

export function placeAwayFromSpawnKeepOut(
  lon: number,
  lat: number,
): { lon: number; lat: number } {
  if (!inSpawnKeepOut(lon, lat)) {
    return { lon, lat };
  }
  return offsetLngLat(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat, 0, PLAYER_SHOP_NORTH_M);
}

export function placeAwayFromOthers(
  lon: number,
  lat: number,
  others: { lon: number; lat: number }[],
): { lon: number; lat: number } {
  let next = placeAwayFromSpawnKeepOut(lon, lat);
  if (!Number.isFinite(next.lon) || !Number.isFinite(next.lat)) {
    next = placeAwayFromSpawnKeepOut(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat);
  }
  for (let i = 0; i < 4; i += 1) {
    const clash = others.some((row) => distanceM(next, row) < MIN_SEPARATION_M);
    if (!clash && !inSpawnKeepOut(next.lon, next.lat)) {
      return next;
    }
    next = offsetLngLat(next.lon, next.lat, NUDGE_EAST_M, 0);
    if (inSpawnKeepOut(next.lon, next.lat)) {
      next = placeAwayFromSpawnKeepOut(next.lon, next.lat);
    }
  }
  return next;
}

/**
 * New player-shop persist sits on the Harbor/Tram sidewalk plant,
 * not the asphalt centerline. Create-at-spawn still walks north first.
 * Existing catalog rows are not rewritten.
 */
export function placeNewLocalShopLngLat(
  lon: number,
  lat: number,
  others: { lon: number; lat: number }[],
  streets: readonly WorldStreet[] = [],
): { lon: number; lat: number } {
  let next = placeAwayFromOthers(lon, lat, others);
  if (!streets.length) {
    return next;
  }
  for (let i = 0; i < 4; i += 1) {
    const planted = persistSidewalkLngLat(next.lon, next.lat, streets);
    const offKeep = inSpawnKeepOut(planted.lon, planted.lat)
      ? placeAwayFromSpawnKeepOut(planted.lon, planted.lat)
      : planted;
    const again =
      offKeep.lon !== planted.lon || offKeep.lat !== planted.lat
        ? persistSidewalkLngLat(offKeep.lon, offKeep.lat, streets)
        : planted;
    const clash = others.some((row) => distanceM(again, row) < MIN_SEPARATION_M);
    if (!clash && !inSpawnKeepOut(again.lon, again.lat)) {
      return again;
    }
    next = offsetLngLat(again.lon, again.lat, NUDGE_EAST_M, 0);
    if (inSpawnKeepOut(next.lon, next.lat)) {
      next = placeAwayFromSpawnKeepOut(next.lon, next.lat);
    }
  }
  const last = persistSidewalkLngLat(next.lon, next.lat, streets);
  return inSpawnKeepOut(last.lon, last.lat) ? next : last;
}

export function createLocalShop(input: {
  name: string;
  sells: string;
  lon: number;
  lat: number;
  canPublish: boolean;
  existing?: { lon: number; lat: number }[];
  streets?: readonly WorldStreet[];
  now?: string;
  shopId?: string;
}): LocalShop | null {
  const name = sanitizePublicText(input.name);
  const sells = sanitizePublicText(input.sells);
  if (!name || !sells) {
    return null;
  }
  const suffix =
    input.shopId && SHOP_ID.test(input.shopId)
      ? input.shopId.slice(LOCAL_SHOP_PREFIX.length)
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  const shop_id = `${LOCAL_SHOP_PREFIX}${suffix}`;
  const place = placeNewLocalShopLngLat(
    input.lon,
    input.lat,
    input.existing ?? [],
    input.streets ?? [],
  );
  const updated_at = input.now ?? new Date().toISOString();
  return {
    v: 1,
    shop_id,
    owner_id: DEMO_OWNER_ID,
    name,
    description: `Player-opened shop on this machine. Sells ${sells}. Not a real storefront. NOT_PLAN_PASS.`,
    place_id: `place-local-${suffix}`,
    lon: place.lon,
    lat: place.lat,
    status: input.canPublish ? "published" : "draft",
    owner_presence: "offline",
    updated_at,
    version: 1,
    world_id: LOCAL_SHOP_WORLD,
    source: "local-demo",
    sells,
    not_plan_pass: true,
  };
}

export function loadLocalShops(): LocalShop[] {
  if (typeof localStorage === "undefined") {
    return [];
  }
  try {
    const raw = localStorage.getItem(LOCAL_SHOPS_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map((row) => sanitizeLocalShop(row))
      .filter((row): row is LocalShop => row !== null);
  } catch {
    return [];
  }
}

export function saveLocalShops(rows: LocalShop[]): LocalShop[] {
  const clean = rows
    .map((row) => sanitizeLocalShop(row))
    .filter((row): row is LocalShop => row !== null);
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(LOCAL_SHOPS_KEY, JSON.stringify(clean));
  }
  return clean;
}

export function mergeLocalShops(local: LocalShop[], incoming: LocalShop[]): LocalShop[] {
  const map = new Map<string, LocalShop>();
  for (const row of [...local, ...incoming]) {
    const prev = map.get(row.shop_id);
    if (!prev || row.version > prev.version || row.updated_at > prev.updated_at) {
      map.set(row.shop_id, row);
    }
  }
  return [...map.values()];
}
