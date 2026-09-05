import type { PresenceMode } from "../modes/modes";
import { isSeatId, type SeatId } from "./seats";

export const SEAT_MODE_KEY = "hh-world.demo-seat-mode.v1";

export type SeatModeRow = {
  mode: PresenceMode;
  opted_in: boolean;
};

const DEFAULT_ROW: SeatModeRow = { mode: "offline", opted_in: false };

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function sanitizeRow(value: unknown): SeatModeRow {
  const rec = asRecord(value);
  if (!rec) {
    return { ...DEFAULT_ROW };
  }
  return {
    mode: rec["mode"] === "online" ? "online" : "offline",
    opted_in: rec["opted_in"] === true,
  };
}

export function loadSeatModes(): Record<SeatId, SeatModeRow> {
  const empty: Record<SeatId, SeatModeRow> = {
    a: { ...DEFAULT_ROW },
    b: { ...DEFAULT_ROW },
    c: { ...DEFAULT_ROW },
  };
  if (typeof localStorage === "undefined") {
    return empty;
  }
  try {
    const raw = localStorage.getItem(SEAT_MODE_KEY);
    if (!raw) {
      return empty;
    }
    const rec = asRecord(JSON.parse(raw));
    if (!rec) {
      return empty;
    }
    for (const seat of ["a", "b", "c"] as const) {
      empty[seat] = sanitizeRow(rec[seat]);
    }
    return empty;
  } catch {
    return empty;
  }
}

export function loadSeatMode(seat: SeatId): SeatModeRow {
  return loadSeatModes()[seat];
}

export function saveSeatMode(seat: SeatId, row: SeatModeRow): SeatModeRow {
  const all = loadSeatModes();
  all[seat] = {
    mode: row.mode === "online" ? "online" : "offline",
    opted_in: row.opted_in === true,
  };
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(SEAT_MODE_KEY, JSON.stringify(all));
  }
  return all[seat];
}

export function parseSeatParam(value: string | null): SeatId {
  return isSeatId(value) ? value : "a";
}
