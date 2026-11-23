// Diagonal cover marks (diagonal_marks.js; diagonal cover by hand, KB-20): a corner switched on and off, a mark moved
// and deleted, a map's mark changed, moved, deleted and reset, what a project saves and reads back, and the last
// build's words for a mark.
// Run: node tools/viewer/tests/diagonal_marks_test.mjs
import assert from 'node:assert/strict';
import { addMark, areaWords, builtWords, carryMark, CORNERS, cornerNear, deleteMark, handFromSaved, heightOf, marksNow, middleOf, moveMark,
         movedCentre, ownMarks, resetMark, reworkAreas, reworkWords, reworkedBy, savedDiagonal, setCorners, setHalf, tileOf, tidyHand,
         toggleCorner, turnedCorners } from '../web/diagonal_marks.js';

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
// a mark carried by its piece's move (a view-space matrix, three.js's column-major elements; the view is the game's
// [x, z, y]): moved two tiles along x, one along y and a level up, its tile goes with it and its corners stay
const moveBy = (dx, dy, dz) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, dx, dz, dy, 1];
assert.deepEqual(carryMark(moveBy(192, 96, 64), middleOf([10, 10, 0], corner), [[-1, -1]], corner),
                 { at: middleOf([12, 11, 1], corner), toward: [[-1, -1]] });
// a quarter turn about the mark's tile (about the view's up): the tile stays and the corner turns with it
const turnAbout = (g, deg) => {
  const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), [x, z] = [g[0], g[1]];
  // T(g) R T(-g), R about the view's y: (x, z) -> (x c + z s, -x s + z c)
  return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, x - (x * c + z * s), 0, z - (-x * s + z * c), 1];
};
const home = middleOf([10, 10, 0], corner);
assert.deepEqual(carryMark(turnAbout(home, 90), home, [[-1, -1]], corner), { at: home, toward: [[-1, 1]] });
assert.deepEqual(carryMark(turnAbout(home, 180), home, [[-1, -1], [1, 1]], corner).toward, [[-1, -1], [1, 1]]);
// a turn off the quarter turns takes the corner to the nearest diagonal, and says so
const skewed = carryMark(turnAbout(home, 30), home, [[-1, -1]], corner);
assert.equal(skewed.skew, true);
assert.deepEqual(carryMark(turnAbout(home, 2), home, [[-1, -1]], corner), { at: home, toward: [[-1, -1]] });
// a carried mark whose piece is deleted: the map's mark goes, and nothing is listed for it
const goneWith = [{ at: middleOf([10, 10, 0], corner), toward: [[-1, -1]], from: middleOf([10, 10, 0], corner), by: "XComLevelActor_3", gone: true }];
assert.deepEqual(marksNow(scene, null, corner, goneWith).map(m => m.key), ['12,10,0']);
assert.equal(savedDiagonal(null, goneWith).marks[0].gone, true);
// the Add panel's mark: on an empty tile, toward the corner nearest the click; none on a tile with a mark
const spot = middleOf([20, 20, 0], corner);
assert.deepEqual(cornerNear([20, 20, 0], [spot[0] + 30, spot[1] - 10, spot[2]], corner), [1, -1]);
assert.deepEqual(addMark(scene, null, corner, [20, 20, 0], [1, -1]).marks, [{ at: spot, toward: [[1, -1]] }]);
assert.equal(addMark(scene, null, corner, [10, 10, 0], [1, 1]), null);
// a mark's corners set at once ([ and ] turn them a quarter): a map's mark set back to its own is the map's again
assert.deepEqual(turnedCorners([[-1, -1], [1, 1]], -1), [[-1, 1], [1, -1]]);
assert.deepEqual(turnedCorners([[-1, -1]], 1), [[1, -1]]);
const set = setCorners(scene, null, corner, [10, 10, 0], [[1, -1]]);
assert.deepEqual(set.marks, [{ at: middleOf([10, 10, 0], corner), toward: [[1, -1]], from: middleOf([10, 10, 0], corner) }]);
assert.equal(tidyHand(setCorners(scene, set, corner, [10, 10, 0], [[-1, -1]])), null);
assert.equal(setCorners(scene, null, corner, [30, 30, 0], [[1, 1]]), null);

