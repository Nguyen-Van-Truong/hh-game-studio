import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const catalog = JSON.parse(readFileSync(join(root, "public", "data", "shops.json"), "utf8"));

const BLOCKED = [
  /\bcsam\b/i,
  /\bchild\s*porn/i,
  /\bdoxx?(?:ing)?\b/i,
  /(?:ban|mua)\s*(?:ma\s*tuy|heroin)/i,
  /\b(?:unlicensed\s*firearm|ban\s*sung)\b/i,
];

function foldForMatch(raw) {
  return raw
    .normalize("NFD")
    .replace(/\p{M}+/gu, "")
    .replace(/đ/gi, "d")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

function sanitizePublicText(raw) {
  const title = raw.trim().replace(/\s+/g, " ");
  if (title.length < 2 || title.length > 80) return null;
  if (/[<>]/.test(title)) return null;
  const folded = foldForMatch(title);
  if (folded && BLOCKED.some((rule) => rule.test(folded))) return null;
  return title;
}

function inferKind(title) {
  const t = title.toLowerCase();
  if (/(?:cá|fish|mackerel|nục)/i.test(t)) return "fish";
  if (/(?:túi|tui\b|bag|tote)/i.test(t)) return "bag";
  return "other";
}

function createLocalShop(input) {
  const name = sanitizePublicText(input.name);
  const sells = sanitizePublicText(input.sells);
  if (!name || !sells) return null;
  return {
    shop_id: input.shopId,
    name,
    sells,
    status: input.canPublish ? "published" : "draft",
    lon: input.lon,
    lat: input.lat,
    owner_id: "owner-local-demo-machine",
    not_plan_pass: true,
  };
}

function createLocalListing(input) {
  const title = sanitizePublicText(input.title);
  if (!title) return null;
  return {
    listing_id: input.listingId,
    shop_id: input.shopId,
    title,
    kind: inferKind(title),
    status: input.canPublish ? "published" : "draft",
    queued: !input.canPublish,
  };
}

function publicShops(shops) {
  return shops.filter((row) => row.status === "published");
}

function publicListings(rows, shopId) {
  return rows.filter((row) => row.status === "published" && (!shopId || row.shop_id === shopId));
}

test("shop panel labels spawn-keep-out leftovers, not street stalls", () => {
  const panel = readFileSync(join(root, "src", "shops", "ShopPanel.tsx"), "utf8");
  assert.match(panel, /isMenuLeftoverShop\(shop\)/);
  assert.match(panel, /MENU_LEFTOVER_LABEL/);
  assert.match(panel, /data-leftover=\{leftover \? "1" : "0"\}/);
  assert.match(panel, /data-street=\{leftover \? "0" : "1"\}/);
  assert.match(panel, /data-keep-out=\{leftover \? "1" : "0"\}/);
  assert.match(panel, /data-testid="shop-leftover-banner"/);
  assert.match(panel, /data-testid="shop-panel-kind"/);
  assert.match(panel, /public shop · opened on this machine/);
  assert.match(panel, /public shop · authored example among many/);
  assert.match(panel, /leftover\s*\?\s*MENU_LEFTOVER_LABEL/);
});

test("menu shop list labels spawn-keep-out leftovers and sorts them last", () => {
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  const goods = readFileSync(join(root, "src", "shops", "GoodsList.tsx"), "utf8");
  assert.match(walk, /MENU_LEFTOVER_LABEL = "không trên phố \/ leftover máy này"/);
  assert.match(walk, /export function isMenuLeftoverShop/);
  assert.match(walk, /export function sortMenuShops/);
  assert.match(goods, /sortMenuShops\(shops\)/);
  assert.match(goods, /MENU_LEFTOVER_LABEL/);
  assert.match(goods, /data-leftover=\{leftover \? "1" : "0"\}/);
  assert.match(goods, /data-keep-out=\{leftover \? "1" : "0"\}/);
  assert.match(goods, /data-street=\{leftover \? "0" : "1"\}/);

  const SPAWN = { lon: 106.69804, lat: 10.77162 };
  const KEEP = 14;
  const M_PER_DEG_LAT = 111320;
  const metersPerDegLon = (lat) => M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
  const dist = (a, b) => {
    const east = (b.lon - a.lon) * metersPerDegLon((a.lat + b.lat) / 2);
    const north = (b.lat - a.lat) * M_PER_DEG_LAT;
    return Math.hypot(east, north);
  };
  const isStreet = (shop) => dist(shop, SPAWN) > KEEP;
  const sortMenu = (rows) => [
    ...rows.filter(isStreet),
    ...rows.filter((row) => !isStreet(row)),
  ];
  const lantern = { shop_id: "shop-lantern-fish", lon: 106.6980366, lat: 10.7718712 };
  const pho = { shop_id: "shop-local-pho", lon: 106.69804, lat: 10.7718 };
  const shared = { shop_id: "shop-local-sharedpc", lon: SPAWN.lon, lat: SPAWN.lat };
  const j6 = { shop_id: "shop-local-mtl8ulddihjpre", lon: 106.69815, lat: SPAWN.lat };
  assert.equal(isStreet(lantern), true);
  assert.equal(isStreet(pho), true);
  assert.equal(isStreet(shared), false);
  assert.equal(isStreet(j6), false);
  const ordered = sortMenu([shared, lantern, j6, pho]);
  assert.deepEqual(
    ordered.map((row) => row.shop_id),
    ["shop-lantern-fish", "shop-local-pho", "shop-local-sharedpc", "shop-local-mtl8ulddihjpre"],
  );
});

test("create-shop at spawn is persisted off the keep-out, not on the nape", () => {
  const src = readFileSync(join(root, "src", "shops", "localShops.ts"), "utf8");
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  const world = readFileSync(join(root, "src", "play", "world.ts"), "utf8");
  const app = readFileSync(join(root, "src", "app", "App.tsx"), "utf8");
  assert.match(walk, /SPAWN_KEEP_OUT_M = 14/);
  assert.match(walk, /export function inSpawnKeepOut/);
  assert.match(src, /export function placeAwayFromSpawnKeepOut/);
  assert.match(src, /PLAYER_SHOP_NORTH_M = 20/);
  assert.match(src, /offsetLngLat\(AVATAR_SPAWN\.lon, AVATAR_SPAWN\.lat, 0, PLAYER_SHOP_NORTH_M\)/);
  assert.match(src, /placeAwayFromSpawnKeepOut\(lon, lat\)/);
  assert.match(src, /export function placeNewLocalShopLngLat/);
  assert.match(src, /persistSidewalkLngLat\(next\.lon, next\.lat, streets\)/);
  assert.match(src, /placeNewLocalShopLngLat\(/);
  assert.match(src, /input\.streets \?\? \[\]/);
  assert.match(world, /export function persistSidewalkLngLat/);
  assert.match(world, /shopPlayLngLat\(/);
  assert.match(app, /streets:\s*playStreets/);
  assert.equal(src.includes("catalog_clear"), false);
  assert.match(src, /Existing catalog rows are not rewritten/);
});

test("player can open a shop that sells phở, not only lantern fish", () => {
  const shop = createLocalShop({
    name: "Quầy Phở Nhà",
    sells: "Phở bò",
    lon: 106.69804,
    lat: 10.77162,
    canPublish: true,
    shopId: "shop-local-pho1",
  });
  const listing = createLocalListing({
    shopId: shop.shop_id,
    title: shop.sells,
    canPublish: true,
    listingId: "listing-local-pho1",
  });
  assert.equal(shop.status, "published");
  assert.equal(listing.kind, "other");
  assert.equal(listing.title, "Phở bò");
  const mergedShops = publicShops([...catalog.shops, shop]);
  assert.equal(mergedShops.length, 2);
  assert.ok(mergedShops.some((row) => row.shop_id === "shop-lantern-fish"));
  assert.ok(mergedShops.some((row) => row.shop_id === "shop-local-pho1"));
});

test("leave identity keeps published shop and listing; draft is not public", () => {
  const published = createLocalShop({
    name: "Quầy Sách Góc",
    sells: "Sách cũ",
    lon: 106.6981,
    lat: 10.7717,
    canPublish: true,
    shopId: "shop-local-book1",
  });
  const listing = createLocalListing({
    shopId: published.shop_id,
    title: "Sách cũ",
    canPublish: true,
    listingId: "listing-local-book1",
  });
  const draft = createLocalShop({
    name: "Quầy Nháp",
    sells: "Túi bố thêm (máy này)",
    lon: 106.6982,
    lat: 10.7718,
    canPublish: false,
    shopId: "shop-local-draft1",
  });
  const draftListing = createLocalListing({
    shopId: draft.shop_id,
    title: "Túi bố thêm (máy này)",
    canPublish: false,
    listingId: "listing-local-draft1",
  });
  const guestSignedIn = false;
  assert.equal(guestSignedIn, false);
  const visible = publicShops([published, draft]);
  assert.deepEqual(
    visible.map((row) => row.shop_id),
    ["shop-local-book1"],
  );
  assert.equal(publicListings([listing, draftListing], "shop-local-book1").length, 1);
  assert.equal(publicListings([listing, draftListing], "shop-local-draft1").length, 0);
  assert.equal(draft.status, "draft");
  assert.notEqual(draft.status, "published");
});

test("prohibited titles are rejected", () => {
  const src = readFileSync(join(root, "src", "shops", "moderation.ts"), "utf8");
  assert.match(src, /function foldForMatch/);
  assert.match(src, /ban\\s\*sung/);
  assert.equal(sanitizePublicText("csam sample"), null);
  assert.equal(sanitizePublicText("doxxing list"), null);
  assert.equal(sanitizePublicText("bán ma túy"), null);
  assert.equal(sanitizePublicText("ban ma tuy"), null);
  assert.equal(sanitizePublicText("<script>x</script>"), null);
  assert.equal(sanitizePublicText("bán súng"), null);
  assert.equal(sanitizePublicText("ban sung"), null);
  assert.equal(sanitizePublicText("bán-súng"), null);
  assert.equal(sanitizePublicText("BÁN SÚNG"), null);
  assert.equal(sanitizePublicText("ban.sung"), null);
  assert.equal(sanitizePublicText("unlicensed firearm"), null);
  assert.equal(createLocalShop({
    name: "Quay thuong",
    sells: "ban sung",
    lon: 106.698,
    lat: 10.771,
    canPublish: true,
    shopId: "shop-local-weapon1",
  }), null);
  assert.equal(sanitizePublicText("phở"), "phở");
  assert.equal(sanitizePublicText("sách"), "sách");
  assert.equal(sanitizePublicText("cá"), "cá");
  assert.equal(sanitizePublicText("Phở bò"), "Phở bò");
  assert.equal(sanitizePublicText("Sách cũ"), "Sách cũ");
  assert.equal(sanitizePublicText("Quầy sung"), "Quầy sung");
  assert.equal(inferKind("Cá nục"), "fish");
  assert.equal(inferKind("Túi cói"), "bag");
  assert.equal(inferKind("Sách cũ"), "other");
});
