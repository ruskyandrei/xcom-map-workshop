// The map's baked light in the Game look (game-likeness plan, stage B2; F-180 to F-183): each lightmapped piece lit by
// its lightmap as the game's shader lights it (the formula in lighting.js's shared patch, USE_BAKED), the sky light
// and the map's static and area lights left out of it (they are in its lightmap, or light only what moves), the sun
// and the other lights live. Nothing is fetched until the Game look is first on (load).
//
// The export (44) gives each lightmapped piece its `lightmap` (two DXT1 atlases, their scales, its UV scale, bias and
// channel). The atlases are packed into one colour atlas and one direction atlas (baked_rules.js), shared by every lit
// material (lighting.js's bakedShared), and each lightmapped part gets a geometry of its own: the shared one's
// attributes with its lightmap UVs moved into the packed atlas and its scales beside them. Its materials stay shared.
import * as THREE from 'three';
import { bakedShared } from './lighting.js';
import { copyBlocks, packAtlases, packedBytes, packedUvs, scaleValues } from './baked_rules.js';
import { canTake, readDds } from './texture_file.js';

/** Off where the page's address says ?baked=off (the checks and the perf probe compare); ?baked=sum draws the three
 *  direction values summed, as the baker's flat_light does (F-181's check). */
export const bakedAsked = new URLSearchParams(globalThis.location?.search ?? '').get('baked');

