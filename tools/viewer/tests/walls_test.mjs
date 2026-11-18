// The wall tool's pure part (walls.js; custom geometry plan, stage M1): a drag to a wall's pose and numbers, the ends'
// limits, flip, reshuffle, openings added, moved and kept or dropped when the wall is shortened, and what the game
// does at an opening by its sweeps. Run: node tools/viewer/tests/walls_test.mjs
import assert from 'node:assert/strict';
import { drawnWall, flippedWall, movedOpening, openingKind, openingParts, openingPlay, openingWords, playWords,
         PRESETS, raisedWall, resizedWall, reshuffled, shiftedLocation, storeysOf, toolWall, topMostOf, wallDirection, wallRotation,
         wallTop, wallWords, withStoreys, wallJoins, joinWords, END_INSETS,
         withOpening, withoutOpening, WALL } from '../web/walls.js';

const origin = [-2784, -1920, -1];
// the Bar's donor: its location on a tile corner, yaw 0, its z the pavement's top
const template = { location: [-576, -192, 16], rotation: [0, 0, 0] };

// ---- drawing
let d = drawnWall([-180, -200], [210, -170], { origin, template, floor: 16 });
assert.deepEqual(d.location, [-192, -192, 16]);
assert.deepEqual(d.rotation, [0, 0, 0]);
assert.deepEqual(d.wall, { x0: 0, x1: 384, openings: [], seed: 1 });
assert.equal(d.tiles, 4);
// along -y: the start's tile edge, a three-quarter turn of yaw, the line nearest the start
d = drawnWall([10, 290], [-5, 10], { origin, template, floor: 16 });
assert.deepEqual(d.location, [0, 288, 16]);
assert.deepEqual(d.rotation, [0, 49152, 0]);
assert.equal(d.wall.x1, 288);
assert.deepEqual(wallDirection(d.rotation[1]), [0, -1]);
// a click with no drag: one tile; a drag past the longest: the longest
assert.equal(drawnWall([5, 5], [6, 6], { origin, template, floor: 16 }).wall.x1, 96);
assert.equal(drawnWall([0, 0], [5000, 0], { origin, template, floor: 16 }).wall.x1, 96 * WALL.maxTiles);
// the z: the floor under the start (a made wall's height is free of the donor's storeys)
assert.equal(drawnWall([5, 5], [200, 6], { origin, template, floor: 14.5 }).location[2], 14.5);
// quarter turns from the donor's yaw
assert.deepEqual(wallRotation([0, 16384, 0], 0, -1), [0, 32768, 0]);
assert.deepEqual(wallRotation([0, -16384, 0], 1, 1), [0, 16384, 0]);
assert.ok(toolWall(d.wall));
assert.ok(!toolWall({ x0: 0, x1: 100, openings: [], seed: 1 }));
assert.ok(!toolWall({ x0: 96, x1: 192, openings: [], seed: 1 }));

// ---- openings
let wall = { x0: 0, x1: 384, openings: [], seed: 2 };
let r = withOpening(wall, 'doorway');
assert.deepEqual(r.wall.openings, [{ x0: 96, x1: 192, z0: -16, z1: 160 }]);   // the tile nearest the middle, the lower
r = withOpening(r.wall, 'window');
assert.deepEqual(r.wall.openings[1], { x0: 192, x1: 288, z0: 72, z1: 168 });
assert.equal(r.index, 1);
wall = r.wall;
assert.equal(openingKind(wall.openings[0]), 'doorway');
assert.deepEqual(openingParts(wall.openings[0]), ['middle', 'x0', 'x1', 'z1']);
assert.deepEqual(openingParts(wall.openings[1]), ['middle', 'x0', 'x1', 'z1', 'z0']);
// a full wall: none
const full = { x0: 0, x1: 96, openings: [{ x0: 0, x1: 96, z0: -16, z1: 160 }], seed: 1 };
assert.equal(withOpening(full, 'window'), null);
// sides in whole tiles, kept off the neighbour; with fine, in eights
assert.deepEqual(movedOpening(wall, 0, 'x1', 100).openings[0], { x0: 96, x1: 192, z0: -16, z1: 160 });   // the window is there
assert.deepEqual(movedOpening(wall, 0, 'x0', -100).openings[0], { x0: 0, x1: 192, z0: -16, z1: 160 });
assert.deepEqual(movedOpening(wall, 0, 'x0', 70, { fine: true }).openings[0], { x0: 168, x1: 192, z0: -16, z1: 160 });
assert.deepEqual(movedOpening(wall, 0, 'x0', 500, { fine: true }).openings[0].x0, 176);       // at least 16 wide
// the middle slides the opening along, never past its neighbours or the ends
assert.deepEqual(movedOpening(wall, 0, 'middle', -500).openings[0], { x0: 0, x1: 96, z0: -16, z1: 160 });
assert.deepEqual(movedOpening(wall, 1, 'middle', 500).openings[1], { x0: 288, x1: 384, z0: 72, z1: 168 });
// the top under the cornice, a window's sill over the floor, each at least 24 from the other
assert.equal(movedOpening(wall, 0, 'z1', 1000).openings[0].z1, 360);
assert.equal(movedOpening(wall, 0, 'z1', -1000).openings[0].z1, 24);
assert.equal(movedOpening(wall, 1, 'z0', -1000).openings[1].z0, 8);
assert.equal(movedOpening(wall, 1, 'z0', 1000).openings[1].z0, 144);
assert.equal(movedOpening(wall, 0, 'z0', -50).openings[0].z0, -16);        // a doorway has no sill
assert.deepEqual(withoutOpening(wall, 0).openings, [wall.openings[1]]);

