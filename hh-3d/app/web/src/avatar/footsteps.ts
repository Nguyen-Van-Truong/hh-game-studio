/**
 * Cheap procedural footsteps. Oscillator + noise, no samples.
 * Tied to Person opposite-stride (sin(time) half-cycle = one plant).
 * Self plus quieter accepted-Online remotes. Plants only — no speech,
 * no looped bed, no voices, no music.
 */

export const FOOTSTEP_KIND = "procedural-thump" as const;
/** One silent graph plant + AudioContext resume on Play mount. Not a plant tick. */
export const HITCH_WARMUP_KIND = "audio-compile" as const;
export const WALK_FOOT_GAIN = 0.14;
export const SPRINT_FOOT_GAIN = 0.22;
export const FRIEND_WALK_FOOT_GAIN = 0.05;
export const FRIEND_SPRINT_FOOT_GAIN = 0.08;
export const FRIEND_FOOT_RANGE_M = 25;

export type FootstepFoot = "left" | "right";

export type FootstepReason = "idle" | "airborne" | "hidden" | "overlay" | "";

export type FriendFootstepReason = FootstepReason | "far";

export type FootstepGate = {
  moving: boolean;
  airborne: boolean;
  hidden: boolean;
  overlay: boolean;
};

export type FootstepProof = {
  kind: typeof FOOTSTEP_KIND;
  live: boolean;
  muted: boolean;
  reason: FootstepReason;
  ticks: number;
  foot: FootstepFoot | "";
  sprint: boolean;
  lastGain: number;
};

export type FriendFootstepProof = {
  kind: typeof FOOTSTEP_KIND;
  live: boolean;
  muted: boolean;
  reason: FriendFootstepReason;
  ticks: number;
  foot: FootstepFoot | "";
  lastGain: number;
  lastDistM: number;
  seat: string;
  nearby: number;
};

type Engine = {
  prevTime: number;
  armed: boolean;
  ticks: number;
  foot: FootstepFoot | "";
  lastGain: number;
  audio: { ctx: AudioContext; noise: AudioBuffer } | null;
  audioFailed: boolean;
};

const engine: Engine = {
  prevTime: 0,
  armed: false,
  ticks: 0,
  foot: "",
  lastGain: 0,
  audio: null,
  audioFailed: false,
};

let audioWarmed = false;

type FriendEngine = {
  prevTime: number;
  armed: boolean;
  ticks: number;
  foot: FootstepFoot | "";
  lastGain: number;
  lastDistM: number;
  live: boolean;
  reason: FriendFootstepReason;
};

const friendEngines = new Map<string, FriendEngine>();
/** Seats that may plant this frame. Empty = Offline / no remotes / not opted-in. */
const allowedFriendSeats = new Set<string>();
let lastFriendSeat = "";
let friendSeatsSynced = false;

/** Same opposite-stride clock as applyWalkPose / sampleWalkLimbs. */
export function footFromStride(time: number): FootstepFoot {
  return Math.sin(time) >= 0 ? "left" : "right";
}

/** One plant when the stride sine crosses zero (other foot). */
export function strideFootfall(prevTime: number, time: number): FootstepFoot | null {
  const prev = footFromStride(prevTime);
  const next = footFromStride(time);
  return prev === next ? null : next;
}

export function footstepsLive(gate: FootstepGate): boolean {
  return gate.moving && !gate.airborne && !gate.hidden && !gate.overlay;
}

export function footstepReason(gate: FootstepGate): FootstepReason {
  if (gate.hidden) {
    return "hidden";
  }
  if (gate.overlay) {
    return "overlay";
  }
  if (gate.airborne) {
    return "airborne";
  }
  if (!gate.moving) {
    return "idle";
  }
  return "";
}

export function documentPlayHidden(): boolean {
  return typeof document !== "undefined" && document.hidden === true;
}

