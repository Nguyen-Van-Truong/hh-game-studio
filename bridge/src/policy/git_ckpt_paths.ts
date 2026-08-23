/** Read r7w3 git-checkpoint manifests without importing the ledger adapter. */

import fs from "node:fs";
import path from "node:path";

export function peekGitCkptFilePaths(projectRoot: string, ref: string): string[] {
  const raw = ref.trim();
  if (!raw || !projectRoot) {
    return [];
  }
  const root = path.join(projectRoot, "r7w3", "ckpts");
  let entries: fs.Dirent[] = [];
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch {
    return [];
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const abs = path.join(root, entry.name, "checkpoint.json");
    if (!fs.existsSync(abs)) {
      continue;
    }
    try {
      const parsed: unknown = JSON.parse(fs.readFileSync(abs, "utf8"));
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        continue;
      }
      const rec = parsed as Record<string, unknown>;
      const ids = [
        rec.checkpoint_id,
        rec.run_id,
        rec.git_ref,
        rec.git_commit,
        typeof rec.project === "string" && typeof rec.run_id === "string" ? `${rec.project}/${rec.run_id}` : "",
      ].map((item) => String(item ?? ""));
      const match =
        ids.includes(raw) ||
        raw.endsWith(`${entry.name}/checkpoint.json`) ||
        raw.endsWith(`r7w3/ckpts/${entry.name}/checkpoint.json`);
      if (!match) {
        continue;
      }
      const files = Array.isArray(rec.files) ? rec.files : [];
      return files
        .map((row) => (row && typeof row === "object" && !Array.isArray(row) ? String((row as { rel?: unknown }).rel ?? "") : ""))
        .filter((rel) => rel.length > 0);
    } catch {
      continue;
    }
  }
  return [];
}
