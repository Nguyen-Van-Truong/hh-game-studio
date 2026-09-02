export type PlayHud = {
  boarded: boolean;
  nearBoat: boolean;
  hasMoved: boolean;
};

export const WALK_SPEED = 2.55;
export const RUN_SPEED = 4.35;
export const BOAT_SPEED = 3.7;
export const BOAT_TURN = 1.85;
export const JUMP_SPEED = 6.1;
export const GRAVITY = 17;
export const PUNCH_DURATION = 0.4;
export const PUNCH_COMBO_AFTER = 0.3;
export const MAX_STEP_DT = 0.05;

export function clampDelta(delta: number): number {
  if (delta < 0) {
    return 0;
  }
  return delta > MAX_STEP_DT ? MAX_STEP_DT : delta;
}

/** Shortest-path yaw blend so the person turns to face travel. */
export function lerpAngle(current: number, target: number, t: number): number {
  let delta = target - current;
  while (delta > Math.PI) {
    delta -= Math.PI * 2;
  }
  while (delta < -Math.PI) {
    delta += Math.PI * 2;
  }
  const k = t < 0 ? 0 : t > 1 ? 1 : t;
  return current + delta * k;
}

export function playStatus(boarded: boolean): string {
  return boarded ? "Trên thuyền" : "Đi bộ";
}
