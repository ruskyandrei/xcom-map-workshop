// The Ground tool's pure part (ground.js; custom geometry plan, stage M6): a drag to a shape's pose and numbers (a ramp
// rising toward the drag's end), its sides, its height, a turn on the same footprint, the slope's words, and the looks
// against tools/bake/ground_looks.json. Run: node tools/viewer/tests/ground_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GROUND, GROUND_LOOKS, drawnGround, groundBox, groundWords, raisedGround, resizedGround, slopeOf, slopeWords,
         toolGround, turnedGround } from '../web/ground.js';
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
  assert.deepEqual(groundBox(p.ground).slice(4), [-7, 1]);
  for (const [start, end, yaw] of [[[-180, -200], [210, -150], 0], [[210, -150], [-180, -200], 32768], [[0, 0], [10, 300], 16384], [[10, 300], [0, 0], 49152]]) {
    const r = drawnGround(start, end, { origin, template, z: 0, shape: 'ramp' });
    assert.equal(r.rotation[1], yaw);
    assert.equal(r.ground.height, GROUND.ramp);
    const plain = drawnGround(start, end, { origin, template, z: 0, shape: 'block' });
    assert.deepEqual(footprint(r), footprint(plain));          // the same tiles, whichever way it rises
  }
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
console.log('ground: ok');
