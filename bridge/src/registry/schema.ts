import { E, typedError } from "./errors.js";
import type { JsonSchema } from "./types.js";
import { decodeVariant } from "./variant.js";

export interface SchemaIssue {
  code: string;
  message: string;
  path: string;
}

function issue(code: string, message: string, path: string): SchemaIssue {
  return typedError(code, message, path);
}

function jsonType(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  return typeof value;
}

function matchesType(schemaType: JsonSchema["type"], value: unknown): boolean {
  if (schemaType === undefined) {
    return true;
  }
  if (schemaType === "object") {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }
  if (schemaType === "array") {
    return Array.isArray(value);
  }
  if (schemaType === "integer") {
    return typeof value === "number" && Number.isInteger(value);
  }
  if (schemaType === "number") {
    return typeof value === "number" && Number.isFinite(value);
  }
  return typeof value === schemaType;
}

export function validateSchema(
  schema: JsonSchema,
  value: unknown,
  path = "",
): SchemaIssue | null {
  if (schema.hhCodec === "variant") {
    const decoded = decodeVariant(value, path);
    if (!decoded.ok) {
      return decoded.error;
    }
    return null;
  }

  if (!matchesType(schema.type, value)) {
    return issue(
      E.E_INVALID_TYPE,
      `expected ${schema.type ?? "value"}, got ${jsonType(value)}`,
      path,
    );
  }

  if (schema.const !== undefined && value !== schema.const) {
    return issue(E.E_OUT_OF_BOUNDS, `expected const ${String(schema.const)}`, path);
  }

  if (schema.enum !== undefined && !schema.enum.some((item) => item === value)) {
    return issue(E.E_OUT_OF_BOUNDS, "value is not in enum", path);
  }

  if (typeof value === "number") {
    if (schema.minimum !== undefined && value < schema.minimum) {
      return issue(E.E_OUT_OF_BOUNDS, `below minimum ${schema.minimum}`, path);
    }
    if (schema.maximum !== undefined && value > schema.maximum) {
      return issue(E.E_OUT_OF_BOUNDS, `above maximum ${schema.maximum}`, path);
    }
    if (schema.exclusiveMinimum !== undefined && value <= schema.exclusiveMinimum) {
      return issue(
        E.E_OUT_OF_BOUNDS,
        `not above exclusiveMinimum ${schema.exclusiveMinimum}`,
        path,
      );
    }
    if (schema.exclusiveMaximum !== undefined && value >= schema.exclusiveMaximum) {
      return issue(
        E.E_OUT_OF_BOUNDS,
        `not below exclusiveMaximum ${schema.exclusiveMaximum}`,
        path,
      );
    }
  }

  if (typeof value === "string") {
    if (schema.minLength !== undefined && value.length < schema.minLength) {
      return issue(E.E_OUT_OF_BOUNDS, `shorter than minLength ${schema.minLength}`, path);
    }
    if (schema.maxLength !== undefined && value.length > schema.maxLength) {
      return issue(E.E_OUT_OF_BOUNDS, `longer than maxLength ${schema.maxLength}`, path);
    }
    if (schema.pattern !== undefined) {
      const re = new RegExp(schema.pattern);
      if (!re.test(value)) {
        return issue(E.E_OUT_OF_BOUNDS, "does not match pattern", path);
      }
    }
  }

  if (Array.isArray(value)) {
    if (schema.minItems !== undefined && value.length < schema.minItems) {
      return issue(E.E_OUT_OF_BOUNDS, `fewer than minItems ${schema.minItems}`, path);
    }
    if (schema.maxItems !== undefined && value.length > schema.maxItems) {
      return issue(E.E_OUT_OF_BOUNDS, `more than maxItems ${schema.maxItems}`, path);
    }
    if (schema.items) {
      for (let i = 0; i < value.length; i += 1) {
        const child = validateSchema(schema.items, value[i], `${path}/${i}`);
        if (child) {
          return child;
        }
      }
    }
  }

  if (
    schema.type === "object" &&
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value)
  ) {
    const record = value as Record<string, unknown>;
    const props = schema.properties ?? {};
    const required = schema.required ?? [];
    for (const key of required) {
      if (!Object.prototype.hasOwnProperty.call(record, key)) {
        return issue(E.E_MISSING_REQUIRED, `missing required ${key}`, joinPath(path, key));
      }
    }
    const additional = schema.additionalProperties !== true;
    for (const key of Object.keys(record)) {
      const childSchema = props[key];
      if (childSchema === undefined) {
        if (additional) {
          return issue(E.E_UNKNOWN_PARAM, `unknown field ${key}`, joinPath(path, key));
        }
        continue;
      }
      const child = validateSchema(childSchema, record[key], joinPath(path, key));
      if (child) {
        return child;
      }
    }
  }

  return null;
}

function joinPath(base: string, key: string): string {
  return base === "" ? key : `${base}/${key}`;
}
