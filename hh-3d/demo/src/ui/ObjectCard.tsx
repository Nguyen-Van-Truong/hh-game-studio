import { useEffect, useRef } from "react";
import type { SelectedObject } from "../lib/types";

type ObjectCardProps = {
  object: SelectedObject;
  onClose: () => void;
};

export function ObjectCard({ object, onClose }: ObjectCardProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const active = document.activeElement;
    returnFocusRef.current =
      active instanceof HTMLElement ? active : null;
    closeRef.current?.focus();

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      returnFocusRef.current?.focus();
    };
  }, [object.id, onClose]);

  return (
    <aside
      className="object-card"
      role="dialog"
      aria-labelledby="object-card-title"
      aria-describedby="object-card-copy"
    >
      <div className="object-card-head">
        <h2 id="object-card-title">{object.title}</h2>
        <button
          ref={closeRef}
          type="button"
          className="ui-button"
          onClick={onClose}
        >
          Đóng
        </button>
      </div>
      <p id="object-card-copy">{object.description}</p>
    </aside>
  );
}
