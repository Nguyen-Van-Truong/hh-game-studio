import { ACTIONS, type Action, type InputFrame } from './contract';
import { BattleWorld, RULESET, type Mode } from './world';
export type Command = 'step' | 'pause' | 'resume' | 'reset';
export interface TraceRow { command: Command; p1: InputFrame; p2: InputFrame; }
export interface Trace { version: 1; ruleset: string; seed: number; mode: Mode; rows: TraceRow[]; hash: string; truncated: boolean; }
export const MAX_ROWS=36000;
export function applyRow(world: BattleWorld, row: TraceRow): void {
  if(row.command==='reset') world.reset();
  else if(row.command==='pause' || row.command==='resume') world.setPaused(row.command==='pause');
  else world.step(row.p1,row.p2);
}
export function validateTrace(value: unknown): Trace {
  if(!value || typeof value!=='object') throw new Error('Trace must be an object');
  const t=value as Trace;
  if(t.version!==1 || t.ruleset!==RULESET || !Number.isInteger(t.seed) || t.seed<0 || t.seed>4294967295 || !['bot','local'].includes(t.mode) || t.truncated!==false || !/^[0-9a-f]{8}$/.test(t.hash)) throw new Error('Unsupported or incomplete trace');
  if(!Array.isArray(t.rows) || t.rows.length>MAX_ROWS) throw new Error('Trace exceeds 36,000 rows');
  for(const r of t.rows) {
    if(!r || !['step','pause','resume','reset'].includes(r.command)) throw new Error('Invalid trace command');
    for(const f of [r.p1,r.p2]) for(const key of ['held','pressed','released'] as const) {
      if(!f || !Array.isArray(f[key]) || f[key].length>ACTIONS.length || f[key].some(a=>!ACTIONS.includes(a as Action)) || new Set(f[key]).size!==f[key].length) throw new Error('Invalid input frame');
    }
  }
  return structuredClone(t);
}
export function replay(trace: Trace): { hash: string; matches: boolean; ticks: number } {
  const t=validateTrace(trace), world=new BattleWorld(t.seed,t.mode);
  for(const row of t.rows) applyRow(world,row);
  return {hash:world.hash(),matches:world.hash()===t.hash,ticks:world.tick};
}
/** Integer time accumulator. Pause/focus resets debt; no unbounded catch-up. */
export class FixedClock {
  private debt=0;
  advance(deltaMs: number, run: () => void): number {
    if(!Number.isFinite(deltaMs) || deltaMs<0) return 0;
    this.debt+=Math.min(deltaMs,100)*60;
    let count=0;
    while(this.debt>=1000-1e-7 && count<6) { run(); this.debt-=1000; count++; }
    return count;
  }
  reset(): void { this.debt=0; }
}
