// The pieces and effects of other maps read as templates (refactor stage P8; library.js is the Add panel's All maps,
// tools/viewer/library.py the server's side). A piece of another map is read on first use: its meshes, materials and
// textures join the page's tables under their own keys, and its components become templates a copy is made of, as
// the map's own pieces are. Here:
// - an asset's url (assetUrl), whether a target is another map's (isForeignTarget) and a piece's record id (recordId);
// - many pieces' records read in a few requests (readLibraryRecords) and one piece's template (libraryTemplate), with
//   its collision, its area lights and its assembly; an effect's, sound's or lens flare's template (effectTemplate,
//   readEffectRecords); the templates a project's or a prefab's added records name (loadForeignTemplates);
// - what a piece of another map costs and says (foreignCount, kilobytes, foreignCost, foreignNote, bakeNote).
//
// createLibraryTemplates takes what it needs of app.js as one argument object, when app.js makes it: a piece's root
// built and its bounds, the Lights view's and the Effects view's sources, the cover blocks' collision meshes, the
// assemblies of other maps and the helpers. Its own state is inside it (the records and effects read ahead); the
// records read, the templates made, the effects and the maps' hashes, and the cache's prefix, are editor_state.js's.
import * as THREE from 'three';
import { cachePrefix, data, donorHashes, effectTemplates, foreignEffects, foreignTemplates, library, libraryRecords,
         lineCollision, roots, setLineCollision } from './editor_state.js';
import { actorMatrix } from './gizmo.js';
import { valuesOf } from './lights_view.js';
import { api as prefabApi } from './prefabs.js';
import { targetKey } from './project.js';

