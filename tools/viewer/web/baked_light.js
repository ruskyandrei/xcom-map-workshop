// The map's baked light in the Game look (game-likeness plan, stage B2; F-180 to F-183): each lightmapped piece lit by
// its lightmap as the game's shader lights it (the formula in lighting.js's shared patch, USE_BAKED), the sky light
// and the map's static and area lights left out of it (they are in its lightmap, or light only what moves), the sun
// and the other lights live. Nothing is fetched until the Game look is first on (load).
//
// The export (44) gives each lightmapped piece its `lightmap` (two DXT1 atlases, their scales, its UV scale, bias and
// channel). The atlases are packed into one colour atlas and one direction atlas (baked_rules.js), shared by every lit
// material (lighting.js's bakedShared), and each lightmapped part gets a geometry of its own: the shared one's
// attributes with its lightmap UVs moved into the packed atlas and its scales beside them. Its materials stay shared.
// The sun's shadow on such a piece (stage B3) is its shadow map of the dominant light (export 44's `sunShadow`, an 8-bit
// distance field), packed the same way into one single-channel atlas, its UVs beside its lightmap's. A piece wholly in
// the sun's shadow (export 45's `sunIrrelevant`: the light on its IrrelevantLights, F-184) takes no sun at all; one
// with no shadow map, or a plain shadow factor (none on the four maps shot), keeps the live shadow map.
import * as THREE from 'three';
import { bakedShared } from './lighting.js';
import { SHADOW_SHAPE, copyBlocks, copyRows, packAtlases, packedBytes, packedUvs, scaleValues } from './baked_rules.js';
import { canTake, readDds } from './texture_file.js';

/** Off where the page's address says ?baked=off (the checks and the perf probe compare); ?baked=sum draws the three
 *  direction values summed, as the baker's flat_light does (F-181's check). */
export const bakedAsked = new URLSearchParams(globalThis.location?.search ?? '').get('baked');

