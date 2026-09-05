export type PresenceMode = "offline" | "online";
export type ConnectionState = "connected" | "lost" | "reconnecting";
export type ConnectionAttr = "on" | "off" | "retry";

export const DEFAULT_PRESENCE: PresenceMode = "offline";

/** Brief HUD flash only (400–1200 ms). Not a presence reconnect server. */
export const RECONNECT_FLASH_MS = 800;

/** Local demo seats on this machine. Not a city presence server. Not M2-WP1. */
export const ONLINE_AVAILABLE = true;

/** Raw online bit. Reconnecting is a pill flash, not this mapping. */
export function connectionState(online: boolean): ConnectionState {
  return online ? "connected" : "lost";
}

/** lost → online becomes reconnecting. First paint / stay-online does not flash. */
export function nextConnectionPill(wasOnline: boolean, online: boolean): ConnectionState {
  if (!online) {
    return "lost";
  }
  if (!wasOnline) {
    return "reconnecting";
  }
  return "connected";
}

export function connectionCopy(state: ConnectionState): string {
  if (state === "lost") {
    return "Mất kết nối";
  }
  if (state === "reconnecting") {
    return "Đang kết nối lại";
  }
  return "Máy này · 4175";
}

export function connectionAttr(state: ConnectionState): ConnectionAttr {
  if (state === "lost") {
    return "off";
  }
  if (state === "reconnecting") {
    return "retry";
  }
  return "on";
}

export function presenceCopy(mode: PresenceMode): string {
  if (mode === "online") {
    return "Online — Meet friends on this machine.";
  }
  return "Offline — Stroll alone; shops still open.";
}

export function presenceChipCopy(mode: PresenceMode): string {
  return mode === "online" ? "Online" : "Offline";
}
