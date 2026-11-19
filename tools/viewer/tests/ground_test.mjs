// The Ground tool's pure part (ground.js; custom geometry plan, stage M6): a drag to a shape's pose and numbers (a ramp
// rising toward the drag's end), its sides, its height, a turn on the same footprint, the slope's words, and the looks
// against tools/bake/ground_looks.json. Run: node tools/viewer/tests/ground_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GROUND, GROUND_LOOKS, ROCK_SEEDS, anotherRock, drawnGround, groundBox, groundWords, raisedGround, resizedGround, slopeOf,
         slopeWords, toolGround, turnedGround, ROCK, POINTS_VERSION, pointsValid, movedPoint, versionedGround, resetRock } from '../web/ground.js';
import { wallDirection } from '../web/walls.js';

const origin = [-2784, -1920];
const template = { rotation: [0, 0, 0] };
// the world footprint a pose covers: [x0, x1, y0, y1]
function footprint(pose) {
  const [dx, dy] = wallDirection(pose.rotation[1]), px = -dy, py = dx, g = pose.ground;
  const pts = [[0, 0], [g.x1, 0], [0, g.y1], [g.x1, g.y1]].map(([x, y]) => [pose.location[0] + dx * x + px * y, pose.location[1] + dy * x + py * y]);
  return [Math.min(...pts.map(p => p[0])), Math.max(...pts.map(p => p[0])), Math.min(...pts.map(p => p[1])), Math.max(...pts.map(p => p[1]))];
}

