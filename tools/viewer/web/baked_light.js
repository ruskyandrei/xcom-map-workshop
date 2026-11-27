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
//
// A piece the project edited (stage B4) is lit live, its local lights scaled by the map's factor (baked_rules.js
// liveFactor, worked out as the lightmaps load) and no sky light, as the game's static pieces: one of the map's own
// moved or deleted, or relit (its lightmap names a light the project moved, changed or deleted: lights_wiring.js
// relitPieces), keeps its geometry with its mark set to 4; every added piece (a copy, a made piece, another map's)
// gets a geometry of its own with that mark. refresh() sets them after each edit (the edit hub, app.js).
//
// The project's last baked Build (B4, its second half: build_light.js gives it, setBuild) lights each piece that is as
// it built it from its own lightmaps: its atlases are packed with the map's, an atlas it wrote again (a relit one, the
// map's texture of the same name) in the map's place, and a piece as built is marked 5 to 7 (4 more than 1 to 3: the
// lights the Build baked are left out of it, lighting.js). An original the Build left where the map has it keeps its
// geometry, with the Build's record where it relit it; a moved original's copy and an added piece get a geometry of the
// Build's record (refresh's `built`).
import * as THREE from 'three';
import { bakedShared } from './lighting.js';
import { SHADOW_SHAPE, bakedLightAt, copyBlocks, copyRows, dxt1Texel, liveFactor, liveLightAt, luminance, packAtlases,
         packedBytes, packedUvs, scaleValues, srgbToLinear } from './baked_rules.js';
import { canTake, readDds } from './texture_file.js';

/** Off where the page's address says ?baked=off (the checks and the perf probe compare); ?baked=sum draws the three
 *  direction values summed, as the baker's flat_light does (F-181's check). */
export const bakedAsked = new URLSearchParams(globalThis.location?.search ?? '').get('baked');

