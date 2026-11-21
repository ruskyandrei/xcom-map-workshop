// Delete, Reset piece and Reset all (refactor stage P8). Here:
// - a step that touches many pieces put under the busy mark (heavy), and undo and redo of a large step (undoStep);
// - Delete: an added piece goes, an original is hidden and returns with undo or Reset all, one undo step
//   (deleteSelection, deleteNow);
// - Reset piece: the selection back where the map has it, a light's values too, one undo step (resetSelected);
// - Reset all: the map as exported, one undo step (resetAll).
//
// createDeleteReset takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the
// selection's pieces and boxes, the busy mark, the pieces', lights', effects' and boxes' roots added and taken away,
// the map's buildings changed and restored, the map's size, the landing zones, the spawn moves and rule, the mission
// picker, a broken piece drawn and the hints. It keeps no state of its own.
import { areaBindings, buildingMeta, cleared, clearKeepsOutside, effectRoots, groups, hintTimer, landingZones,
         lightRoots, missionMoves, ownSet, pickedEffect, projectMissions, projectSpawnRules, roots, setAreaBindings,
         setCleared, setClearKeepsOutside, setGroups, setLandingZones, setLightsDirty, setMergedBuildings, setPickedZone,
         setProjectMissions, setProjectSpawnRules, stage, volumesOn } from './editor_state.js';
import { cloneBlasts } from './piece_records.js';

