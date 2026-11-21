// The cutaway, the tile grid and the Floor tiles overlay (refactor stage P8; first-editor plan, section 2). Here:
// - the cutaway (cutaway): which pieces are drawn, and how each is cut, by the Floor picker (every building at once:
//   the user's choice, 7 November), Interior's planes, the streams of the mission shown, Hide patch helpers, the clear
//   and the landing a moved zone takes along; the status line's count;
// - the tile grid round the selection or the piece being placed (tileTargets, updateTileGrid);
// - View options' Floor tiles: the map's saved floor tiles coloured by the piece that carries each (drawFloorTiles),
//   the tile under the pointer named (floorTileHit, floorTip) and a click on one selecting its piece (floorTileSelect);
// - the Floor picker's buttons up to the tallest building's floors (floorOptions).
//
// createCutaway takes what it needs of app.js as one argument object, when app.js makes it: the scene, the tile grid's
// group, the cut materials and the patch helpers' wireframe, the gizmo, the pieces' listings, the buildings, the
// landing a moved zone takes along, box select's box, picking, the floor buttons and the hints. Its own state is inside
// it (the actors shown and their ceilings, the tiles' owners, what it last followed); the tile grid's key and the
// overlay's layer (tileKey, floorTileLayer: app.js's View options, draw loop and test hooks read or set them) are
// editor_state.js's. After an edit it follows the pieces through the edit hub (edit_hub.js).
import * as THREE from 'three';
import { TILE } from './constants.js';
import { onHub, STOP } from './edit_hub.js';
import { builderMode, cleared, data, floorTileLayer, landingZones, loadErrorCount, pickBox, pickDrag, placing, pointer,
         roots, selected, setFloorTileLayer, setTileKey, setTipDirty, streamSet, tileKey } from './editor_state.js';
import { stampSignature } from './floors.js';
import { withLocalLights } from './lighting.js';
import { floorTilesOverlay, focusBounds, footprintOf, interiorPlanes, tileGridAround } from './view_layout.js';
import { plural, short, text } from './dom_words.js';

