import type { PointerEvent } from "react";
import type { PadState } from "./useAvatar";

type WalkPadProps = {
  onPad: (patch: Partial<PadState>) => void;
  onRelease: () => void;
  canInteract: boolean;
  onInteract: () => void;
  onJump?: () => void;
};

function hold(
  onPad: WalkPadProps["onPad"],
  onRelease: WalkPadProps["onRelease"],
  patch: Partial<PadState>,
) {
  return {
    onPointerDown: (event: PointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      onPad(patch);
    },
    onPointerUp: () => onRelease(),
    onPointerCancel: () => onRelease(),
  };
}

export function WalkPad({ onPad, onRelease, canInteract, onInteract, onJump }: WalkPadProps) {
  return (
    <div className="walk-pad" data-testid="walk-pad">
      <button
        type="button"
        className="walk-jump"
        data-testid="walk-jump"
        aria-label="Jump"
        onPointerDown={(event) => {
          event.preventDefault();
          onJump?.();
        }}
      >
        ⌃
      </button>
      <button
        type="button"
        className="walk-interact"
        data-testid="walk-interact"
        aria-label={canInteract ? "Open nearby stall" : "Too far to open a stall"}
        disabled={!canInteract}
        onClick={onInteract}
      >
        E
      </button>
      <button
        type="button"
        className="walk-n"
        aria-label="Walk forward"
        {...hold(onPad, onRelease, { north: true })}
      >
        ▲
      </button>
      <button
        type="button"
        className="walk-w"
        aria-label="Move left"
        {...hold(onPad, onRelease, { west: true })}
      >
        ◀
      </button>
      <button
        type="button"
        className="walk-e"
        aria-label="Move right"
        {...hold(onPad, onRelease, { east: true })}
      >
        ▶
      </button>
      <button
        type="button"
        className="walk-s"
        aria-label="Walk back"
        {...hold(onPad, onRelease, { south: true })}
      >
        ▼
      </button>
      <button
        type="button"
        className="walk-sprint"
        data-testid="walk-sprint"
        aria-label="Sprint"
        onPointerDown={(event) => {
          event.preventDefault();
          event.currentTarget.setPointerCapture(event.pointerId);
          onPad({ sprint: true });
        }}
        onPointerUp={() => onPad({ sprint: false })}
        onPointerCancel={() => onPad({ sprint: false })}
      >
        ≫
      </button>
    </div>
  );
}
