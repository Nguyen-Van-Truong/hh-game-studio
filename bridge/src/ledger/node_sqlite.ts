import { createRequire } from "node:module";

export type SqlValue = null | number | bigint | string | Uint8Array;

export interface SqliteStatement {
  run(...params: SqlValue[]): { changes: number };
  get(...params: SqlValue[]): unknown;
  all(...params: SqlValue[]): unknown[];
}

export interface SqliteDatabase {
  exec(sql: string): void;
  prepare(sql: string): SqliteStatement;
  close(): void;
}

interface SqliteModule {
  DatabaseSync: new (location: string) => SqliteDatabase;
}

/** Node 24 built-in SQLite. No npm driver. */
export function openSqliteFile(filePath: string): SqliteDatabase {
  const require = createRequire(import.meta.url);
  const sqlite = require("node:sqlite") as SqliteModule;
  return new sqlite.DatabaseSync(filePath);
}
