/** Registry lookup + param validation. Stubs are not dispatched; no editor I/O. */

import { describeExample } from "./actions.js";
import { E, typedError } from "./errors.js";
import { parseEnvelope } from "./envelope.js";
import { actionIdFromMethod, getAction } from "./registry.js";
import { validateSchema } from "./schema.js";
import { DESCRIBE_KINDS, type ValidationResult } from "./types.js";

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function validateDescribeKindParams(
  params: Record<string, unknown>,
): ValidationResult | null {
  const kind = params.kind;
  if (typeof kind !== "string") {
    return null;
  }
  if (!(DESCRIBE_KINDS as readonly string[]).includes(kind)) {
    return null;
  }
  if (kind === "class" && typeof params.class_name !== "string") {
    return {
      accepted: false,
      error: typedError(E.E_MISSING_REQUIRED, "missing required class_name", "class_name"),
    };
  }
  if (kind === "property") {
    if (typeof params.class_name !== "string") {
      return {
        accepted: false,
        error: typedError(E.E_MISSING_REQUIRED, "missing required class_name", "class_name"),
      };
    }
    if (typeof params.property_name !== "string") {
      return {
        accepted: false,
        error: typedError(
          E.E_MISSING_REQUIRED,
          "missing required property_name",
          "property_name",
        ),
      };
    }
  }
  if (kind === "method") {
    if (typeof params.class_name !== "string") {
      return {
        accepted: false,
        error: typedError(E.E_MISSING_REQUIRED, "missing required class_name", "class_name"),
      };
    }
    if (typeof params.method_name !== "string") {
      return {
        accepted: false,
        error: typedError(E.E_MISSING_REQUIRED, "missing required method_name", "method_name"),
      };
    }
  }
  if (kind === "action" && typeof params.action_id !== "string") {
    return {
      accepted: false,
      error: typedError(E.E_MISSING_REQUIRED, "missing required action_id", "action_id"),
    };
  }
  return null;
}

export function acceptCommand(raw: unknown): ValidationResult {
  const parsed = parseEnvelope(raw);
  if (!parsed.ok) {
    return { accepted: false, error: parsed.error };
  }
  const env = parsed.envelope;
  const id = actionIdFromMethod(env.method, env.action);
  if (!id) {
    return {
      accepted: false,
      error: typedError(E.E_UNKNOWN_ACTION, "cannot resolve method+action", "method"),
    };
  }
  const def = getAction(id);
  if (!def) {
    return {
      accepted: false,
      error: typedError(E.E_UNKNOWN_ACTION, `unknown action ${id}`, "action"),
    };
  }
  if (env.action_version !== undefined && env.action_version !== def.action_version) {
    return {
      accepted: false,
      error: typedError(E.E_ACTION_VERSION, "stale action version", "action_version"),
    };
  }
  const paramIssue = validateSchema(def.input_schema, env.params, "");
  if (paramIssue) {
    return { accepted: false, error: paramIssue };
  }
  if (def.id === "capabilities.describe" && isRecord(env.params)) {
    const extra = validateDescribeKindParams(env.params);
    if (extra) {
      return extra;
    }
  }
  return {
    accepted: true,
    command_id: env.command_id,
    action_id: def.id,
    postcondition: {
      verified: false,
      checks: [def.postcondition],
    },
  };
}

export function exampleEnvelope(
  actionId: string,
  params: Record<string, unknown>,
  extras: Record<string, unknown> = {},
): Record<string, unknown> {
  const def = getAction(actionId);
  if (!def) {
    throw new Error(`unknown action ${actionId}`);
  }
  return {
    protocol: "hh-godot-agent/1",
    command_id: "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    method: def.method,
    action: def.verb,
    params,
    ...extras,
  };
}

export function describePositiveEnvelope(kind: (typeof DESCRIBE_KINDS)[number]): Record<string, unknown> {
  return exampleEnvelope("capabilities.describe", describeExample(kind));
}
