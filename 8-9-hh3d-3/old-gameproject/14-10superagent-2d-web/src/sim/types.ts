import type { PlayerId, WeaponId } from './contract';
export interface Platform {
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
  readonly oneWay?: boolean;
}

export interface Ladder {
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
}

export interface Crate {
  x: number;
  y: number;
  readonly w: number;
  readonly h: number;
  hp: number;
  broken: boolean;
  readonly drop: PickupKind;
  material: 'crate' | 'glass' | 'barrel';
  vx: number;
  vy: number;
}

export type PickupKind = 'medkit' | 'ammo' | 'weapon';

export interface Pickup {
  x: number;
  y: number;
  readonly kind: PickupKind;
  life: number;
}

export interface Projectile {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  readonly owner: PlayerId;
  readonly damage: number;
}

export interface Grenade {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fuse: number;
  readonly owner: PlayerId;
}

export interface Particle {
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

export interface Floater {
  x: number;
  y: number;
  life: number;
  readonly text: string;
  readonly color: string;
}

export interface Fighter {
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
  weapon: WeaponId;
  slowTimer: number;
  dropTimer: number;
  crouching: boolean;
  rollTimer: number;
  rollCooldown: number;
  lastDown: number;
  aim: number;
  coyote: number;
  jumpBuffer: number;
}

export type EventKind = 'jump' | 'shot' | 'throw' | 'melee' | 'hit' | 'pickup' | 'explode' | 'break' | 'land' | 'power' | 'result';
export interface SimEvent { readonly id: number; readonly tick: number; readonly kind: EventKind; readonly x: number; readonly y: number; readonly color: number; readonly text: string; }
export interface Fire { x: number; y: number; life: number; }

