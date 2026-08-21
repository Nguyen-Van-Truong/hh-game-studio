/** Profile / side-effect gates. OWNER_AUTOPILOT is project-scoped, not unrestricted OS. */

import { E, typedError } from "../registry/errors.js";
import { POLICIES, type Policy, type SideEffect } from "../registry/types.js";

export const DEFAULT_POLICY: Policy = "OWNER_AUTOPILOT";

export function normalizePolicy(raw: string | undefined): Policy {
  if (raw === "OBSERVE" || raw === "EDIT" || raw === "OWNER_AUTOPILOT") {
    return raw;
  }
  return DEFAULT_POLICY;
}

export function isPolicy(value: string): value is Policy {
  return (POLICIES as readonly string[]).includes(value);
}

export function isMutatingSideEffect(side: string): boolean {
  return side === "mutate" || side === "destructive" || side === "external";
}

export function profileAllows(policy: Policy, side: SideEffect | string, approvedDestructive: boolean): boolean {
  if (side === "read" || side === "view" || side === "") {
    return true;
  }
  if (policy === "OBSERVE") {
    return false;
  }
  if (policy === "EDIT") {
    if (side === "mutate") {
      return true;
    }
    if (side === "destructive") {
      return approvedDestructive;
    }
    return false;
  }
  return side === "mutate" || side === "destructive" || side === "external";
}

export function denyProfile(
  policy: Policy,
  side: string,
  approvedDestructive: boolean,
): { code: string; message: string; path: string } | undefined {
  if (profileAllows(policy, side, approvedDestructive)) {
    return undefined;
  }
  if (policy === "OBSERVE") {
    return typedError(E.E_POLICY, "OBSERVE allows read/view/noop only", "policy");
  }
  if (policy === "EDIT" && side === "destructive" && !approvedDestructive) {
    return typedError(E.E_POLICY, "EDIT requires approve before destructive", "policy");
  }
  return typedError(E.E_POLICY, `${policy} does not allow ${side}`, "policy");
}
