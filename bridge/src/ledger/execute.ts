/** Durable command ledger: flush before dispatch, dedup, uncertain recovery. */

import fs from "node:fs";
import path from "node:path";

import { runMutationGate, type GateResult, type PolicyServices } from "../policy/engine.js";
import { extractTargetPaths, jailProjectPath } from "../policy/jail.js";
import { contentHash } from "../policy/leases.js";
import { DEFAULT_POLICY, normalizePolicy } from "../policy/profiles.js";
import { isSidecarOnlyAction, trySidecarRead } from "../read/sidecar_reads.js";
import { acceptCommand } from "../registry/dispatch.js";
import { E, typedError } from "../registry/errors.js";
import { getAction } from "../registry/registry.js";
import { PROTOCOL } from "../registry/types.js";
import { isUlid } from "../registry/ulid.js";
import {
  isNoopEnvelope,
  PLUGIN_NOOP_ACTION,
  PLUGIN_NOOP_METHOD,
  unverifiedResult,
  type PluginCommandResult,
} from "../transport/plugin_rpc.js";
import { LedgerPluginDeath, maybeCrashAfterDispatchAttempt, maybeFault } from "./fault.js";
import { canonicalRequestHash } from "./hash.js";
import {
  durableResPath,
  isAnimationApply,
  isAssetIngestApply,
  isAssetRefApply,
  isCameraApply,
  isCanvasApply,
  isProjectSettingsApply,
  isTilemapApply,
  isPropertyApply,
  isProvenEditorApply,
  isResourceApply,
  isSceneLifecycleApply,
  isScriptApply,
  isSidecarMutateApply,
  isSignalApply,
  isTransactionApply,
  isUiApply,
  isPhysicsApply,
  isAudioApply,
  isRenderApply,
  isPlayApply,
  isInputApply,
  isRuntimeApply,
  isTestApply,
  isOrchestratorApply,
  isExportApply,
  mutationNeedsDiskHash,
  nodeNeedsUidAfter,
  sceneNeedsDiskHash,
} from "./scene_lifecycle.js";
import { notePlayAfter } from "./play_session.js";
import { handleOrchAction } from "../orchestrator/machine.js";
import { handleExportAction } from "../export/job.js";
import { handleScheduleAction } from "../scheduler/machine.js";
import { handleSoakAction } from "../soak/machine.js";
import { lookupSoakCached, rememberSoakResult } from "../soak/store.js";
import { emptyRow, type CommandLedger, type CommandRow } from "./store.js";
import type { LedgerState } from "./states.js";
import {
  applyGitCheckpoint,
  applyGitRevert,
  checkpointEvidence,
  compensateFromManifest,
  mergeAfter,
  transactionApplyOk,
} from "./transaction.js";

export { DEFAULT_POLICY as DEFAULT_LEDGER_POLICY, normalizePolicy };

export interface LedgerBound {
  actorId: string;
  projectId: string;
  policy: string;
}

export interface PluginReadback {
  command_id: string;
  found: boolean;
  ok: boolean;
  postcondition: { verified: boolean; checks: string[] };
}

export interface LedgerRuntime {
  dispatch(envelope: Record<string, unknown>, timeoutMs: number): Promise<PluginCommandResult>;
  readPostcondition(commandId: string): Promise<PluginReadback>;
  pluginConnected(): boolean;
  killPlugin?: () => void;
  policy?: PolicyServices;
  projectRoot?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isNoopVerified(post: { verified: boolean; checks: string[] }): boolean {
  return post.verified === true && post.checks.length === 1 && post.checks[0] === "noop";
}

export function errorResult(
  commandId: string,
  code: string,
  message: string,
  path = "",
): PluginCommandResult {
  return {
    type: "result",
    ok: false,
    command_id: commandId,
    changed: false,
    postcondition: { verified: false, checks: [] },
    error: typedError(code, message, path),
  };
}

export function parseStoredResult(raw: string, commandId: string): PluginCommandResult | undefined {
  if (!raw) {
    return undefined;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed)) {
      return undefined;
    }
    const postRaw = parsed.postcondition;
    const checks =
      isRecord(postRaw) && Array.isArray(postRaw.checks)
        ? postRaw.checks.filter((item): item is string => typeof item === "string")
        : [];
    const result: PluginCommandResult = {
      type: "result",
      ok: parsed.ok === true,
      command_id: typeof parsed.command_id === "string" ? parsed.command_id : commandId,
      changed: parsed.changed === true,
      postcondition: {
        verified: isRecord(postRaw) && postRaw.verified === true,
        checks,
      },
    };
    if (isRecord(parsed.error) && typeof parsed.error.code === "string") {
      result.error = {
        code: parsed.error.code,
        message: typeof parsed.error.message === "string" ? parsed.error.message : "",
        path: typeof parsed.error.path === "string" ? parsed.error.path : "",
      };
    }
    if (isRecord(parsed.after)) {
      result.after = parsed.after;
    }
    if (typeof parsed.undo_action === "string") {
      result.undo_action = parsed.undo_action;
    }
    return result;
  } catch {
    return undefined;
  }
}

function nowIso(): string {
  return new Date().toISOString();
}

function envelopeFields(raw: Record<string, unknown>): {
  command_id: string;
  method: string;
  action: string;
  params: Record<string, unknown>;
} {
  const params = isRecord(raw.params) ? raw.params : {};
  return {
    command_id: typeof raw.command_id === "string" ? raw.command_id : "",
    method: typeof raw.method === "string" ? raw.method : "",
    action: typeof raw.action === "string" ? raw.action : "",
    params,
  };
}

function identityConflict(row: CommandRow, hash: string, bound: LedgerBound): boolean {
  return (
    row.request_hash !== hash ||
    row.actor_id !== bound.actorId ||
    row.project_id !== bound.projectId ||
    row.policy !== bound.policy
  );
}

function persistResult(row: CommandRow, result: PluginCommandResult): void {
  row.result_json = JSON.stringify(result);
  row.postcondition_json = JSON.stringify(result.postcondition);
  row.error_code = result.error?.code ?? "";
  row.error_message = result.error?.message ?? "";
}

function asCachedReplay(stored: PluginCommandResult): PluginCommandResult {
  const after = isRecord(stored.after) ? { ...stored.after, soak_cached: true } : { soak_cached: true };
  const checks = stored.postcondition?.checks ?? [];
  return {
    ...stored,
    changed: false,
    after,
    postcondition: {
      verified: stored.postcondition?.verified === true || stored.ok === true,
      checks: checks.includes("soak_cached") ? checks : [...checks, "soak_cached"],
    },
  };
}

function cachedOrError(row: CommandRow): PluginCommandResult {
  if (row.state === "uncertain") {
    return errorResult(
      row.command_id,
      E.E_UNCERTAIN,
      row.error_message || "command is uncertain; will not apply blind",
    );
  }
  const stored = parseStoredResult(row.result_json, row.command_id);
  if (stored) {
    // Durable replay must not look like a second apply (changed:true, no soak_cached).
    if (row.state === "committed_durable") {
      return asCachedReplay(stored);
    }
    return stored;
  }
  if (row.state === "failed") {
    return errorResult(
      row.command_id,
      row.error_code || E.E_UNVERIFIED,
      row.error_message || "failed",
    );
  }
  return errorResult(row.command_id, E.E_UNVERIFIED, "cached result missing");
}

function saveState(
  ledger: CommandLedger,
  row: CommandRow,
  state: LedgerState,
  extras?: Partial<CommandRow>,
): void {
  row.state = state;
  row.updated_at = nowIso();
  if (extras) {
    Object.assign(row, extras);
    row.state = state;
    row.updated_at = nowIso();
  }
  ledger.save(row);
}

type Classified =
  | { kind: "noop"; timeoutMs: number }
  | { kind: "forward"; sideEffect: string; actionId: string; timeoutMs: number }
  | { kind: "mutate"; sideEffect: string; actionId: string; timeoutMs: number }
  | { kind: "blocked"; sideEffect: string; actionId: string; result: PluginCommandResult }
  | { kind: "invalid"; result: PluginCommandResult };

export function isReadVerified(post: { verified: boolean; checks: string[] }, actionId: string): boolean {
  const expected = getAction(actionId)?.postcondition;
  return post.verified === true && expected !== undefined && post.checks.includes(expected);
}

function commitReady(result: PluginCommandResult, row: CommandRow): boolean {
  if (!result.ok) {
    return false;
  }
  if (row.action_id === "hh.plugin/noop" || row.method === PLUGIN_NOOP_METHOD) {
    return isNoopVerified(result.postcondition);
  }
  if (row.action_id) {
    return isReadVerified(result.postcondition, row.action_id);
  }
  return false;
}

function storedSceneReady(
  stored: PluginCommandResult,
  row: CommandRow,
  envelope: Record<string, unknown>,
  runtime: LedgerRuntime,
): boolean {
  if (!commitReady(stored, row)) {
    return false;
  }
  const params = envelopeFields(envelope).params;
  if (!mutationNeedsDiskHash(row.action_id, params)) {
    return true;
  }
  const projectRoot = runtime.projectRoot ?? runtime.policy?.projectRoot ?? "";
  if (!projectRoot) {
    return false;
  }
  return durableDiskOk(stored, row.action_id, params, projectRoot) === undefined;
}

function classify(raw: Record<string, unknown>, commandId: string): Classified {
  const fields = envelopeFields(raw);
  if (fields.method === PLUGIN_NOOP_METHOD) {
    if (fields.action !== PLUGIN_NOOP_ACTION) {
      return {
        kind: "invalid",
        result: errorResult(commandId, E.E_UNKNOWN_ACTION, "unknown plugin action", "action"),
      };
    }
    return { kind: "noop", timeoutMs: 5_000 };
  }
  const accepted = acceptCommand({
    protocol: typeof raw.protocol === "string" ? raw.protocol : PROTOCOL,
    command_id: commandId,
    method: fields.method,
    action: fields.action,
    params: fields.params,
    ...(typeof raw.action_version === "string" ? { action_version: raw.action_version } : {}),
    ...(isRecord(raw.precondition) ? { precondition: raw.precondition } : {}),
    ...(isRecord(raw.presentation) ? { presentation: raw.presentation } : {}),
  });
  if (!accepted.accepted) {
    return {
      kind: "invalid",
      result: errorResult(
        commandId,
        accepted.error.code,
        accepted.error.message,
        accepted.error.path,
      ),
    };
  }
  const def = getAction(accepted.action_id);
  const side = def?.side_effect ?? "";
  if (side === "read" || side === "view") {
    return {
      kind: "forward",
      sideEffect: side,
      actionId: accepted.action_id,
      timeoutMs: def?.timeout_ms ?? 5_000,
    };
  }
  if (
    isProvenEditorApply(accepted.action_id) ||
    isSidecarMutateApply(accepted.action_id) ||
    isPlayApply(accepted.action_id) ||
    isInputApply(accepted.action_id) ||
    isRuntimeApply(accepted.action_id) ||
    isTestApply(accepted.action_id) ||
    isOrchestratorApply(accepted.action_id) ||
    isExportApply(accepted.action_id) ||
    accepted.action_id === "editor.pause"
  ) {
    return {
      kind: "mutate",
      sideEffect: side,
      actionId: accepted.action_id,
      timeoutMs:
        def?.timeout_ms ??
        (isPlayApply(accepted.action_id) ||
        isInputApply(accepted.action_id) ||
        isRuntimeApply(accepted.action_id) ||
        isTestApply(accepted.action_id) ||
        isOrchestratorApply(accepted.action_id) ||
        isExportApply(accepted.action_id)
          ? 120_000
          : 15_000),
    };
  }
  return {
    kind: "blocked",
    sideEffect: side,
    actionId: accepted.action_id,
    result: unverifiedResult(commandId, "not dispatched"),
  };
}

