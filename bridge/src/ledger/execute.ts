/** Durable command ledger: flush before dispatch, dedup, uncertain recovery. */

import fs from "node:fs";

import { runMutationGate, type PolicyServices } from "../policy/engine.js";
import { jailProjectPath } from "../policy/jail.js";
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
  isPropertyApply,
  isProvenEditorApply,
  isSceneLifecycleApply,
  nodeNeedsUidAfter,
  sceneNeedsDiskHash,
} from "./scene_lifecycle.js";
import { emptyRow, type CommandLedger, type CommandRow } from "./store.js";
import type { LedgerState } from "./states.js";

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
  if (!sceneNeedsDiskHash(row.action_id)) {
    return true;
  }
  const projectRoot = runtime.projectRoot ?? runtime.policy?.projectRoot ?? "";
  if (!projectRoot) {
    return false;
  }
  return durableDiskOk(stored, row.action_id, envelopeFields(envelope).params, projectRoot) === undefined;
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
  if (isProvenEditorApply(accepted.action_id)) {
    return {
      kind: "mutate",
      sideEffect: side,
      actionId: accepted.action_id,
      timeoutMs: def?.timeout_ms ?? 15_000,
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

function encodedClose(a: unknown, b: unknown): boolean {
  return JSON.stringify(canonJson(a)) === JSON.stringify(canonJson(b));
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

function durableDiskOk(
  result: PluginCommandResult,
  actionId: string,
  params: Record<string, unknown>,
  projectRoot: string,
): PluginCommandResult | undefined {
  if (!sceneNeedsDiskHash(actionId)) {
    return undefined;
  }
  if (!result.ok) {
    return result;
  }
  const rawPath = typeof params.path === "string" ? params.path : "";
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
  if (!isProvenEditorApply(classified.actionId)) {
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
    if (!runtime.pluginConnected()) {
      const result = unverifiedResult(row.command_id, "no plugin");
      persistResult(row, result);
      saveState(ledger, row, "failed");
      return result;
    }
    saveState(ledger, row, "applying", {
      before_summary: JSON.stringify({
        kind: "scene",
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
      return markUncertain(ledger, row, "dispatch interrupted; postcondition unknown");
    }
    row.apply_count = 1;
    persistResult(row, result);
    row.after_summary = JSON.stringify({
      kind: isPropertyApply(classified.actionId)
        ? "property"
        : isSceneLifecycleApply(classified.actionId)
          ? "scene"
          : "node",
      action_id: classified.actionId,
      checks: result.postcondition.checks,
      disk_hash: isRecord(result.after) ? result.after.disk_hash ?? "" : "",
      uid: isRecord(result.after) ? result.after.uid ?? "" : "",
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
      saveState(ledger, row, "failed");
      return result;
    }
    if (!isReadVerified(result.postcondition, classified.actionId)) {
      const failed = unverifiedResult(row.command_id, "scene postcondition failed");
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
    const projectRoot = runtime.projectRoot ?? runtime.policy?.projectRoot ?? "";
    const diskFail = durableDiskOk(result, classified.actionId, fields.params, projectRoot);
    if (diskFail) {
      persistResult(row, diskFail);
      saveState(ledger, row, "failed");
      return diskFail;
    }
    if (runtime.policy && sceneNeedsDiskHash(classified.actionId)) {
      const rawPath = typeof fields.params.path === "string" ? fields.params.path : "";
      if (rawPath) {
        const jailed = jailProjectPath(projectRoot, rawPath, { forWrite: true });
        if (jailed.ok) {
          runtime.policy.leases.noteWritten(runtime.policy.writerId, jailed.rel, jailed.abs);
        }
      }
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
    if (sceneNeedsDiskHash(row.action_id)) {
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
  return continueAfterReceived(ledger, row, envelope, bound, runtime);
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
