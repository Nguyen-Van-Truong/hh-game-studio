import { useCallback, useEffect, useRef, useState } from "react";
import { applyLookDelta, lookFromHeading, type LookMode, type LookState } from "./look";
import type { BuildingPoly, BBox, AvatarState } from "./walk";
import {
  applyJump,
  applyLookMove,
  AVATAR_SPAWN,
  integrateVertical,
  isWalkable,
  offsetLngLat,
  moveSpeedMps,
} from "./walk";

const MOVE = new Set(["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright"]);

export type PadState = {
  north: boolean;
  south: boolean;
  east: boolean;
  west: boolean;
  sprint: boolean;
};

const PAD_OFF: PadState = {
  north: false,
  south: false,
  east: false,
  west: false,
  sprint: false,
};

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function moveIntent(keys: Set<string>, pad: PadState): { forward: number; keySide: number } {
  let forward = 0;
  let keySide = 0;
  if (keys.has("w") || keys.has("arrowup") || pad.north) {
    forward += 1;
  }
  if (keys.has("s") || keys.has("arrowdown") || pad.south) {
    forward -= 1;
  }
  if (keys.has("d") || keys.has("arrowright") || pad.east) {
    keySide += 1;
  }
  if (keys.has("a") || keys.has("arrowleft") || pad.west) {
    keySide -= 1;
  }
  return { forward, keySide };
}

export function useAvatar(
  buildings: BuildingPoly[],
  bbox: BBox | null,
  onInteract: () => void,
  spawn: AvatarState = AVATAR_SPAWN,
  lookPitch = 0,
  lookYaw?: number,
): {
  avatar: AvatarState;
  blocked: boolean;
  slid: boolean;
  look: LookState;
  applyLookDeltaPx: (dx: number, dy: number) => void;
  setLookMode: (mode: LookMode) => void;
  setPad: (patch: Partial<PadState>) => void;
  resetPad: () => void;
  jump: () => void;
  isMoveHeld: () => boolean;
} {
  const [avatar, setAvatar] = useState<AvatarState>(spawn);
  const [blocked, setBlocked] = useState(false);
  const [slid, setSlid] = useState(false);
  const [look, setLook] = useState<LookState>(() => lookFromHeading(lookYaw ?? spawn.heading, lookPitch));
  const keysRef = useRef(new Set<string>());
  const padRef = useRef<PadState>({ ...PAD_OFF });
  const buildingsRef = useRef(buildings);
  const bboxRef = useRef(bbox);
  const interactRef = useRef(onInteract);
  const blockedRef = useRef(false);
  const slidRef = useRef(false);
  const jumpRef = useRef(false);
  const lookRef = useRef<LookState>(look);
  const moveHeldRef = useRef(false);
  buildingsRef.current = buildings;
  bboxRef.current = bbox;
  interactRef.current = onInteract;
  lookRef.current = look;

  useEffect(() => {
    setAvatar(spawn);
    const nextLook = lookFromHeading(lookYaw ?? spawn.heading, lookPitch);
    lookRef.current = nextLook;
    setLook(nextLook);
    padRef.current = { ...PAD_OFF };
    keysRef.current.clear();
  }, [spawn.lon, spawn.lat, spawn.heading, lookPitch, lookYaw]);

  const setPad = (patch: Partial<PadState>) => {
    padRef.current = { ...padRef.current, ...patch };
  };
  const resetPad = () => {
    padRef.current = { ...PAD_OFF, sprint: padRef.current.sprint };
  };
  const jump = () => {
    jumpRef.current = true;
  };

  const applyLookDeltaPx = useCallback((dx: number, dy: number) => {
    if (dx === 0 && dy === 0) {
      return;
    }
    const next = applyLookDelta(lookRef.current, dx, dy);
    lookRef.current = next;
    setLook(next);
    setAvatar((prev) => (prev.heading === next.yaw ? prev : { ...prev, heading: next.yaw }));
  }, []);

  const setLookMode = useCallback((mode: LookMode) => {
    if (lookRef.current.mode === mode) {
      return;
    }
    const next = { ...lookRef.current, mode };
    lookRef.current = next;
    setLook(next);
  }, []);

  useEffect(() => {
    const onDown = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) {
        return;
      }
      const key = event.key.toLowerCase();
      if (MOVE.has(key)) {
        event.preventDefault();
        keysRef.current.add(key);
        moveHeldRef.current = moveIntent(keysRef.current, padRef.current).forward !== 0;
      }
      if (event.code === "ShiftLeft" || event.code === "ShiftRight" || key === "shift") {
        keysRef.current.add("shift");
      }
      if (key === "e") {
        event.preventDefault();
        interactRef.current();
      }
      if (event.code === "Space" && !event.repeat) {
        event.preventDefault();
        jumpRef.current = true;
      }
    };
    const onUp = (event: KeyboardEvent) => {
      keysRef.current.delete(event.key.toLowerCase());
      if (event.code === "ShiftLeft" || event.code === "ShiftRight") {
        keysRef.current.delete("shift");
      }
      moveHeldRef.current = moveIntent(keysRef.current, padRef.current).forward !== 0;
    };
    const onBlur = () => {
      keysRef.current.clear();
      padRef.current = { ...PAD_OFF };
    };
    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", onUp);
    window.addEventListener("blur", onBlur);
    let last = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const box = bboxRef.current;
      if (box) {
        const { forward, keySide } = moveIntent(keysRef.current, padRef.current);
        moveHeldRef.current = forward !== 0 || keySide !== 0;
        const sprintHeld = keysRef.current.has("shift") || padRef.current.sprint;
        const wantsJump = jumpRef.current;
        jumpRef.current = false;
        setAvatar((prev) => {
          const launched = wantsJump ? applyJump(prev) : prev;
          const faced = { ...launched, heading: lookRef.current.yaw };
          let next = applyLookMove(faced, forward, keySide, dt, buildingsRef.current, box, sprintHeld);
          next = integrateVertical(next, dt);
          const stepM = moveSpeedMps(sprintHeld) * dt;
          const rad = (next.heading * Math.PI) / 180;
          const wanted = offsetLngLat(prev.lon, prev.lat, Math.sin(rad) * forward * stepM, Math.cos(rad) * forward * stepM);
          const fullBlocked =
            forward !== 0 && !isWalkable(wanted.lon, wanted.lat, buildingsRef.current, box);
          const moved = next.lon !== prev.lon || next.lat !== prev.lat;
          const hit = forward !== 0 && !moved && !next.airborne;
          const nowSlid = fullBlocked && moved;
          if (hit !== blockedRef.current) {
            blockedRef.current = hit;
            setBlocked(hit);
          }
          if (nowSlid !== slidRef.current) {
            slidRef.current = nowSlid;
            setSlid(nowSlid);
          }
          return next;
        });
        setLook((prev) => {
          const next = lookRef.current;
          return prev.yaw === next.yaw && prev.pitch === next.pitch && prev.mode === next.mode
            ? prev
            : next;
        });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", onUp);
      window.removeEventListener("blur", onBlur);
      cancelAnimationFrame(raf);
    };
  }, []);

  return {
    avatar,
    blocked,
    slid,
    look,
    applyLookDeltaPx,
    setLookMode,
    setPad,
    resetPad,
    jump,
    isMoveHeld: () => moveHeldRef.current,
  };
}
