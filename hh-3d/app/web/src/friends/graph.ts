import { isSeatId, type SeatId } from "./seats";

export const FRIENDS_KEY = "hh-world.demo-friends.v1";

export type FriendPair = {
  left: SeatId;
  right: SeatId;
  status: "pending" | "accepted";
  requested_by: SeatId;
};

export type FriendGraph = {
  v: 1;
  kind: "local-demo-friends";
  pairs: FriendPair[];
  updated_at: number;
  not_presence_server: true;
  not_plan_pass: true;
};

export type FriendRelation = "none" | "outgoing" | "incoming" | "accepted";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function orderedPair(a: SeatId, b: SeatId): { left: SeatId; right: SeatId } | null {
  if (a === b) {
    return null;
  }
  const allow = (a === "a" && b === "b") || (a === "b" && b === "a");
  if (!allow) {
    return null;
  }
  return a < b ? { left: a, right: b } : { left: b, right: a };
}

export function emptyGraph(): FriendGraph {
  return {
    v: 1,
    kind: "local-demo-friends",
    pairs: [],
    updated_at: 0,
    not_presence_server: true,
    not_plan_pass: true,
  };
}

function sanitizePair(value: unknown): FriendPair | null {
  const rec = asRecord(value);
  if (!rec) {
    return null;
  }
  const left = rec["left"];
  const right = rec["right"];
  const requested = rec["requested_by"];
  if (!isSeatId(left) || !isSeatId(right) || !isSeatId(requested)) {
    return null;
  }
  const ordered = orderedPair(left, right);
  if (!ordered) {
    return null;
  }
  const status = rec["status"] === "accepted" ? "accepted" : rec["status"] === "pending" ? "pending" : null;
  if (!status) {
    return null;
  }
  if (requested !== ordered.left && requested !== ordered.right) {
    return null;
  }
  return {
    left: ordered.left,
    right: ordered.right,
    status,
    requested_by: requested,
  };
}

export function sanitizeGraph(value: unknown): FriendGraph | null {
  const rec = asRecord(value);
  if (!rec || rec["v"] !== 1 || rec["kind"] !== "local-demo-friends") {
    return null;
  }
  if (rec["not_presence_server"] !== true || rec["not_plan_pass"] !== true) {
    return null;
  }
  if (!Array.isArray(rec["pairs"])) {
    return null;
  }
  const pairs: FriendPair[] = [];
  for (const row of rec["pairs"]) {
    const pair = sanitizePair(row);
    if (pair) {
      pairs.push(pair);
    }
  }
  return {
    ...emptyGraph(),
    pairs,
    updated_at: typeof rec["updated_at"] === "number" ? rec["updated_at"] : 0,
  };
}

export function loadGraph(): FriendGraph {
  if (typeof localStorage === "undefined") {
    return emptyGraph();
  }
  try {
    const raw = localStorage.getItem(FRIENDS_KEY);
    if (!raw) {
      return emptyGraph();
    }
    return sanitizeGraph(JSON.parse(raw)) ?? emptyGraph();
  } catch {
    return emptyGraph();
  }
}

export function saveGraph(graph: FriendGraph): FriendGraph {
  const clean = sanitizeGraph({ ...graph, updated_at: Date.now() }) ?? emptyGraph();
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(FRIENDS_KEY, JSON.stringify(clean));
  }
  return clean;
}

function findPair(graph: FriendGraph, a: SeatId, b: SeatId): FriendPair | null {
  const ordered = orderedPair(a, b);
  if (!ordered) {
    return null;
  }
  return graph.pairs.find((row) => row.left === ordered.left && row.right === ordered.right) ?? null;
}

export function relation(graph: FriendGraph, me: SeatId, other: SeatId): FriendRelation {
  const pair = findPair(graph, me, other);
  if (!pair) {
    return "none";
  }
  if (pair.status === "accepted") {
    return "accepted";
  }
  return pair.requested_by === me ? "outgoing" : "incoming";
}

export function isMutualAccepted(graph: FriendGraph, a: SeatId, b: SeatId): boolean {
  return relation(graph, a, b) === "accepted";
}

export function requestFriend(graph: FriendGraph, from: SeatId, to: SeatId): FriendGraph {
  const ordered = orderedPair(from, to);
  if (!ordered) {
    return graph;
  }
  const existing = findPair(graph, from, to);
  if (existing?.status === "accepted") {
    return graph;
  }
  if (existing?.status === "pending" && existing.requested_by !== from) {
    return {
      ...graph,
      pairs: graph.pairs.map((row) =>
        row.left === ordered.left && row.right === ordered.right
          ? { ...row, status: "accepted" }
          : row,
      ),
    };
  }
  if (existing) {
    return graph;
  }
  return {
    ...graph,
    pairs: [
      ...graph.pairs,
      { left: ordered.left, right: ordered.right, status: "pending", requested_by: from },
    ],
  };
}

export function acceptFriend(graph: FriendGraph, me: SeatId, other: SeatId): FriendGraph {
  const ordered = orderedPair(me, other);
  if (!ordered) {
    return graph;
  }
  const existing = findPair(graph, me, other);
  if (!existing || existing.status !== "pending" || existing.requested_by === me) {
    return graph;
  }
  return {
    ...graph,
    pairs: graph.pairs.map((row) =>
      row.left === ordered.left && row.right === ordered.right
        ? { ...row, status: "accepted" }
        : row,
    ),
  };
}

export function unfriend(graph: FriendGraph, me: SeatId, other: SeatId): FriendGraph {
  const ordered = orderedPair(me, other);
  if (!ordered) {
    return graph;
  }
  return {
    ...graph,
    pairs: graph.pairs.filter((row) => row.left !== ordered.left || row.right !== ordered.right),
  };
}

export function canFriend(a: SeatId, b: SeatId): boolean {
  return orderedPair(a, b) !== null;
}

export type GraphOp = {
  op: "request" | "accept" | "unfriend";
  from: SeatId;
  to: SeatId;
};

export function applyGraphOp(graph: FriendGraph, op: GraphOp): FriendGraph {
  if (op.op === "request") {
    return requestFriend(graph, op.from, op.to);
  }
  if (op.op === "accept") {
    return acceptFriend(graph, op.from, op.to);
  }
  return unfriend(graph, op.from, op.to);
}
