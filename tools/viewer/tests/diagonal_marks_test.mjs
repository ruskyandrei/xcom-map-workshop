// Diagonal cover marks (diagonal_marks.js; diagonal cover by hand, KB-20): a corner switched on and off, a mark moved
// and deleted, a map's mark changed, moved, deleted and reset, what a project saves and reads back, and the last
// build's words for a mark.
// Run: node tools/viewer/tests/diagonal_marks_test.mjs
import assert from 'node:assert/strict';
import { builtWords, CORNERS, deleteMark, handFromSaved, marksNow, middleOf, moveMark, ownMarks, resetMark, savedDiagonal,
         tileOf, tidyHand, toggleCorner } from '../web/diagonal_marks.js';

const corner = [-1001, -2001, -65];
const scene = { tactical: { diagonalCover: [
  { tile: [10, 10, 0], floor: -60, location: null, directions: [{ name: 'E', toward: [-1, -1], low: false }] },
  { tile: [12, 10, 0], floor: -60, location: null, directions: [{ name: 'W', toward: [1, 1], low: true }] }] } };
const kinds = hand => marksNow(scene, hand, corner).map(m => `${m.key}:${m.kind}:${m.toward.map(c => c.join('/')).join('+')}`).sort();

// places: a tile's middle, and back
assert.deepEqual(middleOf([10, 10, 0], corner), [7, -993, -33]);
assert.deepEqual(tileOf(middleOf([3, 7, 2], corner), corner), [3, 7, 2]);
assert.deepEqual(ownMarks(scene).map(o => o.toward), [[[-1, -1]], [[1, 1]]]);
assert.deepEqual(ownMarks({ ...scene, preview: true }), []);
assert.equal(CORNERS.length, 4);

// the map's as it is
assert.deepEqual(kinds(null), ['10,10,0:map:-1/-1', '12,10,0:map:1/1']);

// a corner on an empty tile adds a mark; a second corner joins it; switched off again, the mark goes
let hand = toggleCorner(scene, null, corner, [20, 20, 0], [1, -1]);
assert.deepEqual(hand, { marks: [{ at: middleOf([20, 20, 0], corner), toward: [[1, -1]] }], removed: [] });
hand = toggleCorner(scene, hand, corner, [20, 20, 0], [-1, 1]);
assert.deepEqual(hand.marks[0].toward, [[-1, 1], [1, -1]]);        // (the table's order)
assert.ok(kinds(hand).includes('20,20,0:added:-1/1+1/-1'));
hand = toggleCorner(scene, hand, corner, [20, 20, 0], [-1, 1]);
hand = toggleCorner(scene, hand, corner, [20, 20, 0], [1, -1]);
assert.deepEqual(kinds(hand), kinds(null));
assert.equal(tidyHand(hand), null);

// a map's mark turned: changed, with its home; turned back: the map's own again
hand = toggleCorner(scene, null, corner, [10, 10, 0], [1, 1]);
assert.deepEqual(hand.marks, [{ at: middleOf([10, 10, 0], corner), toward: [[-1, -1], [1, 1]], from: middleOf([10, 10, 0], corner) }]);
assert.ok(kinds(hand).includes('10,10,0:changed:-1/-1+1/1'));
assert.equal(tidyHand(toggleCorner(scene, hand, corner, [10, 10, 0], [1, 1])), null);

// a map's mark moved: listed at its new tile with its home; onto a tile with a mark: refused; moved home: as it was
hand = moveMark(scene, null, corner, [10, 10, 0], [10, 11, 0]);
assert.deepEqual(kinds(hand), ['10,11,0:moved:-1/-1', '12,10,0:map:1/1']);
assert.equal(moveMark(scene, hand, corner, [10, 11, 0], [12, 10, 0]), null);
assert.equal(moveMark(scene, hand, corner, [30, 30, 0], [31, 31, 0]), null);
assert.equal(tidyHand(moveMark(scene, hand, corner, [10, 11, 0], [10, 10, 0])), null);

