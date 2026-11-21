// A made piece's texture mapping on the page (made_mapping.js; the custom geometry improvements plan, stage 4): the
// rule on test_uv_mapping.py's numbers (uv_mapping.uv is the twin), its inverse, the handles' drags in the snap steps,
// the surfaces, the mapping read and written, the words, and where a world-aligned surface is counted from. Run: node
// tools/viewer/tests/made_mapping_test.mjs
import assert from 'node:assert/strict';
import { DEFAULT_REPEAT, framePoint, lookRepeat, lookSurface, MAPPING_ROLES, mappingOrigin, mappingWords, materialTiling, nextSurface,
         patternCorner, patternPoint, patternSize, sizable, sizedMapping, slidMapping, surfaceAt, surfaceExtent, surfaceMapping,
         surfaceOfNormal, surfacePlane, surfaceSlots, surfaceSteps, surfaceWords, reframed, textureNotes, tidySurface, turnedMapping,
         uv, withMode, withSurface, withValue } from '../web/made_mapping.js';
import { forgetLooks, loadLooks } from '../web/looks.js';

const near = (got, want, what, eps = 1e-9) => {
  assert.equal(got.length, want.length, what);
  got.forEach((v, k) => assert.ok(Math.abs(v - want[k]) <= eps, `${what}: ${JSON.stringify(got)} against ${JSON.stringify(want)}`));
};

// ---- the rule, on test_uv_mapping.py's numbers (a wall's face, 384 along and 384 up from -16)
const EXTENT = [0, 384, -16, 368];
near(uv({ mode: 'size', u: 96, v: 96 }, 96, 48, EXTENT), [1, 0.5], 'size keeps the repeat');
near(uv({ mode: 'size', u: 96, v: 96 }, 96, 48, [0, 768, -16, 368]), [1, 0.5], 'a longer wall: the same coordinates');
near(uv({ mode: 'count', u: 3, v: 1.5 }, 384, 368, EXTENT), [3, 1.5], 'count');
near(uv({ mode: 'count', u: 3, v: 1.5 }, 768, 368, [0, 768, -16, 368]), [3, 1.5], 'three stay three');
near(uv({ mode: 'fit', u: 7, v: 7 }, 192, 176, EXTENT), [0.5, 0.5], 'fit reads u and v as 1');
near(uv({ mode: 'size', modeV: 'fit', u: 64, v: 1 }, 128, 368, EXTENT), [2, 1], 'tile along, fit up');
// (100, 0) -> turned 90 (0, 100) -> scaled (0, 2) -> flipped (-0, 2) -> slid (0.25, 1.5)
near(uv({ mode: 'size', u: 100, v: 50, flipU: true, turn: 90, offsetU: 0.25, offsetV: -0.5 }, 100, 0, EXTENT), [0.25, 1.5], 'turn, scale, flip, offset');
near(uv({ mode: 'size', u: 10, v: 10, turn: 30 }, 10, 0, EXTENT), [Math.cos(Math.PI / 6), Math.sin(Math.PI / 6)], 'thirty');
// a 96 by 48 repeat turned 30 degrees stays a rectangle of its size
{
  const s = { mode: 'size', u: 96, v: 48, turn: 30 }, c = Math.cos(Math.PI / 6), s3 = Math.sin(Math.PI / 6), o = uv(s, 0, 0, EXTENT);
  near(uv(s, 96 * c, -96 * s3, EXTENT).map((v, k) => v - o[k]), [1, 0], 'a turned repeat along u');
  near(uv(s, 48 * s3, 48 * c, EXTENT).map((v, k) => v - o[k]), [0, 1], 'a turned repeat along v');
}
// a turned count or fit is across the turned axes: a quarter turn's corners whole counts; 30 degrees fitted 0 to 1
{
  const got = [0, 384].flatMap(a => [-16, 368].map(b => uv({ mode: 'count', u: 3, v: 2, turn: 90 }, a, b, EXTENT)));
  assert.deepEqual([...new Set(got.map(q => Math.round(q[0] * 1e9) / 1e9 + 0))].sort(), [0, 3]);
  assert.deepEqual([...new Set(got.map(q => Math.round(q[1] * 1e9) / 1e9 + 0))].sort(), [0, 2]);
  const fit = [0, 384].flatMap(a => [-16, 368].map(b => uv({ mode: 'fit', u: 1, v: 1, turn: 30 }, a, b, EXTENT)));
  near([Math.min(...fit.map(q => q[0])), Math.max(...fit.map(q => q[0])), Math.min(...fit.map(q => q[1])), Math.max(...fit.map(q => q[1]))],
       [0, 1, 0, 1], 'a turned fit');
}
const world = { mode: 'size', u: 96, v: 96, world: true };
near(uv(world, 384, 0, EXTENT, [0, 0]), uv(world, 0, 0, EXTENT, [384, 0]), 'world-aligned pieces side by side line up');
assert.notEqual(uv({ ...world, world: false }, 0, 0, EXTENT, [384, 0])[0], uv(world, 384, 0, EXTENT, [0, 0])[0] + 1);

