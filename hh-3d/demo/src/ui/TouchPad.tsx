import type { PointerEvent, RefObject } from "react";
import type { PlayerInput } from "../lib/input";

type TouchPadProps = {
  inputRef: RefObject<PlayerInput>;
};

function hold(
  inputRef: RefObject<PlayerInput>,
  apply: (input: PlayerInput) => void,
  clear: (input: PlayerInput) => void,
) {
  return {
    onPointerDown: (event: PointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      apply(inputRef.current);
    },
    onPointerUp: (event: PointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      clear(inputRef.current);
    },
    onPointerCancel: () => {
      clear(inputRef.current);
    },
  };
}

export function TouchPad({ inputRef }: TouchPadProps) {
  return (
    <div className="touch-pad" aria-label="Điều khiển chạm">
      <button
        type="button"
        className="touch-key"
        aria-label="Tiến"
        {...hold(
          inputRef,
          (input) => {
            input.z = 1;
          },
          (input) => {
            if (input.z > 0) {
              input.z = 0;
            }
          },
        )}
      >
        ↑
      </button>
      <div className="touch-row">
        <button
          type="button"
          className="touch-key"
          aria-label="Trái"
          {...hold(
            inputRef,
            (input) => {
              input.x = -1;
            },
            (input) => {
              if (input.x < 0) {
                input.x = 0;
              }
            },
          )}
        >
          ←
        </button>
        <button
          type="button"
          className="touch-key"
          aria-label="Lùi"
          {...hold(
            inputRef,
            (input) => {
              input.z = -1;
            },
            (input) => {
              if (input.z < 0) {
                input.z = 0;
              }
            },
          )}
        >
          ↓
        </button>
        <button
          type="button"
          className="touch-key"
          aria-label="Phải"
          {...hold(
            inputRef,
            (input) => {
              input.x = 1;
            },
            (input) => {
              if (input.x > 0) {
                input.x = 0;
              }
            },
          )}
        >
          →
        </button>
      </div>
      <div className="touch-row">
        <button
          type="button"
          className="touch-key touch-wide"
          aria-label="Chạy"
          {...hold(
            inputRef,
            (input) => {
              input.run = true;
            },
            (input) => {
              input.run = false;
            },
          )}
        >
          Chạy
        </button>
        <button
          type="button"
          className="touch-key touch-wide"
          aria-label="Nhảy"
          onPointerDown={(event) => {
            event.preventDefault();
            inputRef.current.jumpEdge = true;
          }}
        >
          Nhảy
        </button>
        <button
          type="button"
          className="touch-key touch-wide"
          aria-label="Lên hoặc xuống thuyền"
          onPointerDown={(event) => {
            event.preventDefault();
            inputRef.current.interactEdge = true;
          }}
        >
          E
        </button>
        <button
          type="button"
          className="touch-key touch-wide"
          aria-label="Đấm"
          onPointerDown={(event) => {
            event.preventDefault();
            inputRef.current.punchEdge = true;
          }}
        >
          Đấm
        </button>
      </div>
    </div>
  );
}
