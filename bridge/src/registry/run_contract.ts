/** Execute the contract matrix and envelope guards. No Godot. */

import path from "node:path";
import { pathToFileURL } from "node:url";
import { E } from "./errors.js";
import { validateResult } from "./envelope.js";
import { acceptCommand, exampleEnvelope } from "./dispatch.js";
import { buildContractMatrix, matrixStats } from "./matrix.js";
import { actionCount, allActionDefs, missingRequiredVerbs } from "./registry.js";
import { EXAMPLE_ULID } from "./ulid.js";
import { FORBIDDEN_CLIENT_FIELDS, RESULT_SCHEMA } from "./types.js";

export interface ContractReport {
  ok: boolean;
  actions: number;
  cases: number;
  failed: number;
  errors: string[];
}

function runEnvelopeGuards(errors: string[]): void {
  const base = exampleEnvelope("node.query", {
    scene: "res://scenes/world.tscn",
    by: "group",
    group: "interactable",
  });

  const proto2 = { ...base, protocol: "hh-godot-agent/2" };
  const proto = acceptCommand(proto2);
  if (proto.accepted || proto.error.code !== E.E_PROTOCOL_VERSION) {
    errors.push("hh-godot-agent/2 must be E_PROTOCOL_VERSION");
  }

  const stale = acceptCommand({ ...base, action_version: "0" });
  if (stale.accepted || stale.error.code !== E.E_ACTION_VERSION) {
    errors.push("stale action_version must be E_ACTION_VERSION");
  }

  for (const field of FORBIDDEN_CLIENT_FIELDS) {
    const raw = { ...base, [field]: field === "grants" ? [] : "client-set" };
    const got = acceptCommand(raw);
    if (got.accepted || got.error.code !== E.E_CLIENT_ESCALATION) {
      errors.push(`${field} must be E_CLIENT_ESCALATION`);
    }
  }

  const unknownParam = acceptCommand(
    exampleEnvelope("node.query", {
      scene: "res://scenes/world.tscn",
      by: "group",
      group: "interactable",
      __hh_unknown: true,
    }),
  );
  if (unknownParam.accepted || unknownParam.error.code !== E.E_UNKNOWN_PARAM) {
    errors.push("__hh_unknown must be E_UNKNOWN_PARAM");
  }

  const okOnly = validateResult({ ok: true });
  if (!okOnly || okOnly.code !== E.E_MISSING_REQUIRED) {
    errors.push("{ok:true} must fail result schema (postcondition required)");
  }

  const required = RESULT_SCHEMA.required ?? [];
  if (!required.includes("postcondition")) {
    errors.push("RESULT_SCHEMA must require postcondition");
  }
  const post = RESULT_SCHEMA.properties?.postcondition;
  if (!post || !(post.required ?? []).includes("verified") || !(post.required ?? []).includes("checks")) {
    errors.push("RESULT_SCHEMA.postcondition must require verified and checks");
  }

  const good = validateResult({
    ok: true,
    command_id: EXAMPLE_ULID,
    postcondition: { verified: false, checks: ["schema_only"] },
  });
  if (good) {
    errors.push(`valid result rejected: ${good.code} ${good.message}`);
  }

  const paper = validateResult({
    ok: true,
    command_id: EXAMPLE_ULID,
    postcondition: { verified: true, checks: [] },
  });
  if (!paper || paper.code !== E.E_UNVERIFIED) {
    errors.push("verified:true with empty checks must fail as paper success");
  }
}

export function runContract(): ContractReport {
  const errors: string[] = [];
  const missing = missingRequiredVerbs();
  if (missing.length > 0) {
    errors.push(`REQUIRED_VERBS missing from catalog: ${missing.join(",")}`);
  }
  const actions = actionCount();
  if (actions !== allActionDefs().length) {
    errors.push("actionCount mismatch");
  }

  const cases = buildContractMatrix();
  const stats = matrixStats(cases);
  if (stats.actions !== actions) {
    errors.push(`matrix covers ${stats.actions} actions, catalog has ${actions}`);
  }
  if (stats.missing < actions || stats.unknown < actions || stats.type < actions || stats.bounds < actions) {
    errors.push("matrix missing a 4-way lane for some action");
  }
  if (stats.positives < actions) {
    errors.push("matrix missing a positive case for some action");
  }

  let failed = 0;
  for (const c of cases) {
    const result = acceptCommand(exampleEnvelope(c.action_id, c.params));
    if (c.expect === "accept") {
      if (!result.accepted) {
        failed += 1;
        errors.push(`${c.id}: expected accept got ${result.error.code} ${result.error.message}`);
        continue;
      }
      if (
        typeof result.postcondition !== "object" ||
        result.postcondition === null ||
        typeof result.postcondition.verified !== "boolean" ||
        !Array.isArray(result.postcondition.checks)
      ) {
        failed += 1;
        errors.push(`${c.id}: ValidationOk.postcondition must be {verified, checks}`);
      }
    } else if (result.accepted) {
      failed += 1;
      errors.push(`${c.id}: expected ${c.expect} but accepted`);
    } else if (result.error.code !== c.expect) {
      failed += 1;
      errors.push(`${c.id}: expected ${c.expect} got ${result.error.code} (${result.error.message})`);
    }
  }

  runEnvelopeGuards(errors);
  const extraFails = errors.length - failed;
  if (extraFails > 0) {
    failed += extraFails;
  }

  return {
    ok: errors.length === 0,
    actions,
    cases: cases.length,
    failed,
    errors,
  };
}

function invokedDirectly(): boolean {
  const argv1 = process.argv[1];
  if (!argv1) {
    return false;
  }
  return import.meta.url === pathToFileURL(path.resolve(argv1)).href;
}

if (invokedDirectly()) {
  const report = runContract();
  const summary = {
    ok: report.ok,
    actions: report.actions,
    cases: report.cases,
    failed: report.failed,
  };
  process.stdout.write(`${JSON.stringify(summary)}\n`);
  if (!report.ok) {
    for (const err of report.errors.slice(0, 40)) {
      process.stderr.write(`  - ${err}\n`);
    }
    if (report.errors.length > 40) {
      process.stderr.write(`  - … ${report.errors.length - 40} more\n`);
    }
    process.exitCode = 1;
  }
}
