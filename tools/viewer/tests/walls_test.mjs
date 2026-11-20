// The wall tool's pure part (walls.js; custom geometry plan, stage M1): a drag to a wall's pose and numbers, the ends'
// limits, flip, reshuffle, openings added, moved and kept or dropped when the wall is shortened, and what the game
// does at an opening by its sweeps. Run: node tools/viewer/tests/walls_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { drawnWall, flippedWall, movedOpening, openingEdges, openingParts, openingPlay, openingWords, playWords,
         PRESETS, raisedWall, resizedWall, reshuffled, shiftedLocation, storeysOf, toolWall, topMostOf, wallDirection, wallRotation,
         levelsOf, storeyCounts, steppedStoreys,
         wallTop, wallWords, withStoreys, wallJoins, joinWords, END_INSETS, drawnRoom,
         withOpening, withoutOpening, WALL, WALL_LOOKS,
         SLAB, SLAB_LOOKS, drawnSlab, resizedSlab, withHole, withoutHole, movedHole, toolSlab, slabWords, holeWords, roomRoof } from '../web/walls.js';

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
assert.equal(drawnWall([0, 0], [20000, 0], { origin, template, floor: 16 }).wall.x1, 96 * WALL.maxTiles);
// the z: the floor under the start (a made wall's height is free of the donor's storeys)
assert.equal(drawnWall([5, 5], [200, 6], { origin, template, floor: 14.5 }).location[2], 14.5);
// quarter turns from the donor's yaw
assert.deepEqual(wallRotation([0, 16384, 0], 0, -1), [0, 32768, 0]);
assert.deepEqual(wallRotation([0, -16384, 0], 1, 1), [0, 16384, 0]);
assert.ok(toolWall(d.wall));
assert.ok(!toolWall({ x0: 0, x1: 100, openings: [], seed: 1 }));
assert.ok(!toolWall({ x0: 96, x1: 192, openings: [], seed: 1 }));

