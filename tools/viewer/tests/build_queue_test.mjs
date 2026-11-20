// The build queue's page side (web/build_queue.js; private build queue plan, Q2 and Q3): the "Needs a full build"
// filter, the order Build sends, the rows' and the strip's words, honest estimates, and the one controller: its
// cadence, one request at a time, older answers dropped, a 404 ending it, slower while the server doesn't answer.
// Run: node tools/viewer/tests/build_queue_test.mjs
import assert from 'node:assert/strict';
import { CADENCE, chipWords, createQueueController, needsFullBuild, ordinal, requestOrder, rowLine, stripWords,
         timing, timingWords } from '../web/build_queue.js';

// the filter
const v = '0.5.2';
const built = (b = {}) => ({ id: 'p', build: { quick: false, stale: false, editorVersion: v, lightingUnchanged: false, ...b } });
assert.equal(needsFullBuild({ id: 'p' }, v), true, 'not built');
assert.equal(needsFullBuild(built(), v), false, 'a full build of this revision by this version');
assert.equal(needsFullBuild(built({ lightingUnchanged: true }), v), false, 'lighting kept as it was is a full build');
assert.equal(needsFullBuild(built({ quick: true }), v), true, 'not baked');
assert.equal(needsFullBuild(built({ stale: true }), v), true, 'an older revision');
assert.equal(needsFullBuild(built({ editorVersion: '0.5.1' }), v), true, 'another version');
assert.equal(needsFullBuild(built({ editorVersion: null }), v), true, 'an unknown version');
assert.equal(needsFullBuild({ id: 'x', error: 'unreadable' }, v), false, 'unreadable: never');

// the order: the list's sort, hidden ticked rows included, unreadable ones never
const sorted = [{ id: 'c' }, { id: 'a' }, { id: 'x', error: 'bad' }, { id: 'b' }];
assert.deepEqual(requestOrder(sorted, new Set(['b', 'x', 'c'])), ['c', 'b']);
assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 111].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '101st', '111th']);

// rows
const q = (state, items, more = {}) => ({ state, items, queueId: 'q1', revision: 3, counts: counts(items), ...more });
function counts(items) {
  const c = Object.fromEntries(['waiting', 'starting', 'building', 'built', 'failed'].map(s => [s, items.filter(i => i.state === s).length]));
  return { ...c, total: items.length, processed: c.built + c.failed };
}
const building = { itemId: 'i1', project: 'p1', name: 'Bar', state: 'building', revision: 4, elapsed: 100, estimate: 300,
                   job: { stage: 'compile', running: 'relighting', progress: { what: 'relighting', done: 12, total: 85 } } };
const waiting = (n, estimate = 200) => ({ itemId: `w${n}`, project: `pw${n}`, name: `W${n}`, state: 'waiting', position: n, estimate });
let line = rowLine(building, q('running', [building]));
assert.equal(line.text, 'Building: relighting: 12 of 85');
assert.ok(Math.abs(line.progress - 12 / 85) < 1e-9);
assert.equal(rowLine(waiting(2), q('running', [])).text, 'Waiting (2nd)');
assert.equal(rowLine(waiting(1), q('stopped', [])).text, 'Stopped: starts again on Resume');
assert.equal(rowLine({ state: 'failed', error: 'the project does not compile' }, q('finished', [])).text, 'Failed: the project does not compile');
assert.equal(rowLine({ state: 'built', result: { buildId: 'B-1', revision: 4 } }, q('finished', [])).text, 'Built');
assert.equal(rowLine(null, null), null);

// estimates: known time left, unknown rows counted apart, never a whole-queue time with an unknown in it
let t = timing(q('running', [building, waiting(1, 200), waiting(2, null)]));
assert.deepEqual([t.known, t.unknown, t.current.left, t.current.longer], [400, 1, 200, false]);
assert.match(timingWords(q('running', [building, waiting(1, 200), waiting(2, null)])), /About 6:40 for the projects built before, and 1 project without/);
assert.match(timingWords(q('running', [building, waiting(1, 200)])), /^About 6:40 left/);
const late = { ...building, elapsed: 400 };
t = timing(q('running', [late]));
assert.deepEqual([t.current.left, t.current.longer, t.known], [0, true, 0]);       // a floor at zero, not negative
assert.match(timingWords(q('running', [late])), /taking longer than its last build \(5:00\)/);
assert.match(timingWords(q('running', [{ ...building, estimate: null }])), /no full build before/);
assert.match(timingWords(q('running', [waiting(1)], { waitingFor: { kind: 'build', name: 'Other' } })), /is not known/);
for (const bad of [0, -5, NaN, Infinity, '300']) assert.equal(timing(q('running', [waiting(1, bad)])).unknown, 1, String(bad));