/** Menu (Tab) or shop sheet covering Play. */
export function playOverlayCovering(): boolean {
  if (typeof document === "undefined") {
    return false;
  }
  const menu = document.querySelector('[data-testid="play-menu"]');
  if (menu instanceof HTMLElement && menu.dataset.open === "yes") {
    return true;
  }
  const shop = document.querySelector('[data-testid="shop-panel"]');
  return shop instanceof HTMLElement;
}

export function footGain(sprint: boolean): number {
  return sprint ? SPRINT_FOOT_GAIN : WALK_FOOT_GAIN;
}

/** Quieter than self. Linear falloff; silent past FRIEND_FOOT_RANGE_M. */
export function friendFootGain(sprint: boolean, distM: number): number {
  if (distM > FRIEND_FOOT_RANGE_M) {
    return 0;
  }
  const base = sprint ? FRIEND_SPRINT_FOOT_GAIN : FRIEND_WALK_FOOT_GAIN;
  const falloff = 1 - Math.max(0, distM) / FRIEND_FOOT_RANGE_M;
  return base * falloff;
}

function makeNoise(ctx: AudioContext): AudioBuffer {
  const n = Math.max(64, Math.floor(ctx.sampleRate * 0.046));
  const buf = ctx.createBuffer(1, n, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < n; i += 1) {
    const env = 1 - i / n;
    data[i] = (Math.random() * 2 - 1) * env * env;
  }
  return buf;
}

function ensureAudio(): { ctx: AudioContext; noise: AudioBuffer } | null {
  if (engine.audio) {
    return engine.audio;
  }
  if (engine.audioFailed || typeof window === "undefined") {
    return null;
  }
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) {
    engine.audioFailed = true;
    return null;
  }
  try {
    const ctx = new Ctor();
    engine.audio = { ctx, noise: makeNoise(ctx) };
    return engine.audio;
  } catch {
    engine.audioFailed = true;
    return null;
  }
}

/** Compile the thump graph once at gain 0. Does not increment plant ticks. */
function plantSilentTick(): boolean {
  const pack = ensureAudio();
  if (!pack) {
    return false;
  }
  const { ctx, noise } = pack;
  if (ctx.state === "suspended") {
    void ctx.resume();
  }
  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  osc.type = "triangle";
  osc.frequency.setValueAtTime(92, now);
  const og = ctx.createGain();
  og.gain.setValueAtTime(0, now);
  osc.connect(og);
  og.connect(ctx.destination);
  osc.start(now);
  osc.stop(now + 0.02);

  const src = ctx.createBufferSource();
  src.buffer = noise;
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = 880;
  bp.Q.value = 0.9;
  const ng = ctx.createGain();
  ng.gain.setValueAtTime(0, now);
  src.connect(bp);
  bp.connect(ng);
  ng.connect(ctx.destination);
  src.start(now);
  src.stop(now + 0.03);
  return true;
}

/**
 * Play-mount warmup: create/resume AudioContext and plant one silent tick
 * so the first Harbor W does not compile the graph. Not a footstep proof tick.
 */
export function warmupPlayAudio(): boolean {
  const pack = ensureAudio();
  if (!pack) {
    return false;
  }
  if (pack.ctx.state === "suspended") {
    void pack.ctx.resume().then(() => {
      if (!audioWarmed) {
        audioWarmed = plantSilentTick();
      }
    });
  }
  if (!audioWarmed) {
    audioWarmed = plantSilentTick();
  }
  return audioWarmed || pack.ctx.state !== "closed";
}

