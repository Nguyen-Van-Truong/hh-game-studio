/** Sidecar entry. Transport + registry. Editor mutations are not dispatched. Read/view/noop may forward to a connected plugin. */

export const BRIDGE_PACKAGE = "hh-godot-bridge" as const;
export const BRIDGE_STATUS = "session-transport" as const;

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
export { startSidecar } from "./session/session.js";
export { generateSessionToken } from "./session/token.js";
export { listenLoopback, listenExplicit } from "./transport/loopback.js";
export { startMcpStdio } from "./transport/mcp_stdio.js";
export { runDoctor, runSessionDoctor, tokenAbsentFromBlob } from "./doctor/doctor.js";
export { listResources } from "./resources/mcp_resources.js";
export { openLedger } from "./ledger/store.js";
export { executeCommand } from "./ledger/execute.js";
export { ledgerFilePath } from "./ledger/paths.js";
export { runMutationGate } from "./policy/engine.js";
export { jailProjectPath, jailExportOutDir } from "./policy/jail.js";
export { PauseGate } from "./policy/pause.js";
export { DEFAULT_POLICY, normalizePolicy } from "./policy/profiles.js";
export { ApprovalBinder, approvalToken } from "./policy/approve.js";
