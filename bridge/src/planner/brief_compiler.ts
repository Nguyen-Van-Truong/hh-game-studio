/**
 * PROJECT_BRIEF → task DAG. Sidecar source of truth for R7-WP1.
 * Small gaps follow plan §6.2. E1–E4 become blocker nodes, never silent picks.
 */

import fs from "node:fs";
import path from "node:path";

import { jailProjectPath } from "../policy/jail.js";
import { E, typedError } from "../registry/errors.js";

export const PLAN_SCHEMA = "hh-plan/1" as const;
export const PINNED_GODOT = "4.7.1-stable";

export type GateCode = "E1" | "E2" | "E3" | "E4";
export type TaskKind = "test" | "verify" | "produce" | "checkpoint" | "blocker";

export interface TaskNode {
  id: string;
  kind: TaskKind;
  acceptance: string[];
  outputs: string[];
  files: string[];
  scene_leases: string[];
  deps: string[];
  verify: string;
  budget: { commands: number; minutes: number };
  rollback: string;
  commands: string[];
  checkpoint: string;
  criterion?: string;
  blocker?: { code: GateCode; message: string };
}

export interface AcceptanceItem {
  id: string;
  text: string;
  task_ids: string[];
}

export interface Assumption {
  id: string;
  field: string;
  value: string;
  rule: string;
}

export interface Blocker {
  code: GateCode;
  message: string;
  task_id: string;
}

export interface TraceRow {
  brief: string;
  task: string;
  command: string;
  test: string;
  checkpoint: string;
}

export interface CompiledPlan {
  ok: boolean;
  schema: typeof PLAN_SCHEMA;
  status: "ready" | "blocked" | "invalid";
  run_id: string;
  complete: boolean;
  acyclic: boolean;
  tasks: TaskNode[];
  acceptance: AcceptanceItem[];
  assumptions: Assumption[];
  blockers: Blocker[];
  traces: TraceRow[];
  cards: Array<{ id: string; kind: string; summary: string }>;
  error?: { code: string; message: string; path: string };
}

export interface CompileInput {
  brief?: string;
  fields?: Record<string, unknown>;
  run_id?: string;
  inject_cycle?: boolean;
}

export const CYCLIC_FIXTURE: Array<{ id: string; deps: string[] }> = [
  { id: "a", deps: ["b"] },
  { id: "b", deps: ["c"] },
  { id: "c", deps: ["a"] },
];

const KIND_ORDER: Record<TaskKind, number> = {
  test: 0,
  verify: 1,
  produce: 2,
  checkpoint: 3,
  blocker: 4,
};

const GENRE_FAMILIES: ReadonlyArray<readonly string[]> = [
  ["platformer", "platform"],
  ["puzzle", "match-3", "match3"],
  ["shooter", "twin-stick", "twin stick", "shmup"],
  ["rpg", "role-playing", "role playing"],
  ["adventure"],
  ["farming", "harvest"],
  ["novel", "dialogue", "vn"],
  ["tower defense", "tower-defense", " td "],
  ["racing"],
  ["stealth"],
];

const EXCLUSIVE = /\b(only|exclusive|must be|must remain|cannot be anything but|strictly)\b/i;

function lower(s: string): string {
  return s.toLowerCase();
}

function headingKey(raw: string): string {
  return raw.trim().toLowerCase().replace(/\s+/g, " ");
}

function fieldKey(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function isPlaceholder(value: string): boolean {
  const t = value.trim();
  if (!t) {
    return true;
  }
  if (t.startsWith("(e.g.") || t.startsWith("(e.g ") || t.startsWith("(")) {
    return true;
  }
  if (t === "yes | no" || t === "no | yes") {
    return true;
  }
  if (t.includes(" | ") && t.length < 64 && !EXCLUSIVE.test(t)) {
    return true;
  }
  return false;
}

function parseSections(md: string): Record<string, string> {
  const sections: Record<string, string> = {};
  let current = "preamble";
  const buf: string[] = [];
  const flush = (): void => {
    sections[current] = buf.join("\n");
  };
  for (const line of md.replace(/\r\n/g, "\n").split("\n")) {
    const m = line.match(/^##\s+(.+)\s*$/);
    if (m?.[1]) {
      flush();
      current = headingKey(m[1]);
      buf.length = 0;
      continue;
    }
    buf.push(line);
  }
  flush();
  return sections;
}

function parseBullets(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of body.split("\n")) {
    const bold = line.match(/^\s*[-*]\s+\*\*([^*]+)\*\*\s*:\s*(.*)$/);
    if (bold?.[1]) {
      out[fieldKey(bold[1])] = (bold[2] ?? "").trim();
      continue;
    }
    const plain = line.match(/^\s*[-*]\s+([^:]+):\s*(.*)$/);
    if (plain?.[1]) {
      out[fieldKey(plain[1])] = (plain[2] ?? "").trim();
    }
  }
  return out;
}

function parseAcceptance(body: string): string[] {
  const items: string[] = [];
  for (const line of body.split("\n")) {
    const m = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/);
    if (!m?.[1]) {
      continue;
    }
    let text = m[1].replace(/^\*\*[^*]+:\*\*\s*/, "").trim();
    if (isPlaceholder(text) || text.toLowerCase().startsWith("replace these")) {
      continue;
    }
    items.push(text);
  }
  return items;
}

