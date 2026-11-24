// Clear map, the missions, the ground grid and the map picture (refactor stage P8; Clear map plan, mission types plan,
// LWR map packs plan). Here:
// - the landing zones as the project has them (zonesNow: its own, or the map's own landings joined with the install's
//   lines), the landing zone's pieces (isLanding), the ground's height (groundHeight) and the notes under a size
//   (sizeNotes, groundWords);
// - Clear map by parts (private/plans/todo/modular-clear-plan.md; clear_parts.js): the play area a part's clear keeping
//   the scenery outside goes by (outsideBox, pointOutside), what a clear takes and keeps of the pieces, lights, spawn
//   points and effects (clearPlan, clearedSpawns, clearedEffects), its window (showClearMap, clearWords) and the clear
//   itself, any parts in one undo step (clearParts; clearMap, all of them);
// - the missions: the Missions panel and the project's missions set (showMissions, setMissions), which game is set
//   (lwrInstall, plainEw, gameUnknownWhy), a cleared map's missions (clearedMissions) and the header's Mission picker
//   (headerMissions, headerMission, refreshMissionPicker, chooseMission);
// - the Map picture dialog and its Map menu item (the view taken by app.js's grabView);
// - the ground grid: a faint grid on the ground's plane where the map has no floor (refreshGroundGrid, setGroundGrid),
//   and the pieces still where the map has them (floorStays).
//
// createClearMap takes what it needs of app.js as one argument object, when app.js makes it: the scene, the gizmo, the
// pieces' and lights' roots added and taken away, the map's size, the Spawns, Landing zones and Buildings views'
// functions, Play's installs, the project's change, the view taken (grabView), the popups and the hints; what the
// other areas draw after a clear or a change of the missions or the zones follows the edit hub's runs (edit_hub.js).
// Its own state is inside it (the caches of what it works out, the window, the panels); the install's landing lines,
// the starting zones worked out, the last clear's time and the landing pieces as the server names them (app.js's scene
// start, the map's families in map_families.js and the test hooks read or set them) are editor_state.js's.
import * as THREE from 'three';
import { call } from './api.js';
import { LEVEL, TILE } from './constants.js';
import { onHub, runHub } from './edit_hub.js';
import { CLEAR_PARTS, PART_LABELS, WINDOW_PARTS, keepsOutside, partCleared, partsAfter } from './clear_parts.js';
import { activeMapId, areaBindings, askedPick, builderMode, cleared, clearedParts, data, effectRoots,
         landingActors, landingLines, landingZones, lightRoots, missionIndex, missionMoves, missionPickValue,
         playStatus, project, projectMissions, projectPicture, roots, setAreaBindings, setAskedPick, setClearedParts,
         setGroups, setLandingLines, setLandingRead, setLandingZones, setLastClearMs,
         setLightsDirty, setMergedBuildings, setMissionIndex, setMissionPickValue, setPickedZone, setProjectMissions,
         setProjectPicture, setStartingCache, setStreamSet, stage, startingCache, streamSet } from './editor_state.js';
import { survivesClear } from './effects_rules.js';
import { createMapPicture } from './map_picture.js';
import { ADDED_KINDS, addedMission, kindKey } from './missions.js';
import { createMissionsPanel } from './missions_panel.js';
import { validLandingZone } from './project.js';
import { groundOf, ownLandings, startingZones } from './spawns.js';
import { deletedEntry, spawnEditable, spawnKey, spawnNamed } from './spawns_view.js';
import { recall, remember } from './storage.js';
import { plural } from './dom_words.js';
import { fromOf, isStream } from './piece_records.js';

