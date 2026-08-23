/** Compose profile, pause, jail, leases, and recovery checkpoint before applying. */

import { E, typedError } from "../registry/errors.js";
import type { Policy, SideEffect } from "../registry/types.js";
import { ApprovalBinder, projectRevision } from "./approve.js";
import { createRecoveryCheckpoint, type CheckpointOk } from "./checkpoint.js";
import { extractTargetPaths, jailProjectPath, type JailOk } from "./jail.js";
import { LeaseTable } from "./leases.js";
import { PauseGate } from "./pause.js";
import { denyProfile, isMutatingSideEffect } from "./profiles.js";

export interface PolicyServices {
  projectRoot: string;
  writerId: string;
  pause: PauseGate;
  leases: LeaseTable;
  approvals?: ApprovalBinder;
  approvalToken?: string;
  revision?: string;
  checkpointFail?: boolean;
}

export interface GateInput {
  commandId: string;
  sideEffect: SideEffect | string;
  actionId: string;
  checkpointRequired: boolean;
  policy: Policy;
  params: Record<string, unknown>;
  requestHash?: string;
  services?: PolicyServices;
}

export interface GateDenied {
  ok: false;
  error: { code: string; message: string; path: string };
}

export interface GateAllowed {
  ok: true;
  jailed: JailOk[];
  checkpoint?: CheckpointOk;
}

export type GateResult = GateDenied | GateAllowed;

export function runMutationGate(input: GateInput): GateResult {
  const services = input.services;
  const orchControl = input.actionId === "job.run" || input.actionId === "job.cancel" || input.actionId === "job.wait";
  if (services && !orchControl && !services.pause.allowsSideEffect(input.sideEffect)) {
    return {
      ok: false,
      error: typedError(E.E_PAUSED, "mutation gate is paused", "pause"),
    };
  }
  const denied = denyProfile(
    input.policy,
    input.sideEffect,
    consumeEditApproval(services, input.policy, input.sideEffect, input.requestHash ?? ""),
  );
  if (denied) {
    return { ok: false, error: denied };
  }
  if (!isMutatingSideEffect(input.sideEffect)) {
    return { ok: true, jailed: [] };
  }
  if (!services) {
    return {
      ok: false,
      error: typedError(E.E_PATH, "project root required for mutation gates", "project"),
    };
  }
  const targets = extractTargetPaths(input.params, input.actionId);
  const jailed: JailOk[] = [];
  for (const target of targets) {
    const result = jailProjectPath(services.projectRoot, target, {
      forWrite: true,
      allowProjectGodot: isProjectSettingsAction(input.actionId),
    });
    if (!result.ok) {
      return { ok: false, error: result.error };
    }
    jailed.push(result);
  }
  try {
    services.leases.acquireWriter(services.writerId);
    for (const item of jailed) {
      services.leases.acquireFile(services.writerId, item.rel, item.abs);
    }
    for (const item of jailed) {
      services.leases.assertUnchanged(item.rel, item.abs);
    }
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && typeof err.code === "string") {
      return {
        ok: false,
        error: typedError(err.code, err instanceof Error ? err.message : "lease", "lease"),
      };
    }
    return { ok: false, error: typedError(E.E_BUSY, "lease acquire failed", "lease") };
  }
  const needsCheckpoint = input.sideEffect === "destructive" || input.checkpointRequired;
  if (!needsCheckpoint) {
    return { ok: true, jailed };
  }
  const created = createRecoveryCheckpoint({
    projectRoot: services.projectRoot,
    commandId: input.commandId,
    targets: targets.length > 0 ? targets : [],
    ...(services.checkpointFail ? { fail: true } : {}),
  });
  if (!created.ok) {
    return { ok: false, error: created.error };
  }
  return { ok: true, jailed, checkpoint: created };
}

const PROJECT_SETTINGS_APPLY = new Set([
  "project.settings",
  "project.input",
  "project.autoload",
  "project.plugin",
]);

function isProjectSettingsAction(actionId: string): boolean {
  return PROJECT_SETTINGS_APPLY.has(actionId);
}

function consumeEditApproval(
  services: PolicyServices | undefined,
  policy: Policy,
  side: string,
  requestHash: string,
): boolean {
  if (policy !== "EDIT" || side !== "destructive") {
    return true;
  }
  if (!services || !requestHash) {
    return false;
  }
  const revision = services.revision ?? projectRevision(services.projectRoot);
  const token = services.approvalToken ?? "";
  if (services.approvals) {
    return services.approvals.consume(services.writerId, requestHash, revision, token);
  }
  return false;
}
