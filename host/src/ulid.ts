/** Crockford Base32 ULID (26 chars). Format check plus CSPRNG mint. */

import { randomBytes } from "node:crypto";

import { E, HostError } from "./errors.js";

const ULID_RE = /^[0-7][0-9A-HJKMNPQRSTVWXYZ]{25}$/;
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

export function isUlid(value: string): boolean {
  return ULID_RE.test(value.toUpperCase());
}

export function newUlid(nowMs = Date.now()): string {
  let time = BigInt(nowMs);
  const timeChars: string[] = [];
  for (let i = 0; i < 10; i++) {
    timeChars.push(CROCKFORD[Number(time % 32n)] ?? "0");
    time /= 32n;
  }
  const entropy = randomBytes(10);
  let acc = 0n;
  for (const byte of entropy) {
    acc = (acc << 8n) | BigInt(byte);
  }
  const randChars: string[] = [];
  for (let i = 0; i < 16; i++) {
    randChars.push(CROCKFORD[Number(acc % 32n)] ?? "0");
    acc /= 32n;
  }
  return `${timeChars.reverse().join("")}${randChars.reverse().join("")}`;
}

export function parseUlid(value: string, path: string): string {
  if (!isUlid(value)) {
    throw new HostError(E.E_INVALID_COMMAND_ID, `invalid ULID at ${path}`, path);
  }
  return value.toUpperCase();
}