// ---- the ends: openings stay where they are in the world; shortening past one drops it
r = resizedWall(wall, 'x1', 200);
assert.deepEqual([r.wall.x1, r.shift, r.removed], [576, 0, 0]);
assert.deepEqual(resizedWall(wall, 'x1', -100).removed, 0);      // the window ends at the new end: kept
r = resizedWall(wall, 'x1', -200);
assert.deepEqual([r.wall.x1, r.removed], [192, 1]);
assert.deepEqual(r.wall.openings, [wall.openings[0]]);
r = resizedWall(wall, 'x0', 100);
assert.deepEqual([r.wall.x1, r.shift, r.removed], [288, 96, 0]);
assert.deepEqual(r.wall.openings, [{ x0: 0, x1: 96, z0: -16, z1: 160 }, { x0: 96, x1: 192, z0: 72, z1: 168 }]);
r = resizedWall(wall, 'x0', -192);
assert.deepEqual([r.wall.x1, r.shift], [576, -192]);
assert.equal(r.wall.openings[0].x0, 288);
assert.equal(resizedWall(wall, 'x1', -5000).wall.x1, 96);
assert.equal(resizedWall(wall, 'x0', 5000).wall.x1, 96);
assert.equal(resizedWall(wall, 'x1', 50000).wall.x1, 96 * WALL.maxTiles);
assert.deepEqual(shiftedLocation([-192, -192, 16], [0, 16384, 0], 96), [-192, -96, 16]);

// ---- flip: the openings stay where they were; reshuffle: a new seed
const f = flippedWall(wall, [-192, -192, 16], [0, 0, 0]);
assert.deepEqual(f.location, [192, -192, 16]);
assert.deepEqual(f.rotation, [0, 32768, 0]);
assert.deepEqual(f.wall.openings, [{ x0: 96, x1: 192, z0: 72, z1: 168 }, { x0: 192, x1: 288, z0: -16, z1: 160 }]);
assert.deepEqual(flippedWall(f.wall, f.location, f.rotation).wall, wall);
assert.equal(reshuffled(wall, 0.5).seed, 500000);
assert.notEqual(reshuffled({ ...wall, seed: 1 }, 0).seed, 1);

// ---- what the game does at an opening
assert.deepEqual(openingPlay(wall, wall.openings[0]), { tiles: 1, walk: true, climb: false, sight: true, cover: 'none' });
assert.deepEqual(openingPlay(wall, wall.openings[1]), { tiles: 1, walk: false, climb: true, sight: true, cover: 'low' });
// a high window: high cover under it, no sight; a low one: walked through
assert.deepEqual(openingPlay(wall, { x0: 0, x1: 96, z0: 112, z1: 200 }), { tiles: 1, walk: false, climb: false, sight: false, cover: 'high' });
assert.deepEqual(openingPlay(wall, { x0: 0, x1: 96, z0: 40, z1: 200 }), { tiles: 1, walk: true, climb: false, sight: true, cover: 'none' });
// an opening between two tiles' centre lines: nothing passes
assert.deepEqual(openingPlay(wall, { x0: 56, x1: 136, z0: -16, z1: 160 }), { tiles: 0, walk: false, climb: false, sight: false, cover: 'whole' });
assert.equal(openingWords(wall.openings[0]), 'Doorway, 1 tile wide, 160 tall');
assert.equal(openingWords(wall.openings[1]), 'Window, 1 tile wide, 96 tall, its sill 72 over the floor');
assert.match(playWords(wall, wall.openings[0]), /^Units walk through it, see and shoot through it; it gives no cover\. A unit in a doorway/);
assert.doesNotMatch(playWords(wall, wall.openings[0], { door: true }), /put a door/);
assert.equal(playWords(wall, wall.openings[1]), 'Units climb through it, see and shoot through it; the wall under it gives low cover.');
assert.equal(wallWords(wall), '4 tiles long, two storeys (400 tall)');