function canonJson(value: unknown): unknown {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => canonJson(item));
  }
  if (isRecord(value)) {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value).sort()) {
      out[key] = canonJson(value[key]);
    }
    return out;
  }
  return value;
}

function encodedClose(after: unknown, requested: unknown): boolean {
  return valueClose(canonJson(after), canonJson(requested));
}

function valueClose(after: unknown, requested: unknown): boolean {
  if (typeof after === "number" && typeof requested === "number") {
    if (!Number.isFinite(after) || !Number.isFinite(requested)) {
      return after === requested;
    }
    if (after === requested) {
      return true;
    }
    const scale = Math.max(Math.abs(after), Math.abs(requested), 1);
    return Math.abs(after - requested) <= 1e-5 * scale;
  }
  if (Array.isArray(after) && Array.isArray(requested)) {
    return after.length === requested.length && after.every((item, i) => valueClose(item, requested[i]));
  }
  if (isRecord(after) && isRecord(requested)) {
    for (const key of Object.keys(requested)) {
      if (!valueClose(after[key], requested[key])) {
        return false;
      }
    }
    return true;
  }
  return after === requested;
}

function propertyApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isPropertyApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "property missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after) || after.readback_equals !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "property readback did not equal set");
  }
  if (actionId === "property.set") {
    if (!isRecord(after.value)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "property.set missing encoded value");
    }
    if (!encodedClose(after.value, params.value)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "property.set readback != requested value");
    }
  }
  if (actionId === "property.batch") {
    if (!Array.isArray(after.items) || after.items.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "property.batch missing items readback");
    }
    const requested = Array.isArray(params.items) ? params.items : [];
    if (after.items.length !== requested.length) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "property.batch item count mismatch");
    }
    for (let i = 0; i < requested.length; i += 1) {
      const want = requested[i];
      const got = after.items[i];
      if (!isRecord(want) || !isRecord(got) || !encodedClose(got.value, want.value)) {
        return errorResult(result.command_id, E.E_UNVERIFIED, `property.batch item ${i} readback != set`);
      }
    }
  }
  if (actionId === "property.reset" && after.is_default !== true && after.reverted !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "property.reset missing default readback");
  }
  return undefined;
}

function canvasApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isCanvasApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "canvas missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after) || after.readback_equals !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "canvas readback did not equal set");
  }
  if (actionId === "canvas.layout_batch") {
    if (!Array.isArray(after.items) || after.items.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "canvas.layout_batch missing items readback");
    }
    const requested = Array.isArray(params.items) ? params.items : [];
    if (after.items.length !== requested.length) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "canvas.layout_batch item count mismatch");
    }
    for (let i = 0; i < requested.length; i += 1) {
      const want = requested[i];
      const got = after.items[i];
      if (
        !isRecord(want) ||
        !isRecord(got) ||
        got.node_path !== want.node_path ||
        got.property !== want.property ||
        !encodedClose(got.value, want.value)
      ) {
        return errorResult(result.command_id, E.E_UNVERIFIED, `canvas.layout_batch item ${i} readback != set`);
      }
    }
  }
  return undefined;
}

function tilemapApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isTilemapApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap missing after readback");
  }
  if (Array.isArray(after.cells) && after.cells.length > 100) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap after returned more than one page of cells");
  }
  if (
    (actionId === "tilemap.tileset" ||
      actionId === "tilemap.layer" ||
      actionId === "tilemap.cell" ||
      actionId === "tilemap.fill" ||
      actionId === "tilemap.stamp") &&
    after.node_path !== params.node_path
  ) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap node_path bind mismatch");
  }
  if (actionId === "tilemap.tileset") {
    if (after.tileset !== params.tileset) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.tileset path bind mismatch");
    }
    if (after.class_name !== "TileSet" && after.tileset_class !== "TileSet") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.tileset class bind mismatch");
    }
  }
  if (actionId === "tilemap.source") {
    if (after.tileset !== params.tileset) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.source tileset bind mismatch");
    }
    if (after.source_id !== params.source_id) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.source source_id bind mismatch");
    }
    if (params.op !== "remove" && after.has_source !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.source has_source readback failed");
    }
    if (typeof after.tile_count !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.source missing tile_count");
    }
  }
  if (actionId === "tilemap.terrain") {
    if (after.tileset !== params.tileset) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.terrain tileset bind mismatch");
    }
    if (after.terrain_name !== params.terrain_name) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.terrain name bind mismatch");
    }
    if (params.op === "connect") {
      if (after.node_path !== params.node_path) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.terrain connect node_path bind mismatch");
      }
      const wantCells = Array.isArray(params.cells) ? params.cells.length : 0;
      if (typeof after.cell_count !== "number" || (wantCells > 0 && after.cell_count !== wantCells)) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.terrain connect cell count mismatch");
      }
    }
  }
  if (actionId === "tilemap.layer") {
    if (after.enabled !== params.enabled && params.op !== "remove" && params.op !== "reorder") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.layer enabled bind mismatch");
    }
    if (after.class_name !== "TileMapLayer" && params.op !== "remove") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.layer class bind mismatch");
    }
  }
  if (actionId === "tilemap.cell") {
    const chunk = Array.isArray(params.cells) ? params.cells : [];
    if (chunk.length > 0) {
      if (after.cell_count !== chunk.length && after.cell_count !== chunk.length + 1) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.cell chunk count mismatch");
      }
    } else if (after.x !== params.x || after.y !== params.y) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.cell coord bind mismatch");
    }
    if (params.erase !== true && chunk.length === 0) {
      if (after.source_id !== params.source_id) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.cell source_id bind mismatch");
      }
      if (after.atlas_x !== params.atlas_x || after.atlas_y !== params.atlas_y) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.cell atlas bind mismatch");
      }
    }
    if (after.readback_equals !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.cell readback did not equal set");
    }
  }
  if (actionId === "tilemap.fill") {
    const w = typeof params.w === "number" ? params.w : -1;
    const h = typeof params.h === "number" ? params.h : -1;
    if (after.x !== params.x || after.y !== params.y || after.w !== params.w || after.h !== params.h) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.fill region bind mismatch");
    }
    if (after.source_id !== params.source_id) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.fill source_id bind mismatch");
    }
    if (after.cell_count !== w * h) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.fill cell count mismatch");
    }
    if (after.compact !== true && w * h > 16) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.fill must use a compact after payload");
    }
    if (after.readback_equals !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.fill readback did not equal set");
    }
  }
  if (actionId === "tilemap.stamp") {
    if (after.x !== params.x || after.y !== params.y) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.stamp origin bind mismatch");
    }
    if (after.pattern !== params.pattern) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.stamp pattern bind mismatch");
    }
    if (typeof after.cell_count !== "number" || after.cell_count < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.stamp missing cell_count");
    }
    if (after.readback_equals !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "tilemap.stamp readback did not equal set");
    }
  }
  return undefined;
}

function animationApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isAnimationApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "animation missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "animation missing after readback");
  }
  if (Array.isArray(after.keys) && after.keys.length > 100) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "animation after dumped more than one page of keys");
  }
  if (after.node_path !== params.node_path) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "animation node_path bind mismatch");
  }
  if (actionId === "animation.library") {
    if (after.library !== params.library) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation library name bind mismatch");
    }
    if (params.op !== "remove" && after.has_library !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation library missing after add");
    }
  }
  if (actionId === "animation.animation") {
    if (after.name !== params.name && after.animation !== params.name) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation name bind mismatch");
    }
    if (after.has_animation !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation named clip missing after add");
    }
  }
  if (actionId === "animation.track") {
    if (typeof after.track !== "number" || after.track < 0) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation track index bind mismatch");
    }
    if (after.track_path !== params.track_path) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation track path bind mismatch");
    }
    if (after.animation !== params.animation) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation name bind mismatch");
    }
  }
  if (actionId === "animation.key") {
    if (after.track !== params.track) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation track index bind mismatch");
    }
    if (after.animation !== params.animation) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation name bind mismatch");
    }
    if (typeof after.time_sec !== "number" || after.time_sec !== params.time_sec) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation key time bind mismatch");
    }
    const batch = Array.isArray(params.keys) ? params.keys.length : 1;
    if (typeof after.key_count !== "number" || after.key_count < batch) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation key count mismatch");
    }
    if (after.readback_equals !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation key readback did not equal set");
    }
  }
  if (actionId === "animation.sprite_frames") {
    if (after.animation !== params.animation) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation name bind mismatch");
    }
    if (typeof after.frame_count !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation sprite_frames missing frame_count");
    }
    const wantFrames = Array.isArray(params.frames) ? params.frames.length : 0;
    if (wantFrames > 0 && after.frame_count < wantFrames) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation sprite_frames frame count mismatch");
    }
    if (after.has_animation !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation sprite_frames clip missing");
    }
  }
  if (actionId === "animation.state_machine") {
    if (after.from !== params.from || after.to !== params.to) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation state_machine from/to bind mismatch");
    }
    if (after.has_transition !== true && params.op !== "add_node") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation state_machine transition missing");
    }
    if (typeof params.condition === "string" && params.condition && after.condition !== params.condition) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "animation state_machine condition bind mismatch");
    }
  }
  return undefined;
}

function uiApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isUiApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "ui missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "ui missing after readback");
  }
  if (after.node_path !== params.node_path) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "ui node_path bind mismatch");
  }
  if (after.invented_box === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "ui invented a bounds box");
  }
  if (actionId === "ui.control") {
    if (after.preset !== params.preset) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui control preset bind mismatch");
    }
    if (after.container_child_anchors_acked === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "anchors on Container child must not paper-ACK");
    }
    for (const key of [
      "offset_left",
      "offset_top",
      "offset_right",
      "offset_bottom",
      "anchor_left",
      "anchor_top",
      "anchor_right",
      "anchor_bottom",
    ]) {
      if (typeof after[key] !== "number") {
        return errorResult(result.command_id, E.E_UNVERIFIED, `ui control missing ${key} readback`);
      }
    }
    if (!isRecord(after.size) || !isRecord(after.position) || !isRecord(after.rect)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui control missing size/position/rect readback");
    }
  }
  if (actionId === "ui.theme") {
    if (after.theme !== params.theme) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui theme path bind mismatch");
    }
    if (after.theme_assigned !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui theme not assigned on Control");
    }
    if (typeof params.theme === "string" && params.theme.includes("::")) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "refusing RAM-only Theme durable ACK");
    }
  }
  if (actionId === "ui.layout") {
    if (after.separation !== params.separation) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui layout separation bind mismatch");
    }
    if (after.queue_sort !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui layout missing queue_sort");
    }
    if (after.container_child_anchors_acked === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "anchors on Container child must not paper-ACK");
    }
    if (!Array.isArray(after.rects)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui layout missing computed rects");
    }
  }
  if (actionId === "ui.anchor") {
    if (after.container_child_anchors_acked === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "anchors on Container child must not paper-ACK");
    }
    for (const key of [
      "anchor_left",
      "anchor_top",
      "anchor_right",
      "anchor_bottom",
      "offset_left",
      "offset_top",
      "offset_right",
      "offset_bottom",
    ]) {
      if (typeof after[key] !== "number") {
        return errorResult(result.command_id, E.E_UNVERIFIED, `ui anchor missing ${key} readback`);
      }
    }
    if (after.anchor_left !== params.anchor_left || after.anchor_top !== params.anchor_top) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ui anchor left/top bind mismatch");
    }
  }
  return undefined;
}

function physicsApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isPhysicsApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "physics missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "physics missing after readback");
  }
  if (after.node_path !== params.node_path) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "physics node_path bind mismatch");
  }
  if (after.invented_box === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "physics invented a bounds box");
  }
  if (typeof after.class_name !== "string" || after.class_name.length < 1) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "physics class bind mismatch");
  }
  for (const key of ["material", "shape_path", "navpoly_path", "path"] as const) {
    const raw = params[key];
    if (typeof raw === "string" && raw.includes("::")) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "refusing RAM-only physics durable ACK");
    }
  }
  if (after.durable === true && (typeof after.disk_hash !== "string" || after.disk_hash.length < 16)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "refusing RAM-only physics durable ACK");
  }
  if (actionId === "physics.body") {
    const allowed = ["CharacterBody2D", "RigidBody2D", "Area2D", "StaticBody2D"];
    if (!allowed.includes(after.class_name)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics class bind mismatch");
    }
  }
  if (actionId === "physics.shape") {
    if (typeof after.shape_class !== "string" || after.shape_class.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics shape class bind mismatch");
    }
    if (!isRecord(after.geometry)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics missing explicit geometry");
    }
    if (params.shape === "rectangle" && !isRecord(after.geometry.size)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics rectangle size bind mismatch");
    }
    if (params.shape === "circle" && typeof after.geometry.radius !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics circle radius bind mismatch");
    }
    if (
      params.shape === "capsule" &&
      (typeof after.geometry.radius !== "number" || typeof after.geometry.height !== "number")
    ) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics capsule geometry bind mismatch");
    }
    if (
      (params.shape === "convex" || params.shape === "polygon") &&
      !Array.isArray(after.geometry.points)
    ) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics polygon points bind mismatch");
    }
  }
  if (actionId === "physics.layers") {
    if (typeof after.collision_layer !== "number" || typeof after.collision_mask !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics layer/mask bind mismatch");
    }
    if (!isRecord(after.layer_values) || !isRecord(after.mask_values)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics missing per-layer values");
    }
    if (typeof params.collision_layer === "number" && after.collision_layer !== params.collision_layer) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics collision_layer bind mismatch");
    }
    if (typeof params.collision_mask === "number" && after.collision_mask !== params.collision_mask) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics collision_mask bind mismatch");
    }
  }
  if (actionId === "physics.nav_region") {
    if (typeof after.outline_count !== "number" || typeof after.polygon_count !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics nav counts bind mismatch");
    }
    if (after.is_baking === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics nav bake still running");
    }
  }
  if (actionId === "physics.nav_agent") {
    if (!isRecord(after.target_position)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics nav agent target bind mismatch");
    }
    const want = isRecord(params.target_position) ? params.target_position : {};
    if (
      typeof want.x === "number" &&
      typeof after.target_position.x === "number" &&
      after.target_position.x !== want.x
    ) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics nav agent target bind mismatch");
    }
    if (
      typeof want.y === "number" &&
      typeof after.target_position.y === "number" &&
      after.target_position.y !== want.y
    ) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "physics nav agent target bind mismatch");
    }
  }
  return undefined;
}

function audioApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isAudioApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "audio missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "audio missing after readback");
  }
  if (after.invented_box === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "audio invented a bounds box");
  }
  for (const key of ["stream", "layout", "path"] as const) {
    const raw = params[key];
    if (typeof raw === "string" && raw.includes("::")) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "refusing RAM-only audio durable ACK");
    }
  }
  if (after.durable === true && (typeof after.disk_hash !== "string" || after.disk_hash.length < 16)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "refusing RAM-only audio durable ACK");
  }
  if (actionId === "audio.player") {
    if (after.node_path !== params.node_path) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio node_path bind mismatch");
    }
    if (after.stream_class !== "AudioStreamGenerator") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio stream class bind mismatch");
    }
    if (typeof after.bus !== "string" || after.bus.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio bus bind mismatch");
    }
    if (typeof params.bus === "string" && after.bus !== params.bus) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio bus bind mismatch");
    }
    if (typeof after.volume_db !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio volume_db bind mismatch");
    }
    if (typeof params.volume_db === "number" && after.volume_db !== params.volume_db) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio volume_db bind mismatch");
    }
    if (after.heard === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio player must not paper-ACK heard SFX");
    }
  }
  if (actionId === "audio.bus") {
    if (typeof after.bus !== "string" || after.bus.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio bus bind mismatch");
    }
    if (typeof params.bus === "string" && after.bus !== params.bus) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio bus bind mismatch");
    }
    if (typeof params.mute === "boolean" && after.mute !== params.mute) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio bus mute bind mismatch");
    }
    if (typeof params.volume_db === "number" && after.volume_db !== params.volume_db) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "audio volume_db bind mismatch");
    }
  }
  return undefined;
}

function renderApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isRenderApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "render missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "render missing after readback");
  }
  if (after.node_path !== params.node_path) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "render node_path bind mismatch");
  }
  if (after.invented_box === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "render invented a bounds box");
  }
  for (const key of ["shader", "material", "process_material", "environment", "texture", "path"] as const) {
    const raw = params[key];
    if (typeof raw === "string" && raw.includes("::")) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "refusing RAM-only render durable ACK");
    }
  }
  if (after.durable === true && (typeof after.disk_hash !== "string" || after.disk_hash.length < 16)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "refusing RAM-only render durable ACK");
  }
  if (actionId === "render.shader") {
    if (typeof after.shader !== "string" || after.shader.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render shader path bind mismatch");
    }
    if (typeof params.shader === "string" && after.shader !== params.shader) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render shader path bind mismatch");
    }
    if (after.mode !== "MODE_CANVAS_ITEM" && after.mode !== 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render shader mode bind mismatch");
    }
    if (!Array.isArray(after.uniforms)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render shader missing uniform list");
    }
    if (typeof params.required_uniform === "string" && params.required_uniform) {
      const names = after.uniforms.map((item) =>
        isRecord(item) ? String(item.name ?? "") : String(item),
      );
      if (!names.includes(params.required_uniform)) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "render shader required uniform missing");
      }
    }
  }
  if (actionId === "render.particles") {
    if (typeof after.amount !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render particles amount bind mismatch");
    }
    if (typeof after.lifetime !== "number") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render particles lifetime bind mismatch");
    }
    if (typeof params.amount === "number" && after.amount !== params.amount) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render particles amount bind mismatch");
    }
    if (typeof params.lifetime === "number" && after.lifetime !== params.lifetime) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "render particles lifetime bind mismatch");
    }
  }
  return undefined;
}

function normalizeResPath(path: string): string {
  const trimmed = path.trim().replace(/\\/g, "/");
  if (!trimmed) {
    return "";
  }
  if (trimmed.startsWith("res://")) {
    return trimmed;
  }
  return `res://${trimmed.replace(/^\/+/, "")}`;
}

function playApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isPlayApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "play missing after readback");
  }
  if (after.tree_kind === "remote") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "play apply must label tree_kind=editor");
  }
  if (after.remote_tree === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "never claim editor tree is remote");
  }
  if (after.game_tree_source === "get_edited_scene_root") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "never return get_edited_scene_root as the game tree");
  }
  if (after.pid_source === "editor") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "refusing editor OS.get_process_id as play PID");
  }
  const wantPlaying = actionId !== "play.stop";
  if (after.playing !== wantPlaying) {
    return errorResult(
      result.command_id,
      E.E_UNVERIFIED,
      `play after.playing must be ${wantPlaying} for ${actionId}`,
    );
  }
  if (after.is_playing_scene !== wantPlaying) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "play is_playing_scene bind mismatch");
  }
  if (wantPlaying && after.headless_play === "unproven") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "refusing invented playing=true when headless_play=unproven");
  }
  if (wantPlaying) {
    const runId = typeof after.run_id === "string" ? after.run_id : "";
    if (!isUlid(runId)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "play missing run_id");
    }
    const wantScene = typeof params.scene === "string" ? normalizeResPath(params.scene) : "";
    const gotScene =
      typeof after.playing_scene === "string"
        ? normalizeResPath(after.playing_scene)
        : typeof after.scene === "string"
          ? normalizeResPath(after.scene)
          : "";
    if (wantScene && gotScene !== wantScene) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "get_playing_scene bind mismatch");
    }
    if (!gotScene) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "get_playing_scene bind mismatch");
    }
  }
  if (actionId === "play.debug" && after.debugger_attached !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "play.debug requires debugger session attached");
  }
  if (actionId === "play.start" && params.mode === "debug" && after.debugger_attached !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "play.start mode=debug requires debugger session attached");
  }
  if (actionId === "play.restart") {
    const runId = typeof after.run_id === "string" ? after.run_id : "";
    const prev = typeof after.previous_run_id === "string" ? after.previous_run_id : "";
    if (prev && prev === runId) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "play.restart must mint a new run_id");
    }
    if (after.previous_alive === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "play.restart left the previous run alive");
    }
  }
  return undefined;
}

function inputApplyOk(
  result: PluginCommandResult,
  actionId: string,
): PluginCommandResult | undefined {
  if (!isInputApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "input missing after readback");
  }
  if (after.send_input === true || after.rpa === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "refusing desktop SendInput/RPA input ACK");
  }
  if (after.playing !== true || after.is_playing_scene !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "input ACK requires proven Play");
  }
  const runId = typeof after.run_id === "string" ? after.run_id : "";
  if (!isUlid(runId)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "input missing Play run_id");
  }
  if (after.source !== "hh_agent_runtime") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "input reply is not from Play hh_agent_runtime");
  }
  if (after.injected !== true && after.released !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "Play process did not confirm injected input");
  }
  if (actionId !== "input.release_all" && after.seen !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "Play process _input did not see the event");
  }
  const scene =
    typeof after.playing_scene === "string"
      ? after.playing_scene
      : typeof after.scene === "string"
        ? after.scene
        : "";
  if (!scene) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "input missing get_playing_scene bind");
  }
  return undefined;
}

function runtimeApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isRuntimeApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "runtime freeze/step missing after readback");
  }
  if (after.editor_time_scale === true) {
    return errorResult(
      result.command_id,
      E.E_UNVERIFIED,
      "refusing editor-only Engine.time_scale paper freeze/step",
    );
  }
  if (after.playing !== true || after.is_playing_scene !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "freeze/step ACK requires proven Play");
  }
  const runId = typeof after.run_id === "string" ? after.run_id : "";
  if (!isUlid(runId)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "freeze/step missing Play run_id");
  }
  if (actionId === "runtime.screenshot" || actionId === "runtime.perf") {
    if (after.source !== "hh_agent_runtime") {
      return errorResult(
        result.command_id,
        E.E_UNVERIFIED,
        "screenshot/perf reply is not from Play hh_agent_runtime",
      );
    }
    if (after.dummy === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "refusing dummy screenshot/perf ACK");
    }
    if (actionId === "runtime.screenshot") {
      if (after.screenshot_artifact_present !== true) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "screenshot_artifact_present failed");
      }
      const path = typeof after.path === "string" ? after.path.replace(/\\/g, "/") : "";
      if (
        !path ||
        path.includes("..") ||
        (!path.includes(".hh-agent/") && !path.includes("r6w5/") && !path.includes("r6w6/"))
      ) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "screenshot path is not under project artifacts");
      }
      const bytes = after.bytes;
      if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 32) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "screenshot ACK requires a real captured file");
      }
    }
    if (actionId === "runtime.perf") {
      if (after.perf_counters_present !== true) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "perf_counters_present failed");
      }
      if (!isRecord(after.hardware_manifest)) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "perf ACK requires a hardware manifest");
      }
    }
    return undefined;
  }
  if (after.source !== "hh_agent_runtime") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "freeze/step reply is not from Play hh_agent_runtime");
  }
  if (actionId === "runtime.freeze") {
    if (after.frozen !== params.frozen) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "runtime_frozen_matches failed");
    }
    if (params.frozen === true && after.observed_frozen !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "Play fixture/probe did not observe freeze");
    }
    if (params.frozen === true && after.paused !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "Play tree was not paused");
    }
  }
  if (actionId === "runtime.step") {
    if (after.stepped !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "Play process did not confirm a step");
    }
    const advanced = after.frames_advanced;
    if (typeof advanced !== "number" || !Number.isInteger(advanced) || advanced < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "step ACK requires observed frames_advanced");
    }
    if (isRecord(params.until) && after.matched !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "step-until ACK requires matched predicate");
    }
  }
  return undefined;
}

