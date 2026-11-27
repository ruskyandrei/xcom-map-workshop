// The map's baked light packed for the page (game-likeness plan, stage B2; F-180, F-183). Pure: numbers and bytes, no
// three.js. baked_light.js loads the export's lightmap atlases (export 44: DXT1, read through sRGB) and draws with these.
//
// A material for each lightmapped piece costs more than its lightmap (F-183: each draw then refreshes the material's
// uniforms), so the page draws every piece with the materials it shares: the map's atlases are packed into one colour
// atlas and one direction atlas (their DXT1 blocks copied where the packing puts them, so the texels are the game's),
// and each piece carries its own lightmap UVs, moved into the packed atlas, and its two scales, as attributes of a
// geometry of its own. The packed atlases keep their top level alone: a partial mip chain is not a complete texture,
// and the lightmaps' light is soft at the editor's distances.

const BLOCK = 4, BLOCK_BYTES = 8;      // DXT1: 4 by 4 texels in 8 bytes

/** Where each atlas goes in the packed one: { width, height, places: { key: { x, y } } } for atlases [{ key, width,
 *  height }] (each a multiple of 4 across and down), packed in rows, the tallest first, in an atlas `width` across
 *  (the smallest power of two from 1024 that the widest fits in and that keeps it no taller than wide, at most `max`),
 *  its height a multiple of 4. Null when they don't fit in `max` by `max`. */
export function packAtlases(atlases, max = 8192) {
  const items = [...atlases].sort((a, b) => b.height - a.height || b.width - a.width || String(a.key).localeCompare(String(b.key)));
  const area = items.reduce((s, a) => s + a.width * a.height, 0);
  const widest = items.reduce((m, a) => Math.max(m, a.width), 0);
  for (let width = 1024; width <= max; width *= 2) {
    if (width < widest || area > width * max) continue;
    const places = {};
    let x = 0, y = 0, row = 0;
    for (const a of items) {
      if (a.width % BLOCK || a.height % BLOCK) throw new Error(`an atlas of ${a.width} by ${a.height} is not whole blocks`);
      if (x + a.width > width) { y += row; x = 0; row = 0; }
      places[a.key] = { x, y };
      x += a.width; row = Math.max(row, a.height);
    }
    const height = Math.ceil((y + row) / BLOCK) * BLOCK;
    if (height <= max && height <= width) return { width, height, places };
  }
  return null;
}

/** DXT1 blocks of an atlas (`src`, `width` by `height` texels) copied into the packed one (`dst`, `packedWidth`
 *  across) at texel (x, y), each a multiple of 4. */
export function copyBlocks(dst, packedWidth, src, width, height, x, y) {
  const rowBytes = (width / BLOCK) * BLOCK_BYTES, packedRow = (packedWidth / BLOCK) * BLOCK_BYTES;
  for (let by = 0; by < height / BLOCK; by++) {
    const from = by * rowBytes, to = (y / BLOCK + by) * packedRow + (x / BLOCK) * BLOCK_BYTES;
    dst.set(src.subarray(from, from + rowBytes), to);
  }
}

/** The bytes of a packed atlas `width` by `height` texels. */
export const packedBytes = (width, height) => new Uint8Array((width / BLOCK) * (height / BLOCK) * BLOCK_BYTES);

/** A piece's lightmap UVs moved into the packed atlas: [u, v, 1] a vertex (the third the piece's mark: lightmapped),
 *  from its mesh's lightmap channel `uv` (pairs), the record's UV scale and bias, its atlas's size and place and the
 *  packed atlas's size. */
export function packedUvs(uv, record, atlas, place, packed) {
  const out = new Float32Array((uv.length / 2) * 3);
  const sx = record.uvScale[0] * atlas.width / packed.width, sy = record.uvScale[1] * atlas.height / packed.height;
  const bx = (record.uvBias[0] * atlas.width + place.x) / packed.width, by = (record.uvBias[1] * atlas.height + place.y) / packed.height;
  for (let i = 0, j = 0; i < uv.length; i += 2, j += 3) {
    out[j] = uv[i] * sx + bx; out[j + 1] = uv[i + 1] * sy + by; out[j + 2] = 1;
  }
  return out;
}

/** The piece's two scales a vertex: [scale0, scale1] six numbers a vertex (the colour's and the directions'). */
export function scaleValues(record, count) {
  const out = new Float32Array(count * 6), one = [...record.scale0, ...record.scale1];
  for (let i = 0; i < count; i++) out.set(one, i * 6);
  return out;
}

/** The game's lightmap at a texel, in numbers: colour x scale0 x dot(directions x scale1, b) with b the squared
 *  saturated cosines of the normal `n` (tangent space) with UE3's three basis vectors (section 0; F-181). The node test
 *  holds the GLSL's sums to it. */
export function bakedLightAt(colour, directions, scale0, scale1, n = [0, 0, 1]) {
  const basis = [[0, 0.816496611, 0.577350259], [-0.707106769, -0.408248305, 0.577350259], [0.707106769, -0.408248305, 0.577350259]];
  const len = Math.hypot(...n) || 1, nn = n.map(v => v / len);
  const b = basis.map(v => Math.max(0, Math.min(1, v[0] * nn[0] + v[1] * nn[1] + v[2] * nn[2])) ** 2);
  const d = directions[0] * scale1[0] * b[0] + directions[1] * scale1[1] * b[1] + directions[2] * scale1[2] * b[2];
  return colour.map((c, k) => c * scale0[k] * d);
}

// The sun's baked shadows (stage B3): each piece's shadow map of the dominant light, an 8-bit distance field (0.5 on
// the shadow's edge, 1 in the light and 0 in the shadow 25 units either side: XCOM's Lightmass, MaxTransitionDistance
// 50; tools/bake/shadowmaps.py), packed the same way into one single-channel atlas.

/** Rows of a one-byte-a-texel atlas (`src`, `width` by `height`) copied into the packed one (`dst`, `packedWidth`
 *  across) at texel (x, y). */
export function copyRows(dst, packedWidth, src, width, height, x, y) {
  for (let row = 0; row < height; row++) dst.set(src.subarray(row * width, (row + 1) * width), (y + row) * packedWidth + x);
}

/** How the game's light pass turns the field into light: pow(saturate((field - 0.5) * sharpness + 0.5), exponent)
 *  (its shader's (field + bias) x scale, then the power: DistanceFieldParameters, which the engine sets at run time;
 *  SHADOW_SHAPE the editor's, held against the game's shots). */
export const SHADOW_SHAPE = { sharpness: 2, exponent: 2 };
export const shadowAt = (field, shape = SHADOW_SHAPE) => Math.pow(Math.min(1, Math.max(0, (field - 0.5) * shape.sharpness + 0.5)), shape.exponent);