// ---- its inverse: every mode, turned, flipped, slid, aligned to the world
for (const s of [{ mode: 'size', u: 64, v: 32, turn: 30, flipU: true, offsetU: 0.3, offsetV: -1.2 },
                 { mode: 'count', u: 3, v: 2, turn: -75, flipV: true, offsetU: 0.5 },
                 { mode: 'fit', u: 1, v: 1, turn: 10 }, { mode: 'size', modeV: 'count', u: 50, v: 4, turn: 200 },
                 { mode: 'size', u: 96, v: 96, world: true, turn: 45, offsetV: 0.25 }]) {
  for (const p of [[0, 0], [100.5, 37.25], [-20, 300]]) {
    const back = patternPoint(s, EXTENT, [1000.5, -40], uv(s, p[0], p[1], EXTENT, [1000.5, -40]));
    near(back, p, `inverse of ${JSON.stringify(s)}`, 1e-7);
  }
}
assert.equal(patternPoint({ mode: 'fit', u: 1, v: 1 }, [5, 5, 0, 10], [0, 0], [0.5, 0.5]), null);     // (no extent along a)
// the corner nearest a point: whole coordinates, and the point of the surface they are at
const turned = { mode: 'size', u: 64, v: 64, turn: 30, offsetU: 0.4 };
const corner = patternCorner(turned, EXTENT, [0, 0], [192, 176]);
assert.ok(corner.every(Number.isInteger), corner);
const at = patternPoint(turned, EXTENT, [0, 0], corner);
assert.ok(Math.hypot(at[0] - 192, at[1] - 176) < 64, at);

// ---- the drags
// the blue dot: the pattern moves with the pointer; the corner under the pointer at the start is under it at the end
const size = { mode: 'size', u: 64, v: 48, turn: 30, flipV: true, offsetU: 0.1 };
const slid = slidMapping(size, EXTENT, [0, 0], [10.5, -7]);
near(patternPoint(slid, EXTENT, [0, 0], corner), patternPoint(size, EXTENT, [0, 0], corner).map((v, k) => v + [10.5, -7][k]), 'slid', 1e-6);
// in steps (24 along, 64 up: tile snap's on a face): 10.5 is no step along, -40 a level down
const stepped = slidMapping({ mode: 'size', u: 64, v: 64 }, EXTENT, [0, 0], [10.5, -40], [96, 64]);
near([stepped.offsetU ?? 0, stepped.offsetV ?? 0], [0, 1], 'a slide a level down');
// the ring: the turn in steps, the corner staying where it is; the pattern turning as the pointer does on the surface,
// mirrored or not (the rule turns the point, so the turn is the pointer's the other way)
const ring = turnedMapping(size, EXTENT, [0, 0], corner, 20);
assert.equal(ring.turn, 10);
near(patternPoint(ring, EXTENT, [0, 0], corner), patternPoint(size, EXTENT, [0, 0], corner), 'the corner stays as it turns', 1e-6);
const way = s => { const p = patternPoint(s, EXTENT, [0, 0], corner), q = patternPoint(s, EXTENT, [0, 0], [corner[0] + 1, corner[1]]);
                   return Math.atan2(q[1] - p[1], q[0] - p[0]) * 180 / Math.PI; };
