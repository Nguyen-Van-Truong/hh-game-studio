import { wrapHeadingDeg } from "./walk";

/** Degrees per CSS pixel. Slow enough that a pad turn still wins if both are used. */
export const LOOK_SENS_DEG = 0.14;
/** Same as hh-3d/demo lookYawSign. +1 was play-tested inverted (owner, twice). */
export const LOOK_YAW_SIGN = -1;
export const LOOK_PITCH_MIN = -42;
export const LOOK_PITCH_MAX = 28;

export type LookMode = "off" | "pointer-lock" | "drag";

export type LookState = {
  yaw: number;
  pitch: number;
  mode: LookMode;
};

export function clampLookPitch(pitch: number): number {
  return Math.max(LOOK_PITCH_MIN, Math.min(LOOK_PITCH_MAX, pitch));
}

export function applyLookDelta(look: LookState, dxPx: number, dyPx: number): LookState {
  return {
    ...look,
    yaw: wrapHeadingDeg(look.yaw + dxPx * LOOK_SENS_DEG * LOOK_YAW_SIGN),
    pitch: clampLookPitch(look.pitch - dyPx * LOOK_SENS_DEG),
  };
}

export function lookFromHeading(heading: number, pitch = 0, mode: LookMode = "off"): LookState {
  return { yaw: wrapHeadingDeg(heading), pitch: clampLookPitch(pitch), mode };
}
