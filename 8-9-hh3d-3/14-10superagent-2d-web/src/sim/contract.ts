export const ACTIONS = ['left', 'right', 'up', 'down', 'jump', 'melee', 'shoot', 'throw', 'power', 'weapon', 'roll'] as const;
export type Action = typeof ACTIONS[number];
export type PlayerId = 'p1' | 'p2';
export type WeaponId = 'pulse' | 'scatter';
export interface InputFrame { readonly held: readonly Action[]; readonly pressed: readonly Action[]; readonly released: readonly Action[]; }
export const EMPTY: InputFrame = Object.freeze({ held: Object.freeze([]), pressed: Object.freeze([]), released: Object.freeze([]) });
export function frame(held: readonly Action[] = [], previous: readonly Action[] = []): InputFrame {
  return Object.freeze({ held: Object.freeze([...new Set(held)].sort()), pressed: Object.freeze(held.filter(x => !previous.includes(x))), released: Object.freeze(previous.filter(x => !held.includes(x))) });
}
export const has = (input: InputFrame, action: Action): boolean => input.held.includes(action);
export const pressed = (input: InputFrame, action: Action): boolean => input.pressed.includes(action);
export class SeededRng {
  state: number;
  constructor(seed: number) { this.state = (seed >>> 0) || 0x9e3779b9; }
  next(): number { let v = this.state; v ^= v << 13; v ^= v >>> 17; v ^= v << 5; this.state = v >>> 0; return this.state / 4294967296; }
}
/** Diagnostic hash, not cryptography; quantization epsilon 0.0001 world units. */
export function hash(value: unknown): string {
  const text = JSON.stringify(value, (_key, v: unknown) => typeof v === 'number' ? Math.round(v * 10000) / 10000 : v);
  let result = 2166136261;
  for (let i = 0; i < text.length; i++) { result ^= text.charCodeAt(i); result = Math.imul(result, 16777619); }
  return (result >>> 0).toString(16).padStart(8, '0');
}