export function createBakedLight({ data, roots, assetUrl, hasExtension }) {
  let loading = null, parts = [], packed = null, why = null;

  const lightmapped = () => [...roots.values()].filter(r => r.userData.source?.lightmap && !r.userData.source.added);

  async function atlas(key) {
    const record = data.textures[key];
    if (!record || record.container !== 'dds' || record.format !== 'PF_DXT1') throw new Error(`atlas ${key} is not a DXT1 file`);
    const response = await fetch(assetUrl(record.url));
    if (!response.ok) throw new Error(`atlas ${key}: ${response.status}`);
    const file = readDds(await response.arrayBuffer());
    return { key, width: file.width, height: file.height, data: file.mipmaps[0].data };
  }

  function texture(bytes, width, height) {
    const tex = new THREE.CompressedTexture([{ data: bytes, width, height }], width, height, THREE.RGBA_S3TC_DXT1_Format);
    tex.colorSpace = THREE.SRGBColorSpace;          // (both atlases are read through sRGB: F-180)
    tex.minFilter = tex.magFilter = THREE.LinearFilter;
    tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.flipY = false; tex.generateMipmaps = false; tex.needsUpdate = true;
    return tex;
  }

  // each lightmapped part's geometry of its own: the shared attributes, its packed UVs and its scales
  function ownGeometry(part, record, atlasSize, place) {
    const shared = part.userData.bakedFrom ?? part.geometry;
    const channel = shared.attributes[record.channel ? `uv${record.channel}` : 'uv'];
    if (!channel || channel.itemSize !== 2) return false;
    const geometry = new THREE.BufferGeometry();
    for (const [name, attribute] of Object.entries(shared.attributes)) geometry.setAttribute(name, attribute);
    geometry.setIndex(shared.index);
    for (const g of shared.groups) geometry.addGroup(g.start, g.count, g.materialIndex);
    geometry.boundingBox = shared.boundingBox; geometry.boundingSphere = shared.boundingSphere;
    geometry.morphAttributes = shared.morphAttributes;
    const uv = channel.array instanceof Float32Array && !channel.isInterleavedBufferAttribute ? channel.array
      : Float32Array.from({ length: channel.count * 2 }, (_, i) => (i % 2 ? channel.getY(i >> 1) : channel.getX(i >> 1)));
    geometry.setAttribute('bakedUv', new THREE.BufferAttribute(packedUvs(uv, record, atlasSize, place, packed), 3));
    const scales = scaleValues(record, channel.count);
    const both = new THREE.InterleavedBuffer(scales, 6);
    geometry.setAttribute('bakedScale0', new THREE.InterleavedBufferAttribute(both, 3, 0));
    geometry.setAttribute('bakedScale1', new THREE.InterleavedBufferAttribute(both, 3, 3));
    part.userData.bakedFrom = shared;
    part.geometry = geometry;
    return true;
  }

  async function loadNow() {
    const pieces = lightmapped();
    if (!pieces.length) { why = 'this export has no lightmaps (export 44 or newer has them)'; return; }
    if (!canTake('DXT1', true, hasExtension)) { why = 'this GPU can\'t read the lightmaps\' compressed atlases'; return; }
    const keys = [...new Set(pieces.flatMap(r => [r.userData.source.lightmap.colour, r.userData.source.lightmap.directions]))];
    const atlases = new Map((await Promise.all(keys.map(atlas))).map(a => [a.key, a]));
    // the colour atlases and the direction atlases each packed the same way (a piece's two are the same size)
    const colours = [...new Set(pieces.map(r => r.userData.source.lightmap.colour))].map(k => atlases.get(k));
    packed = packAtlases(colours.map(a => ({ key: a.key, width: a.width, height: a.height })));
    if (!packed) { why = 'the map\'s lightmaps don\'t fit in one atlas'; return; }
    const colourBytes = packedBytes(packed.width, packed.height), directionBytes = packedBytes(packed.width, packed.height);
    for (const r of pieces) {
      const lm = r.userData.source.lightmap, colour = atlases.get(lm.colour), directions = atlases.get(lm.directions), place = packed.places[lm.colour];
      if (!colour || !directions || directions.width !== colour.width || directions.height !== colour.height) continue;
      if (!colour.copied) { copyBlocks(colourBytes, packed.width, colour.data, colour.width, colour.height, place.x, place.y); colour.copied = true; }
      if (!directions.copied?.[lm.colour]) {
        copyBlocks(directionBytes, packed.width, directions.data, directions.width, directions.height, place.x, place.y);
        directions.copied = { ...(directions.copied ?? {}), [lm.colour]: true };
      }
      for (const part of r.userData.parts ?? []) {
        if (ownGeometry(part, lm, colour, place)) parts.push(part);
      }
    }
    bakedShared.bakedColour.value = texture(colourBytes, packed.width, packed.height);
    bakedShared.bakedDirections.value = texture(directionBytes, packed.width, packed.height);
    bakedShared.bakedWeight.value = bakedAsked === 'sum' ? 3 : 1;
    // the sky light lights no static piece on any of the game's maps (F-182): the lightmap stands in its place
    bakedShared.bakedSky.value = 0;
  }

  /** Load the map's lightmaps (once; a promise), then turn the baked light on. Nothing where ?baked=off. */
  function load() {
    if (bakedAsked === 'off') return Promise.resolve(false);
    loading ??= loadNow().then(() => { bakedShared.bakedOn.value = parts.length ? 1 : 0; return Boolean(parts.length); })
      .catch(error => { why = error.message; bakedShared.bakedOn.value = 0; return false; });
    return loading;
  }
  /** As a map opens: nothing loaded, the light off. */
  function reset() {
    for (const part of parts) if (part.userData.bakedFrom) { part.geometry = part.userData.bakedFrom; delete part.userData.bakedFrom; }
    parts = []; packed = null; why = null; loading = null;
    bakedShared.bakedOn.value = 0;
    for (const name of ['bakedColour', 'bakedDirections']) { bakedShared[name].value?.dispose(); bakedShared[name].value = null; }
  }
  /** The baked light on or off while loaded (the perf probe's and the checks' comparison: only its uniform changes). */
  function set(on) { bakedShared.bakedOn.value = on && parts.length ? 1 : 0; }
  /** What the checks and the perf probe read. */
  const state = () => ({ on: Boolean(bakedShared.bakedOn.value), parts: parts.length, atlas: packed ? [packed.width, packed.height] : null, why });
  return { load, reset, set, state };
}
