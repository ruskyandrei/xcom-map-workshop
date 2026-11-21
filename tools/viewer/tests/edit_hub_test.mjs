// The edit hub (edit_hub.js): a run calls its refreshes in the order RUNS lists them, whatever order they were
// registered in; STOP ends the run; a name the run doesn't list, or one registered twice, throws.
// Run: node tools/viewer/tests/edit_hub_test.mjs
import assert from 'node:assert/strict';
import { onHub, RUNS, runHub, STOP } from '../web/edit_hub.js';

// each run lists its names once
for (const [run, names] of Object.entries(RUNS)) assert.equal(new Set(names).size, names.length, run);

// registered backwards, run in RUNS' order, each given the run's arguments
const called = [];
for (const name of [...RUNS.edit].reverse()) onHub('edit', name, (...args) => { called.push([name, ...args]); });
assert.equal(runHub('edit', 'a', 2), undefined);
assert.deepEqual(called, RUNS.edit.map(name => [name, 'a', 2]));

// a name not registered is passed over; STOP ends the run where it is given back
const drag = [];
assert.equal(runHub('drag'), undefined);
onHub('drag', 'lights', () => { drag.push('lights'); return STOP; });
assert.equal(runHub('drag'), STOP);
assert.deepEqual(drag, ['lights']);

// unknown runs and names, and a second registration, throw
assert.throws(() => onHub('edit', 'nothing', () => {}), /no nothing in its edit run/);
assert.throws(() => onHub('nowhere', 'lights', () => {}), /no lights in its nowhere run/);
assert.throws(() => onHub('edit', 'flags', () => {}), /has its flags already/);
console.log('edit hub: ok');
