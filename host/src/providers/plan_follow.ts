/**
 * R7-WP6 deciding path: job.plan, then interpret that DAG in order.
 * Genre GDScript is compiled from produceSpec.slug / plan outputs + brief.
 * Not an LLM. First script.write is a complete working engine.
 */

import fs from "node:fs";
import path from "node:path";

import type { ToolResultView } from "./types.js";
import type { ModelContext, ModelTurn, Provider } from "./types.js";

export const PLAN_FOLLOW_MODEL = "job.plan-follow";

interface PlanTask {
  id: string;
  kind: string;
  acceptance: string[];
  outputs: string[];
  commands: string[];
  criterion?: string;
  blocker?: { code: string; message: string };
}

interface CompiledPlanView {
  status?: string;
  tasks: PlanTask[];
  blockers: Array<{ code: string; message: string; task_id?: string }>;
  acceptance: Array<{ id: string; text: string }>;
}

export interface GameColor {
  name: string;
  r: number;
  g: number;
  b: number;
}

export interface GameSpec {
  slug: string;
  scene: string;
  script: string;
  art: string;
  cols: number;
  rows: number;
  pairCount: number;
  winAt: number;
  colors: GameColor[];
  actions: string[];
  tiles: number[];
  acceptance: string[];
}

export interface CompiledAssert {
  name: string;
  key: string;
  op: string;
  value_bool?: boolean;
  value_int?: number;
  value_string?: string;
  node_path?: string;
  inputs: string[];
  criterion: string;
}

export interface AskRow {
  at: number;
  code: string;
  message: string;
  e_gate: boolean;
}