for (const s of [size, { ...size, flipV: false }, { ...size, flipU: true }, { ...size, flipU: true, flipV: false }]) {
  const turnedBy = way(turnedMapping(s, EXTENT, [0, 0], corner, 25)) - way(s);
  assert.ok(Math.abs(((turnedBy % 360) + 360) % 360 - 25) < 1e-6, `${JSON.stringify(s)}: the pattern turned ${turnedBy}`);
}
assert.equal(turnedMapping({ mode: 'size', u: 64, v: 64 }, EXTENT, [0, 0], [0, 0], 20).turn, -20);
assert.equal(turnedMapping({ mode: 'size', u: 64, v: 64, turn: 7.5 }, EXTENT, [0, 0], [0, 0], -22, 15).turn, 22.5);
assert.equal(turnedMapping({ mode: 'size', u: 64, v: 64, turn: 170 }, EXTENT, [0, 0], [0, 0], -30).turn, -160);   // (kept in -180..180)
// the white dot: u and v in proportion, the corner staying; a count the other way; in steps; a repeat of 1 at least
const big = sizedMapping({ mode: 'size', u: 64, v: 32, offsetU: 0.25 }, EXTENT, [0, 0], [1, 0], 1, 64, 96);
assert.deepEqual([big.u, big.v], [96, 48]);
near(patternPoint(big, EXTENT, [0, 0], [1, 0]), patternPoint({ mode: 'size', u: 64, v: 32, offsetU: 0.25 }, EXTENT, [0, 0], [1, 0]), 'the corner stays as it sizes', 1e-6);
assert.deepEqual([sizedMapping({ mode: 'size', u: 192, v: 192 }, EXTENT, [0, 0], [0, 0], 1, 192, 203, 24).u], [192]);   // (11: no step of 24)
assert.deepEqual([sizedMapping({ mode: 'size', u: 192, v: 192 }, EXTENT, [0, 0], [0, 0], 1, 192, 210, 24).u], [216]);
assert.deepEqual([sizedMapping({ mode: 'size', u: 192, v: 192 }, EXTENT, [0, 0], [0, 0], 2, 384, 0).u], [1]);          // (two repeats on the dot)
assert.equal(sizedMapping({ mode: 'size', u: 100, v: 100 }, EXTENT, [0, 0], [0, 0], 1, 100, -500, 96).u, 4);          // (the least of 100 less steps of 96)
const counted = sizedMapping({ mode: 'count', u: 3, v: 2 }, EXTENT, [0, 0], [0, 0], 1, 128, 256);
assert.deepEqual([counted.u, counted.v], [1.5, 1]);
// a turned repeat sized: still a rectangle, u and v scaled alike
const turnedBig = sizedMapping({ mode: 'size', u: 96, v: 48, turn: 30 }, EXTENT, [0, 0], [0, 0], 1, 96, 192);
assert.deepEqual([turnedBig.u, turnedBig.v, turnedBig.turn], [192, 96, 30]);
// the frame moved (Pivot to corner): a size axis's offset keeps the pattern in place, turned, flipped; a count's and
// a world-aligned surface's stay
for (const s of [{ mode: 'size', u: 64, v: 32, turn: 30, flipU: true, offsetV: 0.5 }, { mode: 'size', modeV: 'count', u: 50, v: 3, turn: 0 }]) {
  const moved = reframed(s, [100, -40]), shifted = [EXTENT[0] - 100, EXTENT[1] - 100, EXTENT[2] + 40, EXTENT[3] + 40];
  for (const p of [[0, 0], [150, 77.5]]) near(uv(moved, p[0] - 100, p[1] + 40, shifted), uv(s, p[0], p[1], EXTENT), `reframed ${JSON.stringify(s)}`, 1e-7);
}
assert.equal(reframed({ mode: 'size', u: 64, v: 64, world: true }, [100, 0]).offsetU, undefined);
assert.equal(reframed({ mode: 'count', u: 2, v: 2 }, [100, 0]).offsetU, undefined);
assert.ok(sizable({ mode: 'size', u: 1, v: 1 }) && !sizable({ mode: 'fit', u: 1, v: 1 }) && sizable({ mode: 'fit', modeV: 'size', u: 1, v: 1 }));

