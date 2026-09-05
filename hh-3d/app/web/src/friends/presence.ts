import type { AvatarPose } from "../avatar/walk";
import type { PresenceMode } from "../modes/modes";
import { isMutualAccepted, type FriendGraph } from "./graph";
import { DEMO_SEATS, isSeatId, type SeatId } from "./seats";

export const PRESENCE_TTL_MS = 10000;
export const PRESENCE_MOVE_MS = 200;
export const PRESENCE_IDLE_MS = 2000;

export type PresencePacket = {
  v: 1;
  kind: "local-demo-presence";
  seat_id: SeatId;
  display_name: string;
  mode: PresenceMode;
  opted_in: boolean;
  lon: number;
  lat: number;
  heading: number;
  pose: AvatarPose;
  /** Optional. Missing on older local packets; remotes then walk, not sprint. */
  sprint?: boolean;
  /** Optional. Set while this seat has a shop shelf open. Not a shared interior. */
  viewing_shop_id?: string;
  /** Optional. This-PC publisher generation; stale tab leave cannot wipe it. */
  presence_session?: string;
  ts: number;
  not_gps: true;
  not_presence_server: true;
  not_plan_pass: true;
};

export const VIEWING_SHOP_COPY = "Đang xem cửa hàng";
const VIEWING_SHOP_ID = /^shop-[a-z0-9-]+$/;