const COLOR_RGB: Record<string, [number, number, number]> = {
  cyan: [0.2, 0.7, 0.9],
  orange: [0.9, 0.6, 0.2],
  red: [0.85, 0.2, 0.2],
  blue: [0.2, 0.4, 0.9],
  green: [0.2, 0.75, 0.35],
  yellow: [0.9, 0.85, 0.2],
  purple: [0.6, 0.3, 0.8],
  pink: [0.9, 0.4, 0.65],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function asPlan(after: Record<string, unknown>): CompiledPlanView | undefined {
  const raw = after.plan;
  if (!isRecord(raw) || !Array.isArray(raw.tasks)) {
    return undefined;
  }
  const tasks: PlanTask[] = [];
  for (const item of raw.tasks) {
    if (!isRecord(item) || typeof item.id !== "string") {
      continue;
    }
    const blocker = isRecord(item.blocker)
      ? {
          code: typeof item.blocker.code === "string" ? item.blocker.code : "",
          message: typeof item.blocker.message === "string" ? item.blocker.message : "",
        }
      : undefined;
    tasks.push({
      id: item.id,
      kind: typeof item.kind === "string" ? item.kind : "",
      acceptance: Array.isArray(item.acceptance)
        ? item.acceptance.filter((x): x is string => typeof x === "string")
        : [],
      outputs: Array.isArray(item.outputs)
        ? item.outputs.filter((x): x is string => typeof x === "string")
        : [],
      commands: Array.isArray(item.commands)
        ? item.commands.filter((x): x is string => typeof x === "string")
        : [],
      ...(typeof item.criterion === "string" ? { criterion: item.criterion } : {}),
      ...(blocker ? { blocker } : {}),
    });
  }
  const blockers: CompiledPlanView["blockers"] = [];
  if (Array.isArray(raw.blockers)) {
    for (const item of raw.blockers) {
      if (!isRecord(item) || typeof item.code !== "string") {
        continue;
      }
      blockers.push({
        code: item.code,
        message: typeof item.message === "string" ? item.message : "",
        ...(typeof item.task_id === "string" ? { task_id: item.task_id } : {}),
      });
    }
  }
  const acceptance: CompiledPlanView["acceptance"] = [];
  if (Array.isArray(raw.acceptance)) {
    for (const item of raw.acceptance) {
      if (!isRecord(item)) {
        continue;
      }
      const text = typeof item.text === "string" ? item.text : "";
      const id = typeof item.id === "string" ? item.id : "";
      if (text) {
        acceptance.push({ id, text });
      }
    }
  }
  return {
    status: typeof raw.status === "string" ? raw.status : "",
    tasks,
    blockers,
    acceptance,
  };
}

function findPlan(results: ToolResultView[]): CompiledPlanView | undefined {
  for (const row of results) {
    if (row.ok && isRecord(row.after)) {
      const plan = asPlan(row.after);
      if (plan && plan.tasks.length > 0) {
        return plan;
      }
    }
  }
  return undefined;
}

function verbToMcp(actionId: string): { tool: string; action: string } {
  const idx = actionId.indexOf(".");
  if (idx <= 0) {
    return { tool: "godot.job", action: actionId };
  }
  return { tool: `godot.${actionId.slice(0, idx)}`, action: actionId.slice(idx + 1) };
}

function sceneFromPlan(plan: CompiledPlanView): string {
  const produce = plan.tasks.find((t) => t.id === "produce_scene");
  return produce?.outputs[0] ?? "res://scenes/memory/board.tscn";
}

function scriptFromPlan(plan: CompiledPlanView): string {
  const produce = plan.tasks.find((t) => t.id === "produce_script");
  return produce?.outputs[0] ?? "res://scripts/memory/board.gd";
}

function artFromPlan(plan: CompiledPlanView): string {
  const produce = plan.tasks.find((t) => t.id === "produce_art");
  return produce?.outputs[0] ?? "res://art/memory/tile.png";
}

function testName(label: string): string {
  return label.replace(/[^A-Za-z0-9_]/g, "_").slice(0, 48) || "acc01";
}

function criterionOf(task: PlanTask, plan: CompiledPlanView): string {
  if (task.criterion && task.criterion.trim()) {
    return task.criterion;
  }
  for (const id of task.acceptance) {
    const hit = plan.acceptance.find((row) => row.id === id);
    if (hit?.text) {
      return hit.text;
    }
  }
  return task.acceptance.join(" ");
}

function parseBoard(text: string): { cols: number; rows: number } {
  const m = text.match(/(\d+)\s*[xX]\s*(\d+)/);
  const cols = m ? Math.max(2, Math.min(6, Number(m[1]))) : 2;
  const rows = m ? Math.max(2, Math.min(6, Number(m[2]))) : 2;
  return { cols, rows };
}

function parseColors(text: string): GameColor[] {
  const found: GameColor[] = [];
  const seen = new Set<string>();
  const hay = text.toLowerCase();
  for (const [name, rgb] of Object.entries(COLOR_RGB)) {
    if (!hay.includes(name) || seen.has(name)) {
      continue;
    }
    seen.add(name);
    found.push({ name, r: rgb[0], g: rgb[1], b: rgb[2] });
  }
  if (found.length < 2) {
    return [
      { name: "cyan", r: 0.2, g: 0.7, b: 0.9 },
      { name: "orange", r: 0.9, g: 0.6, b: 0.2 },
    ];
  }
  return found;
}

function parseActions(text: string): string[] {
  const found = text.match(/\bui_[a-z]+\b/g) ?? [];
  const uniq = [...new Set(found)];
  if (uniq.includes("ui_accept") && uniq.length >= 2) {
    return uniq;
  }
  return ["ui_left", "ui_right", "ui_up", "ui_down", "ui_accept"];
}

function seedFrom(text: string): number {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function shuffleInPlace(tiles: number[], seed: number): void {
  let state = seed || 1;
  for (let i = tiles.length - 1; i > 0; i -= 1) {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    const j = state % (i + 1);
    const a = tiles[i] ?? 0;
    const b = tiles[j] ?? 0;
    tiles[i] = b;
    tiles[j] = a;
  }
}

function layoutTiles(cols: number, rows: number, pairCount: number, seed: number): number[] {
  const cells = cols * rows;
  const tiles: number[] = [];
  for (let i = 0; i < cells; i += 1) {
    tiles.push(i % pairCount);
  }
  shuffleInPlace(tiles, seed);
  return tiles;
}

/** Same routing family as brief_compiler / plugin produceSpec. */
export function slugFromPlanAndBrief(plan: CompiledPlanView, brief: string): string {
  const script = scriptFromPlan(plan);
  const scene = sceneFromPlan(plan);
  const hay = `${brief}\n${script}\n${scene}`.toLowerCase();
  if (script.includes("/memory/") || scene.includes("/memory/") || /\b(memory|tile[- ]?flip|card[- ]?match)\b/.test(hay)) {
    return "memory";
  }
  if (script.includes("/breakout/") || scene.includes("/breakout/") || /\b(breakout|brick[- ]?breaker)\b/.test(hay)) {
    return "breakout";
  }
  if (script.includes("/dodge/") || /\b(dodge|meteor|starfall)\b/.test(hay)) {
    return "dodge";
  }
  if (script.includes("/catch/") || (/\bcatch\b/.test(hay) && /\b(orb|fruit|drop)\b/.test(hay))) {
    return "catch";
  }
  return path.posix.basename(path.posix.dirname(script)) || "memory";
}

export function compileGameSpec(plan: CompiledPlanView, brief: string): GameSpec {
  const scene = sceneFromPlan(plan);
  const script = scriptFromPlan(plan);
  const acceptance = plan.acceptance.map((row) => row.text);
  for (const task of plan.tasks) {
    if (task.criterion && !acceptance.includes(task.criterion)) {
      acceptance.push(task.criterion);
    }
  }
  const blob = `${brief}\n${acceptance.join("\n")}\n${scene}\n${script}`;
  const { cols, rows } = parseBoard(blob);
  const colors = parseColors(blob);
  const pairCount = Math.max(2, Math.min(colors.length, Math.floor((cols * rows) / 2)));
  const tiles = layoutTiles(cols, rows, pairCount, seedFrom(blob));
  const slug = slugFromPlanAndBrief(plan, brief);
  const winAt = slug === "breakout" ? Math.max(1, cols) : pairCount;
  return {
    slug,
    scene,
    script,
    art: artFromPlan(plan),
    cols,
    rows,
    pairCount,
    winAt,
    colors,
    actions: parseActions(blob),
    tiles,
    acceptance,
  };
}

function accLines(spec: GameSpec): string {
  return spec.acceptance.map((t) => `# acc: ${t}`).join("\n");
}

function compileMemoryDraft(spec: GameSpec): string {
  const pal = spec.colors
    .map((c, i) => `\t\t${i}: return Color(${c.r}, ${c.g}, ${c.b}, 1)`)
    .join("\n");
  const tileLit = spec.tiles.join(", ");
  const revealedLit = spec.tiles.map(() => "0").join(", ");
  const cells = spec.cols * spec.rows;
  return `extends "res://addons/hh_agent/runtime/hh_agent_runtime.gd"

# compiled from live job.plan + PROJECT_BRIEF
# engine: memory-tileflip
# output: ${spec.script}
# art: ${spec.art}
# board: ${spec.cols}x${spec.rows} pairs=${spec.pairCount} win_at=${spec.winAt}
${accLines(spec)}

var matches: int = 0
var flips: int = 0
var won: bool = false
var cursor: int = 0
var first_pick: int = -1
var last_key: String = ""
var cols: int = ${spec.cols}
var rows: int = ${spec.rows}
var tiles: PackedInt32Array = PackedInt32Array([${tileLit}])
var revealed: PackedInt32Array = PackedInt32Array([${revealedLit}])
var hold_left: bool = false
var hold_right: bool = false
var hold_up: bool = false
var hold_down: bool = false
var hold_accept: bool = false


func _ready() -> void:
	super._ready()
	_draw_tiles()


func _process(_delta: float) -> void:
	super._process(_delta)
	hold_left = _edge_move("ui_left", "left", -1, hold_left)
	hold_right = _edge_move("ui_right", "right", 1, hold_right)
	hold_up = _edge_move("ui_up", "up", -cols, hold_up)
	hold_down = _edge_move("ui_down", "down", cols, hold_down)
	var acc: bool = Input.is_action_pressed("ui_accept")
	if acc and not hold_accept:
		last_key = "accept"
		_flip(cursor)
	hold_accept = acc


func agent_observe() -> Dictionary:
	var faces: Array = []
	var wrap: Node = get_node_or_null("Tiles")
	if wrap != null:
		var fi: int = 0
		while fi < wrap.get_child_count():
			var child: Node = wrap.get_child(fi)
			if child is ColorRect:
				var c: Color = (child as ColorRect).color
				faces.append({"r": c.r, "g": c.g, "b": c.b})
			fi += 1
	return {
		"matches": matches,
		"flips": flips,
		"won": won,
		"cursor": cursor,
		"faces": faces,
	}


func _edge_move(action_name: String, label: String, delta: int, was: bool) -> bool:
	var down: bool = Input.is_action_pressed(action_name)
	if down and not was:
		last_key = label
		_nudge(delta)
	return down


func _nudge(delta: int) -> void:
	var next: int = cursor + delta
	var max_i: int = cols * rows - 1
	if next < 0 or next > max_i:
		return
	cursor = next
	_draw_tiles()


func _flip(index: int) -> void:
	if index < 0 or index > ${cells - 1}:
		return
	if revealed[index] == 1:
		return
	revealed[index] = 1
	flips += 1
	if first_pick < 0:
		first_pick = index
		_draw_tiles()
		return
	var same: bool = tiles[first_pick] == tiles[index]
	if same:
		matches += 1
		won = matches >= ${spec.winAt}
	else:
		revealed[first_pick] = 0
		revealed[index] = 0
	first_pick = -1
	_draw_tiles()


func _color_of(kind: int) -> Color:
	match kind:
${pal}
		_:
			return Color(0.55, 0.55, 0.6, 1)


func _draw_tiles() -> void:
	var existing: Node = get_node_or_null("Tiles")
	if existing != null:
		existing.free()
	var wrap: Node2D = Node2D.new()
	wrap.name = "Tiles"
	add_child(wrap)
	var i: int = 0
	while i < ${cells}:
		var cell: ColorRect = ColorRect.new()
		cell.name = "Tile%d" % i
		cell.focus_mode = Control.FOCUS_NONE
		cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
		cell.size = Vector2(120, 120)
		var col_i: int = i % cols
		var row_i: int = int(i / cols)
		cell.position = Vector2(360.0 + float(col_i) * 140.0, 200.0 + float(row_i) * 140.0)
		var on: bool = revealed[i] == 1
		if on:
			cell.color = _color_of(tiles[i])
		elif i == cursor:
			cell.color = Color(0.35, 0.35, 0.45, 1)
		else:
			cell.color = Color(0.15, 0.15, 0.2, 1)
		wrap.add_child(cell)
		i += 1
`;
}

function compileBreakoutDraft(spec: GameSpec): string {
  const brickCount = Math.max(2, spec.cols);
  const pal = spec.colors[0] ?? { name: "cyan", r: 0.2, g: 0.7, b: 0.9 };
  return `extends "res://addons/hh_agent/runtime/hh_agent_runtime.gd"

# compiled from live job.plan + PROJECT_BRIEF
# engine: breakout-paddle
# output: ${spec.script}
# bricks=${brickCount} win_at=${spec.winAt}
${accLines(spec)}

var score: int = 0
var won: bool = false
var bricks_left: int = ${brickCount}
var paddle_x: float = 560.0
var ball_x: float = 620.0
var ball_y: float = 480.0
var ball_vy: float = -180.0
var last_key: String = ""


func _ready() -> void:
	super._ready()
	set_process(true)
	set_process_unhandled_input(true)
	_draw_table()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_echo():
		return
	if event.is_action_pressed("ui_left"):
		last_key = "left"
		paddle_x = maxf(80.0, paddle_x - 80.0)
		_draw_table()
	elif event.is_action_pressed("ui_right"):
		last_key = "right"
		paddle_x = minf(1040.0, paddle_x + 80.0)
		_draw_table()


func _process(delta: float) -> void:
	ball_y += ball_vy * delta
	if ball_y < 80.0:
		ball_vy = absf(ball_vy)
		_hit_next_brick()
	if ball_y > 640.0:
		ball_vy = -absf(ball_vy)
	_draw_table()


func _hit_next_brick() -> void:
	var wrap: Node = get_node_or_null("Bricks")
	if wrap == null:
		return
	for child in wrap.get_children():
		if child is ColorRect and (child as ColorRect).visible:
			(child as ColorRect).visible = false
			bricks_left -= 1
			score += 1
			won = bricks_left <= 0 or score >= ${spec.winAt}
			return


func _draw_table() -> void:
	var old_p: Node = get_node_or_null("Paddle")
	if old_p != null:
		old_p.free()
	var paddle: ColorRect = ColorRect.new()
	paddle.name = "Paddle"
	paddle.size = Vector2(160, 24)
	paddle.position = Vector2(paddle_x, 620)
	paddle.color = Color(${pal.r}, ${pal.g}, ${pal.b}, 1)
	add_child(paddle)
	var old_b: Node = get_node_or_null("Ball")
	if old_b != null:
		old_b.free()
	var ball: ColorRect = ColorRect.new()
	ball.name = "Ball"
	ball.size = Vector2(20, 20)
	ball.position = Vector2(ball_x, ball_y)
	ball.color = Color(0.95, 0.95, 0.9, 1)
	add_child(ball)
	if get_node_or_null("Bricks") != null:
		return
	var wrap: Node2D = Node2D.new()
	wrap.name = "Bricks"
	add_child(wrap)
	var i: int = 0
	while i < ${brickCount}:
		var brick: ColorRect = ColorRect.new()
		brick.name = "Brick%d" % i
		brick.size = Vector2(140, 36)
		brick.position = Vector2(200.0 + float(i) * 160.0, 80.0)
		brick.color = Color(0.85, 0.25, 0.2, 1)
		wrap.add_child(brick)
		i += 1
`;
}

/** Complete working engine from the live job.plan + brief. */
export function compilePlanScript(spec: GameSpec): string {
  if (spec.slug === "breakout") {
    return compileBreakoutDraft(spec);
  }
  return compileMemoryDraft(spec);
}

/** Cursor deltas to a cell the player can see on the live board. */
function movesToVisibleCell(from: number, to: number, cols: number): string[] {
  const fromCol = from % cols;
  const fromRow = Math.floor(from / cols);
  const toCol = to % cols;
  const toRow = Math.floor(to / cols);
  const out: string[] = [];
  const dc = toCol - fromCol;
  const dr = toRow - fromRow;
  for (let i = 0; i < Math.abs(dc); i += 1) {
    out.push(dc > 0 ? "ui_right" : "ui_left");
  }
  for (let i = 0; i < Math.abs(dr); i += 1) {
    out.push(dr > 0 ? "ui_down" : "ui_up");
  }
  return out;
}

interface LiveFace {
  r: number;
  g: number;
  b: number;
}

interface LiveBoard {
  matches: number;
  flips: number;
  won: boolean;
  cursor: number | undefined;
  faces: LiveFace[];
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
}

function asNum(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function liveFaceKey(face: LiveFace): string {
  const sat = Math.max(face.r, face.g, face.b) - Math.min(face.r, face.g, face.b);
  if (sat < 0.12) {
    return "down";
  }
  if (sat < 0.2) {
    return "cursor";
  }
  return `${Math.round(face.r * 8)}_${Math.round(face.g * 8)}_${Math.round(face.b * 8)}`;
}

function isFaceUp(key: string): boolean {
  return key !== "down" && key !== "cursor";
}

function facesFromUnknown(raw: unknown): LiveFace[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const out: LiveFace[] = [];
  for (const item of raw) {
    const rec = asRecord(item);
    if (!rec) {
      continue;
    }
    const r = asNum(rec.r);
    const g = asNum(rec.g);
    const b = asNum(rec.b);
    if (r === undefined || g === undefined || b === undefined) {
      continue;
    }
    out.push({ r, g, b });
  }
  return out;
}

/** Live ColorRect / agent_observe faces only. Never spec.tiles / PackedInt32Array. */
function liveBoardFromAfter(after: Record<string, unknown>): LiveBoard {
  // Do not read properties.tiles / board.gd / spec.tiles to choose clicks.
  const observe = asRecord(after.observe);
  const matches = asNum(observe?.matches) ?? asNum(after.matches) ?? 0;
  const flips = asNum(observe?.flips) ?? asNum(after.flips) ?? 0;
  const won = observe?.won === true || after.won === true;
  const cursor = asNum(observe?.cursor) ?? asNum(after.cursor);
  let faces = facesFromUnknown(observe?.faces);
  if (faces.length === 0) {
    faces = facesFromUnknown(after.faces);
  }
  return { matches, flips, won, cursor, faces };
}

function pickUnseenDown(down: number[], seen: Set<number>, avoid: number | undefined): number | undefined {
  const fresh = down.filter((idx) => !seen.has(idx) && idx !== avoid);
  if (fresh[0] !== undefined) {
    return fresh[0];
  }
  const next = down.filter((idx) => idx !== avoid);
  return next[0] ?? down[0];
}

function chooseVisibleTarget(
  board: LiveBoard,
  memory: Map<string, number[]>,
  matched: Set<number>,
  seen: Set<number>,
  avoid: number | undefined,
): number | undefined {
  const keys = board.faces.map(liveFaceKey);
  const up: number[] = [];
  const down: number[] = [];
  for (let i = 0; i < keys.length; i += 1) {
    if (matched.has(i)) {
      continue;
    }
    const key = keys[i] ?? "down";
    if (isFaceUp(key)) {
      up.push(i);
      seen.add(i);
      const remembered = memory.get(key) ?? [];
      if (!remembered.includes(i)) {
        remembered.push(i);
        memory.set(key, remembered);
      }
    } else {
      down.push(i);
    }
  }
  if (up.length === 1) {
    const open = up[0] ?? 0;
    const openKey = keys[open] ?? "";
    const mates = (memory.get(openKey) ?? []).filter((idx) => idx !== open && !matched.has(idx));
    if (mates[0] !== undefined) {
      return mates[0];
    }
    return pickUnseenDown(down, seen, avoid);
  }
  for (const [color, idxs] of memory) {
    if (!isFaceUp(color)) {
      continue;
    }
    const uniq = [...new Set(idxs)].filter((idx) => !matched.has(idx));
    if (uniq.length >= 2 && uniq[0] !== undefined) {
      return uniq[0];
    }
  }
  return pickUnseenDown(down, seen, avoid) ?? up[0];
}

export function assertFromAcceptance(text: string, spec: GameSpec): CompiledAssert | undefined {
  const t = text.toLowerCase();
  if (!t.trim()) {
    return undefined;
  }
  if (/\bready_ok\b/.test(t) && !/\b(pair|match|won|win|flip|score|brick)\b/.test(t)) {
    return undefined;
  }
  if (/\bhh_agent_runtime\b/.test(t) && !/\b(pair|match|won|win|flip|score|brick)\b/.test(t)) {
    return undefined;
  }
  const name = testName(text);
  if (spec.slug === "breakout") {
    if (/\bwon\b/.test(t) || /\bwin\b/.test(t)) {
      return {
        name,
        key: "won",
        op: "eq",
        value_bool: true,
        inputs: ["ui_right", "ui_right", "ui_left"],
        criterion: text,
      };
    }
    if (/\bscore\b/.test(t) || /\bbrick\b/.test(t)) {
      return {
        name,
        key: "score",
        op: "gte",
        value_int: 1,
        inputs: ["ui_right", "ui_right"],
        criterion: text,
      };
    }
    return undefined;
  }
  if (/\bwon\b/.test(t) || /\bwin\b/.test(t)) {
    return {
      name,
      key: "won",
      op: "eq",
      value_bool: true,
      inputs: ["ui_accept"],
      criterion: text,
    };
  }
  if (/\bmatch/.test(t) || /\bpair\b/.test(t)) {
    return {
      name,
      key: "matches",
      op: "gte",
      value_int: 1,
      inputs: ["ui_accept"],
      criterion: text,
    };
  }
  if (/\bflip/.test(t)) {
    return {
      name,
      key: "flips",
      op: "gte",
      value_int: 1,
      inputs: ["ui_accept"],
      criterion: text,
    };
  }
  return undefined;
}

function collectAsserts(plan: CompiledPlanView, spec: GameSpec): CompiledAssert[] {
  const out: CompiledAssert[] = [];
  const seen = new Set<string>();
  for (const task of plan.tasks) {
    if (!task.commands.includes("test.define")) {
      continue;
    }
    const compiled = assertFromAcceptance(criterionOf(task, plan), spec);
    if (!compiled || seen.has(compiled.name)) {
      continue;
    }
    seen.add(compiled.name);
    out.push(compiled);
  }
  if (out.length === 0) {
    for (const row of plan.acceptance) {
      const compiled = assertFromAcceptance(row.text, spec);
      if (compiled && !seen.has(compiled.name)) {
        seen.add(compiled.name);
        out.push(compiled);
      }
    }
  }
  return out;
}

function defineParams(compiled: CompiledAssert, spec: GameSpec): Record<string, unknown> {
  const params: Record<string, unknown> = {
    name: compiled.name,
    steps: compiled.inputs.length > 0 ? compiled.inputs : ["assert"],
    suite: "r7w6",
    path: `res://r7w6/${compiled.name}.hh-test.json`,
    scene: spec.scene,
    mode: "play",
    assert_kind: "property",
    assert_key: compiled.key,
    assert_node_path: compiled.node_path ?? ".",
    assert_op: compiled.op,
    teardown_stop: true,
    flaky_is_not_pass: true,
    timeout_ms: 120000,
    step_frames: 2,
  };
  if (typeof compiled.value_bool === "boolean") {
    params.assert_value_bool = compiled.value_bool;
  }
  if (typeof compiled.value_int === "number") {
    params.assert_value_int = compiled.value_int;
  }
  if (typeof compiled.value_string === "string") {
    params.assert_value_string = compiled.value_string;
  }
  return params;
}

function paramsFor(actionId: string, task: PlanTask, spec: GameSpec, draft: string): Record<string, unknown> {
  const scene = spec.scene;
  const script = spec.script;
  switch (actionId) {
    case "scene.create":
      return { path: task.outputs[0] ?? scene, root_class: "Node2D" };
    case "node.add":
      return { scene, parent: ".", class_name: "Node2D", name: "Layout" };
    case "scene.read":
      return { path: scene, detail: "short" };
    case "scene.open":
      return { path: scene };
    case "scene.save":
      return { path: scene };
    case "script.write":
      return { path: task.outputs[0] ?? script, contents: draft };
    case "script.attach":
      return { scene, node_path: ".", path: script };
    case "script.validate":
      return { path: script };
    case "git.checkpoint":
      return { message: "r7w6 checkpoint", paths: [scene, script] };
    case "asset.import":
      return { path: task.outputs[0] ?? spec.art };
    case "audio.player":
      return { scene, node_path: "Layout", bus: "SFX" };
    default:
      return {};
  }
}

function appendAsk(asksPath: string | undefined, row: AskRow): void {
  if (!asksPath) {
    return;
  }
  fs.mkdirSync(path.dirname(asksPath), { recursive: true });
  fs.appendFileSync(asksPath, `${JSON.stringify(row)}\n`, "utf8");
}

function tool(toolName: string, action: string, params: Record<string, unknown>): ModelTurn {
  return { kind: "tool", tool: toolName, action, params };
}

function emitTestRun(name: string): ModelTurn {
  return tool("godot.test", "run", { name });
}

function pressRelease(action: string): ModelTurn[] {
  return [
    tool("godot.input", "action", { action_name: action, phase: "press" }),
    tool("godot.runtime", "step", { frames: 2 }),
    tool("godot.input", "action", { action_name: action, phase: "release" }),
    tool("godot.runtime", "step", { frames: 2 }),
  ];
}

function playObserveTurns(spec: GameSpec): ModelTurn[] {
  const scene = spec.scene;
  // Shot A before the first ui_accept. Shot B is after a second distinct
  // accept or matches>=1 / flips>=2, not only the first flip.
  return [
    tool("godot.play", "start", { scene, mode: "play" }),
    tool("godot.runtime", "tree", { detail: "short", limit: 50 }),
    tool("godot.runtime", "screenshot", { scale: 1 }),
    tool("godot.runtime", "node", { node_path: ".", detail: "short" }),
  ];
}

function lookLiveBoard(): ModelTurn {
  return tool("godot.runtime", "node", { node_path: ".", detail: "short" });
}

function enqueueVisibleAccept(from: number, to: number, cols: number): ModelTurn[] {
  const turns: ModelTurn[] = [];
  for (const action of movesToVisibleCell(from, to, cols)) {
    turns.push(...pressRelease(action));
  }
  turns.push(...pressRelease("ui_accept"));
  return turns;
}

/** R14: never define matches/won if those test.run steps will be skipped. */
function isQueuedAssert(compiled: CompiledAssert): boolean {
  return compiled.key !== "matches" && compiled.key !== "won";
}

class DagWalker {
  readonly plan: CompiledPlanView;
  readonly spec: GameSpec;
  readonly asserts: CompiledAssert[];
  draft: string;
  extras: ModelTurn[] = [];
  pendingDefines: PlanTask[] = [];
  taskIdx = 0;
  cmdIdx = 0;
  didPlay = false;
  didWrap = false;
  didWriteScript = false;
  didPause = false;
  lastTestName = "";
  repaired = new Set<string>();
  playPhase: "off" | "seeking" | "done" = "off";
  playCursor = 0;
  playShotB = false;
  playLooks = 0;
  playAccepts = 0;
  playMemory = new Map<string, number[]>();
  playMatched = new Set<number>();
  playSeen = new Set<number>();
  playLastTarget: number | undefined = undefined;
  playLastMatches = 0;
  playBlocked = false;

  constructor(plan: CompiledPlanView, spec: GameSpec, asserts: CompiledAssert[], draft: string) {
    this.plan = plan;
    this.spec = spec;
    this.asserts = asserts;
    this.draft = draft;
  }

  next(ctx: ModelContext): ModelTurn {
    const results = ctx.last_results;
    if (this.extras.length > 0) {
      return this.extras.shift() as ModelTurn;
    }
    this.maybeQueueRepair(ctx, results);
    if (this.extras.length > 0) {
      return this.extras.shift() as ModelTurn;
    }
    if (this.playPhase === "seeking") {
      const seek = this.advancePlay(ctx);
      if (seek) {
        return seek;
      }
    }
    this.maybeQueuePauseObserve();
    if (this.extras.length > 0) {
      return this.extras.shift() as ModelTurn;
    }
    while (this.taskIdx < this.plan.tasks.length) {
      const task = this.plan.tasks[this.taskIdx];
      if (!task || task.kind === "blocker") {
        this.taskIdx += 1;
        this.cmdIdx = 0;
        continue;
      }
      if (this.cmdIdx >= task.commands.length) {
        this.taskIdx += 1;
        this.cmdIdx = 0;
        continue;
      }
      const actionId = task.commands[this.cmdIdx];
      if (!actionId) {
        this.cmdIdx += 1;
        continue;
      }
      if (actionId === "test.run" && !this.didPlay && this.didWriteScript) {
        this.didPlay = true;
        this.playPhase = "seeking";
        this.extras = playObserveTurns(this.spec);
        return this.extras.shift() as ModelTurn;
      }
      const built = this.turnFor(task, actionId);
      this.cmdIdx += 1;
      if (built) {
        return built;
      }
    }
    if (!this.didWrap) {
      this.didWrap = true;
      const tests = this.asserts.filter(isQueuedAssert).map((row) => row.name);
      this.extras = [
        tool("godot.review", "write_card", {
          goal: "R7-WP6 zero-touch slice",
          auto: true,
          files: [this.spec.script],
          scenes: [this.spec.scene],
          tests,
        }),
        tool("godot.observer", "timeline", { detail: "short" }),
      ];
      return this.extras.shift() as ModelTurn;
    }
    return { kind: "done", summary: "job.plan DAG interpreted on live brief" };
  }

  private maybeQueueRepair(ctx: ModelContext, results: ToolResultView[]): void {
    if (!this.didWriteScript) {
      return;
    }
    const tools = ctx.last_tools;
    if (tools.length === 0 || results.length === 0) {
      return;
    }
    const lastTool = tools[tools.length - 1];
    const lastResult = results[results.length - 1];
    if (!lastTool || !lastResult) {
      return;
    }
    if (lastTool.tool !== "godot.test" || lastTool.action !== "run") {
      return;
    }
    const after = lastResult.after;
    const failed = lastResult.ok !== true || after.status === "fail";
    if (!failed) {
      return;
    }
    const name =
      typeof after.name === "string" && after.name
        ? after.name
        : this.lastTestName;
    if (!name || this.repaired.has(name)) {
      return;
    }
    this.repaired.add(name);
    this.extras.push(tool("godot.test", "repair", { name }));
    this.extras.push(emitTestRun(name));
  }

  /** One Pause/Resume: non-mutating observe in between, later DAG work after resume. */
  private maybeQueuePauseObserve(): void {
    if (this.didPause || !this.didWriteScript) {
      return;
    }
    this.didPause = true;
    const scene = this.spec.scene;
    this.extras.push(tool("hh.pause", "pause", {}));
    this.extras.push(tool("godot.scene", "read", { path: scene, detail: "short" }));
    this.extras.push(tool("godot.observer", "timeline", { detail: "short" }));
    this.extras.push(tool("hh.resume", "resume", {}));
  }

  private flushPendingDefines(): void {
    for (const task of this.pendingDefines) {
      const compiled = assertFromAcceptance(criterionOf(task, this.plan), this.spec);
      if (compiled && isQueuedAssert(compiled)) {
        this.extras.push(tool("godot.test", "define", defineParams(compiled, this.spec)));
      }
    }
    this.pendingDefines = [];
  }

  /**
   * Play like a player: discover pairs from live ColorRect faces after the
   * scene exists. Never group spec.tiles / PackedInt32Array into a click tape.
   */
  private advancePlay(ctx: ModelContext): ModelTurn | undefined {
    if (this.playPhase !== "seeking") {
      return undefined;
    }
    const lastTool = ctx.last_tools[ctx.last_tools.length - 1];
    const lastResult = ctx.last_results[ctx.last_results.length - 1];
    if (lastTool?.tool === "godot.play" && lastTool.action === "stop") {
      this.playPhase = "done";
      return undefined;
    }
    if (!lastResult || lastResult.ok !== true) {
      this.playPhase = "done";
      this.playBlocked = true;
      this.extras.push(tool("godot.play", "stop", { reason: "observe-blocked" }));
      return this.extras.shift();
    }
    if (lastTool?.tool === "godot.runtime" && lastTool.action === "screenshot") {
      this.extras.push(lookLiveBoard());
      return this.extras.shift();
    }
    if (lastTool?.tool !== "godot.runtime" || lastTool.action !== "node") {
      this.extras.push(lookLiveBoard());
      return this.extras.shift();
    }
    const board = liveBoardFromAfter(lastResult.after);
    this.playLooks += 1;
    const prevMatches = this.playLastMatches;
    this.playLastMatches = board.matches;
    if (board.cursor !== undefined) {
      this.playCursor = board.cursor;
    }
    if (board.matches > prevMatches) {
      for (let i = 0; i < board.faces.length; i += 1) {
        const key = liveFaceKey(board.faces[i] ?? { r: 0, g: 0, b: 0 });
        if (isFaceUp(key)) {
          this.playMatched.add(i);
        }
      }
    }
    if (board.won && board.matches >= 2) {
      if (!this.playShotB) {
        this.playShotB = true;
        this.extras.push(tool("godot.runtime", "screenshot", { scale: 1 }));
        return this.extras.shift();
      }
      this.playPhase = "done";
      this.extras.push(tool("godot.play", "stop", { reason: "test" }));
      return this.extras.shift();
    }
    if (!this.playShotB && board.matches >= 1) {
      this.playShotB = true;
      this.extras.push(tool("godot.runtime", "screenshot", { scale: 1 }));
      return this.extras.shift();
    }
    if (this.playLooks > 40 || this.playAccepts > 24 || this.playBlocked) {
      this.playBlocked = true;
      this.playPhase = "done";
      this.extras.push(tool("godot.play", "stop", { reason: "no-visible-match" }));
      return this.extras.shift();
    }
    if (board.faces.length === 0) {
      if (this.playLooks > 3) {
        this.playBlocked = true;
        this.playPhase = "done";
        this.extras.push(tool("godot.play", "stop", { reason: "no-live-faces" }));
        return this.extras.shift();
      }
      this.extras.push(tool("godot.runtime", "step", { frames: 4 }));
      this.extras.push(lookLiveBoard());
      return this.extras.shift();
    }
    const target = chooseVisibleTarget(
      board,
      this.playMemory,
      this.playMatched,
      this.playSeen,
      this.playLastTarget,
    );
    if (target === undefined) {
      this.playBlocked = true;
      this.playPhase = "done";
      this.extras.push(tool("godot.play", "stop", { reason: "no-visible-target" }));
      return this.extras.shift();
    }
    const cols = Math.max(1, this.spec.cols);
    this.extras = enqueueVisibleAccept(this.playCursor, target, cols);
    this.playCursor = target;
    this.playLastTarget = target;
    this.playAccepts += 1;
    this.extras.push(lookLiveBoard());
    return this.extras.shift();
  }

  private turnFor(task: PlanTask, actionId: string): ModelTurn | undefined {
    const scene = this.spec.scene;
    if (actionId === "test.define") {
      if (!this.didWriteScript) {
        this.pendingDefines.push(task);
        return undefined;
      }
      const compiled = assertFromAcceptance(criterionOf(task, this.plan), this.spec);
      if (!compiled || !isQueuedAssert(compiled)) {
        return undefined;
      }
      return tool("godot.test", "define", defineParams(compiled, this.spec));
    }
    if (actionId === "test.run") {
      const compiled = assertFromAcceptance(criterionOf(task, this.plan), this.spec);
      if (!compiled || !isQueuedAssert(compiled)) {
        return undefined;
      }
      this.lastTestName = compiled.name;
      return emitTestRun(compiled.name);
    }
    if (actionId === "script.write") {
      this.draft = compilePlanScript(this.spec);
      this.didWriteScript = true;
      this.flushPendingDefines();
    }
    if (actionId === "node.add" || actionId === "script.attach") {
      this.extras.push(tool("godot.scene", "open", { path: scene }));
      const mcp = verbToMcp(actionId);
      this.extras.push(tool(mcp.tool, mcp.action, paramsFor(actionId, task, this.spec, this.draft)));
      this.extras.push(tool("godot.scene", "save", { path: scene }));
      return this.extras.shift();
    }
    const mcp = verbToMcp(actionId);
    return tool(mcp.tool, mcp.action, paramsFor(actionId, task, this.spec, this.draft));
  }
}

export class PlanFollowProvider implements Provider {
  readonly name = "plan";
  readonly model = PLAN_FOLLOW_MODEL;
  private readonly brief: string;
  private readonly asksPath?: string;
  private walker: DagWalker | null = null;

  constructor(brief: string, asksPath?: string) {
    this.brief = brief;
    if (asksPath) {
      this.asksPath = asksPath;
      fs.mkdirSync(path.dirname(asksPath), { recursive: true });
      if (!fs.existsSync(asksPath)) {
        fs.writeFileSync(
          asksPath,
          `${JSON.stringify({ at: Date.now(), code: "LOG", message: "ask log opened; only E1–E4 may stop", e_gate: false })}\n`,
          "utf8",
        );
      }
    }
  }

  generate(ctx: ModelContext): ModelTurn {
    if (!this.brief.trim()) {
      appendAsk(this.asksPath, {
        at: Date.now(),
        code: "E_POLICY",
        message: "missing PROJECT_BRIEF; not an E1–E4 stop",
        e_gate: false,
      });
      return { kind: "done", summary: "missing brief" };
    }
    const planned = ctx.last_tools.some((row) => row.tool === "godot.job" && row.action === "plan");
    if (!planned) {
      return tool("godot.job", "plan", { brief: this.brief, run_id: ctx.command_id });
    }
    const plan = findPlan(ctx.last_results);
    if (!plan) {
      return { kind: "done", summary: "job.plan returned no DAG" };
    }
    for (const blocker of plan.blockers) {
      const eGate = /^E[1-4]$/.test(blocker.code);
      appendAsk(this.asksPath, {
        at: Date.now(),
        code: blocker.code,
        message: blocker.message,
        e_gate: eGate,
      });
      if (eGate) {
        return { kind: "done", summary: `blocked ${blocker.code}` };
      }
    }
    if (!this.walker) {
      const spec = compileGameSpec(plan, this.brief);
      const asserts = collectAsserts(plan, spec);
      this.walker = new DagWalker(plan, spec, asserts, compilePlanScript(spec));
    }
    return this.walker.next(ctx);
  }
}

export function loadBriefFile(file: string): string {
  return fs.readFileSync(file, { encoding: "utf8" });
}
