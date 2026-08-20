/** Crockford Base32 ULID (26 chars). Format check only. */

const ULID_RE = /^[0-7][0-9A-HJKMNPQRSTVWXYZ]{25}$/;

export const EXAMPLE_ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV";

export function isUlid(value: string): boolean {
  return ULID_RE.test(value.toUpperCase());
}