export function createClearMap({ $, addEffectRoots, addLightRoots, addRoots, allBuildings, banner, clearedChanged, cloneGroups,
                                 editedKey, explicitZones, flashHint, gizmo, grabView, lightViewOnly, liveVolumes,
                                 missionFloorLost, missionReached, ownSize, projectChanged, projectsAvailable,
                                 refreshInstalls, removeEffectRoots, removeLightRoots, removeRoots, sceneChanged, setMissionMoves,
                                 setStage, showPop, spawnFamilyBuilds, spawnsAvailable, world, zoneSoldiers,
                                 zoneState }) {
  // The landing zone's pieces (compiler.LANDING_PREFIXES, F-45): from the server's families, else by their archetype.
  const LANDING_PREFIXES = ['dgn_dropshipsoldierspawn.', 'veh_lv1skyranger_mod.prefabs.'];
  // (landingActors, as the server names them: editor_state.js)
  const isLanding = o => !o.foreign && (landingActors ? landingActors.has(fromOf(o).actor)
    : LANDING_PREFIXES.some(p => String(o.archetype ?? '').toLowerCase().startsWith(p)));

  // ---------------------------------------------------------------- Clear map (private/plans/done/clear-map-plan.md)
  // The landing zones as the project has them: its own list, or the map's own landings joined with the install's lines
  // (spawns.js startingZones; ids stable for a map, so an unchanged list is saved as nothing)
  // (startingCache, the starting zones worked out: editor_state.js)
  // The install's landing lines for the map, read as a map opens (app.js's startScene); the ground grid and the zones
  // follow once they come.
  function readLandingLines() {
    setStartingCache(null); setLandingLines({ kind: null, lines: [] });
    // the install's landing lines for the map (Clear map plan, section 4): the starting list of landing zones. A failed
    // read leaves the game unknown, with the reason (review finding 31).
    if (data.scope === 'map' && !data.preview && !builderMode && activeMapId)
      setLandingRead(call('GET', `/maps/${encodeURIComponent(activeMapId)}/landing-lines.json`, undefined,
                          { fallback: r => `the editor's server answered ${r.status}` })
        .then(v => {
          if (!Array.isArray(v.lines)) throw new Error(v.error ?? "the editor's server answered 200");
          return v;
        })
        .then(v => { setLandingLines(v); }, error => {
          setLandingLines({ kind: null, lines: [], failed: String(error?.message ?? error) });
          banner(`The game install's landing lines for this map couldn't be read (${landingLines.failed}), so the editor doesn't know which game is set: the Long War landing lines are missing and Long War only missions aren't checked. Open the map again to ask again.`);
        })
        .then(() => { setStartingCache(null); refreshGroundGrid(); runHub('landing-zones'); }));
  }
  function zonesNow() {
    if (landingZones) return landingZones.filter(validLandingZone);
    if (!startingCache && data) setStartingCache(startingZones(ownLandings(data), landingLines.lines ?? [], (() => { let n = 0; return () => `start-${++n}`; })()));
    return startingCache ?? [];
  }
  // The ground's height (section 3): the commonest ground of the landing zones, else the map's own landing's, else the
  // commonest lowest saved floor; and its level in the grid
  function groundHeight() {
    const counts = new Map();
    for (const z of zonesNow()) { const g = Math.round(groundOf(z)); counts.set(g, (counts.get(g) ?? 0) + 1); }
    if (!counts.size) for (const o of ownLandings(data ?? {})) { const g = Math.round(groundOf(o.zone)); counts.set(g, (counts.get(g) ?? 0) + 1); }
    if (!counts.size) {
      const lowest = new Map();
      for (const f of data?.tactical?.floorTiles ?? []) { const k = `${f.tile[0]},${f.tile[1]}`; if (!lowest.has(k) || f.location[2] < lowest.get(k)) lowest.set(k, f.location[2]); }
      for (const z of lowest.values()) { const g = Math.round(z); counts.set(g, (counts.get(g) ?? 0) + 1); }
    }
    if (!counts.size) return data?.tileGrid?.origin?.[2] ?? 0;
    return [...counts].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
  }
  const LEVEL_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six'];
  function groundWords(levels) {
    const oz = data.tileGrid.origin[2], sz = data.tileGrid.size?.[2] ?? LEVEL, ground = groundHeight();
    const under = Math.max(0, Math.floor((ground - oz + 2) / sz));
    if (under >= levels) return `The ground is at ${Math.round(ground)}, above the grid's top: the grid needs ${under + 1} levels or more.`;
    return `The ground is at level ${under + 1} of ${levels}: ${under ? `${LEVEL_WORDS[under] ?? under} level${under === 1 ? '' : 's'} of the grid ${under === 1 ? 'is' : 'are'}` : 'no level of the grid is'} under it.`;
  }
  // The notes under a size, none of which blocks (warn, don't block): zones outside the grid, no room for LWR's pods
  // (F-90), the ground above the grid
  function sizeNotes([nx, ny, nz], zoneList = null) {
    const notes = [], [ox, oy, oz] = data.tileGrid.origin, [sx, sy, sz] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
    const box = [ox, oy, oz, ox + nx * sx, oy + ny * sy, oz + nz * sz];
    const zones = zoneList ?? zonesNow();
    const inside = p => p[0] >= box[0] && p[0] <= box[3] && p[1] >= box[1] && p[1] <= box[4] && p[2] >= box[2] && p[2] <= box[5];
    const st = zoneState(), outside = zones.filter(z => !zoneSoldiers(z, st).every(s => inside(s.location)));
    if (outside.length) notes.push(`${outside.length} of ${plural(zones.length, 'landing zone')} ${outside.length === 1 ? 'is' : 'are'} outside the new grid.`);
    const far = zones.some(z => {
      const pts = zoneSoldiers(z, st).map(s => s.location), mx = pts.reduce((a, p) => a + p[0], 0) / pts.length, my = pts.reduce((a, p) => a + p[1], 0) / pts.length;
      return Math.max(...[box[0], box[3]].flatMap(x => [box[1], box[4]].map(y => Math.hypot(x - mx, y - my)))) < 29 * sx;
    });
    if (far) notes.push('No part of the grid is 29 tiles from a landing zone: LWR places no pods or Meld there for a squad landing at it.');
    if (Math.floor((groundHeight() - oz + 2) / sz) >= nz) notes.push('The ground is above the grid.');
    return notes;
  }
  // The play area a clear that keeps the scenery outside goes by, across, in game units [x0, y0, x1, y1]: the map's level
  // volume as exported and the grid of `dims` tiles together (the compiler's outside_box)
  function outsideBox(dims = data.tileGrid.dimensions) {
    const own = ownSize(), b = data.playableBounds, [ox, oy] = data.tileGrid.origin, [sx, sy] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
    return [Math.min(b.min[0], ox), Math.min(b.min[2], oy), Math.max(own?.max[0] ?? b.max[0], ox + dims[0] * sx),
            Math.max(own?.max[2] ?? b.max[2], oy + dims[1] * sy)];
  }
  let outsideCache = null;
  // Whether a place (game x, y) is outside the play area of `part`'s clear, when it kept the scenery out there
  function pointOutside(x, y, part) {
    if (!keepsOutside(clearedParts, part) || !data?.playableBounds) return false;
    const key = data.tileGrid.dimensions.join(',');
    if (outsideCache?.key !== key) outsideCache = { key, box: outsideBox() };
    const [x0, y0, x1, y1] = outsideCache.box;
    return x < x0 || x > x1 || y < y0 || y > y1;
  }
  // What a clear takes and keeps, from the pieces, lights and effects on the map now, each part's own (the Pieces part's:
  // originals, added, boxes, pieces; the Lights part's: originalLights, addedLights, lights; the Effects part's:
  // addedEffects, movedEffects). `keepOutside`: the grid size (tiles, levels) the clear gives, to leave the scenery
  // wholly outside the play area (outsideBox): a piece whose every part's box is outside it, and a light placed outside
  // it.
  function clearPlan(keepOutside = null) {
    const originals = [], added = [], landing = new Set(), script = new Map(), actors = new Set(), addedActors = new Set();
    const area = keepOutside ? outsideBox(keepOutside) : null, boxes = new Map(), outside = new Set();
    const out = (x, y) => area && (x < area[0] || x > area[2] || y < area[1] || y > area[3]);
    for (const r of roots.values()) {
      const o = r.userData.source;
      if (o.added) { added.push(r); addedActors.add(o.actor); continue; }
      if (isStream(o) || o.hidden || o.environment || r.userData.deleted) continue;
      if (isLanding(o)) { landing.add(o.actor); continue; }
      if (area) { const b = new THREE.Box3().setFromObject(r); if (!b.isEmpty()) (boxes.get(o.actor) ?? boxes.set(o.actor, []).get(o.actor)).push(b); }
      originals.push(r);
    }
    // across, an actor wholly outside the play area: every part's box beyond the same side or another
    if (area) for (const [actor, bs] of boxes)
      if (bs.every(b => b.max.x < area[0] || b.min.x > area[2] || b.max.z < area[1] || b.min.z > area[3])) outside.add(actor);
    for (let k = originals.length - 1; k >= 0; k--) if (outside.has(originals[k].userData.source.actor)) originals.splice(k, 1);
    for (const r of originals) {
      const o = r.userData.source;
      actors.add(o.actor);
      if (o.referencedBy?.length) script.set(o.actor, o.referencedBy);
    }
    const originalLights = [], addedLights = [], kept = [];
    let lightCount = 0, lightsOutside = 0;
    for (const r of lightRoots.values()) {
      const o = r.userData.source;
      if (isStream(o)) continue;
      if (o.added) { addedLights.push(r); lightCount++; continue; }
      if (o.kind === 'directional' || o.kind === 'sky' || o.role === 'dominant' || o.role === 'sky') { kept.push(o); continue; }
      // (an area light goes with its glowing piece: the Pieces part's, the Build's clear_level)
      if (r.userData.deleted || o.role === 'area') continue;
      const e = r.matrix.elements;       // (a light's place is its root's own matrix, in the view's basis)
      // the lights the editor edits are deleted here; the view-only ones the Build takes out (clear_level), and an earlier
      // clear of the lights has taken them already but where it kept the outside
      const viewOnly = lightViewOnly(o);
      if (viewOnly && partCleared(clearedParts, 'lights') && !pointOutside(e[12], e[14], 'lights')) continue;
      if (out(e[12], e[14])) { lightsOutside++; continue; }
      lightCount++;
      if (!viewOnly) originalLights.push(r);
    }
    // the effects, ambient sounds and lens flares (the user, 23 November 2026: a clear left a boat's 35 added effects
    // standing): the project's added ones go as its added pieces do; the map's own go by the cleared mark
    // (effects_rules.js survivesClear, the Build's clear_level), and one the project moved, which the mark keeps, is
    // deleted here, as a moved piece is; the landing's and those outside a kept play area stay
    const addedEffects = [], movedEffects = [];
    for (const r of effectRoots.values()) {
      const o = r.userData.source;
      if (isStream(o) || r.userData.deleted || r.userData.derivedGone) continue;
      if (o.added) { addedEffects.push(r); continue; }
      if (r.userData.edit && !o.landingActor && !out(o.location[0], o.location[1])) movedEffects.push(r);
    }
    return { originals, added, originalLights, addedLights, addedEffects, movedEffects, pieces: actors.size + addedActors.size,
             lights: lightCount, landing: landing.size, script: [...script], kept, boxes: liveVolumes(), outside: outside.size, lightsOutside };
  }
  // What a clear does to the spawn points (the user, 18 November 2026: "clear should also clear all of these"): the map's
  // pods, Meld points and drop-in points are deleted (their moves and values go), but for one something names (the Build
  // would keep it and warn: it stays, with its edit); the project's copies of them go. No-spawn volumes (the map's and
  // the project's) and the mission streams' objects stay as they are. { after (the edits after the clear), deleted,
  // named (the records), copies (how many go), volumes (how many stay) }.
  function clearedSpawns() {
    const after = new Map(missionMoves), deleted = [], named = [];
    if (!spawnsAvailable() || !spawnFamilyBuilds()) return { after, deleted, named, copies: 0, volumes: 0 };
    let copies = 0, volumes = 0;
    for (const [k, m] of missionMoves) {
      if (m.stream !== 'copy') continue;
      if (m.copy.kind === 'noSpawn') volumes++; else { after.delete(k); copies++; }
    }
    for (const o of data?.spawns ?? []) {
      const k = spawnKey(null, o.actor);
      if (o.landing || missionMoves.get(k)?.deleted || !spawnEditable(o)) continue;
      if (o.kind === 'noSpawn') { volumes++; continue; }
      if (spawnNamed(o)) { named.push(o); continue; }
      after.set(k, deletedEntry(o)); deleted.push(o);
    }
    return { after, deleted, named, copies, volumes };
  }
  // What a clear does to the effects, sounds and lens flares standing now (clearPlan's rule): { effects (and flares) and
  // sounds that go (the project's added ones, the map's own but for the landing's and those outside a kept play area,
  // a moved one among them), landing: the landing's that stay (the Skyranger's lights, dust and sound) }. `keepOutside`:
  // the grid size of a clear that keeps the scenery outside the play area.
  function clearedEffects(keepOutside = null) {
    const area = keepOutside ? outsideBox(keepOutside) : null;
    const outside = (x, y) => Boolean(area) && (x < area[0] || x > area[2] || y < area[1] || y > area[3]);
    let effects = 0, sounds = 0, landing = 0;
    for (const root of effectRoots.values()) {
      const o = root.userData.source;
      if (isStream(o) || root.userData.deleted || root.userData.derivedGone) continue;
      if (!o.added) {
        const ctx = { carrierMoved: root.userData.carrierMoved, moved: Boolean(root.userData.edit) };
        if (!survivesClear(o, { ...ctx, cleared: partCleared(clearedParts, 'effects'), outside: (x, y) => pointOutside(x, y, 'effects') })) continue;      // (an earlier clear's)
        if (o.landingActor) { landing++; continue; }
        if (outside(o.location[0], o.location[1])) continue;
      }
      if (o.kind === 'sound') sounds++;
      else effects++;
    }
    return { effects, sounds, landing };
  }
  // The Clear map window (the clear-by-parts plan, section 3: design A): a tick for each part with its count, the parts
  // already cleared chipped, then "Keep the scenery outside the play area" and the notes of what the clear leaves.
  const clearDialog = { root: $('clearMap'), keep: $('clearMapKeepOutside'),
                        rows: new Map(WINDOW_PARTS.map(k => [k, $('clearMapParts').querySelector(`[data-part="${k}"]`)])) };
  const CLEAR_KEEP_OUTSIDE = 'workshop.clearKeepOutside';
  clearDialog.keep.checked = recall(CLEAR_KEEP_OUTSIDE) === '1';
  // The map's triggers (F-159; export 39's triggerCounts): its touch and water volumes and its sight points, none of
  // which the editor shows. In words for the window, or '' for a map with none (an older export says nothing of them).
  function triggerWords() {
    const t = data?.triggerCounts;
    if (!t || !(t.volumes + t.sight)) return '';
    const touch = t.volumes - t.water;
    return [touch && plural(touch, 'touch trigger'), t.water && plural(t.water, 'water volume'), t.sight && plural(t.sight, 'sight point')]
      .filter(Boolean).join(', ').replace(/, ([^,]*)$/, ' and $1');
  }
  // What each part's clear takes now, at the grid's size (a clear keeps it; the rail's Map grid changes it), the scenery
  // outside the play area kept or not: { part: { count, words } } (the user, 23 November 2026: "just give a very brief
  // count"). A part already cleared counts what stands since; the triggers, which a project adds none of, then count
  // none.
  function partCounts(keepOutside) {
    const dims = keepOutside ? [...data.tileGrid.dimensions] : null;
    const plan = clearPlan(dims), sp = clearedSpawns(), fx = clearedEffects(dims), zones = zonesNow();
    const points = sp.deleted.length + sp.copies, extraZones = Math.max(0, zones.length - 1);
    // (an export before 39 doesn't count them: the row says nothing, and the Build takes what there is)
    const t = data?.triggerCounts, triggers = partCleared(clearedParts, 'triggers') ? 0 : t ? t.volumes + t.sight : 1;
    const fxWords = [fx.effects && plural(fx.effects, 'effect'), fx.sounds && plural(fx.sounds, 'sound')].filter(Boolean).join(', ');
    return {
      pieces: { count: plan.pieces, words: plural(plan.pieces, 'piece') },
      lights: { count: plan.lights, words: plural(plan.lights, 'light') },
      effects: { count: fx.effects + fx.sounds, words: fxWords },
      spawns: { count: points, words: plural(points, 'point') },
      zones: { count: extraZones, words: `${extraZones} of ${zones.length}, one kept` },
      triggers: { count: triggers, words: t ? triggerWords() : '' },
    };
  }
  // A part the window can't take: nothing of it stands, but the pieces before they are cleared (their clear also takes
  // the map's volumes, cover and stains, and lets the grid shrink)
  const partEmpty = (k, counts) => !counts[k].count && !(k === 'pieces' && !partCleared(clearedParts, 'pieces'));
  let windowCounts = null;
  // The rows' counts, chips and states again (`fresh`: the window opens, every part not yet cleared ticked; else the
  // ticks are kept but on a part that can't be taken)
  function refreshClearRows(fresh = false) {
    windowCounts = partCounts(clearDialog.keep.checked);
    for (const [k, row] of clearDialog.rows) {
      const c = windowCounts[k], empty = partEmpty(k, windowCounts), box = row.querySelector('input');
      row.querySelector('.tickval').textContent = empty || !c.count ? 'none' : c.words;
      row.querySelector('.chip')?.toggleAttribute('hidden', !partCleared(clearedParts, k));
      row.classList.toggle('none', empty);
      box.disabled = empty;
      if (empty) box.checked = false;
      else if (fresh) box.checked = !partCleared(clearedParts, k);
    }
    clearWords();
  }
  const tickedParts = () => WINDOW_PARTS.filter(k => clearDialog.rows.get(k).querySelector('input').checked);
  // The notes under the ticks: what the clear leaves standing that may surprise, each one sentence, shown only when
  // true (section 2); and the button naming what it does
  function clearWords() {
    const asked = tickedParts(), counts = windowCounts, has = k => asked.includes(k);
    const left = k => !has(k) && !partCleared(clearedParts, k) && counts[k].count > 0;
    const notes = [], warn = [];
    if (has('pieces')) {
      if (!has('zones') && zonesNow().length) notes.push('The landing zones stay where they are, with no ground under them: lay floor there or move them in the Landing zones view.');
      if (left('lights')) notes.push('The map\'s lights stay where they are, lighting what you build there.');
      if (left('effects')) notes.push('The map\'s smoke, fire and sounds stay where their pieces were.');
      if (left('spawns') && plainEw()) warn.push('The map\'s pods stay where the floor was: move them onto your floors in the Spawns view.');
    }
    if (has('lights')) {
      if (!has('pieces') && !cleared) notes.push('The pieces keep the light baked into them until a Build with the bake.');
      notes.push('The sun, moon and sky light stay.');
    }
    if (has('spawns') && plainEw()) warn.push('Plain Enemy Within puts the aliens at the map\'s pods and Meld points, and the clear deletes them: place new ones on your floors with the Add panel\'s Spawn points.');
    $('clearMapPlan').textContent = notes.join(' '); $('clearMapPlan').hidden = !notes.length;
    $('clearMapWarn').textContent = warn.join(' '); $('clearMapWarn').hidden = !warn.length;
    $('clearMapMissions').hidden = !has('pieces');
    const open = WINDOW_PARTS.filter(k => !clearDialog.rows.get(k).querySelector('input').disabled);
    const ok = $('clearMapOk');
    ok.disabled = !asked.length;
    ok.textContent = asked.length && asked.length === open.length ? 'Clear map' : `Clear ${plural(asked.length, 'part')}`;
  }
  function showClearMap() {
    showPop(null);
    if (!projectsAvailable() || !ownSize()) { banner('Clear map is for a whole map, not a preview or the prefab builder.'); return; }
    refreshClearRows(true);
    clearDialog.root.hidden = false;
    setTimeout(() => $('clearMapOk').focus(), 0);
  }
  function hideClearMap() { clearDialog.root.hidden = true; }
  clearDialog.keep.onchange = () => { remember(CLEAR_KEEP_OUTSIDE, clearDialog.keep.checked ? '1' : '0'); refreshClearRows(); };
  for (const row of clearDialog.rows.values()) row.querySelector('input').onchange = () => clearWords();
  $('clearMapForm').onsubmit = e => {
    e.preventDefault();
    const asked = tickedParts();
    if (!asked.length) return;
    clearDialog.root.hidden = true;
    clearParts(asked, { keepOutside: clearDialog.keep.checked });
  };
  $('clearMapClose').onclick = $('clearMapCancel').onclick = hideClearMap;
  clearDialog.root.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); hideClearMap(); } });
  $('projectClear').onclick = showClearMap;
  // The one landing zone a clear keeps (the user, 13 November: "just leave 1 LZ"): plain EW's first, the map's own
  // first landing (else the first zone), used by both games
  function clearKeptZone() {
    const zones = data ? explicitZones() : [], z = zones.find(v => v.ew) ?? zones[0];
    if (!z) return null;
    const { lwr, ew, ...rest } = z;
    return { ...rest, ...(ownLandings(data).length ? { ew: true } : {}) };
  }
  // The clear of `asked` (the window's parts, WINDOW_PARTS), one undo step: for each part what a clear of the whole map
  // did to it, and the parts of CLEAR_PARTS marked for the Build (clear_parts.js partsAfter: a part cleared twice keeps
  // the outside only if both clears kept it). The pieces: the originals and the map's buildings deleted, the added
  // pieces gone, the groups and area-light bindings emptied, the grid kept as it is now (a size given, the tests' and
  // scripts', is the clear's) and the missions set to what a cleared map is for, which the Missions panel then asks
  // unless `ask` is false; the lights: the editable ones deleted, the added ones gone; the effects: the added ones gone,
  // a moved one deleted; the spawn points: clearedSpawns; the landing zones: one kept (clearKeptZone). `keepOutside`
  // leaves the scenery wholly outside the play area of the pieces, lights, effects and triggers asked.
  function clearParts(asked, { keepOutside = false, size = null, ask = !size } = {}) {
    const has = k => asked.includes(k);
    if (!asked.some(k => WINDOW_PARTS.includes(k))) return;
    const own = ownSize(), plan = clearPlan(keepOutside ? (size ?? [...data.tileGrid.dimensions]) : null);
    const gone = [...(has('pieces') ? [...plan.originals, ...plan.boxes] : []), ...(has('lights') ? plan.originalLights : []),
                  ...(has('effects') ? plan.movedEffects : [])];
    const addedPieces = has('pieces') ? plan.added : [], addedLights = has('lights') ? plan.addedLights : [];
    const addedEffects = has('effects') ? plan.addedEffects : [];
    const partsBefore = clearedParts, partsNext = partsAfter(clearedParts, asked, keepOutside);
    const pieces = has('pieces');
    // a size given (the tests, scripts) is the clear's; none keeps the grid as it is now
    const next = !pieces ? stage : size ? (size.some((v, k) => v !== own.dims[k]) ? { grid: [...size] } : null)
      : (stage ? { grid: [...data.tileGrid.dimensions] } : null);
    const picks = gizmo.picks(), groupsBefore = cloneGroups(), bindingsBefore = new Map(areaBindings), stageBefore = stage;
    // what a cleared map is for (mission types plan, D2): the header's mission when it is an abduction, a terror site or
    // a bomb (a record of the map's, or a kind the project adds), else an abduction; the Missions panel asks once the
    // clear is made
    const missionsBefore = projectMissions ? projectMissions.map(e => ({ ...e })) : null;
    const missionsCleared = pieces ? clearedMissions() : missionsBefore;
    // (the map's pods, Meld points and drop-in points deleted, the project's copies of them gone: clearedSpawns)
    const spawnsBefore = new Map(missionMoves), spawnsAfter = has('spawns') ? clearedSpawns().after : spawnsBefore;
    const kept = has('zones') ? clearKeptZone() : null, zonesBefore = landingZones ? landingZones.map(z => ({ ...z })) : null;
    const started = performance.now();
    const state = (parts, missions, spawns, zones, grid) => {
      setClearedParts(parts); setMissionMoves(new Map(spawns)); setStage(grid);
      if (pieces) setMergedBuildings(null);
      clearedChanged();
      setProjectMissions(missions ? missions.map(e => ({ ...e })) : null); refreshMissionPicker();
      if (kept) { setLandingZones(zones ? zones.map(z => ({ ...z })) : null); setPickedZone(null); runHub('landing-zones'); }
    };
    gizmo.record({
      redo: () => {
        removeRoots(addedPieces); removeLightRoots(addedLights); removeEffectRoots(addedEffects);
        for (const r of gone) r.userData.deleted = true;
        if (pieces) { setAreaBindings(new Map()); setGroups(new Map()); }
        state(partsNext, missionsCleared, spawnsAfter, kept ? [kept] : null, next);
        runHub('clear'); setLightsDirty(true); gizmo.setSelection([]); sceneChanged();
      },
      undo: () => {
        addRoots(addedPieces); addLightRoots(addedLights); addEffectRoots(addedEffects);
        for (const r of gone) r.userData.deleted = false;
        if (pieces) { setAreaBindings(new Map(bindingsBefore)); setGroups(cloneGroups(groupsBefore)); }
        state(partsBefore, missionsBefore, spawnsBefore, zonesBefore, stageBefore);
        runHub('clear'); setLightsDirty(true); gizmo.setSelection(picks.ids, picks.active); sceneChanged();
      },
    });
    setLastClearMs(Math.round(performance.now() - started));
    flashHint(asked.length >= WINDOW_PARTS.length ? 'Cleared · Ctrl+Z brings it back'
      : `Cleared ${asked.map(k => PART_LABELS[k].toLowerCase()).join(', ')} · Ctrl+Z brings it back`);
    if (pieces && ask) setTimeout(() => showMissions(true), 0);
  }
  // The whole clear (Clear map plan; the tests and scripts call it): every part, or every part but the triggers with
  // `keepTriggers` (the project's old clearKeepsTriggers, F-159)
  function clearMap(size, keepOutside = false, keepTriggers = false) {
    clearParts(WINDOW_PARTS.filter(k => !(keepTriggers && k === 'triggers')), { keepOutside, size });
  }
  // The Missions panel (missions_panel.js; mission types plan, D2): the base map's missions and the kinds a record alone
  // gives the map, ticked as the project has them; OK sets them, one undo step.
  const missionsPanel = createMissionsPanel({
    els: { root: $('missionsDialog'), form: $('missionsForm'), title: $('missionsTitle'), note: $('missionsNote'), list: $('missionsList'),
           warn: $('missionsWarn'), ok: $('missionsOk'), close: $('missionsClose'), cancel: $('missionsCancel') } });
  // Which game is set (review finding 31): Long War, plain Enemy Within, or neither known, a state of its own
  const lwrInstall = () => ['lwr', 'longwar'].includes(landingLines?.kind);
  const plainEw = () => landingLines?.kind === 'ew';
  const gameUnknownWhy = () => (landingLines?.kind ? null : landingLines?.failed
    ? `the editor couldn't read it: ${landingLines.failed}` : 'the settings name no game folder the editor recognises');
  // whether a UFO building stands on the map: one of the project's, or one of the map's own that stays
  const hasUfoBuilding = () => allBuildings().some(b => (b.project ? (b.project.kind ?? 'building') === 'ufo' : b.isUfo));
  const baseHas = kind => (data?.missions ?? []).some(m => kindKey(m) === kind);
  // A cleared map's missions: the header's when it is one of the first three kinds (its own record, else added), else
  // the base map's abduction record, else an added abduction.
  function clearedMissions() {
    const picked = (data?.missions ?? [])[missionIndex], key = picked ? kindKey(picked) : null;
    const addedPick = missionPickValue.startsWith('kind:') ? missionPickValue.slice(5) : null;
    if (['Abduction', 'TerrorSite', 'Special/Bomb'].includes(addedPick) && (addedPick !== 'Special/Bomb' || !plainEw())) return [{ kind: addedPick }];
    // (the base map's bomb is its own record, its objects standing where the original map has them until moved)
    if (picked && ['Abduction', 'TerrorSite', 'Special/Bomb'].includes(key)) return [{ record: missionIndex }];
    const abduction = (data?.missions ?? []).findIndex(m => kindKey(m) === 'Abduction');
    return abduction >= 0 ? [{ record: abduction }] : [{ kind: 'Abduction' }];
  }
  async function showMissions(asked = false) {
    showPop(null);
    if (!projectsAvailable() || !data || data.preview) return;
    if (!playStatus) await refreshInstalls();     // what is known of each kind played (the page asks at its start too)
    const missions = data.missions ?? [], labels = missionLabels(missions), kinds = playStatus?.missionKinds ?? {};
    const listed = Array.isArray(projectMissions) ? projectMissions : missions.map((_, i) => ({ record: i }));
    const has = entry => listed.some(e => (entry.record !== undefined ? e.record === entry.record : e.kind === entry.kind));
    const rows = missions.map((m, i) => {
      const objects = (m.streams ?? []).flatMap(s => data.streams?.[s]?.missionObjects ?? []);
      const lost = objects.filter(o => missionReached(o) && missionFloorLost(o)).length;
      return { entry: { record: i }, label: labels[i], checked: has({ record: i }), words: kinds[kindKey(m)]?.words ? `${kinds[kindKey(m)].words}.` : '',
               detail: [objects.length ? `${plural(objects.length, 'object')} in its stream${cleared ? ', standing where the original map has them' : ''}.` : '',
                        lost ? `${plural(lost, 'object')} of the map's floor taken from under ${lost === 1 ? 'it' : 'them'} (the Build warns).` : ''].filter(Boolean).join(' ') };
    });
    for (const [kind, k] of Object.entries(ADDED_KINDS)) {
      if (baseHas(kind) && !listed.some(e => e.kind === kind)) continue;     // the base map's own record is the row for it
      const entry = listed.find(e => e.kind === kind) ?? { kind, ...(k.ufo ? { ship: 'eShip_UFOSmallScout' } : {}) };
      const unknown = k.lwr ? gameUnknownWhy() : null;
      rows.push({ entry, label: `${k.label} (added)`, checked: has({ kind }), words: '', ufo: k.ufo,
                  detail: unknown ? `${k.needs} Which game is set isn't known (${unknown}), so the editor can't check that it is Long War.` : k.needs,
                  disabled: k.lwr && plainEw() ? 'Long War only: plain Enemy Within would play the bomb where Slaughterhouse has it.'
                    : k.ufo && !hasUfoBuilding() ? 'Place a UFO prefab first: the mission needs a UFO building on the map.' : null });
    }
    missionsPanel.show({
      title: asked ? 'What is this map for?' : `Missions${project ? ` of ${project.doc.name}` : ''}`,
      note: asked ? 'The cleared map is played as the missions ticked here; the Build writes a record for each. Missions in the Map menu changes them later.'
        : 'The Build writes a record for each mission ticked, and Play in game plays one of them. An added kind is made from the base map\'s abduction record.',
      rows, onOk: entries => setMissions(entries),
    });
  }
  // The project's missions set, one undo step: every base record and nothing added on a map that isn't cleared is the
  // default (null: saved as nothing).
  function setMissions(entries) {
    const all = (data.missions ?? []).length, records = entries.filter(e => Number.isInteger(e.record));
    const next = !cleared && records.length === all && entries.length === all ? null : entries.map(e => ({ ...e }));
    const before = projectMissions ? projectMissions.map(e => ({ ...e })) : null;
    if (JSON.stringify(next) === JSON.stringify(before)) return;
    gizmo.record({
      redo: () => { setProjectMissions(next ? next.map(e => ({ ...e })) : null); refreshMissionPicker(); projectChanged(); },
      undo: () => { setProjectMissions(before ? before.map(e => ({ ...e })) : null); refreshMissionPicker(); projectChanged(); },
    });
  }
  $('projectMissions').onclick = () => showMissions(false);
  // The Map picture dialog (map_picture.js; LWR map packs plan, 4.2): the picture is kept by the server with the project
  // and named in the project by its SHA-256, so the project's next save carries it (no undo step: the file is kept
  // outside the edit history).
  const mapPicture = createMapPicture({
    els: { root: $('mapPictureDialog'), form: $('mapPictureForm'), title: $('mapPictureTitle'), note: $('mapPictureNote'), drop: $('mapPictureDrop'),
           canvas: $('mapPictureCanvas'), empty: $('mapPictureEmpty'), file: $('mapPictureFile'), choose: $('mapPictureChoose'), take: $('mapPictureTake'),
           result: $('mapPictureResult'), resultNote: $('mapPictureResultNote'), status: $('mapPictureStatus'), use: $('mapPictureUse'),
           remove: $('mapPictureRemove'), close: $('mapPictureClose') },
    onUse: result => { setProjectPicture({ sha256: result.sha256 }); projectChanged(); flashHint('The map picture is set: save the project to keep it'); },
    onRemove: () => { setProjectPicture(null); projectChanged(); flashHint('The map picture is removed: save the project to keep it so'); },
    grabView,
  });
  $('projectPicture').onclick = () => {
    showPop(null);
    // the picture is kept with a saved project (by its id)
    if (!project) { banner('Save the project first: its map picture is kept with it.'); return; }
    mapPicture.show({ project: { id: project.doc.id, name: project.doc.name }, map: project.doc.source?.map ?? activeMapId, own: projectPicture?.sha256 ?? null });
  };
  // (lastClearMs, how long the last clear took: editor_state.js)

  // The ground grid (Clear map plan, section 3): a faint grid on the ground's plane (groundHeight: the landing zones'),
  // over the map's tile grid and no further, drawn only where the map has no floor: a tile is left out where a saved
  // floor at or under the ground is carried by a piece still where the map has it. So on a map as it is it shows only
  // over holes, and on a cleared one everywhere. Drawn with the depth test 2 units under the ground, so a floor piece
  // laid at ground level covers it; never picked. View options' Ground grid, on by default and remembered.
  const GROUND_GRID = 'workshop.groundGrid';
  const groundGrid = new THREE.Group(); world.add(groundGrid);
  groundGrid.visible = recall(GROUND_GRID) !== '0';
  const groundGridMaterials = {
    sheet: new THREE.MeshBasicMaterial({ color: 0x778c91, transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide }),
    line: new THREE.LineBasicMaterial({ color: 0x91a9ac, transparent: true, opacity: 0.14, depthWrite: false }),
    outline: new THREE.LineBasicMaterial({ color: 0x91a9ac, transparent: true, opacity: 0.35, depthWrite: false }),
  };
  // The pieces still where the map has them (not deleted, not moved): their saved floor tiles count
  function floorStays(actor) {
    const list = floorRootsByActor().get(actor);
    return Boolean(list) && list.every(r => !r.userData.deleted && !r.userData.edit);
  }
  let floorRootsCache = null, floorRootsKey = null;
  function floorRootsByActor() {
    if (!floorRootsCache || floorRootsKey !== roots.size) {
      floorRootsCache = new Map(); floorRootsKey = roots.size;
      for (const r of roots.values()) {
        const o = r.userData.source;
        if (o.added || o.layer !== 'base') continue;
        if (!floorRootsCache.has(o.actor)) floorRootsCache.set(o.actor, []);
        floorRootsCache.get(o.actor).push(r);
      }
    }
    return floorRootsCache;
  }
  let groundGridKey = null;
  function refreshGroundGrid(force = true) {
    if (!data || builderMode || data.scope !== 'map' || data.preview || !data.tileGrid?.origin || !data.tileGrid.dimensions) {
      for (const child of [...groundGrid.children]) { child.geometry.dispose(); groundGrid.remove(child); }
      return;
    }
    const ground = groundHeight(), key = `${roots.size}|${editedKey()}|${data.tileGrid.dimensions.join(',')}|${ground}|${cleared}`;
    if (!force && key === groundGridKey) return;
    groundGridKey = key;
    for (const child of [...groundGrid.children]) { child.geometry.dispose(); groundGrid.remove(child); }
    const [ox, oy] = data.tileGrid.origin, [nx, ny] = data.tileGrid.dimensions, [sx, sy, sz] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
    const covered = new Set();
    for (const f of data.tactical?.floorTiles ?? []) {
      if (f.location[2] <= ground + sz / 2 && floorStays(f.actor)) covered.add(`${f.tile[0]},${f.tile[1]}`);
    }
    const y = ground - 2, sheet = [], lines = [], edge = new Set();
    const segment = (x0, z0, x1, z1) => { const k = `${x0},${z0},${x1},${z1}`; if (!edge.has(k)) { edge.add(k); lines.push(x0, y, z0, x1, y, z1); } };
    for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
      if (covered.has(`${i},${j}`)) continue;
      const x0 = ox + i * sx, x1 = x0 + sx, z0 = oy + j * sy, z1 = z0 + sy;
      sheet.push(x0, y, z0, x1, y, z0, x1, y, z1, x0, y, z0, x1, y, z1, x0, y, z1);
      segment(x0, z0, x1, z0); segment(x0, z1, x1, z1); segment(x0, z0, x0, z1); segment(x1, z0, x1, z1);
    }
    if (sheet.length) {
      const mesh = new THREE.Mesh(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(sheet, 3)), groundGridMaterials.sheet);
      mesh.raycast = () => {}; mesh.name = 'groundGridSheet'; groundGrid.add(mesh);
      const grid = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(lines, 3)), groundGridMaterials.line);
      grid.raycast = () => {}; grid.name = 'groundGridLines'; groundGrid.add(grid);
    }
    // the grid's outline at the ground's height, so the gap under it to the play area's bottom is seen
    const X = ox + nx * sx, Z = oy + ny * sy;
    const outline = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(
      [ox, y, oy, X, y, oy, X, y, oy, X, y, Z, X, y, Z, ox, y, Z, ox, y, Z, ox, y, oy], 3)), groundGridMaterials.outline);
    outline.raycast = () => {}; outline.name = 'groundGridOutline'; groundGrid.add(outline);
    groundGrid.userData = { ground, bare: sheet.length / 18 };
  }
  function setGroundGrid(on) {
    groundGrid.visible = Boolean(on); $('groundGridToggle').checked = groundGrid.visible;
    remember(GROUND_GRID, groundGrid.visible ? '1' : '0');
  }
  $('groundGridToggle').checked = groundGrid.visible;
  $('groundGridToggle').onchange = e => { setGroundGrid(e.target.checked); e.target.blur(); };
  // The map's missions (an export's `missions`: its DefaultMaps.ini records) and the one whose streamed packages show.
  // missionPickValue is the picker's value: a record's index ('0', '1', ...), or 'kind:<kind>' for a kind the project
  // adds (mission types plan, D2), which streams nothing; missionIndex is the record's index, -1 for an added kind.
  // (missionIndex, the picker's value, missionPickValue, and the streams shown, streamSet: editor_state.js)
  // (an added kind the address asks for, askedPick: editor_state.js)
  // The missions the header's picker lists: the map's records, or the project's missions when it names them (its
  // records kept, then the kinds it adds).
  function headerMissions() {
    const missions = data?.preview ? [] : data?.missions ?? [];
    const labels = missionLabels(missions);
    const all = missions.map((m, i) => ({ value: String(i), index: i, label: labels[i], mission: m }));
    if (!Array.isArray(projectMissions)) return all;
    const kept = new Set(projectMissions.filter(e => Number.isInteger(e.record)).map(e => e.record));
    return [...all.filter(m => kept.has(m.index)),
            ...projectMissions.filter(e => ADDED_KINDS[e.kind]).map(e => ({ value: `kind:${e.kind}`, index: -1,
                                                                            label: `${ADDED_KINDS[e.kind].label} (added)`, mission: addedMission(e.kind), entry: e }))];
  }
  // the mission the header shows: a record of the map, or a kind the project adds
  const headerMission = () => (missionIndex >= 0 ? (data?.missions ?? [])[missionIndex] : headerMissions().find(m => m.value === missionPickValue)?.mission);
  // The picker's options again (the project's missions changed, or a project opened), keeping the choice when it is
  // still listed.
  function refreshMissionPicker() {
    if (!data) return;
    const list = headerMissions(), before = missionPickValue;
    if (askedPick && list.some(m => m.value === askedPick)) { chooseMission(askedPick); setAskedPick(null); }
    $('missionPick').hidden = list.length < 2;
    $('mission').replaceChildren(...list.map(m => new Option(m.label, m.value)));
    if (!list.some(m => m.value === missionPickValue)) chooseMission(list[0]?.value ?? '0');
    $('mission').value = missionPickValue;
    // (a clear done or undone changes the streams shown, the mission kept: a cleared map shows no patch level's)
    const streams = shownStreams(), same = streams.size === streamSet.size && [...streams].every(s => streamSet.has(s));
    if (!same) setStreamSet(streams);
    if (missionPickValue !== before || !same) runHub('mission');
  }
  // The header's Mission picker as a map opens (app.js's startScene).
  function startMissionPicker() {
    // The mission picker: shown when the map's missions stream different packages (Police Station's data recovery
    // streams its radar arrays, its abduction and terror missions don't).
    const missions = headerMissions();
    $('missionPick').hidden = missions.length < 2;
    $('mission').replaceChildren(...missions.map(m => new Option(m.label, m.value)));
    $('mission').value = missionPickValue;
    $('mission').title = 'Which mission\'s streamed packages to show: LWR\'s patches and the mission\'s own objects, for reference';
  }
  const missionName = m => m.label;
  function missionLabels(missions) {
    const count = {};
    for (const m of missions) count[m.label] = (count[m.label] || 0) + 1;
    // two records of one kind (a landed transport and a landed terror ship): their display names tell them apart
    return missions.map(m => count[m.label] > 1 ? `${m.label} (${m.display.match(/\(([^)]*)\)/)?.[1]?.trim() || m.display})` : m.label);
  }
  function chooseMission(value) {
    const missions = data?.preview ? [] : data?.missions ?? [];
    const v = String(value ?? '0');
    if (v.startsWith('kind:')) { setMissionPickValue(v); setMissionIndex(-1); setStreamSet(new Set()); return; }
    const index = Number(v);
    setMissionIndex(Number.isInteger(index) && missions[index] ? index : 0);
    setMissionPickValue(String(missionIndex));
    setStreamSet(shownStreams());
  }
  // The streams the mission picked shows: its record's, but on a cleared map none of LWR's patch levels, which its
  // build streams none of (their pieces, lights, effects and spawn points were made for the map that is gone; KB-23).
  function shownStreams() {
    const names = missionIndex >= 0 ? (data?.preview ? [] : data?.missions ?? [])[missionIndex]?.streams ?? [] : [];
    return new Set(names.filter(s => !(cleared && data.streams?.[s]?.kind === 'lwr')));
  }

  // The scene's pieces changed (the edit hub's scene run, edit_hub.js): the ground grid drawn again if its pieces did.
  onHub('scene', 'ground-grid', () => { refreshGroundGrid(false); });
  // The cleared mark set, a landing zone edited (the edit hub's cleared and zone-edit runs): the ground grid drawn
  // again.
  onHub('cleared', 'ground-grid', () => { refreshGroundGrid(); });
  onHub('zone-edit', 'ground-grid', () => { refreshGroundGrid(); });
  // The cleared mark set, the project's missions set again by Reset all (the edit hub's cleared and project-missions
  // runs): the header's Mission picker.
  onHub('cleared', 'mission-picker', () => { refreshMissionPicker(); });
  onHub('project-missions', 'mission-picker', () => { refreshMissionPicker(); });

  return { chooseMission, clearMap, clearParts, clearPlan, floorStays, groundGrid, groundHeight, groundWords, headerMission,
           headerMissions, isLanding, mapPicture, missionName, missionsPanel, outsideBox, pointOutside,
           readLandingLines, refreshGroundGrid, showClearMap, showMissions, sizeNotes, startMissionPicker, zonesNow };
}
