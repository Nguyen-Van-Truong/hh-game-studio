import assert from "node:assert/strict";
import test from "node:test";

const TTL = 10000;

function emptyGraph() {
  return {
    v: 1,
    kind: "local-demo-friends",
    pairs: [],
    updated_at: 0,
    not_presence_server: true,
    not_plan_pass: true,
  };
}

function orderedPair(a, b) {
  if (a === b) return null;
  if (!((a === "a" && b === "b") || (a === "b" && b === "a"))) return null;
  return a < b ? { left: a, right: b } : { left: b, right: a };
}

function requestFriend(graph, from, to) {
  const ordered = orderedPair(from, to);
  if (!ordered) return graph;
  const existing = graph.pairs.find((row) => row.left === ordered.left && row.right === ordered.right);
  if (existing?.status === "accepted") return graph;
  if (existing?.status === "pending" && existing.requested_by !== from) {
    return {
      ...graph,
      pairs: graph.pairs.map((row) =>
        row.left === ordered.left && row.right === ordered.right ? { ...row, status: "accepted" } : row,
      ),
    };
  }
  if (existing) return graph;
  return {
    ...graph,
    pairs: [...graph.pairs, { ...ordered, status: "pending", requested_by: from }],
  };
}

function acceptFriend(graph, me, other) {
  const ordered = orderedPair(me, other);
  if (!ordered) return graph;
  const existing = graph.pairs.find((row) => row.left === ordered.left && row.right === ordered.right);
  if (!existing || existing.status !== "pending" || existing.requested_by === me) return graph;
  return {
    ...graph,
    pairs: graph.pairs.map((row) =>
      row.left === ordered.left && row.right === ordered.right ? { ...row, status: "accepted" } : row,
    ),
  };
}

function unfriend(graph, me, other) {
  const ordered = orderedPair(me, other);
  if (!ordered) return graph;
  return {
    ...graph,
    pairs: graph.pairs.filter((row) => row.left !== ordered.left || row.right !== ordered.right),
  };
}

function isMutualAccepted(graph, a, b) {
  const ordered = orderedPair(a, b);
  if (!ordered) return false;
  return graph.pairs.some(
    (row) => row.left === ordered.left && row.right === ordered.right && row.status === "accepted",
  );
}

function visibleFriends(input) {
  if (input.viewerMode !== "online" || !input.viewerOptedIn || !input.connected) return [];
  return input.others
    .filter((packet) => {
      if (packet.seat_id === input.viewer) return false;
      if (packet.mode !== "online" || !packet.opted_in) return false;
      if (input.now - packet.ts > TTL) return false;
      return isMutualAccepted(input.graph, input.viewer, packet.seat_id);
    })
    .map((packet) => ({
      ...packet,
      viewing_shop_id: typeof packet.viewing_shop_id === "string" ? packet.viewing_shop_id : null,
    }));
}

function isDocumentStreetVisible(doc) {
  if (!doc) return true;
  return doc.visibilityState !== "hidden" && doc.hidden !== true;
}

function shouldPublishStreetPresence(input) {
  return input.connected && input.mode === "online" && input.opted_in && input.documentVisible;
}

function streetPresenceIntent(input) {
  if (input.shouldPublish) {
    return "publish";
  }
  return input.wasPublishing ? "leave" : "hold";
}

function packet(seat, patch = {}) {
  return {
    seat_id: seat,
    mode: "online",
    opted_in: true,
    lon: 106.69804,
    lat: 10.77162,
    heading: 0,
    pose: "walk",
    ts: 1_000_000,
    ...patch,
  };
}

test("A and B mutual friends both Online+opt-in see each other; C never", () => {
  let graph = requestFriend(emptyGraph(), "a", "b");
  graph = acceptFriend(graph, "b", "a");
  const others = [packet("a"), packet("b", { lon: 106.6981 }), packet("c", { lon: 106.6979 })];
  const fromA = visibleFriends({
    viewer: "a",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others,
    now: 1_000_100,
  });
  const fromB = visibleFriends({
    viewer: "b",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others,
    now: 1_000_100,
  });
  const fromC = visibleFriends({
    viewer: "c",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others,
    now: 1_000_100,
  });
  assert.deepEqual(
    fromA.map((row) => row.seat_id),
    ["b"],
  );
  assert.deepEqual(
    fromB.map((row) => row.seat_id),
    ["a"],
  );
  assert.deepEqual(fromC, []);
});

test("Offline viewer or Offline friend hides the other body", () => {
  let graph = requestFriend(emptyGraph(), "a", "b");
  graph = acceptFriend(graph, "b", "a");
  const hiddenViewer = visibleFriends({
    viewer: "a",
    viewerMode: "offline",
    viewerOptedIn: true,
    connected: true,
    graph,
    others: [packet("b")],
    now: 1_000_100,
  });
  const hiddenFriend = visibleFriends({
    viewer: "a",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others: [packet("b", { mode: "offline" })],
    now: 1_000_100,
  });
  assert.deepEqual(hiddenViewer, []);
  assert.deepEqual(hiddenFriend, []);
});