function asRecord(v: unknown): Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

function strField(rec: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const v = rec[key];
    if (typeof v === "string" && v.trim()) {
      return v.trim();
    }
  }
  return "";
}

interface BriefDoc {
  raw: string;
  sections: Record<string, string>;
  genre: string;
  fantasy: string;
  out_of_scope: string;
  camera: string;
  zoom: string;
  resolution: string;
  stretch: string;
  aspect: string;
  devices: string;
  actions: string;
  platform: string;
  art: string;
  audio_bus: string;
  audio_music: string;
  audio_license: string;
  save_needed: string;
  save_slots: string;
  audience: string;
  content: string;
  performance: string;
  acceptance: string[];
  scan_text: string;
}

function mergeFields(base: BriefDoc, fields: Record<string, unknown>): void {
  const genre = asRecord(fields.genre);
  const camera = asRecord(fields.camera);
  const resolution = asRecord(fields.resolution);
  const input = asRecord(fields.input);
  const platform = asRecord(fields.platform);
  const art = asRecord(fields.art);
  const audio = asRecord(fields.audio);
  const save = asRecord(fields.save);
  if (strField(genre, "value")) {
    base.genre = strField(genre, "value");
  }
  if (strField(genre, "player_fantasy", "fantasy")) {
    base.fantasy = strField(genre, "player_fantasy", "fantasy");
  }
  if (strField(genre, "out_of_scope")) {
    base.out_of_scope = strField(genre, "out_of_scope");
  }
  if (strField(camera, "mode")) {
    base.camera = strField(camera, "mode");
  }
  if (strField(resolution, "base", "base_design_resolution")) {
    base.resolution = strField(resolution, "base", "base_design_resolution");
  }
  if (strField(input, "devices")) {
    base.devices = strField(input, "devices");
  }
  if (strField(platform, "ship", "ship_target")) {
    base.platform = strField(platform, "ship", "ship_target");
  }
  if (strField(art, "style")) {
    base.art = strField(art, "style");
  }
  if (strField(audio, "bus", "bus_layout")) {
    base.audio_bus = strField(audio, "bus", "bus_layout");
  }
  if (strField(save, "needed")) {
    base.save_needed = strField(save, "needed");
  }
  if (typeof fields.audience === "string") {
    base.audience = fields.audience.trim();
  }
  if (Array.isArray(fields.acceptance)) {
    for (const item of fields.acceptance) {
      if (typeof item === "string" && item.trim() && !isPlaceholder(item)) {
        base.acceptance.push(item.trim());
      }
    }
  }
}

