// The map's baked light packed for the page (baked_rules.js; game-likeness plan, B2). Run:
// node tools/viewer/tests/baked_rules_test.mjs
import assert from 'node:assert/strict';
import { bakedLightAt, copyBlocks, packAtlases, packedBytes, packedUvs, scaleValues } from '../web/baked_rules.js';

// URB_Bar's atlases by size (export 44): nine 1024 by 1024 a channel, five 1024 by 512, and many small ones
const bar = [...Array(9)].map((_, k) => ({ key: `big${k}`, width: 1024, height: 1024 }))
  .concat([...Array(5)].map((_, k) => ({ key: `half${k}`, width: 1024, height: 512 })))
  .concat([...Array(24)].map((_, k) => ({ key: `s${k}`, width: 16, height: 16 })), [{ key: 'odd', width: 64, height: 16 }]);
const packed = packAtlases(bar);
assert.ok(packed && packed.width === 4096 && packed.height <= 4096, packed && [packed.width, packed.height]);
// every atlas inside, on whole blocks, none over another
const rects = bar.map(a => ({ ...a, ...packed.places[a.key] }));
for (const r of rects) {
  assert.ok(r.x % 4 === 0 && r.y % 4 === 0 && r.x + r.width <= packed.width && r.y + r.height <= packed.height, r);
}
for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
  const a = rects[i], b = rects[j];
  assert.ok(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y, [a.key, b.key]);
}
// too much for the largest is none; the same atlases pack the same each time
assert.equal(packAtlases([...Array(80)].map((_, k) => ({ key: k, width: 1024, height: 1024 })), 8192), null);
assert.deepEqual(packAtlases(bar), packed);
assert.throws(() => packAtlases([{ key: 'x', width: 6, height: 8 }]), /whole blocks/);

// the blocks copied where the packing put them: a 8 by 8 atlas (four blocks) into a 16 by 8 one at x 8
const src = new Uint8Array(4 * 8).map((_, i) => i + 1), dst = packedBytes(16, 8);
copyBlocks(dst, 16, src, 8, 8, 8, 0);
// the packed atlas's rows of blocks are four blocks across: the atlas's first row in its third and fourth
assert.deepEqual([...dst.subarray(16, 32)], [...src.subarray(0, 16)]);
assert.deepEqual([...dst.subarray(48, 64)], [...src.subarray(16, 32)]);
assert.equal(dst.subarray(0, 16).reduce((s, v) => s + v, 0), 0);

// a piece's UVs moved into the packed atlas: its rectangle of its atlas, then the atlas's place
const record = { uvScale: [0.5, 0.25], uvBias: [0.25, 0.5] };
const uvs = packedUvs(new Float32Array([0, 0, 1, 1]), record, { width: 1024, height: 512 }, { x: 1024, y: 512 }, { width: 4096, height: 2048 });
assert.deepEqual([...uvs].map(v => Math.round(v * 1e6) / 1e6), [(0.25 * 1024 + 1024) / 4096, (0.5 * 512 + 512) / 2048, 1,
  ((0.5 + 0.25) * 1024 + 1024) / 4096, ((0.25 + 0.5) * 512 + 512) / 2048, 1]);
assert.deepEqual([...scaleValues({ scale0: [1, 1, 1], scale1: [1, 1.1, 1.2] }, 2)].map(v => Math.round(v * 100) / 100), [1, 1, 1, 1, 1.1, 1.2, 1, 1, 1, 1, 1.1, 1.2]);

// the game's lightmap: a flat normal takes a third of each direction value (F-181); a normal toward one basis vector all of it
const flat = bakedLightAt([0.5, 0.5, 0.5], [0.9, 0.6, 0.3], [1, 1, 1], [1, 1, 1]);
assert.ok(Math.abs(flat[0] - 0.5 * (0.9 + 0.6 + 0.3) / 3) < 1e-6, flat);
const toward = bakedLightAt([1, 1, 1], [0.9, 0.6, 0.3], [1, 1, 1], [1, 1, 1], [0, 0.816496611, 0.577350259]);
assert.ok(Math.abs(toward[0] - 0.9) < 1e-6, toward);
console.log('baked rules: ok');