// ---- the surfaces
assert.deepEqual(MAPPING_ROLES, { fracWall: ['faces'], fracSlab: ['top', 'underside'], ground: ['top', 'sides'] });
assert.deepEqual(surfaceOfNormal('fracWall', [0, -1, 0]), { role: 'faces', side: 'y0' });
assert.deepEqual(surfaceOfNormal('fracWall', [0.1, 0.9, 0.2]), { role: 'faces', side: 'y1' });
assert.equal(surfaceOfNormal('fracWall', [0, 0, 1]), null);               // (its top keeps its look's: D8)
assert.deepEqual([surfaceOfNormal('fracSlab', [0, 0, 1]), surfaceOfNormal('fracSlab', [0, 0, -1]), surfaceOfNormal('fracSlab', [1, 0, 0])],
                 [{ role: 'top' }, { role: 'underside' }, null]);
assert.deepEqual([surfaceOfNormal('ground', [0, 0.3, 0.95]), surfaceOfNormal('ground', [1, 0, 0]), surfaceOfNormal('ground', [0, 0, -1])],
                 [{ role: 'top' }, { role: 'sides' }, null]);
assert.deepEqual(nextSurface('fracWall', { role: 'faces', side: 'y1' }), { role: 'faces', side: 'y0' });
assert.deepEqual(nextSurface('fracSlab', { role: 'underside' }), { role: 'top' });
assert.deepEqual(nextSurface('ground', { role: 'top' }, -1), { role: 'sides' });
assert.deepEqual(nextSurface('ground', null), { role: 'top' });
const wallN = { free: 1, x0: -20, x1: 300, y0: -8, y1: 10, z0: -16, z1: 400 };
assert.deepEqual(surfacePlane('fracWall', wallN, { role: 'faces', side: 'y0' }).origin, [0, -8, 0]);
assert.deepEqual(surfaceExtent('fracWall', wallN, 'faces'), [-20, 300, -16, 400]);
const ramp = { free: 1, shape: 'ramp', x0: 0, x1: 96, y0: 0, y1: 96, z0: 0, z1: 48 };
const plane = surfacePlane('ground', ramp, { role: 'top' });
assert.deepEqual([plane.origin, plane.a], [[0, 0, 0], [1, 0, 0.5]]);
assert.equal(surfacePlane('ground', ramp, { role: 'sides' }), null);
// a point of the surface and back: on the ramp's slope, on a wall's back face
assert.deepEqual(framePoint(plane, [48, 10]), [48, 10, 24]);
assert.deepEqual(surfaceAt('ground', 'top', framePoint(plane, [48, 10])), [48, 10]);
const back = surfacePlane('fracWall', wallN, { role: 'faces', side: 'y0' });
assert.deepEqual(surfaceAt('fracWall', 'faces', framePoint(back, [100, 50])), [100, 50]);
assert.deepEqual(surfaceExtent('fracSlab', { x0: 1, x1: 2, y0: 3, y1: 4, z0: 5, z1: 6 }, 'top'), [1, 2, 3, 4]);
assert.deepEqual([surfaceSteps('fracWall', 'faces', 'tile'), surfaceSteps('fracSlab', 'top', 'fine'), surfaceSteps('ground', 'top', 'off')],
                 [[96, 64], [24, 24], [0, 0]]);
assert.match(surfaceWords('fracWall', { role: 'faces', side: 'y1' }), /both take/);
assert.match(surfaceWords('fracSlab', { role: 'top' }), /Tab: its underside/);

// ---- the mapping in the numbers
assert.deepEqual(tidySurface({ world: false, offsetV: 0, turn: 0, v: 64, u: 64, mode: 'size', modeV: 'size', flipU: true }),
                 { mode: 'size', u: 64, v: 64, flipU: true });