export function createBakedLight({ data, roots, assetUrl, hasExtension }) {
  let loading = null, parts = [], packed = null, shadowPacked = null, shadows = 0, darks = 0, why = null;
  // B4: the lightmapped pieces with their parts, the parts given a geometry of their own since (added pieces' live
  // ones, the Build's), how many are lit live, the factor (null: too few samples, 1 used) and its samples
  let entries = [], touched = new Set(), liveNow = 0, factor = null, samples = 0;
  // B4: the project's last baked Build's light (setBuild: its pieces' records by built component, its textures, where
  // its files are served, and the map's textures it wrote again by key), its records placed in the packed atlases, and
  // how many pieces it lights now (with a record of its own)
  let build = null, builtPlaced = new Map(), builtLit = 0, builtOwn = 0;
  const LIVE = 4, BUILT = 4, FACTOR_RANGE = [0.25, 4];

  const lightmapped = () => [...roots.values()].filter(r => r.userData.source?.lightmap && !r.userData.source.added);

  // the places a texture's file may be read from, each [its record, its address], the first that answers taken: a
  // Build's own (build-<n>) from the Build's folder; one of the map's from the Build's where the Build wrote it again
  // (its relit atlas, by the same name), then from the map's
  function sources(key) {
    const out = [], own = build?.textures[key], again = build?.again.get(key), map = data.textures[key];
    if (own) out.push([own, build.base + own.url]);
    if (again) out.push([build.textures[again], build.base + build.textures[again].url]);
    if (map) out.push([map, assetUrl(map.url)]);
    return out;
  }
  async function answer(key, fits = () => true) {
    let failure = new Error(`texture ${key} is not in the export`);
    for (const [record, url] of sources(key).filter(([record]) => fits(record))) {
      try {
        const response = await fetch(url);
        if (response.ok) return response;
        failure = new Error(`texture ${key}: ${response.status}`);
      } catch (error) { failure = error; }
    }
    throw failure;
  }
  // the key a Build's record names a texture by, as the packing knows it: the map's own where the Build wrote it again
  const keyOf = key => build?.sameAs.get(key) ?? key;
  // (a Build's own texture that can't be read leaves its pieces live; one of the map's stops the baked light)
  const spare = (key, error) => { if (!build?.textures[key]) throw error; console.warn(`the Build's light: ${error.message}`); return null; };

  async function atlas(key) {
    const response = await answer(key, r => r.container === 'dds' && r.format === 'PF_DXT1');
    const file = readDds(await response.arrayBuffer());
    return { key, width: file.width, height: file.height, data: file.mipmaps[0].data };
  }

  // a shadow map's atlas (a PNG of its one channel), its red values
  async function shadowAtlas(key) {
    const response = await answer(key);
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

  // A geometry of a part's own with a lightmap: the shared geometry's attributes, its UVs moved into the packed atlases
  // (the lightmap's and its sun shadow map's) and its scales with its mark (1: a lightmap, 2: and a shadow map of the
  // sun, 3: and no sun at all; `offset` more for a Build's: BUILT). Null where the mesh lacks the lightmap's channel.
  function litGeometry(shared, { lm, colour, place, shadow, dark }, offset = 0) {
    const channel = shared.attributes[lm.channel ? `uv${lm.channel}` : 'uv'];
    if (!channel || channel.itemSize !== 2) return null;
    const geometry = new THREE.BufferGeometry();
    for (const [name, attribute] of Object.entries(shared.attributes)) geometry.setAttribute(name, attribute);
    geometry.setIndex(shared.index);
    for (const g of shared.groups) geometry.addGroup(g.start, g.count, g.materialIndex);
    geometry.boundingBox = shared.boundingBox; geometry.boundingSphere = shared.boundingSphere;
    geometry.morphAttributes = shared.morphAttributes;
    const uv = channel.array instanceof Float32Array && !channel.isInterleavedBufferAttribute ? channel.array
      : Float32Array.from({ length: channel.count * 2 }, (_, i) => (i % 2 ? channel.getY(i >> 1) : channel.getX(i >> 1)));
    const mark = (dark ? 3 : shadow ? 2 : 1) + offset;
    const at = packedUvs(uv, lm, colour, place, packed);
    const sh = shadow ? packedUvs(uv, shadow.record, shadow.atlas, shadow.place, shadowPacked) : null;
    const uvs = new Float32Array(channel.count * 4), scales = scaleValues(lm, channel.count), both = new Float32Array(channel.count * 7);
    for (let i = 0; i < channel.count; i++) {
      uvs[i * 4] = at[i * 3]; uvs[i * 4 + 1] = at[i * 3 + 1];
      if (sh) { uvs[i * 4 + 2] = sh[i * 3]; uvs[i * 4 + 3] = sh[i * 3 + 1]; }
      both.set(scales.subarray(i * 6, i * 6 + 3), i * 7); both[i * 7 + 3] = mark;
      both.set(scales.subarray(i * 6 + 3, i * 6 + 6), i * 7 + 4);
    }
    geometry.setAttribute('bakedUv', new THREE.BufferAttribute(uvs, 4));
    const interleaved = new THREE.InterleavedBuffer(both, 7);
    geometry.setAttribute('bakedScale0', new THREE.InterleavedBufferAttribute(interleaved, 4, 0));
    geometry.setAttribute('bakedScale1', new THREE.InterleavedBufferAttribute(interleaved, 3, 4));
    return { geometry, interleaved, mark };
  }
  // each lightmapped part's geometry of its own from the map's record
  function ownGeometry(part, lit) {
    const shared = part.userData.bakedFrom ?? part.geometry, made = litGeometry(shared, lit);
    if (!made) return false;
    part.userData.bakedFrom = shared;
    part.userData.bakedOwn = made.geometry;
    part.userData.bakedMark = part.userData.bakedNow = made.mark;
    part.userData.bakedScales = made.interleaved;
    part.geometry = made.geometry;
    return true;
  }
  // a part's mark set (its own lightmap's, the Build's on the same record, or LIVE), every vertex
  function setMark(part, mark) {
    const scales = part.userData.bakedScales;
    for (let i = 3; i < scales.array.length; i += 7) scales.array[i] = mark;
    scales.needsUpdate = true;
    part.userData.bakedNow = mark;
  }
  // an added piece's part: a geometry of its own, the attributes of the one it has, its mark LIVE
  function liveGeometry(part) {
    const shared = part.userData.bakedFrom, count = shared.attributes.position?.count ?? 0;
    if (!count) return null;
    const geometry = new THREE.BufferGeometry();
    for (const [name, attribute] of Object.entries(shared.attributes)) geometry.setAttribute(name, attribute);
    geometry.setIndex(shared.index);
    for (const g of shared.groups) geometry.addGroup(g.start, g.count, g.materialIndex);
    geometry.boundingBox = shared.boundingBox; geometry.boundingSphere = shared.boundingSphere;
    geometry.morphAttributes = shared.morphAttributes;
    const marks = new Float32Array(count * 4);
    for (let i = 3; i < marks.length; i += 4) marks[i] = LIVE;
    geometry.setAttribute('bakedUv', new THREE.BufferAttribute(new Float32Array(count * 4), 4));
    geometry.setAttribute('bakedScale0', new THREE.BufferAttribute(marks, 4));
    geometry.setAttribute('bakedScale1', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    part.userData.bakedOwn = geometry;
    return geometry;
  }
  // a part's geometry of a Build's record (`placed`), made once for that record and kept while it stands
  function builtGeometry(part, placed) {
    if (part.userData.bakedBuilt?.placed !== placed) {
      const made = litGeometry(part.userData.bakedFrom, placed, BUILT);
      part.userData.bakedBuilt = made ? { placed, geometry: made.geometry } : null;
    }
    return part.userData.bakedBuilt?.geometry ?? null;
  }
  // a part's drawn geometry: the shared one it was given anew since (a made piece drawn again) taken as its source
  function use(part, geometry) {
    touched.add(part);
    if (part.geometry !== geometry) part.geometry = geometry;
  }
  function freshSource(part) {
    const now = part.geometry;
    if (part.userData.bakedFrom && (now === part.userData.bakedOwn || now === part.userData.bakedBuilt?.geometry)) return;
    part.userData.bakedFrom = now;
    part.userData.bakedOwn = part.userData.bakedBuilt = null;
  }

  // the baked light against the live lights at some of a lightmapped part's vertices (B4's factor): [baked, live] each,
  // in luminance, the baked at the texel of its lightmap there for a flat normal
  function sampleLight(part, record, colour, directions, lights, out, most = 12) {
    const geometry = part.userData.bakedFrom, position = geometry.attributes.position, normal = geometry.attributes.normal;
    const uv = geometry.attributes[record.channel ? `uv${record.channel}` : 'uv'];
    if (!position || !normal || !uv) return;
    part.updateWorldMatrix(true, false);
    const matrix = part.matrixWorld, normals = new THREE.Matrix3().getNormalMatrix(matrix);
    const p = new THREE.Vector3(), n = new THREE.Vector3(), step = Math.max(1, Math.floor(position.count / most));
    const texel = (atlas, u, v) => dxt1Texel(atlas.data, atlas.width, Math.min(atlas.width - 1, Math.max(0, Math.floor(u * atlas.width))),
                                             Math.min(atlas.height - 1, Math.max(0, Math.floor(v * atlas.height)))).map(srgbToLinear);
    for (let i = 0; i < position.count; i += step) {
      p.fromBufferAttribute(position, i).applyMatrix4(matrix);
      n.fromBufferAttribute(normal, i).applyMatrix3(normals).normalize();
      const u = uv.getX(i) * record.uvScale[0] + record.uvBias[0], v = uv.getY(i) * record.uvScale[1] + record.uvBias[1];
      const baked = bakedLightAt(texel(colour, u, v), texel(directions, u, v), record.scale0, record.scale1);
      // (the view's axes are the game's x, z, y)
      out.push([luminance(baked), luminance(liveLightAt([p.x, p.z, p.y], [n.x, n.z, n.y], lights))]);
    }
  }

  async function loadNow() {
    const pieces = lightmapped();
    // what is lit from a lightmap: the map's pieces' records, and the Build's (its keys as the packing knows them)
    const fieldOf = (sun, irrelevant) => (sun && !sun.factor && !irrelevant ? sun : null);
    const mapLit = pieces.map(r => ({ root: r, lm: r.userData.source.lightmap, sun: fieldOf(r.userData.source.sunShadow, r.userData.source.sunIrrelevant),
                                       dark: Boolean(r.userData.source.sunIrrelevant) }));
    const buildLit = Object.entries(build?.pieces ?? {}).filter(([, b]) => b.lightmap).map(([component, b]) => ({
      component, lm: { ...b.lightmap, colour: keyOf(b.lightmap.colour), directions: keyOf(b.lightmap.directions) },
      sun: fieldOf(b.sunShadow && { ...b.sunShadow, texture: keyOf(b.sunShadow.texture) }, b.sunIrrelevant), dark: Boolean(b.sunIrrelevant) }));
    const all = [...mapLit, ...buildLit];
    if (!pieces.length) { why = 'this export has no lightmaps (export 44 or newer has them)'; return; }
    if (!canTake('DXT1', true, hasExtension)) { why = 'this GPU can\'t read the lightmaps\' compressed atlases'; return; }
    const keys = [...new Set(all.flatMap(x => [x.lm.colour, x.lm.directions]))];
    const atlases = new Map((await Promise.all(keys.map(k => atlas(k).catch(error => spare(k, error))))).filter(Boolean).map(a => [a.key, a]));
    // the colour atlases and the direction atlases each packed the same way (a piece's two are the same size)
    const colours = [...new Set(all.map(x => x.lm.colour))].map(k => atlases.get(k)).filter(Boolean);
    packed = packAtlases(colours.map(a => ({ key: a.key, width: a.width, height: a.height })));
    if (!packed) { why = 'the map\'s lightmaps don\'t fit in one atlas'; return; }
    const colourBytes = packedBytes(packed.width, packed.height), directionBytes = packedBytes(packed.width, packed.height);
    // the sun's shadow maps of the lightmapped pieces, packed into one single-channel atlas (a failure keeps the live shadow)
    const shadowKeys = [...new Set(all.filter(x => x.sun).map(x => x.sun.texture))];
    const shadowAtlases = new Map();
    try {
      for (const a of await Promise.all(shadowKeys.map(k => shadowAtlas(k).catch(error => spare(k, error))))) if (a) shadowAtlases.set(a.key, a);
      shadowPacked = shadowAtlases.size ? packAtlases([...shadowAtlases.values()].map(a => ({ key: a.key, width: a.width, height: a.height }))) : null;
    } catch (error) { shadowPacked = null; console.warn(`the sun's baked shadows: ${error.message}`); }
    const shadowBytes = shadowPacked ? new Uint8Array(shadowPacked.width * shadowPacked.height) : null;
    if (shadowPacked) {
      for (const a of shadowAtlases.values()) copyRows(shadowBytes, shadowPacked.width, a.data, a.width, a.height, shadowPacked.places[a.key].x, shadowPacked.places[a.key].y);
    }
    // each record's atlases copied where the packing put them, and what a part's geometry is made from
    const placed = x => {
      const colour = atlases.get(x.lm.colour), directions = atlases.get(x.lm.directions), place = packed.places[x.lm.colour];
      if (!colour || !directions || directions.width !== colour.width || directions.height !== colour.height) return null;
      if (!colour.copied) { copyBlocks(colourBytes, packed.width, colour.data, colour.width, colour.height, place.x, place.y); colour.copied = true; }
      if (!directions.copied?.[x.lm.colour]) {
        copyBlocks(directionBytes, packed.width, directions.data, directions.width, directions.height, place.x, place.y);
        directions.copied = { ...(directions.copied ?? {}), [x.lm.colour]: true };
      }
      const sunAtlas = shadowPacked && x.sun ? shadowAtlases.get(x.sun.texture) : null;
      return { lm: x.lm, colour, directions, place, dark: x.dark,
               shadow: sunAtlas ? { record: x.sun, atlas: sunAtlas, place: shadowPacked.places[x.sun.texture] } : null };
    };
    for (const x of mapLit) {
      const lit = placed(x);
      if (!lit) continue;
      const own = [];
      for (const part of x.root.userData.parts ?? []) {
        if (ownGeometry(part, lit)) { parts.push(part); own.push(part); if (lit.shadow) shadows++; if (lit.dark) darks++; }
      }
      if (own.length) entries.push({ root: x.root, parts: own, record: x.lm, colour: lit.colour, directions: lit.directions });
    }
    builtPlaced = new Map();
    for (const x of buildLit) { const lit = placed(x); if (lit) builtPlaced.set(x.component, lit); }
    // B4's factor: the lightmaps against the live lights an edited piece takes (its static and area lights); a piece the
    // Build relit by the Build's record, whose scales go with its atlas's texels as the Build wrote them
    const lights = (data.lights ?? []).filter(l => l.enabled && (l.kind === 'point' || l.kind === 'spot') && l.radius > 0
                                                && (l.role === 'static' || l.role === 'area'));
    const pairs = [];
    for (const e of entries) {
      const own = builtPlaced.get(e.root.userData.source.component) ?? { lm: e.record, colour: e.colour, directions: e.directions };
      for (const part of e.parts) sampleLight(part, own.lm, own.colour, own.directions, lights, pairs);
    }
    factor = liveFactor(pairs);
    samples = pairs.filter(([, live]) => live > 1e-3).length;
    bakedShared.bakedLiveFactor.value = factor === null ? 1 : Math.min(FACTOR_RANGE[1], Math.max(FACTOR_RANGE[0], factor));
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
  /** After an edit (the edit hub's edit and scene runs, app.js), with build_light.js's plan: `live`, the ids of the
   *  pieces lit live (the map's relit, or changed since the Build); `built`, null without a Build, else the pieces as
   *  the Build built them, id -> the built component whose record lights them (null: an original the Build left where
   *  the map has it, by its own record unless the Build relit it). The map's own pieces moved or deleted, and those
   *  `live` names, are lit live, the others by their lightmaps (the Build's, as built); an added piece by the Build's
   *  record as built, else live. */
  function refresh({ live = new Set(), built = null } = {}) {
    if (!packed) return;
    liveNow = 0; builtLit = 0; builtOwn = 0;
    for (const e of entries) {
      const id = e.root.userData.source.id, copy = built?.get(id) ?? null, asBuilt = built?.has(id) ?? false;
      const placed = asBuilt ? builtPlaced.get(copy ?? e.root.userData.source.component) : null;
      // (lit live: one moved or deleted, or relit, or changed since the Build; a moved original's copy with no record
      // of the Build's is lit live too, its own lightmap being for where the map has it)
      const lit = asBuilt ? Boolean(copy && !placed) : Boolean(live.has(id) || e.root.userData.edit || e.root.userData.deleted);
      let own = false;
      for (const part of e.parts) {
        // (a geometry another area gave the part since, a broken piece's without its knocked-out fragments, made from
        // its own and so with its marks, is left as it is)
        const mine = part.geometry === part.userData.bakedOwn || part.geometry === part.userData.bakedBuilt?.geometry;
        const geometry = placed && mine ? builtGeometry(part, placed) : null;
        if (geometry) { use(part, geometry); own = true; continue; }
        if (mine && part.geometry !== part.userData.bakedOwn) part.geometry = part.userData.bakedOwn;
        const mark = lit || copy ? LIVE : part.userData.bakedMark + (asBuilt ? BUILT : 0);
        if (part.userData.bakedNow !== mark) setMark(part, mark);
      }
      if (lit) liveNow++;
      else if (asBuilt) { builtLit++; if (own) builtOwn++; }
    }
    for (const root of roots.values()) {
      if (!root.userData.source?.added || root.userData.deleted) continue;
      const placed = built?.has(root.userData.source.id) ? builtPlaced.get(built.get(root.userData.source.id)) : null;
      let drawn = false;
      for (const part of root.userData.parts ?? []) {
        freshSource(part);
        const geometry = (placed && builtGeometry(part, placed)) || part.userData.bakedOwn || liveGeometry(part);
        if (geometry) use(part, geometry);
        drawn ||= Boolean(placed && geometry === part.userData.bakedBuilt?.geometry);
      }
      if (drawn) { builtLit++; builtOwn++; } else liveNow++;
    }
  }
  /** Nothing loaded, the light off; every part back on its shared geometry. */
  function unload() {
    for (const part of [...parts, ...touched]) {
      if (part.userData.bakedFrom) part.geometry = part.userData.bakedFrom;
      for (const key of ['bakedFrom', 'bakedOwn', 'bakedMark', 'bakedNow', 'bakedScales', 'bakedBuilt']) delete part.userData[key];
    }
    entries = []; touched = new Set(); liveNow = 0; factor = null; samples = 0; builtPlaced = new Map(); builtLit = 0; builtOwn = 0;
    bakedShared.bakedLiveFactor.value = 1;
    parts = []; packed = null; shadowPacked = null; shadows = 0; darks = 0; why = null; loading = null;
    bakedShared.bakedOn.value = 0;
    for (const name of ['bakedColour', 'bakedDirections', 'bakedShadowMap']) { bakedShared[name].value?.dispose(); bakedShared[name].value = null; }
  }
  /** As a map opens: nothing loaded, no Build, the light off. */
  function reset() { unload(); build = null; }
  /** The project's last baked Build's light (build_light.js: the server's answer), or null. Where the lightmaps are
   *  loaded, they are loaded again with its atlases; a promise of whether they were. */
  function setBuild(next) {
    if ((next?.buildId ?? null) === (build?.buildId ?? null)) return Promise.resolve(false);
    if (next) {
      // its atlases the map's own written again (a relit one keeps the map's texture's name), the map's keys for them
      const byName = new Map(Object.entries(next.textures ?? {}).map(([k, t]) => [t.name, k]));
      const again = new Map(), sameAs = new Map();
      for (const [k, t] of Object.entries(data.textures ?? {})) {
        const theirs = /^\d+$/.test(k) && t ? byName.get(t.name) : undefined;
        if (theirs) { again.set(k, theirs); sameAs.set(theirs, k); }
      }
      build = { ...next, textures: next.textures ?? {}, pieces: next.pieces ?? {}, again, sameAs };
    } else build = null;
    if (!loading) return Promise.resolve(false);
    return loading.then(() => { unload(); return load(); });
  }
  /** The baked light on or off while loaded (the perf probe's and the checks' comparison: only its uniform changes). */
  function set(on) { bakedShared.bakedOn.value = on && parts.length ? 1 : 0; }
  /** Whether the lightmaps were asked for (the Game look has been on). */
  const asked = () => loading !== null;
  /** What the checks and the perf probe read. */
  const state = () => ({ on: Boolean(bakedShared.bakedOn.value), parts: parts.length, atlas: packed ? [packed.width, packed.height] : null,
                         shadows, sunless: darks, shadowAtlas: shadowPacked ? [shadowPacked.width, shadowPacked.height] : null,
                         sunShadows: Boolean(bakedShared.bakedSunOn.value), live: liveNow, factor, samples, why,
                         build: build ? { id: build.buildId, records: builtPlaced.size, lit: builtLit, own: builtOwn } : null });
  /** The sun's baked shadows standing for the sun or not (the project's sun turned: the live shadow map everywhere). */
  function setSunShadows(on) { bakedShared.bakedSunOn.value = on ? 1 : 0; }
  return { asked, load, refresh, reset, set, setBuild, setSunShadows, state };
}
