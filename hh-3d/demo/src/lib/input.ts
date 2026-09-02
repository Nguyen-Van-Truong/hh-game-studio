import { useEffect, useRef, type RefObject } from "react";

export type PlayerInput = {
  x: number;
  z: number;
  run: boolean;
  interactEdge: boolean;
  lookDx: number;
  lookDy: number;
  lookEnabled: boolean;
  jumpEdge: boolean;
  punchEdge: boolean;
};

export function clearPlayerInput(input: PlayerInput): void {
  input.x = 0;
  input.z = 0;
  input.run = false;
  input.interactEdge = false;
  input.lookDx = 0;
  input.lookDy = 0;
  input.jumpEdge = false;
  input.punchEdge = false;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT"
  );
}

export function createPlayerInput(): PlayerInput {
  return {
    x: 0,
    z: 0,
    run: false,
    interactEdge: false,
    lookDx: 0,
    lookDy: 0,
    lookEnabled: false,
    jumpEdge: false,
    punchEdge: false,
  };
}

export function consumeJump(input: PlayerInput): boolean {
  if (!input.jumpEdge) {
    return false;
  }
  input.jumpEdge = false;
  return true;
}

export function consumePunch(input: PlayerInput): boolean {
  if (!input.punchEdge) {
    return false;
  }
  input.punchEdge = false;
  return true;
}

export function consumeLook(input: PlayerInput): { dx: number; dy: number } {
  const dx = input.lookDx;
  const dy = input.lookDy;
  input.lookDx = 0;
  input.lookDy = 0;
  return { dx, dy };
}

export function consumeInteract(input: PlayerInput): boolean {
  if (!input.interactEdge) {
    return false;
  }
  input.interactEdge = false;
  return true;
}

export function setAxis(
  input: PlayerInput,
  axis: "x" | "z",
  value: number,
): void {
  input[axis] = value < -1 ? -1 : value > 1 ? 1 : value;
}

const MOVE_CODES = new Set([
  "KeyW",
  "KeyA",
  "KeyS",
  "KeyD",
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "ShiftLeft",
  "ShiftRight",
  "Space",
]);

export function usePlayerInput(): RefObject<PlayerInput> {
  const inputRef = useRef<PlayerInput>(createPlayerInput());

  useEffect(() => {
    const held = new Set<string>();
    const input = inputRef.current;

    const sync = () => {
      const right =
        held.has("KeyD") || held.has("ArrowRight") ? 1 : 0;
      const left = held.has("KeyA") || held.has("ArrowLeft") ? 1 : 0;
      const forward = held.has("KeyW") || held.has("ArrowUp") ? 1 : 0;
      const back = held.has("KeyS") || held.has("ArrowDown") ? 1 : 0;
      input.x = right - left;
      input.z = forward - back;
      input.run = held.has("ShiftLeft") || held.has("ShiftRight");
    };

    const onDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) {
        return;
      }
      if (event.code === "KeyE" && !event.repeat) {
        input.interactEdge = true;
      }
      if (event.code === "Space" && !event.repeat) {
        input.jumpEdge = true;
      }
      if (event.code === "KeyF" && !event.repeat) {
        input.punchEdge = true;
      }
      if (
        !MOVE_CODES.has(event.code) &&
        event.code !== "KeyE" &&
        event.code !== "KeyF"
      ) {
        return;
      }
      if (
        event.code.startsWith("Arrow") ||
        event.code === "KeyE" ||
        event.code === "Space"
      ) {
        event.preventDefault();
      }
      held.add(event.code);
      sync();
    };

    const onUp = (event: KeyboardEvent) => {
      held.delete(event.code);
      sync();
    };

    let dragging = false;

    const onBlur = () => {
      held.clear();
      dragging = false;
      sync();
    };

    const addLook = (dx: number, dy: number) => {
      if (!input.lookEnabled) {
        return;
      }
      input.lookDx += dx;
      input.lookDy += dy;
    };

    const onPointerDown = (event: PointerEvent) => {
      if (!input.lookEnabled || event.button !== 0) {
        return;
      }
      if ((event.target as Element | null)?.tagName !== "CANVAS") {
        return;
      }
      // First click only locks. After lock, click is melee (GTA-style punch).
      if (document.pointerLockElement) {
        input.punchEdge = true;
        return;
      }
      dragging = true;
      const canvas = event.target as Element;
      if (canvas.requestPointerLock) {
        void canvas.requestPointerLock();
      }
    };

    const onPointerMove = (event: PointerEvent) => {
      if (document.pointerLockElement || dragging) {
        addLook(event.movementX, event.movementY);
      }
    };

    const onPointerUp = () => {
      dragging = false;
    };

    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", onUp);
    window.addEventListener("blur", onBlur);
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", onUp);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      held.clear();
      clearPlayerInput(input);
    };
  }, []);

  return inputRef;
}
