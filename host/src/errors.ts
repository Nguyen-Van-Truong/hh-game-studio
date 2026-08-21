/** Typed host errors. E_EXTERNAL lives here so the bridge registry is not churned. */

export const E = {
  E_EXTERNAL: "E_EXTERNAL",
  E_POLICY: "E_POLICY",
  E_CANCELLED: "E_CANCELLED",
  E_TIMEOUT: "E_TIMEOUT",
  E_BUSY: "E_BUSY",
  E_PATH: "E_PATH",
  E_INVALID_COMMAND_ID: "E_INVALID_COMMAND_ID",
  E_UNVERIFIED: "E_UNVERIFIED",
} as const;

export type ErrorCode = (typeof E)[keyof typeof E];

export type TypedError = { code: string; message: string; path: string };

export function typedError(code: string, message: string, path = ""): TypedError {
  return { code, message, path };
}

export class HostError extends Error {
  readonly code: string;
  readonly path: string;

  constructor(code: string, message: string, path: string) {
    super(message);
    this.name = "HostError";
    this.code = code;
    this.path = path;
  }

  static from(err: TypedError): HostError {
    return new HostError(err.code, err.message, err.path);
  }

  typed(): TypedError {
    return typedError(this.code, this.message, this.path);
  }
}

export function isTypedError(value: unknown): value is TypedError {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const rec = value as { code?: unknown; message?: unknown; path?: unknown };
  return (
    typeof rec.code === "string" &&
    typeof rec.message === "string" &&
    typeof rec.path === "string"
  );
}
