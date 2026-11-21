// Prefabs saved and placed (refactor stage P5; prefab plan 5.6 and 5.7; prefabs.js, tools/viewer/prefabs.py). A prefab
// is what a paste makes, saved: added records in a space of its own (the tile grid), with the groups and buildings
// among them.
// - Saved: the selection (or, in the prefab builder, its whole document) as a prefab's records (prefabRecords), the
//   Save as prefab dialog, the save with its pieces copied to the library first (savePrefab), and its picture drawn
//   from what was saved (drawPrefabPictures, a frame at a time).
// - Placed: a prefab of the Add panel's Prefabs tab read into a clip (prefabClip) and placed as a paste is
//   (choosePrefab), and what a placed clip reaches outside the map's tile grid said (prefabPlacementProblem).
//
// createPrefabPlace takes what it needs of app.js as one argument object, when app.js makes it: the clipboard's,
// the placing's and the snapshot's functions, the readers of other maps' pieces and effects, the busy mark and the
// hints, and the prefab builder's records and save (builder_session.js). Its own state is inside it (the dialog's);
// the Prefabs tab, the donor maps' hashes, the pictures waiting, the clipboard and the other maps' pieces read are
// editor_state.js's.
import * as THREE from 'three';
import { TILE } from './constants.js';
import { COVER_KIND } from './cover.js';
import { builder, builderMode, chooseToken, data, donorHashes, effectIndex, effectTemplates, families, foreignEffects,
         geometryCache, library, libraryRecords, nextChooseToken, pieces, prefabPictures, prefabTab, setClipboard } from './editor_state.js';
import { recordName, savedValues } from './effects_rules.js';
import { SOFT } from './library.js';
import { fromOf, isStream, optionsOf, recordOf, stateOf, stateOfRoot } from './piece_records.js';
import { pieceGrid } from './pieces.js';
import { normalizePrefab } from './prefab_document.js';
import { api as prefabApi, newPrefab, prefabWords } from './prefabs.js';
import { BUILDING_FLOORS_MAX, buildingKey, memberKey, targetKey, tidyBuilding, uuid, validBuilding } from './project.js';
import { plural, short, text } from './dom_words.js';