// ---- gaps (one kind since 19 November 2026: every handle reaches the wall's edges)
let wall = { x0: 0, x1: 384, openings: [], seed: 2 };
let r = withOpening(wall, 'doorway');
// the tile nearest the middle, the lower; a threshold of 8 under it
assert.deepEqual(r.wall.openings, [{ x0: 96, x1: 192, z0: 8, z1: 160 }]);
r = withOpening(r.wall, 'window');
assert.deepEqual(r.wall.openings[1], { x0: 192, x1: 288, z0: 72, z1: 168 });
assert.equal(r.index, 1);
wall = r.wall;
assert.deepEqual(openingParts(), ['middle', 'x0', 'x1', 'z1', 'z0']);
// a full wall: none
const full = { x0: 0, x1: 96, openings: [{ x0: 0, x1: 96, z0: -16, z1: 160 }], seed: 1 };
assert.equal(withOpening(full, 'window'), null);
// sides: by whole tiles (the default step), kept off the neighbour, to the wall's end; in eights; smoothly
assert.deepEqual(movedOpening(wall, 0, 'x1', 100).openings[0], { x0: 96, x1: 192, z0: 8, z1: 160 });   // the window is there
assert.deepEqual(movedOpening(wall, 0, 'x0', -100).openings[0], { x0: 0, x1: 192, z0: 8, z1: 160 });
assert.deepEqual(movedOpening(wall, 0, 'x0', 70, { along: 8 }).openings[0], { x0: 168, x1: 192, z0: 8, z1: 160 });
assert.equal(movedOpening(wall, 0, 'x0', 500, { along: 8 }).openings[0].x0, 176);       // at least 16 wide
assert.equal(movedOpening(wall, 0, 'x0', 13.4, { along: 1 }).openings[0].x0, 109);
assert.equal(movedOpening(wall, 1, 'x1', 41, { along: 1 }).openings[1].x1, 329);
assert.equal(movedOpening(wall, 1, 'x1', 1000, { along: 1 }).openings[1].x1, 384);
// the middle slides the gap along, never past its neighbours or the ends
assert.deepEqual(movedOpening(wall, 0, 'middle', -500).openings[0], { x0: 0, x1: 96, z0: 8, z1: 160 });
assert.deepEqual(movedOpening(wall, 1, 'middle', 500).openings[1], { x0: 288, x1: 384, z0: 72, z1: 168 });
assert.deepEqual(movedOpening(wall, 1, 'middle', 7, { along: 1 }).openings[1], { x0: 199, x1: 295, z0: 72, z1: 168 });
// (the user, 19 November 2026) and up and down, [along, up], its height kept: up to the highest a gap's top goes under
// the cornice; down to the floor, where it is cut to the wall's bottom (a doorway); one cut through the top stays put
assert.deepEqual(movedOpening(wall, 1, 'middle', [0, 100], { along: 96, up: 24 }).openings[1], { x0: 192, x1: 288, z0: 168, z1: 264 });
assert.deepEqual(movedOpening(wall, 1, 'middle', [0, 1000], { along: 96, up: 24 }).openings[1], { x0: 192, x1: 288, z0: 264, z1: 360 });
assert.deepEqual(movedOpening(wall, 1, 'middle', [0, -1000], { along: 96, up: 24 }).openings[1], { x0: 192, x1: 288, z0: -16, z1: 96 });
assert.deepEqual(movedOpening(wall, 1, 'middle', [96, 24], { along: 96, up: 24 }).openings[1], { x0: 288, x1: 384, z0: 96, z1: 192 });
assert.deepEqual(movedOpening(wall, 0, 'middle', [0, 48], { along: 96, up: 24 }).openings[0], { x0: 96, x1: 192, z0: 48, z1: 200 });
const through = { ...wall, openings: [{ x0: 96, x1: 192, z0: 100, z1: 384 }] };
assert.deepEqual(movedOpening(through, 0, 'middle', [96, 50], { along: 96, up: 24 }).openings[0], { x0: 192, x1: 288, z0: 100, z1: 384 });
// the top: under the cornice, or past it cut through the wall's top; the bottom: over the floor, or at it cut to the
// wall's bottom; each at least 24 from the other
assert.equal(movedOpening(wall, 0, 'z1', 200).openings[0].z1, 360);
assert.equal(movedOpening(wall, 0, 'z1', 201, { up: 1 }).openings[0].z1, 384);
assert.equal(movedOpening(wall, 0, 'z1', 1000).openings[0].z1, 384);
assert.equal(movedOpening(wall, 0, 'z1', -1000).openings[0].z1, 32);
assert.equal(movedOpening(wall, 0, 'z0', -8).openings[0].z0, -16);
assert.equal(movedOpening(wall, 0, 'z0', -5, { up: 1 }).openings[0].z0, 3);
assert.equal(movedOpening(wall, 1, 'z0', -1000).openings[1].z0, -16);
assert.equal(movedOpening(wall, 1, 'z0', 1000).openings[1].z0, 144);
// a gap cut to the wall's bottom has its bottom handle on the floor: it moves from there
{
  const cut = movedOpening(wall, 0, 'z0', -100);
  assert.equal(movedOpening(cut, 0, 'z0', 5, { up: 1 }).openings[0].z0, 5);
  assert.deepEqual(openingEdges(cut, cut.openings[0]), { bottom: true, top: false, start: false, end: false });
  assert.ok(toolWall(cut));
}
// a gap never takes the whole wall: the last edge it would reach stays short of it
{
  const slot = { x0: 0, x1: 96, openings: [{ x0: 0, x1: 96, z0: -16, z1: 160 }], seed: 1 };
  assert.equal(movedOpening(slot, 0, 'z1', 1000).openings[0].z1, 360);
  const strip = { x0: 0, x1: 96, openings: [{ x0: 0, x1: 96, z0: 8, z1: 384 }], seed: 1 };
  assert.equal(movedOpening(strip, 0, 'z0', -100).openings[0].z0, 8);
  const half = { x0: 0, x1: 192, openings: [{ x0: 0, x1: 96, z0: -16, z1: 384 }], seed: 1 };
  assert.equal(movedOpening(half, 0, 'x1', 1000, { along: 1 }).openings[0].x1, 176);
  assert.ok(toolWall(half));
  assert.ok(!toolWall({ ...half, openings: [{ x0: 0, x1: 192, z0: -16, z1: 384 }] }));
  // (review finding 32: a one-tile wall's gap moved by whole tiles never closes up, and stays a gap the tool makes)
  const narrow = { x0: 0, x1: 96, openings: [{ x0: 0, x1: 48, z0: -16, z1: 384 }], seed: 1 };
  for (const [index, part, delta] of [[0, 'x1', 100], [0, 'x1', 40]]) {
    const moved = movedOpening(narrow, index, part, delta);
    assert.deepEqual(moved.openings[0], narrow.openings[0]);
    assert.ok(toolWall(moved));
  }
  const right = { x0: 0, x1: 96, openings: [{ x0: 48, x1: 96, z0: -16, z1: 384 }], seed: 1 };
  assert.deepEqual(movedOpening(right, 0, 'x0', -100).openings[0], right.openings[0]);
  // (a gap that reaches the end from the start: the fallback keeps it OPENING.width wide, never zero)
  const whole = { x0: 0, x1: 96, openings: [{ x0: 0, x1: 96, z0: -16, z1: 384 }], seed: 1 };
  assert.deepEqual(['x0', 'x1'].map(part => { const o = movedOpening(whole, 0, part, part === 'x0' ? -10 : 10).openings[0]; return o.x1 - o.x0; }),
                   [16, 16]);
  assert.equal(movedOpening(half, 0, 'x1', 1000).openings[0].x1, 96);      // (whole tiles: a tile in, as before)
}
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
assert.deepEqual(r.wall.openings, [{ x0: 0, x1: 96, z0: 8, z1: 160 }, { x0: 96, x1: 192, z0: 72, z1: 168 }]);
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
assert.deepEqual(f.wall.openings, [{ x0: 96, x1: 192, z0: 72, z1: 168 }, { x0: 192, x1: 288, z0: 8, z1: 160 }]);
assert.deepEqual(flippedWall(f.wall, f.location, f.rotation).wall, wall);
assert.equal(reshuffled(wall, 0.5).seed, 500000);
assert.notEqual(reshuffled({ ...wall, seed: 1 }, 0).seed, 1);
// (a floor's Reshuffle never gives back its seed either: review finding 34)
{
  const { reshuffledSlab } = await import('../web/walls.js');
  const slab = { x0: 0, x1: 192, y0: 0, y1: 192, holes: [], seed: 500000 };
  assert.notEqual(reshuffledSlab(slab, 0.4999995).seed, 500000);
  assert.notEqual(reshuffledSlab({ ...slab, seed: 1 }, 0).seed, 1);
  assert.equal(reshuffledSlab(slab, 0.25).seed, 250000);
}