assert.deepEqual(Object.keys(tidySurface({ world: true, offsetU: 0.5, turn: 30, v: 2, u: 1, mode: 'count', modeV: 'fit' })),
                 ['mode', 'modeV', 'u', 'v', 'turn', 'offsetU', 'world']);
const bare = { free: 1, x0: 0, x1: 384, y0: -8, y1: 8, z0: -16, z1: 384, seed: 1 };
const sized = withMode('fracWall', bare, 'faces', 'size');
assert.deepEqual(surfaceMapping(sized, 'faces'), { mode: 'size', u: DEFAULT_REPEAT, v: DEFAULT_REPEAT });
assert.deepEqual(surfaceMapping(withMode('fracWall', sized, 'faces', 'count'), 'faces'), { mode: 'count', u: 1, v: 1 });
assert.equal(withMode('fracWall', sized, 'faces', 'size'), sized);                         // (the same mode: as it is)
assert.ok(!('mapping' in withMode('fracWall', sized, 'faces', 'original')));               // (the last surface out: mapping goes)
assert.equal(withMode('fracWall', bare, 'faces', 'original'), bare);
// a mode chosen keeps the turn, flips, offsets and world, and drops a modeV
const kept = withSurface(bare, 'faces', { mode: 'size', modeV: 'fit', u: 64, v: 1, turn: 30, flipU: true, offsetU: 0.5, world: true });
assert.deepEqual(surfaceMapping(withMode('fracWall', kept, 'faces', 'count'), 'faces'),
                 { mode: 'count', u: 1, v: 1, turn: 30, flipU: true, offsetU: 0.5, world: true });