function testPathOk(path: string): boolean {
  const p = path.replace(/\\/g, "/");
  if (!p || p.includes("..")) {
    return false;
  }
  return (
    p.includes("r6w6/") ||
    p.includes(".hh-agent/r6w6") ||
    p.includes("r6w7/") ||
    p.includes(".hh-agent/r6w7") ||
    p.includes("r7w6/") ||
    p.includes(".hh-agent/r7w6") ||
    p.endsWith(".hh-test.json") ||
    p.includes("/.hh-test.json")
  );
}

function testApplyOk(
  result: PluginCommandResult,
  actionId: string,
): PluginCommandResult | undefined {
  if (!isTestApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    const afterFail = result.after;
    if (isRecord(afterFail) && afterFail.status === "pass") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.run must not stamp pass on a failed ACK");
    }
    if (isRecord(afterFail) && afterFail.flaky === true && afterFail.status === "pass") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "flaky retry must not become pass");
    }
    return result;
  }
  const after = result.after;
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "test apply missing after readback");
  }
  if (actionId === "test.define") {
    const path = typeof after.path === "string" ? after.path : "";
    if (!testPathOk(path)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.define path is not under r6w6");
    }
    if (after.test_definition_saved !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test_definition_saved failed");
    }
    return undefined;
  }
  if (actionId === "test.baseline") {
    if (after.reviewed !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "baseline update requires explicit reviewed action");
    }
    if (after.invented === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "refusing invented baseline hash");
    }
    const hash = typeof after.hash === "string" ? after.hash : "";
    if (hash.length < 8) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "baseline_hash_saved failed");
    }
    return undefined;
  }
  if (actionId === "test.assert") {
    if (after.matched !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.assert ACK requires a matched state assertion");
    }
    if (after.source !== "hh_agent_runtime") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.assert must come from Play hh_agent_runtime");
    }
    return undefined;
  }
  if (actionId === "test.repair") {
    const root = typeof after.root_cause === "string" ? after.root_cause : "";
    const artifact = typeof after.artifact_uri === "string" ? after.artifact_uri : "";
    if (root.length < 4) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.repair requires a root_cause string");
    }
    if (!testPathOk(artifact)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.repair artifact must stay under r6w7");
    }
    if (after.edited_test === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.repair must not edit the official test");
    }
    if (after.false_pass === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "test.repair refused a false pass");
    }
    if (result.ok) {
      if (after.retest_status !== "pass" || after.status === "fail") {
        return errorResult(
          result.command_id,
          E.E_UNVERIFIED,
          "test.repair ACK requires retest_status=pass",
        );
      }
    } else if (after.status === "pass" || after.retest_status === "pass") {
      return errorResult(
        result.command_id,
        E.E_UNVERIFIED,
        "test.repair must not stamp pass on a failed ACK",
      );
    }
    return undefined;
  }
  if (actionId !== "test.run") {
    return undefined;
  }
  if (after.status !== "pass") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "test.run ACK requires status=pass");
  }
  if (after.flaky === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "flaky retry must not become pass");
  }
  if (after.play_proven !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "test.run pass requires proven Play");
  }
  if (after.invented_hashes === true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "refusing invented test hashes");
  }
  const report = typeof after.report_path === "string" ? after.report_path : "";
  const html = typeof after.html_path === "string" ? after.html_path : "";
  if (!testPathOk(report) || !testPathOk(html)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "test.report must point at a real project file");
  }
  const index = after.evidence_index;
  if (!Array.isArray(index) || index.length < 1) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "test.run pass requires an evidence index with file URIs");
  }
  const hashes = after.hashes;
  if (!isRecord(hashes)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "test.run pass requires computed hashes");
  }
  return undefined;
}

function cameraApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isCameraApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "camera missing Agent UndoRedo name");
  }
  const after = result.after;
  if (!isRecord(after) || after.is_current !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "camera.make_current readback is not current");
  }
  if (after.node_path !== params.node_path || after.class_name !== "Camera2D") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "camera.make_current node bind mismatch");
  }
  return undefined;
}

function nodeIdentityOk(result: PluginCommandResult, actionId: string): PluginCommandResult | undefined {
  if (!result.ok) {
    return result;
  }
  const after = result.after;
  if (actionId === "node.remove") {
    if (!isRecord(after) || after.absent !== true || typeof after.path !== "string" || after.path.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "remove postcondition missing absent path");
    }
    if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "remove missing Agent UndoRedo name");
    }
    return undefined;
  }
  if (actionId === "node.undo" || actionId === "node.redo") {
    if (!isRecord(after) || typeof after.fingerprint !== "string" || after.fingerprint.length < 8) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "history op missing fingerprint readback");
    }
    return undefined;
  }
  if (actionId === "node.make_local") {
    if (!isRecord(after) || after.instance_is_local !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "make_local missing instance_is_local");
    }
    if (typeof after.uid !== "string" || after.uid.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "make_local uid missing");
    }
    if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "make_local missing Agent UndoRedo name");
    }
    return undefined;
  }
  if (!nodeNeedsUidAfter(actionId)) {
    return undefined;
  }
  if (!isRecord(after)) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "node after-summary missing");
  }
  if (typeof after.uid !== "string" || after.uid.length < 1) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "node uid missing after plugin ACK");
  }
  if (typeof after.path !== "string" || after.path.length < 1) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "node tree path missing after plugin ACK");
  }
  if (typeof after.owner !== "string") {
    return errorResult(result.command_id, E.E_UNVERIFIED, "node owner missing after plugin ACK");
  }
  if (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: ")) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "mutation missing Agent UndoRedo name");
  }
  return undefined;
}

function resourceApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (
    !isResourceApply(actionId) &&
    !isSignalApply(actionId) &&
    !isAssetRefApply(actionId) &&
    !isAssetIngestApply(actionId)
  ) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const after = result.after;
  const needsUndo =
    actionId === "resource.assign" ||
    actionId === "resource.edit" ||
    actionId === "signal.connect" ||
    actionId === "signal.disconnect";
  if (needsUndo && (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: "))) {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} missing Agent UndoRedo name`);
  }
  if (actionId === "resource.assign") {
    if (!isRecord(after) || after.readback_equals !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "resource.assign readback failed");
    }
    const want = typeof params.resource === "string" ? params.resource : "";
    const got = typeof after.path === "string" ? after.path : "";
    if (want && got && want !== got && !got.includes("::") && !got.endsWith(want)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "resource.assign path mismatch");
    }
    return undefined;
  }
  if (actionId === "resource.edit") {
    if (!isRecord(after) || after.readback_equals !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "resource.edit readback failed");
    }
    return undefined;
  }
  if (actionId === "resource.create") {
    if (!isRecord(after)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "resource.create missing after");
    }
    if (after.builtin === true) {
      return undefined;
    }
    if (typeof after.path !== "string" || after.path.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "resource.create missing path");
    }
    if (typeof after.uid !== "string" || after.uid.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "resource.create missing uid");
    }
    return undefined;
  }
  if (actionId === "resource.duplicate") {
    if (!isRecord(after) || typeof after.uid !== "string" || after.uid.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "duplicate uid missing");
    }
    if (typeof after.source_uid === "string" && after.source_uid === after.uid) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "duplicate uid not distinct");
    }
    return undefined;
  }
  if (actionId === "resource.save") {
    if (!isRecord(after) || typeof after.disk_hash !== "string" || after.disk_hash.length < 16) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "resource.save missing disk hash");
    }
    return undefined;
  }
  if (actionId === "signal.connect") {
    if (!isRecord(after) || after.connected !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "signal.connect missing connection readback");
    }
    return undefined;
  }
  if (actionId === "signal.disconnect") {
    if (!isRecord(after) || after.connected === true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "signal.disconnect still connected");
    }
    return undefined;
  }
  if (actionId === "asset.move" || actionId === "asset.rename") {
    if (!isRecord(after) || after.old_path_absent !== true || typeof after.path !== "string") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "move/rename missing dest path");
    }
    if (typeof after.uid !== "string" || after.uid.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "move/rename uid missing");
    }
    return undefined;
  }
  if (actionId === "asset.delete") {
    if (!isRecord(after) || after.absent !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "delete missing absent readback");
    }
    if (after.quarantined !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "delete missing quarantine stamp");
    }
    return undefined;
  }
  if (actionId === "asset.import" || actionId === "asset.reimport") {
    if (!isRecord(after) || typeof after.path !== "string" || after.path.length < 1) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "import missing dest path");
    }
    if (after.import_sidecar !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "import sidecar missing after wait");
    }
    if (after.resource_exists !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "ResourceLoader.exists was false after wait");
    }
    if (typeof after.disk_hash !== "string" || after.disk_hash.length < 16) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "import missing disk hash");
    }
    if (typeof after.job !== "string" || after.job !== result.command_id) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "late import must not commit an old job");
    }
    return undefined;
  }
  return undefined;
}

function scriptApplyOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
): PluginCommandResult | undefined {
  if (!isScriptApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const after = result.after;
  const needsUndo = actionId === "script.attach" || actionId === "script.detach";
  if (needsUndo && (typeof result.undo_action !== "string" || !result.undo_action.startsWith("Agent: "))) {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} missing Agent UndoRedo name`);
  }
  if (actionId === "script.write" || actionId === "script.patch") {
    if (actionId === "script.patch" && params.buffer_only === true) {
      if (!isRecord(after) || after.buffer_only !== true) {
        return errorResult(result.command_id, E.E_UNVERIFIED, "buffer_only patch missing buffer readback");
      }
      return undefined;
    }
    if (!isRecord(after) || typeof after.disk_hash !== "string" || after.disk_hash.length < 16) {
      return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} missing disk hash`);
    }
    const want = typeof params.path === "string" ? params.path : "";
    const got = typeof after.path === "string" ? after.path : "";
    if (want && got && want !== got) {
      return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} path mismatch`);
    }
    return undefined;
  }
  if (actionId === "script.attach") {
    if (!isRecord(after) || after.readback_equals !== true) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "script.attach readback failed");
    }
    const want = typeof params.path === "string" ? params.path : "";
    const got = typeof after.path === "string" ? after.path : "";
    if (want && got && want !== got) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "script.attach path mismatch");
    }
    return undefined;
  }
  if (actionId === "script.detach") {
    if (!isRecord(after) || after.attached === true || (typeof after.path === "string" && after.path.length > 0)) {
      return errorResult(result.command_id, E.E_UNVERIFIED, "script.detach still attached");
    }
    return undefined;
  }
  if (actionId === "script.rename") {
    if (!isRecord(after) || after.old_path_absent !== true || typeof after.path !== "string") {
      return errorResult(result.command_id, E.E_UNVERIFIED, "script.rename missing dest path");
    }
    return undefined;
  }
  return undefined;
}

function projectSettingsApplyOk(
  result: PluginCommandResult,
  actionId: string,
  projectRoot: string,
): PluginCommandResult | undefined {
  if (!isProjectSettingsApply(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const after = result.after;
  if (!isRecord(after) || after.readback_equals !== true) {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} disk parse readback failed`);
  }
  const source = after.disk_source === "project.binary" ? "project.binary" : "project.godot";
  if (after.disk_source !== "project.godot" && after.disk_source !== "project.binary") {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} missing project file source`);
  }
  if (typeof after.disk_hash !== "string" || after.disk_hash.length < 16) {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} missing project disk hash`);
  }
  if (!projectRoot) {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} missing project root for disk hash`);
  }
  const abs = path.join(projectRoot, source);
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} project file missing after save`, source);
  }
  const disk = contentHash(abs);
  if (!disk || disk === "missing" || disk !== after.disk_hash) {
    return errorResult(result.command_id, E.E_UNVERIFIED, `${actionId} project disk hash mismatch`, source);
  }
  return undefined;
}

function durableDiskOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
  projectRoot: string,
): PluginCommandResult | undefined {
  if (!mutationNeedsDiskHash(actionId, params)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const rawPath = durableResPath(actionId, params, isRecord(result.after) ? result.after : undefined);
  if (!rawPath) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "durable save missing path", "params.path");
  }
  const jailed = jailProjectPath(projectRoot, rawPath, { forWrite: true });
  if (!jailed.ok) {
    return errorResult(result.command_id, jailed.error.code, jailed.error.message, jailed.error.path);
  }
  if (!fs.existsSync(jailed.abs) || !fs.statSync(jailed.abs).isFile()) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "durable save file missing after plugin ACK", rawPath);
  }
  if (
    (actionId === "asset.import" || actionId === "asset.reimport") &&
    (!fs.existsSync(`${jailed.abs}.import`) || !fs.statSync(`${jailed.abs}.import`).isFile())
  ) {
    return errorResult(result.command_id, E.E_UNVERIFIED, "durable .import sidecar missing after wait", rawPath);
  }
  const disk = contentHash(jailed.abs);
  const reported = isRecord(result.after) && typeof result.after.disk_hash === "string" ? result.after.disk_hash : "";
  if (!reported || reported === "missing" || reported !== disk) {
    return errorResult(
      result.command_id,
      E.E_UNVERIFIED,
      "durable save disk hash missing or mismatched",
      rawPath,
    );
  }
  return undefined;
}

function settleBlocked(
  ledger: CommandLedger,
  row: CommandRow,
  envelope: Record<string, unknown>,
  bound: LedgerBound,
  runtime: LedgerRuntime,
  classified: Extract<Classified, { kind: "blocked" }>,
): PluginCommandResult {
  const def = getAction(classified.actionId);
  const fields = envelopeFields(envelope);
  runtime.policy?.pause.registerJob(row.command_id, { cancellable: true });
  const pausedJob = runtime.policy?.pause.job(row.command_id);
  if (pausedJob?.cancelled || (runtime.policy && !runtime.policy.pause.allowsSideEffect(classified.sideEffect))) {
    runtime.policy?.pause.finishJob(row.command_id);
    const result = errorResult(row.command_id, E.E_PAUSED, "mutation gate is paused", "pause");
    persistResult(row, result);
    saveState(ledger, row, "failed");
    return result;
  }
  const gated = runMutationGate({
    commandId: row.command_id,
    sideEffect: classified.sideEffect,
    actionId: classified.actionId,
    checkpointRequired: def?.checkpoint_required === true,
    policy: normalizePolicy(bound.policy),
    params: fields.params,
    requestHash: row.request_hash,
    ...(runtime.policy ? { services: runtime.policy } : {}),
  });
  runtime.policy?.pause.finishJob(row.command_id);
  if (!gated.ok) {
    const result = errorResult(
      row.command_id,
      gated.error.code,
      gated.error.message,
      gated.error.path,
    );
    persistResult(row, result);
    row.after_summary = JSON.stringify({ rejected: gated.error.code });
    saveState(ledger, row, "failed");
    return result;
  }
  const message = gated.checkpoint
    ? `not dispatched; checkpoint ${gated.checkpoint.checkpoint_id} recorded`
    : classified.result.error?.message || "not dispatched";
  const result = unverifiedResult(row.command_id, message);
  persistResult(row, result);
  row.after_summary = JSON.stringify({
    rejected: result.error?.code ?? E.E_UNVERIFIED,
    ...(gated.checkpoint
      ? {
          checkpoint_id: gated.checkpoint.checkpoint_id,
          checkpoint_dir: gated.checkpoint.dir,
          manifest_path: gated.checkpoint.manifest_path,
          hard_delete_blocked: gated.checkpoint.manifest.hard_delete_blocked,
        }
      : {}),
  });
  if (gated.checkpoint) {
    row.evidence_json = JSON.stringify([gated.checkpoint.manifest_path]);
    ledger.addCheckpoint(
      gated.checkpoint.checkpoint_id,
      [gated.checkpoint.manifest_path],
      row.command_id,
    );
  }
  saveState(ledger, row, "failed");
  return result;
}

function handlePluginFault(runtime: LedgerRuntime, err: unknown): void {
  if (err instanceof LedgerPluginDeath) {
    runtime.killPlugin?.();
    return;
  }
  throw err;
}

async function applyNoopOnce(
  ledger: CommandLedger,
  row: CommandRow,
  envelope: Record<string, unknown>,
  runtime: LedgerRuntime,
  timeoutMs: number,
): Promise<PluginCommandResult> {
  if (row.apply_count > 0 || row.dispatch_attempted > 0) {
    return markUncertain(ledger, row, "already attempted; refusing blind replay");
  }
  if (!isNoopEnvelope(envelope)) {
    return markUncertain(ledger, row, "only hh.plugin/noop may apply");
  }
  if (!runtime.pluginConnected()) {
    const result = unverifiedResult(row.command_id, "no plugin");
    persistResult(row, result);
    saveState(ledger, row, "failed");
    return result;
  }
  runtime.policy?.pause.registerJob(row.command_id, { atomic: true });
  try {
    saveState(ledger, row, "applying", {
      before_summary: '{"kind":"noop"}',
      side_effect: "read",
      action_id: "hh.plugin/noop",
    });
    try {
      maybeFault("applying", row.command_id);
    } catch (err) {
      handlePluginFault(runtime, err);
    }
    if (!runtime.pluginConnected()) {
      return unverifiedResult(row.command_id, "no plugin");
    }
    row.dispatch_attempted = 1;
    row.updated_at = nowIso();
    ledger.save(row);
    maybeCrashAfterDispatchAttempt(row.command_id);
    let result: PluginCommandResult;
    try {
      result = await runtime.dispatch(envelope, timeoutMs);
    } catch (err) {
      if (err instanceof LedgerPluginDeath) {
        runtime.killPlugin?.();
      }
      return markUncertain(
        ledger,
        row,
        "dispatch interrupted; postcondition unknown",
      );
    }
    row.apply_count = 1;
    persistResult(row, result);
    row.after_summary = JSON.stringify({
      kind: "noop",
      checks: result.postcondition.checks,
    });
    saveState(ledger, row, "applied_volatile");
    if (!result.ok || !isNoopVerified(result.postcondition)) {
      const failed = result.ok
        ? errorResult(row.command_id, E.E_UNVERIFIED, "noop postcondition failed")
        : result;
      persistResult(row, failed);
      saveState(ledger, row, "failed");
      return failed;
    }
    saveState(ledger, row, "verified");
    try {
      maybeFault("verified", row.command_id);
    } catch (err) {
      handlePluginFault(runtime, err);
    }
    saveState(ledger, row, "committed_durable");
    return result;
  } finally {
    runtime.policy?.pause.finishJob(row.command_id);
  }
}

async function applyReadOnce(
  ledger: CommandLedger,
  row: CommandRow,
  envelope: Record<string, unknown>,
  bound: LedgerBound,
  runtime: LedgerRuntime,
  classified: Extract<Classified, { kind: "forward" }>,
): Promise<PluginCommandResult> {
  if (row.apply_count > 0 || row.dispatch_attempted > 0) {
    return markUncertain(ledger, row, "already attempted; refusing blind replay");
  }
  const fields = envelopeFields(envelope);
  runtime.policy?.pause.registerJob(row.command_id, { atomic: true });
  try {
    const gated = runMutationGate({
      commandId: row.command_id,
      sideEffect: classified.sideEffect,
      actionId: classified.actionId,
      checkpointRequired: false,
      policy: normalizePolicy(bound.policy),
      params: fields.params,
      requestHash: row.request_hash,
      ...(runtime.policy ? { services: runtime.policy } : {}),
    });
    if (!gated.ok) {
      const result = errorResult(
        row.command_id,
        gated.error.code,
        gated.error.message,
        gated.error.path,
      );
      persistResult(row, result);
      saveState(ledger, row, "failed");
      return result;
    }
    saveState(ledger, row, "applying", {
      before_summary: JSON.stringify({ kind: "read", action_id: classified.actionId }),
      side_effect: classified.sideEffect,
      action_id: classified.actionId,
    });
    const projectRoot = runtime.projectRoot ?? runtime.policy?.projectRoot ?? "";
    const sidecarOnly = isSidecarOnlyAction(classified.actionId, fields.params);
    let result: PluginCommandResult | undefined;
    if (sidecarOnly || !runtime.pluginConnected()) {
      result = trySidecarRead({
        actionId: classified.actionId,
        commandId: row.command_id,
        params: fields.params,
        projectRoot,
        ...(runtime.policy?.pause ? { pause: runtime.policy.pause } : {}),
      });
    }
    if (!result && runtime.pluginConnected()) {
      row.dispatch_attempted = 1;
      row.updated_at = nowIso();
      ledger.save(row);
      try {
        result = await runtime.dispatch(envelope, classified.timeoutMs);
      } catch (err) {
        if (err instanceof LedgerPluginDeath) {
          runtime.killPlugin?.();
        }
        return markUncertain(ledger, row, "dispatch interrupted; postcondition unknown");
      }
    }
    if (!result && !runtime.pluginConnected()) {
      result = unverifiedResult(row.command_id, "no plugin");
    }
    if (!result) {
      result = unverifiedResult(row.command_id, "no read adapter");
    }
    row.apply_count = 1;
    persistResult(row, result);
    row.after_summary = JSON.stringify({
      kind: "read",
      action_id: classified.actionId,
      checks: result.postcondition.checks,
    });
    saveState(ledger, row, "applied_volatile");
    if (!result.ok) {
      saveState(ledger, row, "failed");
      return result;
    }
    if (!isReadVerified(result.postcondition, classified.actionId)) {
      const failed = unverifiedResult(row.command_id, "read postcondition failed");
      persistResult(row, failed);
      saveState(ledger, row, "failed");
      return failed;
    }
    saveState(ledger, row, "verified");
    saveState(ledger, row, "committed_durable");
    return result;
  } finally {
    runtime.policy?.pause.finishJob(row.command_id);
  }
}

