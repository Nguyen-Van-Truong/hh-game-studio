/** Corner MapLibre waits for idle Play frames. Not a restored dashboard. */
export const MINIMAP_DEFER_KIND = "play-idle" as const;
/** Idle-pose rAF after first Play paint; walk time does not count. */
export const MINIMAP_DEFER_MS = 800;

/** Construct MapLibre only after idle Play frames. First W does not mount it. */
export function minimapMayConstruct(
  playPainted: boolean,
  idlePoseMs: number,
  pose: "idle" | "walk",
  walkHeld = false,
): boolean {
  if (!playPainted || pose === "walk" || walkHeld) {
    return false;
  }
  return idlePoseMs >= MINIMAP_DEFER_MS;
}
