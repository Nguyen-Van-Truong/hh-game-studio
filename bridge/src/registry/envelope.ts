/** §5.1 envelope + result validation. Schema-only; binds no session/actor/policy. */

import { E, typedError } from "./errors.js";
import { validateSchema } from "./schema.js";
import {
  ACTION_VERSION,
  ENVELOPE_ALLOWED_FIELDS,
  FORBIDDEN_CLIENT_FIELDS,
  PROTOCOL,
  RESULT_SCHEMA,
  type CommandEnvelope,
  type JsonSchema,
  type TypedError,
} from "./types.js";
import { isUlid } from "./ulid.js";

const ALLOWED = new Set<string>(ENVELOPE_ALLOWED_FIELDS);
const FORBIDDEN = new Set<string>(FORBIDDEN_CLIENT_FIELDS);

export const PRECONDITION_SCHEMA: JsonSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    scene: { type: "string", minLength: 6, maxLength: 256, pattern: "^res://[^\\s]+$" },
    scene_hash: { type: "string", minLength: 8, maxLength: 128 },
    target_uid: { type: "string", minLength: 1, maxLength: 128 },
    property_hash: { type: "string", minLength: 8, maxLength: 128 },
  },
};

export const PRESENTATION_SCHEMA: JsonSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    mode: { type: "string", enum: ["watch", "fast"] },
    duration_ms: { type: "integer", minimum: 0, maximum: 60_000 },
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function validateResult(value: unknown): TypedError | null {
  const issue = validateSchema(RESULT_SCHEMA, value);
  return issue;
}

export type EnvelopeOk = { ok: true; envelope: CommandEnvelope };
export type EnvelopeErr = { ok: false; error: TypedError };

export function parseEnvelope(raw: unknown): EnvelopeOk | EnvelopeErr {
  if (!isRecord(raw)) {
    return {
      ok: false,
      error: typedError(E.E_INVALID_ENVELOPE, "envelope must be an object", ""),
    };
  }

  for (const key of Object.keys(raw)) {
    if (FORBIDDEN.has(key)) {
      return {
        ok: false,
        error: typedError(
          E.E_CLIENT_ESCALATION,
          `client must not set ${key}`,
          key,
        ),
      };
    }
    if (!ALLOWED.has(key)) {
      return {
        ok: false,
        error: typedError(E.E_INVALID_ENVELOPE, `unknown envelope field ${key}`, key),
      };
    }
  }

  if (raw.protocol !== PROTOCOL) {
    return {
      ok: false,
      error: typedError(
        E.E_PROTOCOL_VERSION,
        `protocol must be ${PROTOCOL}`,
        "protocol",
      ),
    };
  }

  if (typeof raw.command_id !== "string" || !isUlid(raw.command_id)) {
    return {
      ok: false,
      error: typedError(E.E_INVALID_COMMAND_ID, "command_id must be a ULID", "command_id"),
    };
  }

  if (typeof raw.method !== "string" || !raw.method.startsWith("godot.")) {
    return {
      ok: false,
      error: typedError(E.E_UNKNOWN_ACTION, "method must be godot.<group>", "method"),
    };
  }

  if (typeof raw.action !== "string" || raw.action.length < 1) {
    return {
      ok: false,
      error: typedError(E.E_UNKNOWN_ACTION, "action verb required", "action"),
    };
  }

  if (!isRecord(raw.params)) {
    return {
      ok: false,
      error: typedError(E.E_INVALID_TYPE, "params must be an object", "params"),
    };
  }

  if (raw.action_version !== undefined) {
    if (raw.action_version !== ACTION_VERSION) {
      return {
        ok: false,
        error: typedError(
          E.E_ACTION_VERSION,
          `action_version must be ${ACTION_VERSION}`,
          "action_version",
        ),
      };
    }
  }

  if (raw.precondition !== undefined) {
    const issue = validateSchema(PRECONDITION_SCHEMA, raw.precondition, "precondition");
    if (issue) {
      return { ok: false, error: issue };
    }
  }

  if (raw.presentation !== undefined) {
    const issue = validateSchema(PRESENTATION_SCHEMA, raw.presentation, "presentation");
    if (issue) {
      return { ok: false, error: issue };
    }
  }

  const envelope: CommandEnvelope = {
    protocol: PROTOCOL,
    command_id: raw.command_id,
    method: raw.method,
    action: raw.action,
    params: raw.params,
  };
  if (typeof raw.action_version === "string") {
    envelope.action_version = raw.action_version;
  }
  if (isRecord(raw.precondition)) {
    envelope.precondition = raw.precondition;
  }
  if (isRecord(raw.presentation)) {
    envelope.presentation = raw.presentation;
  }
  return { ok: true, envelope };
}
