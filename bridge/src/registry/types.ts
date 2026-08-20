/** Shared types for the action registry (R2-WP1). No live editor dispatch. */

export const PROTOCOL = "hh-godot-agent/1" as const;
export const REGISTRY_VERSION = "hh-godot-actions/1" as const;
export const VARIANT_SCHEMA_VERSION = "hh-godot-variant/1" as const;
export const ACTION_VERSION = "1" as const;

export const SIDE_EFFECTS = [
  "read",
  "view",
  "mutate",
  "destructive",
  "external",
] as const;
export type SideEffect = (typeof SIDE_EFFECTS)[number];

export const UNDO_STRATEGIES = [
  "none",
  "n/a",
  "editor_undo_redo",
  "atomic_file",
  "project_settings_save",
  "git_checkpoint",
  "job_supervisor",
] as const;
export type UndoStrategy = (typeof UNDO_STRATEGIES)[number];

export const DESCRIBE_KINDS = [
  "version",
  "class",
  "property",
  "method",
  "action",
] as const;
export type DescribeKind = (typeof DESCRIBE_KINDS)[number];

export const POLICIES = ["OBSERVE", "EDIT", "OWNER_AUTOPILOT"] as const;
export type Policy = (typeof POLICIES)[number];

export type JsonSchemaType =
  | "object"
  | "string"
  | "number"
  | "integer"
  | "boolean"
  | "array";

export interface JsonSchema {
  type?: JsonSchemaType;
  description?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  additionalProperties?: boolean;
  enum?: ReadonlyArray<string | number | boolean>;
  const?: string | number | boolean;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  minItems?: number;
  maxItems?: number;
  items?: JsonSchema;
  hhCodec?: "variant";
}

export interface ActionDef {
  id: string;
  group: string;
  verb: string;
  method: string;
  action_version: typeof ACTION_VERSION;
  summary: string;
  side_effect: SideEffect;
  undo: UndoStrategy;
  timeout_ms: number;
  cancellable: boolean;
  required_policy: Policy;
  checkpoint_required: boolean;
  input_schema: JsonSchema;
  output_schema: JsonSchema;
  error_codes: readonly string[];
  postcondition: string;
  example_params: Record<string, unknown>;
}

export interface CommandEnvelope {
  protocol: string;
  command_id: string;
  method: string;
  action: string;
  params: Record<string, unknown>;
  action_version?: string;
  variant_schema?: string;
  precondition?: Record<string, unknown>;
  presentation?: Record<string, unknown>;
}

export interface TypedError {
  code: string;
  message: string;
  path: string;
}

export interface PostconditionResult {
  verified: boolean;
  checks: string[];
}

export interface ValidationOk {
  accepted: true;
  command_id: string;
  action_id: string;
  postcondition: PostconditionResult;
}

export interface ValidationErr {
  accepted: false;
  error: TypedError;
}

export type ValidationResult = ValidationOk | ValidationErr;

export const RESULT_SCHEMA: JsonSchema = {
  type: "object",
  additionalProperties: false,
  required: ["ok", "command_id", "postcondition"],
  properties: {
    ok: { type: "boolean" },
    command_id: { type: "string", minLength: 26, maxLength: 26 },
    changed: { type: "boolean" },
    before: { type: "object", additionalProperties: true },
    after: { type: "object", additionalProperties: true },
    postcondition: {
      type: "object",
      additionalProperties: false,
      required: ["verified", "checks"],
      properties: {
        verified: { type: "boolean" },
        checks: { type: "array", items: { type: "string" } },
      },
    },
    undo_action: { type: "string" },
    evidence: { type: "array", items: { type: "string" } },
    warnings: { type: "array", items: { type: "string" } },
    error: {
      type: "object",
      additionalProperties: false,
      properties: {
        code: { type: "string" },
        message: { type: "string" },
        path: { type: "string" },
      },
    },
  },
};

export const FORBIDDEN_CLIENT_FIELDS = [
  "session_id",
  "actor",
  "actor_id",
  "project_id",
  "policy",
  "profile",
  "capability",
  "capability_grant",
  "grants",
] as const;

export const ENVELOPE_ALLOWED_FIELDS = [
  "protocol",
  "command_id",
  "method",
  "action",
  "params",
  "precondition",
  "presentation",
  "action_version",
] as const;
