// A texture file the export wrote as the game stores it (texture.py: a DDS file of DXT1, DXT3, DXT5 or BC5 blocks
// with every live mip), read for the GPU: its size, its block format and each level's bytes, and which WebGL
// extension the GPU needs for it (game-likeness plan, A-S3b). Pure: no three.js, no page. scene_pieces.js makes a
// compressed texture from what this gives, or asks the server for the file's PNG (<file>.png) where the GPU lacks the
// extension.

const MAGIC = 0x20534444;                         // 'DDS '
const FOURCC = { DXT1: 'DXT1', DXT3: 'DXT3', DXT5: 'DXT5', ATI2: 'BC5' };

/** The WebGL extensions each format needs, the colour (sRGB) form apart. */
export const EXTENSIONS = {
  DXT1: 'WEBGL_compressed_texture_s3tc', DXT3: 'WEBGL_compressed_texture_s3tc', DXT5: 'WEBGL_compressed_texture_s3tc',
  BC5: 'EXT_texture_compression_rgtc',
};
export const SRGB_EXTENSION = 'WEBGL_compressed_texture_s3tc_srgb';

/** Whether a url names a DDS file. */
export const isDds = url => /\.dds(\?|$)/i.test(url ?? '');

/** The bytes of one level of a block format. */
export function levelBytes(format, width, height) {
  return Math.max(1, (width + 3) >> 2) * Math.max(1, (height + 3) >> 2) * (format === 'DXT1' ? 8 : 16);
}

/** { width, height, format (DXT1, DXT3, DXT5, BC5), mipmaps: [{ data (Uint8Array), width, height }] } of a DDS
 *  file's bytes (an ArrayBuffer). Throws on a file it can't read: another magic, a format not listed, a level cut
 *  short. */
export function readDds(buffer) {
  const view = new DataView(buffer);
  if (buffer.byteLength < 128 || view.getUint32(0, true) !== MAGIC) throw new Error('not a DDS file');
  const height = view.getUint32(12, true), width = view.getUint32(16, true);
  const flags = view.getUint32(8, true);
  const count = flags & 0x20000 ? Math.max(1, view.getUint32(28, true)) : 1;
  const code = String.fromCharCode(...new Uint8Array(buffer, 84, 4));
  const format = FOURCC[code];
  if (!format) throw new Error(`a DDS file of ${code} blocks`);
  if (!width || !height || width > 16384 || height > 16384) throw new Error('a DDS file of no size');
  const mipmaps = [];
  let at = 128, w = width, h = height;
  for (let k = 0; k < count; k++) {
    const size = levelBytes(format, w, h);
    if (at + size > buffer.byteLength) throw new Error(`level ${k} of the DDS file is cut short`);
    mipmaps.push({ data: new Uint8Array(buffer, at, size), width: w, height: h });
    at += size;
    w = Math.max(1, w >> 1);
    h = Math.max(1, h >> 1);
  }
  return { width, height, format, mipmaps };
}

/** Whether a GPU with the extensions `has` (name => bool) can take a texture of `format`, as colour (sRGB) or not. */
export function canTake(format, srgb, has) {
  const needed = EXTENSIONS[format];
  if (!needed || !has(needed)) return false;
  return !(srgb && format !== 'BC5' && !has(SRGB_EXTENSION));
}

/** The extensions a page's address says to treat as missing (?texfallback=s3tc,srgb,rgtc or all), for the checks. */
export function missingByAddress(search) {
  const asked = new URLSearchParams(search ?? '').get('texfallback');
  if (!asked) return new Set();
  const words = asked.split(',').map(w => w.trim());
  const out = new Set();
  if (words.includes('all') || words.includes('s3tc')) out.add(EXTENSIONS.DXT1);
  if (words.includes('all') || words.includes('srgb')) out.add(SRGB_EXTENSION);
  if (words.includes('all') || words.includes('rgtc')) out.add(EXTENSIONS.BC5);
  return out;
}
