import { E, typedError, type ErrorCode } from "../registry/errors.js";
import { PROTOCOL } from "../registry/types.js";
import { tokensEqual } from "../session/token.js";

export interface HelloRequest {
  type: "hello";
  protocol: string;
  project_id: string;
  token: string;
}

export interface HelloOk {
  ok: true;
  type: "hello_ok";
  protocol: typeof PROTOCOL;
  project_id: string;
  session_id: string;
}

export interface HelloErr {
  ok: false;
  type: "hello_err";
  error: { code: string; message: string; path: string };
}

export function parseHello(raw: unknown): HelloRequest | HelloErr {
  if (!raw || typeof raw !== "object") {
    return fail(E.E_INVALID_ENVELOPE, "hello must be an object", "");
  }
  const rec = raw as Record<string, unknown>;
  if (rec.type !== "hello") {
    return fail(E.E_INVALID_ENVELOPE, "first frame must be hello", "type");
  }
  if (typeof rec.protocol !== "string") {
    return fail(E.E_PROTOCOL_VERSION, "protocol required", "protocol");
  }
  if (typeof rec.project_id !== "string") {
    return fail(E.E_PROJECT_MISMATCH, "project_id required", "project_id");
  }
  if (typeof rec.token !== "string") {
    return fail(E.E_AUTH, "session rejected", "token");
  }
  return {
    type: "hello",
    protocol: rec.protocol,
    project_id: rec.project_id,
    token: rec.token,
  };
}

export function evaluateHello(
  hello: HelloRequest,
  expected: { protocol: string; projectId: string; token: string; sessionId: string },
): HelloOk | HelloErr {
  if (hello.protocol !== expected.protocol) {
    return fail(E.E_PROTOCOL_VERSION, "protocol mismatch", "protocol");
  }
  if (hello.project_id !== expected.projectId) {
    return fail(E.E_PROJECT_MISMATCH, "project mismatch", "project_id");
  }
  if (!tokensEqual(hello.token, expected.token)) {
    return fail(E.E_AUTH, "session rejected", "token");
  }
  return {
    ok: true,
    type: "hello_ok",
    protocol: PROTOCOL,
    project_id: expected.projectId,
    session_id: expected.sessionId,
  };
}

function fail(code: ErrorCode, message: string, path: string): HelloErr {
  return { ok: false, type: "hello_err", error: typedError(code, message, path) };
}
