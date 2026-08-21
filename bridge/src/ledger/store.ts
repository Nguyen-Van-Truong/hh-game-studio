import fs from "node:fs";

import { E, typedError } from "../registry/errors.js";
import { applyCurrentUserAcl } from "../session/acl.js";
import { agentHome } from "../session/paths.js";
import type { ProcessSupervisor } from "../session/supervisor.js";
import { openSqliteFile, type SqliteDatabase } from "./node_sqlite.js";
import { ledgerFilePath, projectStoreDir } from "./paths.js";
import { isLedgerState, type LedgerState } from "./states.js";

export interface CommandRow {
  command_id: string;
  request_hash: string;
  actor_id: string;
  project_id: string;
  policy: string;
  method: string;
  action: string;
  action_id: string;
  side_effect: string;
  state: LedgerState;
  envelope_json: string;
  result_json: string;
  error_code: string;
  error_message: string;
  postcondition_json: string;
  precondition_json: string;
  before_summary: string;
  after_summary: string;
  apply_count: number;
  dispatch_attempted: number;
  evidence_json: string;
  created_at: string;
  updated_at: string;
}

export interface CheckpointRow {
  checkpoint_id: string;
  command_id: string;
  evidence_json: string;
  created_at: string;
}

export interface OpenLedgerOpts {
  projectId: string;
  supervisor: ProcessSupervisor;
  home?: string;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS commands (
  command_id TEXT PRIMARY KEY,
  request_hash TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  policy TEXT NOT NULL,
  method TEXT NOT NULL,
  action TEXT NOT NULL,
  action_id TEXT NOT NULL DEFAULT '',
  side_effect TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL,
  envelope_json TEXT NOT NULL,
  result_json TEXT NOT NULL DEFAULT '',
  error_code TEXT NOT NULL DEFAULT '',
  error_message TEXT NOT NULL DEFAULT '',
  postcondition_json TEXT NOT NULL DEFAULT '',
  precondition_json TEXT NOT NULL DEFAULT '',
  before_summary TEXT NOT NULL DEFAULT '',
  after_summary TEXT NOT NULL DEFAULT '',
  apply_count INTEGER NOT NULL DEFAULT 0,
  dispatch_attempted INTEGER NOT NULL DEFAULT 0,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  command_id TEXT NOT NULL DEFAULT '',
  evidence_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
`;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asInt(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "bigint") {
    return Number(value);
  }
  return 0;
}

function parseRow(raw: unknown): CommandRow | undefined {
  if (!isRecord(raw)) {
    return undefined;
  }
  const state = asString(raw.state);
  if (!isLedgerState(state)) {
    return undefined;
  }
  return {
    command_id: asString(raw.command_id),
    request_hash: asString(raw.request_hash),
    actor_id: asString(raw.actor_id),
    project_id: asString(raw.project_id),
    policy: asString(raw.policy),
    method: asString(raw.method),
    action: asString(raw.action),
    action_id: asString(raw.action_id),
    side_effect: asString(raw.side_effect),
    state,
    envelope_json: asString(raw.envelope_json),
    result_json: asString(raw.result_json),
    error_code: asString(raw.error_code),
    error_message: asString(raw.error_message),
    postcondition_json: asString(raw.postcondition_json),
    precondition_json: asString(raw.precondition_json),
    before_summary: asString(raw.before_summary),
    after_summary: asString(raw.after_summary),
    apply_count: asInt(raw.apply_count),
    dispatch_attempted: asInt(raw.dispatch_attempted),
    evidence_json: asString(raw.evidence_json, "[]"),
    created_at: asString(raw.created_at),
    updated_at: asString(raw.updated_at),
  };
}

function parseEvidence(raw: string): string[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is string => typeof item === "string" && item.length > 0);
  } catch {
    return [];
  }
}

export class CommandLedger {
  readonly filePath: string;
  readonly projectId: string;
  readonly home: string;
  private readonly db: SqliteDatabase;

  constructor(filePath: string, projectId: string, home: string, db: SqliteDatabase) {
    this.filePath = filePath;
    this.projectId = projectId;
    this.home = home;
    this.db = db;
  }

  pragmaInfo(): { journal_mode: string; synchronous: number } {
    const journal = this.db.prepare("PRAGMA journal_mode").get();
    const sync = this.db.prepare("PRAGMA synchronous").get();
    const journalMode = isRecord(journal) ? asString(journal.journal_mode) : "";
    const synchronous = isRecord(sync) ? asInt(sync.synchronous) : -1;
    return { journal_mode: journalMode, synchronous };
  }

  get(commandId: string): CommandRow | undefined {
    return parseRow(this.db.prepare("SELECT * FROM commands WHERE command_id = ?").get(commandId));
  }

  listInFlight(): CommandRow[] {
    const rows = this.db
      .prepare(
        "SELECT * FROM commands WHERE state NOT IN ('committed_durable', 'failed', 'uncertain')",
      )
      .all();
    return rows.map(parseRow).filter((row): row is CommandRow => row !== undefined);
  }

  insertReceived(row: CommandRow): void {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db
        .prepare(
          `INSERT INTO commands (
            command_id, request_hash, actor_id, project_id, policy, method, action,
            action_id, side_effect, state, envelope_json, result_json, error_code,
            error_message, postcondition_json, precondition_json, before_summary,
            after_summary, apply_count, dispatch_attempted, evidence_json, created_at, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          row.command_id,
          row.request_hash,
          row.actor_id,
          row.project_id,
          row.policy,
          row.method,
          row.action,
          row.action_id,
          row.side_effect,
          row.state,
          row.envelope_json,
          row.result_json,
          row.error_code,
          row.error_message,
          row.postcondition_json,
          row.precondition_json,
          row.before_summary,
          row.after_summary,
          row.apply_count,
          row.dispatch_attempted,
          row.evidence_json,
          row.created_at,
          row.updated_at,
        );
      this.db.exec("COMMIT");
    } catch (err) {
      this.db.exec("ROLLBACK");
      throw err;
    }
    this.flush();
  }

  save(row: CommandRow): void {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db
        .prepare(
          `UPDATE commands SET
            request_hash = ?, actor_id = ?, project_id = ?, policy = ?, method = ?, action = ?,
            action_id = ?, side_effect = ?, state = ?, envelope_json = ?, result_json = ?,
            error_code = ?, error_message = ?, postcondition_json = ?, precondition_json = ?,
            before_summary = ?, after_summary = ?, apply_count = ?, dispatch_attempted = ?,
            evidence_json = ?, updated_at = ?
          WHERE command_id = ?`,
        )
        .run(
          row.request_hash,
          row.actor_id,
          row.project_id,
          row.policy,
          row.method,
          row.action,
          row.action_id,
          row.side_effect,
          row.state,
          row.envelope_json,
          row.result_json,
          row.error_code,
          row.error_message,
          row.postcondition_json,
          row.precondition_json,
          row.before_summary,
          row.after_summary,
          row.apply_count,
          row.dispatch_attempted,
          row.evidence_json,
          row.updated_at,
          row.command_id,
        );
      this.db.exec("COMMIT");
    } catch (err) {
      this.db.exec("ROLLBACK");
      throw err;
    }
    this.flush();
  }

  flush(): void {
    this.db.exec("PRAGMA wal_checkpoint(FULL)");
  }

  attachEvidence(commandId: string, refs: readonly string[]): CommandRow {
    const row = this.get(commandId);
    if (!row) {
      throw typedError(E.E_UNVERIFIED, "command not in ledger", "command_id");
    }
    const merged = [...new Set([...parseEvidence(row.evidence_json), ...refs])];
    row.evidence_json = JSON.stringify(merged);
    row.updated_at = new Date().toISOString();
    this.save(row);
    return row;
  }

  addCheckpoint(checkpointId: string, evidenceRefs: readonly string[], commandId = ""): void {
    const now = new Date().toISOString();
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db
        .prepare(
          "INSERT OR REPLACE INTO checkpoints (checkpoint_id, command_id, evidence_json, created_at) VALUES (?, ?, ?, ?)",
        )
        .run(checkpointId, commandId, JSON.stringify([...evidenceRefs]), now);
      this.db.exec("COMMIT");
    } catch (err) {
      this.db.exec("ROLLBACK");
      throw err;
    }
    this.flush();
  }

  listCheckpoints(): CheckpointRow[] {
    const rows = this.db.prepare("SELECT * FROM checkpoints").all();
    const out: CheckpointRow[] = [];
    for (const raw of rows) {
      if (!isRecord(raw)) {
        continue;
      }
      out.push({
        checkpoint_id: asString(raw.checkpoint_id),
        command_id: asString(raw.command_id),
        evidence_json: asString(raw.evidence_json, "[]"),
        created_at: asString(raw.created_at),
      });
    }
    return out;
  }

  /** Drop old committed/failed rows that a live checkpoint does not still name. */
  compact(nowMs: number, maxAgeMs: number): { deleted: number; kept: number } {
    const cutoff = new Date(nowMs - maxAgeMs).toISOString();
    const protectedIds = new Set<string>();
    const protectedEvidence = new Set<string>();
    for (const cp of this.listCheckpoints()) {
      if (cp.command_id) {
        protectedIds.add(cp.command_id);
      }
      for (const ref of parseEvidence(cp.evidence_json)) {
        protectedEvidence.add(ref);
      }
    }
    const candidates = this.db
      .prepare(
        "SELECT * FROM commands WHERE state IN ('committed_durable', 'failed') AND updated_at <= ?",
      )
      .all(cutoff);
    let deleted = 0;
    let kept = 0;
    for (const raw of candidates) {
      const row = parseRow(raw);
      if (!row) {
        continue;
      }
      const refs = parseEvidence(row.evidence_json);
      const pinned =
        protectedIds.has(row.command_id) || refs.some((ref) => protectedEvidence.has(ref));
      if (pinned) {
        kept += 1;
        continue;
      }
      this.db.prepare("DELETE FROM commands WHERE command_id = ?").run(row.command_id);
      deleted += 1;
    }
    this.flush();
    return { deleted, kept };
  }

  close(): void {
    this.db.close();
  }
}