// the sun's baked shadows (B3): rows copied a byte a texel; the field turned into light
{
  const { copyRows, shadowAt } = await import('../web/baked_rules.js');
  const rows = new Uint8Array(4 * 2).map((_, i) => i + 1), into = new Uint8Array(8 * 4);
  copyRows(into, 8, rows, 4, 2, 4, 1);
  assert.deepEqual([...into.subarray(12, 16)], [1, 2, 3, 4]);
  assert.deepEqual([...into.subarray(20, 24)], [5, 6, 7, 8]);
  assert.equal(into.subarray(0, 12).reduce((s, v) => s + v, 0), 0);
  assert.equal(shadowAt(1), 1);
  assert.equal(shadowAt(0), 0);
  assert.ok(Math.abs(shadowAt(0.5) - 0.25) < 1e-12);      // (half light at the edge, squared)
  assert.ok(shadowAt(0.6) > shadowAt(0.5) && shadowAt(0.5) > shadowAt(0.4));
  console.log('baked rules (shadows): ok');
}

// edited pieces (B4): a DXT1 texel decoded, the live light at a point, the factor
{
  const { dxt1Texel, liveFactor, liveLightAt, luminance, srgbToLinear } = await import('../web/baked_rules.js');
  // one block: colour 0 white (0xffff), colour 1 black (0x0000), four-colour mode; texels 0 to 3 of its first row indices 0 to 3
  const block = new Uint8Array([0xff, 0xff, 0x00, 0x00, 0b11100100, 0, 0, 0]);
  assert.deepEqual(dxt1Texel(block, 4, 0, 0), [1, 1, 1]);
  assert.deepEqual(dxt1Texel(block, 4, 1, 0), [0, 0, 0]);
  assert.ok(Math.abs(dxt1Texel(block, 4, 2, 0)[0] - 2 / 3) < 1e-9);
  assert.ok(Math.abs(dxt1Texel(block, 4, 3, 0)[0] - 1 / 3) < 1e-9);
  // three-colour mode (colour 0 below colour 1): index 3 is black, index 2 halfway
  const three = new Uint8Array([0x00, 0x00, 0xff, 0xff, 0b11100000, 0, 0, 0]);
  assert.ok(Math.abs(dxt1Texel(three, 4, 2, 0)[1] - 0.5) < 1e-9);
  assert.deepEqual(dxt1Texel(three, 4, 3, 0), [0, 0, 0]);
  assert.ok(Math.abs(srgbToLinear(0.5) - 0.2140) < 1e-3);
  // a white point light of radius 100, falloff 2, straight above a floor: at 50 units (1 - 0.25)^2 of its light
  const lamp = { kind: 'point', location: [0, 0, 50], radius: 100, falloffExponent: 2, color: [1, 1, 1], brightness: 1 };
  const under = liveLightAt([0, 0, 0], [0, 0, 1], [lamp]);
  assert.ok(Math.abs(under[0] - 0.5625) < 1e-9, under);
  assert.deepEqual(liveLightAt([0, 0, 0], [0, 0, -1], [lamp]), [0, 0, 0]);       // (facing away)
  assert.deepEqual(liveLightAt([0, 0, 150], [0, 0, -1], [lamp]), [0, 0, 0]);     // (out of reach)
  // a spot light pointing down lights under it and not beside it, outside its cone
  const spot = { ...lamp, kind: 'spot', direction: [0, 0, -1], innerConeAngle: 10, outerConeAngle: 20 };
  assert.ok(luminance(liveLightAt([0, 0, 0], [0, 0, 1], [spot])) > 0.5);
  assert.deepEqual(liveLightAt([40, 0, 0], [0, 0, 1], [spot]), [0, 0, 0]);
  // the factor: the sums' ratio over the samples the live lights reach; none from too few
  assert.ok(Math.abs(liveFactor([[0.2, 0.1], [0.4, 0.3], [0.5, 0]], 2) - 1.5) < 1e-12);
  assert.equal(liveFactor([[0.2, 0.1]], 2), null);
  console.log('baked rules (edited pieces): ok');
}
