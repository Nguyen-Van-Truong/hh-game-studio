/** Placeholder sidecar entry. MCP server lands in R2. */
export const BRIDGE_PACKAGE = "hh-godot-bridge" as const;
export const BRIDGE_STATUS = "scaffold" as const;

export function bridgeVersion(): string {
  return "0.0.0";
}