export type VisibleFriend = {
  seat_id: SeatId;
  display_name: string;
  lon: number;
  lat: number;
  heading: number;
  pose: AvatarPose;
  ts: number;
  alt: number;
  vy: number;
  airborne: boolean;
  sprint: boolean;
  turning: boolean;
  viewing_shop_id: string | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

export function sanitizeViewingShopId(value: unknown): string | null {
  return typeof value === "string" && VIEWING_SHOP_ID.test(value) ? value : null;
}

export function isStreetFriend(friend: Pick<VisibleFriend, "viewing_shop_id">): boolean {
  return !friend.viewing_shop_id;
}

export function makePresencePacket(input: {
  seat: SeatId;
  mode: PresenceMode;
  optedIn: boolean;
  lon: number;
  lat: number;
  heading: number;
  pose: AvatarPose;
  sprint?: boolean;
  viewingShopId?: string | null;
  presenceSession?: string;
  now?: number;
}): PresencePacket {
  const viewing = sanitizeViewingShopId(input.viewingShopId);
  const presenceSession =
    typeof input.presenceSession === "string" && /^[a-z0-9-]{6,64}$/i.test(input.presenceSession)
      ? input.presenceSession
      : null;
  return {
    v: 1,
    kind: "local-demo-presence",
    seat_id: input.seat,
    display_name: DEMO_SEATS[input.seat].display_name,
    mode: input.mode,
    opted_in: input.optedIn,
    lon: input.lon,
    lat: input.lat,
    heading: input.heading,
    pose: input.pose,
    sprint: input.sprint === true,
    ...(viewing ? { viewing_shop_id: viewing } : {}),
    ...(presenceSession ? { presence_session: presenceSession } : {}),
    ts: input.now ?? Date.now(),
    not_gps: true,
    not_presence_server: true,
    not_plan_pass: true,
  };
}

export function sanitizePresence(value: unknown): PresencePacket | null {
  const rec = asRecord(value);
  if (!rec || rec["v"] !== 1 || rec["kind"] !== "local-demo-presence") {
    return null;
  }
  const seat = rec["seat_id"];
  if (!isSeatId(seat)) {
    return null;
  }
  if (rec["not_gps"] !== true || rec["not_presence_server"] !== true || rec["not_plan_pass"] !== true) {
    return null;
  }
  if (rec["mode"] !== "online" && rec["mode"] !== "offline") {
    return null;
  }
  if (typeof rec["opted_in"] !== "boolean") {
    return null;
  }
  if (typeof rec["lon"] !== "number" || typeof rec["lat"] !== "number") {
    return null;
  }
  if (typeof rec["heading"] !== "number" || typeof rec["ts"] !== "number") {
    return null;
  }
  if (rec["pose"] !== "idle" && rec["pose"] !== "walk") {
    return null;
  }
  const viewing = sanitizeViewingShopId(rec["viewing_shop_id"]);
  const sessionRaw = rec["presence_session"];
  const presence_session =
    typeof sessionRaw === "string" && /^[a-z0-9-]{6,64}$/i.test(sessionRaw) ? sessionRaw : null;
  return {
    v: 1,
    kind: "local-demo-presence",
    seat_id: seat,
    display_name: DEMO_SEATS[seat].display_name,
    mode: rec["mode"],
    opted_in: rec["opted_in"],
    lon: rec["lon"],
    lat: rec["lat"],
    heading: rec["heading"],
    pose: rec["pose"],
    sprint: rec["sprint"] === true,
    ...(viewing ? { viewing_shop_id: viewing } : {}),
    ...(presence_session ? { presence_session } : {}),
    ts: rec["ts"],
    not_gps: true,
    not_presence_server: true,
    not_plan_pass: true,
  };
}

export function isFresh(packet: PresencePacket, now: number, ttlMs = PRESENCE_TTL_MS): boolean {
  return now - packet.ts <= ttlMs;
}

export function isPublishing(packet: Pick<PresencePacket, "mode" | "opted_in">): boolean {
  return packet.mode === "online" && packet.opted_in;
}

/** Tab visible enough to publish this-PC street presence. Hide is not Offline. */
export function isDocumentStreetVisible(
  doc: { hidden?: boolean; visibilityState?: string } | null | undefined =
    typeof document !== "undefined" ? document : null,
): boolean {
  if (!doc) {
    return true;
  }
  return doc.visibilityState !== "hidden" && doc.hidden !== true;
}

/**
 * Street publish gate for this seat. Hidden / not opted-in / Offline / no
 * bus: do not publish. Never flips social mode — hide is not Offline.
 */
export function shouldPublishStreetPresence(input: {
  mode: PresenceMode;
  opted_in: boolean;
  connected: boolean;
  documentVisible: boolean;
}): boolean {
  return input.connected && isPublishing({ mode: input.mode, opted_in: input.opted_in }) && input.documentVisible;
}

export type StreetPresenceIntent = "publish" | "leave" | "hold";

/**
 * Leave only on the falling edge (was publishing → should not).
 * A visible Online opted-in tick never leaves. Repeat hidden ticks hold.
 * visibilitychange to visible is publish, not leave.
 */
export function streetPresenceIntent(input: {
  shouldPublish: boolean;
  wasPublishing: boolean;
}): StreetPresenceIntent {
  if (input.shouldPublish) {
    return "publish";
  }
  return input.wasPublishing ? "leave" : "hold";
}

export function visibleFriends(input: {
  viewer: SeatId;
  viewerMode: PresenceMode;
  viewerOptedIn: boolean;
  connected: boolean;
  graph: FriendGraph;
  others: PresencePacket[];
  now: number;
}): VisibleFriend[] {
  if (input.viewerMode !== "online" || !input.viewerOptedIn || !input.connected) {
    return [];
  }
  const out: VisibleFriend[] = [];
  for (const packet of input.others) {
    if (packet.seat_id === input.viewer) {
      continue;
    }
    if (!isPublishing(packet) || !isFresh(packet, input.now)) {
      continue;
    }
    if (!isMutualAccepted(input.graph, input.viewer, packet.seat_id)) {
      continue;
    }
    out.push({
      seat_id: packet.seat_id,
      display_name: packet.display_name,
      lon: packet.lon,
      lat: packet.lat,
      heading: packet.heading,
      pose: packet.pose,
      ts: packet.ts,
      alt: 0,
      vy: 0,
      airborne: false,
      sprint: packet.sprint === true && packet.pose === "walk",
      turning: false,
      viewing_shop_id: sanitizeViewingShopId(packet.viewing_shop_id),
    });
  }
  return out;
}
