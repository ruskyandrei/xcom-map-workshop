// The build window's words (web/build_window.js; moved out of app.js renderBuild, review finding 22): the steps with
// their states, times and progress, the patch's and the transplant's steps only when they do something, the pieces
// left out and the mission warnings with their counts, the bar against the last build's time, and the log's lines.
// Run: node tools/viewer/tests/build_window_test.mjs
import assert from 'node:assert/strict';
import { BUILD_ROWS, buildBar, buildSteps, flagWords, leftOutList, lightWords, logText, missionWarnings, secondsBetween,
         stepDetail } from '../web/build_window.js';

const at = s => new Date(Date.UTC(2026, 10, 20, 12, 0, s)).toISOString();
assert.equal(secondsBetween(at(0), at(75)), 75);
assert.equal(secondsBetween(at(75), at(0)), 0);
assert.deepEqual(BUILD_ROWS.map(r => r[0]), ['snapshot', 'compile', 'patch', 'transplant', 'light', 'package']);

// a quick build running its light step: done steps timed from the one before, the running one with its progress
const running = { state: 'running', job: { startedAt: at(0), quick: true, progress: { what: 'relighting', done: 3, total: 12 },
  stages: [{ stage: 'snapshot', at: at(4) }, { stage: 'compile', at: at(10), nativeCopies: 2, hides: 1 }] } };
let steps = buildSteps(running);
assert.deepEqual(steps.map(s => [s.key, s.state]), [['snapshot', 'done'], ['compile', 'done'], ['light', 'now'], ['package', 'todo']]);
assert.deepEqual(steps.slice(0, 2).map(s => s.time), ['0:04', '0:06']);
assert.equal(steps[1].detail, '2 copies and 1 hidden piece made in the map');
assert.equal(steps[2].label, 'Make the edit in the map (lighting not baked)');
assert.equal(steps[2].detail, 'Relighting: 3 of 12');
assert.equal(steps[2].progress, 0.25);
assert.deepEqual([steps[3].time, steps[3].progress], ['', null]);

// a failed build: the step it stopped in failed, those after it to do; a transplant shown for pieces from other maps
const failed = { state: 'failed', job: { startedAt: at(0), finishedAt: at(30), stages: [{ stage: 'snapshot', at: at(2) },
  { stage: 'compile', at: at(5), foreignCopies: 1, copierCopies: 1 }] } };
steps = buildSteps(failed);
assert.deepEqual(steps.map(s => [s.key, s.state]), [['snapshot', 'done'], ['compile', 'done'], ['patch', 'failed'], ['transplant', 'todo'],
                                                   ['light', 'todo'], ['package', 'todo']]);
assert.equal(steps[2].time, '0:25');
// built: every step done, the package timed to the end
const built = { state: 'built', job: { startedAt: at(0), finishedAt: at(90), stages: [{ stage: 'snapshot', at: at(2) }, { stage: 'compile', at: at(5) },
  { stage: 'patch', at: at(6), skipped: true }, { stage: 'light', at: at(80), written: 3, unchanged: 40 }] } };
steps = buildSteps(built);
assert.deepEqual(steps.map(s => s.key), ['snapshot', 'compile', 'light', 'package']);
assert.ok(steps.every(s => s.state === 'done'));
assert.deepEqual(steps.map(s => s.time), ['0:02', '0:03', '1:14', '0:10']);
assert.equal(steps[2].detail, '3 pieces relit, 40 unchanged');

// step details
assert.equal(stepDetail('patch', { bytes: 4096 }, {}, false), '4 KB cooked');
assert.equal(stepDetail('transplant', { donors: [{ map: 'URB_Bar', pieces: 2, effects: 3, flares: 1, bytes: 3 << 20 }] }, {}, false),
             '2 pieces and 2 effects and sounds and 1 lens flare from URB_Bar: 3.0 MB more in the map');
assert.equal(stepDetail('light', { baked: false, nativeCopies: 1, lights: 2 }, {}, false), '1 copy made, light edits made, lighting not baked');
assert.equal(stepDetail('light', { lightingUnchanged: true }, {}, false), 'lighting unchanged: no texel to relight');
assert.equal(stepDetail('snapshot', null, { running: 'reading the map' }, true), 'Reading the map…');
assert.equal(stepDetail('snapshot', null, {}, false), '');
assert.equal(lightWords({ moved: 1, added: 2, recipeSpots: 1, area: { moved: 1, copied: 1, pieces: ['a'] } }),
             'lights 1 moved, 2 added (1 from the recipe); 2 glow lights following 1 piece');
assert.equal(flagWords({ inPlace: 2, onCopies: 1, refused: ['X'], regions: 3 }), 'flags written on 2 pieces, 3 tile regions worked out again, not written on X');
assert.equal(lightWords(null), '');

// the pieces left out: the compiler's and the Build's own, counted together; fifty listed
const pieces = n => Array.from({ length: n }, (_, k) => ({ message: `piece ${k}`, actor: `A_${k}` }));
assert.equal(leftOutList(running), null);
let gone = leftOutList({ state: 'built', job: { stages: [{ stage: 'compile', leftOut: 60, leftOutPieces: pieces(48) }, { stage: 'leftout', count: 2, pieces: pieces(2) }] } });
assert.equal(gone.head, '62 pieces left out of this build: they can\'t be built. The rest is built.');
assert.equal(gone.rows.length, 50);
assert.equal(gone.more, '… and 12 more (the build\'s compile-report.json has them all)');
gone = leftOutList({ state: 'running', job: { stages: [{ stage: 'compile', leftOutPieces: pieces(1) }] } });
assert.deepEqual([gone.head, gone.more], ['1 piece left out of this build: it can\'t be built. The rest is being built.', null]);

// mission warnings by mission
assert.equal(missionWarnings(running), null);
const warned = missionWarnings({ job: { stages: [{ stage: 'compile', missionWarningCount: 4, missionWarnings: [
  { mission: 'Bomb', message: 'Bomb: a node is under a piece' }, { mission: 'Bomb', message: 'Bomb: another' }, { mission: null, message: 'x' }] }] } });
assert.match(warned.head, /^4 mission warnings: what the edit does to 2 missions the variant keeps\./);
assert.deepEqual(warned.missions.map(([m, rows]) => [m, rows.length]), [['Bomb', 2], [null, 1]]);
assert.equal(warned.more, '… and 1 more (the build\'s compile-report.json has them all)');

// the bar
assert.deepEqual(buildBar(running, null, 20), { className: 'buildbar running indeterminate', share: 0.3,
  text: 'This project hasn\'t had an unbaked build before, so there is no time to go by.' });
assert.deepEqual(buildBar(running, 100, 40), { className: 'buildbar running', share: 0.4, text: 'About 1:00 left, going by the last unbaked build (1:40).' });
assert.equal(buildBar({ ...running, job: { ...running.job, quick: false } }, 100, 140).text, 'Taking longer than the last baked build (1:40).');
assert.equal(buildBar(running, 100, 140).share, 0.97);
assert.deepEqual(buildBar(built, 60, 90), { className: 'buildbar built', share: 1, text: '' });
assert.equal(buildBar(failed, 60, 30).share, 0.5);

// the log: the latest four lines, the tools' records and commands left out; all of it when full
const job = { lines: ['$ python build.py', 'compile: {"a": 1}', 'one', '  two  ', '', 'three', 'four', 'five'] };
assert.equal(logText(job, false), 'two\nthree\nfour\nfive');
assert.equal(logText(job, true), job.lines.join('\n'));
assert.equal(logText({}, false), '…');
console.log('build window: ok');
