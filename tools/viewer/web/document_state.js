// The scene to and from a document (refactor stage P3). editStateNow reads the edits on screen as a project records
// them, sorted: the map's pieces, lights and effects changed or deleted (overrides), what was added (records written
// by piece_records.js's recordOf), the groups, the map's size, the buildings, the cleared map with its landing zones
// and missions, the spawn rules and the picture. applyState puts such a state on the map as exported; the records
// naming what this export lacks are given back, to be kept and saved back unchanged. A project's file, its drafts and
// the prefab builder's document all go through these two (app.js's editState keeps editStateNow's answer for one
// edit event).
//
// createDocumentState takes what it needs of app.js as one argument object, when app.js makes it: the roots' makers
// and readers, the lights', effects' and spawn points' records, and the groups', buildings' and map grid's own parts.
// The shared state it reads and writes is editor_state.js's.
import * as THREE from 'three';
import { COVER_KIND } from './cover.js';
import { areaBindings, builderMode, clearKeepsOutside, cleared, copySerial, data, effectRoots, landingZones, library, lightIndex,
         lightRoots, loadErrorCount, projectMissions, projectPicture, projectSpawnRules, roots, setClearKeepsOutside, setCleared,
         setCopySerial, setGroups, setLandingZones, setLoadErrorCount, setMergedBuildings, setProjectMissions, setProjectPicture,
         setProjectSpawnRules, stage, volumeRoots } from './editor_state.js';
import { cloneBlasts, optionsOf, recordOf, stateOfRoot } from './piece_records.js';
import { memberKey, pruneGroups, sortState, targetKey, validBuilding, validPicture, validPrefabMark, validStage } from './project.js';
import { NEW_VOLUME, SPAWN_COPY_KINDS, copyEntryOf, spawnEntryOf, spawnKey } from './spawns_view.js';