async function applyMutateOnce(
  ledger: CommandLedger,
  row: CommandRow,
  envelope: Record<string, unknown>,
  bound: LedgerBound,
  runtime: LedgerRuntime,
  classified: Extract<Classified, { kind: "mutate" }>,
): Promise<PluginCommandResult> {
  if (row.apply_count > 0 || row.dispatch_attempted > 0) {
    return markUncertain(ledger, row, "already attempted; refusing blind replay");
  }
  if (isNoopEnvelope(envelope)) {
    return markUncertain(ledger, row, "noop cannot use scene mutate apply");
  }
  if (
    !isProvenEditorApply(classified.actionId) &&
    !isSidecarMutateApply(classified.actionId) &&
    !isPlayApply(classified.actionId) &&
    !isInputApply(classified.actionId) &&
    !isRuntimeApply(classified.actionId) &&
    !isTestApply(classified.actionId) &&
    !isOrchestratorApply(classified.actionId) &&
    !isExportApply(classified.actionId) &&
    !(classified.actionId === "editor.pause" && !runtime.pluginConnected())
  ) {
    return markUncertain(ledger, row, "only proven editor apply verbs may apply");
  }
  const fields = envelopeFields(envelope);
  runtime.policy?.pause.registerJob(row.command_id, { atomic: true });
  try {
    const def = getAction(classified.actionId);
    const gated = runMutationGate({
      commandId: row.command_id,
      sideEffect: classified.sideEffect,
      actionId: classified.actionId,
      checkpointRequired: def?.checkpoint_required === true,
      policy: normalizePolicy(bound.policy),
      params: fields.params,
      requestHash: row.request_hash,
      ...(runtime.policy ? { services: runtime.policy } : {}),
    });
    if (!gated.ok) {
      const result = errorResult(
        row.command_id,
        gated.error.code,
        gated.error.message,
        gated.error.path,
      );
      persistResult(row, result);
      saveState(ledger, row, "failed");
      return result;
    }
    const projectRoot = runtime.projectRoot ?? runtime.policy?.projectRoot ?? "";
    if (classified.actionId === "editor.pause" && !runtime.pluginConnected()) {
      return await finishSidecarMutate(
        ledger,
        row,
        classified.actionId,
        fields.params,
        projectRoot,
        gated,
        runtime.policy,
      );
    }
    if (
      isSidecarMutateApply(classified.actionId) &&
      !(classified.actionId === "job.schedule" && runtime.pluginConnected())
    ) {
      return await finishSidecarMutate(
        ledger,
        row,
        classified.actionId,
        fields.params,
        projectRoot,
        gated,
        runtime.policy,
      );
    }
    if (isOrchestratorApply(classified.actionId) && !runtime.pluginConnected()) {
      return finishSidecarOrchestrator(
        ledger,
        row,
        classified.actionId,
        fields.params,
        projectRoot,
        gated,
        runtime.policy,
      );
    }
    if (isExportApply(classified.actionId) && !runtime.pluginConnected()) {
      return finishSidecarExport(
        ledger,
        row,
        classified.actionId,
        fields.params,
        projectRoot,
        gated,
        runtime.policy,
      );
    }
    if (!runtime.pluginConnected()) {
      const result = unverifiedResult(row.command_id, "no plugin");
      persistResult(row, result);
      saveState(ledger, row, "failed");
      return result;
    }
    saveState(ledger, row, "applying", {
      before_summary: JSON.stringify({
        kind: isTransactionApply(classified.actionId) ? "transaction" : "scene",
        action_id: classified.actionId,
        ...(gated.checkpoint
          ? { checkpoint_id: gated.checkpoint.checkpoint_id }
          : {}),
      }),
      side_effect: classified.sideEffect,
      action_id: classified.actionId,
    });
    row.dispatch_attempted = 1;
    row.updated_at = nowIso();
    ledger.save(row);
    maybeCrashAfterDispatchAttempt(row.command_id);
    let result: PluginCommandResult;
    try {
      result = await runtime.dispatch(envelope, classified.timeoutMs);
    } catch (err) {
      if (err instanceof LedgerPluginDeath) {
        runtime.killPlugin?.();
      }
      if (gated.checkpoint) {
        const recovery = compensateFromManifest(gated.checkpoint.manifest_path);
        const uncertain = errorResult(
          row.command_id,
          E.E_UNCERTAIN,
          "dispatch interrupted; postcondition unknown; checkpoint restore attempted",
        );
        mergeAfter(uncertain, { ...checkpointEvidence(gated.checkpoint), recovery });
        persistResult(row, uncertain);
        row.evidence_json = JSON.stringify([gated.checkpoint.manifest_path]);
        ledger.addCheckpoint(
          gated.checkpoint.checkpoint_id,
          [gated.checkpoint.manifest_path],
          row.command_id,
        );
        saveState(ledger, row, "uncertain");
        return uncertain;
      }
      return markUncertain(ledger, row, "dispatch interrupted; postcondition unknown");
    }
    if (gated.checkpoint) {
      mergeAfter(result, checkpointEvidence(gated.checkpoint));
      if (!result.ok && (result.changed === true || isTransactionApply(classified.actionId))) {
        const recovery = compensateFromManifest(gated.checkpoint.manifest_path);
        mergeAfter(result, { recovery });
      }
    }
    row.apply_count = 1;
    persistResult(row, result);
    row.after_summary = JSON.stringify({
      kind: isTransactionApply(classified.actionId)
        ? "transaction"
        : isPropertyApply(classified.actionId) || isCanvasApply(classified.actionId)
          ? "property"
          : isCameraApply(classified.actionId)
            ? "camera"
          : isTilemapApply(classified.actionId)
            ? "tilemap"
          : isAnimationApply(classified.actionId)
            ? "animation"
          : isUiApply(classified.actionId)
            ? "ui"
          : isPhysicsApply(classified.actionId)
            ? "physics"
          : isAudioApply(classified.actionId)
            ? "audio"
          : isRenderApply(classified.actionId)
            ? "render"
          : isResourceApply(classified.actionId) ||
              isAssetRefApply(classified.actionId) ||
              isAssetIngestApply(classified.actionId)
            ? "resource"
            : isSignalApply(classified.actionId)
              ? "signal"
              : isScriptApply(classified.actionId)
                ? "script"
                : isSceneLifecycleApply(classified.actionId)
                  ? "scene"
                  : isProjectSettingsApply(classified.actionId)
                    ? "project"
                    : isPlayApply(classified.actionId)
                      ? "play"
                    : isInputApply(classified.actionId)
                      ? "input"
                    : isRuntimeApply(classified.actionId)
                      ? "runtime"
                    : isTestApply(classified.actionId)
                      ? "test"
                    : isOrchestratorApply(classified.actionId)
                      ? "orchestrator"
                    : isExportApply(classified.actionId)
                      ? "export"
                    : "node",
      action_id: classified.actionId,
      checks: result.postcondition.checks,
      disk_hash: isRecord(result.after) ? result.after.disk_hash ?? "" : "",
      uid: isRecord(result.after) ? result.after.uid ?? "" : "",
      ...(gated.checkpoint ? { checkpoint_id: gated.checkpoint.checkpoint_id } : {}),
    });
    if (gated.checkpoint) {
      row.evidence_json = JSON.stringify([gated.checkpoint.manifest_path]);
      ledger.addCheckpoint(
        gated.checkpoint.checkpoint_id,
        [gated.checkpoint.manifest_path],
        row.command_id,
      );
    }
    saveState(ledger, row, "applied_volatile");
    if (!result.ok) {
      const testFailEarly = testApplyOk(result, classified.actionId);
      if (testFailEarly && testFailEarly !== result) {
        persistResult(row, testFailEarly);
        saveState(ledger, row, "failed");
        return testFailEarly;
      }
      saveState(ledger, row, "failed");
      return result;
    }
    if (!isReadVerified(result.postcondition, classified.actionId)) {
      const failed = unverifiedResult(row.command_id, "scene postcondition failed");
      if (gated.checkpoint && isTransactionApply(classified.actionId)) {
        mergeAfter(failed, {
          ...checkpointEvidence(gated.checkpoint),
          recovery: compensateFromManifest(gated.checkpoint.manifest_path),
        });
      }
      persistResult(row, failed);
      saveState(ledger, row, "failed");
      return failed;
    }
    const identityFail = nodeIdentityOk(result, classified.actionId);
    if (identityFail) {
      persistResult(row, identityFail);
      saveState(ledger, row, "failed");
      return identityFail;
    }
    const propertyFail = propertyApplyOk(result, classified.actionId, fields.params);
    if (propertyFail) {
      persistResult(row, propertyFail);
      saveState(ledger, row, "failed");
      return propertyFail;
    }
    const canvasFail = canvasApplyOk(result, classified.actionId, fields.params);
    if (canvasFail) {
      persistResult(row, canvasFail);
      saveState(ledger, row, "failed");
      return canvasFail;
    }
    const cameraFail = cameraApplyOk(result, classified.actionId, fields.params);
    if (cameraFail) {
      persistResult(row, cameraFail);
      saveState(ledger, row, "failed");
      return cameraFail;
    }
    const tilemapFail = tilemapApplyOk(result, classified.actionId, fields.params);
    if (tilemapFail) {
      persistResult(row, tilemapFail);
      saveState(ledger, row, "failed");
      return tilemapFail;
    }
    const animationFail = animationApplyOk(result, classified.actionId, fields.params);
    if (animationFail) {
      persistResult(row, animationFail);
      saveState(ledger, row, "failed");
      return animationFail;
    }
    const uiFail = uiApplyOk(result, classified.actionId, fields.params);
    if (uiFail) {
      persistResult(row, uiFail);
      saveState(ledger, row, "failed");
      return uiFail;
    }
    const physicsFail = physicsApplyOk(result, classified.actionId, fields.params);
    if (physicsFail) {
      persistResult(row, physicsFail);
      saveState(ledger, row, "failed");
      return physicsFail;
    }
    const audioFail = audioApplyOk(result, classified.actionId, fields.params);
    if (audioFail) {
      persistResult(row, audioFail);
      saveState(ledger, row, "failed");
      return audioFail;
    }
    const renderFail = renderApplyOk(result, classified.actionId, fields.params);
    if (renderFail) {
      persistResult(row, renderFail);
      saveState(ledger, row, "failed");
      return renderFail;
    }
    const playFail = playApplyOk(result, classified.actionId, fields.params);
    if (playFail) {
      persistResult(row, playFail);
      saveState(ledger, row, "failed");
      return playFail;
    }
    const inputFail = inputApplyOk(result, classified.actionId);
    if (inputFail) {
      persistResult(row, inputFail);
      saveState(ledger, row, "failed");
      return inputFail;
    }
    const runtimeFail = runtimeApplyOk(result, classified.actionId, fields.params);
    if (runtimeFail) {
      persistResult(row, runtimeFail);
      saveState(ledger, row, "failed");
      return runtimeFail;
    }
    const testFail = testApplyOk(result, classified.actionId);
    if (testFail) {
      persistResult(row, testFail);
      saveState(ledger, row, "failed");
      return testFail;
    }
    const resourceFail = resourceApplyOk(result, classified.actionId, fields.params);
    if (resourceFail) {
      persistResult(row, resourceFail);
      saveState(ledger, row, "failed");
      return resourceFail;
    }
    const scriptFail = scriptApplyOk(result, classified.actionId, fields.params);
    if (scriptFail) {
      persistResult(row, scriptFail);
      saveState(ledger, row, "failed");
      return scriptFail;
    }
    const txFail = isTransactionApply(classified.actionId) ? transactionApplyOk(result) : undefined;
    if (txFail) {
      if (gated.checkpoint) {
        mergeAfter(txFail, {
          ...checkpointEvidence(gated.checkpoint),
          recovery: compensateFromManifest(gated.checkpoint.manifest_path),
        });
      }
      persistResult(row, txFail);
      saveState(ledger, row, "failed");
      return txFail;
    }
    const settingsFail = projectSettingsApplyOk(result, classified.actionId, projectRoot);
    if (settingsFail) {
      persistResult(row, settingsFail);
      saveState(ledger, row, "failed");
      return settingsFail;
    }
    const diskFail = durableDiskOk(result, classified.actionId, fields.params, projectRoot);
    if (diskFail) {
      if (gated.checkpoint && isTransactionApply(classified.actionId)) {
        mergeAfter(diskFail, {
          ...checkpointEvidence(gated.checkpoint),
          recovery: compensateFromManifest(gated.checkpoint.manifest_path),
        });
      }
      persistResult(row, diskFail);
      saveState(ledger, row, "failed");
      return diskFail;
    }
    if (runtime.policy) {
      const rawPath = durableResPath(
        classified.actionId,
        fields.params,
        isRecord(result.after) ? result.after : undefined,
      );
      const shouldNote =
        mutationNeedsDiskHash(classified.actionId, fields.params) ||
        (classified.actionId === "resource.edit" && fields.params.unique === true);
      if (shouldNote && rawPath) {
        const jailed = jailProjectPath(projectRoot, rawPath, { forWrite: true });
        if (jailed.ok) {
          runtime.policy.leases.noteWritten(runtime.policy.writerId, jailed.rel, jailed.abs);
        }
      }
      if (isAudioApply(classified.actionId)) {
        for (const target of extractTargetPaths(fields.params, classified.actionId)) {
          const jailed = jailProjectPath(projectRoot, target, { forWrite: true });
          if (jailed.ok && fs.existsSync(jailed.abs)) {
            runtime.policy.leases.noteWritten(runtime.policy.writerId, jailed.rel, jailed.abs);
          }
        }
      }
      if (isTransactionApply(classified.actionId)) {
        for (const target of extractTargetPaths(fields.params, classified.actionId)) {
          const jailed = jailProjectPath(projectRoot, target, { forWrite: true });
          if (jailed.ok && fs.existsSync(jailed.abs)) {
            runtime.policy.leases.noteWritten(runtime.policy.writerId, jailed.rel, jailed.abs);
          }
        }
      }
      if (isProjectSettingsApply(classified.actionId)) {
        const jailed = jailProjectPath(projectRoot, "res://project.godot", {
          forWrite: true,
          allowProjectGodot: true,
        });
        if (jailed.ok) {
          runtime.policy.leases.noteWritten(runtime.policy.writerId, jailed.rel, jailed.abs);
        }
      }
      const after = isRecord(result.after) ? result.after : undefined;
      if (
        after &&
        (classified.actionId === "asset.move" || classified.actionId === "asset.rename") &&
        Array.isArray(after.rewritten_paths)
      ) {
        for (const item of after.rewritten_paths) {
          if (typeof item !== "string" || !item.startsWith("res://")) {
            continue;
          }
          const jailed = jailProjectPath(projectRoot, item, { forWrite: true });
          if (jailed.ok) {
            runtime.policy.leases.noteWritten(runtime.policy.writerId, jailed.rel, jailed.abs);
          }
        }
      }
    }
    if (isPlayApply(classified.actionId) && isRecord(result.after)) {
      notePlayAfter(classified.actionId, result.after);
    }
    saveState(ledger, row, "verified");
    try {
      maybeFault("verified", row.command_id);
    } catch (err) {
      handlePluginFault(runtime, err);
    }
    saveState(ledger, row, "committed_durable");
    return result;
  } finally {
    runtime.policy?.pause.finishJob(row.command_id);
  }
}

