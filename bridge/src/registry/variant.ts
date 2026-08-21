import { E, typedError } from "./errors.js";
import { VARIANT_SCHEMA_VERSION } from "./types.js";

export const VARIANT_TYPES = [
  "bool",
  "int",
  "float",
  "string",
  "Vector2",
  "Color",
  "NodePath",
  "RID",
  "Resource",
] as const;

export type VariantType = (typeof VARIANT_TYPES)[number];

const TYPE_SET = new Set<string>(VARIANT_TYPES);
const UID_RE = /^uid:\/\/[A-Za-z0-9]+$/;
const NODE_PATH_RE = /^[A-Za-z_./%:@][A-Za-z0-9_./%:@-]*$/;
const VEC_ABS_MAX = 1_000_000;

export interface EncodedVariant {
  schema: typeof VARIANT_SCHEMA_VERSION;
  type: VariantType;
  value: unknown;
}

export type VariantDecode =
  | { ok: true; value: EncodedVariant }
  | { ok: false; error: { code: string; message: string; path: string } };

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function num(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function decodeVariant(raw: unknown, path = "value"): VariantDecode {
  if (!isRecord(raw)) {
    return {
      ok: false,
      error: typedError(E.E_INVALID_TYPE, "variant must be an object", path),
    };
  }
  const extra = Object.keys(raw).filter((k) => k !== "schema" && k !== "type" && k !== "value");
  if (extra.length > 0) {
    return {
      ok: false,
      error: typedError(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`),
    };
  }
  if (raw.schema !== VARIANT_SCHEMA_VERSION) {
    return {
      ok: false,
      error: typedError(
        E.E_INVALID_VARIANT,
        `variant schema must be ${VARIANT_SCHEMA_VERSION}`,
        `${path}/schema`,
      ),
    };
  }
  if (typeof raw.type !== "string") {
    return {
      ok: false,
      error: typedError(E.E_INVALID_TYPE, "variant type must be a string", `${path}/type`),
    };
  }
  if (!TYPE_SET.has(raw.type)) {
    return {
      ok: false,
      error: typedError(
        E.E_UNKNOWN_VARIANT_TYPE,
        `unknown Variant type ${raw.type}`,
        `${path}/type`,
      ),
    };
  }
  const kind = raw.type as VariantType;
  const value = raw.value;
  const valuePath = `${path}/value`;
  const shape = checkValue(kind, value, valuePath);
  if (shape) {
    return { ok: false, error: shape };
  }
  return {
    ok: true,
    value: {
      schema: VARIANT_SCHEMA_VERSION,
      type: kind,
      value,
    },
  };
}

function checkValue(
  kind: VariantType,
  value: unknown,
  path: string,
): { code: string; message: string; path: string } | null {
  switch (kind) {
    case "bool":
      return typeof value === "boolean"
        ? null
        : typedError(E.E_INVALID_TYPE, "bool value must be boolean", path);
    case "int":
      return typeof value === "number" && Number.isInteger(value)
        ? null
        : typedError(E.E_INVALID_TYPE, "int value must be an integer", path);
    case "float":
      return num(value)
        ? null
        : typedError(E.E_INVALID_TYPE, "float value must be a finite number", path);
    case "string":
      return typeof value === "string"
        ? null
        : typedError(E.E_INVALID_TYPE, "string value must be a string", path);
    case "Vector2": {
      if (!isRecord(value)) {
        return typedError(E.E_INVALID_TYPE, "Vector2 value must be an object", path);
      }
      const extra = Object.keys(value).filter((k) => k !== "x" && k !== "y");
      if (extra[0]) {
        return typedError(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      if (!num(value.x) || !num(value.y)) {
        return typedError(E.E_INVALID_TYPE, "Vector2 needs finite x and y", path);
      }
      if (Math.abs(value.x) > VEC_ABS_MAX || Math.abs(value.y) > VEC_ABS_MAX) {
        return typedError(E.E_OUT_OF_BOUNDS, "Vector2 component out of range", path);
      }
      return null;
    }
    case "Color": {
      if (!isRecord(value)) {
        return typedError(E.E_INVALID_TYPE, "Color value must be an object", path);
      }
      const keys = ["r", "g", "b", "a"] as const;
      const extra = Object.keys(value).filter((k) => !keys.includes(k as (typeof keys)[number]));
      if (extra[0]) {
        return typedError(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      for (const key of keys) {
        const channel = value[key];
        if (!num(channel)) {
          return typedError(E.E_INVALID_TYPE, `Color.${key} must be a finite number`, `${path}/${key}`);
        }
        if (channel < 0 || channel > 1) {
          return typedError(E.E_OUT_OF_BOUNDS, `Color.${key} must be 0..1`, `${path}/${key}`);
        }
      }
      return null;
    }
    case "NodePath":
      if (typeof value !== "string" || value.length < 1 || value.length > 256) {
        return typedError(E.E_OUT_OF_BOUNDS, "NodePath string length 1..256", path);
      }
      if (!NODE_PATH_RE.test(value)) {
        return typedError(E.E_OUT_OF_BOUNDS, "NodePath has illegal characters", path);
      }
      return null;
    case "RID":
      if (typeof value !== "string" || value.length < 1 || value.length > 128) {
        return typedError(E.E_OUT_OF_BOUNDS, "RID string length 1..128", path);
      }
      return null;
    case "Resource": {
      if (!isRecord(value)) {
        return typedError(E.E_INVALID_TYPE, "Resource value must be an object", path);
      }
      const extra = Object.keys(value).filter((k) => k !== "uid");
      if (extra[0]) {
        return typedError(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      if (typeof value.uid !== "string") {
        return typedError(E.E_INVALID_TYPE, "Resource.uid must be a string", `${path}/uid`);
      }
      if (value.uid.length < 7 || value.uid.length > 128 || !UID_RE.test(value.uid)) {
        return typedError(E.E_OUT_OF_BOUNDS, "Resource.uid must look like uid://…", `${path}/uid`);
      }
      return null;
    }
    default:
      return typedError(E.E_UNKNOWN_VARIANT_TYPE, "unknown Variant type", path);
  }
}

export function variantSchemaDoc(): Record<string, unknown> {
  return {
    schema: VARIANT_SCHEMA_VERSION,
    types: [...VARIANT_TYPES],
    unknown_type: "reject",
    notes: "RID is a string; Resource is { uid }. Godot objects are not inlined.",
  };
}
