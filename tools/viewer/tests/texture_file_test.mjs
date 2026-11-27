// A DDS texture file read for the GPU (texture_file.js; game-likeness plan, A-S3b). Run:
// node tools/viewer/tests/texture_file_test.mjs
import assert from 'node:assert/strict';
import { EXTENSIONS, SRGB_EXTENSION, canTake, isDds, levelBytes, missingByAddress, readDds } from '../web/texture_file.js';

// a DDS file as texture.py writes it: the header, then each level from the largest
function dds(width, height, fourcc, levels) {
  const format = { DXT1: 'DXT1', DXT5: 'DXT5', ATI2: 'BC5' }[fourcc];
  const sizes = [];
  for (let k = 0, w = width, h = height; k < levels; k++, w = Math.max(1, w >> 1), h = Math.max(1, h >> 1)) sizes.push(levelBytes(format, w, h));
  const buffer = new ArrayBuffer(128 + sizes.reduce((a, b) => a + b, 0));
  const view = new DataView(buffer);
  view.setUint32(0, 0x20534444, true);
  view.setUint32(4, 124, true);
  view.setUint32(8, 0x81007 | (levels > 1 ? 0x20000 : 0), true);
  view.setUint32(12, height, true);
  view.setUint32(16, width, true);
  view.setUint32(20, sizes[0], true);
  view.setUint32(28, levels, true);
  view.setUint32(76, 32, true);
  view.setUint32(80, 4, true);
  for (let k = 0; k < 4; k++) view.setUint8(84 + k, fourcc.charCodeAt(k));
  let at = 128;
  sizes.forEach((size, k) => { new Uint8Array(buffer, at, size).fill(k + 1); at += size; });
  return buffer;
}

// a 2048 by 2048 DXT1 texture of 12 levels: each level its size and its own bytes
const read = readDds(dds(2048, 2048, 'DXT1', 12));
assert.equal(read.format, 'DXT1');
assert.equal(read.width, 2048);
assert.equal(read.mipmaps.length, 12);
assert.deepEqual(read.mipmaps.map(m => m.width), [2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2, 1]);
assert.equal(read.mipmaps[0].data.length, 512 * 512 * 8);
assert.equal(read.mipmaps[11].data.length, 8);              // a 1 by 1 level is still a block
assert.equal(read.mipmaps[3].data[0], 4);

// a non-square DXT5 texture, and a BC5 normal map of one level
const tall = readDds(dds(256, 64, 'DXT5', 3));
assert.deepEqual(tall.mipmaps.map(m => [m.width, m.height, m.data.length]), [[256, 64, 64 * 16 * 16], [128, 32, 32 * 8 * 16], [64, 16, 16 * 4 * 16]]);
assert.equal(readDds(dds(512, 512, 'ATI2', 1)).format, 'BC5');

// what it refuses
assert.throws(() => readDds(new ArrayBuffer(64)), /not a DDS/);
assert.throws(() => readDds(dds(64, 64, 'DXT1', 4).slice(0, 200)), /cut short/);
const odd = dds(64, 64, 'DXT1', 1);
new DataView(odd).setUint8(84, 'Q'.charCodeAt(0));
assert.throws(() => readDds(odd), /QXT1/);

// which GPU can take what
const has = names => name => names.includes(name);
assert.equal(canTake('DXT1', true, has([EXTENSIONS.DXT1, SRGB_EXTENSION])), true);
assert.equal(canTake('DXT1', true, has([EXTENSIONS.DXT1])), false);       // a colour texture needs the sRGB form
assert.equal(canTake('DXT1', false, has([EXTENSIONS.DXT1])), true);
assert.equal(canTake('BC5', false, has([EXTENSIONS.DXT1, SRGB_EXTENSION])), false);
assert.equal(canTake('BC5', false, has([EXTENSIONS.BC5])), true);

// the address's fallbacks, for the checks
assert.deepEqual([...missingByAddress('?map=URB_Bar&texfallback=srgb,rgtc')].sort(), [EXTENSIONS.BC5, SRGB_EXTENSION].sort());
assert.equal(missingByAddress('?texfallback=all').size, 3);
assert.equal(missingByAddress('?map=URB_Bar').size, 0);
assert.equal(isDds('texture-12.dds'), true);
assert.equal(isDds('/cache-library/x/texture-12.dds?r=1'), true);
assert.equal(isDds('texture-12.png'), false);
console.log('texture_file: ok');
