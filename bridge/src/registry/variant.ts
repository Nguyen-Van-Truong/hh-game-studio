import { E, typedError } from "./errors.js";
import { VARIANT_SCHEMA_VERSION } from "./types.js";

export const VARIANT_TYPES = [
  "bool",
  "int",
  "float",
  "string",
  "Vector2",
  "Vector2i",
  "Vector3",
  "Rect2",
  "Transform2D",
  "Transform3D",
  "Color",
  "NodePath",
  "RID",
  "Resource",
  "Array",
  "Dictionary",
  "TypedArray",
] as const;

export type VariantType = (typeof VARIANT_TYPES)[number];

const TYPE_SET = new Set<string>(VARIANT_TYPES);
const UID_RE = /^uid:\/\/[A-Za-z0-9]+$/;
const NODE_PATH_RE = /^[A-Za-z_./%:@][A-Za-z0-9_./%:@-]*$/;
const RES_PATH_RE = /^res:\/\/[^\s]+$/;
const CLASS_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const VEC_ABS_MAX = 1_000_000;
const CONTAINER_MAX = 256;

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

function typed(
  code: string,
  message: string,
  path: string,
): { code: string; message: string; path: string } {
  return typedError(code, message, path);
}

export function decodeVariant(raw: unknown, path = "value"): VariantDecode {
  if (!isRecord(raw)) {
    return {
      ok: false,
      error: typed(E.E_INVALID_TYPE, "variant must be an object", path),
    };
  }
  const extra = Object.keys(raw).filter((k) => k !== "schema" && k !== "type" && k !== "value");
  if (extra.length > 0) {
    return {
      ok: false,
      error: typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`),
    };
  }
  if (raw.schema !== VARIANT_SCHEMA_VERSION) {
    return {
      ok: false,
      error: typed(
        E.E_INVALID_VARIANT,
        `variant schema must be ${VARIANT_SCHEMA_VERSION}`,
        `${path}/schema`,
      ),
    };
  }
  if (typeof raw.type !== "string") {
    return {
      ok: false,
      error: typed(E.E_INVALID_TYPE, "variant type must be a string", `${path}/type`),
    };
  }
  if (!TYPE_SET.has(raw.type)) {
    return {
      ok: false,
      error: typed(
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

export function encodeVariant(kind: VariantType, value: unknown, path = "value"): VariantDecode {
  const shape = checkValue(kind, value, path);
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

function vec2(value: unknown, path: string, integer: boolean): ReturnType<typeof typed> | null {
  if (!isRecord(value)) {
    return typed(E.E_INVALID_TYPE, "vector value must be an object", path);
  }
  const extra = Object.keys(value).filter((k) => k !== "x" && k !== "y");
  if (extra[0]) {
    return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
  }
  if (integer) {
    if (typeof value.x !== "number" || !Number.isInteger(value.x) || typeof value.y !== "number" || !Number.isInteger(value.y)) {
      return typed(E.E_INVALID_TYPE, "vector needs integer x and y", path);
    }
  } else if (!num(value.x) || !num(value.y)) {
    return typed(E.E_INVALID_TYPE, "vector needs finite x and y", path);
  }
  if (Math.abs(value.x) > VEC_ABS_MAX || Math.abs(value.y) > VEC_ABS_MAX) {
    return typed(E.E_OUT_OF_BOUNDS, "vector component out of range", path);
  }
  return null;
}

function vec3(value: unknown, path: string): ReturnType<typeof typed> | null {
  if (!isRecord(value)) {
    return typed(E.E_INVALID_TYPE, "Vector3 value must be an object", path);
  }
  const extra = Object.keys(value).filter((k) => k !== "x" && k !== "y" && k !== "z");
  if (extra[0]) {
    return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
  }
  if (!num(value.x) || !num(value.y) || !num(value.z)) {
    return typed(E.E_INVALID_TYPE, "Vector3 needs finite x, y, z", path);
  }
  if (Math.abs(value.x) > VEC_ABS_MAX || Math.abs(value.y) > VEC_ABS_MAX || Math.abs(value.z) > VEC_ABS_MAX) {
    return typed(E.E_OUT_OF_BOUNDS, "Vector3 component out of range", path);
  }
  return null;
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
        : typed(E.E_INVALID_TYPE, "bool value must be boolean", path);
    case "int":
      return typeof value === "number" && Number.isInteger(value)
        ? null
        : typed(E.E_INVALID_TYPE, "int value must be an integer", path);
    case "float":
      return num(value)
        ? null
        : typed(E.E_INVALID_TYPE, "float value must be a finite number", path);
    case "string":
      return typeof value === "string"
        ? null
        : typed(E.E_INVALID_TYPE, "string value must be a string", path);
    case "Vector2":
      return vec2(value, path, false);
    case "Vector2i":
      return vec2(value, path, true);
    case "Vector3":
      return vec3(value, path);
    case "Rect2": {
      if (!isRecord(value)) {
        return typed(E.E_INVALID_TYPE, "Rect2 value must be an object", path);
      }
      const extra = Object.keys(value).filter((k) => !["x", "y", "w", "h"].includes(k));
      if (extra[0]) {
        return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      if (!num(value.x) || !num(value.y) || !num(value.w) || !num(value.h)) {
        return typed(E.E_INVALID_TYPE, "Rect2 needs finite x, y, w, h", path);
      }
      if (
        Math.abs(value.x) > VEC_ABS_MAX ||
        Math.abs(value.y) > VEC_ABS_MAX ||
        Math.abs(value.w) > VEC_ABS_MAX ||
        Math.abs(value.h) > VEC_ABS_MAX
      ) {
        return typed(E.E_OUT_OF_BOUNDS, "Rect2 component out of range", path);
      }
      return null;
    }
    case "Transform2D": {
      if (!isRecord(value)) {
        return typed(E.E_INVALID_TYPE, "Transform2D value must be an object", path);
      }
      const extra = Object.keys(value).filter((k) => k !== "x" && k !== "y" && k !== "origin");
      if (extra[0]) {
        return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      return vec2(value.x, `${path}/x`, false) ?? vec2(value.y, `${path}/y`, false) ?? vec2(value.origin, `${path}/origin`, false);
    }
    case "Transform3D": {
      if (!isRecord(value)) {
        return typed(E.E_INVALID_TYPE, "Transform3D value must be an object", path);
      }
      const extra = Object.keys(value).filter((k) => k !== "basis" && k !== "origin");
      if (extra[0]) {
        return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      if (!isRecord(value.basis)) {
        return typed(E.E_INVALID_TYPE, "Transform3D.basis must be an object", `${path}/basis`);
      }
      const basisExtra = Object.keys(value.basis).filter((k) => k !== "x" && k !== "y" && k !== "z");
      if (basisExtra[0]) {
        return typed(E.E_UNKNOWN_PARAM, `unknown field ${basisExtra[0]}`, `${path}/basis/${basisExtra[0]}`);
      }
      return (
        vec3(value.basis.x, `${path}/basis/x`) ??
        vec3(value.basis.y, `${path}/basis/y`) ??
        vec3(value.basis.z, `${path}/basis/z`) ??
        vec3(value.origin, `${path}/origin`)
      );
    }
    case "Color": {
      if (!isRecord(value)) {
        return typed(E.E_INVALID_TYPE, "Color value must be an object", path);
      }
      const keys = ["r", "g", "b", "a"] as const;
      const extra = Object.keys(value).filter((k) => !keys.includes(k as (typeof keys)[number]));
      if (extra[0]) {
        return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      for (const key of keys) {
        const channel = value[key];
        if (!num(channel)) {
          return typed(E.E_INVALID_TYPE, `Color.${key} must be a finite number`, `${path}/${key}`);
        }
        if (channel < 0 || channel > 1) {
          return typed(E.E_OUT_OF_BOUNDS, `Color.${key} must be 0..1`, `${path}/${key}`);
        }
      }
      return null;
    }
    case "NodePath":
      if (value === null || value === "") {
        return null;
      }
      if (typeof value !== "string" || value.length > 256) {
        return typed(E.E_OUT_OF_BOUNDS, "NodePath string length 0..256", path);
      }
      if (!NODE_PATH_RE.test(value)) {
        return typed(E.E_OUT_OF_BOUNDS, "NodePath has illegal characters", path);
      }
      return null;
    case "RID":
      if (typeof value !== "string" || value.length < 1 || value.length > 128) {
        return typed(E.E_OUT_OF_BOUNDS, "RID string length 1..128", path);
      }
      return null;
    case "Resource": {
      if (value === null) {
        return null;
      }
      if (!isRecord(value)) {
        return typed(E.E_INVALID_TYPE, "Resource value must be an object or null", path);
      }
      const extra = Object.keys(value).filter((k) => k !== "uid" && k !== "path" && k !== "class_name");
      if (extra[0]) {
        return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      const uid = value.uid;
      const resPath = value.path;
      const className = value.class_name;
      if (uid === undefined && resPath === undefined && className === undefined) {
        return typed(E.E_INVALID_VARIANT, "Resource needs uid, path, or class_name", path);
      }
      if (uid !== undefined) {
        if (typeof uid !== "string") {
          return typed(E.E_INVALID_TYPE, "Resource.uid must be a string", `${path}/uid`);
        }
        if (uid.length < 7 || uid.length > 128 || !UID_RE.test(uid)) {
          return typed(E.E_OUT_OF_BOUNDS, "Resource.uid must look like uid://…", `${path}/uid`);
        }
      }
      if (resPath !== undefined) {
        if (typeof resPath !== "string") {
          return typed(E.E_INVALID_TYPE, "Resource.path must be a string", `${path}/path`);
        }
        if (resPath.length < 6 || resPath.length > 256 || !RES_PATH_RE.test(resPath) || resPath.includes("..")) {
          return typed(E.E_OUT_OF_BOUNDS, "Resource.path must be a jailed res:// path", `${path}/path`);
        }
      }
      if (className !== undefined) {
        if (typeof className !== "string") {
          return typed(E.E_INVALID_TYPE, "Resource.class_name must be a string", `${path}/class_name`);
        }
        if (className.length < 1 || className.length > 128 || !CLASS_RE.test(className)) {
          return typed(E.E_OUT_OF_BOUNDS, "Resource.class_name is not a class ident", `${path}/class_name`);
        }
      }
      return null;
    }
    case "Array": {
      if (!Array.isArray(value)) {
        return typed(E.E_INVALID_TYPE, "Array value must be an array", path);
      }
      if (value.length > CONTAINER_MAX) {
        return typed(E.E_OUT_OF_BOUNDS, `Array longer than ${CONTAINER_MAX}`, path);
      }
      for (let i = 0; i < value.length; i += 1) {
        const decoded = decodeVariant(value[i], `${path}/${i}`);
        if (!decoded.ok) {
          return decoded.error;
        }
      }
      return null;
    }
    case "Dictionary": {
      if (Array.isArray(value)) {
        if (value.length > CONTAINER_MAX) {
          return typed(E.E_OUT_OF_BOUNDS, `Dictionary longer than ${CONTAINER_MAX}`, path);
        }
        for (let i = 0; i < value.length; i += 1) {
          const pair = value[i];
          if (!isRecord(pair)) {
            return typed(E.E_INVALID_TYPE, "Dictionary pair must be an object", `${path}/${i}`);
          }
          const extra = Object.keys(pair).filter((k) => k !== "key" && k !== "value");
          if (extra[0]) {
            return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${i}/${extra[0]}`);
          }
          const keyDec = decodeVariant(pair.key, `${path}/${i}/key`);
          if (!keyDec.ok) {
            return keyDec.error;
          }
          const valDec = decodeVariant(pair.value, `${path}/${i}/value`);
          if (!valDec.ok) {
            return valDec.error;
          }
        }
        return null;
      }
      if (!isRecord(value)) {
        return typed(E.E_INVALID_TYPE, "Dictionary value must be an object or pair array", path);
      }
      const keys = Object.keys(value);
      if (keys.length > CONTAINER_MAX) {
        return typed(E.E_OUT_OF_BOUNDS, `Dictionary longer than ${CONTAINER_MAX}`, path);
      }
      for (const key of keys) {
        const decoded = decodeVariant(value[key], `${path}/${key}`);
        if (!decoded.ok) {
          return decoded.error;
        }
      }
      return null;
    }
    case "TypedArray": {
      if (!isRecord(value)) {
        return typed(E.E_INVALID_TYPE, "TypedArray value must be an object", path);
      }
      const extra = Object.keys(value).filter((k) => k !== "element" && k !== "items");
      if (extra[0]) {
        return typed(E.E_UNKNOWN_PARAM, `unknown field ${extra[0]}`, `${path}/${extra[0]}`);
      }
      if (typeof value.element !== "string") {
        return typed(E.E_INVALID_TYPE, "TypedArray.element must be a string", `${path}/element`);
      }
      if (!TYPE_SET.has(value.element) || value.element === "TypedArray") {
        return typed(
          E.E_UNKNOWN_VARIANT_TYPE,
          `unknown TypedArray element ${value.element}`,
          `${path}/element`,
        );
      }
      if (!Array.isArray(value.items)) {
        return typed(E.E_INVALID_TYPE, "TypedArray.items must be an array", `${path}/items`);
      }
      if (value.items.length > CONTAINER_MAX) {
        return typed(E.E_OUT_OF_BOUNDS, `TypedArray longer than ${CONTAINER_MAX}`, `${path}/items`);
      }
      const element = value.element as VariantType;
      for (let i = 0; i < value.items.length; i += 1) {
        const item = value.items[i];
        const itemPath = `${path}/items/${i}`;
        if (element === "Array" || element === "Dictionary") {
          const wrapped = decodeVariant(item, itemPath);
          if (!wrapped.ok) {
            return wrapped.error;
          }
          if (wrapped.value.type !== element) {
            return typed(E.E_INVALID_TYPE, `TypedArray item must be ${element}`, itemPath);
          }
        } else {
          const shape = checkValue(element, item, itemPath);
          if (shape) {
            return shape;
          }
        }
      }
      return null;
    }
    default:
      return typed(E.E_UNKNOWN_VARIANT_TYPE, "unknown Variant type", path);
  }
}

export function variantSchemaDoc(): Record<string, unknown> {
  return {
    schema: VARIANT_SCHEMA_VERSION,
    types: [...VARIANT_TYPES],
    unknown_type: "reject",
    notes:
      "RID is a string; Resource is null | { uid?, path?, class_name? }. " +
      "Array items are encoded variants. TypedArray is { element, items }. " +
      "Godot objects are not inlined except Resource refs and local class_name.",
  };
}
