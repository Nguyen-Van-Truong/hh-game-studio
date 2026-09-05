import { AVATAR_SPAWN, offsetLngLat, onGround, type AvatarState } from "../avatar/walk";

export const SEAT_IDS = ["a", "b", "c"] as const;
export type SeatId = (typeof SEAT_IDS)[number];

export type DemoSeat = {
  seat_id: SeatId;
  display_name: string;
  short_name: string;
  kind: "local-demo-seat";
  stranger: boolean;
  not_real_account: true;
  not_oidc: true;
  not_presence_server: true;
  not_plan_pass: true;
};

export const DEMO_SEATS: Record<SeatId, DemoSeat> = {
  a: {
    seat_id: "a",
    display_name: "Bạn A (máy này)",
    short_name: "Bạn A",
    kind: "local-demo-seat",
    stranger: false,
    not_real_account: true,
    not_oidc: true,
    not_presence_server: true,
    not_plan_pass: true,
  },
  b: {
    seat_id: "b",
    display_name: "Bạn B (máy này)",
    short_name: "Bạn B",
    kind: "local-demo-seat",
    stranger: false,
    not_real_account: true,
    not_oidc: true,
    not_presence_server: true,
    not_plan_pass: true,
  },
  c: {
    seat_id: "c",
    display_name: "Người lạ C (máy này)",
    short_name: "Người lạ C",
    kind: "local-demo-seat",
    stranger: true,
    not_real_account: true,
    not_oidc: true,
    not_presence_server: true,
    not_plan_pass: true,
  },
};

export const SEAT_SPAWNS: Record<SeatId, AvatarState> = {
  a: { ...AVATAR_SPAWN },
  b: onGround({
    ...offsetLngLat(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat, 7, 0),
    heading: 292,
    pose: "idle",
  }),
  c: onGround({
    ...offsetLngLat(AVATAR_SPAWN.lon, AVATAR_SPAWN.lat, -7, 0),
    heading: 90,
    pose: "idle",
  }),
};

/** Seat B looks at the street / A, not zenith. A keeps the north-sky default. */
export const SEAT_LOOK_PITCH: Record<SeatId, number> = {
  a: 0,
  b: -8,
  c: 0,
};

/** B aims WNW so the street-side camera sees A (~7 m west), not the east wall. */
export const SEAT_LOOK_YAW: Record<SeatId, number> = {
  a: 0,
  b: 292,
  c: 90,
};

export function isSeatId(value: unknown): value is SeatId {
  return value === "a" || value === "b" || value === "c";
}

export function readSeatFromUrl(search = window.location.search): SeatId {
  const raw = new URLSearchParams(search).get("seat");
  return isSeatId(raw) ? raw : "a";
}

export function otherFriendSeat(seat: SeatId): SeatId | null {
  if (seat === "a") {
    return "b";
  }
  if (seat === "b") {
    return "a";
  }
  return null;
}
