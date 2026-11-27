// The map's baked light packed for the page (game-likeness plan, stage B2; F-180, F-183). Pure: numbers and bytes, no
// three.js. baked_light.js loads the export's lightmap atlases (export 44: DXT1, read through sRGB) and draws with these.
//
// A material for each lightmapped piece costs more than its lightmap (F-183: each draw then refreshes the material's
// uniforms), so the page draws every piece with the materials it shares: the map's atlases are packed into one colour
// atlas and one direction atlas (their DXT1 blocks copied where the packing puts them, so the texels are the game's),
// and each piece carries its own lightmap UVs, moved into the packed atlas, and its two scales, as attributes of a
// geometry of its own. The packed atlases keep their top level alone: a partial mip chain is not a complete texture,
// and the lightmaps' light is soft at the editor's distances.

import { effectiveCone } from './light_rules.js';

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

// Edited pieces (stage B4): a piece the project moved, added or relit is lit live, its local lights scaled by one factor
// a map that brings them to its lightmaps' level (a lightmap holds the light bounced about as well, which the live
// lights don't). The factor is worked out as the map opens, on the lightmapped pieces: the baked light at some of each
// piece's vertices (the texel of its lightmap there, a flat normal) against the live lights at the same points.

/** A texel of a DXT1 atlas (`bytes`, `width` texels across) as stored: [r, g, b] from 0 to 1 (sRGB). */
export function dxt1Texel(bytes, width, x, y) {
  const at = ((y >> 2) * (width >> 2) + (x >> 2)) * BLOCK_BYTES;
  const c0 = bytes[at] | (bytes[at + 1] << 8), c1 = bytes[at + 2] | (bytes[at + 3] << 8);
  const bits = (bytes[at + 4] | (bytes[at + 5] << 8) | (bytes[at + 6] << 16) | (bytes[at + 7] << 24)) >>> 0;
  const index = (bits >>> (2 * ((y & 3) * 4 + (x & 3)))) & 3;
  const rgb = c => [((c >> 11) & 31) / 31, ((c >> 5) & 63) / 63, (c & 31) / 31];
  const a = rgb(c0), b = rgb(c1);
  if (index < 2) return index ? b : a;
  if (c0 > c1) return a.map((v, k) => (index === 2 ? 2 * v + b[k] : v + 2 * b[k]) / 3);
  return index === 2 ? a.map((v, k) => (v + b[k]) / 2) : [0, 0, 0];
}

export const srgbToLinear = v => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
export const luminance = rgb => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];

/** The live light of `lights` (the export's records: game units and axes) at a point with a unit normal, before the
 *  material's diffuse colour, as the Game look's shader gives it a piece without a lightmap (lighting.js): for each
 *  point or spot light in reach, dot(n, l) x its colour (a 2.2 power) x brightness x pow(1 - d^2 / R^2, falloff),
 *  times the spot's cone squared. */
export function liveLightAt(point, normal, lights) {
  const out = [0, 0, 0];
  for (const l of lights) {
    const dx = l.location[0] - point[0], dy = l.location[1] - point[1], dz = l.location[2] - point[2];
    const d2 = (dx * dx + dy * dy + dz * dz) / (l.radius * l.radius);
    if (!(d2 < 1)) continue;
    const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1, lx = dx / d, ly = dy / d, lz = dz / d;
    const cos = normal[0] * lx + normal[1] * ly + normal[2] * lz;
    if (cos <= 0) continue;
    let att = Math.pow(1 - d2, l.falloffExponent ?? 2);
    if (l.kind === 'spot') {
      const [inner, outer] = effectiveCone(l.innerConeAngle, l.outerConeAngle), dir = l.direction;
      const len = Math.hypot(...dir) || 1, cosOuter = Math.cos(outer);
      const cone = Math.min(1, Math.max(0, (-(lx * dir[0] + ly * dir[1] + lz * dir[2]) / len - cosOuter) / (Math.cos(inner) - cosOuter)));
      att *= cone * cone;
    }
    const k = cos * att * (l.brightness ?? 1);
    for (let c = 0; c < 3; c++) out[c] += Math.pow(l.color[c], 2.2) * k;
  }
  return out;
}

/** The factor that brings the live lights to the lightmaps' level: the baked light summed over the live light summed,
 *  in luminance, over the samples [baked, live] the live lights reach; null with fewer than `least` of them. */
export function liveFactor(samples, least = 20) {
  let baked = 0, live = 0, n = 0;
  for (const [b, l] of samples) if (l > 1e-3) { baked += b; live += l; n++; }
  return n >= least && live > 0 ? baked / live : null;
}
