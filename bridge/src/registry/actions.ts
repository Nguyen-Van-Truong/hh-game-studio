/**
 * Live ActionDef catalog — one row per §5.2 verb. Schema-only; no editor handlers.
 */

import { requiredActionIds } from "./catalog.js";
import { COMMON_PARAM_ERRORS, E } from "./errors.js";
import { validateSchema } from "./schema.js";
import {
  ACTION_VERSION,
  DESCRIBE_KINDS,
  RESULT_SCHEMA,
  type ActionDef,
  type JsonSchema,
  type Policy,
  type SideEffect,
  type UndoStrategy,
} from "./types.js";
import {
  BOOL,
  DETAIL,
  DESCRIBE_INPUT,
  CURSOR,
  HASH,
  IDENT,
  INDEX,
  UID_TEXT,
  JOB_ID,
  LIMIT,
  OFFSET,
  REVIEW_REL,
  NODE_PATH,
  OS_SOURCE,
  PROP_PATH,
  RES_PATH,
  SCRIPT_TEXT,
  TEXT,
  VARIANT,
  exampleVariantBool,
  exampleVariantInt,
  exampleVariantVec2,
  obj,
} from "./shapes.js";

export interface ActionSpec {
  summary: string;
  side_effect: SideEffect;
  undo: UndoStrategy;
  required_policy: Policy;
  timeout_ms?: number;
  cancellable?: boolean;
  checkpoint_required?: boolean;
  input: JsonSchema;
  example: Record<string, unknown>;
  postcondition: string;
  extra_errors?: readonly string[];
}

const NA = new Set<UndoStrategy>(["none", "n/a"]);

function defaultTimeout(se: SideEffect): number {
  switch (se) {
    case "read":
    case "view":
      return 5_000;
    case "mutate":
      return 15_000;
    case "destructive":
      return 30_000;
    case "external":
      return 120_000;
  }
}

function defaultCancel(se: SideEffect): boolean {
  return se === "external" || se === "destructive";
}

const COMMON_ERRORS: readonly string[] = [
  ...COMMON_PARAM_ERRORS,
  E.E_UNKNOWN_ACTION,
  E.E_PROTOCOL_VERSION,
  E.E_ACTION_VERSION,
  E.E_CLIENT_ESCALATION,
  E.E_INVALID_COMMAND_ID,
  E.E_INVALID_ENVELOPE,
  E.E_UNVERIFIED,
];

function read(
  summary: string,
  post: string,
  input: JsonSchema,
  example: Record<string, unknown>,
  undo: UndoStrategy = "none",
  extra?: { timeout_ms?: number },
): ActionSpec {
  const spec: ActionSpec = {
    summary,
    side_effect: "read",
    undo,
    required_policy: "OBSERVE",
    input,
    example,
    postcondition: post,
  };
  if (extra?.timeout_ms !== undefined) {
    spec.timeout_ms = extra.timeout_ms;
  }
  return spec;
}

function view(
  summary: string,
  post: string,
  input: JsonSchema,
  example: Record<string, unknown>,
  undo: UndoStrategy = "n/a",
  extra?: { timeout_ms?: number },
): ActionSpec {
  const spec: ActionSpec = {
    summary,
    side_effect: "view",
    undo,
    required_policy: "OBSERVE",
    input,
    example,
    postcondition: post,
  };
  if (extra?.timeout_ms !== undefined) {
    spec.timeout_ms = extra.timeout_ms;
  }
  return spec;
}

const SCENE_MUTATE_ERRORS: readonly string[] = [
  E.E_CONFLICT,
  E.E_PATH,
  E.E_PAUSED,
  E.E_LEASE,
  E.E_CHECKPOINT,
];

const PROJECT_MUTATE_ERRORS: readonly string[] = [
  E.E_CONFLICT,
  E.E_PATH,
  E.E_PAUSED,
  E.E_LEASE,
  E.E_CHECKPOINT,
  E.E_POLICY,
];

const PLUGIN_NAME = {
  type: "string",
  minLength: 1,
  maxLength: 256,
  pattern: "^[A-Za-z_][A-Za-z0-9_]*$|^res://[A-Za-z0-9_./-]+$",
} as const;

function mutate(
  summary: string,
  undo: UndoStrategy,
  post: string,
  input: JsonSchema,
  example: Record<string, unknown>,
  extra?: {
    policy?: Policy;
    cancel?: boolean;
    extra_errors?: readonly string[];
    timeout_ms?: number;
    checkpoint?: boolean;
  },
): ActionSpec {
  const spec: ActionSpec = {
    summary,
    side_effect: "mutate",
    undo,
    required_policy: extra?.policy ?? "EDIT",
    input,
    example,
    postcondition: post,
  };
  if (extra?.cancel !== undefined) {
    spec.cancellable = extra.cancel;
  }
  if (extra?.extra_errors) {
    spec.extra_errors = extra.extra_errors;
  }
  if (extra?.timeout_ms !== undefined) {
    spec.timeout_ms = extra.timeout_ms;
  }
  if (extra?.checkpoint) {
    spec.checkpoint_required = true;
  }
  return spec;
}

function dest(
  summary: string,
  post: string,
  input: JsonSchema,
  example: Record<string, unknown>,
  extra?: { extra_errors?: readonly string[] },
): ActionSpec {
  const spec: ActionSpec = {
    summary,
    side_effect: "destructive",
    undo: "git_checkpoint",
    required_policy: "OWNER_AUTOPILOT",
    checkpoint_required: true,
    input,
    example,
    postcondition: post,
  };
  if (extra?.extra_errors) {
    spec.extra_errors = extra.extra_errors;
  }
  return spec;
}

function ext(
  summary: string,
  post: string,
  input: JsonSchema,
  example: Record<string, unknown>,
  undo: UndoStrategy = "job_supervisor",
): ActionSpec {
  return {
    summary,
    side_effect: "external",
    undo,
    required_policy: "OWNER_AUTOPILOT",
    input,
    example,
    postcondition: post,
  };
}

