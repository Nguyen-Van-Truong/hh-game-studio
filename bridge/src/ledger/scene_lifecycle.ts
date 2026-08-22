/** Proven editor apply verbs. Scene, node, property, resource, signal, script, asset-ref. */

export const SCENE_LIFECYCLE_APPLY = [
  "scene.create",
  "scene.open",
  "scene.save",
  "scene.save_as",
  "scene.reload",
  "scene.activate",
  "scene.close",
] as const;

export const NODE_CRUD_APPLY = [
  "node.add",
  "node.remove",
  "node.rename",
  "node.reparent",
  "node.reorder",
  "node.duplicate",
  "node.group",
  "node.make_local",
  "node.undo",
  "node.redo",
  "scene.instantiate",
] as const;

export const PROPERTY_APPLY = ["property.set", "property.batch", "property.reset"] as const;

export const CANVAS_APPLY = ["canvas.layout_batch"] as const;

export const CAMERA_APPLY = ["camera.make_current"] as const;

export const TILEMAP_APPLY = [
  "tilemap.tileset",
  "tilemap.source",
  "tilemap.terrain",
  "tilemap.layer",
  "tilemap.cell",
  "tilemap.fill",
  "tilemap.stamp",
] as const;

export const ANIMATION_APPLY = [
  "animation.library",
  "animation.animation",
  "animation.track",
  "animation.key",
  "animation.sprite_frames",
  "animation.state_machine",
] as const;

export const UI_APPLY = ["ui.control", "ui.theme", "ui.layout", "ui.anchor"] as const;

export const PHYSICS_APPLY = [
  "physics.body",
  "physics.shape",
  "physics.layers",
  "physics.nav_region",
  "physics.nav_agent",
] as const;

export const RESOURCE_APPLY = [
  "resource.create",
  "resource.assign",
  "resource.duplicate",
  "resource.edit",
  "resource.save",
] as const;

export const SIGNAL_APPLY = ["signal.connect", "signal.disconnect"] as const;

export const ASSET_INGEST_APPLY = ["asset.import", "asset.reimport"] as const;

export const ASSET_REF_APPLY = ["asset.move", "asset.rename", "asset.delete"] as const;

export const SCRIPT_APPLY = [
  "script.write",
  "script.patch",
  "script.attach",
  "script.detach",
  "script.rename",
] as const;

export const PROJECT_SETTINGS_APPLY = [
  "project.settings",
  "project.input",
  "project.autoload",
  "project.plugin",
] as const;

export const SIDECAR_MUTATE_APPLY = ["git.checkpoint", "git.revert_checkpoint"] as const;

export const TRANSACTION_APPLY = ["job.transaction"] as const;

export const NODE_UID_AFTER = [
  "node.add",
  "node.rename",
  "node.reparent",
  "node.reorder",
  "node.duplicate",
  "node.group",
  "scene.instantiate",
] as const;

export const SCENE_DURABLE_DISK = ["scene.create", "scene.save", "scene.save_as"] as const;

export function isSceneLifecycleApply(actionId: string): boolean {
  return (SCENE_LIFECYCLE_APPLY as readonly string[]).includes(actionId);
}

export function isNodeCrudApply(actionId: string): boolean {
  return (NODE_CRUD_APPLY as readonly string[]).includes(actionId);
}

export function isPropertyApply(actionId: string): boolean {
  return (PROPERTY_APPLY as readonly string[]).includes(actionId);
}

export function isCanvasApply(actionId: string): boolean {
  return (CANVAS_APPLY as readonly string[]).includes(actionId);
}

export function isCameraApply(actionId: string): boolean {
  return (CAMERA_APPLY as readonly string[]).includes(actionId);
}

export function isTilemapApply(actionId: string): boolean {
  return (TILEMAP_APPLY as readonly string[]).includes(actionId);
}

export function isAnimationApply(actionId: string): boolean {
  return (ANIMATION_APPLY as readonly string[]).includes(actionId);
}

export function isUiApply(actionId: string): boolean {
  return (UI_APPLY as readonly string[]).includes(actionId);
}

