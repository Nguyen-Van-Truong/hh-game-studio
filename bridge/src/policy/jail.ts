/** A8 path jail: canonicalize under project root; reject escape, device, reserved, overlong. */

import fs from "node:fs";
import path from "node:path";

import { E, typedError } from "../registry/errors.js";

export const DEFAULT_MAX_PATH_CHARS = 240;

const WIN_RESERVED = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)/i;

const LOCKED_PREFIXES = [
  "addons/hh_agent/",
  "res://addons/hh_agent/",
  "res://addons/",
  ".hh-agent/",
];

const LOCKED_NAMES = new Set([
  "capability-lock.json",
  "ledger.sqlite",
  "sidecar.lock",
  "session.json",
]);

export interface JailOk {
  ok: true;
  abs: string;
  rel: string;
}

export interface JailErr {
  ok: false;
  error: { code: string; message: string; path: string };
}

export type JailResult = JailOk | JailErr;

function fail(message: string, raw: string, code: string = E.E_PATH): JailErr {
  return { ok: false, error: typedError(code, message, raw) };
}

function posixish(s: string): string {
  return s.replace(/\\/g, "/");
}

function win32Component(part: string): string {
  if (part === "." || part === "..") {
    return part;
  }
  if (part.includes(":")) {
    part = part.split(":", 1)[0] ?? part;
  }
  return part.replace(/[ .]+$/g, "");
}

export function stripResScheme(raw: string): string {
  const t = raw.trim();
  if (t.toLowerCase().startsWith("res://")) {
    return t.slice(6);
  }
  return t;
}

export function collapsePosix(s: string): string {
  let rest = posixish(s.trim());
  let scheme = "";
  if (rest.toLowerCase().startsWith("res://")) {
    scheme = "res://";
    rest = rest.slice(6);
  }
  while (rest.startsWith("./") || rest.startsWith("/")) {
    rest = rest.startsWith("./") ? rest.slice(2) : rest.slice(1);
  }
  const parts: string[] = [];
  for (const rawPart of rest.split("/")) {
    const part = win32Component(rawPart);
    if (part === "" || part === ".") {
      continue;
    }
    parts.push(part === ".." ? ".." : part.toLowerCase());
  }
  return scheme + parts.join("/");
}

function hasDotdot(s: string): boolean {
  return collapsePosix(s)
    .replace(/^res:\/\//, "")
    .split("/")
    .includes("..");
}

function isOsAbsolute(s: string): boolean {
  const t = s.trim();
  if (!t || t === "." || t === "./") {
    return false;
  }
  if (t.toLowerCase().startsWith("res://")) {
    return false;
  }
  if (t.startsWith("//") || t.startsWith("\\\\")) {
    return true;
  }
  if (t.length >= 3 && /[A-Za-z]/.test(t[0] ?? "") && t[1] === ":" && (t[2] === "\\" || t[2] === "/")) {
    return true;
  }
  if (t.startsWith("/")) {
    return true;
  }
  return path.isAbsolute(t);
}

function hasNtfsStream(s: string): boolean {
  const raw = posixish(stripResScheme(s));
  return raw.split("/").some((part) => part.includes(":"));
}

function hasReservedDevice(s: string): boolean {
  const raw = posixish(stripResScheme(s));
  return raw.split("/").some((part) => WIN_RESERVED.test(win32Component(part)));
}

function stripLongPathPrefix(p: string): string {
  if (p.startsWith("\\\\?\\UNC\\")) {
    return `\\\\${p.slice(8)}`;
  }
  if (p.startsWith("\\\\?\\")) {
    return p.slice(4);
  }
  return p;
}

function realExisting(p: string): string {
  try {
    return stripLongPathPrefix(fs.realpathSync.native(p));
  } catch {
    return path.resolve(p);
  }
}

function existingPrefix(abs: string): { base: string; rest: string } {
  let cur = abs;
  const parts: string[] = [];
  for (;;) {
    try {
      if (fs.existsSync(cur)) {
        return { base: cur, rest: parts.reverse().join(path.sep) };
      }
    } catch {
      /* continue */
    }
    const parent = path.dirname(cur);
    if (parent === cur) {
      return { base: cur, rest: parts.reverse().join(path.sep) };
    }
    parts.push(path.basename(cur));
    cur = parent;
  }
}

export function isLockedProjectRel(rel: string): boolean {
  const collapsed = collapsePosix(rel);
  const body = collapsed.startsWith("res://") ? collapsed : collapsed;
  const prefixed = body.endsWith("/") ? body : `${body}/`;
  for (const lock of LOCKED_PREFIXES) {
    if (prefixed.startsWith(lock) || body === lock.replace(/\/$/, "")) {
      return true;
    }
  }
  const name = body.split("/").pop() ?? "";
  if (LOCKED_NAMES.has(name)) {
    return true;
  }
  if (body.includes("/.hh-agent/") || body.startsWith(".hh-agent")) {
    return true;
  }
  return false;
}

export function jailProjectPath(
  projectRoot: string,
  candidate: string,
  opts: { maxPathChars?: number; forWrite?: boolean } = {},
): JailResult {
  const maxChars = opts.maxPathChars ?? DEFAULT_MAX_PATH_CHARS;
  if (!candidate || typeof candidate !== "string") {
    return fail("path required", String(candidate ?? ""));
  }
  if (candidate.includes("\0")) {
    return fail("NUL in path", candidate);
  }
  if (candidate.length > maxChars) {
    return fail("path too long", candidate);
  }
  if (hasDotdot(candidate)) {
    return fail("path escapes via ..", candidate);
  }
  if (hasNtfsStream(candidate)) {
    return fail("NTFS stream / reserved colon", candidate);
  }
  if (hasReservedDevice(candidate)) {
    return fail("device or reserved name", candidate);
  }
  if (isOsAbsolute(candidate)) {
    return fail("absolute path is outside the project jail", candidate);
  }

  let rootAbs: string;
  try {
    rootAbs = realExisting(projectRoot);
  } catch {
    return fail("project root is not a directory", projectRoot);
  }

  const stripped = stripResScheme(candidate);
  // path.resolve on Windows is GetFullPathNameW-equivalent (., .., drive).
  const resolved = stripLongPathPrefix(path.resolve(rootAbs, stripped));
  const { base, rest } = existingPrefix(resolved);
  let realBase: string;
  try {
    realBase = stripLongPathPrefix(fs.realpathSync.native(base));
  } catch {
    realBase = stripLongPathPrefix(path.resolve(base));
  }
  const combined = rest ? path.resolve(realBase, rest) : realBase;
  const relToRoot = path.relative(rootAbs, combined);
  if (relToRoot.startsWith("..") || path.isAbsolute(relToRoot)) {
    return fail("symlink/junction/absolute escape from project root", candidate);
  }
  const relPosix = posixish(relToRoot);
  if (opts.forWrite !== false && isLockedProjectRel(relPosix)) {
    return fail("generic write/delete is locked for this path", candidate, E.E_POLICY);
  }
  if (relPosix.length > maxChars) {
    return fail("canonical path too long", candidate);
  }
  return { ok: true, abs: combined, rel: relPosix };
}

export function extractTargetPaths(params: Record<string, unknown>): string[] {
  const keys = ["path", "scene", "from", "to", "target", "file"];
  const out: string[] = [];
  for (const key of keys) {
    const value = params[key];
    if (typeof value === "string" && value.length > 0) {
      out.push(value);
    }
  }
  for (const value of Object.values(params)) {
    if (typeof value === "string" && value.toLowerCase().startsWith("res://") && !out.includes(value)) {
      out.push(value);
    }
  }
  return out;
}
