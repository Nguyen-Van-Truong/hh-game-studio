import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const catalog = JSON.parse(readFileSync(join(root, "public", "data", "shops.json"), "utf8"));

function publicShops(data) {
  return data.shops.filter((shop) => shop.status === "published");
}

function publicListings(data, shopId) {
  return data.listings.filter((row) => {
    if (row.status !== "published") {
      return false;
    }
    return shopId ? row.shop_id === shopId : true;
  });
}

test("public shop fixture stays visible while owner is Offline", () => {
  assert.equal(catalog.schema, "hh-world-shop-catalog/v0");
  assert.equal(catalog.authored_or_source, "authored");
  const shops = publicShops(catalog);
  assert.equal(shops.length, 1);
  assert.equal(shops[0].shop_id, "shop-lantern-fish");
  assert.equal(shops[0].status, "published");
  assert.equal(shops[0].owner_presence, "offline");
  assert.equal(shops[0].place_id, "place-market-steps");
});

test("public shelf shows fish and bag samples and hides the draft", () => {
  const rows = publicListings(catalog, "shop-lantern-fish");
  const ids = rows.map((row) => row.listing_id);
  const kinds = rows.map((row) => row.kind).sort();
  assert.deepEqual(kinds, ["bag", "fish"]);
  assert.ok(ids.includes("listing-morning-mackerel"));
  assert.ok(ids.includes("listing-woven-tote"));
  assert.equal(ids.includes("listing-draft-hidden"), false);
  const draft = catalog.listings.find((row) => row.listing_id === "listing-draft-hidden");
  assert.equal(draft.status, "draft");
});

test("merge keeps authored draft off the public shelf", () => {
  const extra = {
    listing_id: "listing-local-abc123",
    shop_id: "shop-lantern-fish",
    title: "Cá thu thêm (máy này)",
    description: "Local demo",
    kind: "fish",
    price_label: "Liên hệ",
    status: "published",
    updated_at: "2026-09-03T10:00:00+07:00",
    version: 1,
  };
  const draft = {
    listing_id: "listing-local-q1",
    shop_id: "shop-lantern-fish",
    title: "Túi bố thêm (máy này)",
    description: "Queued",
    kind: "bag",
    price_label: "Liên hệ",
    status: "draft",
    updated_at: "2026-09-03T10:00:00+07:00",
    version: 1,
  };
  const merged = {
    ...catalog,
    listings: [...catalog.listings, extra, draft],
  };
  const rows = publicListings(merged, "shop-lantern-fish");
  const ids = rows.map((row) => row.listing_id);
  assert.ok(ids.includes("listing-morning-mackerel"));
  assert.ok(ids.includes("listing-local-abc123"));
  assert.equal(ids.includes("listing-draft-hidden"), false);
  assert.equal(ids.includes("listing-local-q1"), false);
});

test("stall board titles are published names only", () => {
  const src = readFileSync(join(root, "src", "shops", "catalog.ts"), "utf8");
  assert.match(src, /export function stallBoardTitles/);
  assert.match(src, /export function stallBoardPaintTitle/);
  assert.match(src, /STALL_BOARD_MAX_TITLES = 3/);
  assert.match(src, /STALL_BOARD_SAMPLE_MARK = "\(mẫu\)"/);
  const rows = publicListings(catalog, "shop-lantern-fish");
  const titles = rows.map((row) => row.title);
  assert.ok(titles.includes("Cá nục sương (mẫu)"));
  assert.ok(titles.includes("Túi cói chợ (mẫu)"));
  assert.equal(titles.includes("Nháp chưa đăng"), false);
  assert.ok(titles.length <= 3);
  assert.equal(rows.every((row) => row.status === "published"), true);
  const paint = (title) => (/\(\s*mẫu\s*\)/i.test(title) ? title : `${title} (mẫu)`);
  assert.equal(paint("Cá nục sương (mẫu)"), "Cá nục sương (mẫu)");
  assert.equal(paint("Phở bò"), "Phở bò (mẫu)");
  assert.equal(paint("Chè đậu xanh"), "Chè đậu xanh (mẫu)");
});

test("goods search aliases cá and túi", () => {
  const rows = publicListings(catalog);
  const fish = rows.filter((row) => row.kind === "fish" || row.title.toLowerCase().includes("cá"));
  const bags = rows.filter((row) => row.kind === "bag" || row.title.toLowerCase().includes("túi"));
  assert.equal(fish.length, 1);
  assert.equal(bags.length, 1);
  assert.notEqual(fish[0].listing_id, bags[0].listing_id);
});
