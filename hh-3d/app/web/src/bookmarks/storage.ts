import type { Bookmark } from "../contracts/types";

export const BOOKMARK_KEY = "hh-world.bookmarks.v1";
const ID_PATTERN = /^place-[a-z0-9-]+$/;

export function loadBookmarks(): Bookmark[] {
  if (typeof localStorage === "undefined") {
    return [];
  }
  try {
    const raw = localStorage.getItem(BOOKMARK_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map((row) => sanitizeBookmark(row))
      .filter((row): row is Bookmark => row !== null);
  } catch {
    return [];
  }
}

export function saveBookmarks(rows: Bookmark[]): Bookmark[] {
  const clean = rows
    .map((row) => sanitizeBookmark(row))
    .filter((row): row is Bookmark => row !== null);
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify(clean));
  return clean;
}

export function toggleBookmark(rows: Bookmark[], id: string, now: string): Bookmark[] {
  const existing = rows.filter((row) => row.id !== id);
  if (existing.length !== rows.length) {
    return saveBookmarks(existing);
  }
  return saveBookmarks([...rows, { v: 1, id, savedAt: now }]);
}

export function resetBookmarks(): Bookmark[] {
  localStorage.removeItem(BOOKMARK_KEY);
  return [];
}

export function exportBookmarks(rows: Bookmark[]): string {
  return `${JSON.stringify(rows, null, 2)}\n`;
}

export function sanitizeBookmark(row: unknown): Bookmark | null {
  if (!row || typeof row !== "object") {
    return null;
  }
  const rec = row as Record<string, unknown>;
  if (rec["v"] !== 1) {
    return null;
  }
  const id = rec["id"];
  const savedAt = rec["savedAt"];
  if (typeof id !== "string" || !ID_PATTERN.test(id)) {
    return null;
  }
  if (typeof savedAt !== "string" || savedAt.length < 8 || savedAt.length > 40) {
    return null;
  }
  return { v: 1, id, savedAt };
}

export function isBookmarked(rows: Bookmark[], id: string): boolean {
  return rows.some((row) => row.id === id);
}
