// The selection (refactor stage P9): select, which picks a piece, a light, a building's box or an effect (or nothing)
// and fills the piece panel for it, and the selected piece's marks. Here:
// - select: the views stepping aside for what is picked and the piece panel for it, its name, chips and source fields;
//   a cover block's or invisible floor's panel (showCover). Each area's own part of it (its section shown or hidden,
//   its panel, the flags chip) is run through the edit hub's select runs, where the area registers it (edit_hub.js);
// - the selected piece's marks: its highlight (refreshHighlight), a ladder's ends and its chip (ladderNow, floorPlan,
//   refreshLadder) and the grid chip of a piece the recipe snap holds (gridNow, refreshGrid), which the edit hub's
//   edit run keeps up, with the selection following the gizmo when a command changed it;
// - the pieces and lights an actor name stands for, selected and framed (selectActors: a compile report's or a
//   prefab test's actor);
// - the selection's pieces that can be copied or deleted (copyable: hidden helpers shown for inspection left out),
//   those Align lines up (copyablePieces), the floor boxes selected with pieces in the normal view (selectedBoxes)
//   and what a group can hold of the selection (groupables), which the gizmo's selection gives;
// - what some roots are, by kind, in words (selectionWords: "12 pieces, 2 lights and 1 building"), and what a
//   selected root is called in a list (rootName), plain exports at the top, before the factory: they read only
//   their arguments, the scene and the buildings' names.
//
// createSelection takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the
// selection's highlight and ladder marks, the group chip (app.js makes it, and gives it to the groups too), the panel's
// helpers, the pieces' boxes, poses and recipes, which lights and effects can only be seen, the views' switches,
// a light's glowing piece, the effect picked, the floors a piece is listed on, the buildings, the map's size, the
// missions' names and the landing's pieces, what a piece of another map costs and says, the flags' contract and the
// Lights view's storage key. Its own state is inside it (the map's floor tiles as a set, and the piece panel's ladder
// and grid chips); the selection itself (selected) is editor_state.js's.
import { LEVEL, TILE } from './constants.js';
import { coverWords, isBlocker, isFloor, lengthWords, sizeWords } from './cover.js';
import { copyText, field, plural, short, text } from './dom_words.js';
import { onHub, runHub, STOP } from './edit_hub.js';
import { recordName } from './effects_rules.js';
import { allRoots, buildingMeta, data, effectRoots, effectsOn, families, lightRoots, lightsOn, lightsShown,
         normalEffects, ownSet, pickedEffect, roots, selected, setAreaShown, setEffectsDirty, setOwnPickedValue,
         setPickedEffect, setSelected, setWallFocus, volumeRoots, volumesOn, wallFocus,
         zonesOn } from './editor_state.js';
import { placedPose } from './gizmo.js';
import { addedFloors, ladderEnds } from './ladders.js';
import { plan as planFlags, rawOf as flagRaw } from './piece_flags.js';
import { destructionNote, lootNote } from './pieces.js';
import { gridMove } from './poserule.js';
import { remember } from './storage.js';
import { focusBounds } from './view_layout.js';

// "12 pieces, 2 lights and 1 building": what these roots are, by kind.
export function selectionWords(list, other = '') {
  const lights = list.filter(r => r.userData.light).length, boxes = list.filter(r => r.userData.volume);
  const fx = kind => list.filter(r => r.userData.effect && r.userData.source.kind === kind).length;
  const effects = fx('effect'), sounds = fx('sound'), flares = fx('flare');
  const made = new Set(boxes.map(r => r.userData.volume.building)).size, n = list.length - lights - boxes.length - effects - sounds - flares;
  const parts = [n && plural(n, `${other}piece`), lights && plural(lights, `${n ? '' : other}light`), effects && plural(effects, 'effect'),
                 sounds && plural(sounds, 'sound'), flares && plural(flares, 'lens flare'),
                 made && plural(made, `${n || lights ? '' : other}building`)].filter(Boolean);
  return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0] ?? `0 ${other}pieces`;
}
// What a selected root is called in a list: a piece by its mesh, a light by its actor.
export const rootName = r => (r.userData.volume ? `Floor box of ${buildingMeta.get(r.userData.volume.building)?.name || 'a building'}`
  : r.userData.light ? short(r.userData.source.actor) : r.userData.effect ? recordName(r.userData.source, data)
  : short(data.meshes[r.userData.source.mesh].name));