function parseBrief(input: CompileInput): BriefDoc {
  const raw = typeof input.brief === "string" ? input.brief : "";
  const sections = parseSections(raw);
  const genreB = parseBullets(sections["genre"] ?? "");
  const cameraB = parseBullets(sections["camera"] ?? "");
  const resB = parseBullets(sections["resolution"] ?? "");
  const inputB = parseBullets(sections["input"] ?? "");
  const platB = parseBullets(sections["platform"] ?? "");
  const artB = parseBullets(sections["art"] ?? "");
  const audioB = parseBullets(sections["audio"] ?? "");
  const saveB = parseBullets(sections["save"] ?? "");
  const contentB = parseBullets(sections["content / license"] ?? sections["content"] ?? "");
  const perfB = parseBullets(sections["performance"] ?? "");
  const audienceB = parseBullets(sections["audience"] ?? "");
  const doc: BriefDoc = {
    raw,
    sections,
    genre: genreB["value"] ?? "",
    fantasy: genreB["player_fantasy"] ?? "",
    out_of_scope: genreB["out_of_scope"] ?? "",
    camera: cameraB["mode"] ?? "",
    zoom: cameraB["zoom_limits"] ?? cameraB["zoom"] ?? "",
    resolution: resB["base_design_resolution"] ?? resB["base"] ?? "",
    stretch: resB["stretch_mode"] ?? resB["stretch"] ?? "",
    aspect: resB["aspect"] ?? "",
    devices: inputB["devices"] ?? "",
    actions: inputB["actions"] ?? "",
    platform: platB["ship_target"] ?? platB["ship"] ?? "",
    art: artB["style"] ?? "",
    audio_bus: audioB["bus_layout"] ?? audioB["bus"] ?? "",
    audio_music: audioB["music"] ?? "",
    audio_license: audioB["license_source"] ?? audioB["license"] ?? "",
    save_needed: saveB["needed"] ?? "",
    save_slots: saveB["slots_autosave"] ?? saveB["slots"] ?? "",
    audience: audienceB["value"] ?? audienceB["rating"] ?? "",
    content: Object.values(contentB).join(" "),
    performance: Object.values(perfB).join(" "),
    acceptance: parseAcceptance(sections["acceptance"] ?? ""),
    scan_text: "",
  };
  if (input.fields) {
    mergeFields(doc, input.fields);
  }
  const skip = new Set(["assumption policy", "assumption_policy"]);
  const scanParts: string[] = [];
  for (const [key, body] of Object.entries(doc.sections)) {
    if (skip.has(key)) {
      continue;
    }
    scanParts.push(body);
  }
  scanParts.push(
    doc.genre,
    doc.fantasy,
    doc.out_of_scope,
    doc.camera,
    doc.platform,
    doc.save_needed,
    doc.audio_license,
    doc.audience,
    doc.content,
    ...doc.acceptance,
  );
  doc.scan_text = scanParts.join("\n");
  return doc;
}

function filled(v: string): boolean {
  return !isPlaceholder(v);
}

function isComplete(doc: BriefDoc): boolean {
  return (
    filled(doc.genre) &&
    filled(doc.camera) &&
    filled(doc.resolution) &&
    filled(doc.devices) &&
    filled(doc.platform) &&
    filled(doc.art) &&
    (filled(doc.audio_bus) || filled(doc.audio_music)) &&
    filled(doc.save_needed) &&
    doc.acceptance.length >= 2
  );
}

function familiesOf(text: string): string[] {
  const hay = ` ${lower(text)} `;
  const found: string[] = [];
  for (const group of GENRE_FAMILIES) {
    const name = group[0];
    if (!name) {
      continue;
    }
    if (group.some((needle) => hay.includes(needle))) {
      found.push(name);
    }
  }
  return found;
}

function has2dExclusive(text: string): boolean {
  return /\b(2d[- ]only|must be 2d|2d exclusive|strictly 2d)\b/i.test(text);
}

function has3dExclusive(text: string): boolean {
  return /\b(3d[- ]only|must be 3d|3d exclusive|strictly 3d)\b/i.test(text);
}