function playThump(gain: number, sprint: boolean, foot: FootstepFoot): void {
  if (gain < 0.002) {
    return;
  }
  const pack = ensureAudio();
  if (!pack) {
    return;
  }
  const { ctx, noise } = pack;
  if (ctx.state === "suspended") {
    void ctx.resume();
  }
  const now = ctx.currentTime;
  const hz = sprint ? (foot === "left" ? 118 : 108) : foot === "left" ? 92 : 84;
  const thumpMs = sprint ? 0.068 : 0.09;

  const osc = ctx.createOscillator();
  osc.type = "triangle";
  osc.frequency.setValueAtTime(hz, now);
  osc.frequency.exponentialRampToValueAtTime(Math.max(40, hz * 0.42), now + thumpMs);

  const og = ctx.createGain();
  og.gain.setValueAtTime(gain, now);
  og.gain.exponentialRampToValueAtTime(0.0008, now + thumpMs);
  osc.connect(og);
  og.connect(ctx.destination);
  osc.start(now);
  osc.stop(now + thumpMs + 0.02);

  const src = ctx.createBufferSource();
  src.buffer = noise;
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = sprint ? 1400 : 880;
  bp.Q.value = 0.9;
  const ng = ctx.createGain();
  ng.gain.setValueAtTime(gain * 0.38, now);
  ng.gain.exponentialRampToValueAtTime(0.0008, now + 0.042);
  src.connect(bp);
  bp.connect(ng);
  ng.connect(ctx.destination);
  src.start(now);
  src.stop(now + 0.05);
}

function writeProof(proof: FootstepProof): void {
  (globalThis as { __hhFootsteps?: FootstepProof }).__hhFootsteps = proof;
  const live = proof.live ? "1" : "0";
  const sels = [
    "[data-testid='play-view']",
    "[data-testid='play-proof']",
    "[data-testid='walk-cycle-proof']",
    "[data-testid='self-avatar']",
    "[data-testid='footstep-proof']",
    "canvas.play-canvas",
  ];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!(el instanceof HTMLElement)) {
      continue;
    }
    el.dataset.footsteps = live;
    el.dataset.footstepKind = proof.kind;
    el.dataset.footstepTicks = String(proof.ticks);
    el.dataset.footstepMuted = proof.muted ? "1" : "0";
    el.dataset.footstepReason = proof.reason;
    el.dataset.footstepSprint = proof.sprint ? "1" : "0";
    el.dataset.footstepFoot = proof.foot;
  }
}

export function readFootstepProof(): FootstepProof | null {
  return (globalThis as { __hhFootsteps?: FootstepProof }).__hhFootsteps ?? null;
}

