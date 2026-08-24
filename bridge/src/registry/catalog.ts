/**
 * §5.2 required groups and verbs. Tests fail if the live registry misses one.
 * Slash lists in the plan become dotted ids: animation.state-machine → state_machine.
 */

export const REQUIRED_VERBS: Readonly<Record<string, readonly string[]>> = {
  capabilities: ["describe"],
  project: ["inspect", "settings", "input", "autoload", "plugin", "doctor"],
  scene: [
    "create",
    "open",
    "read",
    "save",
    "close",
    "instantiate",
    "dependencies",
    "list_tabs",
    "activate",
    "save_as",
    "reload",
  ],
  node: [
    "add",
    "remove",
    "rename",
    "reparent",
    "reorder",
    "duplicate",
    "group",
    "query",
    "make_local",
    "undo",
    "redo",
  ],
  property: ["get", "set", "batch", "reset"],
  resource: ["create", "load", "assign", "duplicate", "edit", "save", "uid"],
  signal: ["list", "connect", "disconnect", "inspect"],
  script: ["read", "write", "patch", "validate", "attach", "detach", "rename", "open_at", "diagnostics"],
  asset: ["import", "reimport", "move", "rename", "delete", "dependencies", "preview"],
  tilemap: ["tileset", "source", "terrain", "layer", "cell", "fill", "stamp", "query"],
  animation: ["library", "animation", "track", "key", "sprite_frames", "state_machine", "preview"],
  ui: ["control", "theme", "layout", "anchor", "focus", "accessibility"],
  editor: ["state", "select", "focus", "main_screen", "frame_view", "replay", "pause"],
  observer: ["timeline", "append", "focus", "overlay", "scheduler", "review"],
  review: ["card", "diff", "open", "replay", "write_card"],
  play: ["start", "stop", "restart", "debug", "status", "logs"],
  input: ["action", "key", "mouse", "touch", "sequence", "release_all"],
  runtime: [
    "tree",
    "node",
    "state",
    "signal",
    "time",
    "freeze",
    "step",
    "screenshot",
    "perf",
    "assert",
  ],
  test: ["define", "run", "assert", "report", "evidence", "baseline", "repair"],
  export: ["preset", "validate", "build", "cancel", "artifacts"],
  git: ["status", "diff", "checkpoint", "revert_checkpoint"],
  job: ["status", "list", "cancel", "wait", "transaction", "plan", "run", "schedule", "compact"],
  canvas: ["bounds", "layout_batch"],
  camera: ["make_current"],
  physics: ["body", "shape", "layers", "nav_region", "nav_agent", "path", "lint", "debug"],
  audio: ["player", "bus", "preview"],
  render: ["shader", "particles", "quality"],
};

export function requiredActionIds(): string[] {
  const ids: string[] = [];
  for (const [group, verbs] of Object.entries(REQUIRED_VERBS)) {
    for (const verb of verbs) {
      ids.push(`${group}.${verb}`);
    }
  }
  return ids;
}

export const REQUIRED_ACTION_COUNT = requiredActionIds().length;