// a moved map mark deleted: deleted at its home; reset: back as the map has it
let gone = deleteMark(scene, hand, corner, [10, 11, 0]);
assert.deepEqual(gone, { marks: [], removed: [middleOf([10, 10, 0], corner)] });
assert.deepEqual(kinds(gone), ['10,10,0:deleted:-1/-1', '12,10,0:map:1/1']);
assert.equal(tidyHand(resetMark(scene, gone, corner, [10, 10, 0])), null);
assert.equal(resetMark(scene, null, corner, [12, 10, 0]), null);     // (the map's as it is: nothing to reset)
// the last corner of a map's mark switched off deletes it; a corner switched on a deleted one brings it back with it
gone = toggleCorner(scene, null, corner, [12, 10, 0], [1, 1]);
assert.deepEqual(gone.removed, [middleOf([12, 10, 0], corner)]);
const back = toggleCorner(scene, gone, corner, [12, 10, 0], [-1, 1]);
assert.ok(kinds(back).includes('12,10,0:changed:-1/1'), kinds(back));
assert.equal(tidyHand(toggleCorner(scene, gone, corner, [12, 10, 0], [1, 1])), null);     // its own corner: as it was

// an added mark deleted: gone, nothing listed
hand = toggleCorner(scene, null, corner, [5, 5, 1], [1, 1]);
assert.equal(tidyHand(deleteMark(scene, hand, corner, [5, 5, 1])), null);

// what a project saves, and reads back: the carried marks are saved with their piece and worked out again on opening
hand = moveMark(scene, toggleCorner(scene, null, corner, [5, 5, 1], [1, 1]), corner, [10, 10, 0], [10, 12, 0]);
const carried = [{ at: middleOf([40, 40, 0], corner), toward: [[1, 1]], by: 'XComLevelActor_3_copy1' }];
const saved = savedDiagonal(hand, carried, [{ at: 'bad' }]);
assert.equal(saved.marks.length, 4);
assert.deepEqual(saved.marks[2], { at: middleOf([40, 40, 0], corner), toward: [[1, 1]], by: 'XComLevelActor_3_copy1' });
const read = handFromSaved(saved);
assert.deepEqual(read.hand, tidyHand(hand));
assert.deepEqual(read.carriedOver, [{ at: 'bad' }]);
assert.equal(savedDiagonal(null), null);
// a carried mark is listed where no mark of the project's own stands; one that moves its piece's mark leaves its home
assert.ok(marksNow(scene, null, corner, carried).some(m => m.kind === 'carried' && m.key === '40,40,0'));
const moving = [{ at: middleOf([50, 10, 0], corner), toward: [[-1, -1]], from: middleOf([10, 10, 0], corner), by: 'XComLevelActor_3', moves: true }];
assert.deepEqual(marksNow(scene, null, corner, moving).map(m => `${m.key}:${m.kind}`).sort(), ['12,10,0:map', '50,10,0:carried']);
// a carried mark switched is the project's own
const kept = toggleCorner(scene, null, corner, [40, 40, 0], [1, -1], carried);
assert.deepEqual(kept.marks, [{ at: middleOf([40, 40, 0], corner), toward: [[1, -1], [1, 1]] }]);

// the last build's words for a mark, found by its place
const at = middleOf([20, 20, 0], corner);
assert.equal(builtWords({ marks: [{ at, cover: '010002' }] }, at), 'Last build: high cover.');
assert.equal(builtWords({ marks: [{ at, cover: '012022' }] }, at), 'Last build: low cover, a step-out.');
assert.match(builtWords({ marks: [{ at, cover: '010003', noWall: [[-1, 1]] }] }, at), /no wall toward one corner/);
assert.equal(builtWords({ marks: [{ at, cover: '010000', noFloor: true }] }, at), 'Last build: no floor on this tile, so no cover.');
assert.equal(builtWords(null, at), '');
console.log('diagonal_marks: ok');
