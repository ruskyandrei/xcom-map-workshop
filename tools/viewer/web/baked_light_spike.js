// Stage B0's spike of the game-likeness plan: the map's baked light drawn as the game's shader draws it, to measure
// the bar before B2 is built. Throwaway, off unless the page's address asks for it (?baked=on; ?baked=sum draws the
// three direction values summed, as the baker's relight.flat_light does, for the direction scale's check). B2's
// baked_light.js replaces it.
//
// It reads what audit_baked_light.py's spike-export wrote into the map's export (baked-light.json: each lightmapped
// piece's two atlases, their scales, its UV scale and bias and channel; the atlases as DDS files) and gives each
// lightmapped piece's parts a material of their own (the shared one cloned: the program stays shared, the atlases and
// scales are its uniforms), which the Game look draws in place of the shared one. The formula is in the lights'
// patch (lighting.js, USE_BAKED): the lightmap in place of the sky light (which on every map lights only the
// Gameplay_1 channel, not a static piece), the map's static and area lights left out of such a piece (they are in its
// lightmap, or taken to light only what moves), the sun and the other lights live.
import * as THREE from 'three';
import { ask } from './api.js';

export const bakedAsked = new URLSearchParams(globalThis.location?.search ?? '').get('baked');

export function createBakedSpike({ cachePrefix, data, refresh, roots, texture }) {
  const weight = { value: bakedAsked === 'sum' ? 3 : 1 };
  const sky = { value: 0 };    // 1 where the map's sky light lights static pieces (none of the game's maps)
  const parts = [];            // [{ part, plain, baked }]
  let on = false, records = null;

  // a part's own material: the shared one's clone, its patch kept, with the piece's atlases and scales
  function bakedMaterial(base, record, maps, programNormal) {
    const uniforms = {
      bakedColour: { value: maps[0] }, bakedDirections: { value: maps[1] }, bakedWeight: weight, bakedSky: sky,
      bakedScale0: { value: new THREE.Vector4(...record.scale0, 0) },
      bakedScale1: { value: new THREE.Vector4(...record.scale1, 0) },
      bakedUvScaleBias: { value: new THREE.Vector4(...record.uvScale, ...record.uvBias) },
    };
    const inner = base.onBeforeCompile, key = `${base.customProgramCacheKey()}|baked`;
    const defines = { ...(base.defines ?? {}), USE_BAKED: '', ...(programNormal ? { BAKED_PROGRAM_NORMAL: '' } : {}) };
    const setUp = mat => {
      mat.onBeforeCompile = (shader, renderer) => { inner?.call(mat, shader, renderer); Object.assign(shader.uniforms, uniforms); };
      mat.customProgramCacheKey = () => key;
      mat.defines = { ...defines };
      // a clone (the cutaway's) keeps the piece's light
      mat.clone = function clone() { const copy = new this.constructor().copy(this); setUp(copy); return copy; };
      for (const name of ['programTextures', 'programReads']) {
        if (base.userData[name]) Object.defineProperty(mat.userData, name, { value: base.userData[name], enumerable: false, configurable: true });
      }
      mat.needsUpdate = true;
      return mat;
    };
    return setUp(base.clone());
  }

  async function load() {
    records = await ask(`${cachePrefix}baked-light.json`);
    if (!records) { console.warn('baked light spike: no baked-light.json in this export (audit_baked_light.py spike-export)'); return; }
    sky.value = records.skyOnStatic ? 1 : 0;
    Object.assign(data.textures, records.textures);
    for (const root of roots.values()) {
      const record = records.objects[root.userData.source.id];
      if (!record) continue;
      const maps = await Promise.all([texture(record.colour, true), texture(record.directions, true)]);
      if (maps.some(m => !m)) continue;
      for (const m of maps) { m.wrapS = m.wrapT = THREE.ClampToEdgeWrapping; m.needsUpdate = true; }
      for (const part of root.userData.parts) {
        const plain = part.userData.baseMaterial, geometry = part.geometry;
        const channel = geometry.attributes[record.channel ? `uv${record.channel}` : 'uv'];
        if (!plain?.isMeshPhongMaterial || !channel || plain.transparent) continue;
        // the lightmap's UVs under a name of their own (the same buffer): a program may read the same channel
        if (!geometry.attributes.bakedUv) geometry.setAttribute('bakedUv', channel);
        const programNormal = Boolean(plain.defines?.PROGRAM_NORMAL);
        parts.push({ part, plain, baked: bakedMaterial(plain, record, maps, programNormal) });
      }
    }
    console.info(`baked light spike: ${parts.length} parts of ${Object.keys(records.objects).length} lightmapped pieces, weight ${weight.value}`);
  }

  /** The baked light on (the Game look) or off; the cutaway, run after, cuts from the material put here. While on,
   *  the parts of one shared material are drawn one after another (renderOrder, between the sky dome and the rest):
   *  three sorts by material, and with a material a part it would switch program at nearly every draw (about half a
   *  millisecond of URB_Bar's frame, measured in B0). */
  function set(want) {
    want = Boolean(want && records);
    if (want === on) return;
    on = want;
    for (const p of parts) {
      const [from, to] = on ? [p.plain, p.baked] : [p.baked, p.plain];
      p.part.userData.baseMaterial = to;
      if (p.part.material === from) p.part.material = to;
      if (on) { p.order = p.part.renderOrder; p.part.renderOrder = -1 + p.plain.id / 1e6; } else p.part.renderOrder = p.order;
    }
    refresh();
  }

  return { load, set, weight, entries: parts, get on() { return on; }, get parts() { return parts.length; } };
}
