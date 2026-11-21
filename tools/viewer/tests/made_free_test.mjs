// Made pieces in the free form (made_free.js; the custom geometry improvements plan, stage 2). Run: node
// tools/viewer/tests/made_free_test.mjs
import assert from 'node:assert/strict';
import { FREE, FREE_VERSION, freeRequest, freeSizeWords, isFree, pivotedToCorner, resizedFace, toolFree } from '../web/made_free.js';

// ---- an older request in the free form: its extents as its look made them
const wall = { kind: 'fracWall', version: 1, wall: { x0: 0, x1: 384, openings: [{ x0: 96, x1: 192, z0: -16, z1: 160 }], seed: 3 } };
const free = freeRequest(wall);
assert.equal(free.version, FREE_VERSION.fracWall);
assert.ok(isFree(free) && !isFree(wall));
assert.deepEqual(free.wall, { x0: 0, x1: 384, openings: [{ x0: 96, x1: 192, z0: -16, z1: 160 }], seed: 3, free: 1,
                              y0: -8, y1: 8, z0: -16, z1: 384, tall: 'repeat' });
assert.equal(freeRequest(free), free);                                   // (a free one as it is)
// one storey: its top 192; a plain wall keeps saying so
assert.equal(freeRequest({ kind: 'fracWall', version: 1, wall: { x0: 0, x1: 96, seed: 1, storeys: 1 } }).wall.z1, 192);
assert.equal(freeRequest({ kind: 'fracWall', version: 4, wall: { x0: 0, x1: 96, seed: 1 } }).wall.plain, true);
assert.ok(!('storeys' in freeRequest({ kind: 'fracWall', version: 1, wall: { x0: 0, x1: 96, seed: 1, storeys: 1 } }).wall));
// a slab: its look's plate; ground: its box
const slab = freeRequest({ kind: 'fracSlab', version: 1, slab: { x0: 0, x1: 192, y0: 0, y1: 96, holes: [], seed: 1 } });
assert.deepEqual([slab.version, slab.slab.z0, slab.slab.z1], [4, -2, 2]);
const block = freeRequest({ kind: 'ground', version: 1, ground: { shape: 'block', x0: 0, x1: 96, y0: 0, y1: 96, height: 64 } });
assert.deepEqual([block.version, block.ground.z0, block.ground.z1, 'height' in block.ground], [5, 0, 64, false]);
const patch = freeRequest({ kind: 'ground', version: 3, ground: { shape: 'patch', x0: 0, x1: 96, y0: 0, y1: 96 } });
assert.deepEqual([patch.ground.z0, patch.ground.z1, patch.ground.plain], [-5, 3, true]);