function detectBlockers(doc: BriefDoc): Array<{ code: GateCode; message: string }> {
  const text = doc.scan_text;
  const out: Array<{ code: GateCode; message: string }> = [];
  const seen = new Set<string>();
  const add = (code: GateCode, message: string): void => {
    const key = `${code}:${message}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    out.push({ code, message });
  };

  if (
    /\b(api key|apikey|openai key|anthropic key|steamworks secret|account password|oauth token)\b/i.test(
      text,
    ) ||
    /credentials the machine does not/i.test(text) ||
    /must provide (a |an )?(secret|api key|token)/i.test(text) ||
    /\.env file with/i.test(text)
  ) {
    add("E1", "brief requires a secret, account, or API key the machine does not have");
  }
  if (
    /\b(must buy|purchase a|paid asset|paid license|paid quota|unity asset store)\b/i.test(text) ||
    /costs\s*\$/i.test(text)
  ) {
    add("E2", "brief requires spend, paid quota, or buying assets/licenses");
  }
  if (
    /\b(code sign|signing certificate|upload to steam|publish to the store|public publish|itch\.io upload)\b/i.test(
      text,
    ) ||
    /send (project |player )?data off/i.test(text)
  ) {
    add("E3", "brief requires signing, store upload, public publish, or sending data off-machine");
  }

  if (has2dExclusive(text) && has3dExclusive(text)) {
    add("E4", "brief requires both exclusive 2D and exclusive 3D");
  }

  const genreBlob = `${doc.genre} ${doc.fantasy} ${doc.out_of_scope}`;
  const fams = familiesOf(genreBlob);
  if (fams.length >= 2 && EXCLUSIVE.test(genreBlob)) {
    add("E4", `brief names exclusive conflicting genres: ${fams.join(" vs ")}`);
  }

  const cam = lower(doc.camera);
  if (
    (/\btop-?down\b/.test(cam) && EXCLUSIVE.test(cam)) ||
    (/\btop-?down only\b/.test(text) && /\b(side-?scroll|sidescroll) only\b/.test(text))
  ) {
    if (/\b(side-?scroll|sidescroll).*(only|exclusive|must)\b/i.test(text)) {
      add("E4", "brief requires exclusive top-down and exclusive side-scroll cameras");
    }
  }

  const save = lower(doc.save_needed);
  const acc = lower(doc.acceptance.join("\n"));
  const noSave = save === "no" || /\bno save\b/.test(text);
  const yesSave =
    save === "yes" || /\b(must have save|cloud save required|save\/load required)\b/i.test(text);
  if (noSave && yesSave) {
    add("E4", "brief says no save and also requires save");
  }
  if (save === "no" && /\b(save|persist|cloud save)\b/i.test(acc) && /\b(must|required)\b/i.test(acc)) {
    add("E4", "acceptance requires save while save.needed is no");
  }

  const aud = `${doc.audience} ${doc.fantasy} ${doc.genre}`;
  if (
    /\b(kids? only|e-rated only|everyone 10 only|child audience only)\b/i.test(aud) &&
    /\b(mature only|18\+|adults? only)\b/i.test(aud)
  ) {
    add("E4", "brief requires exclusive kids and exclusive mature audiences");
  }

  if (
    /\b(windows only|desktop only)\b/i.test(doc.platform) &&
    /\b(mobile only|ios only|android only)\b/i.test(`${doc.platform} ${text}`)
  ) {
    add("E4", "brief requires exclusive Windows and exclusive mobile platforms");
  }

  if (/\b(change the genre|pivot the genre|pivot to a different|scrap this genre|wrong target audience)\b/i.test(text)) {
    add("E4", "brief asks to change genre, audience, or large scope (product pivot)");
  }

  return out;
}

function applyAssumptions(doc: BriefDoc): Assumption[] {
  const notes: Assumption[] = [];
  const add = (field: string, value: string, rule: string): void => {
    notes.push({ id: `asm${String(notes.length + 1).padStart(2, "0")}`, field, value, rule });
  };
  if (!filled(doc.genre)) {
    doc.genre = "top-down 2D";
    add("genre.value", doc.genre, "1 Godot 4.7.1-stable convention");
  }
  if (!filled(doc.camera)) {
    doc.camera = "follow";
    add("camera.mode", doc.camera, "1 Godot Camera2D follow convention");
  }
  if (!filled(doc.resolution)) {
    doc.resolution = "1280x720";
    add("resolution.base", doc.resolution, "1 pinned 2D template resolution");
  }
  if (!filled(doc.stretch)) {
    doc.stretch = "canvas_items";
    add("resolution.stretch", doc.stretch, "1 Godot 4 stretch convention");
  }
  if (!filled(doc.aspect)) {
    doc.aspect = "keep";
    add("resolution.aspect", doc.aspect, "1 Godot 4 aspect keep");
  }
  if (!filled(doc.devices)) {
    doc.devices = "keyboard";
    add("input.devices", doc.devices, "2 easiest to test and revert");
  }
  if (!filled(doc.actions)) {
    doc.actions = "move, interact, pause";
    add("input.actions", doc.actions, "3 fewest dependencies");
  }
  if (!filled(doc.platform)) {
    doc.platform = "Windows desktop";
    add("platform.ship", doc.platform, "1 repo R9 default");
  }
  if (!filled(doc.art)) {
    doc.art = "PLACEHOLDER labeled sprites";
    add("art.style", doc.art, "2 easiest to test and revert");
  }
  if (!filled(doc.audio_bus) && !filled(doc.audio_music)) {
    doc.audio_bus = "Master / Music / SFX";
    add("audio.bus", doc.audio_bus, "1 Godot bus convention");
  }
  if (!filled(doc.save_needed)) {
    doc.save_needed = "no";
    add("save.needed", doc.save_needed, "3 fewest dependencies");
  }
  if (doc.acceptance.length === 0) {
    doc.acceptance.push("vertical slice: player can move and complete one interaction");
    doc.acceptance.push("play session: 10 minutes with no blocker");
    doc.acceptance.push("tests: GUT unit + MCP/E2E evidence on 4.7.1-stable");
    add("acceptance", "default measurable slice + play + tests", "2 easiest to test and revert");
  }
  return notes;
}

export function detectCycle(tasks: Array<{ id: string; deps?: string[] }>): string[] {
  const ids = new Set(tasks.map((t) => t.id));
  const incoming = new Map<string, number>();
  const edges = new Map<string, string[]>();
  for (const t of tasks) {
    incoming.set(t.id, incoming.get(t.id) ?? 0);
    edges.set(t.id, []);
  }
  for (const t of tasks) {
    for (const dep of t.deps ?? []) {
      if (!ids.has(dep)) {
        continue;
      }
      edges.get(dep)?.push(t.id);
      incoming.set(t.id, (incoming.get(t.id) ?? 0) + 1);
    }
  }
  const ready = [...incoming.entries()].filter(([, n]) => n === 0).map(([id]) => id);
  const seen: string[] = [];
  while (ready.length > 0) {
    const id = ready.shift();
    if (!id) {
      break;
    }
    seen.push(id);
    for (const next of edges.get(id) ?? []) {
      const n = (incoming.get(next) ?? 1) - 1;
      incoming.set(next, n);
      if (n === 0) {
        ready.push(next);
      }
    }
  }
  if (seen.length === ids.size) {
    return [];
  }
  return [...ids].filter((id) => !seen.includes(id));
}

function topoSort(tasks: TaskNode[]): { order: TaskNode[]; cycle: string[] } {
  const cycle = detectCycle(tasks);
  if (cycle.length > 0) {
    return { order: [], cycle };
  }
  const byId = new Map(tasks.map((t) => [t.id, t]));
  const incoming = new Map<string, number>();
  const edges = new Map<string, string[]>();
  for (const t of tasks) {
    incoming.set(t.id, 0);
    edges.set(t.id, []);
  }
  for (const t of tasks) {
    for (const dep of t.deps) {
      if (!byId.has(dep)) {
        continue;
      }
      edges.get(dep)?.push(t.id);
      incoming.set(t.id, (incoming.get(t.id) ?? 0) + 1);
    }
  }
  const ready = tasks
    .filter((t) => (incoming.get(t.id) ?? 0) === 0)
    .sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || a.id.localeCompare(b.id));
  const order: TaskNode[] = [];
  while (ready.length > 0) {
    const node = ready.shift();
    if (!node) {
      break;
    }
    order.push(node);
    const nextIds = [...(edges.get(node.id) ?? [])].sort((a, b) => {
      const na = byId.get(a);
      const nb = byId.get(b);
      if (!na || !nb) {
        return a.localeCompare(b);
      }
      return KIND_ORDER[na.kind] - KIND_ORDER[nb.kind] || na.id.localeCompare(nb.id);
    });
    for (const nid of nextIds) {
      const n = (incoming.get(nid) ?? 1) - 1;
      incoming.set(nid, n);
      const task = byId.get(nid);
      if (n === 0 && task) {
        ready.push(task);
        ready.sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || a.id.localeCompare(b.id));
      }
    }
  }
  return { order, cycle: [] };
}

function accId(i: number): string {
  return `acc${String(i + 1).padStart(2, "0")}`;
}

interface ProduceSpec {
  slug: string;
  scene: string;
  script: string;
  art: string;
  audio: string;
}

type ProduceId = "produce_scene" | "produce_script" | "produce_art" | "produce_audio";

function produceSpec(doc: BriefDoc): ProduceSpec {
  const hay = lower(`${doc.genre} ${doc.fantasy} ${doc.out_of_scope}`);
  if (/\bmatch[- ]?3\b/.test(hay)) {
    return {
      slug: "match3",
      scene: "res://scenes/match3/board.tscn",
      script: "res://scripts/match3/board.gd",
      art: "res://art/match3/gem.png",
      audio: "res://audio/match3/match.wav",
    };
  }
  if (/\btower/.test(hay) || /\btd\b/.test(hay)) {
    return {
      slug: "tower",
      scene: "res://scenes/tower/lane.tscn",
      script: "res://scripts/tower/tower.gd",
      art: "res://art/tower/tower.png",
      audio: "res://audio/tower/shot.wav",
    };
  }
  if (/\b(dialogue|visual novel|\bvn\b)\b/.test(hay)) {
    return {
      slug: "dialogue",
      scene: "res://scenes/dialogue/conversation.tscn",
      script: "res://scripts/dialogue/graph.gd",
      art: "res://art/dialogue/portrait.png",
      audio: "res://audio/dialogue/talk.wav",
    };
  }
  if (/\b(farm|harvest)\b/.test(hay)) {
    return {
      slug: "farming",
      scene: "res://scenes/farm/field.tscn",
      script: "res://scripts/farm/crop.gd",
      art: "res://art/farm/crop.png",
      audio: "res://audio/farm/hoe.wav",
    };
  }
  if (/\b(twin[- ]?stick|shmup|shooter)\b/.test(hay)) {
    return {
      slug: "twin_stick",
      scene: "res://scenes/arena/arena.tscn",
      script: "res://scripts/arena/shooter.gd",
      art: "res://art/arena/bullet.png",
      audio: "res://audio/arena/fire.wav",
    };
  }
  if (/\bplatform/.test(hay)) {
    return {
      slug: "platformer",
      scene: "res://scenes/platformer/level.tscn",
      script: "res://scripts/platformer/player.gd",
      art: "res://art/platformer/tiles.png",
      audio: "res://audio/platformer/jump.wav",
    };
  }
  if (/\bpuzzle\b/.test(hay)) {
    return {
      slug: "puzzle",
      scene: "res://scenes/puzzle/board.tscn",
      script: "res://scripts/puzzle/rules.gd",
      art: "res://art/puzzle/tile.png",
      audio: "res://audio/puzzle/click.wav",
    };
  }
  return {
    slug: "topdown",
    scene: "res://scenes/overworld/overworld.tscn",
    script: "res://scripts/overworld/player.gd",
    art: "res://art/overworld/key.png",
    audio: "res://audio/overworld/pickup.wav",
  };
}

function produceKindForAcceptance(text: string): ProduceId {
  const t = lower(text);
  if (/\b(audio|sfx|sound|music|wav)\b/.test(t)) {
    return "produce_audio";
  }
  if (/\b(art|sprite|tile|portrait|png|palette|pixel|gem art)\b/.test(t)) {
    return "produce_art";
  }
  if (/\b(script|code|logic|input|move|play|swap|shoot|farm|dialogue|choice|save|key|door|match)\b/.test(t)) {
    return "produce_script";
  }
  return "produce_scene";
}

function atomicWriteUtf8(absPath: string, text: string): void {
  fs.mkdirSync(path.dirname(absPath), { recursive: true });
  const tmp = `${absPath}.tmp`;
  fs.writeFileSync(tmp, text, "utf8");
  try {
    fs.unlinkSync(absPath);
  } catch {
    /* dest may not exist */
  }
  fs.renameSync(tmp, absPath);
}

function task(partial: Omit<TaskNode, "budget" | "rollback" | "checkpoint"> & Partial<TaskNode>): TaskNode {
  return {
    budget: { commands: 8, minutes: 10 },
    rollback: "git.revert_checkpoint",
    checkpoint: "",
    ...partial,
  };
}

function buildTasks(
  doc: BriefDoc,
  runId: string,
  blockers: Array<{ code: GateCode; message: string }>,
): TaskNode[] {
  const ev = `r7w1/evidence/${runId}`;
  const spec = produceSpec(doc);
  const accIds = doc.acceptance.map((_, i) => accId(i));
  const mapped: ProduceId[] = doc.acceptance.map((text) => produceKindForAcceptance(text));
  const produceAccs: Record<ProduceId, string[]> = {
    produce_scene: [],
    produce_script: [],
    produce_art: [],
    produce_audio: [],
  };
  for (let i = 0; i < accIds.length; i += 1) {
    const id = accIds[i];
    const kind = mapped[i];
    if (id && kind) {
      produceAccs[kind].push(id);
    }
  }
  const nodes: TaskNode[] = [];
  const defineIds: string[] = [];

  for (let i = 0; i < doc.acceptance.length; i += 1) {
    const id = `verify_define_${accIds[i]}`;
    defineIds.push(id);
    nodes.push(
      task({
        id,
        kind: "test",
        acceptance: [accIds[i] ?? ""],
        criterion: doc.acceptance[i] ?? "",
        outputs: [`${ev}/tests/${accIds[i]}.hh-test.json`],
        files: [`${ev}/tests/${accIds[i]}.hh-test.json`],
        scene_leases: [],
        deps: [],
        verify: "test.define",
        commands: ["test.define"],
        budget: { commands: 4, minutes: 5 },
      }),
    );
  }

  const blockerIds: string[] = [];
  for (let i = 0; i < blockers.length; i += 1) {
    const b = blockers[i];
    if (!b) {
      continue;
    }
    const id = `blocker_${b.code}_${String(i + 1).padStart(2, "0")}`;
    blockerIds.push(id);
    nodes.push(
      task({
        id,
        kind: "blocker",
        acceptance: accIds.slice(),
        outputs: [],
        files: [],
        scene_leases: [],
        deps: [],
        verify: "none",
        commands: [],
        rollback: "none",
        blocker: { code: b.code, message: b.message },
        budget: { commands: 0, minutes: 0 },
      }),
    );
  }

  const produceDeps = [...defineIds, ...blockerIds];
  nodes.push(
    task({
      id: "produce_scene",
      kind: "produce",
      acceptance: produceAccs.produce_scene.slice(),
      outputs: [spec.scene],
      files: [spec.scene],
      scene_leases: [spec.scene],
      deps: produceDeps.slice(),
      verify: "scene.read",
      commands: ["scene.create", "node.add"],
    }),
  );
  nodes.push(
    task({
      id: "produce_script",
      kind: "produce",
      acceptance: produceAccs.produce_script.slice(),
      outputs: [spec.script],
      files: [spec.script],
      scene_leases: [spec.scene],
      deps: ["produce_scene"],
      verify: "script.validate",
      commands: ["script.write", "script.attach"],
    }),
  );
  nodes.push(
    task({
      id: "produce_art",
      kind: "produce",
      acceptance: produceAccs.produce_art.slice(),
      outputs: [spec.art],
      files: [spec.art],
      scene_leases: [],
      deps: produceDeps.slice(),
      verify: "asset.preview",
      commands: ["asset.import"],
      budget: { commands: 6, minutes: 15 },
    }),
  );
  nodes.push(
    task({
      id: "produce_audio",
      kind: "produce",
      acceptance: produceAccs.produce_audio.slice(),
      outputs: [spec.audio],
      files: [spec.audio],
      scene_leases: [],
      deps: produceDeps.slice(),
      verify: "audio.preview",
      commands: ["audio.player"],
      budget: { commands: 6, minutes: 15 },
    }),
  );

  const runIds: string[] = [];
  for (let i = 0; i < doc.acceptance.length; i += 1) {
    const id = `verify_run_${accIds[i]}`;
    runIds.push(id);
    const mappedId = mapped[i] ?? "produce_scene";
    const deps =
      blockers.length > 0 ? [defineIds[i] ?? "", ...blockerIds] : [mappedId];
    nodes.push(
      task({
        id,
        kind: "verify",
        acceptance: [accIds[i] ?? ""],
        outputs: [`${ev}/reports/${accIds[i]}.json`],
        files: [`${ev}/reports/${accIds[i]}.json`],
        scene_leases: [spec.scene],
        deps: deps.filter(Boolean),
        verify: "test.run",
        commands: ["test.run"],
        budget: { commands: 6, minutes: 8 },
      }),
    );
  }

  nodes.push(
    task({
      id: "checkpoint_slice",
      kind: "checkpoint",
      acceptance: accIds.slice(),
      outputs: [`${ev}/checkpoint.json`],
      files: [`${ev}/checkpoint.json`],
      scene_leases: [spec.scene],
      deps: runIds.slice(),
      verify: "git.checkpoint",
      commands: ["git.checkpoint"],
      checkpoint: "git.checkpoint",
      rollback: "git.revert_checkpoint",
      budget: { commands: 2, minutes: 2 },
    }),
  );
  return nodes;
}

function defaultRunId(brief: string): string {
  let hash = 0;
  for (let i = 0; i < brief.length; i += 1) {
    hash = (hash * 33 + brief.charCodeAt(i)) >>> 0;
  }
  const tail = hash.toString(32).toUpperCase().replace(/[ILOU]/g, "X").padStart(8, "0");
  return `01R7WP1BRF00000000${tail}`.slice(0, 26);
}

export function compileBrief(input: CompileInput): CompiledPlan {
  const brief = typeof input.brief === "string" ? input.brief : "";
  const runId =
    typeof input.run_id === "string" && /^[0-7][0-9A-HJKMNPQRSTVWXYZ]{25}$/.test(input.run_id)
      ? input.run_id
      : defaultRunId(brief || JSON.stringify(input.fields ?? {}));
  if (!brief.trim() && !input.fields) {
    return {
      ok: false,
      schema: PLAN_SCHEMA,
      status: "invalid",
      run_id: runId,
      complete: false,
      acyclic: true,
      tasks: [],
      acceptance: [],
      assumptions: [],
      blockers: [],
      traces: [],
      cards: [],
      error: typedError(E.E_MISSING_REQUIRED, "brief or fields required", "brief"),
    };
  }

  const doc = parseBrief(input);
  const rawBlockers = detectBlockers(doc);
  const assumptions = applyAssumptions(doc);
  const tasks = buildTasks(doc, runId, rawBlockers);
  if (input.inject_cycle === true && tasks.length >= 2) {
    const first = tasks[0];
    const last = tasks[tasks.length - 1];
    if (first && last) {
      first.deps = [...first.deps, last.id];
    }
  }
  const sorted = topoSort(tasks);
  if (sorted.cycle.length > 0) {
    return {
      ok: false,
      schema: PLAN_SCHEMA,
      status: "invalid",
      run_id: runId,
      complete: isComplete(parseBrief(input)),
      acyclic: false,
      tasks: [],
      acceptance: [],
      assumptions,
      blockers: [],
      traces: [],
      cards: [],
      error: typedError(E.E_CONFLICT, "circular DAG", "dag"),
    };
  }

  const ordered = sorted.order;
  if (ordered.length === 0) {
    return {
      ok: false,
      schema: PLAN_SCHEMA,
      status: "invalid",
      run_id: runId,
      complete: false,
      acyclic: true,
      tasks: [],
      acceptance: [],
      assumptions,
      blockers: [],
      traces: [],
      cards: [],
      error: typedError(E.E_UNVERIFIED, "empty DAG", "dag"),
    };
  }

  const acceptance: AcceptanceItem[] = doc.acceptance.map((text, i) => {
    const id = accId(i);
    return {
      id,
      text,
      task_ids: ordered.filter((t) => t.acceptance.includes(id)).map((t) => t.id),
    };
  });
  const blockers: Blocker[] = ordered
    .filter((t) => t.kind === "blocker" && t.blocker)
    .map((t) => ({
      code: t.blocker!.code,
      message: t.blocker!.message,
      task_id: t.id,
    }));
  const traces: TraceRow[] = acceptance.map((item) => {
    const covering = ordered.filter((t) => t.acceptance.includes(item.id));
    const define = covering.find((t) => t.kind === "test");
    const produce = covering.find((t) => t.kind === "produce");
    const run = covering.find((t) => t.kind === "verify");
    const ck = covering.find((t) => t.kind === "checkpoint");
    const chosen = produce ?? define;
    const command =
      chosen?.commands[0] ??
      chosen?.verify ??
      define?.commands[0] ??
      "test.define";
    return {
      brief: item.id,
      task: chosen?.id ?? item.task_ids[0] ?? "",
      command,
      test: run ? `test.run:${item.id}` : "",
      checkpoint: ck?.id ?? "",
    };
  });
  return {
    ok: true,
    schema: PLAN_SCHEMA,
    status: blockers.length > 0 ? "blocked" : "ready",
    run_id: runId,
    complete: isComplete(parseBrief(input)),
    acyclic: true,
    tasks: ordered,
    acceptance,
    assumptions,
    blockers,
    traces,
    cards: ordered.map((t) => ({
      id: t.id,
      kind: t.kind,
      summary:
        t.kind === "blocker" && t.blocker
          ? `${t.blocker.code} ${t.blocker.message}`
          : `${t.kind} ${t.verify} ← ${t.acceptance.join(",")}`,
    })),
  };
}

export function renderAssumptionsMarkdown(plan: CompiledPlan): string {
  const lines = [
    "# Assumptions",
    "",
    `Run: ${plan.run_id}`,
    `Schema: ${PLAN_SCHEMA}`,
    `Pin: ${PINNED_GODOT}`,
    "Policy: plan §6.2 (convention → test/revert → fewest deps → quality if cost-equal)",
    "",
  ];
  if (plan.assumptions.length === 0) {
    lines.push("None. Brief specified the small defaults.");
    lines.push("");
    return lines.join("\n");
  }
  for (const a of plan.assumptions) {
    lines.push(`- **${a.id}** \`${a.field}\` = ${a.value} — ${a.rule}`);
  }
  lines.push("");
  lines.push("E1–E4 are blockers, not assumptions.");
  lines.push("");
  return lines.join("\n");
}

function safeRunSeg(runId: string): string | undefined {
  if (!/^[0-7][0-9A-HJKMNPQRSTVWXYZ]{25}$/.test(runId)) {
    return undefined;
  }
  return runId;
}

export function writePlanEvidence(projectRoot: string, plan: CompiledPlan): { assumptions: string; plan: string } {
  const run = safeRunSeg(plan.run_id);
  if (!run) {
    return { assumptions: "", plan: "" };
  }
  const relMd = `r7w1/evidence/${run}/assumptions.md`;
  const relPlan = `r7w1/evidence/${run}/plan.json`;
  const jailedMd = jailProjectPath(projectRoot, relMd, { forWrite: true });
  const jailedPlan = jailProjectPath(projectRoot, relPlan, { forWrite: true });
  if (!jailedMd.ok || !jailedPlan.ok) {
    return { assumptions: "", plan: "" };
  }
  atomicWriteUtf8(jailedMd.abs, renderAssumptionsMarkdown(plan));
  atomicWriteUtf8(jailedPlan.abs, `${JSON.stringify(plan, null, 2)}\n`);
  return { assumptions: relMd, plan: relPlan };
}