function writeFriendProof(focusSeat: string): void {
  let ticks = 0;
  let nearby = 0;
  let live = false;
  let muted = true;
  let reason: FriendFootstepReason = "idle";
  let foot: FootstepFoot | "" = "";
  let lastGain = 0;
  let lastDistM = 0;
  let seat = lastFriendSeat;
  for (const [id, row] of friendEngines) {
    ticks += row.ticks;
    if (row.lastDistM <= FRIEND_FOOT_RANGE_M) {
      nearby += 1;
    }
    if (row.live) {
      live = true;
      muted = false;
      reason = "";
    } else if (!live) {
      if (row.reason === "hidden" || row.reason === "overlay") {
        reason = row.reason;
        muted = true;
      } else if (reason === "idle" && row.reason) {
        reason = row.reason;
      }
    }
    if (id === focusSeat || id === lastFriendSeat) {
      foot = row.foot;
      lastGain = row.lastGain;
      lastDistM = row.lastDistM;
      seat = id;
    }
  }
  if (friendEngines.size === 0 || allowedFriendSeats.size === 0) {
    ticks = 0;
    nearby = 0;
    live = false;
    muted = true;
    reason = "idle";
    seat = "";
  }
  const proof: FriendFootstepProof = {
    kind: FOOTSTEP_KIND,
    live,
    muted,
    reason,
    ticks,
    foot,
    lastGain,
    lastDistM,
    seat,
    nearby,
  };
  (globalThis as { __hhFriendFootsteps?: FriendFootstepProof }).__hhFriendFootsteps = proof;
  const liveBit = live ? "1" : "0";
  const sels = [
    "[data-testid='play-view']",
    "[data-testid='play-proof']",
    "[data-testid='footstep-proof']",
    "[data-testid='friend-footstep-proof']",
    "canvas.play-canvas",
  ];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!(el instanceof HTMLElement)) {
      continue;
    }
    el.dataset.friendFootsteps = liveBit;
    el.dataset.friendFootstepTicks = String(proof.ticks);
    el.dataset.friendFootstepMuted = proof.muted ? "1" : "0";
    el.dataset.friendFootstepReason = proof.reason;
    el.dataset.friendFootstepGain = proof.lastGain.toFixed(3);
    el.dataset.friendFootstepDist = proof.lastDistM.toFixed(1);
    el.dataset.friendFootstepSeat = proof.seat;
  }
  const remoteFocus = allowedFriendSeats.size === 0 ? "" : focusSeat;
  if (remoteFocus) {
    for (const sel of [
      `[data-testid="remote-avatar-${remoteFocus}"]`,
      `[data-testid="remote-walk-cycle-${remoteFocus}"]`,
      `[data-testid="remote-body-${remoteFocus}"]`,
    ]) {
      const el = document.querySelector(sel);
      if (!(el instanceof HTMLElement)) {
        continue;
      }
      const row = friendEngines.get(remoteFocus);
      el.dataset.friendFootsteps = row?.live ? "1" : "0";
      el.dataset.friendFootstepTicks = String(row?.ticks ?? 0);
      el.dataset.friendFootstepMuted = row && !row.live ? "1" : "0";
      el.dataset.friendFootstepReason = row?.reason ?? "";
      el.dataset.friendFootstepGain = (row?.lastGain ?? 0).toFixed(3);
      el.dataset.friendFootstepDist = (row?.lastDistM ?? 0).toFixed(1);
    }
  }
  if (allowedFriendSeats.size === 0 || friendEngines.size === 0) {
    const leftover = document.querySelectorAll(
      "[data-testid^='remote-avatar-'], [data-testid^='remote-walk-cycle-'], [data-testid^='remote-body-']",
    );
    for (const node of leftover) {
      if (!(node instanceof HTMLElement)) {
        continue;
      }
      node.dataset.friendFootsteps = "0";
      node.dataset.friendFootstepTicks = "0";
      node.dataset.friendFootstepMuted = "1";
      node.dataset.friendFootstepReason = "idle";
    }
  }
}

export function readFriendFootstepProof(): FriendFootstepProof | null {
  return (globalThis as { __hhFriendFootsteps?: FriendFootstepProof }).__hhFriendFootsteps ?? null;
}

function cutFriendEngine(seat: string): boolean {
  if (!friendEngines.has(seat)) {
    return false;
  }
  friendEngines.delete(seat);
  if (lastFriendSeat === seat) {
    lastFriendSeat = "";
  }
  return true;
}

export function friendFootstepSeatAllowed(seat: string): boolean {
  return friendSeatsSynced && allowedFriendSeats.size > 0 && allowedFriendSeats.has(seat);
}

/**
 * Call during Play render (not only useEffect). Empty keep cuts every
 * friend plant in this frame — Offline / not opted-in / remotes.length===0.
 */
export function syncFriendFootstepSeats(keep: readonly string[]): void {
  allowedFriendSeats.clear();
  for (const seat of keep) {
    if (seat) {
      allowedFriendSeats.add(seat);
    }
  }
  friendSeatsSynced = true;
  pruneFriendFootsteps(allowedFriendSeats);
}

/** Walker unmount / Offline seat. No leftover stride on the next frame. */
export function cutFriendFootstepSeat(seat: string): void {
  cutFriendEngine(seat);
  writeFriendProof("");
}

export function pruneFriendFootsteps(keep: ReadonlySet<string>): void {
  let changed = false;
  for (const seat of [...friendEngines.keys()]) {
    if (!keep.has(seat)) {
      if (cutFriendEngine(seat)) {
        changed = true;
      }
    }
  }
  if (changed || keep.size === 0 || friendEngines.size === 0) {
    writeFriendProof("");
  }
}

export function armFootstepUnlock(): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  warmupPlayAudio();
  const unlock = () => {
    warmupPlayAudio();
  };
  window.addEventListener("pointerdown", unlock);
  window.addEventListener("keydown", unlock);
  return () => {
    window.removeEventListener("pointerdown", unlock);
    window.removeEventListener("keydown", unlock);
  };
}

