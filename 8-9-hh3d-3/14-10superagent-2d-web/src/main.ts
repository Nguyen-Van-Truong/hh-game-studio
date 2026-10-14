import Phaser from 'phaser';
import './style.css';

const VIEW_W = 960;
const VIEW_H = 540;
const FIXED_DT = 1 / 60;
const GRAVITY = 0.42;

type Action = 'left' | 'right' | 'up' | 'down' | 'jump' | 'melee' | 'shoot' | 'throw' | 'power' | 'pause';
type PlayerId = 'p1' | 'p2';

interface InputFrame {
  readonly held: ReadonlySet<Action>;
  readonly pressed: ReadonlySet<Action>;
  readonly released: ReadonlySet<Action>;
}

interface Platform {
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
  readonly oneWay?: boolean;
}

interface Ladder {
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
}

interface Crate {
  x: number;
  y: number;
  readonly w: number;
  readonly h: number;
  hp: number;
  broken: boolean;
}

interface Projectile {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  readonly owner: PlayerId;
}

interface Grenade {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fuse: number;
  readonly owner: PlayerId;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  readonly maxLife: number;
  readonly size: number;
  readonly color: number;
  readonly gravity: number;
}

interface Floater {
  x: number;
  y: number;
  life: number;
  readonly text: string;
  readonly color: string;
}

interface Fighter {
  readonly id: PlayerId;
  readonly name: string;
  readonly color: number;
  readonly glow: number;
  readonly accent: number;
  readonly spawnX: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  facing: -1 | 1;
  health: number;
  ammo: number;
  grenades: number;
  grounded: boolean;
  climbing: boolean;
  hurtTimer: number;
  attackCooldown: number;
  shootCooldown: number;
  invulnerable: number;
  flash: number;
  score: number;
}

function has(frame: InputFrame, action: Action): boolean {
  return frame.held.has(action);
}

