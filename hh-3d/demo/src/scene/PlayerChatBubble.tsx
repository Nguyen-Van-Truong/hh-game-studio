import { Html } from "@react-three/drei";
import type { PlayerChatBubble as PlayerChatBubbleState } from "../lib/chat";

type PlayerChatBubbleProps = {
  chat: PlayerChatBubbleState;
};

export function PlayerChatBubble({ chat }: PlayerChatBubbleProps) {
  const text = chat.text || "…";

  return (
    <Html
      position={[0, 1.62, 0]}
      center
      distanceFactor={7.5}
      zIndexRange={[40, 0]}
      style={{ pointerEvents: "none" }}
    >
      <div
        className="player-chat-bubble"
        data-chat-phase={chat.phase}
        aria-label={chat.phase === "typing" ? `Đang nhập: ${text}` : text}
      >
        {text}
      </div>
    </Html>
  );
}
