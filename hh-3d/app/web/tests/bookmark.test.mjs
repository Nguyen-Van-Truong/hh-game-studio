import assert from "node:assert/strict";
import test from "node:test";

const ID_PATTERN = /^place-[a-z0-9-]+$/;

function sanitizeBookmark(row) {
  if (!row || typeof row !== "object") {
    return null;
  }
  if (row.v !== 1) {
    return null;
  }
  if (typeof row.id !== "string" || !ID_PATTERN.test(row.id)) {
    return null;
  }
  if (typeof row.savedAt !== "string" || row.savedAt.length < 8 || row.savedAt.length > 40) {
    return null;
  }
  return { v: 1, id: row.id, savedAt: row.savedAt };
}

test("bookmark allowlist rejects extra keys and bad ids", () => {
  assert.deepEqual(
    sanitizeBookmark({ v: 1, id: "place-market-hall", savedAt: "2026-09-03T00:00:00Z" }),
    { v: 1, id: "place-market-hall", savedAt: "2026-09-03T00:00:00Z" },
  );
  assert.equal(sanitizeBookmark({ v: 1, id: "../etc/passwd", savedAt: "2026-09-03" }), null);
  assert.equal(sanitizeBookmark({ v: 2, id: "place-market-hall", savedAt: "2026-09-03" }), null);
  assert.equal(sanitizeBookmark({ id: "place-market-hall" }), null);
});