export function createBakedLight({ data, roots, assetUrl, hasExtension }) {
  let loading = null, parts = [], packed = null, shadowPacked = null, shadows = 0, darks = 0, why = null;

  const lightmapped = () => [...roots.values()].filter(r => r.userData.source?.lightmap && !r.userData.source.added);

  async function atlas(key) {
    const record = data.textures[key];
    if (!record || record.container !== 'dds' || record.format !== 'PF_DXT1') throw new Error(`atlas ${key} is not a DXT1 file`);
    const response = await fetch(assetUrl(record.url));
    if (!response.ok) throw new Error(`atlas ${key}: ${response.status}`);
    const file = readDds(await response.arrayBuffer());
    return { key, width: file.width, height: file.height, data: file.mipmaps[0].data };
  }

  // a shadow map's atlas (a PNG of its one channel), its red values
  async function shadowAtlas(key) {
    const record = data.textures[key];
    if (!record) throw new Error(`shadow atlas ${key} is not in the export`);
    const response = await fetch(assetUrl(record.url));
    if (!response.ok) throw new Error(`shadow atlas ${key}: ${response.status}`);
    const picture = await createImageBitmap(await response.blob());
    const canvas = new OffscreenCanvas(picture.width, picture.height), g = canvas.getContext('2d');
    g.drawImage(picture, 0, 0);
    const rgba = g.getImageData(0, 0, picture.width, picture.height).data, red = new Uint8Array(picture.width * picture.height);
    for (let i = 0; i < red.length; i++) red[i] = rgba[i * 4];
    return { key, width: picture.width, height: picture.height, data: red };
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
  function ownGeometry(part, record, atlasSize, place, shadow, dark) {
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
    // its lightmap UVs and its shadow map's in the packed atlases (the shadow map's none: the live shadow map), and its
    // scales with its mark (1: a lightmap, 2: and a shadow map of the sun, 3: and no sun at all)
    const lm = packedUvs(uv, record, atlasSize, place, packed);
    const sh = shadow ? packedUvs(uv, shadow.record, shadow.atlas, shadow.place, shadowPacked) : null;
    const uvs = new Float32Array(channel.count * 4), scales = scaleValues(record, channel.count), both = new Float32Array(channel.count * 7);
    for (let i = 0; i < channel.count; i++) {
      uvs[i * 4] = lm[i * 3]; uvs[i * 4 + 1] = lm[i * 3 + 1];
      if (sh) { uvs[i * 4 + 2] = sh[i * 3]; uvs[i * 4 + 3] = sh[i * 3 + 1]; }
      both.set(scales.subarray(i * 6, i * 6 + 3), i * 7); both[i * 7 + 3] = dark ? 3 : sh ? 2 : 1;
      both.set(scales.subarray(i * 6 + 3, i * 6 + 6), i * 7 + 4);
    }
    geometry.setAttribute('bakedUv', new THREE.BufferAttribute(uvs, 4));
    const interleaved = new THREE.InterleavedBuffer(both, 7);
    geometry.setAttribute('bakedScale0', new THREE.InterleavedBufferAttribute(interleaved, 4, 0));
    geometry.setAttribute('bakedScale1', new THREE.InterleavedBufferAttribute(interleaved, 3, 4));
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
    // the sun's shadow maps of the lightmapped pieces, packed into one single-channel atlas (a failure keeps the live shadow)
    const fieldOf = r => (r.userData.source.sunShadow && !r.userData.source.sunShadow.factor ? r.userData.source.sunShadow : null);
    const shadowKeys = [...new Set(pieces.filter(fieldOf).map(r => fieldOf(r).texture))];
    const shadowAtlases = new Map();
    try {
      for (const a of await Promise.all(shadowKeys.map(shadowAtlas))) shadowAtlases.set(a.key, a);
      shadowPacked = shadowAtlases.size ? packAtlases([...shadowAtlases.values()].map(a => ({ key: a.key, width: a.width, height: a.height }))) : null;
    } catch (error) { shadowPacked = null; console.warn(`the sun's baked shadows: ${error.message}`); }
    const shadowBytes = shadowPacked ? new Uint8Array(shadowPacked.width * shadowPacked.height) : null;
    if (shadowPacked) {
      for (const a of shadowAtlases.values()) copyRows(shadowBytes, shadowPacked.width, a.data, a.width, a.height, shadowPacked.places[a.key].x, shadowPacked.places[a.key].y);
    }
    for (const r of pieces) {
      const lm = r.userData.source.lightmap, colour = atlases.get(lm.colour), directions = atlases.get(lm.directions), place = packed.places[lm.colour];
      if (!colour || !directions || directions.width !== colour.width || directions.height !== colour.height) continue;
      if (!colour.copied) { copyBlocks(colourBytes, packed.width, colour.data, colour.width, colour.height, place.x, place.y); colour.copied = true; }
      if (!directions.copied?.[lm.colour]) {
        copyBlocks(directionBytes, packed.width, directions.data, directions.width, directions.height, place.x, place.y);
        directions.copied = { ...(directions.copied ?? {}), [lm.colour]: true };
      }
      const dark = Boolean(r.userData.source.sunIrrelevant);
      const sun = fieldOf(r), sunAtlas = shadowPacked && sun ? shadowAtlases.get(sun.texture) : null;
      const shadow = sunAtlas ? { record: sun, atlas: sunAtlas, place: shadowPacked.places[sun.texture] } : null;
      for (const part of r.userData.parts ?? []) {
        if (ownGeometry(part, lm, colour, place, shadow, dark)) { parts.push(part); if (shadow) shadows++; if (dark) darks++; }
      }
    }
    bakedShared.bakedColour.value = texture(colourBytes, packed.width, packed.height);
    bakedShared.bakedDirections.value = texture(directionBytes, packed.width, packed.height);
    if (shadowPacked) {
      const map = new THREE.DataTexture(shadowBytes, shadowPacked.width, shadowPacked.height, THREE.RedFormat, THREE.UnsignedByteType);
      map.minFilter = map.magFilter = THREE.LinearFilter;
      map.wrapS = map.wrapT = THREE.ClampToEdgeWrapping;
      map.flipY = false; map.generateMipmaps = false; map.needsUpdate = true;
      bakedShared.bakedShadowMap.value = map;
    }
    bakedShared.bakedShadowShape.value.set(SHADOW_SHAPE.sharpness, SHADOW_SHAPE.exponent);
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
    parts = []; packed = null; shadowPacked = null; shadows = 0; darks = 0; why = null; loading = null;
    bakedShared.bakedOn.value = 0;
    for (const name of ['bakedColour', 'bakedDirections', 'bakedShadowMap']) { bakedShared[name].value?.dispose(); bakedShared[name].value = null; }
  }
  /** The baked light on or off while loaded (the perf probe's and the checks' comparison: only its uniform changes). */
  function set(on) { bakedShared.bakedOn.value = on && parts.length ? 1 : 0; }
  /** What the checks and the perf probe read. */
  const state = () => ({ on: Boolean(bakedShared.bakedOn.value), parts: parts.length, atlas: packed ? [packed.width, packed.height] : null,
                         shadows, sunless: darks, shadowAtlas: shadowPacked ? [shadowPacked.width, shadowPacked.height] : null,
                         sunShadows: Boolean(bakedShared.bakedSunOn.value), why });
  /** The sun's baked shadows standing for the sun or not (the project's sun turned: the live shadow map everywhere). */
  function setSunShadows(on) { bakedShared.bakedSunOn.value = on ? 1 : 0; }
  return { load, reset, set, setSunShadows, state };
}