// ---- looks: the page's list is ground_looks.json's
{
  const file = JSON.parse(readFileSync(new URL('../../bake/ground_looks.json', import.meta.url), 'utf8'));
  assert.deepEqual(GROUND_LOOKS.map(l => [l.id, l.name, l.package, l.actor, l.mesh, l.lwrOnly, l.words, l.repeat, l.thickness]),
                   file.looks.map(l => [l.id, l.name, l.package, l.actor, l.donor, l.lwrOnly, l.words, l.recipe.repeat, l.recipe.thickness]));
}
// ---- drawing: a block keeps the world's axes; a ramp rises toward the drag's end, its footprint the dragged one
{
  const b = drawnGround([-180, -200], [210, 130], { origin, template, z: 16, shape: 'block' });
  assert.deepEqual([b.location, b.rotation, b.ground], [[-192, -192, 16], [0, 0, 0], { shape: 'block', x0: 0, x1: 384, y0: 0, y1: 288, height: GROUND.block }]);
  assert.ok(toolGround(b.ground));
  const p = drawnGround([0, 0], [100, 100], { origin, template, z: 0, shape: 'patch' });
  assert.equal(p.ground.height, undefined);
  assert.deepEqual(groundBox(p.ground).slice(4), [-5, 3]);     // (F-137: a patch's top 3 over the ground)
  for (const [start, end, yaw] of [[[-180, -200], [210, -150], 0], [[210, -150], [-180, -200], 32768], [[0, 0], [10, 300], 16384], [[10, 300], [0, 0], 49152]]) {
    const r = drawnGround(start, end, { origin, template, z: 0, shape: 'ramp' });
    assert.equal(r.rotation[1], yaw);
    assert.equal(r.ground.height, GROUND.ramp);
    const plain = drawnGround(start, end, { origin, template, z: 0, shape: 'block' });
    assert.deepEqual(footprint(r), footprint(plain));          // the same tiles, whichever way it rises
  }
}
// ---- a piece stands level and square to the world whatever its donor's pitch, roll and yaw (the mesh is ours)
{
  const tipped = { rotation: [-357, -18467, -545] };
  const b = drawnGround([-180, -200], [210, 130], { origin, template: tipped, z: 16, shape: 'block' });
  assert.deepEqual(b.rotation, [0, 0, 0]);
  const r = drawnGround([210, -150], [-180, -200], { origin, template: tipped, z: 0, shape: 'ramp' });
  assert.deepEqual(r.rotation, [0, 32768, 0]);
}
// ---- a rock: the drawing's seed, its height, another rock
{
  const k = drawnGround([-180, -200], [210, 130], { origin, template, z: 16, shape: 'rock', seed: 41 });
  assert.deepEqual(k.ground, { shape: 'rock', x0: 0, x1: 384, y0: 0, y1: 288, height: GROUND.rock, seed: 41 });
  assert.ok(toolGround(k.ground));
  assert.deepEqual(groundBox(k.ground), [0, 384, 0, 288, 0, GROUND.rock]);
  assert.equal(anotherRock(k.ground).seed, 42);
  assert.equal(anotherRock({ ...k.ground, seed: ROCK_SEEDS - 1 }).seed, 0);
  assert.ok(!toolGround({ ...k.ground, seed: 1.5 }));
  assert.ok(!toolGround({ ...k.ground, seed: undefined }));
  assert.equal(groundWords(k.ground), 'Rock, 4 by 3 tiles, 96 high');
  assert.equal(slopeWords(k.ground), '');
}
// ---- sides, height, turn
{
  const r = drawnGround([-180, -200], [210, -150], { origin, template, z: 16, shape: 'ramp' });
  assert.deepEqual(resizedGround(r.ground, 'x1', 100).ground.x1, 480);
  assert.deepEqual(resizedGround(r.ground, 'y0', 96), { ground: { ...r.ground, y1: 192 }, shift: [0, -96] });
  assert.equal(resizedGround(r.ground, 'x0', -5000).ground.x1, 96);
  assert.equal(raisedGround(r.ground, 13).height, 112);
  assert.equal(raisedGround(r.ground, -500).height, GROUND.minHeight);
  assert.equal(raisedGround(r.ground, 5000).height, GROUND.maxHeight);
  const t = turnedGround(r.ground, r.location, r.rotation);
  assert.deepEqual(footprint(t), footprint(r));               // the same footprint, rising the next way round
  assert.equal(t.rotation[1], 16384);
  assert.deepEqual([t.ground.x1, t.ground.y1], [r.ground.y1, r.ground.x1]);
}
// ---- the slope in words (F-81)
assert.equal(slopeWords({ shape: 'block', x0: 0, x1: 96, y0: 0, y1: 96, height: 64 }), '');
assert.match(slopeWords({ shape: 'ramp', x0: 0, x1: 960, y0: 0, y1: 96, height: 96 }), /gives cover/);
assert.match(slopeWords({ shape: 'ramp', x0: 0, x1: 384, y0: 0, y1: 96, height: 96 }), /no cover/);
assert.match(slopeWords({ shape: 'ramp', x0: 0, x1: 96, y0: 0, y1: 96, height: 192 }), /no floor/);
assert.equal(Math.round(slopeOf({ shape: 'ramp', x0: 0, x1: 96, y0: 0, y1: 96, height: 96 })), 45);
assert.equal(groundWords({ shape: 'ramp', x0: 0, x1: 384, y0: 0, y1: 96, height: 96 }), 'Ramp, 4 tiles long and 1 tile wide, rising 96');
// ---- a rock's moved points (look picker and rock points plan, R1)
{
  // 24 points in a 2 by 2 footprint: a ground ring of 7, the rest up to its height
  const ring = Array.from({ length: ROCK.points }, (_, i) => {
    const t = 2 * Math.PI * i / (i < ROCK.ring ? ROCK.ring : ROCK.points - ROCK.ring);
    const r = i < ROCK.ring ? 80 : 60, z = i < ROCK.ring ? 0 : 40 + (i % 5) * 20;
    return [96 + r * Math.cos(t), 96 + r * Math.sin(t), z];
  });
  const rock = { shape: 'rock', x0: 0, x1: 192, y0: 0, y1: 192, height: 120, seed: 4, points: ring };
  assert.ok(pointsValid(rock) && toolGround(rock));
  for (const bad of [ring.slice(1), [[300, 10, 0], ...ring.slice(1)], [[100, 100, 10], ...ring.slice(1)],
                     [...ring.slice(0, 9), [100, 100, 130], ...ring.slice(10)], [...ring.slice(0, 9), [100, 100, -4], ...ring.slice(10)]])
    assert.ok(!toolGround({ ...rock, points: bad }), JSON.stringify(bad[0]));
  assert.ok(!toolGround({ ...rock, shape: 'block', height: 64 }));
  // a point moved inside: the footprint as it was, its height the highest point's
  let m = movedPoint(rock, ring, 10, [100, 90, 150]);
  assert.deepEqual([m.ground.x1, m.ground.y1, m.ground.height, m.shift], [192, 192, 150, [0, 0]]);
  assert.deepEqual(m.ground.points[10], [100, 90, 150]);
  // a point of the ground ring stays on it; none goes below the ground
  assert.equal(movedPoint(rock, ring, 2, [100, 90, 50]).ground.points[2][2], 0);
  assert.equal(movedPoint(rock, ring, 12, [100, 90, -30]).ground.points[12][2], 0);
  // past +x: the footprint grows by whole tiles, its corner stays
  m = movedPoint(rock, ring, 12, [250, 96, 60]);
  assert.deepEqual([m.ground.x1, m.ground.y1, m.shift], [288, 192, [0, 0]]);
  assert.ok(toolGround(m.ground));
  // past -y by a tile and a bit: two tiles added that way, its corner back by them, every point shifted the same
  // (nothing else moves in the world)
  m = movedPoint(rock, ring, 12, [96, -100, 60]);
  assert.deepEqual([m.ground.y1, m.shift], [384, [0, -192]]);
  assert.deepEqual(m.ground.points[0], [ring[0][0], ring[0][1] + 192, 0].map(v => Math.round(v * 1e4) / 1e4));
  assert.deepEqual(m.ground.points[12], [96, 92, 60]);
  assert.ok(toolGround(m.ground));
  // no more than the tool's tiles: a point past them is kept at the edge
  m = movedPoint({ ...rock, x1: 96 * GROUND.maxTiles }, ring, 12, [96 * GROUND.maxTiles + 500, 96, 60]);
  assert.deepEqual([m.ground.x1, m.ground.points[12][0]], [96 * GROUND.maxTiles, 96 * GROUND.maxTiles]);
  // the white handles stretch the points: a side a tile out (either side), the top up
  const wider = resizedGround(rock, 'x1', 96).ground, back = resizedGround(rock, 'x0', 96);
  assert.equal(wider.x1, 288);
  assert.ok(Math.abs(wider.points[5][0] - ring[5][0] * 1.5) < 1e-3 && wider.points[5][1] === ring[5][1]);
  assert.deepEqual(back.shift, [-96, 0]);
  // (from x0: the far side stays where it was in the world, the corner 96 back)
  assert.ok(Math.abs(back.ground.points[5][0] - 96 - ring[5][0] - (back.ground.points[5][0] - ring[5][0] - 96)) < 1e-9);
  assert.ok(Math.abs((192 - ring[5][0]) * 1.5 - (288 - back.ground.points[5][0])) < 1e-3);
  assert.ok(pointsValid(wider) && pointsValid(back.ground));
  const taller = raisedGround(rock, 40);
  assert.equal(taller.height, 160);
  assert.ok(Math.abs(taller.points[12][2] - ring[12][2] * 160 / 120) < 1e-3 && taller.points[0][2] === 0);
  // turned a quarter: (x, y) to (y, w - x); Another rock and Reset points clear them
  const turned = turnedGround({ ...rock, x1: 288 }, [0, 0, 0], [0, 0, 0]).ground;
  assert.deepEqual(turned.points[0].slice(0, 2), [ring[0][1], Math.round((288 - ring[0][0]) * 1e4) / 1e4]);
  assert.ok(!('points' in anotherRock(rock)) && !('points' in resetRock(rock)) && anotherRock(rock).seed === 5);
  // its request: POINTS_VERSION whatever its look while it has points, its look written out; back once cleared
  const req = (version, ground) => ({ kind: 'ground', version, ground });
  const { points: _, ...seeded } = rock;
  assert.deepEqual(versionedGround(req(1, rock)), req(POINTS_VERSION, { ...rock, look: GROUND_LOOKS[0].id }));
  assert.deepEqual(versionedGround(req(3, rock)), req(POINTS_VERSION, rock));
  const donor = { ...rock, look: { mesh: 'A.B', material: 'A.M', measure: 1 } };
  assert.deepEqual(versionedGround(req(2, donor)), req(POINTS_VERSION, donor));
  assert.deepEqual(versionedGround(req(POINTS_VERSION, seeded)), req(3, seeded));
  assert.deepEqual(versionedGround(req(POINTS_VERSION, { ...seeded, look: 'rock' })).version, 1);
  assert.deepEqual(versionedGround(req(POINTS_VERSION, { ...seeded, look: donor.look })).version, 2);
  assert.deepEqual(versionedGround(req(2, { ...seeded, look: donor.look })), req(2, { ...seeded, look: donor.look }));
  const wall = { kind: 'fracWall', version: 3, wall: {} };
  assert.equal(versionedGround(wall), wall);
}
console.log('ground: ok');