// ---- what the game does at an opening
assert.deepEqual(openingPlay(wall, wall.openings[0]), { tiles: 1, walk: true, climb: false, sight: true, cover: 'none' });
assert.deepEqual(openingPlay(wall, wall.openings[1]), { tiles: 1, walk: false, climb: true, sight: true, cover: 'low' });
// a high window: high cover under it, no sight; a low one: walked through
assert.deepEqual(openingPlay(wall, { x0: 0, x1: 96, z0: 112, z1: 200 }), { tiles: 1, walk: false, climb: false, sight: false, cover: 'high' });
assert.deepEqual(openingPlay(wall, { x0: 0, x1: 96, z0: 40, z1: 200 }), { tiles: 1, walk: true, climb: false, sight: true, cover: 'none' });
// an opening between two tiles' centre lines: nothing passes
assert.deepEqual(openingPlay(wall, { x0: 56, x1: 136, z0: -16, z1: 160 }), { tiles: 0, walk: false, climb: false, sight: false, cover: 'whole' });
assert.equal(openingWords(wall.openings[0], wall), 'Gap, 1 tile wide, from 8 over the floor to 160');
assert.equal(openingWords(wall.openings[1], wall), 'Gap, 1 tile wide, from 72 over the floor to 168');
assert.equal(openingWords({ x0: 0, x1: 100, z0: -16, z1: 384 }, wall), 'Gap, 100 wide, from the wall\'s bottom to its top, at its start');
assert.equal(openingWords({ x0: 0, x1: 384, z0: 8, z1: 384 }, wall), 'Gap, 4 tiles wide, from 8 over the floor to its top, at its start and its end');
assert.match(playWords(wall, wall.openings[0]), /^Units walk through it, see and shoot through it; it gives no cover\. A unit in a gap/);
// walked through over a wall that gives cover: no door asked for
assert.doesNotMatch(playWords(wall, { x0: 0, x1: 96, z0: 50, z1: 200 }), /put a door/);
assert.doesNotMatch(playWords(wall, wall.openings[0], { door: true }), /put a door/);
assert.equal(playWords(wall, wall.openings[1]), 'Units climb through it, see and shoot through it; the wall under it gives low cover.');
assert.equal(wallWords(wall), '4 tiles long, two storeys (400 tall)');