export function isPhysicsApply(actionId: string): boolean {
  return (PHYSICS_APPLY as readonly string[]).includes(actionId);
}

export function isResourceApply(actionId: string): boolean {
  return (RESOURCE_APPLY as readonly string[]).includes(actionId);
}

export function isSignalApply(actionId: string): boolean {
  return (SIGNAL_APPLY as readonly string[]).includes(actionId);
}

export function isAssetIngestApply(actionId: string): boolean {
  return (ASSET_INGEST_APPLY as readonly string[]).includes(actionId);
}

export function isAssetRefApply(actionId: string): boolean {
  return (ASSET_REF_APPLY as readonly string[]).includes(actionId);
}

export function isScriptApply(actionId: string): boolean {
  return (SCRIPT_APPLY as readonly string[]).includes(actionId);
}

export function isProjectSettingsApply(actionId: string): boolean {
  return (PROJECT_SETTINGS_APPLY as readonly string[]).includes(actionId);
}

export function isSidecarMutateApply(actionId: string): boolean {
  return (SIDECAR_MUTATE_APPLY as readonly string[]).includes(actionId);
}

export function isTransactionApply(actionId: string): boolean {
  return (TRANSACTION_APPLY as readonly string[]).includes(actionId);
}

export function isProvenEditorApply(actionId: string): boolean {
  return (
    isSceneLifecycleApply(actionId) ||
    isNodeCrudApply(actionId) ||
    isPropertyApply(actionId) ||
    isCanvasApply(actionId) ||
    isCameraApply(actionId) ||
    isTilemapApply(actionId) ||
    isAnimationApply(actionId) ||
    isUiApply(actionId) ||
    isPhysicsApply(actionId) ||
    isResourceApply(actionId) ||
    isSignalApply(actionId) ||
    isAssetRefApply(actionId) ||
    isAssetIngestApply(actionId) ||
    isScriptApply(actionId) ||
    isProjectSettingsApply(actionId) ||
    isTransactionApply(actionId)
  );
}

export function sceneNeedsDiskHash(actionId: string): boolean {
  return (SCENE_DURABLE_DISK as readonly string[]).includes(actionId);
}

function isExternalResPath(path: string): boolean {
  return (path.endsWith(".tres") || path.endsWith(".res")) && !path.includes("::");
}

function isGdPath(path: string): boolean {
  return path.endsWith(".gd") && path.startsWith("res://") && !path.includes("::");
}

export function mutationNeedsDiskHash(actionId: string, params: Record<string, unknown>): boolean {
  if (sceneNeedsDiskHash(actionId)) {
    return true;
  }
  if (actionId === "resource.create" || actionId === "resource.save") {
    return typeof params.path === "string" && isExternalResPath(params.path);
  }
  // unique=true is dest file-copy + RAM edit; the field is durable only after resource.save.
  if (actionId === "resource.duplicate") {
    return typeof params.dest === "string" && isExternalResPath(params.dest);
  }
  if (actionId === "script.write") {
    return typeof params.path === "string" && isGdPath(params.path);
  }
  if (actionId === "script.patch") {
    return params.buffer_only !== true && typeof params.path === "string" && isGdPath(params.path);
  }
  if (actionId === "script.rename") {
    return true;
  }
  if (actionId === "asset.import" || actionId === "asset.reimport") {
    return typeof params.path === "string" && params.path.startsWith("res://");
  }
  if (
    actionId === "tilemap.source" ||
    actionId === "tilemap.terrain" ||
    actionId === "tilemap.tileset"
  ) {
    return typeof params.tileset === "string" && isExternalResPath(params.tileset);
  }
  if (actionId === "animation.sprite_frames") {
    return typeof params.path === "string" && isExternalResPath(params.path);
  }
  if (actionId === "animation.library") {
    return typeof params.library_path === "string" && isExternalResPath(params.library_path);
  }
  if (actionId === "ui.theme") {
    return typeof params.theme === "string" && isExternalResPath(params.theme);
  }
  if (actionId === "physics.shape") {
    return typeof params.shape_path === "string" && isExternalResPath(params.shape_path);
  }
  if (actionId === "physics.body") {
    return typeof params.material === "string" && isExternalResPath(params.material);
  }
  if (actionId === "physics.nav_region") {
    return typeof params.navpoly_path === "string" && isExternalResPath(params.navpoly_path);
  }
  if (actionId === "job.transaction") {
    if (params.save === true) {
      return true;
    }
    const steps = Array.isArray(params.steps) ? params.steps : [];
    return steps.some((step) => {
      if (!step || typeof step !== "object" || Array.isArray(step)) {
        return false;
      }
      const action = (step as Record<string, unknown>).action;
      return action === "scene.save" || action === "scene.create" || action === "script.write";
    });
  }
  return actionId === "asset.move" || actionId === "asset.rename";
}

