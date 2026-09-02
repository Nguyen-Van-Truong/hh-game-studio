export const CHAT_MAX_LENGTH = 96;
export const CHAT_VISIBLE_MS = 6500;

export type PlayerChatBubble = {
  text: string;
  phase: "typing" | "spoken";
};

export function normalizeChatMessage(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, CHAT_MAX_LENGTH);
}
