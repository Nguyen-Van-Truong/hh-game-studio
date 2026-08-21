/** Crockford Base32 ULID (26 chars). Format check plus CSPRNG mint. */

import { randomBytes } from "node:crypto";

const ULID_RE = /^[0-7][0-9A-HJKMNPQRSTVWXYZ]{25}$/;
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

export const EXAMPLE_ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV";

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