export function createDocumentState({ actorPose, addEffectRoots, addLightRoots, addRoots, addedEffectOf, addedLightOf, addedObject,
                                      applyEffectRecord, applyLightRecord, baseSpawnOf, buildRoots, builder, clearEdits,
                                      clearedChanged, cloneGroups, coverOf, coverVersion, drawBroken, editChanged, effectState,
                                      gizmo, lightState, liveMembers, loadForeignTemplates, mapBreakable, memberOf, missionKey,
                                      missionOverrides, movedMatrix, ownSize, plural, projectNote, savedBuildings, sceneChanged,
                                      setBuildings, setMissionMoves, setStage, short, sourceKey, spawnCopyRecords, streamObjects,
                                      syncSpawnRule, templateFor }) {
  function editStateNow() {
    const overrides = new Map(), added = new Map();     // (`added`: units while the roots are read, then their records)
    for (const root of roots.values()) {
      const o = root.userData.source;
      if (o.added && o.cover) {      // a cover block: its recipe (a version that makes its type), size and cover, at its corner
        added.set(o.actor, { form: 'cover', id: o.added.entity, actor: o.actor,
                             template: { ...o.added.template, version: coverVersion(o.added.template.version, o.cover.type) }, cover: o.cover,
                             ...actorPose(o, root.matrix) });
      } else if (o.added) {
        let unit = added.get(o.actor);
        if (!unit) {
          // (its tint, made numbers, flags and a broken copy's blasts: its state)
          unit = { id: o.added.entity, actor: o.actor, from: o.added.from, components: [], ...actorPose(o, root.matrix),
                   prefab: o.prefab, partner: o.partner, state: stateOfRoot(root.userData) };
          if (builderMode && builder.metadata.get(o.actor)?.recipe) unit.recipe = builder.metadata.get(o.actor).recipe;
          else if (builderMode && !builder.metadata.has(o.actor) && o.foreign?.key)
            unit.recipe = { key: o.foreign.key, name: library?.entry(o.foreign.key)?.name ?? short(data.meshes[o.mesh].name) };
          added.set(o.actor, unit);
        }
        unit.components.push(o.component);
      } else if ((root.userData.deleted || root.userData.edit || root.userData.flags || root.userData.blasts?.length) && !overrides.has(sourceKey(o))) {
        // (flags or blasts alone: an override with no pose, the piece where the map has it; a deleted piece has neither)
        const target = { package: o.sourcePackage, level: o.layer, actor: o.actor };
        overrides.set(sourceKey(o), root.userData.deleted ? { target, deleted: true }
          : { target, ...(root.userData.edit ? actorPose(o, root.matrix) : {}), ...(root.userData.flags ? { flags: { ...root.userData.flags } } : {}),
              ...(root.userData.blasts?.length ? { blasts: cloneBlasts(root.userData.blasts) } : {}),
              ...(root.userData.blasts?.length && root.userData.breaksFurther ? { breaksFurther: true } : {}) });
      }
    }
    for (const [actor, unit] of added) added.set(actor, recordOf(unit));
    const areaLightBindings = lightState(overrides, added);
    effectState(overrides, added);
    // A group keeps the pieces still on the map and the groups inside it; one left with fewer than two members isn't
    // saved (its last member takes its place in the group it was in).
    const saved = cloneGroups();
    for (const g of saved.values()) for (const [k, m] of [...g.members]) if (m.group === undefined && !liveMembers().has(k)
      && !(builderMode && builder.kept.some(p => memberKey({ added: p.actor }) === k))) g.members.delete(k);
    const kept = [...pruneGroups(saved).values()].map(g => ({ id: g.id, locked: g.locked, breakTogether: g.breakTogether, members: [...g.members.values()],
                                                               ...(g.prefab ? { prefab: g.prefab } : {}) }));
    return sortState({ overrides: [...overrides.values(), ...missionOverrides()], added: [...added.values(), ...spawnCopyRecords()], groups: kept, areaLightBindings, stage,
                      buildings: savedBuildings(), cleared, landingZones, clearKeepsOutside, missions: projectMissions,
                      spawnRules: projectSpawnRules, picture: projectPicture });
  }
  // Put a project state on the map: originals moved or deleted, copies added. Records naming pieces this export does
  // not have are returned, to be kept and saved back unchanged; nothing is matched by short name.
  const foreignNoted = new Set();
  async function applyState(state, progress = null) {
    // pieces of other maps: their templates read first (a map the install lacks leaves its records carried)
    for (const message of await loadForeignTemplates(state.added, progress))
      if (!foreignNoted.has(message)) { foreignNoted.add(message); projectNote(`${message}: its copies are kept and saved back unchanged.`); }
    clearEdits();
    setCleared(state.cleared === true); setClearKeepsOutside(cleared && state.clearKeepsOutside === true); setMergedBuildings(null);
    setLandingZones(Array.isArray(state.landingZones) ? state.landingZones.map(z => ({ ...z })) : null);
    setProjectMissions(Array.isArray(state.missions) ? state.missions.map(e => ({ ...e })) : null);
    setProjectPicture(validPicture(state.picture) ? { sha256: state.picture.sha256 } : null);
    setProjectSpawnRules(state.spawnRules ?? null); syncSpawnRule();
    setStage(validStage(state.stage, ownSize()?.dims) ? state.stage : null);
    clearedChanged();
    // (a record for a map building this export can't edit is kept and saved back unchanged)
    const unknownBuildings = setBuildings((state.buildings ?? []).filter(validBuilding));
    const actors = new Map(), carried = { overrides: [], added: [], groups: [], areaLightBindings: [], buildings: unknownBuildings };
    for (const r of roots.values()) {
      const key = sourceKey(r.userData.source);
      if (!actors.has(key)) actors.set(key, []);
      actors.get(key).push(r);
    }
    const streamMoves = new Map();
    for (const record of state.overrides) {
      if (record.target?.level === 'stream') {
        // a mission object moved in its stream (Part E): one of this export's, else carried unchanged
        const o = streamObjects(record.target.package).find(x => x.actor === record.target.actor);
        if (o && !record.deleted && Array.isArray(record.location) && Array.isArray(record.rotation))
          streamMoves.set(missionKey(record.target.package, o.actor), { stream: record.target.package, actor: o.actor,
                                                                        location: [...record.location], rotation: [...record.rotation] });
        else carried.overrides.push(record);
        continue;
      }
      // a base pod, Meld point or drop-in point moved, turned or given values (SP6); one the page doesn't take is
      // carried unchanged (below: no piece has its actor)
      if (record.target?.level === 'base' && String(record.target.package).toLowerCase() === String(data.name).toLowerCase()) {
        const o = baseSpawnOf(record.target.actor), entry = o ? spawnEntryOf(o, record) : null;
        if (entry) { streamMoves.set(missionKey(null, o.actor), entry); continue; }
      }
      if (applyLightRecord(record)) continue;
      if (applyEffectRecord(record)) continue;
      const list = actors.get(targetKey(record.target));
      if (!list) { carried.overrides.push(record); continue; }
      if (record.deleted) { for (const r of list) if (!r.userData.source.hidden && !r.userData.source.environment) r.userData.deleted = true; }
      else {
        if (record.location !== undefined) gizmo.applyMatrices(list, list.map(r => movedMatrix(r.userData.source, record.location, record.rotation)));
        if (record.flags) for (const r of list) r.userData.flags = { ...record.flags };
        if (record.blasts) for (const r of list) if (mapBreakable(r.userData.source)) {
          r.userData.blasts = cloneBlasts(record.blasts); r.userData.breaksFurther = record.breaksFurther === true; drawBroken(r);
        }
      }
    }
    const objs = [], lights = [], effects = [], entityOf = new Map();     // (each made piece's record: entityOf)
    for (const entity of state.added) {
      if (SPAWN_COPY_KINDS.includes(entity.kind)) {
        // a copy of one of the map's pods, Meld points or no-spawn volumes (SP7), or a new volume (no `from`); one the page
        // doesn't take is carried unchanged
        const from = entity.from, o = from?.level === 'base' && String(from.package).toLowerCase() === String(data.name).toLowerCase() ? baseSpawnOf(from.actor)
          : from === undefined && entity.kind === 'noSpawn' ? NEW_VOLUME : null;
        const entry = o ? copyEntryOf(o, entity) : null;
        if (entry) {
          streamMoves.set(spawnKey('copy', entry.actor), entry);
          const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
          if (serial > copySerial) setCopySerial(serial);
        } else carried.added.push(entity);
        continue;
      }
      if (entity.kind) {      // an effect, a sound or a flare copied (effects and sounds plan, Part C)
        const root = addedEffectOf(entity);
        if (root) effects.push(root); else carried.added.push(entity);
        continue;
      }
      if (entity.template?.kind === COVER_KIND) {
        const source = coverOf(entity);
        if (!source) { carried.added.push(entity); continue; }
        const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
        if (serial > copySerial) setCopySerial(serial);
        objs.push(addedObject(source, new THREE.Matrix4().fromArray(source.matrix), optionsOf(entity, 'cover')));
        entityOf.set(objs.at(-1), entity);
        continue;
      }
      if (entity.template || lightIndex.has(targetKey(entity.from))) {
        const light = addedLightOf(entity);
        if (light) lights.push(light); else carried.added.push(entity);
        continue;
      }
      // Output names already used, applied or not, are never handed out again.
      const serial = Number(/_copy(\d+)$/.exec(entity.actor)?.[1]);
      if (serial > copySerial) setCopySerial(serial);
      const sources = entity.components.map(c => templateFor(entity.from, c));
      if (sources.some(t => !t)) { carried.added.push(entity); continue; }
      for (const source of sources) {
        const options = optionsOf(entity);
        objs.push(addedObject(source, movedMatrix(source, options.location, options.rotation), options));
        entityOf.set(objs.at(-1), entity);
      }
    }
    // A piece that can't be drawn (its mesh, a material or a texture not had: review finding 29) is a display error, as
    // in the map's own load: its record is kept and saved back unchanged, and none of its parts is drawn.
    const failed = [], built = await buildRoots(objs, progress && ((done, total) => progress('making', done, total)), failed);
    const lost = new Set(failed.map(f => entityOf.get(f.obj)));
    addRoots(built.filter(r => !lost.has(entityOf.get(r.userData.source))));
    if (lost.size) {
      for (const f of failed) console.error(f.obj.actor, f.error);
      carried.added.push(...lost);
      setLoadErrorCount(loadErrorCount + lost.size);
      projectNote(`${plural(lost.size, 'piece')} of the ${builderMode ? 'prefab' : 'project'} could not be drawn (${failed[0].error?.message ?? failed[0].error}): `
        + `${lost.size === 1 ? 'its record is' : 'their records are'} kept and saved back unchanged. The browser console has the errors.`);
    }
    addLightRoots(lights);
    addEffectRoots(effects);
    setMissionMoves(streamMoves);
    // Area lights' glowing pieces as the project sets them; one naming a light this export lacks is carried.
    for (const b of state.areaLightBindings ?? []) {
      const root = lightIndex.get(targetKey(b.target));
      if (root?.userData.source.role === 'area') areaBindings.set(root.userData.source.actor, b.owner); else carried.areaLightBindings.push(b);
    }
    // Groups whose pieces are all here; one naming a piece this export (or this state) lacks is carried unchanged.
    const applied = new Set([...actors.keys()].map(k => `orig|${k}`));
    if (builderMode) for (const p of builder.kept) applied.add(memberKey({ added: p.actor }));
    for (const o of objs) if (!lost.has(entityOf.get(o))) applied.add(memberKey({ added: o.actor }));
    // (lights and the project's buildings are members too)
    for (const r of [...lightRoots.values(), ...volumeRoots.values(), ...effectRoots.values()]) applied.add(memberOf(r.userData.source));
    // (a group that names a group not applied goes with it; so does one in two groups, or in itself)
    const next = new Map(), wanted = state.groups ?? [];
    let fit = wanted.filter(g => g.members.every(m => m.group !== undefined || applied.has(memberKey(m))));
    for (let before = -1; before !== fit.length;) {
      before = fit.length;
      const ids = new Set(fit.map(g => g.id)), holders = new Map();
      for (const g of fit) for (const m of g.members) if (m.group !== undefined) holders.set(m.group, (holders.get(m.group) ?? 0) + 1);
      const loops = g => { for (let x = g, n = 0; x; n++) { if (n > 64) return true; x = fit.find(p => p.members.some(m => m.group === x.id)); } return false; };
      fit = fit.filter(g => g.members.every(m => m.group === undefined || (ids.has(m.group) && m.group !== g.id)) && (holders.get(g.id) ?? 0) <= 1 && !loops(g));
    }
    for (const g of wanted) {
      if (!fit.includes(g)) { carried.groups.push(g); continue; }
      // (a group saved unlocked, before 11 November 2026, is a group as any other now)
      next.set(g.id, { id: g.id, locked: true, breakTogether: g.breakTogether === true,
                       ...(validPrefabMark(g.prefab) ? { prefab: { ...g.prefab } } : {}),
                       members: new Map(g.members.map(m => [memberKey(m), m])) });
    }
    setGroups(next);
    setCopySerial(Math.max(copySerial, Number.isInteger(state.nextSerial) ? state.nextSerial : 0));
    gizmo.setSelection([]); gizmo.clearHistory(); sceneChanged(); editChanged();
    return carried;
  }

  return { editStateNow, applyState };
}
