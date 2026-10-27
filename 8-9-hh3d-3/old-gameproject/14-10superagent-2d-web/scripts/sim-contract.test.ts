import assert from 'node:assert/strict';
import { frame, hash, type TraceFrame } from '../src/sim/contract';
import { FixedClock, replay, type Trace } from '../src/sim/replay';
import { BattleWorld } from '../src/sim/world';

const empty = frame();
const walk = frame(['right']);
const shoot = frame(['shoot']);
const traceRows = Array.from({ length: 180 }, (_, index): TraceFrame => ({ p1: index === 0 ? walk : index === 30 ? shoot : empty, p2: empty }));
const worldA = new BattleWorld(0x53414a32, 'bot');
for (const row of traceRows) worldA.step(row.p1, row.p2);
const worldB = new BattleWorld(0x53414a32, 'bot');
for (const row of traceRows) worldB.step(row.p1, row.p2);
assert.equal(worldA.hash(), worldB.hash(), 'same seed + trace must hash identically');
assert.equal(worldA.tick, 180, 'simulation must advance at fixed 60 Hz ticks');

const paused = new BattleWorld(123, 'local');
paused.step(walk, empty);
paused.setPaused(true);
const before = paused.hash();
paused.step(frame(['right', 'shoot']), empty);
const after = paused.hash();
paused.step(frame(['right', 'shoot']), empty);
assert.equal(paused.hash(), after, 'pause must not mutate simulation state after the pause transition');
assert.equal(paused.tick, 1, 'pause must freeze simulation tick');

const replayWorld = new BattleWorld(77, 'local');
for (const row of traceRows.slice(0, 20)) replayWorld.step(row.p1, row.p2);
const replayTrace: Trace = { version: 1, ruleset: 'neon-relay-v2', seed: 77, mode: 'local', rows: traceRows.slice(0, 20).map((row) => ({ command: 'step', ...row })), hash: replayWorld.hash(), truncated: false };
assert.deepEqual(replay(replayTrace), { hash: replayWorld.hash(), matches: true, ticks: 20 });

const clock = new FixedClock();
let ticks = 0;
assert.equal(clock.advance(1000 / 60, () => ticks++), 1);
assert.equal(clock.advance(1000, () => ticks++), 6, 'catch-up is capped to prevent hidden-tab runaway');
assert.equal(ticks, 7);
assert.equal(hash({ b: 2, a: 1 }), hash({ b: 2, a: 1 }));
console.log(`SIM_CONTRACT_PASS hash=${worldA.hash()} trace_ticks=${worldA.tick}`);