export function durableResPath(
  actionId: string,
  params: Record<string, unknown>,
  after?: Record<string, unknown>,
): string {
  const source = typeof params.path === "string" ? params.path : "";
  if (
    after &&
    typeof after.path === "string" &&
    after.path.startsWith("res://") &&
    (isExternalResPath(after.path) || isGdPath(after.path))
  ) {
    if (
      actionId === "asset.move" ||
      actionId === "asset.rename" ||
      actionId === "resource.duplicate" ||
      actionId === "script.rename"
    ) {
      return after.path;
    }
    if (actionId === "resource.edit" && after.path !== source) {
      return after.path;
    }
  }
  if (
    (actionId === "tilemap.source" ||
      actionId === "tilemap.terrain" ||
      actionId === "tilemap.tileset") &&
    typeof params.tileset === "string" &&
    isExternalResPath(params.tileset)
  ) {
    return params.tileset;
  }
  if (
    actionId === "animation.sprite_frames" &&
    typeof params.path === "string" &&
    isExternalResPath(params.path)
  ) {
    return params.path;
  }
  if (
    actionId === "animation.library" &&
    typeof params.library_path === "string" &&
    isExternalResPath(params.library_path)
  ) {
    return params.library_path;
  }
  if (actionId === "ui.theme" && typeof params.theme === "string" && isExternalResPath(params.theme)) {
    return params.theme;
  }
  if (
    actionId === "physics.shape" &&
    typeof params.shape_path === "string" &&
    isExternalResPath(params.shape_path)
  ) {
    return params.shape_path;
  }
  if (actionId === "physics.body" && typeof params.material === "string" && isExternalResPath(params.material)) {
    return params.material;
  }
  if (
    actionId === "physics.nav_region" &&
    typeof params.navpoly_path === "string" &&
    isExternalResPath(params.navpoly_path)
  ) {
    return params.navpoly_path;
  }
  if (actionId === "resource.duplicate" && typeof params.dest === "string") {
    return params.dest;
  }
  if (actionId === "resource.edit" && params.unique === true && typeof params.dest === "string") {
    return params.dest;
  }
  if (actionId === "asset.move" && typeof params.to === "string") {
    return params.to;
  }
  if (actionId === "job.transaction") {
    if (after && typeof after.path === "string" && after.path.startsWith("res://")) {
      return after.path;
    }
    if (after && typeof after.scene === "string" && after.scene.startsWith("res://")) {
      return after.scene;
    }
    const steps = Array.isArray(params.steps) ? params.steps : [];
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      const step = steps[i];
      if (!step || typeof step !== "object" || Array.isArray(step)) {
        continue;
      }
      const rec = step as Record<string, unknown>;
      const child = rec.params && typeof rec.params === "object" && !Array.isArray(rec.params)
        ? (rec.params as Record<string, unknown>)
        : {};
      if ((rec.action === "scene.save" || rec.action === "scene.create") && typeof child.path === "string") {
        return child.path;
      }
      if (rec.action === "script.write" && typeof child.path === "string") {
        return child.path;
      }
    }
  }
  return source;
}

export function nodeNeedsUidAfter(actionId: string): boolean {
  return (NODE_UID_AFTER as readonly string[]).includes(actionId);
}
