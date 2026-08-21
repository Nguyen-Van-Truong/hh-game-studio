/** Shared JSON Schema fragments. Command params always use additionalProperties: false. */

import type { JsonSchema } from "./types.js";
import { DESCRIBE_KINDS, VARIANT_SCHEMA_VERSION } from "./types.js";

export function obj(
  required: string[],
  properties: Record<string, JsonSchema>,
): JsonSchema {
  return {
    type: "object",
    additionalProperties: false,
    required,
    properties,
  };
}

export const RES_PATH: JsonSchema = {
  type: "string",
  minLength: 6,
  maxLength: 256,
  pattern: "^res://[^\\s]+$",
};

export const NODE_PATH: JsonSchema = {
  type: "string",
  minLength: 1,
  maxLength: 256,
  pattern: "^[A-Za-z_./%:@][A-Za-z0-9_./%:@-]*$",
};

export const IDENT: JsonSchema = {
  type: "string",
  minLength: 1,
  maxLength: 128,
  pattern: "^[A-Za-z_][A-Za-z0-9_]*$",
};

export const PROP_PATH: JsonSchema = {
  type: "string",
  minLength: 1,
  maxLength: 256,
  pattern: "^[A-Za-z_][A-Za-z0-9_]*(?:[/:][A-Za-z_][A-Za-z0-9_]*)*$",
};

export const ACTION_ID: JsonSchema = {
  type: "string",
  minLength: 3,
  maxLength: 128,
  pattern: "^[a-z]+\\.[a-z_]+$",
};

export const DETAIL: JsonSchema = {
  type: "string",
  enum: ["short", "full"],
};

export const INDEX: JsonSchema = {
  type: "integer",
  minimum: 0,
  maximum: 4096,
};

export const LIMIT: JsonSchema = {
  type: "integer",
  minimum: 1,
  maximum: 100,
};

export const CURSOR: JsonSchema = {
  type: "string",
  minLength: 1,
  maxLength: 64,
  pattern: "^[0-9A-Za-z_.:-]+$",
};

export const PREFIX: JsonSchema = {
  type: "string",
  minLength: 1,
  maxLength: 128,
  pattern: "^[A-Za-z_][A-Za-z0-9_]*$",
};

export const VARIANT: JsonSchema = {
  hhCodec: "variant",
};

export const BOOL: JsonSchema = { type: "boolean" };

export const TEXT: JsonSchema = {
  type: "string",
  minLength: 1,
  maxLength: 4000,
};

export const JOB_ID: JsonSchema = {
  type: "string",
  minLength: 1,
  maxLength: 64,
  pattern: "^[A-Za-z0-9_-]+$",
};

export const HASH: JsonSchema = {
  type: "string",
  minLength: 8,
  maxLength: 128,
  pattern: "^[A-Fa-f0-9]+$",
};

export function exampleVariantInt(value = 1): Record<string, unknown> {
  return {
    schema: VARIANT_SCHEMA_VERSION,
    type: "int",
    value,
  };
}

export function exampleVariantBool(value = true): Record<string, unknown> {
  return {
    schema: VARIANT_SCHEMA_VERSION,
    type: "bool",
    value,
  };
}

export function exampleVariantVec2(x = 0, y = 0): Record<string, unknown> {
  return {
    schema: VARIANT_SCHEMA_VERSION,
    type: "Vector2",
    value: { x, y },
  };
}

export const DESCRIBE_KIND_SCHEMA: JsonSchema = {
  type: "string",
  enum: [...DESCRIBE_KINDS],
};

export const DESCRIBE_INPUT: JsonSchema = obj(["kind"], {
  kind: DESCRIBE_KIND_SCHEMA,
  class_name: IDENT,
  property_name: IDENT,
  method_name: IDENT,
  action_id: ACTION_ID,
  limit: LIMIT,
  cursor: CURSOR,
  prefix: PREFIX,
});