export function createDeleteReset({ addEffectRoots, addLightRoots, addRoots, baseMatrix, busy, BUSY_PIECES,
                                    clearedChanged, cloneGroups, copyable, deleteVolumes, drawBroken, effectViewOnly,
                                    flashHint, gizmo, isStream, liveVolumes, mapEdits, mapRestoreChange, nextFrame,
                                    plural, refreshLandingZones, refreshLightVisibility, refreshMissionPicker,
                                    removeEffectRoots, removeLightRoots, removeRoots, restingHint, sceneChanged,
                                    selectedBoxes, selectionWords, setLightValues, setMissionMoves, setStage,
                                    syncSpawnRule, valuesEdited }) {
  // Delete: an added piece goes; an original is hidden (and returns with undo or Reset all).
  // A step that touches many pieces (BUSY_PIECES or more) puts the busy mark up first, so the page says what it is
  // doing instead of standing still (plan "faster editor", L3); a small one runs at once.
  function heavy(message, count, work) {
    if (count < BUSY_PIECES) return work();
    return busy(message, async () => { work(); await nextFrame(); }, { now: true });
  }
  // Undo and redo: a large step (a paste or a delete of many pieces says its size) under the busy mark. Once it is done,
  // the resting hint takes the place of a notice about what was undone ("Deleted 402 pieces · Ctrl+Z brings them back").
  function undoStep(redo = false) {
    const size = (redo ? gizmo.peekRedo() : gizmo.peekUndo())?.size ?? 0;
    heavy(`${redo ? 'Redoing' : 'Undoing'} a step of ${plural(size, 'piece')}…`, size, () => {
      if (redo) gizmo.redo(); else gizmo.undo();
      clearTimeout(hintTimer); restingHint();
    });
  }
  function deleteSelection(quiet = false) {
    if (volumesOn) { deleteVolumes(); return; }
    const count = copyable().length;
    heavy(`Deleting ${plural(count, 'piece')}…`, count, () => deleteNow(quiet));
  }
  // (`only`: those pieces, not the selection, whose locked groups bring their whole groups: a look change's)
  function deleteNow(quiet = false, only = null) {
    const targets = only ?? copyable(), boxes = only ? [] : selectedBoxes();
    if (!targets.length && !boxes.length) {
      const fx = effectRoots.get(pickedEffect);
      if (ownSet.size) flashHint('The map\'s own building is not deleted: its boxes are the map\'s');
      else if (fx) flashHint(`It isn't deleted: ${effectViewOnly(fx.userData.source, 'delete') ?? 'it is deleted'}`);
      return;
    }
    const pieces = targets.filter(r => !r.userData.light && !r.userData.effect), lights = targets.filter(r => r.userData.light);
    const added = pieces.filter(r => r.userData.source.added), originals = pieces.filter(r => !r.userData.source.added);
    const addedLights = lights.filter(r => r.userData.source.added), originalLights = lights.filter(r => !r.userData.source.added);
    // effects and sounds (effects and sounds plan, FX3): those the export lets an edit delete
    const effects = targets.filter(r => r.userData.effect && !effectViewOnly(r.userData.source, 'delete'));
    const addedEffects = effects.filter(r => r.userData.source.added), originalEffects = effects.filter(r => !r.userData.source.added);
    const kept = targets.filter(r => r.userData.effect && effectViewOnly(r.userData.source, 'delete'));
    if (kept.length && kept.length === targets.length && !boxes.length) { flashHint(`It isn't deleted: ${effectViewOnly(kept[0].userData.source, 'delete')}`); return; }
    const before = gizmo.picks();
    gizmo.record({
      size: targets.length,
      redo: () => {
        removeRoots(added); removeLightRoots(addedLights); removeEffectRoots(addedEffects);
        for (const r of [...originals, ...originalLights, ...originalEffects, ...boxes]) r.userData.deleted = true;
        refreshLightVisibility(); setLightsDirty(true); gizmo.setSelection([]); sceneChanged();
      },
      undo: () => {
        addRoots(added); addLightRoots(addedLights); addEffectRoots(addedEffects);
        for (const r of [...originals, ...originalLights, ...originalEffects, ...boxes]) r.userData.deleted = false;
        refreshLightVisibility(); setLightsDirty(true); gizmo.setSelection(before.ids, before.active); sceneChanged();
      },
    });
    const what = selectionWords([...targets, ...boxes]);
    if (!quiet) flashHint(`Deleted ${what} · Ctrl+Z brings ${targets.length + boxes.length === 1 ? 'it' : 'them'} back${ownSet.size ? ' · the map\'s own building stays' : ''}`);
  }
  // Reset piece: the selection back where the map has it; a light's values too. One undo step.
  function resetSelected() {
    const selection = gizmo.selection(), lights = selection.filter(r => r.userData.light && valuesEdited(r));
    // an effect kept where it stands (follow none): back to following its piece (effects and sounds plan, Part C)
    const stays = selection.filter(r => r.userData.effect && r.userData.stays);
    // an effect's or sound's values (stage FX5): back to the map's
    const valued = selection.filter(r => r.userData.effect && r.userData.values), fxValues = valued.map(r => r.userData.values);
    if (!lights.length && !stays.length && !valued.length) { gizmo.resetSelection(); return; }
    const moved = selection.filter(r => r.userData.edit), before = moved.map(r => r.matrix.clone()), home = moved.map(r => baseMatrix(r));
    const values = lights.map(r => ({ ...r.userData.values }));
    gizmo.record({
      redo: () => { gizmo.applyMatrices(moved, home); for (const r of lights) setLightValues(r, r.userData.baseValues); for (const r of stays) r.userData.stays = false; for (const r of valued) r.userData.values = null; sceneChanged(); },
      undo: () => { gizmo.applyMatrices(moved, before); lights.forEach((r, k) => setLightValues(r, values[k])); for (const r of stays) r.userData.stays = true; valued.forEach((r, k) => { r.userData.values = fxValues[k]; }); sceneChanged(); },
    });
  }
  // Reset all: the map as exported. Added pieces go, deleted ones return, moved ones go home, broken ones are mended,
  // groups end, and the grid, the landing zones and the clear mark are the map's own again; one undo step.
  function resetAll() {
    const all = [...roots.values()], lights = [...lightRoots.values()];
    const added = all.filter(r => r.userData.source.added), deleted = [...all, ...lights].filter(r => r.userData.deleted);
    const flagged = all.filter(r => !r.userData.source.added && r.userData.flags), flagsBefore = flagged.map(r => r.userData.flags);
    // the map's own pieces broken (Break, E6) are mended: their blasts and Breaks further in battle go (review finding 28)
    const broken = all.filter(r => !r.userData.source.added && r.userData.blasts?.length);
    const brokenBefore = broken.map(r => ({ blasts: cloneBlasts(r.userData.blasts), further: Boolean(r.userData.breaksFurther) }));
    const moved = [...all, ...lights].filter(r => r.userData.edit && !r.userData.source.added);
    const addedLights = lights.filter(r => r.userData.source.added), changed = lights.filter(r => !r.userData.source.added && valuesEdited(r));
    // effects and sounds: copies go, deleted ones return, moved ones go home, kept ones follow their piece again
    const fx = [...effectRoots.values()].filter(r => !isStream(r.userData.source));
    const addedEffects = fx.filter(r => r.userData.source.added), stays = fx.filter(r => r.userData.stays);
    const valued = fx.filter(r => !r.userData.source.added && r.userData.values), fxValues = valued.map(r => r.userData.values);
    deleted.push(...fx.filter(r => r.userData.deleted && !r.userData.source.added));
    moved.push(...fx.filter(r => r.userData.edit && !r.userData.source.added));
    // the map's own buildings changed or deleted come back as the map has them too
    const edits = mapEdits(), restore = mapRestoreChange([...edits.changed, ...edits.gone]);
    // the project's own buildings go: their boxes, which the buildings are made from
    const ownBoxes = liveVolumes().filter(r => !buildingMeta.get(r.userData.volume.building)?.map);
    if (!added.length && !deleted.length && !moved.length && !flagged.length && !broken.length && !groups.size && !addedLights.length && !changed.length && !areaBindings.size && !restore.count
        && !addedEffects.length && !stays.length && !valued.length
        && !ownBoxes.length && !stage && !landingZones && !cleared && !projectMissions && !missionMoves.size && !projectSpawnRules) return;
    const before = moved.map(r => r.matrix.clone()), home = moved.map(r => baseMatrix(r)), picks = gizmo.picks();
    // the map's own grid, landing zones and no clear mark
    const map = { stage, zones: landingZones ? landingZones.map(z => ({ ...z })) : null, cleared, keeps: clearKeepsOutside,
                  missions: projectMissions ? projectMissions.map(e => ({ ...e })) : null, moves: new Map(missionMoves),
                  rules: projectSpawnRules };
    const mapState = m => {
      setCleared(m.cleared); setClearKeepsOutside(m.keeps); setLandingZones(m.zones ? m.zones.map(z => ({ ...z })) : null);
      setProjectMissions(m.missions ? m.missions.map(e => ({ ...e })) : null);
      setMissionMoves(new Map(m.moves ?? []));
      setProjectSpawnRules(m.rules ?? null); syncSpawnRule();
      setMergedBuildings(null); setPickedZone(null); setStage(m.stage); clearedChanged(); refreshLandingZones(); refreshMissionPicker();
    };
    const groupsBefore = cloneGroups(), valuesBefore = changed.map(r => ({ ...r.userData.values })), bindingsBefore = new Map(areaBindings);
    gizmo.record({
      redo: () => {
        for (const r of flagged) r.userData.flags = null;
        for (const r of broken) { r.userData.blasts = null; r.userData.breaksFurther = false; drawBroken(r); }
        removeRoots(added); removeLightRoots(addedLights); removeEffectRoots(addedEffects); for (const r of stays) r.userData.stays = false;
        for (const r of valued) r.userData.values = null;
        for (const r of deleted) r.userData.deleted = false; gizmo.applyMatrices(moved, home);
        for (const r of changed) setLightValues(r, r.userData.baseValues);
        restore.redo();
        for (const r of ownBoxes) r.userData.deleted = true;
        mapState({ stage: null, zones: null, cleared: false, keeps: false, missions: null, rules: null });
        setAreaBindings(new Map()); setGroups(new Map()); refreshLightVisibility(); setLightsDirty(true); sceneChanged();
      },
      undo: () => {
        flagged.forEach((r, k) => { r.userData.flags = flagsBefore[k]; });
        broken.forEach((r, k) => { r.userData.blasts = cloneBlasts(brokenBefore[k].blasts); r.userData.breaksFurther = brokenBefore[k].further; drawBroken(r); });
        addRoots(added); addLightRoots(addedLights); addEffectRoots(addedEffects); for (const r of stays) r.userData.stays = true;
        valued.forEach((r, k) => { r.userData.values = fxValues[k]; });
        for (const r of deleted) r.userData.deleted = true; gizmo.applyMatrices(moved, before);
        changed.forEach((r, k) => setLightValues(r, valuesBefore[k]));
        restore.undo();
        for (const r of ownBoxes) r.userData.deleted = false;
        mapState(map);
        setAreaBindings(new Map(bindingsBefore)); setGroups(cloneGroups(groupsBefore)); refreshLightVisibility(); setLightsDirty(true);
        gizmo.setSelection(picks.ids, picks.active); sceneChanged();
      },
    });
  }

  return { deleteNow, deleteSelection, resetAll, resetSelected, undoStep };
}