function finishSidecarOrchestrator(
  ledger: CommandLedger,
  row: CommandRow,
  actionId: string,
  params: Record<string, unknown>,
  projectRoot: string,
  gated: Extract<GateResult, { ok: true }>,
  policy?: PolicyServices,
): PluginCommandResult {
  saveState(ledger, row, "applying", {
    before_summary: JSON.stringify({
      kind: "orchestrator",
      action_id: actionId,
      ...(gated.checkpoint ? { checkpoint_id: gated.checkpoint.checkpoint_id } : {}),
    }),
    side_effect: actionId === "job.cancel" ? "destructive" : "mutate",
    action_id: actionId,
  });
  row.dispatch_attempted = 1;
  row.updated_at = nowIso();
  ledger.save(row);
  const result = handleOrchAction(
    actionId,
    {
      projectRoot,
      commandId: row.command_id,
      now: Date.now(),
      paused: policy?.pause.isPaused() === true,
    },
    params,
  );
  if (gated.checkpoint) {
    mergeAfter(result, checkpointEvidence(gated.checkpoint));
    row.evidence_json = JSON.stringify([gated.checkpoint.manifest_path]);
    ledger.addCheckpoint(
      gated.checkpoint.checkpoint_id,
      [gated.checkpoint.manifest_path],
      row.command_id,
    );
  }
  row.apply_count = 1;
  persistResult(row, result);
  row.after_summary = JSON.stringify({
    kind: "orchestrator",
    action_id: actionId,
    checks: result.postcondition.checks,
    ...(gated.checkpoint ? { checkpoint_id: gated.checkpoint.checkpoint_id } : {}),
  });
  saveState(ledger, row, "applied_volatile");
  if (!result.ok) {
    saveState(ledger, row, "failed");
    return result;
  }
  if (!isReadVerified(result.postcondition, actionId)) {
    const failed = unverifiedResult(row.command_id, "orchestrator postcondition failed");
    persistResult(row, failed);
    saveState(ledger, row, "failed");
    return failed;
  }
  saveState(ledger, row, "verified");
  saveState(ledger, row, "committed_durable");
  return result;
}

function finishSidecarExport(
  ledger: CommandLedger,
  row: CommandRow,
  actionId: string,
  params: Record<string, unknown>,
  projectRoot: string,
  gated: Extract<GateResult, { ok: true }>,
  policy?: PolicyServices,
): PluginCommandResult {
  saveState(ledger, row, "applying", {
    before_summary: JSON.stringify({
      kind: "export",
      action_id: actionId,
      ...(gated.checkpoint ? { checkpoint_id: gated.checkpoint.checkpoint_id } : {}),
    }),
    side_effect: actionId === "export.cancel" ? "destructive" : "external",
    action_id: actionId,
  });
  row.dispatch_attempted = 1;
  row.updated_at = nowIso();
  ledger.save(row);
  const result = handleExportAction(
    actionId,
    {
      projectRoot,
      commandId: row.command_id,
      now: Date.now(),
      paused: policy?.pause.isPaused() === true,
    },
    params,
  );
  if (gated.checkpoint) {
    mergeAfter(result, checkpointEvidence(gated.checkpoint));
    row.evidence_json = JSON.stringify([gated.checkpoint.manifest_path]);
    ledger.addCheckpoint(
      gated.checkpoint.checkpoint_id,
      [gated.checkpoint.manifest_path],
      row.command_id,
    );
  }
  row.apply_count = 1;
  persistResult(row, result);
  row.after_summary = JSON.stringify({
    kind: "export",
    action_id: actionId,
    checks: result.postcondition.checks,
    ...(gated.checkpoint ? { checkpoint_id: gated.checkpoint.checkpoint_id } : {}),
  });
  saveState(ledger, row, "applied_volatile");
  if (!result.ok) {
    saveState(ledger, row, "failed");
    return result;
  }
  if (!isReadVerified(result.postcondition, actionId)) {
    const failed = unverifiedResult(row.command_id, "export postcondition failed");
    persistResult(row, failed);
    saveState(ledger, row, "failed");
    return failed;
  }
  saveState(ledger, row, "verified");
  saveState(ledger, row, "committed_durable");
  return result;
}

async function finishSidecarMutate(
  ledger: CommandLedger,
  row: CommandRow,
  actionId: string,
  params: Record<string, unknown>,
  projectRoot: string,
  gated: Extract<GateResult, { ok: true }>,
  policy?: PolicyServices,
): Promise<PluginCommandResult> {
  saveState(ledger, row, "applying", {
    before_summary: JSON.stringify({
      kind: "sidecar",
      action_id: actionId,
      ...(gated.checkpoint ? { checkpoint_id: gated.checkpoint.checkpoint_id } : {}),
    }),
    side_effect: actionId === "git.revert_checkpoint" ? "destructive" : "mutate",
    action_id: actionId,
  });
  row.dispatch_attempted = 1;
  row.updated_at = nowIso();
  ledger.save(row);
  let result: PluginCommandResult;
  if (actionId === "editor.pause") {
    const op = params.op === "resume" ? "resume" : "pause";
    if (!policy?.pause) {
      result = unverifiedResult(row.command_id, "pause gate missing");
    } else {
      const ack = op === "resume" ? policy.pause.resume() : policy.pause.pause();
      result = {
        type: "result",
        ok: true,
        command_id: row.command_id,
        changed: true,
        after: { ...ack, op, source: "sidecar" },
        postcondition: { verified: true, checks: ["pause_gate_ack"] },
      };
    }
  } else if (actionId === "git.checkpoint") {
    const paths = extractTargetPaths(params, actionId);
    const allowlist = Array.isArray(params.allowlist)
      ? params.allowlist.filter((item): item is string => typeof item === "string" && item.length > 0)
      : undefined;
    result = applyGitCheckpoint({
      commandId: row.command_id,
      projectRoot,
      message: typeof params.message === "string" ? params.message : "",
      paths,
      ...(allowlist && allowlist.length > 0 ? { allowlist } : {}),
      ...(typeof params.repo === "string" ? { repo: params.repo } : {}),
      ...(typeof params.run_id === "string" ? { runId: params.run_id } : {}),
      ...(typeof params.project === "string" ? { project: params.project } : {}),
      ...(params.resume === true ? { resume: true } : {}),
      ...(policy?.pause ? { pause: policy.pause } : {}),
    });
  } else if (actionId === "git.revert_checkpoint") {
    result = applyGitRevert({
      commandId: row.command_id,
      projectRoot,
      ref: typeof params.ref === "string" ? params.ref : "",
      ...(policy?.pause ? { pause: policy.pause } : {}),
    });
  } else if (actionId === "job.schedule") {
    result = await handleScheduleAction(
      {
        projectRoot,
        commandId: row.command_id,
        now: Date.now(),
        paused: policy?.pause.isPaused() === true,
      },
      params,
    );
  } else if (actionId === "job.compact") {
    result = handleSoakAction(
      {
        projectRoot,
        commandId: row.command_id,
        now: Date.now(),
      },
      params,
    );
  } else {
    result = unverifiedResult(row.command_id, "sidecar mutate not implemented");
  }
  if (gated.checkpoint) {
    const gitReal = isRecord(result.after) && result.after.git_real === true;
    if (gitReal) {
      mergeAfter(result, { dest_preimage: checkpointEvidence(gated.checkpoint) });
    } else {
      mergeAfter(result, checkpointEvidence(gated.checkpoint));
    }
    row.evidence_json = JSON.stringify([gated.checkpoint.manifest_path]);
    ledger.addCheckpoint(
      gated.checkpoint.checkpoint_id,
      [gated.checkpoint.manifest_path],
      row.command_id,
    );
  }
  row.apply_count = 1;
  persistResult(row, result);
  row.after_summary = JSON.stringify({
    kind: "sidecar",
    action_id: actionId,
    checks: result.postcondition.checks,
    ...(gated.checkpoint ? { checkpoint_id: gated.checkpoint.checkpoint_id } : {}),
    ...(isRecord(result.after) && isRecord(result.after.recovery) ? { recovery: result.after.recovery } : {}),
  });
  saveState(ledger, row, "applied_volatile");
  if (!result.ok || !isReadVerified(result.postcondition, actionId)) {
    const failed = result.ok
      ? unverifiedResult(row.command_id, "sidecar mutate postcondition failed")
      : result;
    persistResult(row, failed);
    saveState(ledger, row, "failed");
    return failed;
  }
  if (policy && actionId === "git.revert_checkpoint" && isRecord(result.after)) {
    const files = [
      ...(Array.isArray(result.after.restored) ? result.after.restored : []),
      ...(Array.isArray(result.after.deleted) ? result.after.deleted : []),
    ];
    for (const rel of files) {
      if (typeof rel !== "string" || !rel) {
        continue;
      }
      const abs = path.join(projectRoot, rel);
      policy.leases.noteWritten(policy.writerId, rel, abs);
    }
  }
  saveState(ledger, row, "verified");
  saveState(ledger, row, "committed_durable");
  return result;
}