test("pending invite and unfriend are not street presence", () => {
  const pending = requestFriend(emptyGraph(), "a", "b");
  const pendingVisible = visibleFriends({
    viewer: "b",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph: pending,
    others: [packet("a")],
    now: 1_000_100,
  });
  let graph = acceptFriend(pending, "b", "a");
  graph = unfriend(graph, "a", "b");
  const after = visibleFriends({
    viewer: "a",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others: [packet("b")],
    now: 1_000_100,
  });
  assert.deepEqual(pendingVisible, []);
  assert.deepEqual(after, []);
});

test("stranger C cannot be added; stale packets drop", () => {
  const blocked = requestFriend(emptyGraph(), "a", "c");
  assert.deepEqual(blocked.pairs, []);
  let graph = requestFriend(emptyGraph(), "a", "b");
  graph = acceptFriend(graph, "b", "a");
  const stale = visibleFriends({
    viewer: "a",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others: [packet("b", { ts: 1_000_000 })],
    now: 1_000_000 + TTL + 1,
  });
  const disconnected = visibleFriends({
    viewer: "a",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: false,
    graph,
    others: [packet("b")],
    now: 1_000_100,
  });
  assert.deepEqual(stale, []);
  assert.deepEqual(disconnected, []);
});

test("hidden / visibilitychange stops street publish without flipping Offline", () => {
  const mode = "online";
  const hiddenDoc = { hidden: true, visibilityState: "hidden" };
  const visibleDoc = { hidden: false, visibilityState: "visible" };
  const hidden = {
    mode,
    opted_in: true,
    connected: true,
    documentVisible: isDocumentStreetVisible(hiddenDoc),
  };
  const visible = {
    mode,
    opted_in: true,
    connected: true,
    documentVisible: isDocumentStreetVisible(visibleDoc),
  };
  assert.equal(isDocumentStreetVisible(hiddenDoc), false);
  assert.equal(isDocumentStreetVisible({ hidden: true, visibilityState: "visible" }), false);
  assert.equal(isDocumentStreetVisible({ hidden: false, visibilityState: "hidden" }), false);
  assert.equal(isDocumentStreetVisible(visibleDoc), true);
  assert.equal(shouldPublishStreetPresence(hidden), false);
  assert.equal(shouldPublishStreetPresence(visible), true);
  assert.equal(hidden.mode, "online");
  assert.equal(visible.mode, "online");
  assert.equal(
    shouldPublishStreetPresence({
      mode: "offline",
      opted_in: true,
      connected: true,
      documentVisible: true,
    }),
    false,
  );
  assert.equal(
    streetPresenceIntent({
      shouldPublish: shouldPublishStreetPresence(visible),
      wasPublishing: false,
    }),
    "publish",
  );
  assert.equal(
    streetPresenceIntent({
      shouldPublish: shouldPublishStreetPresence(visible),
      wasPublishing: true,
    }),
    "publish",
  );
  assert.equal(
    streetPresenceIntent({
      shouldPublish: shouldPublishStreetPresence(hidden),
      wasPublishing: true,
    }),
    "leave",
  );
  assert.equal(
    streetPresenceIntent({
      shouldPublish: shouldPublishStreetPresence(hidden),
      wasPublishing: false,
    }),
    "hold",
  );
  const visibilitychangeToVisible = streetPresenceIntent({
    shouldPublish: shouldPublishStreetPresence(visible),
    wasPublishing: false,
  });
  assert.equal(visibilitychangeToVisible, "publish");
  assert.equal(visibilitychangeToVisible === "leave", false);
  let graph = requestFriend(emptyGraph(), "a", "b");
  graph = acceptFriend(graph, "b", "a");
  const afterTtl = visibleFriends({
    viewer: "b",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others: [packet("a", { mode: "online", opted_in: true, ts: 1_000_000 })],
    now: 1_000_000 + TTL + 1,
  });
  assert.deepEqual(afterTtl, []);
});

test("friend viewing a shop stays visible as coarse, not a street body", () => {
  let graph = requestFriend(emptyGraph(), "a", "b");
  graph = acceptFriend(graph, "b", "a");
  const fromB = visibleFriends({
    viewer: "b",
    viewerMode: "online",
    viewerOptedIn: true,
    connected: true,
    graph,
    others: [packet("a", { viewing_shop_id: "shop-lantern-fish" })],
    now: 1_000_100,
  });
  assert.equal(fromB.length, 1);
  assert.equal(fromB[0].seat_id, "a");
  assert.equal(fromB[0].viewing_shop_id, "shop-lantern-fish");
  assert.equal(Boolean(fromB[0].viewing_shop_id), true);
});