export function emptyRow(partial: Omit<CommandRow, "created_at" | "updated_at"> & {
  created_at?: string;
  updated_at?: string;
}): CommandRow {
  const now = new Date().toISOString();
  return {
    ...partial,
    created_at: partial.created_at ?? now,
    updated_at: partial.updated_at ?? now,
  };
}

export function openLedger(opts: OpenLedgerOpts): CommandLedger {
  const home = opts.home ?? agentHome();
  const dir = projectStoreDir(opts.projectId, home);
  fs.mkdirSync(dir, { recursive: true });
  applyCurrentUserAcl(dir, opts.supervisor);
  const filePath = ledgerFilePath(opts.projectId, home);
  const existed = fs.existsSync(filePath);
  const db = openSqliteFile(filePath);
  db.exec("PRAGMA journal_mode = WAL");
  db.exec("PRAGMA synchronous = FULL");
  db.exec("PRAGMA foreign_keys = ON");
  db.exec(SCHEMA);
  db.exec("INSERT OR REPLACE INTO ledger_meta (key, value) VALUES ('schema', '1')");
  db.exec("PRAGMA wal_checkpoint(FULL)");
  if (!existed) {
    applyCurrentUserAcl(filePath, opts.supervisor);
  }
  const ledger = new CommandLedger(filePath, opts.projectId, home, db);
  const pragma = ledger.pragmaInfo();
  if (pragma.journal_mode !== "wal") {
    ledger.close();
    throw typedError(E.E_PATH, "ledger journal_mode must be WAL", "journal_mode");
  }
  if (pragma.synchronous !== 2) {
    ledger.close();
    throw typedError(E.E_PATH, "ledger synchronous must be FULL", "synchronous");
  }
  return ledger;
}
