import assert from "node:assert/strict";
import test from "node:test";

const DEMO_OWNER_ID = "owner-local-demo-machine";
const DEMO_DISPLAY_NAME = "Chủ quầy (máy này)";
const LISTING_ID = /^listing-local-[a-z0-9-]+$/;

function guestIdentity() {
  return {
    v: 1,
    kind: "local-demo",
    owner_id: DEMO_OWNER_ID,
    display_name: DEMO_DISPLAY_NAME,
    signed_in: false,
    not_real_account: true,
    not_oidc: true,
    not_google: true,
    not_plan_pass: true,
  };
}

function sanitizeDemoIdentity(value) {
  if (!value || value.v !== 1 || value.kind !== "local-demo") {
    return null;
  }
  if (value.owner_id !== DEMO_OWNER_ID) {
    return null;
  }
  if (
    value.not_real_account !== true ||
    value.not_oidc !== true ||
    value.not_google !== true ||
    value.not_plan_pass !== true
  ) {
    return null;
  }
  if (typeof value.signed_in !== "boolean") {
    return null;
  }
  return { ...guestIdentity(), signed_in: value.signed_in };
}

function networkAllowsPublish(browserOnline, networkCutSim) {
  return browserOnline && !networkCutSim;
}

function sanitizeTitle(raw) {
  const title = raw.trim().replace(/\s+/g, " ");
  if (title.length < 2 || title.length > 80) {
    return null;
  }
  if (/[<>]/.test(title)) {
    return null;
  }
  return title;
}

function createLocalListing(input) {
  const title = sanitizeTitle(input.title);
  if (!title) {
    return null;
  }
  const listing_id = input.listingId;
  if (!LISTING_ID.test(listing_id)) {
    return null;
  }
  return {
    listing_id,
    shop_id: input.shopId,
    title,
    status: input.canPublish ? "published" : "draft",
    queued: !input.canPublish,
  };
}

function publicListings(rows, shopId) {
  return rows.filter((row) => row.status === "published" && row.shop_id === shopId);
}

function retryQueuedListing(rows, listingId, canPublish) {
  return rows.map((row) => {
    if (row.listing_id !== listingId || !row.queued || row.status !== "draft") {
      return row;
    }
    if (!canPublish) {
      return row;
    }
    return { ...row, status: "published", queued: false };
  });
}

test("demo identity is local-demo and never an invented human owner", () => {
  const signedIn = sanitizeDemoIdentity({ ...guestIdentity(), signed_in: true });
  assert.equal(signedIn.display_name, "Chủ quầy (máy này)");
  assert.equal(signedIn.kind, "local-demo");
  assert.equal(signedIn.not_oidc, true);
  assert.equal(signedIn.not_google, true);
  assert.equal(signedIn.not_plan_pass, true);
  assert.equal(sanitizeDemoIdentity({ ...guestIdentity(), kind: "oidc" }), null);
  assert.equal(sanitizeDemoIdentity({ ...guestIdentity(), owner_id: "owner-truong" }), null);
  assert.equal(
    sanitizeDemoIdentity({ ...guestIdentity(), display_name: "Truong", signed_in: true }).display_name,
    "Chủ quầy (máy này)",
  );
});

test("social Offline plus network still publishes; no-network stays draft", () => {
  const socialOffline = true;
  assert.equal(socialOffline && networkAllowsPublish(true, false), true);
  assert.equal(networkAllowsPublish(true, true), false);
  assert.equal(networkAllowsPublish(false, false), false);
  const posted = createLocalListing({
    shopId: "shop-lantern-fish",
    title: "Cá thu thêm (máy này)",
    canPublish: true,
    listingId: "listing-local-abc123",
  });
  const queued = createLocalListing({
    shopId: "shop-lantern-fish",
    title: "Túi bố thêm (máy này)",
    canPublish: false,
    listingId: "listing-local-def456",
  });
  assert.equal(posted.status, "published");
  assert.equal(posted.queued, false);
  assert.equal(queued.status, "draft");
  assert.equal(queued.queued, true);
  const shelf = publicListings([posted, queued], "shop-lantern-fish");
  assert.deepEqual(
    shelf.map((row) => row.listing_id),
    ["listing-local-abc123"],
  );
});

test("logout keeps published public and does not auto-publish drafts", () => {
  const rows = [
    createLocalListing({
      shopId: "shop-lantern-fish",
      title: "Cá thu thêm (máy này)",
      canPublish: true,
      listingId: "listing-local-pub1",
    }),
    createLocalListing({
      shopId: "shop-lantern-fish",
      title: "Túi bố thêm (máy này)",
      canPublish: false,
      listingId: "listing-local-q1",
    }),
  ];
  const afterLeave = { identity: guestIdentity(), rows };
  assert.equal(afterLeave.identity.signed_in, false);
  const guestShelf = publicListings(afterLeave.rows, "shop-lantern-fish");
  assert.equal(guestShelf.length, 1);
  assert.equal(guestShelf[0].listing_id, "listing-local-pub1");
  const stillQueued = retryQueuedListing(afterLeave.rows, "listing-local-q1", false);
  assert.equal(stillQueued[1].status, "draft");
  const retried = retryQueuedListing(afterLeave.rows, "listing-local-q1", true);
  assert.equal(retried[1].status, "published");
});

test("title allowlist rejects markup", () => {
  assert.equal(sanitizeTitle("<script>x</script>"), null);
  assert.equal(sanitizeTitle("Cá thu thêm (máy này)"), "Cá thu thêm (máy này)");
});