// Cover, full or half: the map's marks as the map has them (its W corner half), a mark set half and back
const listed = tile => marksNow(scene, null, corner).find(m => m.key === tile);
assert.deepEqual(listed('12,10,0').low, [[1, 1]]);
assert.equal(heightOf(listed('12,10,0')), 'half');
assert.equal(heightOf(listed('10,10,0')), 'full');
assert.equal(heightOf({ toward: [[1, 1], [-1, -1]], low: [[1, 1]] }), 'mixed');
let half = setHalf(scene, null, corner, [10, 10, 0], true);
assert.deepEqual(half.marks, [{ at: home, toward: [[-1, -1]], low: [[-1, -1]], from: home }]);
assert.equal(marksNow(scene, half, corner).find(m => m.key === '10,10,0').kind, 'changed');
assert.equal(tidyHand(setHalf(scene, half, corner, [10, 10, 0], false)), null);      // full again: the map's own
assert.equal(setHalf(scene, null, corner, [10, 10, 0], false), null);                // full already: nothing
const full = setHalf(scene, null, corner, [12, 10, 0], false);
assert.deepEqual(full.marks, [{ at: middleOf([12, 10, 0], corner), toward: [[1, 1]], from: middleOf([12, 10, 0], corner) }]);
// a corner switched on a mark that is all half comes on half; on a mixed or full one, full
half = setHalf(scene, toggleCorner(scene, null, corner, [20, 20, 0], [1, -1]), corner, [20, 20, 0], true);
half = toggleCorner(scene, half, corner, [20, 20, 0], [-1, 1]);
assert.deepEqual(half.marks[0], { at: spot, toward: [[-1, 1], [1, -1]], low: [[-1, 1], [1, -1]] });
const fuller = toggleCorner(scene, setCorners(scene, half, corner, [20, 20, 0], [[-1, 1], [1, -1]], [], [[1, -1]]), corner, [20, 20, 0], [1, 1]);
assert.deepEqual(fuller.marks[0].low, [[1, -1]]);
// turned and moved, the half corners go with their corners; the map's half mark moved home is the map's own again
const turned = setCorners(scene, half, corner, [20, 20, 0], turnedCorners([[-1, 1], [1, -1]], 1), [], turnedCorners([[1, -1]], 1));
assert.deepEqual(turned.marks[0].toward, [[-1, -1], [1, 1]]);
assert.deepEqual(turned.marks[0].low, [[1, 1]]);
const movedHalf = moveMark(scene, null, corner, [12, 10, 0], [12, 11, 0]);
assert.deepEqual(movedHalf.marks[0].low, [[1, 1]]);
assert.equal(tidyHand(moveMark(scene, movedHalf, corner, [12, 11, 0], [12, 10, 0])), null);
// saved and read back with their half corners; half corners a mark doesn't have are dropped, and bad ones refused
assert.deepEqual(tidyHand({ marks: [{ at: spot, toward: [[1, -1]], low: [[1, 1], [1, -1]] }] }).marks[0].low, [[1, -1]]);
const savedHalf = savedDiagonal(half, [{ at: middleOf([40, 40, 0], corner), toward: [[1, 1]], low: [[1, 1]], by: 'X_copy1' }]);
assert.deepEqual(savedHalf.marks[1].low, [[1, 1]]);
assert.deepEqual(handFromSaved(savedHalf).hand, tidyHand(half));
assert.deepEqual(handFromSaved({ marks: [{ at: spot, toward: [[1, 1]], low: 'all' }] }).carriedOver.length, 1);
// a carried mark turns its half corners with it
assert.deepEqual(carryMark(turnAbout(home, 90), home, [[-1, -1], [1, 1]], corner, [[1, 1]]),
                 { at: home, toward: [[-1, 1], [1, -1]], low: [[1, -1]] });
// the areas a streamed level reworks at the battle's start (KB-22, export 41): centre ± radius, floored from the tile
// corner; a cleared map has none of Long War's patch levels; a mission's stream names the missions that stream it
const streamed = { ...scene, missions: [{ label: 'Abduction', streams: ['patch_map'] }, { label: 'Data recovery', streams: ['patch_map', 'Map_CNH'] }],
  streams: { patch_map: { kind: 'lwr', rebuildSpheres: [{ actor: 'V_0', centre: [-1001 + 96 * 20.5, -2001 + 96 * 20.5, -65 + 100], radius: 200 }] },
             Map_CNH: { kind: 'mission', rebuildSpheres: [{ actor: 'V_1', centre: [-1001 + 96 * 40, -2001 + 96 * 40, -65], radius: 10 }] },
             patch_empty: { kind: 'lwr' } } };