/** Self walker. Friends use tickFriendFootsteps (quieter, range-gated). */
export function tickSelfFootsteps(
  time: number,
  state: { moving: boolean; airborne: boolean; sprint: boolean },
): void {
  const hidden = documentPlayHidden();
  const overlay = playOverlayCovering();
  const gate: FootstepGate = {
    moving: state.moving,
    airborne: state.airborne,
    hidden,
    overlay,
  };
  const live = footstepsLive(gate);
  const reason = footstepReason(gate);
  if (!live) {
    engine.armed = false;
    engine.prevTime = time;
    writeProof({
      kind: FOOTSTEP_KIND,
      live: false,
      muted: true,
      reason,
      ticks: engine.ticks,
      foot: engine.foot,
      sprint: false,
      lastGain: engine.lastGain,
    });
    return;
  }
  if (!engine.armed) {
    engine.armed = true;
    engine.prevTime = time;
    writeProof({
      kind: FOOTSTEP_KIND,
      live: true,
      muted: false,
      reason: "",
      ticks: engine.ticks,
      foot: engine.foot,
      sprint: state.sprint,
      lastGain: engine.lastGain,
    });
    return;
  }
  const foot = strideFootfall(engine.prevTime, time);
  engine.prevTime = time;
  if (foot) {
    engine.ticks += 1;
    engine.foot = foot;
    engine.lastGain = footGain(state.sprint);
    playThump(engine.lastGain, state.sprint, foot);
  }
  writeProof({
    kind: FOOTSTEP_KIND,
    live: true,
    muted: false,
    reason: "",
    ticks: engine.ticks,
    foot: engine.foot,
    sprint: state.sprint,
    lastGain: engine.lastGain,
  });
}

/**
 * Accepted Online remotes only (caller is VisibleFriend). Quieter than self.
 * Skip past ~25 m. Mute when the tab is hidden or Play overlay covers.
 * remotes.length===0 / Offline / not opted-in: cut this seat now — no plant
 * in this frame or the next.
 */
export function tickFriendFootsteps(
  seat: string,
  time: number,
  state: { moving: boolean; airborne: boolean; sprint: boolean; distM: number },
): void {
  if (!friendFootstepSeatAllowed(seat)) {
    cutFriendEngine(seat);
    writeFriendProof("");
    return;
  }
  let row = friendEngines.get(seat);
  if (!row) {
    row = {
      prevTime: time,
      armed: false,
      ticks: 0,
      foot: "",
      lastGain: 0,
      lastDistM: state.distM,
      live: false,
      reason: "idle",
    };
    friendEngines.set(seat, row);
  }
  row.lastDistM = state.distM;
  const hidden = documentPlayHidden();
  const overlay = playOverlayCovering();
  const far = state.distM > FRIEND_FOOT_RANGE_M;
  const gate: FootstepGate = {
    moving: state.moving,
    airborne: state.airborne,
    hidden,
    overlay,
  };
  const gated = footstepsLive(gate);
  const live = gated && !far;
  let reason: FriendFootstepReason = footstepReason(gate);
  if (gated && far) {
    reason = "far";
  }
  if (!live) {
    row.armed = false;
    row.prevTime = time;
    row.live = false;
    row.reason = reason;
    writeFriendProof(seat);
    return;
  }
  if (!row.armed) {
    row.armed = true;
    row.prevTime = time;
    row.live = true;
    row.reason = "";
    writeFriendProof(seat);
    return;
  }
  const foot = strideFootfall(row.prevTime, time);
  row.prevTime = time;
  row.live = true;
  row.reason = "";
  if (foot) {
    const gain = friendFootGain(state.sprint, state.distM);
    row.ticks += 1;
    row.foot = foot;
    row.lastGain = gain;
    lastFriendSeat = seat;
    playThump(gain, state.sprint, foot);
  }
  writeFriendProof(seat);
}