// ---- heights (M2): one storey stands to 192; the top handle steps between the two past half a storey
{
  const tall = { x0: 0, x1: 384, seed: 3, openings: [
    { x0: 0, x1: 96, z0: -16, z1: 160 },        // a doorway: stays
    { x0: 96, x1: 192, z0: 72, z1: 300 },       // a tall window: brought down to 168
    { x0: 192, x1: 288, z0: 200, z1: 300 },     // in the upper storey: goes
  ] };
  assert.equal(storeysOf(tall), 2);
  assert.equal(wallTop(tall), 384);
  const low = withStoreys(tall, 1);
  assert.deepEqual([low.cut, low.removed], [1, 1]);
  assert.equal(low.wall.storeys, 1);
  assert.deepEqual(low.wall.openings.map(o => o.z1), [160, 168]);
  assert.equal(wallTop(low.wall), 192);
  assert.equal(topMostOf(low.wall), 168);
  assert.equal(wallWords(low.wall), '4 tiles long, one storey (208 tall)');
  assert.ok(toolWall(low.wall));
  assert.ok(!toolWall({ ...low.wall, openings: [{ x0: 0, x1: 96, z0: 72, z1: 182 }] }));      // over its face
  assert.ok(!toolWall({ ...low.wall, storeys: 3 }));
  // two leaves the number out (the meshes of M1's walls keep their names)
  const back = withStoreys(low.wall, 2);
  assert.ok(!('storeys' in back.wall));
  assert.equal(storeysOf(back.wall), 2);
  // the top handle: less than half a storey changes nothing; past it, the other height
  assert.equal(raisedWall(tall, -90).wall, tall);
  assert.equal(raisedWall(tall, -100).wall.storeys, 1);
  assert.equal(raisedWall(low.wall, 50).wall, low.wall);
  assert.ok(!('storeys' in raisedWall(low.wall, 100).wall));
  assert.equal(raisedWall(low.wall, -300).wall, low.wall);
  // an opening's top stops 24 under the wall's top
  assert.equal(movedOpening(low.wall, 1, 'z1', 200).openings[1].z1, 168);
  assert.equal(movedOpening(tall, 1, 'z1', 200).openings[1].z1, 360);
}
assert.equal(PRESETS.doorway.z1 - 0, 160);

// ---- joints (M3 item 2): the same cases as test_compiler_generated.test_the_join_rule (compiler.wall_joins is the twin)
{
  const Q = 16384;
  const wall = (key, at, yaw = 0, length = 384, storeys = 2) => ({ key, location: at, rotation: [0, yaw, 0],
    wall: { x0: 0, x1: length, openings: [], seed: 1, ...(storeys === 1 ? { storeys: 1 } : {}) } });
  const ends = walls => Object.fromEntries(Object.entries(wallJoins(walls)).map(([k, v]) => [k, v.ends]));
  assert.deepEqual(ends([wall('a', [0, 0, 0], 0, 480), wall('b', [480, 0, 0], Q)]), { a: ['free', 'through'], b: ['free', 'free'] });
  assert.deepEqual(ends([wall('a', [0, 0, 0]), wall('b', [384, 0, 0], Q, 480)]), { a: ['free', 'free'], b: ['through', 'free'] });
  assert.deepEqual(ends([wall('a', [0, 0, 0], 0, 480, 1), wall('b', [480, 0, 0], Q)]), { a: ['free', 'free'], b: ['through', 'free'] });
  assert.deepEqual(ends([wall('a', [0, 0, 0]), wall('b', [0, 384, 0], -Q)]), { a: ['through', 'free'], b: ['free', 'free'] });
  let found = wallJoins([wall('a', [0, 0, 0], 0, 768), wall('b', [384, 0, 0], Q)]);
  assert.deepEqual([found.a.ends, found.b.ends], [['free', 'free'], ['free', 'free']]);
  assert.deepEqual(found.b.joins, [{ end: 0, how: 'stem', other: 'a' }]);
  assert.deepEqual(ends([wall('a', [0, 0, 0]), wall('b', [384, 0, 0])]), { a: ['free', 'line'], b: ['line', 'free'] });
  found = wallJoins([wall('a', [0, 0, 0]), wall('b', [384, 0, 0]), wall('c', [384, 0, 0], Q)]);
  assert.deepEqual([found.a.ends, found.b.ends, found.c.ends], [['free', 'line'], ['line', 'free'], ['free', 'free']]);
  assert.deepEqual(found.c.joins, [{ end: 0, how: 'stem', other: 'b' }]);
  assert.deepEqual(ends([wall('a', [0, 0, 0]), wall('b', [384, 0, 0]), wall('c', [384, 0, 0], Q), wall('d', [384, -384, 0], Q)]),
                   { a: ['free', 'line'], b: ['line', 'free'], c: ['free', 'free'], d: ['free', 'free'] });
  assert.deepEqual(ends([wall('a', [0, 0, 0], 0, 384, 1), wall('b', [384, 0, 192], Q)]), { a: ['free', 'free'], b: ['free', 'free'] });
  assert.deepEqual(ends([wall('a', [0, 0, 0]), wall('b', [0, 0, 0])]), { a: ['free', 'free'], b: ['free', 'free'] });
  assert.deepEqual(ends([wall('a', [0, 0, 0]), wall('b', [386, 0, 0], Q)]), { a: ['free', 'free'], b: ['free', 'free'] });
  // the words, and the insets the Build uses (frac_wall.END_INSETS)
  assert.deepEqual(END_INSETS, { free: 8, line: 0, through: -8 });
  assert.equal(joinWords([]), '');
  assert.equal(joinWords([{ end: 1, how: 'corner', other: 'b' }]),
               "Joined: its far end runs through at a corner. A break passes between joined walls, as between the game's.");
}
console.log('walls: ok');
