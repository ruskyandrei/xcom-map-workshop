// The edit hub (edit_hub.js): a run calls its refreshes in the order RUNS lists them, whatever order they were
// registered in; STOP ends the run; a name the run doesn't list, or one registered twice, throws; checkHub names those
// not registered. And the page's modules register every name RUNS lists, once each (read from their text).
// Run: node tools/viewer/tests/edit_hub_test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import { checkHub, editChangedNow, onHub, RUNS, runHub, STOP } from '../web/edit_hub.js';

// each run lists its names once
for (const [run, names] of Object.entries(RUNS)) assert.equal(new Set(names).size, names.length, run);

// registered backwards, run in RUNS' order, each given the run's arguments
const called = [];
for (const name of [...RUNS.edit].reverse()) onHub('edit', name, (...args) => { called.push([name, ...args]); });
assert.equal(runHub('edit', 'a', 2), undefined);
assert.deepEqual(called, RUNS.edit.map(name => [name, 'a', 2]));
// editChangedNow is the edit run, given nothing
called.length = 0;
assert.equal(editChangedNow(), undefined);
assert.deepEqual(called, RUNS.edit.map(name => [name]));

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

// checkHub throws while a name has no refresh, naming each; with every one registered it passes
assert.throws(() => checkHub(), /no refresh registered for scene\/cutaway, scene\/ground-grid, scene\/joins, landing-zones\/zones,/);
for (const [run, names] of Object.entries(RUNS))
  for (const name of names) if (!(run === 'edit' || (run === 'drag' && name === 'lights'))) onHub(run, name, () => {});
assert.doesNotThrow(() => checkHub());

// the page's modules register each name of each run once, and nothing else (onHub('run', 'name', ...) in their text)
const web = path.join(path.dirname(url.fileURLToPath(import.meta.url)), '..', 'web');
const found = [];
for (const file of fs.readdirSync(web).filter(f => f.endsWith('.js')))
  for (const m of fs.readFileSync(path.join(web, file), 'utf8').matchAll(/onHub\('([\w-]+)', '([\w-]+)'/g)) found.push(`${m[1]}/${m[2]}`);
const listed = Object.entries(RUNS).flatMap(([run, names]) => names.map(name => `${run}/${name}`));
assert.deepEqual([...found].sort(), [...listed].sort(), 'each run\'s names registered once by the page');
console.log('edit hub: ok');