export function createPrefabPlace({ $, BUSY_PIECES, PL, actorPose, assetUrl, banner, boxMatrix, builderRecords, busy,
                                    busyPaint, busyStart, copyable, coverOf, coverVersion, effectTemplate,
                                    effectViewOnly, flashHint, ghostEdges, ghostLine, gltfLoader, gridNow, groupTree,
                                    isForeignTarget, libraryTemplate, lightPose, lightsBlocked, linkOf, madeShape,
                                    mapChain, matrixBox, memberOf, movedMatrix, nextFrame, physicalBox, previewGroup,
                                    readEffectRecords, readLibraryRecords, recipeLight, recordId, rootName,
                                    saveBuilder, selectionGroup, snapshot, startPlacing, stopPlacing, templateFor,
                                    track, withStorableCone }) {
  function prefabPlacementProblem(clip, delta) {
    if (!builderMode && clip.bounds && data.tileGrid) {
      const b = clip.bounds, box = new THREE.Box3(new THREE.Vector3(b[0], b[2], b[1]), new THREE.Vector3(b[3], b[5], b[4])).applyMatrix4(delta);
      const low = [box.min.x, box.min.z, box.min.y], high = [box.max.x, box.max.z, box.max.y], g = data.tileGrid;
      const over = [0, 1, 2].map(k => Math.max(0, g.origin[k] - low[k], high[k] - (g.origin[k] + g.dimensions[k] * g.size[k])));
      if (over.some(v => v > 0.5)) {
        const words = [over[0] > 0.5 && `${Math.ceil(over[0] / g.size[0])} tile${Math.ceil(over[0] / g.size[0]) === 1 ? '' : 's'} along X`,
                       over[1] > 0.5 && `${Math.ceil(over[1] / g.size[1])} tile${Math.ceil(over[1] / g.size[1]) === 1 ? '' : 's'} along Y`,
                       over[2] > 0.5 && `${Math.ceil(over[2] / g.size[2])} level${Math.ceil(over[2] / g.size[2]) === 1 ? '' : 's'} in height`].filter(Boolean);
        return `${clip.name} reaches ${words.join(' and ')} outside this map's tile grid. Out there the map has no tiles: `
          + 'nothing can be stood on or give cover. Move it in, or make the map larger with Map grid.';
      }
    }
    return null;
  }
  // ---- Prefabs (prefab plan 5.6 and 5.7; prefabs.js, tools/viewer/prefabs.py). A prefab is what a paste makes, saved:
  // added records in a space of its own (the tile grid: the origin a tile corner at ground level), with the groups and
  // buildings among them. Saving a selection writes those records; placing reads them into a clip and pastes it, as one
  // group marked with the prefab (a stamp: nothing ties it to the file afterwards).
  // (the Add panel's Prefabs tab, prefabTab: editor_state.js)
  // (a map's package -> its SHA-256, donorHashes: editor_state.js)
  const gridBase = () => (data?.tileGrid?.origin?.length === 3 ? data.tileGrid.origin : [0, 0, 0]);
  // The selection as a prefab's records: { tiles, pieces, groups, buildings, donors, left (what won't go into it, as
  // sentences), offGrid (the pieces that keep the pose rule and stand off the grid), counts, clip, box }, or null with
  // nothing to save.
  function prefabRecords({ complete = false } = {}) {
    if (complete) return builderRecords();
    const clip = snapshot();
    if (!clip) return null;
    const grid = gridBase(), low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
    const grow = b => { for (let k = 0; k < 3; k++) { low[k] = Math.min(low[k], b[k]); high[k] = Math.max(high[k], b[k + 3]); } };
    const offGrid = [];
    for (const r of copyable()) {
      // (an effect, a sound or a lens flare is where it stands: a sound's reach is no part of the footprint)
      if (r.userData.effect) { const p = actorPose(r.userData.source, r.matrix).location; grow([...p, ...p]); continue; }
      if (r.userData.light) { const p = lightPose(r).location; grow([...p, ...p]); continue; }
      const b = physicalBox(r);
      if (b) grow(b);
      const move = isStream(r.userData.source) ? null : gridNow(r);
      if (move && !move.valid && !offGrid.includes(rootName(r))) offGrid.push(rootName(r));
    }
    for (const v of clip.volumes) grow(matrixBox(v.matrix));
    if (!Number.isFinite(low[0])) return null;
    // Height 0 is the map's grid bottom (prefab plan 5.6b): every tile level keeps its number, so what stood on the
    // map's bottom level stands on the builder's drawn grid, and what lies under the grid goes below 0. Builder ground
    // stays zero.
    const down = (v, o, step) => o + Math.floor((v - o + 0.5) / step) * step;
    const origin = [down(low[0], grid[0], TILE), down(low[1], grid[1], TILE), grid[2]];
    const tiles = [0, 1].map(k => Math.max(1, Math.ceil((high[k] - origin[k]) / TILE - 1e-4)));
    const shift = new THREE.Matrix4().makeTranslation(-origin[0], -origin[2], -origin[1]);
    const pieces = [], left = [], donors = new Map(), names = new Map(), copied = [];
    let n = 0;
    const units = new Map();
    for (const e of clip.entries) {
      if (e.source.isLight) continue;
      if (e.source.isEffect) continue;        // (below, with the lights)
      if (!units.has(e.source.actor)) units.set(e.source.actor, []);
      units.get(e.source.actor).push(e);
    }
    const tags = new Map();
    const donor = from => {
      const hash = from.package.toLowerCase() === data.name.toLowerCase() ? data.source?.sha256 : donorHashes.get(from.package.toLowerCase());
      donors.set(from.package.toLowerCase(), { package: from.package, ...(/^[0-9a-f]{64}$/.test(hash ?? '') ? { sha256: hash } : {}) });
    };
    for (const [actor, list] of units) {
      const s = list[0].source, placed = shift.clone().multiply(list[0].matrix), from = fromOf(s);
      if (s.cover) {
        const name = `${from.actor}_copy${++n}`;
        names.set(actor, name); copied.push([memberOf(s), { added: name }]);
        pieces.push(recordOf({ form: 'cover', actor: name, template: { kind: COVER_KIND, version: coverVersion(s.added?.template?.version, s.cover.type) },
                               cover: s.cover, ...actorPose(s, placed) }, 'prefab'));
        continue;
      }
      if (from.level !== 'base') { left.push(`${short(data.meshes[s.mesh].name)}: a piece of a level the mission streams in, not of a map`); continue; }
      const name = `${from.actor}_copy${++n}`, was = linkOf(list[0]);
      names.set(actor, name); copied.push([memberOf(s), { added: name }]);
      if (was && !tags.has(was)) tags.set(was, `copy${tags.size + 1}:${was.replace(/^copy\d+:/, '')}`);
      const entry = s.foreign?.key ? library?.entry(s.foreign.key) : null;
      // (its tint, flags, a made piece's numbers and a broken copy's blasts, as a project keeps them: its state)
      pieces.push(recordOf({ actor: name, from: { package: from.package, level: from.level, actor: from.actor }, components: list.map(e => e.source.component),
                             ...actorPose(s, placed), prefab: was ? tags.get(was) : null, partner: s.partner,
                             state: list[0].state ?? stateOfRoot({ source: s }), recipe: entry ? { key: entry.key, name: entry.name } : null }, 'prefab'));
      donor(from);
    }
    // (a partner is named by its name in the prefab; one left out is no partner)
    for (const p of pieces) if (p.from) p.partner = names.get(p.partner) ?? null;
    // its effects and sounds (effects and sounds plan, stage FX6a) and its lens flares (FX6b): each a copy of its
    // original, with the values set on it (a flare has none). One its piece carries isn't in the clip: the piece's
    // copy brings it (snapshot)
    let effects = 0, sounds = 0, flares = 0;
    for (const e of clip.entries) {
      if (!e.source.isEffect) continue;
      const s = e.source, kind = s.kind, from = fromOf(s), what = kind === 'sound' ? 'a sound' : kind === 'flare' ? 'a lens flare' : 'an effect';
      if (from.level !== 'base') { left.push(`${recordName(s, data)}: ${what} of a level the mission streams in, not of a map`); continue; }
      const name = `${from.actor}_copy${++n}`, values = kind === 'flare' ? null : savedValues(e.values);
      copied.push([memberOf(s), { added: name }]);
      pieces.push(recordOf({ form: 'effect', actor: name, kind, from: { package: from.package, level: from.level, actor: from.actor },
                             ...actorPose(s, shift.clone().multiply(e.matrix)), values }, 'prefab'));
      donor(from);
      if (kind === 'sound') sounds++; else if (kind === 'flare') flares++; else effects++;
    }
    let lights = 0;
    for (const e of clip.entries) {
      if (!e.source.isLight) continue;
      const kind = e.source.kind, recipe = families?.lightRecipes?.[kind];
      if (!recipe) { left.push(`${short(e.source.actor)}: a ${kind} light, which the editor can't make in another map yet`); continue; }
      const pose = actorPose(e.source, shift.clone().multiply(e.matrix));
      if (kind === 'point') pose.rotation = [0, 0, 0];
      const name = `${PL}${kind === 'point' ? 'PointLight' : 'SpotLight'}_copy${++n}`;
      copied.push([memberOf(e.source), { added: name }]); lights++;
      const value = k => { const v = e.values?.[k] ?? recipe.values[k]; return Array.isArray(v) ? [...v] : v; };
      // (a made light holds only cones in the editor's ranges: a map's stored 100 or 580 goes in as the 89.99 it lights as)
      pieces.push(recordOf({ form: 'light', actor: name, template: { kind, version: recipe.latest }, light: withStorableCone(Object.fromEntries(Object.keys(recipe.values).map(k => [k, value(k)]))), ...pose }, 'prefab'));
    }
    // its buildings: the project's and the map's own selected with the pieces, each a building of the prefab
    const by = new Map();
    for (const v of clip.volumes) {
      if (!by.has(v.building)) by.set(v.building, []);
      by.get(v.building).push({ floor: v.floor, box: matrixBox(shift.clone().multiply(v.matrix)) });
    }
    const buildings = [...by].map(([was, list]) => {
      const numbers = [...new Set(list.map(x => x.floor))].sort((a, b) => a - b).slice(0, BUILDING_FLOORS_MAX), id = uuid();
      copied.push([buildingKey(was), { building: id }]);
      return tidyBuilding({ id, name: clip.buildingMeta[was]?.name ?? '', kind: clip.buildingMeta[was]?.kind ?? 'building',
                            floors: numbers.map(f => ({ boxes: list.filter(x => x.floor === f).map(x => x.box) })) });
    });
    const groups = [...groupTree(copied, mapChain).values()].map(g => ({ id: g.id, breakTogether: g.breakTogether === true, members: [...g.members.values()] }));
    const normalized = normalizePrefab({ pieces, groups, buildings }, [['Selection', [...low, ...high].map((v, k) => v - origin[k % 3])]]);
    return { ...normalized, groups, donors: [...donors.values()].sort((a, b) => a.package.localeCompare(b.package)), left, offGrid, clip,
      counts: { pieces: pieces.length - lights - effects - sounds - flares, lights, effects, sounds, flares, buildings: buildings.length, tiles: normalized.tiles },
             box: new THREE.Box3(new THREE.Vector3(low[0], low[2], low[1]), new THREE.Vector3(high[0], high[2], high[1])) };
  }
  // A prefab as a clip to place in this map: its records put on the map's tile grid (the prefab's origin on the grid's
  // corner; the placing moves it from there), each piece from its template, read from its home map when it is another
  // map's. `left`: what can't be had here, as sentences.
  async function prefabClip(doc, step = null) {
    const base = gridBase(), here = v => v.map((x, k) => x + base[k]), left = [];
    const records = doc.pieces.map(p => ({ ...p, location: here(p.location) }));
    const foreign = [...new Map(records.filter(p => !p.template && !p.kind && isForeignTarget(p.from)).map(p => [targetKey(p.from), p.from])).values()];
    // (its effects and sounds of other maps: their templates, as a project's copies read them)
    const foreignFx = [...new Map(records.filter(p => p.kind && !p.template && isForeignTarget(p.from)).map(p => [targetKey(p.from), p.from])).values()];
    const unread = foreign.filter(f => !libraryRecords.has(`${f.package}|${short(f.actor)}`.toLowerCase()));
    // the first use reads each piece from the game's maps: all of them asked for at once, so each map is opened once
    if (unread.length > 1) await readLibraryRecords(unread, (done, total) => step?.(done, total, `Opening ${doc.name}: pieces read`));
    const failed = new Map();
    let loaded = 0;
    await Promise.all(foreign.map(from => libraryTemplate(from).finally(() => step?.(++loaded, foreign.length, `Opening ${doc.name}: pieces loaded`)).then(t => {
      const entry = library?.entry(t.record.key);
      // (what the library only holds back is placed: library.js SOFT; what can't be brought is left)
      if (entry && !entry.placeable && !SOFT.includes(entry.blocked)) failed.set(targetKey(from), `${entry.name} of ${from.package} can't be brought into another map yet (${entry.reason})`);
    }, error => { failed.set(targetKey(from), `${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`); })));
    const unreadFx = foreignFx.filter(f => !effectTemplates.has(recordId(f)));
    if (unreadFx.length > 1) await readEffectRecords(unreadFx);
    await Promise.all(foreignFx.map(from => effectTemplate(from).then(t => {
      const entry = t.foreign?.key ? library?.entry(t.foreign.key) : null;
      if (entry && !entry.placeable && !SOFT.includes(entry.blocked)) failed.set(targetKey(from), `${entry.name} of ${from.package} can't be brought into another map yet (${entry.reason})`);
    }, error => { failed.set(targetKey(from), `${short(from.actor)} of ${from.package} could not be read from the game's maps (${error.message})`); })));
    const entries = [];
    for (const p of records) {
      const key = memberKey({ added: p.actor });
      if (p.kind && !p.template) {
        const e = optionsOf(p, 'effect');
        const failure = failed.get(targetKey(e.from));
        if (failure) { left.push(failure); continue; }
        const source = isForeignTarget(e.from) ? foreignEffects.get(targetKey(e.from)) : effectIndex.get(targetKey(e.from))?.userData.source;
        const what = e.kind === 'sound' ? 'sound' : e.kind === 'flare' ? 'lens flare' : 'effect';
        if (!source || source.kind !== e.kind) { left.push(`${short(e.from.actor)} of ${e.from.package}: this export of the map has no such ${what}`); continue; }
        const why = effectViewOnly(source, 'copy');
        if (why) { left.push(`${recordName(source, data)}: the ${what} isn't copied (${why})`); continue; }
        // its values are placed where their family builds (families.json); the prefab keeps them either way
        const values = e.kind !== 'flare' && families?.families?.[`${e.kind}-values`]?.builds ? e.values : null;
        entries.push({ source, matrix: movedMatrix(source, e.location, e.rotation), ...(values ? { values } : {}), unit: e.actor, key });
        continue;
      }
      if (p.template?.kind === COVER_KIND) {
        const source = coverOf(p), c = optionsOf(p, 'cover');
        if (!source) { left.push(`${short(c.actor)}: a cover block of a recipe this editor doesn't make`); continue; }
        entries.push({ source, matrix: new THREE.Matrix4().fromArray(source.matrix), unit: c.actor, key, link: c.prefab, partner: c.partner });
      } else if (p.template) {
        const l = optionsOf(p, 'light'), made = lightsBlocked() ? null : recipeLight(l.recipe, l.light, l.location, l.rotation);
        if (!made) { left.push(`${short(l.actor)}: a ${l.recipe.kind} light${lightsBlocked() ? ` (${lightsBlocked()})` : ', which this editor can\'t make yet'}`); continue; }
        entries.push({ source: made.source, matrix: new THREE.Matrix4().fromArray(made.source.matrix), values: made.values, unit: l.actor, key });
      } else {
        const failure = failed.get(targetKey(p.from));
        if (failure) { left.push(failure); continue; }
        const sources = p.components.map(c => templateFor(p.from, c));
        if (sources.some(s => !s)) { left.push(`${short(p.from.actor)} of ${p.from.package} is not in this export of the map`); continue; }
        // (each made as its record says, made numbers and blasts included, as a project's copy is)
        for (const source of sources) {
          const state = stateOf(p), o = optionsOf(p, 'piece', state);
          entries.push({ source, matrix: movedMatrix(source, o.location, o.rotation), unit: o.actor, key, link: o.prefab, partner: o.partner, state });
        }
      }
    }
    // its made pieces' meshes asked for now, so the placing preview draws them as they will stand (previewGroup); one
    // the server can't draw shows its donor there, and the paste says why (buildRoot)
    await Promise.all(entries.filter(e => e.state?.generated).map(e => {
      const mesh = madeShape(e.source, e.state.generated).mesh;
      if (!mesh) return null;
      track(geometryCache, mesh, () => gltfLoader.loadAsync(assetUrl(data.meshes[mesh].url)));
      return geometryCache.get(mesh)?.catch(() => null);
    }));
    const volumes = [], meta = {};
    for (const b of (doc.buildings ?? []).filter(validBuilding)) {
      meta[b.id] = { name: b.name ?? '', kind: b.kind ?? 'building' };
      b.floors.forEach((floor, k) => { for (const box of floor.boxes) volumes.push({ matrix: boxMatrix(box.map((v, i) => v + base[i % 3])), building: b.id, floor: k }); });
    }
    const tiles = doc.floor?.tiles ?? [1, 1], mark = { id: doc.id, name: doc.name, revision: doc.revision ?? 0 };
    return { entries, volumes, buildingMeta: meta, left, name: doc.name, prefab: mark, wrap: mark, pivotIndex: 0,
             groups: (doc.groups ?? []).map(g => ({ id: g.id, breakTogether: g.breakTogether === true, members: g.members.map(memberKey) })),
             // held by the middle of its footprint, on a tile corner
             pivot: [base[0] + Math.round(tiles[0] / 2) * TILE, base[1] + Math.round(tiles[1] / 2) * TILE, base[2]],
             gridLocked: volumes.length > 0 || entries.some(e => !e.source.isLight && !e.source.isEffect && pieceGrid(e.source)) };
  }
  function canRecoverPrefabSources(doc, missing) {
    const actors = new Set(missing);
    return doc.pieces.some(p => p.from && p.recipe && actors.has(p.actor));
  }
  // A prefab of the Prefabs tab: read, then placed as a paste is.
  async function choosePrefab(p) {
    const token = nextChooseToken();
    if (!p) { stopPlacing(); return null; }
    flashHint(`Reading ${p.name}…`);
    return busy(`Opening the prefab ${p.name}…`, step => placePrefab(p, token, step));
  }
  async function placePrefab(p, token, step = null) {
    let clip, recovered = 0;
    try {
      let doc = await prefabApi.load(p.id), size = await prefabApi.size(doc);
      if (canRecoverPrefabSources(doc, size.unknown)) {
        const match = await prefabApi.recoverSources(doc).catch(() => null);
        if (match?.repaired.length) {
          doc = match.document;
          recovered = match.repaired.length;
          size = await prefabApi.size(doc);
        }
      }
      if (!size.supported) throw Error(size.errors.join('; ') + '. Open Edit to repair it.');
      clip = await prefabClip({ ...doc, floor: { tiles: size.tiles } }, step);
      clip.bounds = size.bounds.map((v, k) => v + gridBase()[k % 3]);
    }
    catch (error) { if (token === chooseToken) flashHint(`${p.name} could not be placed: ${error.message}`); return null; }
    if (token !== chooseToken) return null;
    if (clip.left.length) {
      banner(`${p.name}: ${plural(clip.left.length, 'piece')} could not be placed. ${clip.left[0]}`);
    }
    if (!clip.entries.length && !clip.volumes.length) {
      if (!clip.left.length) flashHint(`There is nothing to place in ${p.name}.`);
      return clip;
    }
    setClipboard(clip);
    if (clip.entries.length >= BUSY_PIECES) await nextFrame();
    startPlacing(clip, { prefab: p, key: `prefab:${p.id}` });
    flashHint(`${p.name}${recovered ? ` · recovered ${plural(recovered, 'piece')} by recipe` : ''} · click to place it${clip.gridLocked ? ' (by whole tiles)' : ''} · R turns it`);
    return clip;
  }
  // A saved prefab's picture: drawn from the selection it was saved from, in a frame (drawPrefabPictures), and kept by
  // the server.
  // (the pictures waiting to be drawn, prefabPictures: editor_state.js)
  function drawPrefabPictures() {
    const job = prefabPictures.shift();
    if (!job) return;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 96;
    const object = previewGroup(job.entries, null, new THREE.Matrix4());
    for (const v of job.volumes ?? []) {
      const line = new THREE.LineSegments(ghostEdges, ghostLine); line.matrix.copy(v.matrix); line.matrixAutoUpdate = false; object.add(line);
    }
    if (!pieces.paintThumbs([{ object, box: job.box, thumb: canvas }])) return;
    canvas.toBlob(blob => blob && prefabApi.putPicture(job.id, blob).then(() => prefabTab.refresh()).catch(() => {}), 'image/png');
  }
  // Save the selection as a prefab under a name: a new one, or over the prefab `replace` (its summary) as its next
  // revision. Gives { id, name, revision }, null when `going()` turned false before the save was sent, or throws.
  // The server keeps a copy of every piece of a prefab in the library, and the first save of a map's pieces exports
  // each one (about 0.2 s a piece: three minutes for 800), so they are exported first, a few at a time, with
  // step(done, total) after each batch; the save itself then reads them back at once.
  const PREFAB_EXPORT_CHUNK = 20;
  async function savePrefab(name, records = prefabRecords(), replace = null, { step = null, going = () => true } = {}) {
    if (!records || (!records.pieces.length && !records.buildings.length)) throw Error('Nothing selected can go into a prefab');
    if (records.size && !records.size.supported) throw Error(records.size.errors.join('; '));
    const sources = [...new Map(records.pieces.filter(p => p.from && !p.kind).map(p => {
      const source = { package: p.from.package, level: 'base', actor: short(p.from.actor) };
      return [recordId(source), source];
    })).values()];
    for (let k = 0; k < sources.length; k += PREFAB_EXPORT_CHUNK) {
      if (!going()) return null;
      step?.(k, sources.length);
      // (a piece that can't be had is the save's to judge: it counts it unknown; a failed request leaves the rest to it)
      try { await prefabApi.warm(sources.slice(k, k + PREFAB_EXPORT_CHUNK)); } catch { break; }
    }
    if (!going()) return null;
    step?.(sources.length, sources.length);
    const id = replace?.id ?? uuid();
    const doc = newPrefab(id, name, records);
    const saved = await prefabApi.save(id, replace ? { ...doc, created: (await prefabApi.load(id)).created } : doc, replace?.revision ?? 0);
    prefabPictures.push({ id, entries: records.clip.entries, volumes: records.clip.volumes, box: records.box });
    prefabTab.refresh();
    return { id, name, revision: saved.revision };
  }
  const prefabDialog = { root: $('prefabDialog'), records: null, replace: null, builder: false, resolve: null, confirmed: null };
  function showPrefabDialog(whole = false) {
    whole = whole === true;
    if (!data) return;
    const records = prefabRecords({ complete: whole });
    if (!records || (!records.pieces.length && !records.buildings.length)) {
      flashHint('Select what should be the prefab first (Box select, T, takes a whole building)');
      return;
    }
    prefabDialog.records = records; prefabDialog.replace = null;
    prefabDialog.builder = whole; prefabDialog.confirmed = null;
    const maps = records.donors.map(d => d.package);
    $('prefabWhat').textContent = `${prefabWords(records.counts)}${records.groups.length ? ` · ${plural(records.groups.length, 'group')}` : ''}`
      + `${maps.length ? ` · pieces of ${maps.join(', ')}` : ''}. It is saved to the Add panel's Prefabs tab, to place in any map as one thing. `
      + 'The file holds references and places only, so it can be passed on.';
    const list = (id, title, lines) => {
      const box = $(id);
      box.hidden = !lines.length;
      box.replaceChildren();
      if (!lines.length) return;
      text(box, 'b', title);
      for (const line of lines.slice(0, 40)) text(box, 'div', line);
      if (lines.length > 40) text(box, 'div', `… and ${lines.length - 40} more`);
    };
    list('prefabLeft', `Left out of the prefab (${records.left.length})`, records.left);
    list('prefabOff', `Off the grid (${records.offGrid.length}): ladders, doors, cars, vans and fracturing pieces build exactly only on whole tiles and quarter turns from where their originals stand`, records.offGrid);
    // a name to start: the prefab the selection was placed from, else its one building's, else the pivot piece's
    const held = selectionGroup(), one = records.buildings.length === 1 ? records.buildings[0].name : '';
    $('prefabName').value = whole ? (builder.doc.revision ? `${builder.doc.name} copy` : '') : (held.kind === 'whole' && held.group.prefab?.name) || one || records.clip.name.replace(/ and \d+ other pieces?$/, '');
    prefabNameCheck();
    prefabDialog.root.hidden = false;
    prefabTab.refresh().then(prefabNameCheck);
    setTimeout(() => $('prefabName').select(), 0);
    return new Promise(resolve => { prefabDialog.resolve = resolve; });
  }
  function prefabNameCheck() {
    const name = $('prefabName').value.trim(), here = name ? prefabTab.byName(name) : null;
    prefabDialog.replace = here;
    const self = prefabDialog.builder && here?.id === builder.doc.id;
    $('prefabOk').disabled = !name || self;
    $('prefabOk').textContent = here ? 'Replace' : 'Save';
    $('prefabStatus').textContent = here ? `The library has “${here.name}” (revision ${here.revision}): Replace saves over it. What is placed in maps stays as it is.` : '';
    if (self) $('prefabStatus').textContent = 'Use Save to update the prefab being edited, or choose another name for Save as.';
  }
  // The dialog's progress row: a ring while it saves, and a bar with a count while the pieces are copied to the library.
  function prefabProgress(on, done = 0, total = 0) {
    $('prefabProgress').hidden = !on;
    $('prefabProgressBar').hidden = !(on && total > 0);
    $('prefabProgressBar').firstElementChild.style.width = total > 0 ? `${Math.round(100 * Math.min(1, done / total))}%` : '0';
    $('prefabProgressCount').textContent = on && total > 0 ? `${Math.min(done, total)} of ${total}` : '';
    $('prefabName').disabled = on;
  }
  function hidePrefabDialog(saved = false) { prefabProgress(false); prefabDialog.root.hidden = true; prefabDialog.records = null; prefabDialog.resolve?.(saved === true); prefabDialog.resolve = null; }
  $('prefabName').oninput = () => { prefabDialog.confirmed = null; prefabNameCheck(); };
  $('prefabForm').onsubmit = async e => {
    e.preventDefault();
    const name = $('prefabName').value.trim(), { records, replace } = prefabDialog;
    if (!name || !records) return;
    if (prefabDialog.builder && replace?.id === builder.doc.id) { prefabNameCheck(); return; }
    if (prefabDialog.builder && replace && prefabDialog.confirmed !== `${replace.id}:${replace.revision}`) {
      prefabDialog.confirmed = `${replace.id}:${replace.revision}`;
      $('prefabStatus').textContent = `Replace “${replace.name}” with these contents? The prefab being edited stays unchanged. Click Confirm replacement to continue.`;
      $('prefabOk').textContent = 'Confirm replacement'; return;
    }
    $('prefabOk').disabled = true; $('prefabStatus').textContent = 'Saving…';
    prefabProgress(true);
    // (closed while it saves, the view's own mark says it is still going)
    const endBusy = busyStart(`Saving the prefab ${name}…`);
    try {
      if (prefabDialog.builder) {
        const saved = await saveBuilder({ name, replace });
        if (saved) hidePrefabDialog(true);
        else { hidePrefabDialog(false); }
        return;
      }
      // Closing the dialog while the pieces are exported stops there; once the save is sent it finishes and says so.
      const open = () => prefabDialog.records === records;
      const step = (done, total) => {
        endBusy.job.done = done; endBusy.job.total = done < total ? total : null; busyPaint();
        if (!open()) return;
        prefabProgress(true, done, done < total ? total : 0);
        if (total >= PREFAB_EXPORT_CHUNK)
          $('prefabStatus').textContent = done < total ? 'Copying the pieces to the library (the first save of a map\'s pieces takes a while)…' : 'Saving…';
      };
      const saved = await savePrefab(name, records, replace, { step, going: open });
      if (!saved) return;
      if (open()) hidePrefabDialog(true);
      flashHint(`Saved the prefab ${saved.name}${replace ? ` (revision ${saved.revision})` : ''} · it is in the Add panel's Prefabs tab`);
    } catch (error) {
      if (prefabDialog.records !== records) { flashHint(`The prefab ${name} was not saved: ${error.message}`); return; }
      $('prefabOk').disabled = false; $('prefabStatus').textContent = `Not saved: ${error.message}`;
    } finally {
      endBusy();
      if (prefabDialog.records === records || !prefabDialog.records) prefabProgress(false);
    }
  };
  $('prefabClose').onclick = $('prefabCancel').onclick = hidePrefabDialog;
  prefabDialog.root.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Escape') { e.preventDefault(); hidePrefabDialog(); } });
  $('selectionPrefab').onclick = $('prefabSave').onclick = $('volumePrefab').onclick = showPrefabDialog;

  return { choosePrefab, drawPrefabPictures, prefabClip, prefabPlacementProblem, prefabRecords, savePrefab, showPrefabDialog };
}