// the strip: processed of all (a failure is processed, not built), the stage's progress apart
const failed = { itemId: 'f', project: 'pf', name: 'F', state: 'failed', error: 'no export' };
let strip = stripWords(q('running', [failed, building, waiting(3)]));
assert.equal(strip.title, 'Building 2 of 3: Bar');
assert.equal(strip.progress, 1 / 3);
assert.ok(Math.abs(strip.stage - 12 / 85) < 1e-9);
assert.deepEqual(strip.failures, ['F: no export']);
strip = stripWords(q('finished', [failed, { ...building, state: 'built' }]));
assert.equal(strip.title, '1 project built, 1 failed');
assert.equal(strip.progress, 1);
assert.match(stripWords(q('running', [waiting(1)], { waitingFor: { kind: 'build', name: 'Other bar' } })).title, /^Waiting for Other bar to end/);
assert.match(stripWords(q('stopped', [waiting(1)], { contextChanged: true })).note, /clear it/);
assert.match(stripWords(q('running', [waiting(1)], { fault: 'Disk full.' })).note, /^Disk full\./);
assert.equal(stripWords(q('idle', [])), null);
assert.equal(stripWords({ state: 'unavailable', items: [] }), null);
assert.equal(stripWords({ state: 'unreadable', error: 'torn', items: [] }).note, 'torn');

// the chip
assert.deepEqual(chipWords(q('running', [failed, building, waiting(3)])), { text: 'Building 2 of 3', warn: false });
assert.equal(chipWords(q('stopped', [waiting(1)])).text, 'Queue stopped');
assert.deepEqual(chipWords(q('finished', [failed, { ...building, state: 'built' }])), { text: '1 built, 1 failed', warn: true });
assert.equal(chipWords(q('idle', [])), null);

// the controller
function harness() {
  const timers = [], calls = [], changes = [];
  let answer = null;
  const pending = [];
  const c = createQueueController({
    get: () => new Promise((resolve, reject) => { calls.push('get'); pending.push({ resolve, reject }); }),
    post: async (action, body) => { calls.push([action, body]); if (answer instanceof Error) throw answer; return answer; },
    onChange: (state, info) => changes.push({ state, info }),
    uuid: () => 'u-1',
    timers: { set: (fn, ms) => { timers.push({ fn, ms }); return timers.length; }, clear: () => {} },
  });
  return { c, timers, calls, changes, pending, set answer(v) { answer = v; } };
}
const tick = () => new Promise(r => setTimeout(r, 0));
{
  const h = harness();
  h.c.start();
  h.c.refresh();                                          // one request at a time: this one waits for the first
  assert.equal(h.calls.filter(x => x === 'get').length, 1);
  h.pending.shift().resolve(q('running', [building], { revision: 5 }));
  await tick();
  assert.equal(h.calls.filter(x => x === 'get').length, 2);   // the refresh asked once the first answered
  h.pending.shift().resolve(q('running', [building], { revision: 4 }));     // older: dropped
  await tick();
  assert.equal(h.c.state.revision, 5);
  assert.equal(h.timers.at(-1).ms, CADENCE.active);
  h.c.setOpen(true);
  h.pending.shift().resolve(q('running', [{ ...building, state: 'built' }], { revision: 6 }));
  await tick();
  assert.equal(h.timers.at(-1).ms, CADENCE.open);
  assert.deepEqual(h.changes.at(-1).info.ended.map(i => i.itemId), ['i1']);   // a row that ended: the page refreshes
  // a change: the envelope of the queue last seen; its answer's queue taken as the newest
  h.answer = { appended: ['p9'], queue: q('running', [building], { revision: 7 }) };
  const sent = await h.c.send('add', { projects: ['p9'] });
  assert.deepEqual(h.calls.at(-1), ['add', { queueId: 'q1', expectedRevision: 6, requestId: 'u-1', projects: ['p9'] }]);
  assert.equal(sent.appended[0], 'p9');
  assert.equal(h.c.state.revision, 7);
  // a refused change still brings the queue now
  h.answer = Object.assign(new Error('stale'), { status: 409, body: { queue: q('stopped', [waiting(1)], { revision: 9 }) } });
  await assert.rejects(h.c.send('stop'), /stale/);
  assert.equal(h.c.state.state, 'stopped');
  assert.equal(h.timers.at(-1).ms, CADENCE.open);
}
{
  const h = harness();
  h.c.start();
  h.pending.shift().reject(Object.assign(new Error('offline'), { status: 0 }));
  await tick();
  assert.equal(h.changes.at(-1).info.offline, true);
  assert.equal(h.c.state, null);                          // nothing made up
  assert.equal(h.timers.at(-1).ms, CADENCE.idle * 2);     // slower while the server doesn't answer
  h.timers.at(-1).fn();
  h.pending.shift().reject(Object.assign(new Error('gone'), { status: 404 }));
  await tick();
  assert.equal(h.c.disabled, true);
  const before = h.timers.length;
  h.c.refresh();
  assert.equal(h.timers.length, before);                  // nothing more asked
  assert.equal(h.calls.filter(x => x === 'get').length, 2);
}
// the clock, which the Build panel's estimate shares (build_options.js; review finding 34): whole seconds down
{
  const { clock } = await import('../web/build_queue.js');
  assert.deepEqual([clock(119.6), clock(60), clock(59.99), clock(3725)], ['1:59', '1:00', '0:59', '62:05']);
}
console.log('build_queue_test: ok');
