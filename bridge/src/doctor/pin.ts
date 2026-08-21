import fs from "node:fs";
import path from "node:path";

export const PINNED_VERSION_ID = "4.7.1.stable.official.a13da4feb" as const;
export const PINNED_TAG = "4.7.1-stable" as const;
export const PINNED_REGISTRY = "hh-godot-actions/1" as const;
export const REFUSE_VERSION_NEEDLES = ["4.7.2", "4.8"] as const;
export const PINNED_CONSOLE_EXE = "Godot_v4.7.1-stable_win64_console.exe" as const;
export const PINNED_CACHE_DIR = "godot-4.7.1-stable" as const;
export const PINNED_TEMPLATES_TPZ = "Godot_v4.7.1-stable_export_templates.tpz" as const;
export const PINNED_TEMPLATE_VERSION_DIR = "4.7.1.stable" as const;

export function findRepoRoot(start: string): string | undefined {
  let dir = path.resolve(start);
  for (;;) {
    const pin = path.join(dir, "tools", "godot", "pin.json");
    const plan = path.join(dir, "zdocs", "20-8-godot-agent-autopilot-plan.txt");
    if (fs.existsSync(pin) && fs.existsSync(plan)) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      return undefined;
    }
    dir = parent;
  }
}

export function toolingRoot(home: string): string {
  return path.join(home, "tooling", PINNED_CACHE_DIR);
}

export function pinnedConsolePath(home: string): string {
  return path.join(toolingRoot(home), "bin", PINNED_CONSOLE_EXE);
}

export function pinnedTemplatesTpz(home: string): string {
  return path.join(toolingRoot(home), "downloads", PINNED_TEMPLATES_TPZ);
}

export function installedTemplatesDir(): string | undefined {
  const roaming = process.env.APPDATA;
  if (!roaming) {
    return undefined;
  }
  return path.join(roaming, "Godot", "export_templates", PINNED_TEMPLATE_VERSION_DIR);
}

export function versionIsRefused(version: string): boolean {
  const lowered = version.toLowerCase();
  return REFUSE_VERSION_NEEDLES.some((needle) => lowered.includes(needle.toLowerCase()));
}
