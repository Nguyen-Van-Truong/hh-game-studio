/** Transaction coordinator helpers. Checkpoint + compensate; not OS-global atomic. */

import { createRecoveryCheckpoint, resolveCheckpointRef, restoreCheckpoint, type CheckpointOk } from "../policy/checkpoint.js";
import { E, typedError } from "../registry/errors.js";
import type { PluginCommandResult } from "../transport/plugin_rpc.js";

export interface RecoveryReport {
  restored: boolean;
  files: string[];
  deleted: string[];
  error?: string;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function checkpointEvidence(checkpoint: CheckpointOk): Record<string, unknown> {
  return {
    checkpoint_id: checkpoint.checkpoint_id,
    checkpoint_dir: checkpoint.dir,
    manifest_path: checkpoint.manifest_path,
    hard_delete_blocked: checkpoint.manifest.hard_delete_blocked,
    os_global_atomic: false,
  };
}

export function mergeAfter(
  result: PluginCommandResult,
  extra: Record<string, unknown>,
): PluginCommandResult {
  result.after = { ...(isRecord(result.after) ? result.after : {}), ...extra };
  return result;
}

export function compensateFromManifest(manifestPath: string): RecoveryReport {
  const restored = restoreCheckpoint(manifestPath);
  if (!restored.ok) {
    return { restored: false, files: [], deleted: [], error: restored.error.message };
  }
  return { restored: true, files: restored.restored, deleted: restored.deleted };
}

export function applyGitCheckpoint(opts: {
  commandId: string;
  projectRoot: string;
  message: string;
  paths: readonly string[];
}): PluginCommandResult {
  const created = createRecoveryCheckpoint({
    projectRoot: opts.projectRoot,
    commandId: opts.commandId,
    targets: opts.paths,
  });
  if (!created.ok) {
    return {
      type: "result",
      ok: false,
      command_id: opts.commandId,
      changed: false,
      postcondition: { verified: false, checks: [] },
      error: created.error,
    };
  }
  return {
    type: "result",
    ok: true,
    command_id: opts.commandId,
    changed: true,
    after: {
      ...checkpointEvidence(created),
      message: opts.message,
      git_ref: created.manifest.git_ref,
      git_head: created.manifest.git_head,
      files: created.manifest.files,
      source: "sidecar",
    },
    postcondition: { verified: true, checks: ["checkpoint_ref_present"] },
  };
}

export function applyGitRevert(opts: {
  commandId: string;
  projectRoot: string;
  ref: string;
}): PluginCommandResult {
  const manifestPath = resolveCheckpointRef(opts.projectRoot, opts.ref);
  if (!manifestPath) {
    return {
      type: "result",
      ok: false,
      command_id: opts.commandId,
      changed: false,
      postcondition: { verified: false, checks: [] },
      error: typedError(E.E_CHECKPOINT, `checkpoint ref not found: ${opts.ref}`, "params.ref"),
    };
  }
  const restored = restoreCheckpoint(manifestPath);
  if (!restored.ok) {
    return {
      type: "result",
      ok: false,
      command_id: opts.commandId,
      changed: false,
      postcondition: { verified: false, checks: [] },
      error: restored.error,
    };
  }
  return {
    type: "result",
    ok: true,
    command_id: opts.commandId,
    changed: true,
    after: {
      ref: opts.ref,
      manifest_path: manifestPath,
      restored: restored.restored,
      deleted: restored.deleted,
      recovery: {
        restored: true,
        files: restored.restored,
        deleted: restored.deleted,
      },
      os_global_atomic: false,
      source: "sidecar",
    },
    postcondition: { verified: true, checks: ["tree_matches_checkpoint"] },
  };
}

export function transactionApplyOk(result: PluginCommandResult): PluginCommandResult | undefined {
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return {
      type: "result",
      ok: false,
      command_id: result.command_id,
      changed: false,
      postcondition: { verified: false, checks: [] },
      error: typedError(E.E_UNVERIFIED, "transaction missing Agent UndoRedo name", ""),
    };
  }
  const after = result.after;
  if (!isRecord(after) || !Array.isArray(after.steps) || after.steps.length < 1) {
    return {
      type: "result",
      ok: false,
      command_id: result.command_id,
      changed: false,
      postcondition: { verified: false, checks: [] },
      error: typedError(E.E_UNVERIFIED, "transaction missing steps readback", ""),
    };
  }
  if (after.os_global_atomic === true) {
    return {
      type: "result",
      ok: false,
      command_id: result.command_id,
      changed: false,
      postcondition: { verified: false, checks: [] },
      error: typedError(E.E_UNVERIFIED, "transaction must not claim OS-global atomicity", ""),
    };
  }
  return undefined;
}