function pressed(frame: InputFrame, action: Action): boolean {
  return frame.pressed.has(action);
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function approach(value: number, target: number, amount: number): number {
  if (value < target) return Math.min(value + amount, target);
  if (value > target) return Math.max(value - amount, target);
  return target;
}

function rectsOverlap(ax: number, ay: number, aw: number, ah: number, bx: number, by: number, bw: number, bh: number): boolean {
  return Math.abs(ax - bx) * 2 < aw + bw && Math.abs(ay - by) * 2 < ah + bh;
}

class AudioBus {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;

  unlock(): void {
    if (!this.context) {
      const AudioCtor = window.AudioContext ?? window.webkitAudioContext;
      if (!AudioCtor) return;
      this.context = new AudioCtor();
      this.master = this.context.createGain();
      this.master.gain.value = 0.12;
      this.master.connect(this.context.destination);
    }
    void this.context.resume();
  }

  tone(frequency: number, duration: number, type: OscillatorType = 'sine', gain = 0.08, slide = 0): void {
    if (!this.context || !this.master) return;
    const now = this.context.currentTime;
    const oscillator = this.context.createOscillator();
    const envelope = this.context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, now);
    oscillator.frequency.exponentialRampToValueAtTime(Math.max(30, frequency + slide), now + duration);
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(gain, now + 0.008);
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    oscillator.connect(envelope).connect(this.master);
    oscillator.start(now);
    oscillator.stop(now + duration + 0.02);
  }

  noise(duration = 0.08, gain = 0.07): void {
    if (!this.context || !this.master) return;
    const length = Math.max(1, Math.floor(this.context.sampleRate * duration));
    const buffer = this.context.createBuffer(1, length, this.context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
    const source = this.context.createBufferSource();
    const envelope = this.context.createGain();
    source.buffer = buffer;
    envelope.gain.setValueAtTime(gain, this.context.currentTime);
    envelope.gain.exponentialRampToValueAtTime(0.0001, this.context.currentTime + duration);
    source.connect(envelope).connect(this.master);
    source.start();
  }

  start(): void { this.tone(220, 0.18, 'sawtooth', 0.08, 360); this.tone(440, 0.28, 'triangle', 0.06, 220); }
  jump(): void { this.tone(260, 0.12, 'square', 0.045, 160); }
  shoot(): void { this.noise(0.045, 0.09); this.tone(125, 0.08, 'sawtooth', 0.045, -55); }
  hit(): void { this.tone(95, 0.11, 'square', 0.07, -35); this.noise(0.06, 0.035); }
  pickup(): void { this.tone(620, 0.12, 'triangle', 0.05, 340); this.tone(930, 0.18, 'sine', 0.035, 100); }
  explode(): void { this.noise(0.24, 0.14); this.tone(70, 0.24, 'sawtooth', 0.1, -40); }
}

class InputManager {
  private readonly held = new Set<Action>();
  private readonly pressed = new Set<Action>();
  private readonly released = new Set<Action>();
  private readonly p2Held = new Set<Action>();
  private readonly p2Pressed = new Set<Action>();
  private readonly p2Released = new Set<Action>();

  constructor() {
    window.addEventListener('keydown', (event) => this.handleKey(event.code, true, event));
    window.addEventListener('keyup', (event) => this.handleKey(event.code, false, event));
    document.querySelectorAll<HTMLButtonElement>('[data-action]').forEach((button) => {
      const action = button.dataset.action as Action | undefined;
      if (!action) return;
      const down = (event: PointerEvent): void => { event.preventDefault(); button.classList.add('is-held'); this.set(action, true, false); };
      const up = (event: PointerEvent): void => { event.preventDefault(); button.classList.remove('is-held'); this.set(action, false, false); };
      button.addEventListener('pointerdown', down);
      button.addEventListener('pointerup', up);
      button.addEventListener('pointercancel', up);
      button.addEventListener('pointerleave', up);
    });
  }

  private handleKey(code: string, isDown: boolean, event: KeyboardEvent): void {
    const p1: Partial<Record<string, Action>> = {
      KeyA: 'left', KeyD: 'right', KeyW: 'up', KeyS: 'down', KeyJ: 'melee', KeyK: 'shoot', KeyL: 'throw', Slash: 'power', KeyP: 'pause',
    };
    const p2: Partial<Record<string, Action>> = {
      ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Numpad1: 'melee', Numpad2: 'shoot', Numpad3: 'throw', Numpad4: 'power',
    };
    const action = p1[code];
    const secondAction = p2[code];
    if (action || secondAction || code === 'Space') event.preventDefault();
    if (code === 'Space') { this.set('jump', isDown, false); return; }
    if (action) this.set(action, isDown, false);
    if (secondAction) this.set(secondAction, isDown, true);
  }

  private set(action: Action, isDown: boolean, second: boolean): void {
    const held = second ? this.p2Held : this.held;
    const down = second ? this.p2Pressed : this.pressed;
    const up = second ? this.p2Released : this.released;
    if (isDown) {
      if (!held.has(action)) down.add(action);
      held.add(action);
    } else {
      held.delete(action);
      up.add(action);
    }
  }

  consume(player: PlayerId): InputFrame {
    const held = player === 'p1' ? this.held : this.p2Held;
    const down = player === 'p1' ? this.pressed : this.p2Pressed;
    const up = player === 'p1' ? this.released : this.p2Released;
    const frame: InputFrame = { held: new Set(held), pressed: new Set(down), released: new Set(up) };
    down.clear();
    up.clear();
    return frame;
  }
}

class BattleWorld {
  readonly platforms: Platform[] = [
    { x: 0, y: 478, w: 960, h: 62 },
    { x: 54, y: 365, w: 254, h: 18 },
    { x: 654, y: 365, w: 252, h: 18 },
    { x: 338, y: 286, w: 284, h: 16, oneWay: true },
  ];
  readonly ladders: Ladder[] = [{ x: 470, y: 286, w: 34, h: 192 }];
  readonly crates: Crate[] = [
    { x: 210, y: 442, w: 42, h: 36, hp: 30, broken: false },
    { x: 718, y: 329, w: 40, h: 36, hp: 30, broken: false },
    { x: 566, y: 442, w: 42, h: 36, hp: 30, broken: false },
  ];
  readonly particles: Particle[] = [];
  readonly floaters: Floater[] = [];
  readonly projectiles: Projectile[] = [];
  readonly grenades: Grenade[] = [];
  readonly p1: Fighter = this.makeFighter('p1', 'NOVA', 154, 430, 0x52e5ff, 0xffd166, 0x1b8eff);
  readonly p2: Fighter = this.makeFighter('p2', 'VOLT', 806, 430, 0xff7398, 0xffb35c, 0xd92c90);
  shard = { x: 480, y: 248, active: true, respawn: 0 };
  tick = 0;
  paused = false;
  roundOver = false;
  winner: PlayerId | null = null;
  screenShake = 0;
  private readonly audio: AudioBus;

  constructor(audio: AudioBus) { this.audio = audio; }

  private makeFighter(id: PlayerId, name: string, x: number, y: number, color: number, glow: number, accent: number): Fighter {
    return { id, name, color, glow, accent, spawnX: x, x, y, vx: 0, vy: 0, facing: id === 'p1' ? 1 : -1, health: 100, ammo: 12, grenades: 2, grounded: false, climbing: false, hurtTimer: 0, attackCooldown: 0, shootCooldown: 0, invulnerable: 0, flash: 0, score: 0 };
  }

  reset(): void {
    for (const fighter of [this.p1, this.p2]) {
      fighter.x = fighter.spawnX; fighter.y = 430; fighter.vx = 0; fighter.vy = 0; fighter.health = 100; fighter.ammo = 12; fighter.grenades = 2; fighter.facing = fighter.id === 'p1' ? 1 : -1; fighter.hurtTimer = 0; fighter.invulnerable = 0; fighter.score = 0;
    }
    this.projectiles.length = 0; this.grenades.length = 0; this.particles.length = 0; this.floaters.length = 0;
    this.crates[0].broken = false; this.crates[0].hp = 30; this.crates[1].broken = false; this.crates[1].hp = 30; this.crates[2].broken = false; this.crates[2].hp = 30;
    this.shard = { x: 480, y: 248, active: true, respawn: 0 }; this.roundOver = false; this.winner = null; this.paused = false; this.tick = 0; this.screenShake = 0;
  }

  step(p1Input: InputFrame, p2Input: InputFrame): void {
    if (this.paused || this.roundOver) return;
    this.tick += 1;
    this.updateFighter(this.p1, p1Input, this.p2);
    this.updateFighter(this.p2, p2Input, this.p1);
    this.updateProjectiles();
    this.updateGrenades();
    this.updateParticles();
    this.updateFloaters();
    if (this.shard.active) {
      for (const fighter of [this.p1, this.p2]) {
        if (rectsOverlap(fighter.x, fighter.y, 24, 44, this.shard.x, this.shard.y, 24, 24)) this.collectShard(fighter);
      }
    } else if (this.shard.respawn > 0) {
      this.shard.respawn -= 1;
      if (this.shard.respawn === 0) this.shard.active = true;
    }
    if (this.p1.health <= 0 || this.p2.health <= 0) {
      this.roundOver = true;
      this.winner = this.p1.health > this.p2.health ? 'p1' : 'p2';
      this.addFloater(VIEW_W / 2, 220, `${this.winner === 'p1' ? this.p1.name : this.p2.name} TAKES THE RELAY`, '#ffe08a');
      this.audio.explode();
    }
    this.screenShake = Math.max(0, this.screenShake - 0.18);
  }

  private updateFighter(fighter: Fighter, input: InputFrame, target: Fighter): void {
    fighter.hurtTimer = Math.max(0, fighter.hurtTimer - 1);
    fighter.attackCooldown = Math.max(0, fighter.attackCooldown - 1);
    fighter.shootCooldown = Math.max(0, fighter.shootCooldown - 1);
    fighter.invulnerable = Math.max(0, fighter.invulnerable - 1);
    fighter.flash = Math.max(0, fighter.flash - 1);
    const direction = (has(input, 'right') ? 1 : 0) - (has(input, 'left') ? 1 : 0);
    if (direction !== 0) fighter.facing = direction > 0 ? 1 : -1;
    const ladder = this.findLadder(fighter);
    fighter.climbing = Boolean(ladder && (has(input, 'up') || has(input, 'down')) && !fighter.grounded);
    if (fighter.climbing) {
      fighter.vx = 0; fighter.vy = (has(input, 'down') ? 1 : -1) * 2.1; fighter.y += fighter.vy; fighter.x = ladder ? ladder.x + ladder.w / 2 : fighter.x;
      fighter.y = clamp(fighter.y, ladder?.y ?? 285, (ladder?.y ?? 285) + (ladder?.h ?? 190));
      if (pressed(input, 'jump')) { fighter.climbing = false; fighter.vy = -7.2; this.audio.jump(); }
    } else {
      const maxSpeed = has(input, 'down') ? 2.4 : 4.2;
      fighter.vx = approach(fighter.vx, direction * maxSpeed, fighter.grounded ? 0.85 : 0.42);
      if (direction === 0) fighter.vx = approach(fighter.vx, 0, fighter.grounded ? 0.62 : 0.08);
      if (pressed(input, 'jump') && fighter.grounded) { fighter.vy = -8.5; fighter.grounded = false; this.spawnDust(fighter.x, fighter.y + 22, fighter.accent); this.audio.jump(); }
      fighter.vy += GRAVITY;
      const previousBottom = fighter.y + 22;
      fighter.x += fighter.vx; fighter.y += fighter.vy; fighter.grounded = false;
      this.landOnPlatforms(fighter, previousBottom);
    }
    fighter.x = clamp(fighter.x, 18, VIEW_W - 18);
    if (fighter.y > VIEW_H + 30) { fighter.health -= 20; fighter.x = fighter.spawnX; fighter.y = 430; fighter.vy = 0; fighter.invulnerable = 55; this.addFloater(fighter.x, fighter.y - 38, '-20 PIT', '#ff5c77'); }
    if (fighter.id === 'p2' && this.tick % 5 === 0) this.botThink(fighter, target, input);
    if (pressed(input, 'melee') && fighter.attackCooldown === 0) this.melee(fighter, target);
    if (pressed(input, 'shoot') && fighter.shootCooldown === 0 && fighter.ammo > 0) this.shoot(fighter);
    if (pressed(input, 'throw') && fighter.grenades > 0) this.throwGrenade(fighter);
    if (pressed(input, 'power') && fighter.score > 0) { fighter.score -= 1; fighter.health = Math.min(100, fighter.health + 22); this.addFloater(fighter.x, fighter.y - 38, '+22 OVERCHARGE', '#70e1a1'); this.audio.pickup(); }
  }

  private botThink(bot: Fighter, target: Fighter, current: InputFrame): void {
    if (current.held.size > 0) return;
    const dx = target.x - bot.x;
    if (Math.abs(dx) > 48) bot.vx = Math.sign(dx) * 3.4;
    if (Math.abs(dx) < 250 && this.tick % 55 === 0 && bot.ammo > 0) this.shoot(bot);
    if (target.y + 32 < bot.y && bot.grounded && this.tick % 75 === 0) bot.vy = -8.5;
    if (Math.abs(dx) < 46 && this.tick % 40 === 0) this.melee(bot, target);
  }

  private findLadder(fighter: Fighter): Ladder | undefined {
    return this.ladders.find((ladder) => Math.abs(fighter.x - (ladder.x + ladder.w / 2)) < 24 && fighter.y > ladder.y - 30 && fighter.y < ladder.y + ladder.h + 25);
  }

  private landOnPlatforms(fighter: Fighter, previousBottom: number): void {
    const bottom = fighter.y + 22;
    for (const platform of this.platforms) {
      const horizontal = fighter.x + 12 > platform.x && fighter.x - 12 < platform.x + platform.w;
      const crosses = previousBottom <= platform.y && bottom >= platform.y;
      if (horizontal && crosses && fighter.vy >= 0 && (!platform.oneWay || previousBottom <= platform.y + 2)) {
        fighter.y = platform.y - 22; fighter.vy = 0; fighter.grounded = true;
        return;
      }
    }
    for (const crate of this.crates) {
      if (crate.broken) continue;
      const horizontal = fighter.x + 12 > crate.x && fighter.x - 12 < crate.x + crate.w;
      const crosses = previousBottom <= crate.y && bottom >= crate.y;
      if (horizontal && crosses && fighter.vy >= 0) { fighter.y = crate.y - 22; fighter.vy = 0; fighter.grounded = true; return; }
    }
  }

  private melee(attacker: Fighter, target: Fighter): void {
    attacker.attackCooldown = 22;
    this.spawnArc(attacker.x + attacker.facing * 24, attacker.y - 2, attacker.color);
    if (Math.abs(target.x - attacker.x) < 54 && Math.abs(target.y - attacker.y) < 40) this.damage(target, attacker.facing * 3.6, 14, 'STRIKE');
  }

  private shoot(shooter: Fighter): void {
    shooter.ammo -= 1; shooter.shootCooldown = 15;
    this.projectiles.push({ x: shooter.x + shooter.facing * 24, y: shooter.y - 8, vx: shooter.facing * 9.5, vy: 0, life: 75, owner: shooter.id });
    this.spawnMuzzle(shooter.x + shooter.facing * 22, shooter.y - 8, shooter.color, shooter.facing);
    this.audio.shoot();
  }

  private throwGrenade(thrower: Fighter): void {
    thrower.grenades -= 1;
    this.grenades.push({ x: thrower.x + thrower.facing * 18, y: thrower.y - 14, vx: thrower.facing * 4.6, vy: -6.3, fuse: 76, owner: thrower.id });
    this.spawnSpark(thrower.x + thrower.facing * 19, thrower.y - 14, thrower.accent, 3);
  }

  private damage(target: Fighter, impulse: number, amount: number, label: string): void {
    if (target.invulnerable > 0) return;
    target.health = Math.max(0, target.health - amount); target.vx = impulse; target.vy = -3.2; target.hurtTimer = 16; target.invulnerable = 18; target.flash = 8;
    this.addFloater(target.x, target.y - 32, `-${amount}`, '#ff7a89'); this.spawnHit(target.x, target.y - 8, target.glow); this.screenShake = 4; this.audio.hit();
    if (label === 'STRIKE') this.spawnDust(target.x, target.y + 20, target.accent);
  }

  private updateProjectiles(): void {
    for (let i = this.projectiles.length - 1; i >= 0; i -= 1) {
      const projectile = this.projectiles[i]; projectile.x += projectile.vx; projectile.y += projectile.vy; projectile.life -= 1;
      const target = projectile.owner === 'p1' ? this.p2 : this.p1;
      if (projectile.life <= 0 || projectile.x < -20 || projectile.x > VIEW_W + 20 || this.platforms.some((platform) => projectile.x > platform.x && projectile.x < platform.x + platform.w && projectile.y > platform.y - 3 && projectile.y < platform.y + platform.h)) { this.projectiles.splice(i, 1); continue; }
      if (rectsOverlap(projectile.x, projectile.y, 9, 5, target.x, target.y, 24, 42)) { this.damage(target, projectile.vx > 0 ? 2.8 : -2.8, 9, 'SHOT'); this.projectiles.splice(i, 1); continue; }
      for (const crate of this.crates) {
        if (!crate.broken && rectsOverlap(projectile.x, projectile.y, 9, 5, crate.x + crate.w / 2, crate.y + crate.h / 2, crate.w, crate.h)) { crate.hp -= 10; this.spawnHit(projectile.x, projectile.y, 0xffb15c); this.projectiles.splice(i, 1); if (crate.hp <= 0) this.breakCrate(crate); break; }
      }
    }
  }

  private updateGrenades(): void {
    for (let i = this.grenades.length - 1; i >= 0; i -= 1) {
      const grenade = this.grenades[i]; grenade.vy += GRAVITY * 0.72; grenade.x += grenade.vx; grenade.y += grenade.vy; grenade.fuse -= 1;
      if (grenade.y > 456) { grenade.y = 456; grenade.vy *= -0.45; grenade.vx *= 0.82; }
      if (grenade.fuse <= 0) { this.explode(grenade.x, grenade.y, grenade.owner); this.grenades.splice(i, 1); }
    }
  }

  private explode(x: number, y: number, owner: PlayerId): void {
    this.audio.explode(); this.screenShake = 9;
    for (let i = 0; i < 30; i += 1) this.spawnSpark(x, y, i % 2 === 0 ? 0xffc45e : 0xff557d, 3.5);
    const target = owner === 'p1' ? this.p2 : this.p1;
    const distance = Math.hypot(target.x - x, target.y - y);
    if (distance < 112) this.damage(target, target.x > x ? 4.2 : -4.2, distance < 58 ? 24 : 14, 'BLAST');
    for (const crate of this.crates) if (!crate.broken && Math.hypot(crate.x + crate.w / 2 - x, crate.y + crate.h / 2 - y) < 90) { crate.hp = 0; this.breakCrate(crate); }
  }

  private collectShard(fighter: Fighter): void {
    fighter.score += 1; fighter.health = Math.min(100, fighter.health + 12); fighter.ammo = Math.min(18, fighter.ammo + 4); this.shard.active = false; this.shard.respawn = 360; this.addFloater(fighter.x, fighter.y - 40, 'RELAY +1', '#70e1a1'); this.audio.pickup();
    for (let i = 0; i < 18; i += 1) this.spawnSpark(this.shard.x, this.shard.y, fighter.glow, 2.8);
  }

  private breakCrate(crate: Crate): void {
    crate.broken = true; for (let i = 0; i < 12; i += 1) this.spawnSpark(crate.x + crate.w / 2, crate.y + crate.h / 2, 0xffb15c, 2.2); this.audio.hit();
  }

  private updateParticles(): void {
    for (let i = this.particles.length - 1; i >= 0; i -= 1) { const p = this.particles[i]; p.x += p.vx; p.y += p.vy; p.vy += p.gravity; p.vx *= 0.98; p.life -= 1; if (p.life <= 0) this.particles.splice(i, 1); }
  }

  private updateFloaters(): void {
    for (let i = this.floaters.length - 1; i >= 0; i -= 1) { const f = this.floaters[i]; f.y -= 0.35; f.life -= 1; if (f.life <= 0) this.floaters.splice(i, 1); }
  }

  private spawnParticle(x: number, y: number, color: number, size: number, life: number, speed: number, gravity = 0.02): void {
    if (this.particles.length > 180) this.particles.shift();
    const angle = Math.random() * Math.PI * 2; const velocity = Math.random() * speed;
    this.particles.push({ x, y, vx: Math.cos(angle) * velocity, vy: Math.sin(angle) * velocity, life, maxLife: life, size, color, gravity });
  }

  private spawnSpark(x: number, y: number, color: number, speed: number): void { this.spawnParticle(x, y, color, 2 + Math.random() * 2, 16 + Math.random() * 18, speed, 0.07); }
  private spawnDust(x: number, y: number, color: number): void { for (let i = 0; i < 7; i += 1) this.spawnParticle(x, y, color, 2 + Math.random() * 2, 18, 1.4, 0.03); }
  private spawnHit(x: number, y: number, color: number): void { for (let i = 0; i < 10; i += 1) this.spawnSpark(x, y, color, 3.4); }
  private spawnMuzzle(x: number, y: number, color: number, direction: number): void { for (let i = 0; i < 8; i += 1) this.spawnParticle(x, y, color, 2 + Math.random() * 3, 8 + Math.random() * 8, 2.8, 0); this.spawnParticle(x + direction * 6, y, 0xffffff, 5, 5, 0.4, 0); }
  private spawnArc(x: number, y: number, color: number): void { for (let i = 0; i < 10; i += 1) this.spawnParticle(x, y, color, 2, 10 + i, 2.2, 0); }
  private addFloater(x: number, y: number, text: string, color: string): void { this.floaters.push({ x, y, life: 70, text, color }); }
}

class MainScene extends Phaser.Scene {
  private readonly audio = new AudioBus();
  private readonly inputs = new InputManager();
  private readonly world = new BattleWorld(this.audio);
  private gfx!: Phaser.GameObjects.Graphics;
  private hudLeft!: Phaser.GameObjects.Text;
  private hudRight!: Phaser.GameObjects.Text;
  private statusText!: Phaser.GameObjects.Text;
  private statusLine!: HTMLElement;
  private floaterTexts: Phaser.GameObjects.Text[] = [];
  private accumulator = 0;
  private started = false;

  constructor() { super('main'); }

  create(): void {
    this.gfx = this.add.graphics();
    this.hudLeft = this.add.text(28, 20, '', { fontFamily: 'Arial, sans-serif', fontSize: '16px', color: '#dffaff', fontStyle: 'bold' }).setDepth(4);
    this.hudRight = this.add.text(VIEW_W - 28, 20, '', { fontFamily: 'Arial, sans-serif', fontSize: '16px', color: '#ffe7e7', fontStyle: 'bold', align: 'right' }).setOrigin(1, 0).setDepth(4);
    this.add.text(VIEW_W / 2, 26, 'RELAY YARD // ROUND 01', { fontFamily: 'Arial, sans-serif', fontSize: '11px', color: '#8aa1bb', letterSpacing: 2 }).setOrigin(0.5, 0).setDepth(4);
    this.statusText = this.add.text(VIEW_W / 2, VIEW_H - 24, 'CLICK TO DEPLOY', { fontFamily: 'Arial, sans-serif', fontSize: '11px', color: '#8aa1bb', letterSpacing: 1 }).setOrigin(0.5).setDepth(4);
    this.statusLine = document.querySelector<HTMLElement>('#status-line') ?? document.body;
    for (let i = 0; i < 8; i += 1) this.floaterTexts.push(this.add.text(0, 0, '', { fontFamily: 'Arial, sans-serif', fontSize: '12px', color: '#ffffff', fontStyle: 'bold', stroke: '#07101f', strokeThickness: 3 }).setOrigin(0.5).setDepth(5).setVisible(false));
    const startButton = document.querySelector<HTMLButtonElement>('#start-button');
    startButton?.addEventListener('click', () => { this.started = true; this.audio.unlock(); this.audio.start(); this.statusLine.textContent = 'Live · P to pause · R to redeploy'; document.querySelector('#start-gate')?.classList.add('is-hidden'); document.querySelector('#touch-controls')?.setAttribute('aria-hidden', 'false'); });
    window.addEventListener('keydown', (event) => { if (event.code === 'KeyR' && this.world.roundOver) this.world.reset(); if (event.code === 'KeyP' && this.started) this.world.paused = !this.world.paused; });
    this.scale.on('resize', () => this.cameras.main.setViewport(0, 0, VIEW_W, VIEW_H));
    this.render();
  }

  update(_time: number, delta: number): void {
    if (this.started) {
      const frameDelta = Math.min(delta / 1000, 0.25);
      this.accumulator += frameDelta;
      while (this.accumulator >= FIXED_DT) { this.world.step(this.inputs.consume('p1'), this.inputs.consume('p2')); this.accumulator -= FIXED_DT; }
    }
    this.render();
  }

  private render(): void {
    const g = this.gfx;
    const shake = this.world.screenShake;
    this.cameras.main.setScroll(shake > 0 ? (Math.random() - 0.5) * shake : 0, shake > 0 ? (Math.random() - 0.5) * shake : 0);
    g.clear();
    this.drawBackground(g);
    this.drawArena(g);
    this.drawPickups(g);
    this.drawCrates(g);
    this.drawProjectiles(g);
    this.drawGrenades(g);
    this.drawFighter(g, this.world.p1);
    this.drawFighter(g, this.world.p2);
    this.drawParticles(g);
    this.drawFloaters();
    this.updateHud();
  }

  private drawBackground(g: Phaser.GameObjects.Graphics): void {
    g.fillStyle(0x080d22, 1); g.fillRect(0, 0, VIEW_W, VIEW_H);
    for (let i = 0; i < 7; i += 1) { g.fillStyle(i % 2 === 0 ? 0x101b38 : 0x0d1630, 1); g.fillRect(0, 60 + i * 52, VIEW_W, 52); }
    g.fillStyle(0x183059, 0.36); g.fillCircle(780, 110, 116); g.fillStyle(0x5ce8ff, 0.08); g.fillCircle(780, 110, 78);
    for (let i = 0; i < 17; i += 1) { const x = i * 62 - 12; const height = 62 + ((i * 37) % 112); g.fillStyle(i % 3 === 0 ? 0x172849 : 0x111f3e, 0.95); g.fillRect(x, 478 - height, 48, height); g.fillStyle(0x58d6f1, 0.08); g.fillRect(x + 8, 478 - height + 16, 4, 4); g.fillRect(x + 20, 478 - height + 42, 4, 4); }
    g.lineStyle(1, 0x5fdfff, 0.1); for (let x = 0; x <= VIEW_W; x += 48) g.lineBetween(x, 54, x, 478); for (let y = 94; y < 478; y += 48) g.lineBetween(0, y, VIEW_W, y);
    g.fillStyle(0x050812, 0.28); g.fillRect(0, 452, VIEW_W, 88);
  }

  private drawArena(g: Phaser.GameObjects.Graphics): void {
    for (const platform of this.world.platforms) {
      g.fillStyle(0x263955, 0.98); g.fillRect(platform.x, platform.y, platform.w, platform.h); g.fillStyle(0x6de6ff, platform.oneWay ? 0.8 : 0.42); g.fillRect(platform.x, platform.y, platform.w, 3); g.fillStyle(0x0d1729, 0.7); g.fillRect(platform.x, platform.y + 6, platform.w, platform.h - 6);
      if (platform.oneWay) { g.lineStyle(1, 0xffc56d, 0.7); for (let x = platform.x + 8; x < platform.x + platform.w; x += 18) g.lineBetween(x, platform.y + 8, x + 6, platform.y + 2); }
    }
    const ladder = this.world.ladders[0]; g.lineStyle(3, 0x70e1a1, 0.78); g.lineBetween(ladder.x + 7, ladder.y, ladder.x + 7, ladder.y + ladder.h); g.lineBetween(ladder.x + ladder.w - 7, ladder.y, ladder.x + ladder.w - 7, ladder.y + ladder.h); for (let y = ladder.y + 10; y < ladder.y + ladder.h; y += 14) g.lineBetween(ladder.x + 7, y, ladder.x + ladder.w - 7, y);
    g.fillStyle(0x050812, 0.6); g.fillRect(0, 478, VIEW_W, 62); g.lineStyle(2, 0x52e5ff, 0.32); g.lineBetween(0, 478, VIEW_W, 478);
    g.fillStyle(0xff4d6d, 0.12); g.fillRect(384, 480, 192, 60); g.lineStyle(1, 0xff4d6d, 0.5); g.lineBetween(384, 480, 576, 480); g.lineBetween(384, 492, 576, 492);
  }

  private drawPickups(g: Phaser.GameObjects.Graphics): void {
    if (!this.world.shard.active) return;
    const y = this.world.shard.y + Math.sin(this.world.tick * 0.08) * 4; g.fillStyle(0x70e1a1, 0.16); g.fillCircle(this.world.shard.x, y, 25); g.fillStyle(0x70e1a1, 0.95); g.fillTriangle(this.world.shard.x, y - 16, this.world.shard.x + 11, y, this.world.shard.x, y + 16); g.fillTriangle(this.world.shard.x, y - 16, this.world.shard.x - 11, y, this.world.shard.x, y + 16); g.lineStyle(2, 0xe5fff0, 0.8); g.strokeTriangle(this.world.shard.x, y - 14, this.world.shard.x + 9, y, this.world.shard.x, y + 14);
  }

  private drawCrates(g: Phaser.GameObjects.Graphics): void {
    for (const crate of this.world.crates) if (!crate.broken) { g.fillStyle(0x725b4d, 1); g.fillRect(crate.x, crate.y, crate.w, crate.h); g.lineStyle(2, 0xffb15c, 0.72); g.strokeRect(crate.x + 1, crate.y + 1, crate.w - 2, crate.h - 2); g.lineStyle(1, 0x251d25, 0.7); g.lineBetween(crate.x + 6, crate.y + 7, crate.x + crate.w - 6, crate.y + crate.h - 7); g.lineBetween(crate.x + crate.w - 6, crate.y + 7, crate.x + 6, crate.y + crate.h - 7); }
  }

  private drawProjectiles(g: Phaser.GameObjects.Graphics): void { for (const bullet of this.world.projectiles) { g.fillStyle(0xfff5c8, 0.18); g.fillCircle(bullet.x, bullet.y, 10); g.fillStyle(0xfff5c8, 1); g.fillCircle(bullet.x, bullet.y, 3); g.lineStyle(2, 0xffc56d, 0.65); g.lineBetween(bullet.x - bullet.vx * 1.6, bullet.y, bullet.x - bullet.vx * 0.35, bullet.y); } }
  private drawGrenades(g: Phaser.GameObjects.Graphics): void { for (const grenade of this.world.grenades) { g.fillStyle(0xff4d6d, 0.16); g.fillCircle(grenade.x, grenade.y, 15); g.fillStyle(0xff4d6d, 1); g.fillCircle(grenade.x, grenade.y, 6); g.lineStyle(2, 0xffe08a, 0.9); g.lineBetween(grenade.x, grenade.y - 7, grenade.x + 4, grenade.y - 10); } }

  private drawFighter(g: Phaser.GameObjects.Graphics, fighter: Fighter): void {
    const flash = fighter.flash > 0 ? 0xffffff : fighter.color; const x = fighter.x; const y = fighter.y; const facing = fighter.facing;
    g.fillStyle(fighter.glow, 0.14); g.fillEllipse(x, y + 23, 54, 13); g.fillStyle(0x050812, 0.55); g.fillEllipse(x, y + 22, 30, 7);
    g.fillStyle(flash, 1); g.fillRoundedRect(x - 12, y - 8, 24, 29, 7); g.fillStyle(fighter.accent, 1); g.fillCircle(x, y - 15, 10); g.fillStyle(0x081020, 0.9); g.fillRect(x + facing * 4, y - 17, 6, 3); g.fillStyle(fighter.glow, 0.85); g.fillRect(x - 10, y + 5, 20, 4);
    g.lineStyle(4, fighter.accent, 0.95); g.lineBetween(x - 8, y + 20, x - 11, y + 33); g.lineBetween(x + 8, y + 20, x + 11, y + 33); g.lineStyle(5, flash, 0.95); g.lineBetween(x + facing * 9, y, x + facing * 22, y - 3);
    g.lineStyle(2, 0xffffff, 0.52); g.lineBetween(x + facing * 2, y - 25, x + facing * 12, y - 22);
    if (fighter.invulnerable > 0) { g.lineStyle(2, 0xffffff, 0.55); g.strokeCircle(x, y, 30 + Math.sin(this.world.tick * 0.25) * 2); }
  }

  private drawParticles(g: Phaser.GameObjects.Graphics): void { for (const p of this.world.particles) { const alpha = clamp(p.life / p.maxLife, 0, 1); g.fillStyle(p.color, alpha * 0.9); g.fillCircle(p.x, p.y, p.size * (0.65 + alpha * 0.35)); } }
  private drawFloaters(): void {
    for (let i = 0; i < this.floaterTexts.length; i += 1) {
      const label = this.floaterTexts[i];
      const floater = this.world.floaters[i];
      if (!floater) { label.setVisible(false); continue; }
      label.setVisible(true).setPosition(floater.x, floater.y).setText(floater.text).setColor(floater.color).setAlpha(clamp(floater.life / 22, 0, 1));
    }
  }

  private updateHud(): void {
    const left = this.world.p1; const right = this.world.p2; this.hudLeft.setText(`${left.name}   HP ${Math.ceil(left.health).toString().padStart(3, '0')}   AMMO ${left.ammo.toString().padStart(2, '0')}   RELAY ${left.score}`); this.hudRight.setText(`RELAY ${right.score}   AMMO ${right.ammo.toString().padStart(2, '0')}   HP ${Math.ceil(right.health).toString().padStart(3, '0')}   ${right.name}`);
    this.statusText.setText(this.world.roundOver ? `ROUND OVER — PRESS R TO REDEPLOY` : this.world.paused ? 'PAUSED — PRESS P TO RESUME' : `TICK ${this.world.tick.toString().padStart(5, '0')}  ·  SHARD ${this.world.shard.active ? 'LIVE' : 'RESPAWNING'}`);
    this.statusLine.textContent = this.world.roundOver ? 'Round over · press R to redeploy' : this.world.paused ? 'Paused · press P to resume' : this.started ? 'Live · P to pause · R to redeploy' : 'Awaiting deployment';
    this.hudLeft.setColor(left.health < 35 ? '#ff7a89' : '#dffaff'); this.hudRight.setColor(right.health < 35 ? '#ff7a89' : '#ffe7e7');
  }
}

declare global {
  interface Window { webkitAudioContext?: typeof AudioContext; }
}

new Phaser.Game({
  type: Phaser.AUTO,
  width: VIEW_W,
  height: VIEW_H,
  parent: 'game-root',
  backgroundColor: '#080d22',
  render: { antialias: true, pixelArt: false, roundPixels: true },
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH, width: VIEW_W, height: VIEW_H },
  scene: [MainScene],
});
