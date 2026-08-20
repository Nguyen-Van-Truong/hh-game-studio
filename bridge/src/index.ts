/** Sidecar entry. R2-WP1 is the action registry — not a live MCP server. */

export const BRIDGE_PACKAGE = "hh-godot-bridge" as const;
export const BRIDGE_STATUS = "registry" as const;

export function bridgeVersion(): string {
  return "0.0.0";
}

export { REQUIRED_ACTION_COUNT, REQUIRED_VERBS, requiredActionIds } from "./registry/catalog.js";
export { acceptCommand, exampleEnvelope } from "./registry/dispatch.js";
export { parseEnvelope, validateResult } from "./registry/envelope.js";
export { writeGeneratedArtifacts } from "./registry/generate_artifacts.js";
export { buildContractMatrix } from "./registry/matrix.js";
export { runContract } from "./registry/run_contract.js";
export {
  actionCount,
  allActionDefs,
  getAction,
  getRegistry,
  missingRequiredVerbs,
} from "./registry/registry.js";
export {
  ACTION_VERSION,
  DESCRIBE_KINDS,
  ENVELOPE_ALLOWED_FIELDS,
  FORBIDDEN_CLIENT_FIELDS,
  PROTOCOL,
  REGISTRY_VERSION,
  RESULT_SCHEMA,
  VARIANT_SCHEMA_VERSION,
} from "./registry/types.js";
export { decodeVariant } from "./registry/variant.js";