// ---- heights (M2): one storey stands to 192; the top handle steps between the two past half a storey
{
  const tall = { x0: 0, x1: 384, seed: 3, openings: [
    { x0: 0, x1: 96, z0: -16, z1: 160 },        // a doorway: stays
    { x0: 96, x1: 192, z0: 72, z1: 300 },       // a tall window: brought down to 168
    { x0: 192, x1: 288, z0: 200, z1: 300 },     // in the upper storey: goes
    { x0: 288, x1: 384, z0: 8, z1: 384 },       // cut through the top: stays so
  ] };
  assert.equal(storeysOf(tall), 2);
  assert.equal(wallTop(tall), 384);
  const low = withStoreys(tall, 1);
  assert.deepEqual([low.cut, low.removed], [1, 1]);
  assert.equal(low.wall.storeys, 1);
  assert.deepEqual(low.wall.openings.map(o => o.z1), [160, 168, 192]);
  assert.equal(wallTop(low.wall), 192);
  assert.equal(topMostOf(low.wall), 168);
  assert.equal(wallWords(low.wall), '4 tiles long, one storey (208 tall)');
  assert.ok(toolWall(low.wall));
  assert.ok(toolWall({ ...low.wall, openings: [{ x0: 0, x1: 96, z0: 72, z1: 192 }] }));      // through its top
  assert.ok(!toolWall({ ...low.wall, openings: [{ x0: 0, x1: 96, z0: 72, z1: 200 }] }));     // over it
  assert.ok(toolWall({ ...low.wall, storeys: 3 }));
  assert.ok(!toolWall({ ...low.wall, storeys: 13 }));
  // two leaves the number out (the meshes of M1's walls keep their names)
  const back = withStoreys(low.wall, 2);
  assert.ok(!('storeys' in back.wall));
  assert.equal(storeysOf(back.wall), 2);
  assert.deepEqual(back.wall.openings.map(o => o.z1), [160, 168, 384]);
  // the top handle: less than half a storey changes nothing; past it, the other height
  assert.equal(raisedWall(tall, -90).wall, tall);
  assert.equal(raisedWall(tall, -100).wall.storeys, 1);
  assert.equal(raisedWall(low.wall, 50).wall, low.wall);
  assert.ok(!('storeys' in raisedWall(low.wall, 100).wall));
  assert.equal(raisedWall(low.wall, -300).wall, low.wall);
  // a gap's top stops 24 under the wall's top, or past that is cut through it
  assert.equal(movedOpening(low.wall, 1, 'z1', -8).openings[1].z1, 160);
  assert.equal(movedOpening(low.wall, 1, 'z1', 200).openings[1].z1, 192);
  assert.equal(movedOpening(tall, 1, 'z1', 60).openings[1].z1, 360);
  assert.equal(movedOpening(tall, 1, 'z1', 200).openings[1].z1, 384);
}
assert.deepEqual([PRESETS.doorway.z0, PRESETS.doorway.z1], [8, 160]);

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
// ---- rooms (M3 item 6): four walls round the rectangle, anticlockwise, their corners joined, a doorway nearest the camera
{
  const room = drawnRoom([-180, -200], [210, 100], { origin, template, floor: 16, seed: 5, camera: [0, -2000] });
  assert.deepEqual(room.tiles, [4, 3]);
  assert.deepEqual(room.walls.map(w => [w.location, w.rotation[1], w.wall.x1]),
                   [[[-192, -192, 16], 0, 384], [[192, -192, 16], 16384, 288], [[192, 96, 16], 32768, 384], [[-192, 96, 16], 49152, 288]]);
  assert.equal(room.door, 0);                       // the south side faces the camera
  assert.deepEqual(room.walls[0].wall.openings, [{ x0: 96, x1: 192, z0: 8, z1: 160 }]);
  assert.ok(room.walls.slice(1).every(w => !w.wall.openings.length));
  assert.deepEqual(room.walls.map(w => w.wall.seed), [5, 6, 7, 8]);
  // drawn from the far corner the other way round: the same rectangle
  const back = drawnRoom([210, 100], [-180, -200], { origin, template, floor: 16, seed: 5, camera: [2000, 0] });
  assert.deepEqual(back.walls.map(w => w.location), room.walls.map(w => w.location));
  assert.equal(back.door, 1);                       // the east side faces this camera
  // the four corners join: the longer sides run through
  const found = wallJoins(room.walls.map((w, k) => ({ key: String(k), ...w })));
  assert.deepEqual(Object.values(found).map(v => v.ends), [['through', 'through'], ['free', 'free'], ['through', 'through'], ['free', 'free']]);
  // a click: one tile each way; a long drag: the longest
  assert.deepEqual(drawnRoom([5, 5], [6, 6], { origin, template, floor: 0 }).tiles, [1, 1]);
  assert.deepEqual(drawnRoom([0, 0], [20000, 300], { origin, template, floor: 0 }).tiles, [WALL.maxTiles, 3]);
}
// ---- any length and height (custom geometry editing plan, B4): the Build cuts it (made_split), the page draws it whole
{
  const w = { x0: 0, x1: 96 * 40, seed: 1, openings: [] };
  assert.ok(toolWall(w));
  assert.ok(!toolWall({ ...w, x1: 96 * 129 }));
  // its storeys as pieces of its look's, stacked (made_split.levels)
  assert.deepEqual([levelsOf(4, 2, true), levelsOf(3, 2, true), levelsOf(2, 3, true), levelsOf(5, 3, false), levelsOf(1, 2, true)],
                   [[2, 2], [2, 1], [1, 1], [3, 3], [1]]);
  // each stands on the top of the one under it: the Bar's two storeys are 400 tall, one 208
  const four = withStoreys(w, 4).wall, three = withStoreys(w, 3).wall;
  assert.equal(four.storeys, 4);
  assert.deepEqual([wallTop(four), wallTop(three)], [784, 592]);
  assert.equal(wallWords(four), '40 tiles long, four storeys (800 tall)');
  assert.ok(!('storeys' in withStoreys(four, 2).wall));
  // Lower and Taller go a storey at a time, one to twelve, in a look that can be made one storey
  assert.deepEqual(storeyCounts(w), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  assert.deepEqual([steppedStoreys(w, 1).wall.storeys, storeysOf(steppedStoreys(w, -1).wall)], [3, 1]);
  assert.equal(steppedStoreys({ ...w, storeys: 12 }, 1), null);
  assert.equal(steppedStoreys({ ...w, storeys: 1 }, -1), null);
  // the top handle goes as far as it is dragged: 400 up from two storeys is four
  assert.equal(raisedWall(w, 400).wall.storeys, 4);
  assert.equal(raisedWall(four, -190).wall.storeys, 3);
}
// ---- looks (M4 item 1): the page's list is wall_looks.json's, look for look
{
  const file = JSON.parse(readFileSync(new URL('../../bake/wall_looks.json', import.meta.url), 'utf8'));
  assert.deepEqual(WALL_LOOKS.map(l => [l.id, l.name, l.package, l.actor, l.mesh, l.lwrOnly, l.words]),
                   file.looks.map(l => [l.id, l.name, l.package, l.actor, l.donor, l.lwrOnly, l.words]));
  const bar = file.looks[0].recipe;
  assert.deepEqual([WALL.endInset, WALL.bottom, WALL.top, WALL.faceTop, WALL.storey], [bar.endInset, bar.bottom, bar.top, bar.face[1], bar.storey]);
}
// ---- floors and roofs (M5): a drag to a slab's pose and numbers, its edges, its holes; the page's looks are slab_looks.json's
{
  const file = JSON.parse(readFileSync(new URL('../../bake/slab_looks.json', import.meta.url), 'utf8'));
  assert.deepEqual(SLAB_LOOKS.map(l => [l.id, l.name, l.role, l.package, l.actor, l.mesh, l.lwrOnly, l.words, l.bottom, l.top]),
                   file.looks.map(l => [l.id, l.name, l.role, l.package, l.actor, l.donor, l.lwrOnly, l.words, l.recipe.bottom, l.recipe.top]));
  // a drag from one corner to the other: the tile edges nearest them, the piece at the lower corner, its mesh's x the world's
  let s = drawnSlab([-180, -200], [210, 130], { origin, template: { rotation: [0, 16384, 0] }, z: 16 });
  assert.deepEqual(s.location, [-192, -192, 16]);
  assert.deepEqual(s.rotation, [0, 0, 0]);
  assert.deepEqual(s.slab, { x0: 0, x1: 384, y0: 0, y1: 288, holes: [], seed: 1 });
  assert.deepEqual(s.tiles, [4, 3]);
  // backwards, a click, the largest; an upper floor names its look
  assert.deepEqual(drawnSlab([210, 130], [-180, -200], { origin, template, z: 0 }).location.slice(0, 2), [-192, -192]);
  assert.deepEqual(drawnSlab([5, 5], [6, 6], { origin, template, z: 0 }).tiles, [1, 1]);
  assert.deepEqual(drawnSlab([0, 0], [20000, -20000], { origin, template, z: 0 }).tiles, [SLAB.maxTiles, SLAB.maxTiles]);
  assert.deepEqual(drawnSlab([0, 0], [96 * 30, 96 * 20], { origin, template, z: 0 }).tiles, [30, 20]);
  assert.equal(drawnSlab([0, 0], [100, 100], { origin, template, z: 0, look: SLAB_LOOKS[1] }).slab.look, 'floor');
  assert.ok(toolSlab(s.slab));
  assert.ok(!toolSlab({ ...s.slab, x0: 96 }));
  assert.ok(!toolSlab({ ...s.slab, x1: 380 }));
  assert.ok(!toolSlab({ ...s.slab, look: 'marble' }));
  // holes: one tile in the free tile nearest the middle, then the next; slid and sized by whole tiles, kept inside
  let h = withHole(s.slab);
  assert.equal(h.index, 0);
  assert.deepEqual(h.slab.holes, [{ x0: 96, x1: 192, y0: 96, y1: 192 }]);
  h = withHole(h.slab);
  assert.deepEqual(h.slab.holes[1], { x0: 192, x1: 288, y0: 96, y1: 192 });
  let slab = withoutHole(h.slab, 0);
  assert.deepEqual(slab.holes, [{ x0: 192, x1: 288, y0: 96, y1: 192 }]);
  assert.deepEqual(movedHole(slab, 0, 'x', 500).holes[0], { x0: 288, x1: 384, y0: 96, y1: 192 });
  assert.deepEqual(movedHole(slab, 0, 'y', -130).holes[0], { x0: 192, x1: 288, y0: 0, y1: 96 });
  assert.deepEqual(movedHole(slab, 0, 'x1', 200).holes[0], { x0: 192, x1: 384, y0: 96, y1: 192 });
  assert.deepEqual(movedHole(slab, 0, 'x0', 300).holes[0], { x0: 192, x1: 288, y0: 96, y1: 192 });     // a tile wide at least
  assert.equal(holeWords(movedHole(slab, 0, 'y1', 96).holes[0]), 'Hole, 1 by 2 tiles');
  assert.equal(withHole({ x0: 0, x1: 96, y0: 0, y1: 96, holes: [{ x0: 0, x1: 96, y0: 0, y1: 96 }] }), null);
  // its edges: outwards grows it; the near edges move its corner and keep the holes where they are in the world
  let r = resizedSlab(slab, 'x1', 100);
  assert.deepEqual([r.slab.x1, r.shift, r.removed], [480, [0, 0], 0]);
  r = resizedSlab(slab, 'y0', 96);
  assert.deepEqual([r.slab.y1, r.shift, r.slab.holes[0]], [384, [0, -96], { x0: 192, x1: 288, y0: 192, y1: 288 }]);
  r = resizedSlab(slab, 'x1', -96 * 2);
  assert.deepEqual([r.slab.x1, r.removed, r.slab.holes], [192, 1, []]);
  assert.equal(resizedSlab(slab, 'x0', -5000).slab.x1, 96);
  assert.equal(resizedSlab(slab, 'y1', 20000).slab.y1, 96 * SLAB.maxTiles);
  assert.equal(slabWords(h.slab), '4 by 3 tiles, 2 holes');
  // a room's roof: its rectangle, on its walls' tops
  const room = drawnRoom([-180, -200], [210, 130], { origin, template, floor: 16 });
  const roof = roomRoof(room, { template, floor: 16 });
  assert.deepEqual([roof.location, roof.slab.x1, roof.slab.y1], [[-192, -192, 400], 384, 288]);
}
console.log('walls: ok');
