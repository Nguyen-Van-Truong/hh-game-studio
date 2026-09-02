import { useEffect, useRef, type KeyboardEvent } from "react";
import { CHAT_MAX_LENGTH } from "../lib/chat";

type ChatComposerProps = {
  open: boolean;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
};

export function ChatComposer({
  open,
  value,
  onChange,
  onSubmit,
  onCancel,
}: ChatComposerProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      onSubmit();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onCancel();
    }
  };

  return (
    <div className="chat-composer" role="group" aria-label="Chat trên đầu nhân vật">
      <span className="chat-composer-label">Nói</span>
      <input
        ref={inputRef}
        className="chat-composer-input"
        type="text"
        value={value}
        maxLength={CHAT_MAX_LENGTH}
        autoComplete="off"
        spellCheck
        aria-label="Nội dung chat"
        placeholder="Gõ để hiện từng chữ trên đầu…"
        onChange={(event) => {
          onChange(event.currentTarget.value);
        }}
        onKeyDown={onKeyDown}
      />
      <span className="chat-composer-hint">Enter gửi · Esc hủy</span>
    </div>
  );
}