export function createLibraryTemplates({ boundsOf, buildRoot, collisionMesh, effectSource, foreignAssemblies, fromOf,
                                         lightSource, plural, short }) {
  // Pieces of other maps (library.js, tools/viewer/library.py). A piece's record, read on first use, joins the page's
  // tables: its meshes, materials and textures under their own keys (lib-<map>-…, with the folder they are served
  // from), and its components as templates a copy is made of, as the map's own pieces are. A template names its home
  // map (`foreign`), and so does every copy of it; an added record's `from` is the piece in that map.
  // (foreignTemplates, and the records read, libraryRecords: editor_state.js)
  const assetUrl = url => (url.startsWith('/') ? url : cachePrefix + url);
  const isForeignTarget = t => typeof t?.package === 'string' && t.level === 'base' && Boolean(data?.name) && t.package.toLowerCase() !== data.name.toLowerCase();
  // Many pieces' records read in a few requests (a prefab's or a project's opening), kept for libraryTemplate, which
  // then asks the server for none of them. step(done, total) as the chunks arrive. A piece the server could not give
  // is left for libraryTemplate's own request, which says why.
  const RECORD_CHUNK = 100, fetchedRecords = new Map();
  const recordId = source => `${source.package}|${short(source.actor)}`.toLowerCase();
  async function readLibraryRecords(sources, step = null) {
    const want = [...new Map(sources.map(s => [recordId(s), s])).entries()].filter(([id]) => !libraryRecords.has(id) && !fetchedRecords.has(id));
    for (let k = 0; k < want.length; k += RECORD_CHUNK) {
      const chunk = want.slice(k, k + RECORD_CHUNK);
      step?.(k, want.length);
      try {
        const answer = await prefabApi.records(chunk.map(([, s]) => ({ package: s.package, level: 'base', actor: short(s.actor) })));
        answer.pieces.forEach((p, i) => { if (p.record) fetchedRecords.set(chunk[i][0], p.record); });
      } catch { break; }
    }
    if (want.length) step?.(want.length, want.length);
    return want.length;
  }
  function libraryTemplate(source) {
    const id = recordId(source);
    if (!libraryRecords.has(id)) {
      const promise = (async () => {
        let record = fetchedRecords.get(id);
        fetchedRecords.delete(id);
        if (!record) {
          const response = await fetch(`/library/piece.json?${new URLSearchParams({ package: source.package, level: 'base', actor: short(source.actor) })}`);
          record = await response.json().catch(() => ({}));
          if (!response.ok) throw Error(record.error ?? `the piece could not be read (${response.status})`);
        }
        for (const [k, m] of Object.entries(record.meshes)) data.meshes[k] ??= { ...m, url: record.base + m.url };
        for (const [k, m] of Object.entries(record.materials)) data.materials[k] ??= m;
        for (const [k, t] of Object.entries(record.textures)) data.textures[k] ??= { ...t, url: record.base + t.url };
        lineCollision ?? setLineCollision(new Map());
        for (const [k, c] of Object.entries(record.collision ?? {})) lineCollision.set(k, collisionMesh(c));
        const foreign = { package: record.source.package, key: record.key, buildings: record.buildings ?? [], areaLights: record.areaLights ?? {} };
        if (record.source.sha256) donorHashes.set(record.source.package.toLowerCase(), record.source.sha256);
        // where the piece stands on its home map's tile grid, said on this map's (the compiler does the same): the
        // pose rule's snap then works as for one of the map's own pieces
        const here = data.tileGrid?.origin, shift = record.grid && here?.length === 3 ? here.map((v, k) => v - record.grid[k]) : [0, 0, 0];
        const rebased = o => {
          const matrix = [...o.matrix];
          matrix[12] += shift[0]; matrix[13] += shift[2]; matrix[14] += shift[1];
          return { ...o, matrix, location: o.location.map((v, k) => v + shift[k]) };
        };
        const sources = record.objects.map(o => {
          const source = { ...rebased(o), layer: 'base', floorLocation: o.location, referencedBy: [], foreign };
          const lights = (foreign.areaLights[o.actor]?.lights ?? []).filter(l => l.component === o.component);
          if (!lights.length) return source;
          const inverse = actorMatrix(o.location, o.rotation).invert();
          const foreignAreaLights = lights.map(light => {
            const source = lightSource(light);
            const relative = inverse.clone().multiply(new THREE.Matrix4().fromArray(source.matrix));
            return { root: { userData: { source, values: valuesOf(source) } }, relative };
          });
          return { ...source, foreignAreaLights };
        });
        for (const s of sources) foreignTemplates.set(`${targetKey(fromOf(s))}|${s.component}`, s);
        // an assembly (a car's body, glass and parts; a door's leaf and frame) comes whole: its parts are placed, moved
        // and copied as one, by the link tag an assembly of the map's own has (useMapFamilies)
        if (record.assembly) {
          const a = record.assembly;
          const assembly = { ...a, tag: a.members.length > 1 ? (record.objects.map(o => o.prefab).find(Boolean) ?? short(a.pivot)) : null };
          for (const m of a.members) foreignAssemblies.set(targetKey({ package: record.source.package, level: 'base', actor: m }), assembly);
        }
        // its meshes and materials loaded, as a placed piece's are (the preview and the thumbnail draw from the caches)
        await Promise.all(sources.map(buildRoot));
        const radius = s => data.meshes[s.mesh].bounds?.[6] ?? 0;
        const pivot = sources.find(s => s.actor === record.assembly?.pivot) ?? sources.reduce((a, b) => (radius(b) > radius(a) ? b : a));
        const frame = actorMatrix(pivot.location, pivot.rotation).invert();
        return { sources, pivotIndex: sources.indexOf(pivot), frame, box: boundsOf(sources, frame), record };
      })();
      promise.catch(() => libraryRecords.delete(id));
      libraryRecords.set(id, promise);
    }
    return libraryRecords.get(id);
  }
  // An effect, ambient sound or lens flare of another map (effects and sounds plan, stage FX4; a flare since FX6b): its
  // template read from its map
  // (/library/effect.json: export 28's record, its particle system or waves), kept for the placing and the project's
  // copies (foreignEffects, by its target), its system and waves joined to the map's (the panel, the box, the Wave
  // preview read them by their ids, which name the donor). Gives the record as an effect root's source.
  const fetchedEffects = new Map();     // (effectTemplates, foreignEffects: editor_state.js)
  function effectTemplate(source) {
    const id = recordId(source);
    if (!effectTemplates.has(id)) {
      const promise = (async () => {
        let t = fetchedEffects.get(id);
        fetchedEffects.delete(id);
        if (!t) {
          const response = await fetch(`/library/effect.json?${new URLSearchParams({ package: source.package, level: 'base', actor: short(source.actor) })}`);
          t = await response.json().catch(() => ({}));
          if (!response.ok) throw Error(t.error ?? `it could not be read (${response.status})`);
        }
        data.effectSystems ??= {}; data.soundWaves ??= {};
        for (const [k, v] of Object.entries(t.systems ?? {})) data.effectSystems[k] ??= v;
        for (const [k, v] of Object.entries(t.waves ?? {})) data.soundWaves[k] ??= v;
        // what its likeness is drawn from (export 29): the donor's textures, meshes and materials, by their own keys
        if (t.draw) {
          for (const [k, m] of Object.entries(t.draw.meshes ?? {})) data.meshes[k] ??= { ...m, url: t.draw.base + m.url };
          for (const [k, m] of Object.entries(t.draw.materials ?? {})) data.materials[k] ??= m;
          for (const [k, x] of Object.entries(t.draw.textures ?? {})) data.textures[k] ??= { ...x, url: t.draw.base + x.url };
        }
        if (t.source.sha256) donorHashes.set(t.source.package.toLowerCase(), t.source.sha256);
        const out = effectSource({ ...t.record, foreign: { package: t.source.package, key: t.key } });
        foreignEffects.set(targetKey({ package: out.sourcePackage, level: 'base', actor: out.actor }), out);
        return out;
      })();
      promise.catch(() => effectTemplates.delete(id));
      effectTemplates.set(id, promise);
    }
    return effectTemplates.get(id);
  }
  // Many effects' templates in a few requests (a project's opening), kept for effectTemplate
  async function readEffectRecords(sources) {
    for (let k = 0; k < sources.length; k += RECORD_CHUNK) {
      const chunk = sources.slice(k, k + RECORD_CHUNK);
      try {
        const response = await fetch('/library/effects.json', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sources: chunk.map(s => ({ package: s.package, level: 'base', actor: short(s.actor) })) }) });
        if (!response.ok) break;
        const answer = await response.json();
        answer.effects.forEach((r, i) => { if (r.record) fetchedEffects.set(recordId(chunk[i]), r.record); });
      } catch { break; }
    }
  }
  // The templates of the foreign pieces, effects and sounds some added records name, read before the records are
  // applied. Gives what could not be had, as sentences.
  async function loadForeignTemplates(added, progress = null) {
    const wanted = new Map(), effects = new Map(), failed = [];
    for (const e of added) if (!e.template && isForeignTarget(e.from)) (e.kind ? effects : wanted).set(targetKey(e.from), e.from);
    const list = [...wanted.values()], effectList = [...effects.values()];
    if (list.length > 1) await readLibraryRecords(list, (done, total) => progress?.('reading', done, total));
    if (effectList.length > 1) await readEffectRecords(effectList);
    let made = 0;
    await Promise.all([...list.map(from => libraryTemplate(from)
      .catch(error => failed.push(`${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`))
      .finally(() => progress?.('loading', ++made, list.length))),
      ...effectList.map(from => effectTemplate(from)
        .catch(error => failed.push(`${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`)))]);
    return failed;
  }
  const foreignCount = () => new Set([...roots.values()].map(r => r.userData.source).filter(o => o.added && o.foreign).map(o => o.actor)).size;
  const kilobytes = bytes => (bytes >= 1 << 20 ? `${(bytes / (1 << 20)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
  function foreignCost(obj) {
    const entry = library?.entry(obj.foreign.key);
    return entry?.closure ? `By the Build, from ${obj.foreign.package}: up to ${kilobytes(entry.closure.bytes)} more in the map` : null;
  }
  const foreignNote = obj => `A piece of ${obj.foreign.package}, not of this map. The Build copies it into the map with the meshes, materials and `
    + 'textures it needs. A build with Bake the lighting lights it for where it stands (EXP-38); without, it keeps the '
    + 'light it has in its home map, so it can look too dark or too bright here.';
  // What Build's panel says of a project with pieces of other maps: what baking does for them.
  const bakeNote = () => (foreignCount() ? `${plural(foreignCount(), 'piece')} from other maps: baked, ${foreignCount() === 1 ? 'it is' : 'they are'} lit for `
    + `where ${foreignCount() === 1 ? 'it stands' : 'they stand'}; unbaked, ${foreignCount() === 1 ? 'it keeps' : 'they keep'} the light of the map ${foreignCount() === 1 ? 'it comes' : 'they come'} from.` : null);

  return { assetUrl, bakeNote, effectTemplate, foreignCost, foreignNote, isForeignTarget, libraryTemplate,
           loadForeignTemplates, readEffectRecords, readLibraryRecords, recordId };
}
