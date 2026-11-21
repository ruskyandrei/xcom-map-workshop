// The Buildings view and box select (refactor stage P6; prefab plan 5.3a and the map buildings plan; floors.js holds
// the floors' rules: a box's floors around pieces, the cursor's floors, a building's problems, the pieces a box
// lists). The project's buildings are drawn as boxes, one for each box of each floor, each a root as a piece or a
// light is (volumeRoots); the map's own buildings that can be edited come with them, and the others show in grey, to
// be read. Here:
// - the map's buildings' records: every building the floors code reads (allBuildings: the map's as exported where
//   unchanged, the project's and the map's changed ones by their boxes), which of the map's own can be edited
//   (mapEditable), which the project changed or deleted (mapChanged, mapEdits), what the project saves of them
//   (savedBuildings) and whether a box is new or changed (freshBox);
// - the boxes made, put and painted (makeVolume, setVolumeBox, paintVolume), the project's buildings worked out from
//   them after every edit (buildingsFromVolumes, syncVolumes) and put back from a project (setBuildings), what is drawn
//   (refreshVolumes, drawOwnVolumes);
// - the view on or off (setVolumesShown), its tools (New box, Boxes around the pieces selected), a box clicked
//   (volumeClick) and the map's own picked to be read (setOwnPicked, pickOwn);
// - the boxes changed, each change one undo step: deleted, copied, pasted, a new building, a box added
//   (recordVolumes, addVolumes); the map's own buildings back as the map has them (restoreMapBuildings);
// - the six face handles a box has (and a picked no-spawn volume's, and box select's), their drags (startVolumeDrag,
//   moveVolumeDrag, endVolumeDrag), the cursor's floors drawn round the boxes;
// - the panel (volumePanel): the selected boxes' building, name, kind and floor, their heights, the map's changed
//   buildings, the notes and warnings;
// - the Normal button's Floor boxes switch (setBoxesShown) and a box's edge picked in the normal view (pickBoxEdge);
// - box select: the box drawn over the ground, stretched and moved (setPickTool, startPickDrag, movePickDrag,
//   endPickDrag), what it would take (refreshPickBox) and Select (takePickBox).
//
// createBuildingsWiring takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the
// camera, the renderer and the scene, the boxes' layer, the floors' listings and the cursor's floors, the Spawns view's
// no-spawn volumes, the other views' switches and the selection. Its own state is inside it (the map's edits worked
// out, the boxes' serial and key, the hovered handle, the boxes copied, the last building, the pieces to put boxes
// around, the panel's counts, the cursor rings' key); what other areas read or set (the Normal button's switch, the
// buildings' names and kinds, the map's own selected or picked, the tool, a drag, box select's tool, box, drag and
// hits) is editor_state.js's.
import * as THREE from 'three';
import { LEVEL, TILE } from './constants.js';
import { onHub, STOP } from './edit_hub.js';
import { allRoots, boxesShown, builderMode, buildingMeta, buildings, buildingsVersion, cleared, data, effectRoots,
         effectsOn, hintTimer, lightRoots, lightsOn, lightsShown, mergedBuildings, ownPicked, ownSet, pickBox,
         pickCentres, pickDrag, pickedSpawn, pickHits, pickTool, placing, roots, selected, setBoxesShownValue,
         setBuildingsValue, setBuildingsVersion, setLightsOn, setLiveCache, setMergedBuildings, setMissionDragView,
         setOwnPickedValue, setPickBoxValue, setPickCentres, setPickDrag, setPickHits, setPickToolValue, setVolumeDrag,
         setVolumesOn, setVolumeToolValue, spawnPlacing, volumeDrag, volumeRoots, volumesOn, volumeTool,
         zonesOn } from './editor_state.js';
import { buildingProblems, CURSOR_NEAR, cursorMiss, floorsAround, floorsOf, LISTED_CLASSES, STOREY_HEIGHT,
         storeysOver, touchedFloors } from './floors.js';
import { scaleMarker } from './lights_view.js';
import { PREFAB_MAX_Z, PREFAB_MIN_Z } from './prefab_document.js';
import { BUILDING_FLOORS_MAX, BUILDING_SAME, mapBuildingId, targetKey, tidyBuilding,
         validBuilding } from './project.js';
import { boxWords } from './spawns_view.js';

