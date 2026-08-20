/** Contract cases: every action × missing / unknown / type / bounds + 1 positive. */

import {
  describeExample,
  describeMissing,
  describeOutOfBounds,
  describeWrongType,
} from "./actions.js";
import { E } from "./errors.js";
import { allActionDefs } from "./registry.js";
import type { ActionDef, DescribeKind, JsonSchema } from "./types.js";
import { DESCRIBE_KINDS } from "./types.js";

export type MatrixExpect = "accept" | string;

export interface ContractCase {
  id: string;
  action_id: string;
  kind: string;
  lane: "positive" | "missing" | "unknown" | "type" | "bounds";
  params: Record<string, unknown>;
  expect: MatrixExpect;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function clone(value: Record<string, unknown>): Record<string, unknown> {
  return structuredClone(value);
}

function firstRequired(schema: JsonSchema): string | undefined {
  return schema.required?.[0];
}

function walkProps(
  schema: JsonSchema,
  params: Record<string, unknown>,
  visit: (schema: JsonSchema, value: unknown, key: string, parent: Record<string, unknown>) => boolean,
): boolean {
  const props = schema.properties ?? {};
  for (const key of Object.keys(props)) {
    const child = props[key];
    if (!child) {
      continue;
    }
    if (visit(child, params[key], key, params)) {
      return true;
    }
    if (child.type === "object" && isRecord(params[key])) {
      if (walkProps(child, params[key], visit)) {
        return true;
      }
    }
    if (child.type === "array" && child.items && Array.isArray(params[key]) && params[key][0] !== undefined) {
      const first = params[key][0];
      if (isRecord(first) && child.items.type === "object") {
        if (walkProps(child.items, first, visit)) {
          return true;
        }
      } else if (child.items && visit(child.items, first, "0", params)) {
        return true;
      }
    }
  }
  return false;
}

function wrongTypeValue(schema: JsonSchema): unknown {
  if (schema.hhCodec === "variant") {
    return 0;
  }
  switch (schema.type) {
    case "string":
      return 0;
    case "number":
    case "integer":
      return "x";
    case "boolean":
      return "x";
    case "array":
      return 0;
    case "object":
      return "x";
    default:
      return 0;
  }
}

function boundValue(schema: JsonSchema): unknown | undefined {
  if (schema.enum !== undefined) {
    return "__hh_oob__";
  }
  if (schema.hhCodec === "variant") {
    return {
      schema: "hh-godot-variant/1",
      type: "NodePath",
      value: "",
    };
  }
  if (schema.type === "string") {
    if (schema.minLength !== undefined && schema.minLength > 0) {
      return "";
    }
    if (schema.pattern !== undefined) {
      return "??";
    }
  }
  if (schema.type === "integer" || schema.type === "number") {
    if (schema.minimum !== undefined) {
      return schema.minimum - 1;
    }
    if (schema.maximum !== undefined) {
      return schema.maximum + 1;
    }
  }
  if (schema.type === "array" && schema.minItems !== undefined && schema.minItems > 0) {
    return [];
  }
  return undefined;
}

function applyWrongType(def: ActionDef): Record<string, unknown> {
  const params = clone(def.example_params);
  const ok = walkProps(def.input_schema, params, (schema, _value, key, parent) => {
    if (schema.type === undefined && schema.hhCodec !== "variant") {
      return false;
    }
    parent[key] = wrongTypeValue(schema);
    return true;
  });
  if (!ok) {
    throw new Error(`${def.id}: no typed field for wrong-type case`);
  }
  return params;
}

function applyBounds(def: ActionDef): Record<string, unknown> {
  const params = clone(def.example_params);
  const ok = walkProps(def.input_schema, params, (schema, _value, key, parent) => {
    const next = boundValue(schema);
    if (next === undefined) {
      return false;
    }
    parent[key] = next;
    return true;
  });
  if (!ok) {
    throw new Error(`${def.id}: no bounded field for out-of-bounds case`);
  }
  return params;
}

function applyMissing(def: ActionDef): Record<string, unknown> {
  const params = clone(def.example_params);
  const key = firstRequired(def.input_schema);
  if (!key) {
    throw new Error(`${def.id}: input_schema needs a required field`);
  }
  delete params[key];
  return params;
}

function applyUnknown(def: ActionDef): Record<string, unknown> {
  const params = clone(def.example_params);
  params.__hh_unknown = true;
  return params;
}

function describeCases(): ContractCase[] {
  const cases: ContractCase[] = [];
  for (const kind of DESCRIBE_KINDS) {
    const k = kind as DescribeKind;
    cases.push({
      id: `capabilities.describe/${k}/positive`,
      action_id: "capabilities.describe",
      kind: k,
      lane: "positive",
      params: describeExample(k),
      expect: "accept",
    });
    cases.push({
      id: `capabilities.describe/${k}/missing`,
      action_id: "capabilities.describe",
      kind: k,
      lane: "missing",
      params: describeMissing(k),
      expect: E.E_MISSING_REQUIRED,
    });
    cases.push({
      id: `capabilities.describe/${k}/unknown`,
      action_id: "capabilities.describe",
      kind: k,
      lane: "unknown",
      params: { ...describeExample(k), __hh_unknown: true },
      expect: E.E_UNKNOWN_PARAM,
    });
    cases.push({
      id: `capabilities.describe/${k}/type`,
      action_id: "capabilities.describe",
      kind: k,
      lane: "type",
      params: describeWrongType(k),
      expect: E.E_INVALID_TYPE,
    });
    cases.push({
      id: `capabilities.describe/${k}/bounds`,
      action_id: "capabilities.describe",
      kind: k,
      lane: "bounds",
      params: describeOutOfBounds(k),
      expect: E.E_OUT_OF_BOUNDS,
    });
  }
  return cases;
}

export function buildContractMatrix(): ContractCase[] {
  const cases: ContractCase[] = [];
  for (const def of allActionDefs()) {
    if (def.id === "capabilities.describe") {
      cases.push(...describeCases());
      continue;
    }
    cases.push({
      id: `${def.id}/positive`,
      action_id: def.id,
      kind: "",
      lane: "positive",
      params: clone(def.example_params),
      expect: "accept",
    });
    cases.push({
      id: `${def.id}/missing`,
      action_id: def.id,
      kind: "",
      lane: "missing",
      params: applyMissing(def),
      expect: E.E_MISSING_REQUIRED,
    });
    cases.push({
      id: `${def.id}/unknown`,
      action_id: def.id,
      kind: "",
      lane: "unknown",
      params: applyUnknown(def),
      expect: E.E_UNKNOWN_PARAM,
    });
    cases.push({
      id: `${def.id}/type`,
      action_id: def.id,
      kind: "",
      lane: "type",
      params: applyWrongType(def),
      expect: E.E_INVALID_TYPE,
    });
    cases.push({
      id: `${def.id}/bounds`,
      action_id: def.id,
      kind: "",
      lane: "bounds",
      params: applyBounds(def),
      expect: E.E_OUT_OF_BOUNDS,
    });
  }
  return cases;
}

export function matrixStats(cases: ContractCase[]): {
  actions: number;
  positives: number;
  missing: number;
  unknown: number;
  type: number;
  bounds: number;
} {
  return {
    actions: new Set(cases.map((c) => c.action_id)).size,
    positives: cases.filter((c) => c.lane === "positive").length,
    missing: cases.filter((c) => c.lane === "missing").length,
    unknown: cases.filter((c) => c.lane === "unknown").length,
    type: cases.filter((c) => c.lane === "type").length,
    bounds: cases.filter((c) => c.lane === "bounds").length,
  };
}
