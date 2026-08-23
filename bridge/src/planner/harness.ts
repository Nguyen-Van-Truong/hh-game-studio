/** CLI: compile one brief, a fixture dir, or the cyclic DAG detector. */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { compileBrief, writePlanEvidence } from "./brief_compiler.js";

function write(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function projectFromArgs(args: string[]): string {
  const idx = args.indexOf("--project");
  const given = idx >= 0 ? args[idx + 1] : undefined;
  if (given) {
    return path.resolve(given);
  }
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "godot", "plugin-project");
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.includes("--cycle")) {
    const plan = compileBrief({
      brief: "# PROJECT_BRIEF\n\nMake a 2D game.\n",
      inject_cycle: true,
    });
    write(plan);
    return;
  }
  const dirIdx = args.indexOf("--dir");
  if (dirIdx >= 0) {
    const dir = args[dirIdx + 1] ?? "";
    const project = projectFromArgs(args);
    const files = fs
      .readdirSync(dir)
      .filter((name) => name.endsWith(".md"))
      .sort();
    const plans = files.map((name) => {
      const brief = fs.readFileSync(path.join(dir, name), "utf8");
      const plan = compileBrief({ brief });
      const evidence = plan.ok ? writePlanEvidence(project, plan) : { assumptions: "", plan: "" };
      return { file: name, plan, evidence };
    });
    write({ ok: true, count: plans.length, plans });
    return;
  }
  const briefIdx = args.indexOf("--brief");
  const file = briefIdx >= 0 ? (args[briefIdx + 1] ?? "") : "";
  if (!file) {
    write({ ok: false, error: { code: "E_MISSING_REQUIRED", message: "--brief or --dir or --cycle" } });
    process.exitCode = 2;
    return;
  }
  const brief = fs.readFileSync(file, "utf8");
  const runIdx = args.indexOf("--run-id");
  const run_id = runIdx >= 0 ? args[runIdx + 1] : undefined;
  const plan = compileBrief({ brief, ...(run_id ? { run_id } : {}) });
  const project = projectFromArgs(args);
  const evidence = plan.ok ? writePlanEvidence(project, plan) : { assumptions: "", plan: "" };
  write({ ...plan, evidence });
}

main();