export function createSelection({ $, actorPose, allBuildings, AREA_SHOWN, areaOwner, boxOf, editChanged,
                                  effectViewOnly, flagContract, flagSource, flashHint, foreignCost, foreignNote, frame,
                                  gizmo, gridOrigin, groupChip, highlight, isLanding, isStream, ladderMarks,
                                  lightViewOnly, listingsNow, missionName, ownSize, pickEffect, RECIPE_NOTE, recipeOf,
                                  setEffectsShown, setLightsShown, setVolumesShown, setZonesShown, tileCorner }) {
  // The floor boxes selected with pieces in the normal view (View options' Floor boxes): each building's, whole.
  const selectedBoxes = () => (volumesOn ? [] : gizmo.selection().filter(r => r.userData.volume && !r.userData.deleted));
  // The selection's pieces that can be copied or deleted: hidden helpers shown for inspection are left out.
  function copyable() {
    return gizmo.selection().filter(r => !r.userData.volume).filter(r => (r.userData.light ? !lightViewOnly(r.userData.source)
      : r.userData.effect ? !effectViewOnly(r.userData.source, 'copy') || !effectViewOnly(r.userData.source, 'delete')
      : !r.userData.source.hidden && !r.userData.source.environment));
  }
  // (Align lines up pieces only: lights and effects have no box of their own to line up)
  const copyablePieces = () => copyable().filter(r => !r.userData.light && !r.userData.effect);
  // What a group can hold of the selection: pieces, lights that can be edited, and the buildings picked with them.
  const groupables = () => [...copyable(), ...selectedBoxes()];
  // add: Ctrl/Shift-click toggles the piece in the selection. keep: only refresh the panel and highlight.
  // The piece panel shows only with a selection: name and what moves with it first, source paths folded away.
  function select(id, add = false, keep = false) {
    if (!keep) gizmo.select(id, add);
    id = gizmo.active;
    // a piece or a light selected from a list while the Buildings view is on: the view steps aside
    if (volumesOn && id && !volumeRoots.has(id)) setVolumesShown(false);
    // the Landing zones view picks zones only: anything selected another way (a list, a paste, a placed piece) leaves it
    if (zonesOn && id) setZonesShown(false);
    // (the Effects view picks its markers only; an effect selected another way, a paste or an undo, opens it unless the
    // normal view draws effects)
    if (effectsOn && id && !effectRoots.has(id)) setEffectsShown(false);
    else if (id && effectRoots.has(id) && !effectsOn && !normalEffects) setEffectsShown(true);
    if (lightsOn && id && !lightRoots.has(id)) setLightsShown(false);
    else if (id && lightRoots.has(id) && !lightsShown) setLightsShown(true);
    if (id) setOwnPickedValue(null);
    if (!add && !keep) ownSet.clear();
    setSelected(id);
    { const was = pickedEffect; setPickedEffect(effectRoots.has(id) ? id : null); if (was !== pickedEffect) setEffectsDirty(true); }     // (one that starts off is drawn while it is picked)
    const root = roots.get(id) ?? lightRoots.get(id) ?? volumeRoots.get(id) ?? effectRoots.get(id);
    $('inspector').hidden = !root || Boolean(root.userData.volume);
    $('rail').classList.toggle('idle', !root);
    runHub('select-sections', root);     // each area's section of the piece panel shown or hidden (edit_hub.js)
    if (wallFocus && wallFocus.id !== id) setWallFocus(null);
    if (!root || root.userData.volume || root.userData.effect) {
      highlight.visible = false; ladderMarks.visible = false;
      if (root?.userData.effect) $('inspector').hidden = true;
      runHub('select-none', root); editChanged(); return;
    }
    if (root.userData.light) { runHub('select-light', root); return; }
    const obj = root.userData.source, mesh = data.meshes[obj.mesh];
    refreshHighlight(root);
    const details = $('details');
    details.replaceChildren();
    if (obj.cover) { showCover(root); return; }
    runHub('select-piece', root, obj);     // a made piece's sections, the Break row (edit_hub.js)
    text(details, 'h2', short(mesh.name));
    text(details, 'div', `${obj.actorClass} · ${obj.sourcePackage || data.source.file.split(/[\\/]/).at(-1)}`, 'sub');
    const chips = text(details, 'div', '', 'chips');
    chips.append(groupChip);
    const others = gizmo.selection().filter(r => r !== root);
    if (others.length) {
      const chip = text(chips, 'span', `Moves with ${selectionWords(others, 'other ')}`, 'chip');
      chip.title = [...new Set(others.map(rootName))].join('\n');
    }
    if (obj.layer === 'inherited') text(chips, 'span', obj.hidden ? 'Inherited patch · hidden helper' : 'Inherited patch', 'chip');
    if (isStream(obj)) {
      const stream = data.streams?.[obj.stream], lwr = stream?.kind === 'lwr';
      const missions = (data.missions || []).filter(m => m.streams.includes(obj.stream)).map(missionName);
      text(chips, 'span', `${lwr ? 'LWR patch' : 'Mission stream'}${obj.hidden ? ' · hidden in game' : ''} · not editable`, 'chip warn').title =
        `From ${obj.stream}, which ${missions.length ? `the ${missions.join(', ')} mission${missions.length > 1 ? 's stream' : ' streams'}` : 'the map streams'} into the map. `
        + `It is shown for reference: a project edits the map's own pieces, and the Build leaves this package as it is.`;
    }
    if (obj.provenance) text(chips, 'span', `Patch ${obj.provenance.type}`, 'chip');
    if (obj.added) text(chips, 'span', 'Added copy', 'chip').title = `A copy of ${short(obj.added.from.actor)}`;
    // a piece of another map (library.js): the Build brings it from its home map
    if (obj.foreign) text(chips, 'span', `From ${obj.foreign.package}`, 'chip').title = foreignNote(obj);
    // export 15: the map's Kismet names the piece (the compiler's mission-linked: a warning when it is moved or deleted)
    if (obj.referencedBy?.length && !obj.added) text(chips, 'span', 'Mission script', 'chip warn').title =
      `Named by the map's Kismet (${obj.referencedBy.join('; ')}). Copied, it is an ordinary piece; moved or deleted, its `
      + 'mission script acts on the hidden original, not on the copy (the Build warns of it)';
    // F-45: LWR's landing-zone mutator spawns the landing from these (compiler.LANDING_PREFIXES)
    if (!isStream(obj) && !obj.foreign && isLanding(obj)) text(chips, 'span', obj.added ? 'Copy of a landing piece' : 'Landing zone', obj.added ? 'chip' : 'chip warn').title =
      obj.added ? 'A copy of one of the map\'s landing-zone pieces: an ordinary piece'
      : `One of the map's landing-zone pieces (${obj.archetype}): LWR's landing-zone mutator spawns the landing from it, so `
        + 'moved or deleted the dropship\'s landing breaks (F-45; the Build warns of it). Copied, it is an ordinary piece';
    gridChip = text(chips, 'span', '', 'chip');
    ladderChip = text(chips, 'span', '', 'chip');
    ladderChip.title = LADDER_NOTE;
    const helpers = families?.helpers?.[obj.actor];
    if (helpers?.length && !obj.added && obj.layer === 'base') text(chips, 'span', `Patch helper${helpers.length > 1 ? 's' : ''}`, 'chip').title =
      `${helpers.map(h => `${short(h.actor)} in ${h.stream}${h.match === 'near' ? ` (near: ${h.distance} units off, with other ends)` : ''}`).join(', ')}: `
      + 'a hidden ladder a streamed patch places with this one. Moved or deleted, the Build takes it out of the variant\'s copy of the patch, so the old place no longer climbs';
    const loot = isStream(obj) ? null : lootNote(obj);
    if (loot) text(chips, 'span', loot.label, 'chip').title = loot.title;
    runHub('select-chips', chips, root);
    // the generated area lights it glows with (export 18's associations, or the project's): they follow it
    const glowActor = obj.added ? obj.added.from.actor : obj.actor;
    const glows = obj.foreign ? (obj.foreign.areaLights?.[glowActor]?.lights ?? []).map(light => short(light.actor))
      : [...lightRoots.values()].filter(r => r.userData.source.role === 'area' && areaOwner(r.userData.source).owner?.actor === glowActor)
        .map(r => short(r.userData.source.actor));
    const unsettled = (obj.areaLights ?? []).map(id => lightRoots.get(id)).filter(r => r && !areaOwner(r.userData.source).owner
                                                                                    && areaOwner(r.userData.source).how !== 'kept');
    if (glows.length && !isStream(obj)) {
      const chip = text(chips, 'span', `Glows · ${plural(glows.length, 'light')}`, 'chip');
      chip.title = `${glows.join(', ')}: generated lights the bake made for its glow. They move, copy and go `
        + 'with it; click to see them (Area lights in View options)';
      chip.onclick = () => { setAreaShown(true); remember(AREA_SHOWN, '1'); setLightsShown(true); };
    }
    // the effects it carries (export 23's carriedBy; tools/bake/native_effects.py): the Build moves, copies and deletes
    // them with it. A click shows them in the Effects view.
    const effects = obj.foreign || isStream(obj) ? [] : (data?.effects ?? []).filter(e => e.carriedBy === glowActor);
    if (effects.length) {
      const chip = text(chips, 'span', effects.length === 1 ? 'Carries an effect' : `Carries ${effects.length} effects`, 'chip');
      chip.title = `${effects.map(e => `${short(e.actor)} (${String(e.template ?? 'a particle system').split('.').at(-1)})`).join(', ')}: `
        + 'a particle effect standing on it, such as a Skyranger\'s lights. The Build moves, copies and deletes it with the piece. '
        + (effects[0].id ? 'Click to see it in the Effects view (Shift+X)' : 'Prepare the map again to see it in the Effects view');
      if (effects[0].id) chip.onclick = () => { setEffectsShown(true); pickEffect(effects[0].id); };
    }
    if (unsettled.length && !obj.added && !isStream(obj)) {
      const chip = text(chips, 'span', `May glow · ${plural(unsettled.length, 'light')} to settle`, 'chip warn');
      chip.title = `${unsettled.map(r => short(r.userData.source.actor)).join(', ')}: generated lights the export couldn't tie to one piece. Before this piece `
        + 'moves, assign each its glowing piece or keep it fixed (select the light: click to show area lights)';
      chip.onclick = () => { setAreaShown(true); remember(AREA_SHOWN, '1'); setLightsShown(true); select(unsettled[0].userData.source.id); };
    }
    // Hidden helpers are shown for inspection only; they cannot be copied.
    $('editCopy').disabled = !copyable().length;
    const dl = $('sourceFields');
    dl.replaceChildren();
    field(dl, 'Actor', short(obj.actor));
    if (obj.added) field(dl, 'Copied from', obj.foreign ? `${short(obj.added.from.actor)} of ${obj.foreign.package}` : short(obj.added.from.actor));
    if (obj.foreign) field(dl, 'Brought in', foreignCost(obj) ?? 'By the Build, from its home map').title = foreignNote(obj);
    field(dl, 'Class', obj.actorClass);
    // what the game's damage does to it (export 17): its toughness's health
    const breakage = destructionNote(obj, data.exporterVersion);
    field(dl, 'Destructible', breakage.destructible).title = breakage.title;
    if (breakage.health) field(dl, 'Health', breakage.health).title = breakage.title;
    field(dl, 'Package', obj.sourcePackage || data.source.file.split(/[\\/]/).at(-1));
    if (obj.editorLayers?.length) field(dl, 'Source layers', obj.editorLayers.join(', '));
    if (obj.provenance) {
      field(dl, 'Patch operation', `${obj.provenance.operation} · ${obj.provenance.type}`);
      field(dl, 'Source actor', obj.provenance.sourceActor);
    }
    field(dl, 'Map location', obj.location.map(v => v.toFixed(2)).join(', '));
    field(dl, 'Mesh', mesh.name);
    if (mesh.kind === 'skeletal') field(dl, 'Pose', `Reference pose · ${mesh.bones.length} bones`);
    field(dl, 'Floors', listingsNow(root).map(f => `${short(allBuildings().find(b => b.id === f.building)?.name || f.building)} · floor ${f.floor+1}${f.cutdownFloor ? ' (cuts down)' : ''}`).join('\n') || 'None').title =
      'The building floors whose cutaway it is in. A copy, or a piece moved, joins the floor it stands in, as the Build lists it';
    const materialNames = obj.materials.map(m => data.materials[m]?.name || 'Unresolved');
    field(dl, 'Materials', materialNames.map(short).join('\n')).title = materialNames.join('\n');
    $('copyPaths').onclick = () => copyText($('copyPaths'), [`Actor: ${obj.actor}`, `Mesh: ${mesh.name}`, ...materialNames.map(m => `Material: ${m}`)].join('\n'));
    // (a made wall's mesh is made by the Build from its numbers: the page doesn't count it)
    field(dl, 'Geometry', mesh.made ? 'Made by the Build from the numbers of the wall, as the view draws it'
      : `${mesh.vertices.toLocaleString()} vertices · ${mesh.triangles.toLocaleString()} triangles`);
    const actors = [...new Set(others.filter(r => !r.userData.volume).map(r => r.userData.source.actor))].filter(a => a !== obj.actor);
    if (actors.length) field(dl, 'Moves with', actors.map(short).join('\n'));
    editChanged();
  }
  // A cover block's or invisible floor's panel: what it is, its size, height and cover (coverPanel), its actor and place.
  function showCover(root) {
    const obj = root.userData.source, details = $('details'), c = obj.cover, floor = isFloor(c);
    text(details, 'h2', floor ? 'Invisible floor' : isBlocker(c) ? 'Blocker' : 'Cover block');
    text(details, 'div', floor ? `Invisible in the game · a floor to stand on · ${sizeWords(c.size)}`
      : `Invisible in the game · ${isBlocker(c) ? 'blocks walking, no cover' : coverWords(c)} · ${sizeWords(c.size)}, top ${lengthWords(c.heights[1])}`, 'sub');
    const chips = text(details, 'div', '', 'chips');
    chips.append(groupChip);
    const others = gizmo.selection().filter(r => r !== root);
    if (others.length) text(chips, 'span', `Moves with ${selectionWords(others, 'other ')}`, 'chip');
    text(chips, 'span', floor ? 'Added invisible floor' : isBlocker(c) ? 'Added blocker' : 'Added cover block', 'chip').title = floor
      ? 'The editor\'s own piece: a hidden plate units can stand on (EXP-32). The Build makes it on any install'
      : isBlocker(c) ? 'The editor\'s own piece: a hidden piece that blocks movement and gives no cover. The Build makes it on any '
        + 'install, plain Enemy Within included'
      : 'The editor\'s own piece, as LWR\'s patches add cover: a hidden piece that blocks movement and gives cover. The Build makes '
        + 'it on any install, plain Enemy Within included';
    gridChip = ladderChip = null;
    runHub('select-cover', root);
    $('editCopy').disabled = !copyable().length;
    const dl = $('sourceFields');
    dl.replaceChildren();
    field(dl, 'Actor', short(obj.actor));
    field(dl, 'Class', `${obj.actorClass} (hidden)`);
    field(dl, 'Map location', placedPose(obj, root.matrix).location.map(v => v.toFixed(2)).join(', ')).title = 'Its corner, on the floor';
    $('copyPaths').onclick = () => copyText($('copyPaths'), `Actor: ${obj.actor}`);
    editChanged();
  }
  // The ladder's ends where the selected ladder stands now (ladders.js against the export's original floor tiles and the
  // floor the project's own flat pieces are expected to give, as the compiler counts it), or null. `newFloor` says an
  // end has floor only by a piece of the project. The floor is counted as the compiler's ladder check counts it
  // (compiler.py added_floors, ladder_ends; review finding 34): a piece whose flags make it no floor gives none, and the
  // tiles of the map's own pieces made no floor, moved or deleted are taken out (compiler floor_now);
  // one of the map's own pieces made floor where it stands gives floor; a grown grid's new levels count.
  let floorSet = null, ladderChip = null, gridChip = null;
  function ladderNow(root) {
    const o = root?.userData.source;
    if (!o || o.actorClass !== 'XComLadder' || isStream(o) || !data.tileGrid || !data.tactical?.floorTiles) return null;
    floorSet ??= new Set(data.tactical.floorTiles.map(f => f.tile.join(',')));
    const boxes = [], off = new Set(), gone = new Set();
    for (const r of roots.values()) {
      const s = r.userData.source;
      if (isStream(s) || s.actorClass === 'XComLadder') continue;
      if (!s.added && (r.userData.deleted || r.userData.edit)) gone.add(s.actor);
      if (r.userData.deleted) continue;
      const floor = floorPlan(r);
      if (!s.added && !r.userData.edit) {
        // the map's own piece where it stands: its flags may take its floor away, or give it floor
        if (floor?.before === 'on' && floor.after === 'off') off.add(s.actor);
        else if (floor?.after === 'on' && floor.before !== 'on') boxes.push(boxOf(r));
        continue;
      }
      // a cover block is no floor, bar the invisible floor, which is made to carry one (EXP-32); a copy whose flags make
      // it no floor (and that collides) gives none
      if ((s.cover && s.cover.type !== 'floor') || (floor?.collides && floor.after === 'off')) continue;
      boxes.push(boxOf(r));
    }
    const dims = data.tileGrid.dimensions, own = ownSize()?.dims;
    const added = addedFloors(boxes, data.tileGrid.origin, dims && [dims[0], dims[1], Math.max(dims[2], own?.[2] ?? 0)]);
    const floors = off.size || gone.size ? new Set(data.tactical.floorTiles.filter(f => !off.has(f.actor) && !gone.has(f.actor)).map(f => f.tile.join(',')))
      : floorSet;
    const pose = placedPose(o, root.matrix);
    const ends = ladderEnds(pose.location, pose.rotation, data.meshes[o.mesh].bounds[5], tileCorner(), new Set([...floors, ...added]));
    ends.newFloor = ends.climbs && [ends.footTile, ends.linkedTop].some(t => !floors.has(t.join(',')));
    return ends;
  }
  // A piece's Floor before and after its flags (piece_flags.js plan, as the compiler's flag_plan), with whether it
  // collides, or null when it has no flags request (or they can't be planned).
  function floorPlan(r) {
    const s = r.userData.source, c = flagContract();
    if (!c || !r.userData.flags || !s.pieceFlags) return null;
    const [cls, pf] = flagSource(s), { raw, assumed } = flagRaw(pf), p = planFlags(c, cls, raw, r.userData.flags, assumed);
    if (Object.keys(p.conflicts).length) return null;
    return { before: p.before.floor, after: p.after.floor, collides: s.added?.generated?.kind === 'ground' || s.pieceFlags.collides !== false };
  }
  const LADDER_NOTE = 'The game makes a ladder\'s climb between floors: its foot tile, and its top tile or the one below '
    + 'it, must have floor (the squares: green has floor, red has none). The map\'s own floor counts, and so does a flat '
    + 'piece this project adds with standing room over it (a deck, a slab, an invisible floor). A ladder with a red '
    + 'end is built all the same, with a warning: the game is not expected to make its climb';
  function refreshLadder(root) {
    const ends = ladderNow(root);
    ladderMarks.visible = Boolean(ends) && root.visible;
    if (ladderChip) {
      ladderChip.hidden = !ends;
      if (ends) {
        ladderChip.textContent = ends.newFloor ? 'Climbs, by a floor this project adds' : ends.climbs ? 'Climbs'
          : `Won't climb: no floor at its ${ends.why.join(' or ')}`;
        ladderChip.classList.toggle('warn', !ends.climbs);
      }
    }
    if (!ends) return;
    const [ox, oy, oz] = data.tileGrid.origin;
    const tiles = [[ends.footTile, ends.footFloor], [ends.linkedTop ?? ends.topTile, Boolean(ends.linkedTop)]];
    tiles.forEach(([tile, ok], k) => {
      const mark = ladderMarks.children[k];
      mark.position.set(ox + (tile[0] + 0.5) * TILE, oz + tile[2] * LEVEL + 3, oy + (tile[1] + 0.5) * TILE);
      mark.material.color.set(ok ? 0x5ad17a : 0xe0605a);
    });
  }
  // A ladder, door, car, van or fracturing piece: whether it stands on the tile grid of its original (poserule.js
  // gridMove, as the compiler checks it), or null for another piece. Off the grid it builds, with a warning.
  function gridNow(root) {
    const o = root?.userData.source, from = o && !root.userData.light ? recipeOf(o) : null, origin = gridOrigin();
    if (!from || !origin) return null;
    const pose = actorPose(o, root.matrix);
    return gridMove(from.location, from.rotation, pose.location, pose.rotation, origin);
  }
  const OFF_GRID_NOTE = 'Ladders, doors, cars, vans and fracturing pieces (walls, storey floors) map what the game saves '
    + 'for their tiles exactly only moved by whole tiles (96 across) and storeys (64 up) and turned by quarter turns about '
    + 'the vertical from where the original stands. This one is off that grid: it builds where it stands, with a warning '
    + 'in the Build report. Tile snap (96 on the snap button) keeps such a piece on the grid';
  function refreshGrid(root) {
    if (!gridChip) return;
    const move = isStream(root?.userData.source) ? null : gridNow(root);
    gridChip.hidden = !move || (move.valid && !gizmo.recipe);
    if (gridChip.hidden) return;
    gridChip.textContent = move.valid ? 'Recipe snap' : 'Off the grid';
    gridChip.classList.toggle('warn', !move.valid);
    gridChip.title = move.valid ? `${RECIPE_NOTE}.` : `${OFF_GRID_NOTE}. It misses ${move.why.join(', ')}.`;
  }
  function refreshHighlight(root) {
    // The box covers everything that moves with the selection.
    highlight.box.makeEmpty();
    for (const r of gizmo.selection().length ? gizmo.selection() : [root]) if (r.visible && !r.userData.light && !r.userData.volume) highlight.box.expandByObject(r);
    highlight.visible = root.visible && !root.userData.light;
    // Interior cuts the box to its area, but for a piece it draws whole only by the height
    if($('scenery').value==='interior') {
      const focus = focusBounds(data);
      if (root.userData.interiorWhole) { highlight.box.min.y = Math.max(highlight.box.min.y, focus.min.y); highlight.box.max.y = Math.min(highlight.box.max.y, focus.max.y); }
      else highlight.box.intersect(focus);
    }
    highlight.box.max.y=Math.min(highlight.box.max.y,root.userData.cutHeight ?? Infinity);
    highlight.visible &&= !highlight.box.isEmpty();
  }
  // After an edit (the edit hub, edit_hub.js).
  onHub('edit', 'selection', () => {
    // A command (undo of a paste, a delete) can change the selection under us: follow the gizmo.
    if (data && selected !== gizmo.active) { select(gizmo.active, false, true); return STOP; }
  });
  onHub('edit', 'marks', () => {
    if (selected && roots.get(selected)) { refreshHighlight(roots.get(selected)); refreshLadder(roots.get(selected)); refreshGrid(roots.get(selected)); }
  });

  // The pieces and lights an actor name stands for (a compile report's entity or target, a prefab test's actor),
  // selected and framed. False when none is in the view.
  function selectActors(names) {
    const want = new Set(names.flatMap(n => [n, short(n)]));
    const ids = [...roots.values(), ...lightRoots.values()]
      .filter(r => !r.userData.deleted && (want.has(r.userData.source.actor) || want.has(short(r.userData.source.actor))))
      .map(r => r.userData.source.id);
    if (!ids.length) { flashHint(`${short(names[0])} is not in the view`); return false; }
    gizmo.setSelection(ids, ids[0]); editChanged(); frame(allRoots.get(ids[0]));
    return true;
  }

  // The snap setting changed (the edit hub's snap run, edit_hub.js): the selected piece's grid chip.
  onHub('snap', 'grid', root => { refreshGrid(root); });

  return { copyable, copyablePieces, gridNow, groupables, ladderNow, refreshGrid, refreshHighlight, select,
           selectActors, selectedBoxes };
}