export function createBuildingsWiring({ $, boxOf, builderBounds, camera, chosenStorey, copySelection, deleteSelection,
                                        editBaseSpawn, editChanged, editedCopies, editedKey, editedSpawns,
                                        editSpawnCopy, effectsShown, effectViewOnly, flashHint, floorOptions, gizmo,
                                        HANDLE_PICK, isStream, kindButton, lightViewOnly, missionGizmo, pick, plural,
                                        projectListings, projector, projectsAvailable, rayAt, refreshSpawnMarkers,
                                        renderer, restingHint, select, selectionWords, setEffectsShown, setZonesShown,
                                        short, showPop, spawnBoxNow, spawnEntry, spawnMovable, spawnsShown, storeysNow,
                                        syncLights, text, volumeLayer, world }) {
  // allBuildings is what the floors code reads: the map's as exported where unchanged (their saved listings), the
  // project's and the changed ones of the map by their boxes (worked out once for each state of the buildings:
  // mergedBuildings, editor_state.js).
  const PROJECT_BUILDING = 'project:';
  function allBuildings() {
    if (!mergedBuildings) {
      const edits = mapEdits();
      setMergedBuildings([...(data?.buildings ?? []).filter(b => !edits.exportIds.has(b.id) && !(cleared && !mapEditable(b))),
        ...buildings.filter(b => !buildingMeta.get(b.id)?.map || edits.changed.has(b.id))
          .map(b => ({ id: PROJECT_BUILDING + b.id, name: b.name || 'Building', project: b, floors: floorsOf(b), map: buildingMeta.get(b.id)?.map ?? null }))]);
    }
    return mergedBuildings;
  }
  // The map's own buildings (export 21): one that can be edited is drawn and edited as the project's are, under the id
  // made from its actor; a van's (it goes with the van), one with a floor that has no floor volume, a patch's, and every
  // one of an older export, a preview or the prefab builder stays fixed, drawn grey to be read.
  const mapEditable = b => data?.scope === 'map' && !data.preview && !builderMode && data.exporterVersion >= 21 && Boolean(b.actor)
    && !b.van && /^\d+$/.test(String(b.id)) && (b.floors ?? []).length > 0
    && b.floors.every(f => (f.volumes ?? []).length > 0 && (f.boxes ?? []).length === f.volumes.length);
  const mapIdOf = b => mapBuildingId(b.level ?? 'PersistentLevel', b.actor);
  const mapTarget = b => ({ package: data.name, level: 'base', actor: b.name });
  const mapKind = b => (b.isUfo ? 'ufo' : 'building');
  // a map building's floors as the map has them, as a record's: boxes and the floor volume each is
  const mapFloors = b => b.floors.map(f => ({ boxes: f.boxes.map(x => [...x.min, ...x.max]), volumes: f.volumes.map(short) }));
  // Whether a live record of a map building differs from the map's: its name, kind or a floor (every box within
  // BUILDING_SAME of its own volume's, each volume once: the compiler's rule).
  function mapChanged(b) {
    const e = buildingMeta.get(b.id)?.map;
    if (!e) return true;
    if ((b.name || '') !== short(e.actor) || (b.kind ?? 'building') !== mapKind(e) || b.floors.length !== e.floors.length) return true;
    const own = mapFloors(e);
    return b.floors.some((f, k) => {
      const boxes = new Map(own[k].volumes.map((v, n) => [v, own[k].boxes[n]]));
      return f.volumes.length !== boxes.size || new Set(f.volumes).size !== f.volumes.length
        || f.volumes.some((v, n) => !boxes.has(v) || boxes.get(v).some((x, j) => Math.abs(x - f.boxes[n][j]) > BUILDING_SAME));
    });
  }
  // Which map buildings the project changed (by their boxes, name or kind) and deleted (no box left), worked out once
  // for each state of the buildings: changed, gone (ids), exportIds (the export's ids of both).
  let mapEditsCache = null;
  function mapEdits() {
    if (mapEditsCache?.version === buildingsVersion) return mapEditsCache;
    const live = new Map(buildings.map(b => [b.id, b])), changed = new Set(), gone = new Set(), exportIds = new Set();
    for (const [id, m] of buildingMeta) if (m.map) {
      const b = live.get(id);
      if (!b) { gone.add(id); exportIds.add(m.map.id); }
      else if (mapChanged(b)) { changed.add(id); exportIds.add(m.map.id); }
    }
    return (mapEditsCache = { version: buildingsVersion, changed, gone, exportIds });
  }
  // What the project saves of the buildings: its own, and the map's changed or deleted (an unchanged one is the map's).
  function savedBuildings() {
    const edits = mapEdits();
    return [...buildings.filter(b => !buildingMeta.get(b.id)?.map || edits.changed.has(b.id)),
            ...[...edits.gone].map(id => ({ id, replaces: mapTarget(buildingMeta.get(id).map), deleted: true }))];
  }
  // Whether a box of a building is new or changed (the compiler's warnings are said for those only): a box of the
  // project's own is; one of the map's is when it has no volume of the map's or stands away from its volume's box.
  function freshBox(b, k, n) {
    const e = buildingMeta.get(b.id)?.map;
    if (!e) return true;
    const v = b.floors[k]?.volumes?.[n], own = mapFloors(e).flatMap(f => f.volumes.map((name, i) => [name, f.boxes[i]])).find(x => x[0] === v);
    return !own || own[1].some((x, j) => Math.abs(x - b.floors[k].boxes[n][j]) > BUILDING_SAME);
  }
  // The Buildings view (prefab plan 5.3a): the project's buildings as boxes in the view, one for each box of each floor,
  // made, stretched and moved there. A box is a root as a piece or a light is (volumeRoots; the gizmo moves it, by whole
  // tiles and levels), drawn see-through in its floor's colour; the map's own floor volumes show in grey, never picked.
  // While the view is on (the tool strip's button, Shift+B) only boxes are picked: no piece or light can be selected or
  // moved by accident. `buildings`, what the project saves and the Floor buttons, the cutaway and the pieces' Floors
  // lines read, is written from the boxes after every edit (syncVolumes).
  const FLOOR_COLOURS = [0x4aa3ff, 0xffb347, 0x5ad17a, 0xe06cff, 0xff6b6b, 0x4ad1c8, 0xd1c84a, 0xb0b8c0];
  const volumeMaterials = FLOOR_COLOURS.map(color => ({
    fill: new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthWrite: false }),
    picked: new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.26, side: THREE.DoubleSide, depthWrite: false }),
    // while it is drawn or stretched: the same see-through box, a little whiter
    drag: new THREE.MeshBasicMaterial({ color: new THREE.Color(color).lerp(new THREE.Color(0xffffff), 0.45), transparent: true, opacity: 0.3,
                                        side: THREE.DoubleSide, depthWrite: false }),
    line: new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9, depthWrite: false }),
    through: new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.3, depthWrite: false, depthTest: false }) }));
  const ownVolumeMaterials = {
    fill: new THREE.MeshBasicMaterial({ color: 0x9aa7b0, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false }),
    picked: new THREE.MeshBasicMaterial({ color: 0xc8d4dc, transparent: true, opacity: 0.24, side: THREE.DoubleSide, depthWrite: false }),
    line: new THREE.LineBasicMaterial({ color: 0x9aa7b0, transparent: true, opacity: 0.45, depthWrite: false }) };
  const ownVolumeLayer = new THREE.Group(); world.add(ownVolumeLayer);
  // (building id -> { name, kind }, buildingMeta: editor_state.js)
  let volumeSerial = 0, volumesKey = '[]', volumeHover = null;     // (volumesOn, volumeTool, volumeDrag: editor_state.js)
  let volumeClip = null, lastBuilding = null, aroundIds = [];
  // (one of the map's own boxes, picked to read: its fill mesh, never moved or changed; ownPicked: editor_state.js)
  // The map's own buildings selected with pieces in the normal view (the Normal button's Floor boxes): a copy of the
  // selection then gets a building of the project with the same boxes. They are never moved, turned or deleted: the
  // Build leaves the map's own volumes as they are (the user, 11 November 2026, after copying the Bar).
  // (those buildings, ownSet: editor_state.js)
  const volumeGrid = () => (data?.tileGrid?.origin && data.tileGrid.dimensions
    ? { origin: data.tileGrid.origin, dimensions: data.tileGrid.dimensions, size: data.tileGrid.size ?? [TILE, TILE, LEVEL], unbounded: builderMode,
        ...(builderMode ? { heights: [PREFAB_MIN_Z, PREFAB_MAX_Z] } : {}) } : null);
  const newBuildingId = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  const boxCount = n => `${n} ${n === 1 ? 'box' : 'boxes'}`;
  const liveVolumes = () => [...volumeRoots.values()].filter(r => !r.userData.deleted);
  // (in the normal view a building is picked whole: every box that moves with the selection)
  const pickedVolumes = () => (volumesOn ? gizmo.picks().ids.map(id => volumeRoots.get(id)).filter(r => r && !r.userData.deleted)
    : gizmo.selection().filter(r => r.userData.volume && !r.userData.deleted));
  // A box's place, [x0, y0, z0, x1, y1, z1] in game units. Its root's matrix is the whole box: a unit cube moved to its
  // middle, scaled to its size and, after a turn with pieces in the normal view, turned by quarter turns; so the
  // gizmo's moves, turns and undo carry all of it. The box is what that cube covers along the axes.
  function volumeBox(root) {
    const e = root.matrix.elements, r = v => Number(v.toFixed(3)) + 0;
    const half = row => (Math.abs(e[row]) + Math.abs(e[4 + row]) + Math.abs(e[8 + row])) / 2;
    const hx = half(0), hz = half(1), hy = half(2);
    return [r(e[12] - hx), r(e[14] - hy), r(e[13] - hz), r(e[12] + hx), r(e[14] + hy), r(e[13] + hz)];
  }
  function setVolumeBox(root, box) {
    const v = root.userData.volume, size = [box[3] - box[0], box[4] - box[1], box[5] - box[2]];
    const centre = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2];
    root.matrix.makeScale(size[0], size[2], size[1]).setPosition(centre[0], centre[2], centre[1]); root.matrixWorldNeedsUpdate = true;
    // its unedited pose is where it is put: the gizmo's moves count from here
    Object.assign(root.userData.source, { matrix: root.matrix.toArray(), location: centre, rotation: [0, 0, 0] });
    root.userData.edit = null;
    v.size = size;
    if (!root.children.length) {
      const geometry = new THREE.BoxGeometry(1, 1, 1), edges = new THREE.EdgesGeometry(geometry);
      const fill = new THREE.Mesh(geometry), line = new THREE.LineSegments(edges), through = new THREE.LineSegments(edges.clone());
      fill.userData.volumeId = root.userData.source.id; line.raycast = through.raycast = () => {};
      for (const part of [fill, line, through]) { part.renderOrder = 2; root.add(part); }
      root.userData.fill = fill; root.userData.lines = [line, through];
    }
    // drawn a unit short of its faces, so two boxes that touch don't flicker
    for (const part of root.children) part.scale.set(1 - 1 / Math.max(2, size[0]), 1 - 1 / Math.max(2, size[2]), 1 - 1 / Math.max(2, size[1]));
    paintVolume(root);
  }
  // A box's colours: its floor's, fuller when selected, whiter while it is drawn or stretched.
  function paintVolume(root, picked = pickedVolumes().includes(root)) {
    const m = volumeMaterials[root.userData.volume.effective % volumeMaterials.length];
    root.userData.fill.material = volumeDrag?.root === root ? m.drag : picked ? m.picked : m.fill;
    root.userData.lines[0].material = m.line; root.userData.lines[1].material = m.through;
  }
  // (`origin`: the map's floor volume a box of one of the map's buildings is, null for a new box; it holds only while
  // the box is in that building, its `home`)
  function makeVolume(box, building, floor, origin = null) {
    const id = `volume:${++volumeSerial}`, root = new THREE.Group();
    root.matrixAutoUpdate = false;
    root.userData = { volume: { building, floor, size: [0, 0, 0], effective: floor, origin, home: building }, deleted: false, edit: null,
                      source: { id, isVolume: true, sourcePackage: '', layer: 'volume', actor: id, hidden: false } };
    volumeRoots.set(id, root); volumeLayer.add(root);
    setVolumeBox(root, box);
    return root;
  }
  // The project's buildings as the boxes say them: a building's floors are its boxes' floor numbers in order (a number
  // no box has is no floor: the ones above it count down), and each box's floor as counted (volume.effective).
  function buildingsFromVolumes() {
    const by = new Map();
    for (const root of liveVolumes()) { const b = root.userData.volume.building; if (!by.has(b)) by.set(b, []); by.get(b).push(root); }
    const out = [];
    for (const [id, list] of by) {
      const numbers = [...new Set(list.map(r => r.userData.volume.floor))].sort((a, b) => a - b).slice(0, BUILDING_FLOORS_MAX);
      for (const r of list) r.userData.volume.effective = Math.max(0, Math.min(numbers.length - 1, numbers.indexOf(r.userData.volume.floor)));
      const meta = buildingMeta.get(id) ?? { name: '', kind: 'building' };
      const floorRoots = numbers.map((n, k) => list.filter(r => r.userData.volume.effective === k));
      // one of the map's: `replaces` its building volume, each box with the floor volume it is (tidyBuilding sorts them)
      out.push(tidyBuilding({ id, name: meta.name, kind: meta.kind, ...(meta.map ? { replaces: mapTarget(meta.map) } : {}),
        floors: floorRoots.map(rs => (meta.map
          ? { boxes: rs.map(volumeBox), volumes: rs.map(r => (r.userData.volume.home === id ? r.userData.volume.origin : null)) }
          : { boxes: rs.map(volumeBox).sort((a, b) => a.join().localeCompare(b.join())) })) }));
    }
    return out.sort((a, b) => a.id.localeCompare(b.id));
  }
  // After an edit of the boxes (a move let go, an undo, a new box): the project's buildings follow, and with them the
  // Floor buttons, the cutaway and the pieces' Floors lines.
  function syncVolumes() {
    if (!data || gizmo.controls.dragging || volumeDrag) return;
    const next = buildingsFromVolumes(), key = JSON.stringify(next);
    if (key === volumesKey) return;
    volumesKey = key; setBuildingsValue(next); setBuildingsVersion(buildingsVersion + 1); setMergedBuildings(null);
    setLiveCache(null);     // a group's buildings are counted by their boxes
    floorOptions();       // the Floor buttons, then the cutaway
  }
  // The project's buildings put in the view (a project opened, or the edits cleared): every box made anew. The history
  // is the caller's to forget, as for added pieces.
  // The map's own buildings that can be edited come with them, each as the project's record has it (changed or
  // deleted), else as the map has it. Returns the records of map buildings this export can't edit (a van's, one it
  // lacks, a second record for one): the caller carries them unchanged.
  function setBuildings(next) {
    for (const root of volumeRoots.values()) { for (const child of root.children) child.geometry.dispose(); volumeLayer.remove(root); }
    volumeRoots.clear(); buildingMeta.clear(); lastBuilding = null;
    const editable = new Map((data?.buildings ?? []).filter(mapEditable).map(b => [targetKey(mapTarget(b)), b]));
    const records = new Map(), unknown = [];
    for (const b of next.filter(validBuilding)) {
      if (b.replaces) {
        const key = targetKey(b.replaces);
        if (editable.has(key) && !records.has(key)) records.set(key, b); else unknown.push(b);
        continue;
      }
      const tidy = tidyBuilding(b);
      buildingMeta.set(tidy.id, { name: tidy.name, kind: tidy.kind });
      tidy.floors.forEach((floor, k) => { for (const box of floor.boxes) makeVolume(box, tidy.id, k); });
    }
    for (const [key, e] of editable) {
      const record = records.get(key), id = mapIdOf(e);
      buildingMeta.set(id, { name: record?.name || short(e.actor), kind: record && !record.deleted ? record.kind ?? 'building' : mapKind(e), map: e });
      const floors = record?.deleted ? [] : record ? tidyBuilding(record).floors : mapFloors(e);
      floors.forEach((floor, k) => floor.boxes.forEach((box, n) => makeVolume(box, id, k, floor.volumes?.[n] ?? null)));
    }
    setBuildingsValue(buildingsFromVolumes()); volumesKey = JSON.stringify(buildings);
    setBuildingsVersion(buildingsVersion + 1); setMergedBuildings(null);
    if (data) drawOwnVolumes();
    refreshVolumes();
    if (data) floorOptions();
    return unknown;
  }
  // What is drawn of the boxes: only with the view on, each in its floor's colour, the selected ones fuller.
  function refreshVolumes() {
    const picked = new Set(pickedVolumes());
    for (const root of volumeRoots.values()) {
      root.visible = (volumesOn || (boxesShown && !lightsOn)) && !root.userData.deleted;
      paintVolume(root, picked.has(root));
    }
    const ownShown = volumesOn || (boxesShown && !lightsOn);
    if (ownShown && !ownVolumeLayer.children.length && data?.buildings?.some(b => !mapEditable(b))) drawOwnVolumes();
    ownVolumeLayer.visible = ownShown;
    for (const part of ownVolumeLayer.children) if (part.userData.own)
      part.material = part === ownPicked || ownSet.has(part.userData.own.building) ? ownVolumeMaterials.picked : ownVolumeMaterials.fill;
  }
  function drawOwnVolumes() {
    for (const child of [...ownVolumeLayer.children]) { child.geometry.dispose(); ownVolumeLayer.remove(child); }
    setOwnPickedValue(null);
    for (const b of (data?.buildings ?? []).filter(b => !mapEditable(b))) (b.floors ?? []).forEach((floor, k) => (floor.boxes ?? []).forEach(({ min, max }, n) => {
      const geometry = new THREE.BoxGeometry(max[0] - min[0], max[2] - min[2], max[1] - min[1]);
      const fill = new THREE.Mesh(geometry, ownVolumeMaterials.fill), line = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), ownVolumeMaterials.line);
      // picked to be read, never changed: the building, the floor and the floor volume it is
      fill.userData.own = { building: b, floor: k, box: [...min, ...max],
                            volume: (floor.volumes ?? []).length === (floor.boxes ?? []).length ? floor.volumes[n] : null };
      line.raycast = () => {};
      for (const part of [fill, line]) { part.position.set((min[0] + max[0]) / 2, (min[2] + max[2]) / 2, (min[1] + max[1]) / 2); part.renderOrder = 1; ownVolumeLayer.add(part); }
    }));
  }
  function setOwnPicked(mesh) {
    if (mesh === ownPicked) return;
    setOwnPickedValue(mesh);
    refreshVolumes(); volumePanel();
  }
  function setVolumesShown(on) {
    const next = Boolean(on) && data?.scope === 'map' && !data.preview;
    if (next === volumesOn) return;
    if (next) {
      if (zonesOn) setZonesShown(false);
      if (effectsOn) setEffectsShown(false);
      // the pieces selected on the way in: "Boxes around them" makes a building of them
      aroundIds = gizmo.selection().filter(r => roots.has(r.userData.source.id) && !r.userData.source.cover && !r.userData.deleted).map(r => r.userData.source.id);
      stopPickBox();
      select(null);
      setLightsOn(false);
      setVolumesOn(true);
      if (gizmo.mode === 'rotate') gizmo.setMode('translate');
      if (!ownVolumeLayer.children.length) drawOwnVolumes();
    } else {
      setVolumeTool(null);
      setVolumesOn(false); aroundIds = []; setOwnPickedValue(null);
      if (volumeRoots.has(gizmo.active)) select(null);
    }
    syncLights();
    refreshVolumes(); volumePanel(); restingHint();
  }
  // ---- changes, each one undo step. A box is never thrown away while the history may name it: deleting hides it.
  const volumeState = root => ({ box: volumeBox(root), building: root.userData.volume.building, floor: root.userData.volume.floor, deleted: root.userData.deleted });
  function putVolumeState(root, s) {
    setVolumeBox(root, s.box); root.userData.volume.building = s.building; root.userData.volume.floor = s.floor; root.userData.deleted = s.deleted;
  }
  // change(): alters boxes (`targets`) and building names and kinds; recorded with what they were before.
  function recordVolumes(targets, change, selection = null) {
    const before = targets.map(volumeState), metaBefore = new Map([...buildingMeta].map(([k, v]) => [k, { ...v }])), picksBefore = gizmo.picks();
    change();
    const after = targets.map(volumeState), metaAfter = new Map([...buildingMeta].map(([k, v]) => [k, { ...v }]));
    const put = (states, meta, picks) => {
      targets.forEach((root, i) => putVolumeState(root, states[i]));
      buildingMeta.clear(); for (const [k, v] of meta) buildingMeta.set(k, { ...v });
      if (picks) gizmo.setSelection(picks.ids.filter(id => !volumeRoots.get(id)?.userData.deleted), picks.active);
    };
    gizmo.record({ redo: () => put(after, metaAfter, selection ?? picksBefore), undo: () => put(before, metaBefore, picksBefore) });
  }
  // The floor a new box at height z0 is in a building: the floor whose boxes start there, else one for each floor that
  // starts lower.
  function floorFor(building, z0) {
    const starts = new Map();
    for (const r of liveVolumes()) if (r.userData.volume.building === building) {
      const f = r.userData.volume.floor, z = volumeBox(r)[2];
      starts.set(f, Math.min(starts.get(f) ?? Infinity, z));
    }
    for (const [f, z] of starts) if (Math.abs(z - z0) <= 8) return f;
    const below = [...starts].filter(([, z]) => z < z0).map(([f]) => f);
    return Math.min(BUILDING_FLOORS_MAX - 1, below.length ? Math.max(...below) + 1 : 0);
  }
  function newBuilding() {
    const id = newBuildingId();
    let n = 1;
    const names = new Set([...buildingMeta.values()].map(m => m.name));
    while (names.has(`Building ${n}`)) n++;
    buildingMeta.set(id, { name: `Building ${n}`, kind: 'building' });
    return id;
  }
  // The building a new box joins: the one of the box selected (or made) last, while it still has a box.
  function buildingForNew() {
    const live = new Set(liveVolumes().map(r => r.userData.volume.building));
    const from = volumeRoots.get(selected)?.userData.volume.building ?? lastBuilding;
    return live.has(from) ? from : null;
  }
  function addVolumes(boxes, building = null) {
    const id = building ?? buildingForNew() ?? newBuilding();
    const made = boxes.map(({ box, floor }) => { const root = makeVolume(box, id, floor ?? floorFor(id, box[2])); root.userData.deleted = true; return root; });
    const meta = { ...buildingMeta.get(id) };
    gizmo.record({ redo: () => { for (const r of made) r.userData.deleted = false; if (!buildingMeta.has(id)) buildingMeta.set(id, { ...meta });
                                 gizmo.setSelection(made.map(r => r.userData.source.id)); },
                   undo: () => { for (const r of made) r.userData.deleted = true; gizmo.setSelection([]); } });
    lastBuilding = id;
    return made;
  }
  function deleteVolumes() {
    const targets = pickedVolumes();
    if (!targets.length) return;
    recordVolumes(targets, () => { for (const r of targets) r.userData.deleted = true; }, { ids: [], active: null });
    flashHint(`${boxCount(targets.length)} deleted · Ctrl+Z brings ${targets.length === 1 ? 'it' : 'them'} back`);
  }
  function copyVolumes(cut = false) {
    const targets = pickedVolumes();
    if (!targets.length) return;
    volumeClip = targets.map(r => ({ box: volumeBox(r), building: r.userData.volume.building, floor: r.userData.volume.floor }));
    if (cut) deleteVolumes();
    flashHint(`${boxCount(targets.length)} ${cut ? 'cut' : 'copied'} · Ctrl+V puts ${targets.length === 1 ? 'a copy' : 'copies'} on top, as the next floor`);
  }
  // Paste: each copied box again on top of where it was copied from, as the floor above it in its building (a building
  // that is gone gets the boxes as a new one). Moved from there with the gizmo. One undo step, whatever the buildings
  // (review finding 34: it was one a building), which takes the new buildings' names back too.
  function pasteVolumes() {
    if (!volumeClip?.length) { flashHint('Nothing copied yet: select a box and press Ctrl+C'); return; }
    const live = new Set(liveVolumes().map(r => r.userData.volume.building)), grid = volumeGrid();
    const top = grid && !builderMode ? grid.origin[2] + grid.dimensions[2] * grid.size[2] : Infinity;
    const byBuilding = new Map();
    for (const c of volumeClip) { if (!byBuilding.has(c.building)) byBuilding.set(c.building, []); byBuilding.get(c.building).push(c); }
    const made = [], fresh = new Map(), names = new Set([...buildingMeta.values()].map(m => m.name));
    let last = null;
    for (const [building, clips] of byBuilding) {
      let id = building;
      if (!live.has(building)) {
        // (a building that is gone: a new one, named as newBuilding names one)
        id = newBuildingId();
        let n = 1;
        while (names.has(`Building ${n}`)) n++;
        names.add(`Building ${n}`); fresh.set(id, { name: `Building ${n}`, kind: 'building' });
      }
      const rise = Math.max(...clips.map(c => c.box[5])) - Math.min(...clips.map(c => c.box[2]));
      const fits = Math.max(...clips.map(c => c.box[5])) + rise <= top + 0.5 && live.has(building);
      for (const c of clips) {
        const root = makeVolume(fits ? [c.box[0], c.box[1], c.box[2] + rise, c.box[3], c.box[4], c.box[5] + rise] : [...c.box], id,
                                fits ? Math.min(BUILDING_FLOORS_MAX - 1, c.floor + 1) : c.floor);
        root.userData.deleted = true;
        made.push(root);
      }
      last = id;
    }
    const ids = made.map(r => r.userData.source.id), before = gizmo.picks();
    gizmo.record({
      redo: () => { for (const [id, meta] of fresh) buildingMeta.set(id, { ...meta }); for (const r of made) r.userData.deleted = false; gizmo.setSelection(ids); },
      undo: () => { for (const r of made) r.userData.deleted = true; for (const id of fresh.keys()) buildingMeta.delete(id); gizmo.setSelection(before.ids, before.active); },
    });
    lastBuilding = last;
    flashHint(`${boxCount(made.length)} pasted`);
  }
  // A box for each floor of a building around the pieces that were selected when the view was turned on.
  function volumesAround() {
    const grid = volumeGrid(), boxes = aroundIds.map(id => roots.get(id)).filter(r => r && !r.userData.deleted).map(r => boxOf(r, true)?.slice()).filter(Boolean);
    const floors = grid && floorsAround(boxes, grid);
    if (!floors) { flashHint('Select the building\'s pieces first, then turn this view on'); return; }
    const id = newBuilding();
    addVolumes(floors.map((f, k) => ({ box: f.boxes[0], floor: k })), id);
  }
  // ---- the selected box's six face handles: a drag stretches that face, to tile lines and levels (Alt: 8 units)
  const FACES = [['x0', 0, -1], ['x1', 0, 1], ['y0', 1, -1], ['y1', 1, 1], ['z0', 2, -1], ['z1', 2, 1]];
  const FACE_WORDS = { x0: 'West side', x1: 'East side', y0: 'South side', y1: 'North side', z0: 'Bottom', z1: 'Top' };
  const volumeHandleLayer = new THREE.Group(); world.add(volumeHandleLayer);
  const volumeHandles = new Map(FACES.map(([key]) => {
    const material = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), material);
    mesh.renderOrder = 9; mesh.raycast = () => {}; mesh.userData.material = material; volumeHandleLayer.add(mesh);
    return [key, mesh];
  }));
  const volumeStems = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(36), 3)),
                                             new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthTest: false }));
  volumeStems.renderOrder = 8; volumeStems.raycast = () => {}; volumeStems.frustumCulled = false; volumeHandleLayer.add(volumeStems);
  const handleVolume = () => { const r = volumeRoots.get(selected); return volumesOn && r && !r.userData.deleted && !placing && pickedVolumes().length === 1 ? r : null; };
  // the picked no-spawn volume whose handles show: one the project moves (spawnMovable), its markers shown, nothing placed
  const spawnVolumeHandle = () => {
    const e = spawnEntry(pickedSpawn);
    return e?.record.kind === 'noSpawn' && spawnMovable(e) && spawnsShown() && projectsAvailable() && !placing && !spawnPlacing && !volumesOn
      && !lightsOn && !zonesOn && !effectsOn && !missionGizmo.dragging && spawnBoxNow(e) ? e : null;
  };
  // the box the six handles are on: the selected building's box, a picked no-spawn volume's, or in the normal view the
  // select box
  const handleBox = () => {
    const r = handleVolume();
    if (r) return volumeBox(r);
    const e = spawnVolumeHandle();
    if (e) return spawnBoxNow(e);
    return pickBox && !volumesOn && !placing && pickDrag?.kind !== 'new' ? pickBox : null;
  };
  // game point -> the view's
  const viewPoint = ([x, y, z]) => new THREE.Vector3(x, z, y);
  function facePoint(box, key) {
    const [, axis, side] = FACES.find(f => f[0] === key), p = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2];
    p[axis] = side < 0 ? box[axis] : box[axis + 3];
    return p;
  }
  // Where a face's handle is drawn: out from the face along its axis, clear of the gizmo's arrows, which reach about
  // an eighth of the camera's distance from the box's middle whatever the box's size.
  function handlePoint(box, key) {
    const [, axis, side] = FACES.find(f => f[0] === key), p = facePoint(box, key);
    const centre = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2], d = camera.position.distanceTo(viewPoint(centre));
    p[axis] = centre[axis] + side * Math.max((box[axis + 3] - box[axis]) / 2 + d * 0.035, d * 0.2);
    return p;
  }
  function updateVolumeHandles() {
    const box = volumeDrag?.kind === 'face' ? volumeBox(volumeDrag.root) : volumeDrag?.kind === 'spawn' ? volumeDrag.box : handleBox();
    volumeHandleLayer.visible = Boolean(box) && !gizmo.controls.dragging && !missionGizmo.dragging;
    pickBoxParts.move.visible = volumeHandleLayer.visible && Boolean(pickBox) && !volumesOn;
    if (!volumeHandleLayer.visible) { if (volumeHover) hoverVolumeHandle(null); return; }
    const lit = volumeDrag?.key ?? pickDrag?.key ?? (pickDrag?.kind === 'move' ? 'move' : volumeHover), stems = volumeStems.geometry.attributes.position;
    if (pickBoxParts.move.visible) {
      pickBoxParts.move.position.copy(viewPoint(pickMovePoint()));
      pickBoxParts.moveMaterial.color.setHex(lit === 'move' ? 0xffe27a : 0x96e5d7);
      scaleMarker(pickBoxParts.move, camera, pickBoxParts.move.position);
    }
    let n = 0;
    for (const [key, mesh] of volumeHandles) {
      mesh.position.copy(viewPoint(handlePoint(box, key)));
      mesh.userData.material.color.setHex(key === lit ? 0xffe27a : 0xffffff);
      scaleMarker(mesh, camera, mesh.position);
      const from = viewPoint(facePoint(box, key));
      stems.setXYZ(n++, from.x, from.y, from.z); stems.setXYZ(n++, mesh.position.x, mesh.position.y, mesh.position.z);
    }
    stems.needsUpdate = true;
  }
  function volumeHandleNear(x, y) {
    const box = handleBox();
    if (!box) return null;
    const project = projector();
    return FACES.map(([key]) => { const s = project(viewPoint(handlePoint(box, key))); return s && { key, d: Math.hypot(s[0] - x, s[1] - y) }; })
      .filter(c => c && c.d <= HANDLE_PICK + 2).sort((a, b) => a.d - b.d)[0]?.key ?? null;
  }
  function hoverVolumeHandle(key) {
    if (key === volumeHover) return;
    volumeHover = key;
    renderer.domElement.style.cursor = key ? 'grab' : volumeTool || pickTool ? 'crosshair' : '';
    renderer.domElement.title = !key ? '' : key === 'move' ? 'Drag to move the box over the ground'
      : volumesOn ? `${FACE_WORDS[key]}: drag to stretch the box (to tile lines and levels; Alt for steps of 8)`
        : spawnVolumeHandle() ? `${FACE_WORDS[key]}: drag to stretch the no-spawn volume (to tile lines and levels; Alt for steps of 8)` : `${FACE_WORDS[key]}: drag to stretch the box`;
  }
  // Where the pointer's ray comes nearest a line through `origin` along game axis `axis`: the coordinate on that axis.
  function alongAxis(clientX, clientY, origin, axis) {
    const ray = rayAt(clientX, clientY).ray, o = viewPoint(origin), d = viewPoint([axis === 0 ? 1 : 0, axis === 1 ? 1 : 0, axis === 2 ? 1 : 0]);
    const w = o.clone().sub(ray.origin), b = d.dot(ray.direction), e = d.dot(w), f = ray.direction.dot(w), den = 1 - b * b;
    if (Math.abs(den) < 1e-6) return null;
    return origin[axis] + (b * f - e) / den;
  }
  // The cursor's floors in the Buildings view (floors.js cursorStoreys): around each of the project's boxes, and the
  // map's own box being read, a yellow line at each height where a cursor floor starts over it, with the floor's
  // number at a corner for the selected ones. A box's bottom should sit on one (the panel says when it doesn't), and
  // a face dragged up or down goes to one when it is near.
  const cursorRingLayer = new THREE.Group();
  cursorRingLayer.renderOrder = 3; world.add(cursorRingLayer);
  const ringMaterials = { near: new THREE.LineBasicMaterial({ color: 0xffd84a, depthTest: false, transparent: true, opacity: 0.95 }),
                          far: new THREE.LineBasicMaterial({ color: 0xffd84a, depthTest: false, transparent: true, opacity: 0.3 }) };
  const ringLabels = new Map();
  function ringLabel(label) {
    if (!ringLabels.has(label)) {
      const canvas = Object.assign(document.createElement('canvas'), { width: 128, height: 64 }), c = canvas.getContext('2d');
      c.fillStyle = 'rgba(20, 24, 30, 0.85)'; c.beginPath(); c.roundRect(2, 2, 124, 60, 12); c.fill();
      c.strokeStyle = '#ffd84a'; c.lineWidth = 3; c.stroke();
      c.fillStyle = '#ffd84a'; c.font = '600 30px system-ui, sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      c.fillText(label, 64, 34);
      ringLabels.set(label, new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false, transparent: true }));
    }
    return ringLabels.get(label);
  }
  let cursorRingKey = '';
  function drawCursorRings() {
    const storeys = volumesOn && data ? storeysNow() : null, items = [];
    if (storeys?.length) {
      const picked = new Set(pickedVolumes());
      for (const root of volumeRoots.values()) if (root.visible) items.push([volumeBox(root).map(v => Math.round(v)), picked.has(root) || volumeDrag?.root === root]);
      if (ownPicked) items.push([ownPicked.userData.own.box.map(v => Math.round(v)), true]);
    }
    const key = JSON.stringify(items);
    if (key === cursorRingKey) return;
    cursorRingKey = key;
    for (const child of [...cursorRingLayer.children]) { child.geometry?.dispose(); cursorRingLayer.remove(child); }
    const seen = new Set();
    for (const [box, near] of items.sort((a, b) => b[1] - a[1])) {
      const out = 14, x0 = box[0] - out, x1 = box[3] + out, y0 = box[1] - out, y1 = box[4] + out;
      for (const s of storeysOver(storeys, box)) {
        const at = `${x0},${y0},${x1},${y1},${Math.round(s.z)}`;
        if (seen.has(at)) continue;
        seen.add(at);
        const ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(
          [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([x, y]) => viewPoint([x, y, s.z]))), near ? ringMaterials.near : ringMaterials.far);
        ring.raycast = () => {}; ring.renderOrder = 3; cursorRingLayer.add(ring);
        if (!near) continue;
        const label = new THREE.Sprite(ringLabel(`${s.floor} · ${Math.round(s.z)}`));
        label.position.copy(viewPoint([x0, y0, s.z + 14])); label.scale.set(76, 38, 1); label.renderOrder = 4; label.raycast = () => {};
        cursorRingLayer.add(label);
      }
    }
  }
  // What the panel says of the cursor's floors over a box.
  function cursorLine(over, made) {
    if (!over.length) return 'No cursor volume of the map is over it: the cursor has no floors here.';
    const heights = over.map(s => Math.round(s.z)), list = heights.length > 1 ? `${heights.slice(0, -1).join(', ')} and ${heights.at(-1)}` : `${heights[0]}`;
    return `The cursor's ${plural(over.length, 'floor')} here ${over.length === 1 ? 'starts' : 'start'} at ${list} (the yellow lines)`
      + `${made ? ': the map has no cursor volumes of its own, and the Build gives it these' : ''}.`;
  }
  function snapTo(value, axis, fine, box = null) {
    const grid = volumeGrid();
    if (fine || !grid) return Math.round(value / 8) * 8;
    if (axis === 2 && box) {
      // a cursor floor's start near by wins over the level (a map's may be off the levels: the Bar's second is at 210)
      const near = storeysOver(storeysNow(), box).map(s => s.z).sort((a, b) => Math.abs(a - value) - Math.abs(b - value))[0];
      if (near != null && Math.abs(near - value) <= CURSOR_NEAR) return near;
    }
    return grid.origin[axis] + Math.round((value - grid.origin[axis]) / grid.size[axis]) * grid.size[axis];
  }
  function volumeHint(message) {
    const hint = $('dragHint');
    clearTimeout(hintTimer);
    hint.hidden = false; hint.replaceChildren(`${message} · `);
    text(hint, 'kbd', 'Esc'); hint.append(' cancels');
  }
  const tilesOf = box => { const g = volumeGrid(), s = g?.size ?? [TILE, TILE, LEVEL]; return [(box[3] - box[0]) / s[0], (box[4] - box[1]) / s[1]].map(v => Number(v.toFixed(2)) + 0); };
  // ---- the pointer in the view while it is on: a face handle stretches, the New box tool draws a footprint
  function startVolumeDrag(e) {
    // a picked no-spawn volume's face handle (the Spawns view, or the Normal button's spawn switch): stretches its box
    const sv = !volumesOn && e.button === 0 && !volumeDrag && !gizmo.controls.dragging ? spawnVolumeHandle() : null, sk = sv && volumeHandleNear(e.clientX, e.clientY);
    if (sk) {
      const before = spawnBoxNow(sv), [, axis] = FACES.find(f => f[0] === sk);
      setVolumeDrag({ kind: 'spawn', key: sk, entry: sv.key, stream: sv.stream, actor: sv.record.actor, before, box: before, pointerId: e.pointerId,
                     from: alongAxis(e.clientX, e.clientY, facePoint(before, sk), axis) });
      showPop(null);
      renderer.domElement.setPointerCapture(e.pointerId);
      renderer.domElement.style.cursor = 'grabbing';
      return true;
    }
    if (!volumesOn || placing || e.button !== 0 || volumeDrag || gizmo.controls.dragging) return false;
    const key = volumeHandleNear(e.clientX, e.clientY);
    if (key) {
      const root = handleVolume(), before = volumeBox(root), [, axis] = FACES.find(f => f[0] === key);
      // the handle stands off its face: the drag moves the face by as much as the pointer moves along the axis
      setVolumeDrag({ kind: 'face', root, key, before, pointerId: e.pointerId, from: alongAxis(e.clientX, e.clientY, facePoint(before, key), axis) });
      paintVolume(root);
    } else if (gizmo.busy()) return false;
    else if (volumeTool === 'new') {
      const grid = volumeGrid(), hit = pick(e.clientX, e.clientY)?.point;
      if (!grid) return false;
      // the level under the cursor: what is drawn there, to the nearest level; else the grid's lowest
      const level = hit ? grid.origin[2] + Math.round((hit.y - grid.origin[2]) / grid.size[2]) * grid.size[2] : grid.origin[2];
      // with a floor chosen in the Floor buttons, that floor's height in the building there
      const storey = hit ? chosenStorey(hit.x, hit.z) : null, z0 = builderMode ? (storey ? storey.z : level) : Math.max(grid.origin[2], storey ? storey.z : level);
      const at = rayAt(e.clientX, e.clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -z0), new THREE.Vector3());
      if (!at) return false;
      const tile = [0, 1].map(k => { const n = Math.floor(((k ? at.z : at.x) - grid.origin[k]) / grid.size[k]); return builderMode ? n : Math.max(0, Math.min(grid.dimensions[k] - 1, n)); });
      const building = buildingForNew() ?? newBuilding();
      const root = makeVolume(tileBox(grid, tile, tile, z0), building, floorFor(building, z0));
      setVolumeDrag({ kind: 'new', root, grid, tile, z0, building, pointerId: e.pointerId });
      refreshVolumes();
    } else return false;
    showPop(null);
    renderer.domElement.setPointerCapture(e.pointerId);
    renderer.domElement.style.cursor = 'grabbing';
    return true;
  }
  const tileBox = (grid, a, b, z0) => [grid.origin[0] + Math.min(a[0], b[0]) * grid.size[0], grid.origin[1] + Math.min(a[1], b[1]) * grid.size[1], z0,
                                      grid.origin[0] + (Math.max(a[0], b[0]) + 1) * grid.size[0], grid.origin[1] + (Math.max(a[1], b[1]) + 1) * grid.size[1],
                                      grid.unbounded ? z0 + STOREY_HEIGHT : Math.min(z0 + STOREY_HEIGHT, Math.max(z0 + grid.size[2], grid.origin[2] + grid.dimensions[2] * grid.size[2]))];
  function moveVolumeDrag(e) {
    const d = volumeDrag;
    if (d.kind === 'spawn') {
      // a no-spawn volume's side to the tile lines and levels (Alt: steps of 8), at least a quarter tile from the other;
      // drawn live (missionDragView), one undo step at the release
      const [, axis, side] = FACES.find(f => f[0] === d.key);
      const at = alongAxis(e.clientX, e.clientY, facePoint(d.before, d.key), axis);
      if (at == null || d.from == null) return;
      const least = axis === 2 ? 16 : 24, box = [...d.before];
      let value = snapTo((side < 0 ? d.before[axis] : d.before[axis + 3]) + at - d.from, axis, e.altKey);
      if (side < 0) { value = Math.min(value, d.before[axis + 3] - least); box[axis] = value; }
      else { value = Math.max(value, d.before[axis] + least); box[axis + 3] = value; }
      if (box.every((v, k) => v === d.box[k])) return;
      d.box = box;
      setMissionDragView(d.stream === 'copy' ? editedCopies(d.actor, { box }) : editedSpawns(d.actor, { box }));
      refreshSpawnMarkers();
      volumeHint(`${FACE_WORDS[d.key]} at ${Math.round(value)}: ${boxWords(box)}`);
      return;
    }
    if (d.kind === 'face') {
      const [, axis, side] = FACES.find(f => f[0] === d.key);
      const at = alongAxis(e.clientX, e.clientY, facePoint(d.before, d.key), axis);
      if (at == null || d.from == null) return;
      const least = axis === 2 ? 16 : 24, box = [...d.before];
      let value = snapTo((side < 0 ? d.before[axis] : d.before[axis + 3]) + at - d.from, axis, e.altKey, d.before);
      if (side < 0) { value = Math.min(value, d.before[axis + 3] - least); box[axis] = value; }
      else { value = Math.max(value, d.before[axis] + least); box[axis + 3] = value; }
      setVolumeBox(d.root, box);
      const [tx, ty] = tilesOf(box);
      volumeHint(`${FACE_WORDS[d.key]} at ${Math.round(value)}: ${tx} by ${ty} tiles, ${Math.round(box[5] - box[2])} high`);
      volumePanel();
    } else {
      const at = rayAt(e.clientX, e.clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -d.z0), new THREE.Vector3());
      if (!at) return;
      const tile = [0, 1].map(k => { const n = Math.floor(((k ? at.z : at.x) - d.grid.origin[k]) / d.grid.size[k]); return builderMode ? n : Math.max(0, Math.min(d.grid.dimensions[k] - 1, n)); });
      const box = tileBox(d.grid, d.tile, tile, d.z0);
      setVolumeBox(d.root, box);
      const [tx, ty] = tilesOf(box);
      volumeHint(`New box: ${tx} by ${ty} tiles at height ${Math.round(d.z0)}`);
    }
  }
  function endVolumeDrag(keep) {
    const d = volumeDrag;
    if (!d) return false;
    setVolumeDrag(null);
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
    renderer.domElement.style.cursor = volumeTool ? 'crosshair' : '';
    if (d.kind === 'spawn') {
      setMissionDragView(null);
      const changed = d.box.some((v, k) => Math.abs(v - d.before[k]) > 1e-6), hint = `No-spawn volume ${boxWords(d.box)}`;
      if (!(keep && changed && (d.stream === 'copy' ? editSpawnCopy(d.actor, { box: d.box }, hint) : editBaseSpawn(d.actor, { box: d.box }, hint)))) {
        refreshSpawnMarkers(); restingHint();
      }
      return true;
    }
    if (d.kind === 'face') {
      const after = volumeBox(d.root);
      setVolumeBox(d.root, d.before);
      if (keep && after.some((v, k) => Math.abs(v - d.before[k]) > 1e-6)) recordVolumes([d.root], () => setVolumeBox(d.root, after));
    } else {
      const box = volumeBox(d.root), floor = d.root.userData.volume.floor;
      // the preview goes; the box is made as one undo step
      for (const child of d.root.children) child.geometry.dispose();
      volumeLayer.remove(d.root); volumeRoots.delete(d.root.userData.source.id);
      if (keep) { addVolumes([{ box, floor }], d.building); setVolumeTool(null); }
      else if (!liveVolumes().some(r => r.userData.volume.building === d.building)) buildingMeta.delete(d.building);
    }
    restingHint(); editChanged();
    return true;
  }
  function setVolumeTool(tool) {
    setVolumeToolValue(volumesOn ? tool : null);
    renderer.domElement.style.cursor = volumeTool ? 'crosshair' : '';
    $('volumeNew').classList.toggle('on', volumeTool === 'new');
    if (volumeTool === 'new') { clearTimeout(hintTimer); const hint = $('dragHint'); hint.hidden = false; hint.replaceChildren('New box: drag over the tiles it is to cover · '); text(hint, 'kbd', 'Esc'); hint.append(' cancels'); }
    else restingHint();
  }
  // A click in the view while it is on: the box under it, never a piece or a light.
  function volumeClick(e) {
    if (volumeTool) return;
    const add = e.ctrlKey || e.shiftKey || e.metaKey;
    const hit = rayAt(e.clientX, e.clientY).intersectObjects([...[...volumeRoots.values()].filter(r => r.visible).map(r => r.userData.fill),
                                                              ...ownVolumeLayer.children.filter(c => c.userData.own)])[0];
    if (hit?.object.userData.volumeId) { setOwnPickedValue(null); select(hit.object.userData.volumeId, add); }
    // one of the map's own: shown in the panel, read only
    else if (hit) { if (selected) select(null); setOwnPicked(hit.object); }
    else if (!add) { if (selected) select(null); setOwnPicked(null); }
  }
  // ---- the panel: what the view is for and its tools, and the selected boxes' building and floor
  const volumeUi = { root: $('volumePanel'), picked: $('volumePicked'), title: $('volumeTitle'), bottom: $('volumeBottom'), top: $('volumeTop'),
                     building: $('volumeBuilding'), name: $('volumeName'), kind: $('volumeKind'), floor: $('volumeFloor'), note: $('volumeNote'), warn: $('volumeWarn') };
  let volumeCountKey = '', volumeCountText = '';
  // How many pieces the boxes list, and of them how many cut down (worked out when nothing is being dragged).
  function volumeCounts(targets) {
    const key = `${buildingsVersion}|${editedKey()}|${targets.map(r => r.userData.source.id).join()}`;
    if (key === volumeCountKey) return volumeCountText;
    const boxes = targets.map(r => { const b = volumeBox(r); return { boxes: [{ min: b.slice(0, 3), max: b.slice(3, 6) }] }; });
    let listed = 0, cut = 0;
    for (const root of roots.values()) {
      const o = root.userData.source;
      if (root.userData.deleted || o.cover || o.hidden || !LISTED_CLASSES.has(o.actorClass)) continue;
      const rough = boxOf(root);
      if (!rough || !touchedFloors(rough, boxes).length) continue;
      listed++;
      if (o.cutout && projectListings(root).some(l => l.cutdownFloor)) cut++;
    }
    volumeCountKey = key;
    volumeCountText = `${plural(listed, 'piece')} of the map ${listed === 1 ? 'stands' : 'stand'} in ${targets.length === 1 ? 'it' : 'them'}${cut ? `, ${cut} cutting down` : ''}.`;
    return volumeCountText;
  }
  function volumePanel() {
    // in the normal view: only for a building selected there, without the view's own tools
    const shown = volumesOn || (volumeRoots.has(selected) && pickedVolumes().length > 0) || (Boolean(ownPicked) && !selected);
    volumeUi.root.hidden = !shown;
    if (!shown) return;
    for (const part of [$('volumeIntro').parentElement, $('volumeOwn'), $('volumeNew').parentElement]) part.style.display = volumesOn ? '' : 'none';
    $('volumeHead').replaceChildren(volumesOn ? 'Buildings view ' : 'Building ');
    text($('volumeHead'), 'span', volumesOn ? 'pieces are locked' : 'picked whole');
    const targets = pickedVolumes(), one = targets.length === 1 ? targets[0] : null, grid = volumeGrid();
    const live = liveVolumes().length, ownCount = (data?.buildings ?? []).filter(b => !mapEditable(b) && b.floors?.length).length;
    $('volumeHow').textContent = live && volumesOn ? 'Click a box to select it; the gizmo moves it, the white dots stretch it.' : '';
    $('volumeIntro').textContent = live ? `${boxCount(live)} in ${plural(buildings.length, 'building')}${ownCount ? `; ${ownCount} more of the map's own, in grey` : ''}.`
      : 'A building is boxes laid over its floors: the game hides the pieces in the upper boxes when a soldier is inside, and cuts the walls down. Draw one with New box.';
    $('volumeOwn').textContent = ownCount ? `${ownCount === 1 ? 'One building of the map stays' : `${ownCount} buildings of the map stay`} as the map has `
      + `${ownCount === 1 ? 'it' : 'them'}, in grey: a van's goes with its van${data.exporterVersion >= 21 ? '' : ' (this export predates editing the map\'s buildings: prepare the map again)'}. `
      + 'Click a grey box to read it.' : '';
    mapChangesList();
    $('volumeAround').hidden = !aroundIds.length;
    $('volumeAround').textContent = `Boxes around the ${aroundIds.length === 1 ? 'piece' : `${aroundIds.length} pieces`} selected`;
    const own = ownPicked?.userData.own, readOnly = !targets.length && Boolean(own);
    volumeUi.picked.hidden = !targets.length && !own;
    for (const input of [volumeUi.bottom, volumeUi.top, volumeUi.building, volumeUi.name, volumeUi.kind, volumeUi.floor]) input.disabled = readOnly;
    $('volumeCopy').hidden = $('volumeDelete').hidden = readOnly; volumeUi.kind.parentElement.hidden = readOnly;
    $('volumeRestore').hidden = true;
    $('volumePrefab').hidden = readOnly;      // floor boxes alone are saveable too
    volumeUi.name.parentElement.firstChild.textContent = readOnly ? 'Floor volume' : 'Name';
    if (readOnly) {
      // one of the map's own boxes: what the map saves of it
      const b = own.box, g = grid?.size ?? [TILE, TILE, LEVEL], t = k => Number(((b[k + 3] - b[k]) / g[k]).toFixed(2)) + 0;
      const floor = own.building.floors[own.floor], members = floor.members ?? [], cut = members.filter(m => m.cutdownFloor).length;
      volumeUi.title.textContent = `The map's box · ${t(0)} by ${t(1)} tiles, ${Math.round(b[5] - b[2])} high`;
      volumeUi.bottom.value = Math.round(b[2] * 100) / 100; volumeUi.top.value = Math.round(b[5] * 100) / 100;
      volumeUi.building.replaceChildren(Object.assign(document.createElement('option'), { value: '', textContent: short(own.building.name) }));
      volumeUi.floor.value = own.floor + 1; volumeUi.name.value = own.volume ? short(own.volume) : '';
      volumeUi.note.textContent = `Floor ${own.floor + 1} of ${own.building.floors.length} of the map's own ${short(own.building.name)}`
        + `${floor.boxes.length > 1 ? `, one of this floor's ${floor.boxes.length} boxes` : ''}. The map lists ${plural(members.length, 'piece')} on this floor`
        + `${cut ? `, ${cut} cutting down` : ''}. It is shown to be read: ${own.building.van ? 'a van\'s own building goes with its van' : 'this building stays as the map has it'}.`
        + `${volumesOn ? '' : ' Selected with its pieces and copied (Ctrl+C, Ctrl+V), the copy gets a building of your own with the same boxes; this one stays where it is.'}`
        + `${storeysNow() ? ` ${cursorLine(storeysOver(storeysNow(), b), false)}` : ''}`;
      volumeUi.warn.hidden = true;
      return;
    }
    if (!targets.length) return;
    const boxes = targets.map(volumeBox), same = get => { const values = new Set(targets.map(get)); return values.size === 1 ? [...values][0] : null; };
    const [tx, ty] = one ? tilesOf(boxes[0]) : [0, 0];
    volumeUi.title.textContent = one ? `Box · ${tx} by ${ty} tiles, ${Math.round(boxes[0][5] - boxes[0][2])} high` : `${targets.length} boxes`;
    const whole = !volumesOn;
    const active = document.activeElement, put = (input, value) => { if (active !== input) input.value = value ?? ''; };
    put(volumeUi.bottom, one ? Math.round(boxes[0][2] * 100) / 100 : ''); put(volumeUi.top, one ? Math.round(boxes[0][5] * 100) / 100 : '');
    volumeUi.bottom.disabled = volumeUi.top.disabled = !one || whole;
    volumeUi.building.disabled = volumeUi.floor.disabled = whole;
    const building = same(r => r.userData.volume.building), meta = building ? buildingMeta.get(building) : null;
    const options = [...buildingMeta].filter(([id]) => liveVolumes().some(r => r.userData.volume.building === id))
      .map(([id, m], i) => Object.assign(document.createElement('option'), { value: id, textContent: m.name || `Building ${i + 1}` }));
    if (!building) options.unshift(Object.assign(document.createElement('option'), { value: '', textContent: 'Several', disabled: true }));
    options.push(Object.assign(document.createElement('option'), { value: 'new', textContent: 'New building' }));
    if (active !== volumeUi.building) { volumeUi.building.replaceChildren(...options); volumeUi.building.value = building ?? ''; }
    put(volumeUi.name, meta?.name ?? ''); volumeUi.name.disabled = volumeUi.kind.disabled = !meta;
    if (active !== volumeUi.kind) volumeUi.kind.value = meta?.kind ?? 'building';
    const floor = same(r => r.userData.volume.floor);
    put(volumeUi.floor, floor == null ? '' : floor + 1);
    const dragging = gizmo.controls.dragging || volumeDrag;
    const notes = whole ? ['Here the building is picked whole, to move, turn, copy or delete with its pieces. Its boxes are stretched and set to floors in the Buildings view (Shift+B).'] : [];
    const counted = same(r => r.userData.volume.effective);
    if (floor != null && counted != null && counted !== floor) notes.push(`Counted as floor ${counted + 1}: its building has no box on a floor below.`);
    if (meta?.map) {
      // one of the map's own buildings: whether the project changed it, and its notched volumes
      const changed = mapEdits().changed.has(building);
      notes.push(`One of the map's own buildings (${short(meta.map.actor)}): ${changed ? 'changed, so the Build edits it in place' : 'as the map has it'}.`);
      $('volumeRestore').hidden = !changed;
      const plain = new Map(meta.map.floors.flatMap(f => f.volumes.map((v, n) => [short(v), f.plain?.[n] !== false])));
      const notched = targets.filter(r => r.userData.volume.origin && r.userData.volume.home === building && plain.get(r.userData.volume.origin) === false);
      if (notched.length) notes.push(`${one ? 'This box is' : `${plural(notched.length, 'box')} of these are`} a notched floor volume of the map's, drawn by its outer box: `
        + 'moved, it keeps its notches; stretched, the Build puts a plain box in its place, the notches filled.');
    }
    if (!dragging) notes.push(volumeCounts(targets));
    const storeys = storeysNow(), misses = [];
    if (storeys && one) notes.push(cursorLine(storeysOver(storeys, boxes[0]), storeys.some(s => s.made)));
    if (storeys && !dragging) for (const box of boxes) {
      const over = storeysOver(storeys, box);
      if (cursorMiss(box, over)) misses.push(`${one ? 'This box' : 'A box'} starts at ${Math.round(box[2])}, away from where the cursor's floors start here `
        + `(${over.map(s => Math.round(s.z)).join(', ')}): the mouse wheel would not stop at this storey. Start it within ${CURSOR_NEAR} units of one.`);
    }
    volumeUi.note.textContent = notes.join(' ');
    const problems = new Set();
    if (!dragging && grid) for (const b of buildings) {
      if (!targets.some(r => r.userData.volume.building === b.id)) continue;
      const authored = [...roots.values()].some(r => {
        if (r.userData.deleted || !r.userData.source.added) return false;
        projectListings(r);
        return r.userData.authoredFloors?.has(b.id);
      });
      const others = allBuildings().filter(x => x.project !== b && x.id !== PROJECT_BUILDING + b.id && !(buildingMeta.get(b.id)?.map && x.id === buildingMeta.get(b.id).map.id));
      for (const p of buildingProblems(b, grid, others, authored, (k, n) => freshBox(b, k, n))) problems.add(`${b.name || 'the building'}: ${p}`);
    }
    const said = [problems.size ? `This may behave oddly in the game (the Build builds it and warns): ${[...problems].join('; ')}.` : '', ...new Set(misses)].filter(Boolean);
    volumeUi.warn.hidden = !said.length;
    volumeUi.warn.textContent = said.join(' ');
  }
  function typedHeight(input, index) {
    const root = pickedVolumes().length === 1 ? pickedVolumes()[0] : null, value = Number(input.value);
    if (!root || input.value === '' || !Number.isFinite(value)) { volumePanel(); return; }
    const box = volumeBox(root);
    box[index] = value;
    if (box[5] - box[2] < 16) { flashHint('A box is at least 16 units high'); input.value = volumeBox(root)[index]; return; }
    recordVolumes([root], () => setVolumeBox(root, box));
  }
  // (a field lets go once its change is made, so the keys work in the view again)
  volumeUi.bottom.onchange = () => { typedHeight(volumeUi.bottom, 2); volumeUi.bottom.blur(); };
  volumeUi.top.onchange = () => { typedHeight(volumeUi.top, 5); volumeUi.top.blur(); };
  volumeUi.building.onchange = () => {
    const targets = pickedVolumes(), value = volumeUi.building.value;
    if (!targets.length || !value) return;
    recordVolumes(targets, () => {
      const id = value === 'new' ? newBuilding() : value;
      for (const r of targets) r.userData.volume.building = id;
      lastBuilding = id;
    });
    volumeUi.building.blur();
  };
  const editMeta = change => {
    const id = pickedVolumes()[0]?.userData.volume.building;
    if (id && buildingMeta.has(id)) recordVolumes([], () => Object.assign(buildingMeta.get(id), change));
  };
  volumeUi.name.onchange = () => { editMeta({ name: volumeUi.name.value.trim().slice(0, 60) }); volumeUi.name.blur(); };
  volumeUi.kind.onchange = () => { editMeta({ kind: volumeUi.kind.value }); volumeUi.kind.blur(); };
  volumeUi.floor.max = String(BUILDING_FLOORS_MAX);      // (the script's and the compiler's limit: review finding 34)
  volumeUi.floor.onchange = () => {
    const targets = pickedVolumes(), n = Number(volumeUi.floor.value);
    if (!targets.length || !Number.isInteger(n) || n < 1 || n > BUILDING_FLOORS_MAX) { volumePanel(); return; }
    recordVolumes(targets, () => { for (const r of targets) r.userData.volume.floor = n - 1; });
    volumeUi.floor.blur();
  };
  // Restore the map's (map buildings plan, section 1): a changed or deleted building of the map back as the map has
  // it, its boxes made again from the export and its record gone, as one undo step. (A deleted one has no box left to
  // click: the Buildings view lists the changed and deleted ones, mapChangesList.)
  function mapRestoreChange(ids) {
    const targets = liveVolumes().filter(r => ids.includes(r.userData.volume.building)), made = [];
    for (const id of ids) {
      const e = buildingMeta.get(id)?.map;
      if (e) mapFloors(e).forEach((f, k) => f.boxes.forEach((box, n) => { const r = makeVolume(box, id, k, f.volumes[n]); r.userData.deleted = true; made.push(r); }));
    }
    const before = ids.map(id => ({ ...buildingMeta.get(id) }));
    const after = before.map(m => ({ ...m, name: short(m.map.actor), kind: mapKind(m.map) }));
    const put = (gone, back, metas) => { for (const r of gone) r.userData.deleted = true; for (const r of back) r.userData.deleted = false;
                                         ids.forEach((id, k) => buildingMeta.set(id, { ...metas[k] })); };
    return { redo: () => put(targets, made, after), undo: () => put(made, targets, before), count: ids.length };
  }
  function restoreMapBuildings(ids) {
    ids = ids.filter(id => buildingMeta.get(id)?.map);
    if (!ids.length) return;
    const change = mapRestoreChange(ids), picks = gizmo.picks();
    gizmo.record({ redo: () => { change.redo(); gizmo.setSelection([]); },
                   undo: () => { change.undo(); gizmo.setSelection(picks.ids.filter(id => volumeRoots.get(id) ? !volumeRoots.get(id).userData.deleted : allRoots.has(id)), picks.active); } });
    flashHint(`${ids.length === 1 ? short(buildingMeta.get(ids[0]).map.actor) : plural(ids.length, 'building')} as the map has ${ids.length === 1 ? 'it' : 'them'} · Ctrl+Z undoes it`);
  }
  $('volumeRestore').onclick = () => { const b = pickedVolumes()[0]?.userData.volume.building; if (b) restoreMapBuildings([b]); };
  // The Buildings view's list of the map's buildings the project changed or deleted, each with Restore.
  let mapChangesKey = '';
  function mapChangesList() {
    const edits = mapEdits(), list = $('volumeChanged');
    const ids = volumesOn ? [...edits.changed, ...edits.gone].sort() : [];
    const key = ids.map(id => `${id}:${edits.gone.has(id)}`).join();
    if (key === mapChangesKey) return;
    mapChangesKey = key;
    list.hidden = !ids.length;
    list.replaceChildren();
    if (!ids.length) return;
    text(list, 'div', 'The map\'s buildings this project changes:', 'lightnote');
    for (const id of ids) {
      const row = text(list, 'div', '', 'row');
      text(row, 'span', `${short(buildingMeta.get(id).map.actor)} · ${edits.gone.has(id) ? 'deleted' : 'changed'}`);
      const button = text(row, 'button', 'Restore the map\'s');
      button.type = 'button';
      button.title = 'Back as the map has it: its boxes made again, its name and kind the map\'s (Ctrl+Z undoes it)';
      button.onclick = () => restoreMapBuildings([id]);
    }
  }
  $('volumeNew').onclick = () => setVolumeTool(volumeTool === 'new' ? null : 'new');
  $('volumeAround').onclick = volumesAround;
  $('volumeCopy').onclick = () => (volumesOn ? copyVolumes() : copySelection());
  $('volumeDelete').onclick = () => (volumesOn ? deleteVolumes() : deleteSelection());
  // The Normal button's Floor boxes switch: the project's boxes drawn in the normal view. A click on a box's edge, or the select
  // box, then takes its whole building with whatever else is picked; it moves by whole tiles and turns by quarter turns,
  // is copied with its pieces as a new building, and deleted. Stretching a box and its floor stay the Buildings view's.
  function setBoxesShown(on) {
    setBoxesShownValue(Boolean(on) && data?.scope === 'map' && !data.preview);
    syncLights(); volumePanel();
  }
  $('boxesToggle').onchange = e => { setBoxesShown(e.target.checked); e.target.blur(); };
  // The box whose edge is under a screen point, in the normal view (a box's sides are see-through: the pieces inside
  // are picked through them).
  function pickBoxEdge(x, y) {
    if (!boxesShown || volumesOn || lightsOn) return null;
    const project = projector();
    let best = null;
    const near = (b, hit) => {
      const corner = ([i, j, k]) => project(viewPoint([b[i * 3], b[1 + j * 3], b[2 + k * 3]]));
      for (const [lo, hi] of BOX_EDGES) {
        const p = corner(lo), q = corner(hi);
        if (!p || !q) continue;
        const dx = q[0] - p[0], dy = q[1] - p[1], length = dx * dx + dy * dy;
        const t = length ? Math.max(0, Math.min(1, ((x - p[0]) * dx + (y - p[1]) * dy) / length)) : 0;
        const d = Math.hypot(p[0] + t * dx - x, p[1] + t * dy - y);
        if (d <= 6 && (!best || d < best.d)) best = { d, ...hit };
      }
    };
    // the project's boxes first: one of the map's is taken only where it is nearer
    for (const root of volumeRoots.values()) if (root.visible) near(volumeBox(root), { id: root.userData.source.id });
    for (const mesh of ownVolumeLayer.children) if (mesh.userData.own) near(mesh.userData.own.box, { own: mesh });
    return best;
  }
  const pickVolumeEdge = (x, y) => pickBoxEdge(x, y)?.id ?? null;
  // One of the map's own buildings picked in the normal view: with Ctrl or Shift, added to what is selected (or taken
  // out again); alone, shown to be read.
  function pickOwn(mesh, add) {
    const building = mesh.userData.own.building;
    if (!add) select(null);
    if (add && ownSet.has(building)) ownSet.delete(building); else ownSet.add(building);
    setOwnPickedValue(ownSet.has(building) && !selected ? mesh : null);
    refreshVolumes(); volumePanel();
    if (ownSet.has(building)) flashHint(`${short(building.name)}, a building of the map: copied with its pieces, the copy gets a building of your own`);
  }
  $('volumeDone').onclick = () => setVolumesShown(false);
  $('editBuildings').onclick = () => data && setVolumesShown(!volumesOn);
  // Box select (the user, 11 November 2026: "a better way of selecting many items at once"): in the normal view a box
  // is drawn over the ground (the tool strip's button, T), stretched by the six face handles a building's box has and
  // moved by the dot in its middle. Select (Enter) takes every piece whose middle is inside, with its group and linked
  // pieces whole as a click takes them; Shift+Enter adds them to the selection. Only what is drawn is taken (a floor
  // hidden by the Floor buttons is not), and never a streamed patch's piece. The box is the tool's alone: it is not
  // saved, and no undo step.
  const PICK_SLACK = 4;      // a wall on the box's side counts as inside
  const PICK_DROP = 32;      // the box starts this far under the level it is drawn on: the floor under a house comes too
  const pickBoxLayer = new THREE.Group(); pickBoxLayer.visible = false; world.add(pickBoxLayer);
  const pickBoxParts = (() => {
    const fill = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0x96e5d7, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false }));
    const line = new THREE.LineSegments(new THREE.EdgesGeometry(fill.geometry), new THREE.LineBasicMaterial({ color: 0x96e5d7, transparent: true, opacity: 0.95, depthWrite: false }));
    const through = new THREE.LineSegments(line.geometry, new THREE.LineBasicMaterial({ color: 0x96e5d7, transparent: true, opacity: 0.35, depthWrite: false, depthTest: false }));
    // what Select would take: each piece's box in white
    const hits = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.8, depthTest: false }));
    const moveMaterial = new THREE.MeshBasicMaterial({ color: 0x96e5d7, depthTest: false, transparent: true });
    const move = new THREE.Mesh(new THREE.SphereGeometry(0.7, 16, 12), moveMaterial);
    for (const part of [fill, line, through, hits, move]) { part.raycast = () => {}; part.renderOrder = 7; part.frustumCulled = false; pickBoxLayer.add(part); }
    move.renderOrder = 9;
    return { fill, line, through, hits, move, moveMaterial };
  })();
  // the twelve edges of a box, as pairs of corners (each a 0 or 1 for x, y and z)
  const BOX_EDGES = [];
  for (let axis = 0; axis < 3; axis++) for (let u = 0; u < 2; u++) for (let v = 0; v < 2; v++) {
    const lo = [0, 0, 0], hi = [0, 0, 0], [p, q] = [0, 1, 2].filter(k => k !== axis);
    lo[p] = hi[p] = u; lo[q] = hi[q] = v; hi[axis] = 1;
    BOX_EDGES.push([lo, hi]);
  }
  // The pieces Select can take, each with its drawn box and that box's middle (worked out once for a drag).
  function pickCandidates() {
    if (!pickCentres) {
      setPickCentres([]);
      for (const root of lightsOn || effectsOn ? [] : roots.values()) {
        const o = root.userData.source;
        if (root.userData.deleted || !root.visible || isStream(o)) continue;
        const b = boxOf(root);
        if (b) pickCentres.push({ id: o.id, box: b.slice(), at: [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2] });
      }
      // with the lights shown, the lights that can be edited; with View options' Floor boxes, the project's boxes
      if (lightsShown) for (const root of lightRoots.values()) {
        const o = root.userData.source, e = root.matrix.elements;
        if (!root.visible || root.userData.deleted || isStream(o) || lightViewOnly(o)) continue;
        pickCentres.push({ id: o.id, kind: 'light', at: [e[12], e[14], e[13]], box: [e[12] - 14, e[12] + 14, e[14] - 14, e[14] + 14, e[13] - 14, e[13] + 14] });
      }
      // with the markers drawn (the Effects view, where only they are taken, or the Normal button's switch), the
      // effects, sounds and flares the editor changes (effects and sounds plan, FX3b)
      if (effectsShown() && !lightsOn) for (const root of effectRoots.values()) {
        const o = root.userData.source, e = root.matrix.elements;
        if (!root.visible || root.userData.deleted || isStream(o)) continue;
        if (effectViewOnly(o, 'move') && effectViewOnly(o, 'copy') && effectViewOnly(o, 'delete')) continue;
        pickCentres.push({ id: o.id, kind: o.kind, at: [e[12], e[14], e[13]], box: [e[12] - 14, e[12] + 14, e[14] - 14, e[14] + 14, e[13] - 14, e[13] + 14] });
      }
      if (boxesShown && !lightsOn && !effectsOn) for (const root of volumeRoots.values()) {
        if (!root.visible) continue;
        const b = volumeBox(root);
        pickCentres.push({ id: root.userData.source.id, kind: 'box', at: [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2], box: [b[0], b[3], b[1], b[4], b[2], b[5]] });
      }
      // and the map's own boxes: taken to be copied
      if (boxesShown && !lightsOn && !effectsOn) ownVolumeLayer.children.filter(c => c.userData.own).forEach((mesh, n) => {
        const b = mesh.userData.own.box;
        pickCentres.push({ id: `own:${n}`, kind: 'own', mesh, at: [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2], box: [b[0], b[3], b[1], b[4], b[2], b[5]] });
      });
    }
    return pickCentres;
  }
  // The box and what it would take, drawn again; `recount` after anything that may have moved or hidden a piece.
  function refreshPickBox(recount = false) {
    if (recount) setPickCentres(null);
    const b = pickBox, parts = pickBoxParts, button = $('editBox');
    pickBoxLayer.visible = Boolean(b);
    $('boxBar').hidden = !b;
    button.classList.toggle('on', pickTool || Boolean(b)); button.setAttribute('aria-pressed', pickTool || Boolean(b));
    if (!pickDrag) kindButton();      // Select all of a kind narrows to a box drawn
    if (!b) { setPickHits([]); return; }
    for (const part of [parts.fill, parts.line, parts.through]) {
      part.position.set((b[0] + b[3]) / 2, (b[2] + b[5]) / 2, (b[1] + b[4]) / 2);
      part.scale.set(Math.max(1, b[3] - b[0]), Math.max(1, b[5] - b[2]), Math.max(1, b[4] - b[1]));
    }
    setPickHits(pickCandidates().filter(c => c.at.every((v, k) => v >= b[k] - PICK_SLACK && v <= b[k + 3] + PICK_SLACK)));
    const points = new Float32Array(pickHits.length * 72);
    let n = 0;
    for (const { box } of pickHits) for (const edge of BOX_EDGES) for (const [i, j, k] of edge) {
      points[n++] = box[i]; points[n++] = box[4 + k]; points[n++] = box[2 + j];
    }
    parts.hits.geometry.dispose();
    parts.hits.geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(points, 3));
    $('boxBarText').textContent = pickHits.length ? `${pickWords()} inside` : lightsOn ? 'No light inside' : effectsOn ? 'No effect or sound inside' : 'No piece inside';
    $('boxTake').disabled = $('boxAdd').disabled = !pickHits.length;
  }
  // what the box holds, in words: pieces, lights and floor boxes
  function pickWords() {
    const of = kind => pickHits.filter(c => c.kind === kind).length;
    const lights = of('light'), boxes = of('box') + of('own'), effects = of('effect'), sounds = of('sound'), flares = of('flare');
    const n = pickHits.length - lights - boxes - effects - sounds - flares;
    const parts = [n && plural(n, 'piece'), lights && plural(lights, 'light'), boxes && `${boxes} floor ${boxes === 1 ? 'box' : 'boxes'}`,
                   effects && plural(effects, 'effect'), sounds && plural(sounds, 'sound'), flares && plural(flares, 'lens flare')].filter(Boolean);
    return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0];
  }
  const pickMovePoint = () => [(pickBox[0] + pickBox[3]) / 2, (pickBox[1] + pickBox[4]) / 2, (pickBox[2] + pickBox[5]) / 2];
  function pickMoveNear(x, y) {
    if (!pickBox || volumesOn || placing) return false;
    const s = projector()(viewPoint(pickMovePoint()));
    return Boolean(s) && Math.hypot(s[0] - x, s[1] - y) <= HANDLE_PICK + 4;
  }
  // where the pointer's ray meets the level at height z (a point of the view: x, the height, y)
  const levelPoint = (e, z) => rayAt(e.clientX, e.clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -z), new THREE.Vector3());
  function setPickTool(on) {
    if (on && (!data || placing)) return;
    if (on && volumesOn) setVolumesShown(false);
    if (on && zonesOn) setZonesShown(false);     // box select takes pieces, which the Landing zones view doesn't
    // (the Effects view stays: there the box takes its markers only, as the Lights view's takes lights)
    setPickToolValue(Boolean(on));
    if (!pickTool) { setPickBoxValue(null); setPickDrag(null); }
    renderer.domElement.style.cursor = pickTool ? 'crosshair' : '';
    refreshPickBox(true); restingHint();
  }
  const stopPickBox = () => { if (pickTool || pickBox) setPickTool(false); };
  function startPickDrag(e) {
    if (volumesOn || placing || e.button !== 0 || pickDrag || gizmo.controls.dragging || !(pickTool || pickBox)) return false;
    const key = pickBox ? volumeHandleNear(e.clientX, e.clientY) : null;
    if (key) {
      const [, axis] = FACES.find(f => f[0] === key);
      setPickDrag({ kind: 'face', key, before: [...pickBox], pointerId: e.pointerId, from: alongAxis(e.clientX, e.clientY, facePoint(pickBox, key), axis) });
    } else if (pickMoveNear(e.clientX, e.clientY)) {
      const level = pickMovePoint()[2], at = levelPoint(e, level);
      if (!at) return false;
      setPickDrag({ kind: 'move', before: [...pickBox], pointerId: e.pointerId, from: [at.x, at.z], level });
    } else if (gizmo.busy() || !pickTool) return false;
    else {
      // drawn on what is under the pointer (else the grid's lowest level), from a little under it up to the grid's top
      const grid = volumeGrid(), hit = pick(e.clientX, e.clientY)?.point;
      const work = builderMode ? builderBounds().map(([, box]) => box) : [];
      const level = Math.min(hit ? hit.y : grid ? grid.origin[2] : 0, ...work.map(b => b[2])), at = levelPoint(e, level);
      if (!at) return false;
      const top = Math.max(level + STOREY_HEIGHT, grid ? grid.origin[2] + grid.dimensions[2] * grid.size[2] : level + 4 * STOREY_HEIGHT, ...work.map(b => b[5]));
      setPickDrag({ kind: 'new', before: pickBox, pointerId: e.pointerId, from: [at.x, at.z], level, top });
      setPickBoxValue([at.x, at.z, level - PICK_DROP, at.x, at.z, top].map(Math.round));
    }
    showPop(null);
    renderer.domElement.setPointerCapture(e.pointerId);
    renderer.domElement.style.cursor = 'grabbing';
    refreshPickBox(true);
    return true;
  }
  function movePickDrag(e) {
    const d = pickDrag;
    if (d.kind === 'face') {
      const [, axis, side] = FACES.find(f => f[0] === d.key), at = alongAxis(e.clientX, e.clientY, facePoint(d.before, d.key), axis);
      if (at == null || d.from == null) return;
      const box = [...d.before], value = Math.round((side < 0 ? d.before[axis] : d.before[axis + 3]) + at - d.from);
      if (side < 0) box[axis] = Math.min(value, d.before[axis + 3] - 8); else box[axis + 3] = Math.max(value, d.before[axis] + 8);
      setPickBoxValue(box);
    } else {
      const at = levelPoint(e, d.level);
      if (!at) return;
      if (d.kind === 'move') {
        const dx = Math.round(at.x - d.from[0]), dy = Math.round(at.z - d.from[1]);
        setPickBoxValue([d.before[0] + dx, d.before[1] + dy, d.before[2], d.before[3] + dx, d.before[4] + dy, d.before[5]]);
      } else setPickBoxValue([Math.min(d.from[0], at.x), Math.min(d.from[1], at.z), d.level - PICK_DROP, Math.max(d.from[0], at.x), Math.max(d.from[1], at.z), d.top].map(Math.round));
    }
    refreshPickBox();
    volumeHint(`Box select: ${pickHits.length ? `${pickWords()} inside` : effectsOn ? 'no effect or sound inside' : 'no piece inside'}`);
  }
  function endPickDrag(keep) {
    const d = pickDrag;
    if (!d) return false;
    setPickDrag(null);
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
    if (!keep) setPickBoxValue(d.before && [...d.before]);
    else if (d.kind === 'new') {
      // a press without a drag draws nothing: the tool waits for one
      if (pickBox[3] - pickBox[0] < 8 || pickBox[4] - pickBox[1] < 8) setPickBoxValue(d.before && [...d.before]);
      else setPickToolValue(false);
    }
    renderer.domElement.style.cursor = pickTool ? 'crosshair' : '';
    refreshPickBox(true); restingHint();
    return true;
  }
  // Select: the pieces inside become the selection (`add`: join it), and the box goes.
  function takePickBox(add = false) {
    if (!pickBox) return;
    refreshPickBox(true);
    const owns = pickHits.filter(c => c.kind === 'own'), ids = pickHits.filter(c => c.kind !== 'own').map(c => c.id), was = gizmo.picks();
    if (!ids.length && !owns.length) { flashHint(lightsOn ? 'No light is inside the box' : effectsOn ? 'No effect or sound is inside the box' : 'No piece has its middle inside the box'); return; }
    const before = add ? was.ids.filter(id => allRoots.get(id)) : [];
    stopPickBox();
    // a piece holds the pivot when there is one
    gizmo.setSelection([...new Set([...before, ...ids])], before.includes(was.active) ? was.active : ids.find(id => roots.has(id)) ?? ids[0]);
    if (!add) ownSet.clear();
    for (const c of owns) ownSet.add(c.mesh.userData.own.building);
    setOwnPickedValue(!gizmo.active && owns.length ? owns[0].mesh : null);
    select(gizmo.active, false, true);
    flashHint(`${[gizmo.selection().length && selectionWords(gizmo.selection()), ownSet.size && `${plural(ownSet.size, 'building')} of the map`].filter(Boolean).join(' and ')} selected`);
  }
  $('editBox').onclick = () => setPickTool(!(pickTool || pickBox));
  $('boxTake').onclick = () => takePickBox(false);
  $('boxAdd').onclick = () => takePickBox(true);
  $('boxAgain').onclick = () => setPickTool(true);
  $('boxCancel').onclick = stopPickBox;

  // After an edit (the edit hub, edit_hub.js).
  onHub('edit', 'buildings', () => {
    // the Buildings view: the project's buildings follow the boxes; a box is never turned
    if (data) {
      if (volumesOn && gizmo.mode === 'rotate') { gizmo.setMode('translate'); return STOP; }
      syncVolumes(); refreshVolumes(); volumePanel();
    }
  });

  return { addVolumes, allBuildings, buildingsFromVolumes, copyVolumes, deleteVolumes, drawCursorRings, endPickDrag,
           endVolumeDrag, FACES, handlePoint, hoverVolumeHandle, liveVolumes, makeVolume, mapEdits, mapIdOf,
           mapRestoreChange, movePickDrag, moveVolumeDrag, newBuilding, newBuildingId, ownVolumeLayer, pasteVolumes,
           PICK_SLACK, pickBoxEdge, pickMoveNear, pickMovePoint, pickOwn, pickVolumeEdge, recordVolumes, refreshPickBox,
           refreshVolumes, restoreMapBuildings, savedBuildings, setBoxesShown, setBuildings, setOwnPicked, setPickTool,
           setVolumeBox, setVolumesShown, setVolumeTool, spawnVolumeHandle, startPickDrag, startVolumeDrag, stopPickBox,
           takePickBox, updateVolumeHandles, viewPoint, volumeBox, volumeClick, volumeHandleNear, volumeHint,
           volumePanel };
}