// two surfaces of a slab: one taken out leaves the other
const both = withMode('fracSlab', withMode('fracSlab', { ...bare, y0: 0, y1: 96, z0: -2, z1: 2 }, 'top', 'fit'), 'underside', 'count');
assert.deepEqual(Object.keys(both.mapping.surfaces), ['top', 'underside']);
assert.deepEqual(Object.keys(withSurface(both, 'top', null).mapping.surfaces), ['underside']);
// a field's value
assert.equal(surfaceMapping(withValue(sized, 'faces', 'u', 64), 'faces').u, 64);
assert.equal(withValue(sized, 'faces', 'u', 0), null);
assert.equal(withValue(sized, 'faces', 'v', Number.NaN), null);
assert.equal(surfaceMapping(withValue(sized, 'faces', 'turn', 390), 'faces').turn, 30);
assert.equal(surfaceMapping(withValue(sized, 'faces', 'flipV', true), 'faces').flipV, true);
assert.ok(!('world' in surfaceMapping(withValue(withValue(sized, 'faces', 'world', true), 'faces', 'world', false), 'faces')));
assert.equal(withValue(bare, 'faces', 'u', 64), null);                                    // (Original: no fields)
// the look's repeat: a ground look's own; a wall's or slab's catalogue gives none here
assert.deepEqual(lookRepeat('ground', { shape: 'patch' }, 'top'), [320, 320]);
assert.deepEqual(lookRepeat('ground', { shape: 'patch', look: 'concrete' }, 'sides'), [384, 384]);
assert.deepEqual(lookRepeat('fracSlab', { look: 'floor' }, 'top'), [DEFAULT_REPEAT, DEFAULT_REPEAT]);
assert.deepEqual(lookRepeat('fracWall', { look: { mesh: 'Not.Read', measure: 1 } }, 'faces'), [DEFAULT_REPEAT, DEFAULT_REPEAT]);
// ---- what a look draws on a surface (its catalogue entry's surfaces, tools/bake/looks.py) and the fold's notes
{
  const side = (tiles, slots = [0]) => ({ slots, repeat: [192, 192], share: [2, 0.875], tiles });
  const walls = [
    { mesh: 'Ufo.Meshes.Wall_FRACTURED', surfaces: { faces: { A: side([true, true]), B: { ...side([true, false]), repeat: [288, 916] } } } },
    { mesh: 'Ufo.Meshes.Door_FRACTURED', surfaces: { faces: { A: null, B: null } } },
    { mesh: 'Shop.Meshes.Wall_FRACTURED', surfaces: { faces: { A: null, B: side([true, true], [0, 1]) } } },
  ];
  const roof = { mesh: 'Subway.Meshes.Roof_FRACTURED', facts: {}, surfaces: { top: side([true, false]), underside: side([true, false]) } };
  const answers = { '/looks/walls.json': { kind: 'wall', measure: 1, looks: walls }, '/looks/slabs.json': { kind: 'slab', measure: 1, looks: [roof] } };
  const was = globalThis.fetch;
  globalThis.fetch = async url => ({ ok: url in answers, status: url in answers ? 200 : 404, json: async () => answers[url] ?? {} });
  forgetLooks();
  await Promise.all([loadLooks('wall'), loadLooks('slab')]);
  const wall = mesh => ({ ...bare, look: { mesh, measure: 1 } }), slab = { ...bare, look: { mesh: roof.mesh, measure: 1 } };
  const size = { mode: 'size', u: 96, v: 96 };
  assert.deepEqual(lookSurface('fracSlab', slab, 'top').tiles, [true, false]);
  assert.equal(lookSurface('fracWall', bare, 'faces'), null);                                    // (no look named: no catalogue)
  // the look's measured repeat is Size's first: a wall's from side A's face, else side B's
  assert.deepEqual(lookRepeat('fracWall', wall('Ufo.Meshes.Wall_FRACTURED'), 'faces'), [192, 192]);
  assert.deepEqual(lookRepeat('fracWall', wall('Shop.Meshes.Wall_FRACTURED'), 'faces'), [192, 192]);
  assert.deepEqual(lookRepeat('fracWall', wall('Ufo.Meshes.Door_FRACTURED'), 'faces'), [DEFAULT_REPEAT, DEFAULT_REPEAT]);
  // a part of a larger texture: said once mapped, of whichever face it is
  const front = { role: 'faces', side: 'y1' }, rear = { role: 'faces', side: 'y0' };
  assert.deepEqual(textureNotes('fracSlab', slab, { role: 'top' }), []);
  assert.match(textureNotes('fracSlab', withSurface(slab, 'top', size), { role: 'top' }).join(), /part of a larger texture \(an atlas\) on its top: mapped, the whole texture repeats/);
  assert.deepEqual(textureNotes('fracSlab', withSurface(slab, 'underside', size), { role: 'top' }), []);
  const ufo = withSurface(wall('Ufo.Meshes.Wall_FRACTURED'), 'faces', size);
  assert.match(textureNotes('fracWall', ufo, rear).join(), /on this face:/);
  assert.match(textureNotes('fracWall', ufo, front).join(), /on its other face:/);
  // no face on a side: said before a mode is chosen; none at all
  assert.deepEqual(textureNotes('fracWall', wall('Ufo.Meshes.Door_FRACTURED'), front), ['This look has no faces, only trims, which keep their texture: the mapping changes nothing on it']);
  assert.match(textureNotes('fracWall', wall('Shop.Meshes.Wall_FRACTURED'), front).join(), /^This side of the look has no face/);
  assert.match(textureNotes('fracWall', wall('Shop.Meshes.Wall_FRACTURED'), rear).join(), /^The other side of this look has no face/);
  // its faces in two materials up the wall, once mapped (a picture across it needs one face material)
  assert.match(textureNotes('fracWall', withSurface(wall('Shop.Meshes.Wall_FRACTURED'), 'faces', size), rear).join('|'), /\|Its faces draw 2 materials up the wall/);
  // the slots a surface draws in: a wall's picked side's; null for a look no catalogue holds
  assert.deepEqual([surfaceSlots('fracWall', wall('Shop.Meshes.Wall_FRACTURED'), rear), surfaceSlots('fracWall', wall('Shop.Meshes.Wall_FRACTURED'), front),
                    surfaceSlots('fracSlab', slab, { role: 'underside' }), surfaceSlots('fracWall', bare, front)], [[0, 1], [], [0], null]);
  globalThis.fetch = was;
  forgetLooks();
}
// ---- a pattern's real size: what the surface's materials' own tiling does (their tilings, materialTiling's)
{
  const twice = { scale: [2, 2], known: true }, plain = { scale: [1, 1], known: true }, unread = { scale: [1, 1], known: false };
  assert.deepEqual(patternSize({ mode: 'size', u: 192, v: 192 }, [twice]),
                   { note: 'Its material repeats its texture 2 times in each repeat: the pattern shows every 96', known: true });
  assert.equal(patternSize({ mode: 'size', u: 192, v: 96 }, [twice]).note, 'Its material repeats its texture 2 times in each repeat: the pattern shows every 96 by 48');
  assert.equal(patternSize({ mode: 'count', u: 3, v: 2 }, [{ scale: [1.25, 1.25], known: true }]).note,
               'Its material repeats its texture 1.25 times in each repeat: the pattern shows 3.75 by 2.5 times over the surface');
  assert.equal(patternSize({ mode: 'size', modeV: 'fit', u: 96, v: 1 }, [{ scale: [2, 3], known: true }]).note,
               'Its material repeats its texture 2 by 3 times in each repeat: the pattern shows every 48 along U and 3 times along V');
  // nothing to say: unscaled, unmapped, materials that differ; not known when any material's tiling isn't
  assert.deepEqual(patternSize({ mode: 'size', u: 192, v: 192 }, [plain]), { note: null, known: true });
  assert.deepEqual(patternSize(null, [twice]), { note: null, known: true });
  assert.deepEqual(patternSize({ mode: 'fit', u: 1, v: 1 }, [twice, { scale: [1.25, 1.25], known: true }]), { note: null, known: true });
  assert.deepEqual(patternSize({ mode: 'size', u: 192, v: 192 }, [twice, unread]), { note: null, known: false });
  assert.deepEqual(patternSize({ mode: 'size', u: 192, v: 192 }, []), { note: null, known: false });
  // (the export's records: materialTiling's own cases are material_tiling_cases.json's, in shared_cases_test.mjs)
  assert.deepEqual(materialTiling(null), { scale: [1, 1], known: false });
}
// the fold's shut line
assert.equal(mappingWords('faces', { mode: 'size', u: 64, v: 64, turn: 30 }), 'faces: size 64, 30°');
assert.equal(mappingWords('top', { mode: 'count', u: 3, v: 2, flipU: true, world: true }), 'top: count 3 × 2, flipped, world');
assert.equal(mappingWords('underside', null), 'underside: original');
assert.equal(mappingWords('top', { mode: 'size', modeV: 'fit', u: 64, v: 1 }), 'top: size 64 / fit');