// ---- a face dragged: only its number changes (D1), to fractions of a unit
const w = free.wall;
let r = resizedFace('fracWall', w, 'x1', -240.5);
assert.equal(r.numbers.x1, 143.5);
assert.deepEqual(r.numbers.openings, [{ x0: 96, x1: 143.5, z0: -16, z1: 160 }]);      // clipped to the new end
assert.equal(r.clipped, 1);
r = resizedFace('fracWall', w, 'x0', 200);                                           // the near end: the gap goes
assert.deepEqual([r.numbers.x0, r.numbers.openings.length, r.removed], [200, 0, 1]);
r = resizedFace('fracWall', w, 'x0', -50.25);                                        // out past the origin
assert.deepEqual([r.numbers.x0, r.numbers.x1, r.numbers.openings[0].x0], [-50.25, 384, 96]);
r = resizedFace('fracWall', w, 'z1', -166.75);                                       // the top down to 217.25
assert.equal(r.numbers.z1, 217.25);
r = resizedFace('fracWall', w, 'y1', 4);                                             // a face out: thicker
assert.deepEqual([r.numbers.y0, r.numbers.y1], [-8, 12]);
r = resizedFace('fracWall', w, 'y0', 1000);                                          // never past the other face
assert.equal(r.numbers.y0, 8 - FREE.least);
// a gap cut to the bottom stays so when the bottom moves
r = resizedFace('fracWall', w, 'z0', -20);
assert.deepEqual([r.numbers.z0, r.numbers.openings[0].z0], [-36, -36]);
// a gap cut through the top stays so
const through = { ...w, openings: [{ x0: 96, x1: 192, z0: 72, z1: 384 }] };
assert.equal(resizedFace('fracWall', through, 'z1', -100).numbers.openings[0].z1, 284);
assert.equal(resizedFace('fracWall', through, 'z1', 50).numbers.openings[0].z1, 434);
// a slab's holes clipped on both axes; a hole the new edge passes goes
const s = { ...slab.slab, holes: [{ x0: 96, x1: 192, y0: 0, y1: 96 }] };
r = resizedFace('fracSlab', s, 'x1', -40);
assert.deepEqual(r.numbers.holes, [{ x0: 96, x1: 152, y0: 0, y1: 96 }]);
assert.equal(resizedFace('fracSlab', s, 'x1', -100).removed, 1);
r = resizedFace('fracSlab', s, 'z0', -10);                                           // thicker, the top stays
assert.deepEqual([r.numbers.z0, r.numbers.z1], [-12, 2]);
// a rock's moved points stay inside its footprint
const rock = { shape: 'rock', free: 1, x0: 0, x1: 192, y0: 0, y1: 192, z0: 0, z1: 96, seed: 5, points: [[180, 10, 0], [20, 20, 50]] };
assert.deepEqual(resizedFace('ground', rock, 'x1', -50).numbers.points, [[142, 10, 0], [20, 20, 50]]);

// ---- Pivot to corner: renumbered from the low corner, everything in the frame shifted with it
const off = { ...w, x0: -50.25, openings: [{ x0: 96, x1: 192, z0: -16, z1: 160 }],
              mapping: { surfaces: { faces: { mode: 'size', u: 64, v: 64 }, top: { mode: 'fit', u: 1, v: 1 } } } };
const p = pivotedToCorner('fracWall', off, [{ at: [10, 0, 100], radius: 96 }]);
assert.deepEqual(p.shift, [-50.25, 0, 0]);
assert.deepEqual([p.numbers.x0, p.numbers.x1, p.numbers.y0, p.numbers.y1], [0, 434.25, -8, 8]);
assert.deepEqual(p.numbers.openings[0], { x0: 146.25, x1: 242.25, z0: -16, z1: 160 });
assert.deepEqual(p.blasts, [{ at: [60.25, 0, 100], radius: 96 }]);
assert.equal(p.numbers.mapping.surfaces.faces.offsetU, -50.25 / 64);
assert.equal(p.numbers.mapping.surfaces.top, off.mapping.surfaces.top);              // (fit follows the size)
const ps = pivotedToCorner('fracSlab', { ...s, x0: 10, y0: -20, holes: [{ x0: 96, x1: 150, y0: 0, y1: 50 }] });
assert.deepEqual([ps.shift, ps.numbers.holes[0]], [[10, -20, 0], { x0: 86, x1: 140, y0: 20, y1: 70 }]);

// ---- what the editor makes
assert.ok(toolFree('fracWall', w));
assert.ok(!toolFree('fracWall', { ...w, x1: w.x0 + 0.5 }));
assert.ok(!toolFree('fracWall', { ...w, openings: [{ x0: -10, x1: 50, z0: 0, z1: 100 }] }));
assert.ok(toolFree('fracSlab', s) && !toolFree('fracSlab', { ...s, holes: [{ x0: 0, x1: 500, y0: 0, y1: 10 }] }));
assert.ok(!toolFree('ground', { ...rock, z1: Infinity }));
assert.equal(freeSizeWords({ ...w, x1: 143.5, z1: 201.25 }), '143.5 × 16 × 217.25');

console.log('made free tests passed');