function markUncertain(
  ledger: CommandLedger,
  row: CommandRow,
  message: string,
): PluginCommandResult {
  const result = errorResult(row.command_id, E.E_UNCERTAIN, message);
  persistResult(row, result);
  saveState(ledger, row, "uncertain");
  return result;
}

function commitVerified(ledger: CommandLedger, row: CommandRow, result: PluginCommandResult): PluginCommandResult {
  persistResult(row, result);
  if (row.state !== "verified" && row.state !== "committed_durable") {
    saveState(ledger, row, "verified");
  }
  try {
    maybeFault("verified", row.command_id);
  } catch {
    /* already verified; commit next */
  }
  saveState(ledger, row, "committed_durable");
  return result;
}

async function recoverFromReadback(
  ledger: CommandLedger,
  row: CommandRow,
  runtime: LedgerRuntime,
): Promise<PluginCommandResult | undefined> {
  let readback: PluginReadback;
  try {
    readback = await runtime.readPostcondition(row.command_id);
  } catch {
    return undefined;
  }
  const noopOk = readback.found && readback.ok && isNoopVerified(readback.postcondition);
  const readOk =
    readback.found &&
    readback.ok &&
    row.action_id !== "" &&
    row.action_id !== "hh.plugin/noop" &&
    isReadVerified(readback.postcondition, row.action_id);
  if (noopOk || readOk) {
    if (
      sceneNeedsDiskHash(row.action_id) ||
      isResourceApply(row.action_id) ||
      isAssetRefApply(row.action_id) ||
      isAssetIngestApply(row.action_id) ||
      isScriptApply(row.action_id) ||
      isProjectSettingsApply(row.action_id)
    ) {
      return undefined;
    }
    const result: PluginCommandResult = {
      type: "result",
      ok: true,
      command_id: row.command_id,
      changed: false,
      postcondition: readback.postcondition,
    };
    persistResult(row, result);
    row.after_summary = JSON.stringify({
      kind: noopOk ? "noop" : "read",
      checks: readback.postcondition.checks,
    });
    return commitVerified(ledger, row, result);
  }
  return undefined;
}

async function recoverApplying(
  ledger: CommandLedger,
  row: CommandRow,
  envelope: Record<string, unknown>,
  bound: LedgerBound,
  runtime: LedgerRuntime,
  timeoutMs: number,
): Promise<PluginCommandResult> {
  const fromReadback = await recoverFromReadback(ledger, row, runtime);
  if (fromReadback) {
    return fromReadback;
  }
  const stored = parseStoredResult(row.result_json, row.command_id);
  if (stored && stored.ok && storedSceneReady(stored, row, envelope, runtime)) {
    return commitVerified(ledger, row, stored);
  }
  if (row.dispatch_attempted === 0 && row.apply_count === 0) {
    const classified = classify(envelope, row.command_id);
    if (classified.kind === "noop") {
      return applyNoopOnce(ledger, row, envelope, runtime, timeoutMs);
    }
    if (classified.kind === "forward") {
      return applyReadOnce(ledger, row, envelope, bound, runtime, classified);
    }
    if (classified.kind === "mutate") {
      return applyMutateOnce(ledger, row, envelope, bound, runtime, classified);
    }
  }
  return markUncertain(ledger, row, "applying crashed; cannot confirm postcondition");
}

async function recoverVolatile(
  ledger: CommandLedger,
  row: CommandRow,
  envelope: Record<string, unknown>,
  bound: LedgerBound,
  runtime: LedgerRuntime,
  timeoutMs: number,
): Promise<PluginCommandResult> {
  const stored = parseStoredResult(row.result_json, row.command_id);
  if (stored && stored.ok && storedSceneReady(stored, row, envelope, runtime)) {
    return commitVerified(ledger, row, stored);
  }
  const fromReadback = await recoverFromReadback(ledger, row, runtime);
  if (fromReadback) {
    return fromReadback;
  }
  if (row.dispatch_attempted === 0 && row.apply_count === 0) {
    const classified = classify(envelope, row.command_id);
    if (classified.kind === "noop") {
      return applyNoopOnce(ledger, row, envelope, runtime, timeoutMs);
    }
    if (classified.kind === "forward") {
      return applyReadOnce(ledger, row, envelope, bound, runtime, classified);
    }
    if (classified.kind === "mutate") {
      return applyMutateOnce(ledger, row, envelope, bound, runtime, classified);
    }
  }
  return markUncertain(ledger, row, "applied_volatile without durable verify");
}

async function continueAfterReceived(
  ledger: CommandLedger,
  row: CommandRow,
  envelope: Record<string, unknown>,
  bound: LedgerBound,
  runtime: LedgerRuntime,
): Promise<PluginCommandResult> {
  const classified = classify(envelope, row.command_id);
  row.side_effect =
    classified.kind === "noop"
      ? "read"
      : classified.kind === "blocked" || classified.kind === "forward" || classified.kind === "mutate"
        ? classified.sideEffect
        : "";
  row.action_id =
    classified.kind === "noop"
      ? "hh.plugin/noop"
      : classified.kind === "blocked" || classified.kind === "forward" || classified.kind === "mutate"
        ? classified.actionId
        : "";
  saveState(ledger, row, "validated");
  try {
    maybeFault("validated", row.command_id);
  } catch (err) {
    handlePluginFault(runtime, err);
  }
  if (classified.kind === "invalid") {
    persistResult(row, classified.result);
    saveState(ledger, row, "failed");
    return classified.result;
  }
  if (classified.kind === "blocked") {
    return settleBlocked(ledger, row, envelope, bound, runtime, classified);
  }
  if (classified.kind === "forward") {
    return applyReadOnce(ledger, row, envelope, bound, runtime, classified);
  }
  if (classified.kind === "mutate") {
    return applyMutateOnce(ledger, row, envelope, bound, runtime, classified);
  }
  return applyNoopOnce(ledger, row, envelope, runtime, classified.timeoutMs);
}

export async function executeCommand(
  ledger: CommandLedger,
  envelope: Record<string, unknown>,
  bound: LedgerBound,
  runtime: LedgerRuntime,
): Promise<PluginCommandResult> {
  const fields = envelopeFields(envelope);
  if (!isUlid(fields.command_id)) {
    return errorResult(fields.command_id, E.E_INVALID_COMMAND_ID, "command_id must be a ULID", "command_id");
  }
  const hash = canonicalRequestHash({
    command_id: fields.command_id,
    method: fields.method,
    action: fields.action,
    params: fields.params,
    precondition: envelope.precondition,
    presentation: envelope.presentation,
    action_version: envelope.action_version,
  });
  const existing = ledger.get(fields.command_id);
  if (!existing) {
    const projectRoot = runtime.projectRoot ?? runtime.policy?.projectRoot ?? "";
    const soakHit = projectRoot ? lookupSoakCached(projectRoot, fields.command_id) : undefined;
    if (soakHit) {
      return soakHit;
    }
  }
  if (existing) {
    if (identityConflict(existing, hash, bound)) {
      return errorResult(
        fields.command_id,
        E.E_IDEMPOTENCY_CONFLICT,
        "same command_id with different request hash or bound identity",
        "command_id",
      );
    }
    if (existing.state === "uncertain") {
      return cachedOrError(existing);
    }
    if (existing.state === "committed_durable" || existing.state === "failed") {
      return cachedOrError(existing);
    }
    if (existing.state === "verified") {
      const stored = parseStoredResult(existing.result_json, existing.command_id);
      if (stored && stored.ok && storedSceneReady(stored, existing, envelope, runtime)) {
        return commitVerified(ledger, existing, stored);
      }
      return markUncertain(ledger, existing, "verified without matching postcondition");
    }
    if (existing.state === "applied_volatile") {
      return recoverVolatile(ledger, existing, envelope, bound, runtime, 5_000);
    }
    if (existing.state === "applying") {
      return recoverApplying(ledger, existing, envelope, bound, runtime, 5_000);
    }
    if (existing.state === "validated") {
      const classified = classify(envelope, existing.command_id);
      if (classified.kind === "invalid") {
        persistResult(existing, classified.result);
        saveState(ledger, existing, "failed");
        return classified.result;
      }
      if (classified.kind === "blocked") {
        return settleBlocked(ledger, existing, envelope, bound, runtime, classified);
      }
      if (classified.kind === "forward") {
        return applyReadOnce(ledger, existing, envelope, bound, runtime, classified);
      }
      if (classified.kind === "mutate") {
        return applyMutateOnce(ledger, existing, envelope, bound, runtime, classified);
      }
      return applyNoopOnce(ledger, existing, envelope, runtime, classified.timeoutMs);
    }
    if (existing.state === "received") {
      return continueAfterReceived(ledger, existing, envelope, bound, runtime);
    }
  }

  const precondition = isRecord(envelope.precondition) ? JSON.stringify(envelope.precondition) : "";
  const row = emptyRow({
    command_id: fields.command_id,
    request_hash: hash,
    actor_id: bound.actorId,
    project_id: bound.projectId,
    policy: bound.policy,
    method: fields.method,
    action: fields.action,
    action_id: "",
    side_effect: "",
    state: "received",
    envelope_json: JSON.stringify(envelope),
    result_json: "",
    error_code: "",
    error_message: "",
    postcondition_json: "",
    precondition_json: precondition,
    before_summary: "",
    after_summary: "",
    apply_count: 0,
    dispatch_attempted: 0,
    evidence_json: "[]",
  });
  ledger.insertReceived(row);
  try {
    maybeFault("received", fields.command_id);
  } catch (err) {
    handlePluginFault(runtime, err);
  }
  const result = await continueAfterReceived(ledger, row, envelope, bound, runtime);
  const projectRoot = runtime.projectRoot ?? runtime.policy?.projectRoot ?? "";
  if (result.ok && projectRoot) {
    rememberSoakResult(projectRoot, fields.command_id, result);
  }
  return result;
}

export function inspectRow(row: CommandRow): Record<string, unknown> {
  return {
    command_id: row.command_id,
    state: row.state,
    request_hash: row.request_hash,
    actor_id: row.actor_id,
    project_id: row.project_id,
    policy: row.policy,
    method: row.method,
    action: row.action,
    action_id: row.action_id,
    side_effect: row.side_effect,
    apply_count: row.apply_count,
    dispatch_attempted: row.dispatch_attempted,
    error_code: row.error_code,
    evidence: JSON.parse(row.evidence_json) as unknown,
    before_summary: row.before_summary,
    after_summary: row.after_summary,
  };
}