const SPECS: Record<string, ActionSpec> = {
  "capabilities.describe": {
    summary: "Discover version, class, property, method, or action metadata",
    side_effect: "read",
    undo: "none",
    required_policy: "OBSERVE",
    input: DESCRIBE_INPUT,
    example: { kind: "version" },
    postcondition: "describe_kind_payload_present",
    extra_errors: [E.E_VERSION_SKEW],
  },

  "project.inspect": read(
    "Read project name, features, and main scene",
    "project_inspect_matches_project_godot",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "project.settings": mutate(
    "Get, set, or remove a ProjectSettings key and save",
    "project_settings_save",
    "setting_equals_after_save",
    obj(["key"], {
      key: { type: "string", minLength: 1, maxLength: 256, pattern: "^[A-Za-z0-9_/.]+$" },
      value: VARIANT,
      op: { type: "string", enum: ["get", "set", "remove"] },
    }),
    { key: "application/config/name", value: exampleVariantInt(1), op: "set" },
    { extra_errors: PROJECT_MUTATE_ERRORS },
  ),
  "project.input": mutate(
    "Add or remove an InputMap action binding",
    "project_settings_save",
    "input_action_present",
    obj(["action_name"], {
      action_name: IDENT,
      keycode: IDENT,
      op: { type: "string", enum: ["add", "remove"] },
    }),
    { action_name: "move_left", keycode: "KEY_A", op: "add" },
    { extra_errors: PROJECT_MUTATE_ERRORS },
  ),
  "project.autoload": mutate(
    "Add, remove, or reorder an autoload singleton",
    "project_settings_save",
    "autoload_singleton_registered",
    obj(["name"], {
      name: IDENT,
      path: RES_PATH,
      op: { type: "string", enum: ["add", "remove", "reorder"] },
      index: INDEX,
    }),
    { name: "SaveService", path: "res://autoload/save_service.gd", op: "add" },
    { extra_errors: PROJECT_MUTATE_ERRORS },
  ),
  "project.plugin": mutate(
    "Enable or disable an editor plugin by name",
    "project_settings_save",
    "plugin_enabled_matches",
    obj(["plugin_name", "enabled"], { plugin_name: PLUGIN_NAME, enabled: BOOL }),
    { plugin_name: "hh_agent", enabled: true },
    { extra_errors: PROJECT_MUTATE_ERRORS },
  ),
  "project.doctor": read(
    "Report pin, path jail, and sidecar health (schema-only here)",
    "doctor_report_complete",
    obj(["detail"], { detail: DETAIL }),
    { detail: "full" },
  ),

  "scene.create": mutate(
    "Create a new PackedScene with a typed root via the editor plugin",
    "atomic_file",
    "scene_file_exists_with_root_type",
    obj(["path", "root_class"], {
      path: RES_PATH,
      root_class: IDENT,
      inherit_from: RES_PATH,
    }),
    { path: "res://scenes/world.tscn", root_class: "Node2D" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "scene.open": mutate(
    "Open a scene path in the editor",
    "editor_undo_redo",
    "edited_scene_path_matches",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "scene.read": read(
    "Read the edited or disk scene tree summary",
    "scene_tree_summary_matches",
    obj(["path", "detail"], {
      path: RES_PATH,
      detail: DETAIL,
      limit: LIMIT,
      cursor: CURSOR,
    }),
    { path: "res://scenes/world.tscn", detail: "short" },
  ),
  "scene.save": mutate(
    "Save the edited scene to disk via EditorInterface",
    "atomic_file",
    "scene_disk_hash_matches_pack",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "scene.close": dest(
    "Close a scene tab (checkpoint first if dirty)",
    "scene_not_in_open_list",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "scene.instantiate": mutate(
    "Instance a PackedScene under a parent",
    "editor_undo_redo",
    "instance_child_exists",
    obj(["scene", "packed", "parent"], {
      scene: RES_PATH,
      packed: RES_PATH,
      parent: NODE_PATH,
    }),
    {
      scene: "res://scenes/world.tscn",
      packed: "res://scenes/key.tscn",
      parent: "World",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "scene.dependencies": read(
    "List scene ExtResource / UID dependencies",
    "dependency_list_complete",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world.tscn" },
  ),
  "scene.list_tabs": read(
    "List open scene tabs from EditorInterface.get_open_scenes",
    "open_scene_tabs_match",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "scene.activate": mutate(
    "Switch the edited scene tab so edited_scene matches path",
    "editor_undo_redo",
    "edited_scene_path_matches",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "scene.save_as": mutate(
    "Save the edited scene to a new path via EditorInterface.save_scene_as",
    "atomic_file",
    "scene_disk_hash_matches_pack",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world_copy.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "scene.reload": mutate(
    "Reload a scene from disk via EditorInterface.reload_scene_from_path",
    "editor_undo_redo",
    "scene_tree_matches_disk",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),

  "node.add": mutate(
    "Add a child node with type and name",
    "editor_undo_redo",
    "node_exists_under_parent",
    obj(["scene", "parent", "class_name", "name"], {
      scene: RES_PATH,
      parent: NODE_PATH,
      class_name: IDENT,
      name: IDENT,
    }),
    {
      scene: "res://scenes/world.tscn",
      parent: "World",
      class_name: "Node2D",
      name: "Prop",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.remove": dest(
    "Remove a node from the packed scene",
    "node_path_absent",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/world.tscn", node_path: "World/Prop" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.rename": mutate(
    "Rename a node without breaking unique-name lookups",
    "editor_undo_redo",
    "node_name_equals",
    obj(["scene", "node_path", "name"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      name: IDENT,
    }),
    { scene: "res://scenes/world.tscn", node_path: "World/Temp", name: "Door" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.reparent": mutate(
    "Reparent a node, optionally keeping global transform",
    "editor_undo_redo",
    "node_parent_equals",
    obj(["scene", "node_path", "new_parent"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      new_parent: NODE_PATH,
      keep_global_transform: BOOL,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "World/Props/Door",
      new_parent: "World/Doors",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.reorder": mutate(
    "Move a node to a sibling index",
    "editor_undo_redo",
    "node_index_equals",
    obj(["scene", "node_path", "index"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      index: INDEX,
    }),
    { scene: "res://scenes/world.tscn", node_path: "World/HUD", index: 3 },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.duplicate": mutate(
    "Duplicate a node and its owned children",
    "editor_undo_redo",
    "duplicate_sibling_exists",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/world.tscn", node_path: "World/Prop" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.group": mutate(
    "Add or remove a persistent group membership",
    "editor_undo_redo",
    "node_group_membership",
    obj(["scene", "node_path", "group", "op"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      group: IDENT,
      op: { type: "string", enum: ["add", "remove"] },
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "World/Door",
      group: "interactable",
      op: "add",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.make_local": mutate(
    "Make an instanced PackedScene local if a proven Editor API exists",
    "editor_undo_redo",
    "instance_is_local",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/world.tscn", node_path: "World/Key" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "node.undo": mutate(
    "Undo one or more EditorUndoRedo actions on the edited scene",
    "editor_undo_redo",
    "history_undo_applied",
    obj(["scene"], { scene: RES_PATH, count: INDEX }),
    { scene: "res://scenes/world.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS, timeout_ms: 60_000 },
  ),
  "node.redo": mutate(
    "Redo one or more EditorUndoRedo actions on the edited scene",
    "editor_undo_redo",
    "history_redo_applied",
    obj(["scene"], { scene: RES_PATH, count: INDEX }),
    { scene: "res://scenes/world.tscn" },
    { extra_errors: SCENE_MUTATE_ERRORS, timeout_ms: 60_000 },
  ),
  "node.query": read(
    "Query nodes by type, group, or path prefix",
    "query_hits_match_tree",
    obj(["scene", "by"], {
      scene: RES_PATH,
      by: { type: "string", enum: ["type", "group", "path"] },
      class_name: IDENT,
      group: IDENT,
      prefix: NODE_PATH,
      limit: LIMIT,
      cursor: CURSOR,
    }),
    { scene: "res://scenes/world.tscn", by: "group", group: "interactable" },
  ),

  "property.get": read(
    "Read one Inspector property",
    "property_value_matches_get",
    obj(["scene", "node_path", "property"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      property: PROP_PATH,
    }),
    { scene: "res://scenes/world.tscn", node_path: "Player", property: "position" },
  ),
  "property.set": {
    summary: "Set one property via UndoRedo (Variant codec)",
    side_effect: "mutate",
    undo: "editor_undo_redo",
    required_policy: "EDIT",
    input: obj(["scene", "node_path", "property", "value"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      property: PROP_PATH,
      value: VARIANT,
      expected_old_hash: HASH,
    }),
    example: {
      scene: "res://scenes/world.tscn",
      node_path: "Player",
      property: "position",
      value: exampleVariantVec2(16, 32),
    },
    postcondition: "property_get_equals_set",
    extra_errors: [...SCENE_MUTATE_ERRORS, E.E_INVALID_VARIANT, E.E_UNKNOWN_VARIANT_TYPE],
  },
  "property.batch": {
    summary: "Set several properties in one UndoRedo action",
    side_effect: "mutate",
    undo: "editor_undo_redo",
    required_policy: "EDIT",
    input: obj(["scene", "items"], {
      scene: RES_PATH,
      items: {
        type: "array",
        minItems: 1,
        maxItems: 64,
        items: obj(["node_path", "property", "value"], {
          node_path: NODE_PATH,
          property: PROP_PATH,
          value: VARIANT,
          expected_old_hash: HASH,
        }),
      },
    }),
    example: {
      scene: "res://scenes/world.tscn",
      items: [
        {
          node_path: "Player",
          property: "visible",
          value: exampleVariantBool(true),
        },
      ],
    },
    postcondition: "batch_properties_match",
    extra_errors: [...SCENE_MUTATE_ERRORS, E.E_INVALID_VARIANT, E.E_UNKNOWN_VARIANT_TYPE],
  },
  "property.reset": mutate(
    "Reset a property to its class default",
    "editor_undo_redo",
    "property_is_default",
    obj(["scene", "node_path", "property"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      property: PROP_PATH,
    }),
    { scene: "res://scenes/world.tscn", node_path: "Player", property: "modulate" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),

  "resource.create": mutate(
    "Create a new Resource of a given class",
    "atomic_file",
    "resource_file_exists",
    obj(["path", "class_name"], {
      path: RES_PATH,
      class_name: IDENT,
      builtin: BOOL,
      scene: RES_PATH,
      node_path: NODE_PATH,
      property: PROP_PATH,
      local_to_scene: BOOL,
    }),
    { path: "res://res/tile_set.tres", class_name: "TileSet" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "resource.load": read(
    "Load a resource path or UID and return a summary",
    "resource_load_ok",
    obj(["path"], { path: RES_PATH }),
    { path: "res://res/tile_set.tres" },
  ),
  "resource.assign": mutate(
    "Assign a resource to a node property",
    "editor_undo_redo",
    "resource_property_path_equals",
    obj(["scene", "node_path", "property", "resource"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      property: PROP_PATH,
      resource: RES_PATH,
      uid: UID_TEXT,
      class_name: IDENT,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "Player/Sprite2D",
      property: "texture",
      resource: "res://assets/player.png",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "resource.duplicate": mutate(
    "Duplicate a resource, optionally local-to-scene",
    "editor_undo_redo",
    "duplicate_resource_uid_distinct",
    obj(["path", "dest"], { path: RES_PATH, dest: RES_PATH, local_to_scene: BOOL }),
    { path: "res://res/shape.tres", dest: "res://res/shape_2.tres" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "resource.edit": mutate(
    "Edit a resource field (Variant codec)",
    "editor_undo_redo",
    "resource_field_equals",
    obj(["path", "property", "value"], {
      path: RES_PATH,
      property: PROP_PATH,
      value: VARIANT,
      shared: BOOL,
      unique: BOOL,
      scene: RES_PATH,
      node_path: NODE_PATH,
      dest: RES_PATH,
      assign_property: PROP_PATH,
    }),
    {
      path: "res://res/tile_set.tres",
      property: "tile_size",
      value: exampleVariantInt(16),
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "resource.save": mutate(
    "Save a resource to disk",
    "atomic_file",
    "resource_disk_hash_matches",
    obj(["path"], { path: RES_PATH }),
    { path: "res://res/tile_set.tres" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "resource.uid": read(
    "Resolve a Godot UID to a resource path",
    "uid_maps_to_path",
    obj(["uid"], { uid: UID_TEXT }),
    { uid: "uid://b8k2example" },
  ),

  "signal.list": read(
    "List signals on a node class or instance",
    "signal_list_complete",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/world.tscn", node_path: "World/Door" },
  ),
  "signal.connect": mutate(
    "Connect a signal to a callable",
    "editor_undo_redo",
    "connection_present",
    obj(["scene", "source", "signal", "target", "method"], {
      scene: RES_PATH,
      source: NODE_PATH,
      signal: IDENT,
      target: NODE_PATH,
      method: IDENT,
    }),
    {
      scene: "res://scenes/world.tscn",
      source: "World/Door/Area2D",
      signal: "body_entered",
      target: "World/Door",
      method: "_on_body_entered",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "signal.disconnect": mutate(
    "Disconnect a signal from a callable",
    "editor_undo_redo",
    "connection_absent",
    obj(["scene", "source", "signal", "target", "method"], {
      scene: RES_PATH,
      source: NODE_PATH,
      signal: IDENT,
      target: NODE_PATH,
      method: IDENT,
    }),
    {
      scene: "res://scenes/world.tscn",
      source: "World/Door/Area2D",
      signal: "body_entered",
      target: "World/Door",
      method: "_on_body_entered",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "signal.inspect": read(
    "Inspect one signal's connections",
    "connection_list_matches",
    obj(["scene", "node_path", "signal"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      signal: IDENT,
    }),
    { scene: "res://scenes/world.tscn", node_path: "World/Door", signal: "body_entered" },
  ),

  "script.read": read(
    "Read a GDScript file",
    "script_text_matches_disk",
    obj(["path"], {
      path: RES_PATH,
      limit: LIMIT,
      cursor: CURSOR,
    }),
    { path: "res://scripts/player.gd" },
  ),
  "script.write": mutate(
    "Atomically write a typed GDScript file",
    "atomic_file",
    "script_disk_equals_write",
    obj(["path", "contents"], {
      path: RES_PATH,
      contents: SCRIPT_TEXT,
      expected_hash: HASH,
      base_hash: HASH,
    }),
    { path: "res://scripts/player.gd", contents: "extends CharacterBody2D" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "script.patch": mutate(
    "Apply a bounded text patch to a script",
    "atomic_file",
    "script_patch_applied",
    obj(["path", "find", "replace"], {
      path: RES_PATH,
      find: SCRIPT_TEXT,
      replace: SCRIPT_TEXT,
      start_line: { type: "integer", minimum: 1, maximum: 100000 },
      end_line: { type: "integer", minimum: 1, maximum: 100000 },
      buffer_only: BOOL,
      expected_hash: HASH,
      base_hash: HASH,
    }),
    {
      path: "res://scripts/player.gd",
      find: "speed := 80",
      replace: "speed := 120",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "script.validate": read(
    "Validate GDScript without writing",
    "script_validate_clean",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scripts/player.gd" },
  ),
  "script.attach": mutate(
    "Attach a script to a node",
    "editor_undo_redo",
    "node_script_path_equals",
    obj(["scene", "node_path", "path"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      path: RES_PATH,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "Player",
      path: "res://scripts/player.gd",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "script.detach": mutate(
    "Detach a script from a node",
    "editor_undo_redo",
    "node_script_path_equals",
    obj(["scene", "node_path"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "Player",
    },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "script.rename": mutate(
    "Rename a GDScript file and rewrite references",
    "atomic_file",
    "script_renamed",
    obj(["path", "name"], {
      path: RES_PATH,
      name: IDENT,
      expected_hash: HASH,
      base_hash: HASH,
    }),
    { path: "res://scripts/player.gd", name: "hero" },
    { extra_errors: SCENE_MUTATE_ERRORS, checkpoint: true },
  ),
  "script.open_at": view(
    "Open a script in the editor at a line",
    "script_editor_line_visible",
    obj(["path", "line"], {
      path: RES_PATH,
      line: { type: "integer", minimum: 1, maximum: 100000 },
    }),
    { path: "res://scripts/player.gd", line: 12 },
  ),
  "script.diagnostics": read(
    "Read script parser/linter diagnostics",
    "diagnostics_list_complete",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scripts/player.gd" },
  ),

  "asset.import": mutate(
    "Stage an external source, sniff it, and atomically import under res://",
    "atomic_file",
    "import_sidecar_exists",
    obj(["path"], {
      path: RES_PATH,
      source: OS_SOURCE,
      license: TEXT,
    }),
    { path: "res://assets/tiles/floor.png", source: "C:/tmp/floor.png" },
    { extra_errors: [...SCENE_MUTATE_ERRORS, E.E_BUSY], timeout_ms: 15_000 },
  ),
  "asset.reimport": mutate(
    "Reimport one dirty asset and wait for the import sidecar",
    "atomic_file",
    "import_timestamp_updated",
    obj(["path"], { path: RES_PATH }),
    { path: "res://assets/tiles/floor.png" },
    { extra_errors: [...SCENE_MUTATE_ERRORS, E.E_BUSY], timeout_ms: 15_000 },
  ),
  "asset.move": mutate(
    "Move an asset and rewrite references",
    "atomic_file",
    "old_path_absent_new_path_present",
    obj(["from", "to"], { from: RES_PATH, to: RES_PATH, rewrite_plan: BOOL }),
    { from: "res://assets/key.png", to: "res://assets/key_gold.png" },
    { extra_errors: SCENE_MUTATE_ERRORS, checkpoint: true },
  ),
  "asset.rename": mutate(
    "Rename an asset in place",
    "atomic_file",
    "asset_renamed",
    obj(["path", "name"], { path: RES_PATH, name: IDENT, rewrite_plan: BOOL }),
    { path: "res://assets/key.png", name: "key_gold" },
    { extra_errors: SCENE_MUTATE_ERRORS, checkpoint: true },
  ),
  "asset.delete": dest(
    "Quarantine/delete an unreferenced asset",
    "asset_absent_or_quarantined",
    obj(["path"], { path: RES_PATH, rewrite_plan: BOOL }),
    { path: "res://assets/tmp_PLACEHOLDER.png" },
    { extra_errors: SCENE_MUTATE_ERRORS },
  ),
  "asset.dependencies": read(
    "List reverse dependencies of an asset",
    "dependency_owners_listed",
    obj(["path"], { path: RES_PATH }),
    { path: "res://assets/player.png" },
  ),
  "asset.preview": read(
    "Return a preview handle for an asset",
    "preview_handle_present",
    obj(["path"], { path: RES_PATH }),
    { path: "res://assets/player.png" },
  ),

  "tilemap.tileset": mutate(
    "Assign or create a TileSet on a TileMapLayer",
    "editor_undo_redo",
    "tileset_assigned",
    obj(["scene", "node_path", "tileset"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      tileset: RES_PATH,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "World/Ground",
      tileset: "res://res/tile_set.tres",
    },
  ),
  "tilemap.source": mutate(
    "Add or configure a TileSetAtlasSource",
    "editor_undo_redo",
    "tileset_source_present",
    obj(["tileset", "source_id", "texture"], {
      tileset: RES_PATH,
      source_id: INDEX,
      texture: RES_PATH,
    }),
    { tileset: "res://res/tile_set.tres", source_id: 0, texture: "res://assets/tiles/atlas.png" },
  ),
  "tilemap.terrain": mutate(
    "Configure a terrain set on a TileSet",
    "editor_undo_redo",
    "terrain_set_present",
    obj(["tileset", "terrain_name"], { tileset: RES_PATH, terrain_name: IDENT }),
    { tileset: "res://res/tile_set.tres", terrain_name: "dirt" },
  ),
  "tilemap.layer": mutate(
    "Configure a TileMapLayer (name, z, enabled)",
    "editor_undo_redo",
    "tilemap_layer_matches",
    obj(["scene", "node_path", "enabled"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      enabled: BOOL,
    }),
    { scene: "res://scenes/world.tscn", node_path: "World/Ground", enabled: true },
  ),
  "tilemap.cell": mutate(
    "Set one tile cell",
    "editor_undo_redo",
    "cell_atlas_coords_match",
    obj(["scene", "node_path", "x", "y", "source_id", "atlas_x", "atlas_y"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      x: INDEX,
      y: INDEX,
      source_id: INDEX,
      atlas_x: INDEX,
      atlas_y: INDEX,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "World/Ground",
      x: 4,
      y: 3,
      source_id: 0,
      atlas_x: 1,
      atlas_y: 0,
    },
  ),
  "tilemap.fill": mutate(
    "Fill a rectangle of cells",
    "editor_undo_redo",
    "fill_region_matches",
    obj(["scene", "node_path", "x", "y", "w", "h", "source_id"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      x: INDEX,
      y: INDEX,
      w: { type: "integer", minimum: 1, maximum: 512 },
      h: { type: "integer", minimum: 1, maximum: 512 },
      source_id: INDEX,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "World/Ground",
      x: 0,
      y: 0,
      w: 8,
      h: 8,
      source_id: 0,
    },
  ),
  "tilemap.stamp": mutate(
    "Stamp a pattern at a cell origin",
    "editor_undo_redo",
    "stamp_cells_match",
    obj(["scene", "node_path", "x", "y", "pattern"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      x: INDEX,
      y: INDEX,
      pattern: IDENT,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "World/Ground",
      x: 2,
      y: 2,
      pattern: "tree_clump",
    },
  ),
  "tilemap.query": read(
    "Read cells in a region",
    "cell_query_matches_layer",
    obj(["scene", "node_path", "x", "y", "w", "h"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      x: INDEX,
      y: INDEX,
      w: { type: "integer", minimum: 1, maximum: 512 },
      h: { type: "integer", minimum: 1, maximum: 512 },
    }),
    { scene: "res://scenes/world.tscn", node_path: "World/Ground", x: 0, y: 0, w: 4, h: 4 },
  ),

  "animation.library": mutate(
    "Add or select an AnimationLibrary",
    "editor_undo_redo",
    "animation_library_present",
    obj(["scene", "node_path", "library"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      library: IDENT,
    }),
    { scene: "res://scenes/world.tscn", node_path: "Player/Anim", library: "player" },
  ),
  "animation.animation": mutate(
    "Create or update a named Animation",
    "editor_undo_redo",
    "animation_named_exists",
    obj(["scene", "node_path", "name", "length_sec"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      name: IDENT,
      length_sec: { type: "number", minimum: 0.01, maximum: 3600 },
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "Player/Anim",
      name: "walk",
      length_sec: 0.4,
    },
  ),
  "animation.track": mutate(
    "Add a track to an Animation",
    "editor_undo_redo",
    "animation_track_present",
    obj(["scene", "node_path", "animation", "track_path"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      animation: IDENT,
      track_path: NODE_PATH,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "Player/Anim",
      animation: "walk",
      track_path: "Sprite2D:frame",
    },
  ),
  "animation.key": mutate(
    "Insert a key on an animation track",
    "editor_undo_redo",
    "animation_key_at_time",
    obj(["scene", "node_path", "animation", "track", "time_sec", "value"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      animation: IDENT,
      track: INDEX,
      time_sec: { type: "number", minimum: 0, maximum: 3600 },
      value: VARIANT,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "Player/Anim",
      animation: "walk",
      track: 0,
      time_sec: 0.2,
      value: exampleVariantInt(2),
    },
  ),
  "animation.state_machine": mutate(
    "Edit an AnimationNodeStateMachine transition",
    "editor_undo_redo",
    "state_machine_transition_present",
    obj(["scene", "node_path", "from", "to"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      from: IDENT,
      to: IDENT,
    }),
    {
      scene: "res://scenes/world.tscn",
      node_path: "Player/Tree",
      from: "idle",
      to: "walk",
    },
  ),
  "animation.preview": view(
    "Preview an animation in the editor",
    "animation_preview_playing",
    obj(["scene", "node_path", "animation"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      animation: IDENT,
    }),
    { scene: "res://scenes/world.tscn", node_path: "Player/Anim", animation: "walk" },
  ),

  "ui.control": mutate(
    "Set Control size/position flags",
    "editor_undo_redo",
    "control_layout_flags_match",
    obj(["scene", "node_path", "preset"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      preset: {
        type: "string",
        enum: ["top_left", "center", "full_rect", "bottom_wide"],
      },
    }),
    { scene: "res://scenes/hud.tscn", node_path: "HUD/Label", preset: "top_left" },
  ),
  "ui.theme": mutate(
    "Assign a Theme resource to a Control",
    "editor_undo_redo",
    "control_theme_path_equals",
    obj(["scene", "node_path", "theme"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      theme: RES_PATH,
    }),
    { scene: "res://scenes/hud.tscn", node_path: "HUD", theme: "res://ui/theme.tres" },
  ),
  "ui.layout": mutate(
    "Set container layout properties",
    "editor_undo_redo",
    "container_layout_matches",
    obj(["scene", "node_path", "separation"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      separation: { type: "integer", minimum: 0, maximum: 256 },
    }),
    { scene: "res://scenes/hud.tscn", node_path: "HUD/VBox", separation: 8 },
  ),
  "ui.anchor": mutate(
    "Set Control anchors and offsets",
    "editor_undo_redo",
    "control_anchors_match",
    obj(["scene", "node_path", "anchor_left", "anchor_top"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      anchor_left: { type: "number", minimum: 0, maximum: 1 },
      anchor_top: { type: "number", minimum: 0, maximum: 1 },
    }),
    { scene: "res://scenes/hud.tscn", node_path: "HUD/Label", anchor_left: 0, anchor_top: 0 },
  ),
  "ui.focus": view(
    "Move UI focus to a Control",
    "focus_owner_matches",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/hud.tscn", node_path: "HUD/StartButton" },
  ),
  "ui.accessibility": read(
    "Read accessibility name/hint on a Control",
    "accessibility_fields_present",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/hud.tscn", node_path: "HUD/StartButton" },
  ),

  "editor.state": read(
    "Read editor selection, main screen, pause flag, and activity dock",
    "editor_state_snapshot",
    obj(["detail"], {
      detail: DETAIL,
      cursor: CURSOR,
      limit: LIMIT,
      actor: IDENT,
      scene: { type: "string", minLength: 1, maxLength: 256 },
      status: { type: "string", enum: ["planned", "verified", "failed"] },
      reload: BOOL,
    }),
    { detail: "short" },
  ),
  "observer.timeline": read(
    "Read the activity dock timeline page (virtualized, redacted)",
    "observer_timeline_snapshot",
    obj(["detail"], {
      detail: DETAIL,
      cursor: CURSOR,
      limit: LIMIT,
      actor: IDENT,
      scene: { type: "string", minLength: 1, maxLength: 256 },
      status: { type: "string", enum: ["planned", "verified", "failed"] },
      reload: BOOL,
    }),
    { detail: "short" },
    "none",
    { timeout_ms: 15_000 },
  ),
  "observer.append": view(
    "Append synthetic observer rows (test helper; not a scene mutation)",
    "observer_rows_appended",
    obj(["count"], {
      count: { type: "integer", minimum: 1, maximum: 10000 },
      actor: IDENT,
      scene: { type: "string", minLength: 1, maxLength: 256 },
    }),
    { count: 1 },
    "n/a",
    { timeout_ms: 15_000 },
  ),
  "observer.focus": read(
    "Read live EditorSelection / Inspector / Script / FileSystem focus",
    "observer_focus_snapshot",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "observer.overlay": read(
    "Read the live viewport overlay presentation model",
    "observer_overlay_snapshot",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "observer.scheduler": view(
    "Read presentation scheduler snapshot; optional stress records cell events without UndoRedo",
    "observer_scheduler_snapshot",
    obj(["detail"], {
      detail: DETAIL,
      stress: { type: "integer", minimum: 0, maximum: 10000 },
      unique_keys: BOOL,
      replay: BOOL,
      command_id: { type: "string", minLength: 26, maxLength: 26 },
    }),
    { detail: "short" },
    "n/a",
    { timeout_ms: 15_000 },
  ),
  "observer.review": read(
    "Read the Review Center milestone card snapshot (same card as godot.review card)",
    "observer_review_snapshot",
    obj(["detail"], {
      detail: DETAIL,
      path: REVIEW_REL,
      id: IDENT,
      reload: BOOL,
    }),
    { detail: "short" },
    "none",
    { timeout_ms: 15_000 },
  ),
  "review.card": read(
    "Read a milestone review card from .hh-agent/review/ (honest missing/corrupt)",
    "review_card_snapshot",
    obj(["detail"], {
      detail: DETAIL,
      path: REVIEW_REL,
      id: IDENT,
      reload: BOOL,
    }),
    { detail: "short" },
    "none",
    { timeout_ms: 15_000 },
  ),
  "review.diff": read(
    "Read one page of a large unified diff (offset/limit; never dump megabytes)",
    "review_diff_page",
    obj(["offset", "limit"], {
      offset: OFFSET,
      limit: LIMIT,
      path: REVIEW_REL,
      id: IDENT,
    }),
    { offset: 0, limit: 50 },
    "none",
    { timeout_ms: 15_000 },
  ),
  "review.open": read(
    "Open the review before/after/diff view without mutating the project",
    "review_view_open",
    obj(["view"], {
      view: { type: "string", enum: ["before", "after", "diff"] },
      path: REVIEW_REL,
      id: IDENT,
      offset: OFFSET,
      limit: LIMIT,
    }),
    { view: "diff" },
    "none",
    { timeout_ms: 15_000 },
  ),
  "review.replay": view(
    "Replay a selected action as presentation-only overlay (not a router mutate)",
    "replay_started",
    obj(["command_id"], {
      command_id: { type: "string", minLength: 26, maxLength: 26 },
    }),
    { command_id: "01ARZ3NDEKTSV4RRFFQ69G5FAV" },
  ),
  "editor.select": view(
    "Present a node, resource, script, or filesystem path in the editor",
    "selection_paths_match",
    obj(["scene", "node_path"], {
      scene: RES_PATH,
      node_path: NODE_PATH,
      uid: { type: "string", minLength: 1, maxLength: 128, pattern: "^[A-Za-z0-9_.:-]+$" },
      property: PROP_PATH,
      resource_path: RES_PATH,
      script_path: RES_PATH,
      script_line: { type: "integer", minimum: 1, maximum: 100000 },
      script_column: { type: "integer", minimum: 0, maximum: 10000 },
      filesystem_path: RES_PATH,
      screen: { type: "string", enum: ["2D", "3D", "Script", "Game", "AssetLib"] },
      hide_inspector: BOOL,
      use_external_editor: BOOL,
    }),
    { scene: "res://scenes/world.tscn", node_path: "Player" },
  ),
  "editor.focus": view(
    "Focus the Inspector on an object",
    "inspector_shows_object",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/world.tscn", node_path: "Player" },
  ),
  "editor.main_screen": view(
    "Switch the editor main screen",
    "main_screen_equals",
    obj(["screen"], {
      screen: { type: "string", enum: ["2D", "3D", "Script", "Game", "AssetLib"] },
    }),
    { screen: "2D" },
  ),
  "editor.frame_view": view(
    "Frame the 2D view on a node",
    "view_framed_on_node",
    obj(["scene", "node_path"], { scene: RES_PATH, node_path: NODE_PATH }),
    { scene: "res://scenes/world.tscn", node_path: "Player" },
  ),
  "editor.replay": view(
    "Play a presentation replay of a prior action",
    "replay_started",
    obj(["command_id"], {
      command_id: { type: "string", minLength: 26, maxLength: 26 },
    }),
    { command_id: "01ARZ3NDEKTSV4RRFFQ69G5FAV" },
  ),
  "editor.pause": mutate(
    "Request the agent Pause gate",
    "job_supervisor",
    "pause_gate_ack",
    obj(["op"], { op: { type: "string", enum: ["pause", "resume"] } }),
    { op: "pause" },
    { policy: "EDIT", cancel: false },
  ),

  "play.start": ext(
    "Start Play in a separate game process",
    "play_process_running",
    obj(["scene", "mode"], {
      scene: RES_PATH,
      mode: { type: "string", enum: ["play", "debug"] },
    }),
    { scene: "res://scenes/world.tscn", mode: "play" },
  ),
  "play.stop": ext(
    "Stop the running Play process",
    "play_process_stopped",
    obj(["reason"], {
      reason: { type: "string", enum: ["user", "test", "error"] },
    }),
    { reason: "user" },
  ),
  "play.restart": ext(
    "Restart Play from the same scene",
    "play_process_restarted",
    obj(["scene"], { scene: RES_PATH }),
    { scene: "res://scenes/world.tscn" },
  ),
  "play.debug": ext(
    "Start Play with the debugger attached",
    "play_debug_attached",
    obj(["scene"], { scene: RES_PATH }),
    { scene: "res://scenes/world.tscn" },
  ),
  "play.status": read(
    "Read Play process status",
    "play_status_known",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "play.logs": read(
    "Read recent Play logs",
    "play_logs_returned",
    obj(["limit"], { limit: LIMIT }),
    { limit: 50 },
  ),

  "input.action": ext(
    "Inject an InputMap action press/release into Play",
    "input_action_injected",
    obj(["action_name", "phase"], {
      action_name: IDENT,
      phase: { type: "string", enum: ["press", "release"] },
    }),
    { action_name: "interact", phase: "press" },
  ),
  "input.key": ext(
    "Inject a keyboard event into Play",
    "input_key_injected",
    obj(["keycode", "phase"], {
      keycode: IDENT,
      phase: { type: "string", enum: ["press", "release"] },
    }),
    { keycode: "KEY_E", phase: "press" },
  ),
  "input.mouse": ext(
    "Inject a mouse button/move into Play",
    "input_mouse_injected",
    obj(["button", "x", "y"], {
      button: { type: "string", enum: ["left", "right", "middle", "none"] },
      x: { type: "number", minimum: 0, maximum: 8192 },
      y: { type: "number", minimum: 0, maximum: 8192 },
    }),
    { button: "left", x: 640, y: 360 },
  ),
  "input.touch": ext(
    "Inject a touch event into Play",
    "input_touch_injected",
    obj(["index", "x", "y", "pressed"], {
      index: INDEX,
      x: { type: "number", minimum: 0, maximum: 8192 },
      y: { type: "number", minimum: 0, maximum: 8192 },
      pressed: BOOL,
    }),
    { index: 0, x: 100, y: 100, pressed: true },
  ),
  "input.sequence": ext(
    "Inject a timed input sequence",
    "input_sequence_accepted",
    obj(["steps"], {
      steps: {
        type: "array",
        minItems: 1,
        maxItems: 64,
        items: obj(["action_name", "phase"], {
          action_name: IDENT,
          phase: { type: "string", enum: ["press", "release"] },
        }),
      },
    }),
    { steps: [{ action_name: "move_right", phase: "press" }] },
  ),
  "input.release_all": ext(
    "Release every injected input",
    "all_injected_inputs_released",
    obj(["scope"], { scope: { type: "string", enum: ["all", "keyboard", "mouse"] } }),
    { scope: "all" },
  ),

  "runtime.tree": read(
    "Read the remote Play scene tree",
    "remote_tree_snapshot",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "runtime.node": read(
    "Read one remote node",
    "remote_node_snapshot",
    obj(["node_path"], { node_path: NODE_PATH }),
    { node_path: "Player" },
  ),
  "runtime.state": read(
    "Read named runtime state keys",
    "runtime_state_keys_present",
    obj(["key"], { key: IDENT }),
    { key: "hp" },
  ),
  "runtime.signal": read(
    "Read recent remote signal events",
    "runtime_signal_log",
    obj(["signal", "limit"], { signal: IDENT, limit: LIMIT }),
    { signal: "body_entered", limit: 20 },
  ),
  "runtime.time": read(
    "Read Play time scale and ticks",
    "runtime_time_snapshot",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "runtime.freeze": ext(
    "Freeze or unfreeze Play time",
    "runtime_frozen_matches",
    obj(["frozen", "reason"], {
      frozen: BOOL,
      reason: { type: "string", enum: ["test", "user"] },
    }),
    { frozen: true, reason: "test" },
  ),
  "runtime.step": ext(
    "Step Play a fixed number of physics frames",
    "runtime_stepped_frames",
    obj(["frames"], { frames: { type: "integer", minimum: 1, maximum: 600 } }),
    { frames: 1 },
  ),
  "runtime.screenshot": read(
    "Capture a Play screenshot handle",
    "screenshot_artifact_present",
    obj(["scale"], { scale: { type: "number", minimum: 0.25, maximum: 2 } }),
    { scale: 1 },
  ),
  "runtime.perf": read(
    "Read Play perf counters",
    "perf_counters_present",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),

  "test.define": mutate(
    "Define a gameplay test case",
    "atomic_file",
    "test_definition_saved",
    obj(["name", "steps"], {
      name: IDENT,
      steps: {
        type: "array",
        minItems: 1,
        maxItems: 128,
        items: { type: "string", minLength: 1, maxLength: 256 },
      },
    }),
    { name: "pickup_key", steps: ["start", "move_to_key", "interact"] },
  ),
  "test.run": ext(
    "Run a named test against Play",
    "test_run_recorded",
    obj(["name"], { name: IDENT }),
    { name: "pickup_key" },
  ),
  "test.assert": mutate(
    "Record a structured assertion (not a screenshot-only pass)",
    "atomic_file",
    "assertion_recorded",
    obj(["name", "expect"], { name: IDENT, expect: IDENT }),
    { name: "has_key", expect: "true" },
  ),
  "test.report": read(
    "Read the last test report",
    "test_report_present",
    obj(["name"], { name: IDENT }),
    { name: "pickup_key" },
  ),
  "test.evidence": read(
    "List evidence URIs for a test",
    "evidence_index_present",
    obj(["name"], { name: IDENT }),
    { name: "pickup_key" },
  ),
  "test.baseline": mutate(
    "Write or refresh a test baseline",
    "atomic_file",
    "baseline_hash_saved",
    obj(["name", "hash"], { name: IDENT, hash: HASH }),
    { name: "pickup_key", hash: "deadbeefcafebabe" },
  ),

  "export.preset": mutate(
    "Create or update an export preset",
    "atomic_file",
    "export_preset_present",
    obj(["name", "platform"], {
      name: IDENT,
      platform: { type: "string", enum: ["WindowsDesktop", "Linux", "Web"] },
    }),
    { name: "win64", platform: "WindowsDesktop" },
  ),
  "export.validate": read(
    "Validate an export preset without building",
    "export_preset_valid",
    obj(["name"], { name: IDENT }),
    { name: "win64" },
  ),
  "export.build": ext(
    "Build an export preset as a supervised job",
    "export_job_accepted",
    obj(["name"], { name: IDENT }),
    { name: "win64" },
  ),
  "export.cancel": dest(
    "Cancel an export job",
    "export_job_cancelled",
    obj(["job_id"], { job_id: JOB_ID }),
    { job_id: "export-win64-1" },
  ),
  "export.artifacts": read(
    "List export artifacts",
    "export_artifact_list",
    obj(["name"], { name: IDENT }),
    { name: "win64" },
  ),

  "git.status": read(
    "Read project-scoped git status",
    "git_status_parsed",
    obj(["detail"], { detail: DETAIL }),
    { detail: "short" },
  ),
  "git.diff": read(
    "Read a project-scoped git diff",
    "git_diff_text",
    obj(["path"], { path: RES_PATH }),
    { path: "res://scenes/world.tscn" },
  ),
  "git.checkpoint": mutate(
    "Create a recoverability checkpoint",
    "git_checkpoint",
    "checkpoint_ref_present",
    obj(["message"], {
      message: TEXT,
      paths: {
        type: "array",
        minItems: 1,
        maxItems: 64,
        items: RES_PATH,
      },
    }),
    { message: "before destructive node.remove", paths: ["res://scenes/world.tscn"] },
  ),
  "git.revert_checkpoint": dest(
    "Revert the project to a checkpoint",
    "tree_matches_checkpoint",
    obj(["ref"], { ref: { type: "string", minLength: 7, maxLength: 64, pattern: "^[A-Za-z0-9_./-]+$" } }),
    { ref: "hh-ckpt/abc1234" },
  ),

  "job.status": read(
    "Read one job's state",
    "job_status_known",
    obj(["job_id"], { job_id: JOB_ID }),
    { job_id: "export-win64-1" },
  ),
  "job.list": read(
    "List recent jobs",
    "job_list_returned",
    obj(["limit"], { limit: LIMIT }),
    { limit: 20 },
  ),
  "job.cancel": dest(
    "Cancel a running job at a safe-point",
    "job_cancelled",
    obj(["job_id"], { job_id: JOB_ID }),
    { job_id: "export-win64-1" },
  ),
  "job.wait": mutate(
    "Wait for a job to reach a terminal state",
    "job_supervisor",
    "job_terminal_state",
    obj(["job_id", "timeout_sec"], {
      job_id: JOB_ID,
      timeout_sec: { type: "integer", minimum: 1, maximum: 3600 },
    }),
    { job_id: "export-win64-1", timeout_sec: 30 },
    { cancel: true },
  ),
  "job.transaction": mutate(
    "Stage scene/node/property/script/save as one logical job (checkpoint + one UndoRedo + one final save; not OS-global atomic)",
    "git_checkpoint",
    "transaction_steps_verified",
    obj(["steps"], {
      steps: {
        type: "array",
        minItems: 1,
        maxItems: 32,
        items: obj(["action", "params"], {
          action: {
            type: "string",
            enum: [
              "scene.create",
              "scene.open",
              "scene.save",
              "node.add",
              "property.set",
              "property.batch",
              "script.write",
            ],
          },
          params: { type: "object", additionalProperties: true },
        }),
      },
      save: BOOL,
    }),
    {
      steps: [
        { action: "scene.create", params: { path: "res://scenes/world.tscn", root_class: "Node2D" } },
        {
          action: "node.add",
          params: {
            scene: "res://scenes/world.tscn",
            parent: ".",
            class_name: "Node2D",
            name: "Player",
          },
        },
        {
          action: "property.set",
          params: {
            scene: "res://scenes/world.tscn",
            node_path: "Player",
            property: "visible",
            value: exampleVariantBool(true),
          },
        },
        {
          action: "script.write",
          params: { path: "res://scripts/player.gd", contents: "extends Node2D\n" },
        },
        { action: "scene.save", params: { path: "res://scenes/world.tscn" } },
      ],
      save: true,
    },
    { extra_errors: SCENE_MUTATE_ERRORS, timeout_ms: 60_000, checkpoint: true, cancel: true },
  ),
};

function expand(id: string, spec: ActionSpec): ActionDef {
  const dot = id.indexOf(".");
  const group = id.slice(0, dot);
  const verb = id.slice(dot + 1);
  const se = spec.side_effect;
  if ((se === "read" || se === "view") !== NA.has(spec.undo)) {
    throw new Error(
      `ActionDef ${id}: undo ${spec.undo} is not allowed for side_effect ${se}`,
    );
  }
  if (spec.input.additionalProperties !== false) {
    throw new Error(`ActionDef ${id}: input_schema.additionalProperties must be false`);
  }
  if (se === "destructive" && spec.checkpoint_required !== true) {
    throw new Error(`ActionDef ${id}: destructive actions require checkpoint_required`);
  }
  if (!spec.postcondition || spec.postcondition.length < 3) {
    throw new Error(`ActionDef ${id}: postcondition name required`);
  }
  const issue = validateSchema(spec.input, spec.example);
  if (issue) {
    throw new Error(
      `ActionDef ${id}: example_params fail schema: ${issue.code} ${issue.path} ${issue.message}`,
    );
  }
  if (id === "capabilities.describe") {
    const kind = spec.example.kind;
    if (kind !== "version") {
      throw new Error("capabilities.describe example_params must use kind=version");
    }
    for (const k of DESCRIBE_KINDS) {
      if (typeof k !== "string") {
        throw new Error("DESCRIBE_KINDS drifted");
      }
    }
  }
  return {
    id,
    group,
    verb,
    method: `godot.${group}`,
    action_version: ACTION_VERSION,
    summary: spec.summary,
    side_effect: spec.side_effect,
    undo: spec.undo,
    timeout_ms: spec.timeout_ms ?? defaultTimeout(se),
    cancellable: spec.cancellable ?? defaultCancel(se),
    required_policy: spec.required_policy,
    checkpoint_required: spec.checkpoint_required ?? se === "destructive",
    input_schema: spec.input,
    output_schema: RESULT_SCHEMA,
    error_codes: [...COMMON_ERRORS, ...(spec.extra_errors ?? [])],
    postcondition: spec.postcondition,
    example_params: spec.example,
  };
}

export function loadActionDefs(): ActionDef[] {
  const ids = requiredActionIds();
  const missing = ids.filter((id) => SPECS[id] === undefined);
  const extras = Object.keys(SPECS).filter((id) => !ids.includes(id));
  if (missing.length > 0 || extras.length > 0) {
    throw new Error(
      `ActionDef catalog drift: missing=${missing.join(",")} extra=${extras.join(",")}`,
    );
  }
  return ids.map((id) => {
    const spec = SPECS[id];
    if (!spec) {
      throw new Error(`missing spec ${id}`);
    }
    return expand(id, spec);
  });
}

export function describeExample(kind: (typeof DESCRIBE_KINDS)[number]): Record<string, unknown> {
  switch (kind) {
    case "version":
      return { kind: "version" };
    case "class":
      return { kind: "class", class_name: "Node2D" };
    case "property":
      return { kind: "property", class_name: "Node2D", property_name: "position" };
    case "method":
      return { kind: "method", class_name: "Node2D", method_name: "get_position" };
    case "action":
      return { kind: "action", action_id: "node.add" };
  }
}

export function describeMissing(kind: (typeof DESCRIBE_KINDS)[number]): Record<string, unknown> {
  switch (kind) {
    case "version":
      return {};
    case "class":
      return { kind: "class" };
    case "property":
      return { kind: "property", class_name: "Node2D" };
    case "method":
      return { kind: "method", class_name: "Node2D" };
    case "action":
      return { kind: "action" };
  }
}

export function describeWrongType(kind: (typeof DESCRIBE_KINDS)[number]): Record<string, unknown> {
  switch (kind) {
    case "version":
      return { kind: 0 };
    case "class":
      return { kind: "class", class_name: 0 };
    case "property":
      return { kind: "property", class_name: "Node2D", property_name: 0 };
    case "method":
      return { kind: "method", class_name: "Node2D", method_name: 0 };
    case "action":
      return { kind: "action", action_id: 0 };
  }
}

export function describeOutOfBounds(kind: (typeof DESCRIBE_KINDS)[number]): Record<string, unknown> {
  switch (kind) {
    case "version":
      return { kind: "widget" };
    case "class":
      return { kind: "class", class_name: "" };
    case "property":
      return { kind: "property", class_name: "Node2D", property_name: "" };
    case "method":
      return { kind: "method", class_name: "Node2D", method_name: "" };
    case "action":
      return { kind: "action", action_id: "??" };
  }
}