export function createCutaway({ $, allBuildings, cutMaterials, editedKey, flashHint, gizmo, grid, helperMaterial,
                                isStream, listingsNow, movedLandingActors, rayAt, refreshPickBox, segButton, select,
                                touchShadows, viewport, world }) {
  const WHOLE_OVERHANG = 4 * TILE;    // four tiles
  // the pieces' edits the cutaway last followed (floor_listings.js's editedKey), so the edit hub runs it again only
  // when they changed
  let cutKey = '';
  function cutaway() {
    touchShadows();
    cutKey = editedKey();
    // The floor cut applies to every building at once (the user's choice, 7 November: no building list).
    const requested = $('floor').value ?? 'all';
    const interior=$('scenery').value==='interior';
    const allFloors = $('floor').querySelector('[data-value=all]');
    if (allFloors) allFloors.title = interior ? 'All interior floors' : 'All floors · roof closed';
    const scenePlanes=interior ? interiorPlanes(data) : [];
    // Interior draws a piece that reaches into its area whole across the map (only the height cut stays), unless it
    // reaches more than WHOLE_OVERHANG past the area's sides: big ground and long walls stay cut there, so the outside
    // doesn't come back with them. (interiorPlanes: x min/max, then the height's two, then z min/max.)
    const focus=interior ? focusBounds(data) : null, heightPlanes=scenePlanes.slice(2, 4);
    const actors=new Map();
    const movedLanding = landingZones && !builderMode ? movedLandingActors() : null;
    for (const root of roots.values()) {
      const obj = root.userData.source;
      // a streamed package's pieces show with the chosen mission's streams
      const shownStream = !isStream(obj) || streamSet.has(obj.stream);
      const helper = (obj.layer === 'inherited' || isStream(obj)) && shownStream && obj.hidden && obj.hiddenBy == null && !$('hideHelpers').checked;
      root.visible = (!obj.hidden || helper) && !obj.environment && !root.userData.deleted && shownStream
        && !(cleared && isStream(obj) && data.streams?.[obj.stream]?.kind === 'lwr') && !(movedLanding?.has(obj.actor));
      // Pieces the user added always count as part of the playable scene, whatever their source's layer.
      root.userData.tacticalExcluded=interior && !obj.provenance && !obj.added && ['backdrop','roof','helper'].includes(obj.sceneryRole);
      root.visible &&= !root.userData.tacticalExcluded;
      let height = Infinity;
      if (requested !== 'all') {
        const idx = Number(requested)-1;
        const groups = new Map();
        for (const entry of listingsNow(root)) {
          const old = groups.get(entry.building);
          // The game's floor pass runs top to bottom: the lowest cache entry wins.
          if (!old || entry.floor < old.floor) groups.set(entry.building,entry);
        }
        if (groups.size) {
          const entries = [...groups.values()];
          root.visible &&= entries.some(f => f.floor <= idx);
          for (const f of entries) {
            if (obj.cutout && f.floor <= idx && f.cutdownFloor > idx) {
              const building = allBuildings().find(b => b.id === f.building);
              const top = building?.floors[idx]?.top;
              if (top != null) height = Math.min(height,top);
            }
          }
        }
      }
      root.userData.cutHeight = height;
      let whole = false;
      if (focus && root.visible) {
        const box = new THREE.Box3().setFromObject(root);
        whole = !box.isEmpty() && box.intersectsBox(focus)
          && Math.max(focus.min.x - box.min.x, box.max.x - focus.max.x, focus.min.z - box.min.z, box.max.z - focus.max.z) <= WHOLE_OVERHANG;
      }
      root.userData.interiorWhole = whole;
      const planes=whole ? [...heightPlanes] : [...scenePlanes];
      if(Number.isFinite(height))planes.push(new THREE.Plane(new THREE.Vector3(0,-1,0),height));
      root.userData.clippingPlanes=planes;
      const actor=actors.get(obj.actor) || {visible:false,ceiling:-Infinity};
      actor.visible ||= root.visible;if(root.visible)actor.ceiling=Math.max(actor.ceiling,height);
      actors.set(obj.actor,actor);
      root.traverse(part => {
        if (!part.isMesh || !part.userData.baseMaterial) return;
        const base = part.userData.baseMaterial;
        if (helper) {part.material=helperMaterial;part.castShadow=false;}
        else if (planes.length) {
          const key = `${base.uuid}:${height}:${interior}:${whole}`;
          if (!cutMaterials.has(key)) {
            const mat = withLocalLights(base.clone());
            mat.clippingPlanes = planes;
            mat.clipShadows = true; cutMaterials.set(key,mat);
          }
          part.material = cutMaterials.get(key);
        } else part.material = base;
      });
    }
    // The tile grid follows the saved floors whose actors are shown: draw it again; and the Floor tiles overlay.
    floorActors=actors;setTileKey(null);
    drawFloorTiles();
    if (selected) select(selected, false, true);
    const count=[...roots.values()].filter(r=>r.visible).length;
    $('status').textContent=`${count} visible pieces · ${data.counts.meshes} meshes · ${data.counts.textures} textures${loadErrorCount ? ` · ${loadErrorCount} display errors` : ''}`;
    if (pickBox && !pickDrag) refreshPickBox(true);
  }
  // The tile grid (first-editor plan, section 2): only the tiles around the selection, or around the piece being placed,
  // with the tiles its bounds cover filled (view_layout.js tileGridAround). It is drawn again whenever what it follows
  // moves or turns, or the cutaway changes.
  let floorActors = null;     // (tileKey: editor_state.js)
  function tileTargets() {
    if (!$('grid').checked || !data) return [];
    if (placing) return placing.ghost.visible ? [placing.ghost.children[1]] : [];
    return gizmo.selection().filter(root => root.visible && !root.userData.light && !root.userData.volume && !root.userData.effect);
  }
  function updateTileGrid() {
    const targets = tileTargets();
    // Children too: the footprint is read from each mesh's own world matrix.
    for (const t of targets) t.updateWorldMatrix(true, true);
    const key = targets.map(t => t.uuid + ':' + t.matrixWorld.elements.map(v => v.toFixed(2)).join(',')).join('|');
    if (key === tileKey) return;
    setTileKey(key);
    for (const child of [...grid.children]) {
      grid.remove(child);
      child.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
    }
    const note = $('tileNote'), foot = targets.length ? footprintOf(targets, data) : null;
    note.hidden = !foot;
    if (!foot) return;
    const local = tileGridAround(foot, data, floorActors);
    grid.add(local);
    const { tiles, edges, level, gap, floating } = local.userData;
    note.textContent = `${plural(tiles.length, 'tile')}${edges.length ? ` + ${edges.length} at the edge` : ''} · level ${level}`
      + (floating ? ` · ${Math.round(gap)} above the floor: may give no cover` : '');
    note.classList.toggle('floating', floating);
  }
  // The Floor tiles overlay (View options; view_layout.js floorTilesOverlay): the map's saved floor tiles, coloured by the
  // piece that carries each (one colour per kind of piece: copies of one piece share it), hatched grey where
  // that piece was moved or deleted since. The tiles of pieces hidden or cut away in the view are left out. Hovering a
  // tile names its piece; a click selects it. Drawn again with the cutaway.
  let tileOwners = null;     // (floorTileLayer, tipDirty: editor_state.js)
  function signatureColor(signature) {
    let h = 2166136261;
    for (let i = 0; i < signature.length; i++) { h ^= signature.charCodeAt(i); h = Math.imul(h, 16777619); }
    return new THREE.Color().setHSL(((h >>> 0) % 360) / 360, 0.62, 0.56).getHex();
  }
  function drawFloorTiles() {
    if (floorTileLayer) {
      world.remove(floorTileLayer);
      floorTileLayer.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
      setFloorTileLayer(null);
    }
    $('floorTip').hidden = true;
    if (!data || !$('floorTiles').checked) return;
    const owners = new Map();     // an original's actor -> { roots, sources, gone, color }
    for (const r of roots.values()) {
      const o = r.userData.source;
      if (o.added || o.layer !== 'base') continue;
      if (!owners.has(o.actor)) owners.set(o.actor, { roots: [], sources: [] });
      owners.get(o.actor).roots.push(r); owners.get(o.actor).sources.push(o);
    }
    for (const s of owners.values()) {
      s.gone = s.roots.some(r => r.userData.deleted || r.userData.edit);
      s.color = signatureColor(stampSignature(s.sources));
    }
    tileOwners = owners;
    setFloorTileLayer(floorTilesOverlay(data, {
      shown: f => { const s = owners.get(f.actor), a = floorActors?.get(f.actor);
        if (cleared && s?.gone) return false;     // a cleared map: the gone pieces' tiles are left out, not hatched
        return !s || s.gone || !a || (a.visible && f.location[2] <= a.ceiling + 1); },
      colorOf: a => owners.get(a)?.color ?? 0x82d5ce, gone: a => Boolean(owners.get(a)?.gone) }));
    world.add(floorTileLayer);
  }
  function floorTileHit(clientX, clientY) {
    const mesh = floorTileLayer?.getObjectByName('floorTiles');
    const hit = mesh && rayAt(clientX, clientY).intersectObject(mesh)[0];
    return hit ? { tile: floorTileLayer.userData.tiles[Math.floor(hit.faceIndex / 2)], distance: hit.distance } : null;
  }
  function floorTip() {
    setTipDirty(false);
    const tip = $('floorTip'), hit = pointer && !gizmo.controls.dragging ? floorTileHit(...pointer) : null;
    tip.hidden = !hit;
    if (!hit) return;
    const f = hit.tile, s = tileOwners?.get(f.actor), mesh = s ? data.meshes[s.sources[0].mesh]?.name : null;
    tip.replaceChildren();
    text(tip, 'strong', short(mesh ?? f.actor));
    text(tip, 'small', `${short(f.actor)} · tile ${f.tile[0]}, ${f.tile[1]} · level ${f.tile[2]}`);
    if (s?.gone) text(tip, 'small', s.roots.some(r => r.userData.deleted) ? 'deleted since: the Build\'s rebuild checks this tile again'
                                                                            : 'moved since: the Build\'s rebuild checks this tile again');
    const rect = viewport.getBoundingClientRect();
    tip.style.left = `${pointer[0] - rect.left}px`; tip.style.top = `${pointer[1] - rect.top}px`;
  }
  // A click on a saved floor tile selects its piece, unless another piece stands nearer in front of it.
  function floorTileSelect(e, hit) {
    const tile = floorTileLayer && floorTileHit(e.clientX, e.clientY);
    if (!tile || (hit && hit.distance < tile.distance - 1)) return false;
    const s = tileOwners?.get(tile.tile.actor), live = s?.roots.filter(r => !r.userData.deleted) ?? [];
    if (live.length) { select((live.find(r => r.visible) ?? live[0]).userData.source.id, e.ctrlKey || e.shiftKey || e.metaKey); return true; }
    if (s) { flashHint(`${short(tile.tile.actor)}, which carries that tile, is deleted: Ctrl+Z or Reset all brings it back`); return true; }
    return false;
  }
  // Floor buttons up to the tallest building's floors. The chosen floor stays if there still is one.
  function floorOptions() {
    const previous = $('floor').value;
    const count = Math.max(0,...allBuildings().map(b => b.floors.length));
    $('floorGroup').hidden = !count;
    const buttons = [segButton('all', 'All', 'All floors · roof closed')];
    for (let i=1;i<=count;i++) buttons.push(segButton(String(i), String(i), i === 1 ? 'Up to the ground floor' : `Up to floor ${i}`));
    $('floor').replaceChildren(...buttons);
    $('floor').value = buttons.some(b => b.dataset.value === previous) ? previous : 'all';
    cutaway();
  }
  // View options' patch helpers and the layout's patches and streams, as a scene opens (app.js's startScene; the Floor
  // picker is shown or hidden by floorOptions, which it calls after the pieces are placed).
  function sceneViewOptions(streamObjects) {
    // Patch helpers: pieces a patch places hidden in game (LWR's blockers and cover, ladders' collision), hidden here
    // too by default; unticking Hide patch helpers draws them as a wireframe.
    const streamHelpers = streamObjects.some(o => o.hidden);
    $('helpersRow').hidden = !(data.inheritedPatches?.length || streamHelpers);
    $('composition').textContent = [...(data.inheritedPatches || []).map(p=>{
      const removed=data.objects.filter(o=>o.layer==='inherited' && o.sourcePackage===p.name && o.hiddenBy!=null).length;
      return `${p.name} · ${p.components} source helpers${removed ? ` (${removed} removed by layout)` : ''} · ${p.records.filter(r=>r.actorClass==='XComRebuildWorldDataVolume').length} rebuild volumes`;
    }), ...(data.preview ? [] : Object.entries(data.streams || {}).map(([name, s]) =>
      `${name} · ${s.error ? `not shown: ${s.error}` : `${s.objects.length} pieces (${s.hiddenComponents} hidden in game), ${s.rebuildVolumes} rebuild volumes`}`))].join(' / ');
  }

  // After an edit (the edit hub, edit_hub.js).
  onHub('edit', 'cutaway', () => {
    // pieces moved, deleted or brought back: the cutaway follows once a drag ends
    if (data && !gizmo.controls.dragging && editedKey() !== cutKey) { cutaway(); if (selected) return STOP; }   // (cutaway's select ran the hub)
  });

  // The scene's pieces, or the mission picked, changed (the edit hub's scene and mission runs, edit_hub.js).
  onHub('scene', 'cutaway', () => { cutaway(); });
  onHub('mission', 'cutaway', () => { cutaway(); });

  return { cutaway, drawFloorTiles, floorOptions, floorTileSelect, floorTip, sceneViewOptions, updateTileGrid };
}