// ---- where a world-aligned surface is counted from (the shared cases are shared_cases_test.mjs's)
assert.equal(mappingOrigin('fracWall', { surfaces: { faces: { mode: 'size', u: 1, v: 1 } } }, [10, 20, 30], [0, 0, 0]), null);
assert.deepEqual(mappingOrigin('fracWall', { surfaces: { faces: { mode: 'size', u: 1, v: 1, world: true } } }, [10, 20, 30], [0, 16384, 0]),
                 { faces: [20, 30] });
assert.deepEqual(mappingOrigin('fracSlab', { surfaces: { underside: { mode: 'fit', u: 1, v: 1, world: true } } }, [10, 20, 30], [0, 16384, 0]),
                 { underside: [20, -10] });
// (a ground shape's sides take the place on all three axes: a side along x reads x, one along y reads y)
assert.deepEqual(mappingOrigin('ground', { surfaces: { sides: { mode: 'size', u: 1, v: 1, world: true } } }, [10, 20, 30], [0, 0, 0]),
                 { sides: [10, 20, 30] });
// (a role the kind has not is not counted)
assert.equal(mappingOrigin('ground', { surfaces: { faces: { mode: 'size', u: 1, v: 1, world: true } } }, [1, 2, 3], [0, 0, 0]), null);

console.log('made_mapping_test: ok');
