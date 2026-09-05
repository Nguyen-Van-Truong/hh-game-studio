import assert from "node:assert/strict";
import test from "node:test";

function publishedOnly(shops, listings) {
  return {
    shops: shops.filter((row) => row.status === "published"),
    listings: listings.filter((row) => row.status === "published"),
  };
}

function keepLocalDrafts(local, incomingPublished, idOf) {
  const drafts = local.filter((row) => row.status !== "published");
  const seen = new Set(incomingPublished.map(idOf));
  return [...drafts.filter((row) => !seen.has(idOf(row))), ...incomingPublished];
}

function mergePublished(current, incoming, idKey) {
  const map = new Map();
  for (const row of [...current, ...incoming]) {
    if (row.status !== "published") continue;
    map.set(row[idKey], row);
  }
  return [...map.values()];
}

function orderedPair(a, b) {
  if (a === b) return null;
  if (!((a === "a" && b === "b") || (a === "b" && b === "a"))) return null;
  return a < b ? { left: a, right: b } : { left: b, right: a };
}

function applyGraphOp(pairs, op) {
  const ordered = orderedPair(op.from, op.to);
  if (!ordered) return pairs;
  const existing = pairs.find((row) => row.left === ordered.left && row.right === ordered.right);
  if (op.op === "unfriend") {
    return pairs.filter((row) => row.left !== ordered.left || row.right !== ordered.right);
  }
  if (op.op === "request") {
    if (existing?.status === "accepted") return pairs;
    if (existing?.status === "pending" && existing.requested_by !== op.from) {
      return pairs.map((row) =>
        row.left === ordered.left && row.right === ordered.right ? { ...row, status: "accepted" } : row,
      );
    }
    if (existing) return pairs;
    return [...pairs, { ...ordered, status: "pending", requested_by: op.from }];
  }
  if (op.op === "accept") {
    if (!existing || existing.status !== "pending" || existing.requested_by === op.from) return pairs;
    return pairs.map((row) =>
      row.left === ordered.left && row.right === ordered.right ? { ...row, status: "accepted" } : row,
    );
  }
  return pairs;
}

test("this-PC store rejects drafts; two clients see the same published shop", () => {
  let shops = [];
  let listings = [];
  const fromA = publishedOnly(
    [
      { shop_id: "shop-local-pho", status: "published", version: 1 },
      { shop_id: "shop-local-draft", status: "draft", version: 1 },
    ],
    [
      { listing_id: "listing-local-pho", status: "published", version: 1 },
      { listing_id: "listing-local-draft", status: "draft", version: 1 },
    ],
  );
  shops = mergePublished(shops, fromA.shops, "shop_id");
  listings = mergePublished(listings, fromA.listings, "listing_id");
  assert.deepEqual(
    shops.map((row) => row.shop_id),
    ["shop-local-pho"],
  );
  assert.deepEqual(
    listings.map((row) => row.listing_id),
    ["listing-local-pho"],
  );
  const clientB = keepLocalDrafts(
    [{ shop_id: "shop-local-mine", status: "draft" }],
    shops,
    (row) => row.shop_id,
  );
  assert.deepEqual(
    clientB.map((row) => row.shop_id),
    ["shop-local-mine", "shop-local-pho"],
  );
  assert.equal(clientB.find((row) => row.shop_id === "shop-local-mine")?.status, "draft");
});

test("graph ops are server-authoritative; stale empty snapshot does not unfriend", () => {
  let pairs = [];
  pairs = applyGraphOp(pairs, { op: "request", from: "a", to: "b" });
  pairs = applyGraphOp(pairs, { op: "accept", from: "b", to: "a" });
  assert.equal(pairs[0].status, "accepted");
  const staleEmpty = [];
  const merged = new Map();
  for (const row of [...pairs, ...staleEmpty]) {
    merged.set(`${row.left}:${row.right}`, row);
  }
  assert.equal([...merged.values()][0].status, "accepted");
  pairs = applyGraphOp(pairs, { op: "unfriend", from: "a", to: "b" });
  assert.deepEqual(pairs, []);
  assert.deepEqual(applyGraphOp([], { op: "request", from: "a", to: "c" }), []);
});

function shouldApplyStreetLeave(current, leaveSession) {
  const liveSession = current?.presence_session;
  if (typeof liveSession !== "string" || liveSession.length === 0) {
    return true;
  }
  return leaveSession === liveSession;
}

test("stale or unsigned leave does not wipe a newer visible publisher session", () => {
  const standing = { seat_id: "a", presence_session: "a-live-1", ts: 1000 };
  assert.equal(shouldApplyStreetLeave(standing, undefined), false);
  assert.equal(shouldApplyStreetLeave(standing, "a-old"), false);
  assert.equal(shouldApplyStreetLeave(standing, "a-live-1"), true);
  assert.equal(shouldApplyStreetLeave(undefined, "a-live-1"), true);
  assert.equal(shouldApplyStreetLeave({ ts: 1000 }, undefined), true);
});

test("loopback host allowlist is this PC only", () => {
  const ok = (host) => {
    const name = (host ?? "").split(":")[0].replace(/^\[|\]$/g, "");
    return name === "127.0.0.1" || name === "localhost" || name === "::1";
  };
  assert.equal(ok("127.0.0.1:4175"), true);
  assert.equal(ok("localhost:4175"), true);
  assert.equal(ok("203.0.113.8:4175"), false);
  assert.equal(ok("0.0.0.0:4175"), false);
});