const areas = reworkAreas(streamed, corner);
assert.deepEqual(areas.map(a => [a.stream, a.lo, a.hi, a.missions]), [
  ['patch_map', [18, 18, -2], [22, 22, 4], ['Abduction', 'Data recovery']],
  ['Map_CNH', [39, 39, -1], [40, 40, 0], ['Data recovery']]]);
assert.deepEqual(reworkAreas(streamed, corner, { cleared: true }).map(a => a.stream), ['Map_CNH']);
assert.deepEqual(reworkAreas({ ...streamed, preview: true }, corner), []);
assert.deepEqual(reworkAreas(streamed, null), []);
assert.deepEqual(reworkedBy(areas, [20, 20, 0]).map(a => a.actor), ['V_0']);
assert.deepEqual(reworkedBy(areas, [22, 22, 4]).map(a => a.actor), ['V_0']);        // (its far edge's tiles too)
assert.deepEqual(reworkedBy(areas, [23, 20, 0]), []);
assert.deepEqual(reworkedBy(areas, [20, 20, 5]), []);
// the words: the panel's, the tooltip's, several marks', a mission's stream's, none
const hit = reworkedBy(areas, [20, 20, 0]);
assert.equal(reworkWords(hit), "Long War's patch_map reworks this tile at every battle's start, and the game never writes diagonal "
  + 'cover back. Move the mark off the area drawn dashed.');
assert.equal(reworkWords(hit, true), "No cover in the game: Long War's patch_map reworks this tile at every battle's start");
assert.ok(reworkWords(hit, false, 3).startsWith("3 of these marks get no cover in the game: Long War's patch_map reworks their tiles"));
assert.equal(reworkWords(reworkedBy(areas, [40, 40, 0]), true),
             "No cover in the game: Map_CNH (streamed by Data recovery) reworks this tile at the battle's start");
assert.equal(reworkWords([]), '');
assert.equal(areaWords(hit[0]), 'patch_map reworks this area');
// the project's missions: a record it drops streams nothing; an added bomb brings its donor's volumes
const bomb = { stream: 'Donor_Stream', missionObjects: [
  { actor: 'D_V', location: [-1001 + 96 * 30.5, -2001 + 96 * 30.5, -65], rotation: [0, 0, 0], group: 'bomb', role: 'rebuild' }],
  rebuildSpheres: [{ actor: 'D_V', centre: [-1001 + 96 * 30.5 + 20, -2001 + 96 * 30.5, -65], radius: 40 }] };
const withDonor = { ...streamed, donors: { 'Special/Bomb': bomb } };
assert.deepEqual(reworkAreas(withDonor, corner, { missions: [{ record: 0 }] }).map(a => a.stream), ['patch_map']);
const added = reworkAreas(withDonor, corner, { missions: [{ record: 0 }, { kind: 'Special/Bomb' }] });
assert.deepEqual(added.map(a => [a.stream, a.lo, a.hi, a.missions, a.mutator]), [
  ['patch_map', [18, 18, -2], [22, 22, 4], ['Abduction'], false],
  ['Donor_Stream', [30, 30, -1], [31, 30, 0], ['Bomb (added)'], true]]);
assert.deepEqual(reworkAreas(withDonor, corner).map(a => a.stream), ['patch_map', 'Map_CNH']);     // (no added kind: no donor)
// a mission object's volume follows the project's move: moved ten tiles along x and turned a quarter (its offset
// from the actor turns with it), or deleted
const movedTo = { location: [-1001 + 96 * 40.5, -2001 + 96 * 30.5, -65], rotation: [0, 16384, 0] };
assert.deepEqual(movedCentre(bomb.rebuildSpheres[0].centre, bomb.missionObjects[0], movedTo).map(v => Math.round(v)),
                 [-1001 + 96 * 40.5, -2001 + 96 * 30.5 + 20, -65].map(v => Math.round(v)));
const follow = move => reworkAreas(withDonor, corner, { missions: [{ kind: 'Special/Bomb' }], moved: (s, a) => (s === 'Donor_Stream' && a === 'D_V' ? move : null) });
assert.deepEqual(follow(movedTo).map(a => [a.lo, a.hi]), [[[40, 30, -1], [40, 31, 0]]]);
assert.deepEqual(follow({ deleted: true }), []);
assert.ok(reworkWords(added.slice(1)).endsWith('Under Long War its bomb mutator places the bomb and its power nodes itself, and their areas go with them.'));
assert.ok(!reworkWords(added.slice(0, 1)).includes('mutator'));
console.log('diagonal_marks: ok');
