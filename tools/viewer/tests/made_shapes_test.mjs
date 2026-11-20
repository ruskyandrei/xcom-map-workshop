// Made pieces' meshes on the page (walls.js madeWallShape and madeSlabShape, ground.js madeGroundShape; moved out of
// app.js, review finding 22): the numbers' one spelling, the mesh record put into the scene's meshes once, keyed by the
// request the editor's server draws (generated.py), bounds, materials by the template's slots, blasts in the key, and
// numbers the server can't draw left to the template's own mesh. Run: node tools/viewer/tests/made_shapes_test.mjs
import assert from 'node:assert/strict';
import { WALL, WALL_LOOKS, blastQuery, madeBounds, madeSlabNumbers, madeSlabShape, madeWallNumbers, madeWallShape,
         slabBounds, spelledLook } from '../web/walls.js';
import { GROUND_LOOKS, groundBounds, madeGroundNumbers, madeGroundShape } from '../web/ground.js';

// a template whose mesh has sections in slots 0, 2 and 3 (slot 1 empty), each with its own material
const meshes = { tpl: { name: 'URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED', sections: [{ slot: 0, count: 1 }, { slot: 1, count: 0 },
  { slot: 2, count: 3 }, { slot: 3, count: 1 }] } };
const template = { mesh: 'tpl', materials: ['m0', 'm2', 'm3'] };

// ---- a wall: its numbers, its key and request, its bounds, its materials by slot
const wall = { x0: 0, x1: 288, openings: [{ x0: 96, x1: 192, z0: -16, z1: 176, kind: 'door' }], seed: 3, look: WALL_LOOKS[0].id };
const numbers = madeWallNumbers(wall);
assert.deepEqual(numbers, { x0: 0, x1: 288, openings: [{ x0: 96, x1: 192, z0: -16, z1: 176 }], seed: 3 });    // (the default look and storeys left out)
assert.deepEqual(madeWallNumbers(wall, ['free', 'line']).ends, ['free', 'line']);
assert.equal(madeWallNumbers(wall, ['free', 'free']).ends, undefined);
const shape = madeWallShape(template, wall, null, meshes);
assert.equal(shape.mesh, `made:fracwall:${JSON.stringify(numbers)}`);
assert.deepEqual(shape.materials, ['m0', 'm0', 'm2', 'm3', 'm0', 'm0']);       // six sections: the template's by slot, else its first
const record = meshes[shape.mesh];
assert.equal(record.url, `/generated/fracwall.glb?${new URLSearchParams({ wall: JSON.stringify(numbers) })}`);
assert.deepEqual(record.fallback, { mesh: 'tpl', materials: ['m0', 'm2', 'm3'] });
assert.equal(record.name, 'URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED, made from numbers');
assert.deepEqual(record.bounds, madeBounds(numbers));
// its solid stops 8 short of each free end: 8 to 280, the Bar's look from -16 to 384, 12 each side
assert.deepEqual(madeBounds(numbers).slice(0, 6), [144, 0, 184, 136, WALL.half, 200]);
// made once: the same numbers again find the record
record.marked = true;
assert.equal(madeWallShape(template, wall, null, meshes).mesh, shape.mesh);
assert.equal(meshes[shape.mesh].marked, true);
// blasts are in the key and the request
const broken = madeWallShape(template, wall, [{ at: [10, 0, 50], tiles: 1 }], meshes);
assert.equal(broken.mesh, `${shape.mesh}|${JSON.stringify([{ at: [10, 0, 50], tiles: 1 }])}`);
assert.match(meshes[broken.mesh].url, /&blasts=/);
assert.deepEqual(blastQuery([]), { key: '', query: {} });
// numbers the server can't draw: none
for (const bad of [{ ...wall, x1: 30 }, { ...wall, x1: WALL.maxTiles * 96 + 96 }, { ...wall, seed: 1.5 },
                   { ...wall, openings: [{ x0: 200, x1: 100, z0: 0, z1: 10 }] }, { ...wall, storeys: WALL.maxStoreys + 1 },
                   { ...wall, look: 'no-such-look' }, null])
  assert.deepEqual(madeWallShape(template, bad, null, meshes), {});
// a donor look in one spelling
assert.deepEqual(spelledLook({ mesh: 'A.B', measure: 2, name: 'x' }), { mesh: 'A.B', measure: 2 });
assert.equal(spelledLook('bar-inside'), 'bar-inside');

// ---- a slab
const slab = { x0: 0, x1: 192, y0: 0, y1: 288, holes: [{ x0: 96, x1: 192, y0: 96, y1: 192, extra: 1 }], seed: 2, look: 'roof' };
const sn = madeSlabNumbers(slab);
assert.deepEqual(sn, { x0: 0, x1: 192, y0: 0, y1: 288, holes: [{ x0: 96, x1: 192, y0: 96, y1: 192 }], seed: 2 });
const s = madeSlabShape(template, slab, null, meshes);
assert.equal(s.mesh, `made:fracslab:${JSON.stringify(sn)}`);
assert.deepEqual(s.materials, ['m0', 'm0']);
assert.deepEqual(meshes[s.mesh].bounds, slabBounds(sn));
assert.deepEqual(slabBounds(sn).slice(0, 6), [96, 144, 0, 96, 144, 2]);
assert.deepEqual(madeSlabShape(template, { ...slab, x1: 'wide' }, null, meshes), {});
assert.deepEqual(madeSlabShape(template, { ...slab, look: 'no-such-look' }, null, meshes), {});

// ---- a ground shape
const patch = { shape: 'patch', x0: 0, x1: 192, y0: 0, y1: 96, height: 40, look: GROUND_LOOKS[0].id };
const gn = madeGroundNumbers(patch);
assert.deepEqual(gn, { shape: 'patch', x0: 0, x1: 192, y0: 0, y1: 96 });        // (a patch's height and the default look left out)
const g = madeGroundShape(template, patch, meshes);
assert.equal(g.mesh, `made:ground:${JSON.stringify(gn)}`);
assert.deepEqual(g.materials, ['m0']);
assert.equal(meshes[g.mesh].url, `/generated/ground.glb?${new URLSearchParams({ ground: JSON.stringify(gn) })}`);
assert.deepEqual(meshes[g.mesh].bounds, groundBounds(gn));
assert.deepEqual(madeGroundShape(template, { ...patch, x1: 0 }, meshes), {});
console.log('made shapes: ok');
