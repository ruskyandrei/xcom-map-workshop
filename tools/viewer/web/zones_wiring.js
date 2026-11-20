// The Landing zones view (refactor stage P6; Clear map plan, section 4; spawns.js holds the zones' rules: their
// soldier points, the map's own landings and which zones plain Enemy Within lands at). Each landing zone, the map's or
// the project's, is drawn as its footprint on the landing zones' layer. Here:
// - the view on or off (setZonesShown) and the Add panel's Landing zones kind (zoneEntries);
// - the zones drawn (refreshLandingZones) and the map's own landing pieces a moved zone takes along
//   (movedLandingActors);
// - a zone picked (pickZone, zoneHit), its gizmo (moved by whole tiles and levels, turned by quarter turns) and its
//   panel (landingPanel, its notes and its controls);
// - the zones changed, each change one undo step (setZones, changeZone): copied, deleted, a kind or a game's mark
//   changed; a zone added with a click (startZonePlacing, placeZone);
// - what follows a change of the cleared mark (clearedChanged).
//
// createZonesWiring takes what it needs of app.js as one argument object, when app.js makes it: the camera, the
// renderer and the scene, the landing zones' layer and its storage key, the other views' switches, the header's
// mission and the Clear map window's zones. Its own state is inside it (whether the layer was hidden before the view,
// the gizmo's mode and drag, the floor tiles' tops); what other areas read or set (the view's switch, the picked zone,
// the project's zones, whether a click places one) is editor_state.js's.
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { LEVEL, TILE } from './constants.js';
import { builderMode, cleared, data, effectsOn, landingZones, lightsOn, pickedZone, pieces, placing, project, roots,
         selected, setEffectsDirty, setLandingZones, setMergedBuildings, setPickedZone, setZonePlacing, setZonesOn,
         spawnsOn, stage, volumesOn, zonePlacing, zonesOn } from './editor_state.js';
import { zoneServes } from './missions.js';
import { uuid } from './project.js';
import { DIRECTIONS as ZONE_DIRECTIONS, evacBox, explicitEw, GROUND as ZONE_GROUND, groundOf, landingUnmoved,
         ownLandings, ownSlots, soldierSpots, turn as turnBy, yawOf } from './spawns.js';
import { remember } from './storage.js';

export function createZonesWiring({ $, banner, camera, controls, cutaway, editChanged, flashHint, floorStays,
                                   gameToView, gizmo, groundHeight, headerMission, isLanding, landHere, LANDING_SHOWN,
                                   landingLayer, lightButton, ownSize, plural, projectChanged, projectsAvailable, rayAt,
                                   refreshGroundGrid, refreshLightVisibility, refreshMissionPicker, renderer,
                                   restingHint, select, setEffectsShown, setLightsShown, setSpawnsShown,
                                   setVolumesShown, stopPickBox, tileCorner, world, zonesNow }) {
  // ---------------------------------------------------------------- landing zones (Clear map plan, section 4)
  // Each zone drawn as its footprint: the evac zone's box (faint), the six soldier points as dots, an arrow the way the
  // squad faces, its number, and for a zone that is one of the map's own landings the grounded Skyranger's outline. A
  // click picks one (ahead of the pieces under it); dragged, it moves by whole tiles; the panel turns it, raises it,
  // orders, copies and deletes it. Every change is one undo step, and the first one makes the project's own list.
  // the Landing zones view (the user, 13 November 2026): the zones over everything, and only they are picked
  let zonesHidBefore = false;     // (zonesOn: editor_state.js)
  // The Landing zones view (Shift+Z): the zones shown and drawn over everything (under a floor, inside a piece), and a
  // click picks a zone or lets the picked one go, never a piece or a light. The zones' layer is put back as it was after.
  function setZonesShown(on) {
    on = Boolean(on) && Boolean(data) && data.scope === 'map' && !data.preview && !builderMode;
    if (on === zonesOn) return;
    if (on) {
      if (spawnsOn) setSpawnsShown(false);      // (first: it puts the zones' layer back as it was)
      if (volumesOn) setVolumesShown(false);
      if (lightsOn) setLightsShown(false);
      if (effectsOn) setEffectsShown(false);
      stopPickBox(); select(null);
      zonesHidBefore = !landingLayer.visible;
      landingLayer.visible = true;
    } else {
      setPickedZone(null);
      stopZonePlacing();      // a zone asked for from the Add panel and not placed yet goes with its view
      if (zonesHidBefore) landingLayer.visible = false;
    }
    setZonesOn(on);
    refreshLandingZones(); lightButton();
    if (on) flashHint('Landing zones view: only landing zones are selected · Shift+Z leaves it');
  }
  // The piece list's Landing zones kind: one entry, placed with a click (the one way to add a zone)
  function zoneEntries() {
    if (!data || data.scope !== 'map' || data.preview || builderMode) return [];
    const count = zonesNow().length;
    return [{ key: 'zone', id: 'zone-new', zone: true, name: 'Landing zone', kind: 'Landing zones', pkg: 'where the squad lands',
              detail: 'Placed on a tile, facing north; moved and turned with its gizmo', count, builds: true,
              title: 'A new landing zone: click the tile it is to stand on. It starts as a copy of the first zone\'s kind, facing north, and is used by Long War (tick Plain EW in its panel for plain Enemy Within)',
              sources: [], pivotIndex: 0, materials: [], milestone: 1, role: null, size: [0, 0, 0], extent: 0, mesh: '',
              text: 'landing zone lz drop zone skyranger squad start spawn evac' }];
  }
  const ZONE_OWN = 0x4aa3ff, ZONE_LWR = 0xffb347, ZONE_PICKED = 0xffffff;
  // (whether the next click places a zone, zonePlacing, and the picked zone, pickedZone: editor_state.js)
  // While the zone gizmo is dragged: { id, change } drawn in place of the zone (zoneState)
  let zoneDragView = null;
  const zoneMaterial = (color, opacity, through = false) => (through
    ? new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false, depthTest: false })
    : new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide }));
  // The zones and which are the map's own landings: { zones, own (the map's own landings), slots (zone index -> own index) }
  function zoneState() {
    const zones = zonesNow().map(z => (zoneDragView?.change && z.id === zoneDragView.id ? { ...z, ...zoneDragView.change } : z)), own = data ? ownLandings(data) : [], slots = new Map(ownSlots(zones, own.length).map((z, k) => [z, k]));
    return { zones, own, slots };
  }
  // The floor's top under a point at a zone's ground: the map's floor tile there on the ground's level, by its saved
  // height (the tutorial's road is 18 over its level's start, so marks at the ground itself sink under it), else null
  let floorTopIndex = null;
  function floorTop(x, y, ground) {
    const grid = data?.tileGrid;
    if (!grid?.origin || !data.tactical?.floorTiles) return null;
    if (floorTopIndex?.data !== data) {
      const tops = new Map();
      for (const f of data.tactical.floorTiles) tops.set(f.tile.join(','), Math.max(tops.get(f.tile.join(',')) ?? -Infinity, f.location[2]));
      floorTopIndex = { data, tops };
    }
    // the spot's tile as the game counts it; its ground's level takes a ground up to a unit under a level's start (the
    // maps' floors are a unit over the game's corner: 2 over the origin, as before)
    const [ox, oy, oz] = tileCorner(), [sx, sy, sz] = grid.size ?? [TILE, TILE, LEVEL];
    const key = [Math.floor((x - ox) / sx), Math.floor((y - oy) / sy), Math.floor((ground + 1 - oz) / sz)].join(',');
    const top = floorTopIndex.tops.get(key);
    return top !== undefined && top >= ground - 8 && top <= ground + sz ? top : null;
  }
  // Where the squad stands for a zone (spawns.js soldierSpots): a landing with no frame (the tutorial's) keeps its own
  // points while its zone stays where the map has it
  function zoneSoldiers(z, st = zoneState()) {
    const k = st.zones.findIndex(x => x.id === z.id);
    return soldierSpots(z, k >= 0 && st.slots.has(k) ? st.own[st.slots.get(k)] : null);
  }
  function zoneLabel(text, color) {
    const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 64;
    const c = canvas.getContext('2d');
    c.fillStyle = `#${color.toString(16).padStart(6, '0')}`; c.beginPath(); c.arc(32, 32, 28, 0, Math.PI * 2); c.fill();
    c.fillStyle = '#10161a'; c.font = 'bold 34px sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(text, 32, 34);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false, transparent: true }));
    sprite.scale.set(70, 70, 1); sprite.renderOrder = 9; sprite.raycast = () => {};
    return sprite;
  }
  // The rigid move from one of the map's own landings to its zone: a point of the landing (the Skyranger) carried along
  function carried(point, from, to) {
    const d = yawOf(to.direction) - yawOf(from.direction), v = turnBy([point[0] - from.location[0], point[1] - from.location[1], 0], d);
    return [to.location[0] + v[0], to.location[1] + v[1], point[2] + (to.location[2] - from.location[2])];
  }
  function refreshLandingZones() {
    for (const child of [...landingLayer.children]) {
      child.traverse(o => { o.geometry?.dispose(); if (o.material?.map) o.material.map.dispose(); });
      landingLayer.remove(child);
    }
    const on = data && !builderMode && data.scope === 'map' && !data.preview;
    $('landingRow').hidden = !on;
    placeZoneGizmo();
    if (!on) { $('landingPanel').hidden = true; return; }
    const st = zoneState(), { zones, own, slots } = st;
    zones.forEach((z, k) => {
      const group = new THREE.Group(), soldiers = zoneSoldiers(z, st), ground = groundOf(z), picked = z.id === pickedZone;
      // the marks lie on the floor under each soldier point, so a floor over the level's start doesn't hide them
      const tops = soldiers.map(s => floorTop(s.location[0], s.location[1], ground) ?? ground), lift = Math.max(...tops);
      const color = picked ? ZONE_PICKED : slots.has(k) ? ZONE_OWN : ZONE_LWR;
      group.userData.zoneId = z.id;
      const b = evacBox(z);
      // the evac zone's footprint on the ground (picked by it) and its box faintly
      const foot = new THREE.Mesh(new THREE.PlaneGeometry(b[3] - b[0], b[4] - b[1]).rotateX(-Math.PI / 2), zoneMaterial(color, picked ? 0.32 : 0.18));
      foot.position.set((b[0] + b[3]) / 2, lift + 3, (b[1] + b[4]) / 2); foot.userData.zoneId = z.id; foot.renderOrder = 3;
      group.add(foot);
      const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(b[3] - b[0], b[5] - b[2], b[4] - b[1])), zoneMaterial(color, 0.45, true));
      box.position.set((b[0] + b[3]) / 2, (b[2] + b[5]) / 2, (b[1] + b[4]) / 2); box.raycast = () => {}; group.add(box);
      // the six soldier points, where the squad stands
      soldiers.forEach((s, n) => {
        const dot = new THREE.Mesh(new THREE.CircleGeometry(22, 20).rotateX(-Math.PI / 2), zoneMaterial(color, 0.85));
        dot.position.copy(gameToView([s.location[0], s.location[1], tops[n] + 4])); dot.renderOrder = 4; dot.userData.zoneId = z.id; group.add(dot);
      });
      // an arrow the way the squad faces (the soldier points' facing)
      const mid = soldiers.reduce((a, s) => [a[0] + s.location[0] / soldiers.length, a[1] + s.location[1] / soldiers.length], [0, 0]);
      const f = turnBy([1, 0, 0], soldiers[0].yaw), tip = [mid[0] + f[0] * 260, mid[1] + f[1] * 260], side = [-f[1] * 50, f[0] * 50];
      const arrow = [mid[0], mid[1], tip[0], tip[1], tip[0], tip[1], tip[0] - f[0] * 70 + side[0], tip[1] - f[1] * 70 + side[1], tip[0], tip[1],
                     tip[0] - f[0] * 70 - side[0], tip[1] - f[1] * 70 - side[1]];
      const pts = []; for (let i = 0; i < arrow.length; i += 2) pts.push(arrow[i], lift + 6, arrow[i + 1]);
      const line = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)), zoneMaterial(color, 0.9, true));
      line.raycast = () => {}; group.add(line);
      const label = zoneLabel(String(k + 1), color); label.position.copy(gameToView([mid[0], mid[1], lift + 140])); group.add(label);
      // the number is drawn over everything and picks its zone wherever the zone is (under a floor, inside a piece)
      delete label.raycast; label.userData.zoneId = z.id; label.userData.zoneBadge = true;
      // one of the map's own landings: the grounded Skyranger, carried with it
      const o = slots.has(k) ? own[slots.get(k)] : null, mesh = o?.landing?.skyranger?.actors?.find(a => a.role === 'mesh');
      if (mesh) {
        const c = carried(mesh.location, o.zone, z), yaw = mesh.rotation[1] + yawOf(z.direction) - yawOf(o.zone.direction);
        const outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(900, 300, 700)), zoneMaterial(color, 0.3, true));
        outline.position.copy(gameToView([c[0], c[1], c[2] + 150])); outline.rotation.y = -yaw * Math.PI / 32768; outline.raycast = () => {};
        group.add(outline);
      }
      // the Landing zones view: drawn over everything
      if (zonesOn) group.traverse(o => { if (o.material) { o.material.depthTest = false; o.renderOrder = Math.max(o.renderOrder, 8); } });
      landingLayer.add(group);
    });
    landingPanel();
  }
  // The map's own landing pieces (the frame, the Skyranger) whose zone has moved from where the map has them (as the
  // Build reckons it: spawns.js landingUnmoved, so a zone a unit off its frame keeps them): the zone draws them, the
  // pieces are not shown
  function movedLandingActors() {
    const { zones, own, slots } = zoneState(), out = new Set();
    for (const [k, j] of slots) {
      const o = own[j], z = zones[k];
      if (landingUnmoved(z, o)) continue;
      if (o.frame) out.add(o.frame);
      for (const a of o.landing?.skyranger?.actors ?? []) out.add(a.path);
      if (!o.landing) {     // an older export: the Skyranger nearest the frame
        const sky = [...roots.values()].map(r => r.userData.source).filter(s => isLanding(s) && /skyranger/i.test(s.archetype ?? ''))
          .sort((a, b) => Math.hypot(a.location[0] - o.zone.location[0], a.location[1] - o.zone.location[1])
                        - Math.hypot(b.location[0] - o.zone.location[0], b.location[1] - o.zone.location[1]))[0];
        if (sky) out.add(sky.actor);
      }
    }
    return out;
  }
  // A change of the zones as one undo step; the project's own list from the first change on
  function setZones(next, words) {
    const before = landingZones ? landingZones.map(z => ({ ...z })) : null, after = next.map(z => ({ ...z }));
    gizmo.record({
      redo: () => { setLandingZones(after.map(z => ({ ...z }))); zonesChanged(); },
      undo: () => { setLandingZones(before ? before.map(z => ({ ...z })) : null); zonesChanged(); },
    });
    if (words) flashHint(`${words} · Ctrl+Z undoes`);
  }
  function zonesChanged() {
    if (pickedZone && !zonesNow().some(z => z.id === pickedZone)) setPickedZone(null);
    setEffectsDirty(true);     // (the landing's effects and sound follow a moved zone)
    refreshLandingZones(); refreshGroundGrid(); cutaway(); projectChanged(); editChanged();
  }
  // The zones with plain EW's marks written out (`ew: true`): a list saved before the mark goes by order (ownSlots),
  // and any change keeps the zones plain EW played
  function explicitZones() {
    const zones = zonesNow().map(z => ({ ...z }));
    if (!explicitEw(zones)) for (const k of ownSlots(zones, data ? ownLandings(data).length : 0)) zones[k].ew = true;
    return zones;
  }
  function changeZone(id, change, words) {
    const zones = explicitZones(), k = zones.findIndex(z => z.id === id);
    if (k < 0) return;
    const next = change(zones, k);
    if (next) setZones(next, words);
  }
  function pickZone(id) {
    if (id && !zonesOn) setZonesShown(true);     // a zone is picked and edited in the Landing zones view only
    setPickedZone(id);
    if (id && selected) select(null);
    refreshLandingZones();
  }
  // The picked zone's gizmo (the user, 13 November: a gizmo in place of the panel's buttons). Its handle stands on the
  // drop zone's frame (StartLoc), on the ground. It moves the zone by whole tiles across and whole levels (64 units) up,
  // and turns it by quarter turns about the vertical: the only steps a zone takes (an LZArray line faces one of four
  // ways). G shows the arrows, R the ring; each drag is one undo step, Escape during one puts it back.
  const zoneProxy = new THREE.Object3D(); world.add(zoneProxy);
  const zoneGizmo = new TransformControls(camera, renderer.domElement);
  zoneGizmo.attach(zoneProxy); zoneGizmo.enabled = false; zoneGizmo.setRotationSnap(Math.PI / 2);
  const zoneGizmoHelper = zoneGizmo.getHelper(); zoneGizmoHelper.visible = false; world.add(zoneGizmoHelper);
  let zoneGizmoMode = 'translate', zoneGizmoDrag = null;
  const zoneGizmoWanted = () => Boolean(pickedZone && zonesOn && landingLayer.visible && !placing && !volumesOn && !lightsOn);
  function placeZoneGizmo() {
    const z = zoneGizmoWanted() ? zonesNow().find(v => v.id === pickedZone) : null;
    zoneGizmo.enabled = zoneGizmoHelper.visible = Boolean(z);
    if (!z || zoneGizmo.dragging) return;
    zoneProxy.position.copy(gameToView([z.location[0], z.location[1], groundOf(z)]));
    zoneProxy.quaternion.identity(); zoneProxy.updateMatrixWorld(true);
    zoneGizmo.setMode(zoneGizmoMode);
    zoneGizmo.showX = zoneGizmo.showZ = zoneGizmoMode !== 'rotate';
  }
  function setZoneGizmoMode(mode) {
    zoneGizmoMode = mode; placeZoneGizmo();
    flashHint(mode === 'rotate' ? 'Turn the landing zone by quarter turns (G moves it)' : 'Move the landing zone by whole tiles and levels (R turns it)');
  }
  zoneGizmo.addEventListener('dragging-changed', e => { controls.enabled = !e.value; });
  zoneGizmo.addEventListener('mouseDown', () => {
    const z = zonesNow().find(v => v.id === pickedZone);
    zoneGizmoDrag = z ? { id: z.id, from: z, at: zoneProxy.position.clone(), change: null, key: '' } : null;
  });
  zoneGizmo.addEventListener('objectChange', () => {
    const d = zoneGizmoDrag;
    if (!d || d.cancelled) return;
    if (zoneGizmo.mode === 'translate') {
      const p = zoneProxy.position, dx = Math.round((p.x - d.at.x) / TILE) * TILE, dz = Math.round((p.z - d.at.z) / TILE) * TILE,
            dy = Math.round((p.y - d.at.y) / LEVEL) * LEVEL;
      p.set(d.at.x + dx, d.at.y + dy, d.at.z + dz);
      // the zone's ground lands on a level of the grid: a zone saved off the levels (the tutorial's, fitted before the
      // ground was snapped: 16 under the grid) comes onto one with its first move
      const l = d.from.location, oz = data.tileGrid?.origin?.[2] ?? 0, ground = l[2] - ZONE_GROUND + dy;
      const level = Math.round(oz + Math.round((ground - oz) / LEVEL) * LEVEL) + ZONE_GROUND;
      const z = data.tileGrid && Math.abs(level - (l[2] + dy)) >= 1 ? level : l[2] + dy;
      d.change = dx || dy || dz ? { location: [l[0] + dx, l[1] + dz, z] } : null;
    } else {
      // a turn about the view's up is the opposite turn of the game's yaw (the view's basis is x, up, y)
      const q = Math.round(2 * Math.atan2(zoneProxy.quaternion.y, zoneProxy.quaternion.w) / (Math.PI / 2));
      zoneProxy.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), q * Math.PI / 2);
      const turns = ((-q % 4) + 4) % 4;
      d.change = turns ? { direction: ZONE_DIRECTIONS[(ZONE_DIRECTIONS.indexOf(d.from.direction) + turns) % 4] } : null;
    }
    const key = JSON.stringify(d.change);
    if (key !== d.key) { d.key = key; zoneDragView = { id: d.id, change: d.change }; refreshLandingZones(); }
  });
  zoneGizmo.addEventListener('mouseUp', () => {
    const d = zoneGizmoDrag;
    zoneGizmoDrag = null; zoneDragView = null;
    if (d?.change && !d.cancelled)
      changeZone(d.id, (zones, k) => { zones[k] = { ...zones[k], ...d.change }; return zones; }, d.change.direction ? 'Turned the landing zone' : 'Moved the landing zone');
    else refreshLandingZones();
    setTimeout(placeZoneGizmo, 0);       // (the controls end their drag after this event)
  });
  function cancelZoneGizmo() {
    if (!zoneGizmoDrag) return;
    zoneGizmoDrag.cancelled = true; zoneDragView = null; refreshLandingZones();
  }
  function zoneHit(clientX, clientY) {
    if (!landingLayer.visible || !landingLayer.children.length) return null;
    const hits = rayAt(clientX, clientY).intersectObjects(landingLayer.children, true).filter(h => h.object.userData.zoneId);
    // a zone's number badge first: it is drawn over everything, so a click on it is meant for its zone
    const hit = hits.find(h => h.object.userData.zoneBadge) ?? hits[0];
    return hit ? { id: hit.object.userData.zoneId, distance: hit.distance, point: hit.point, badge: Boolean(hit.object.userData.zoneBadge) } : null;
  }
  // The panel for the picked zone: its number, whether it is one of the map's own landings, its kind and mission, notes
  function landingPanel() {
    const panel = $('landingPanel'), { zones, own, slots } = zoneState(), k = zones.findIndex(z => z.id === pickedZone);
    panel.hidden = k < 0 || volumesOn;
    if (k < 0) return;
    const z = zones[k];
    $('landingTitle').textContent = `Landing zone ${k + 1} of ${zones.length}`;
    const group = own[slots.get(k)]?.group;
    $('landingInfo').textContent = [slots.has(k) && own.length > 1 ? `Plain EW lands here in place of the map's own landing ${slots.get(k) + 1}${/^Group/.test(group ?? '') ? ` (${group})` : ''}.` : '',
      z.missionType || z.councilType ? `Kept for ${[z.missionType, z.councilType].filter(Boolean).join(', ')}.` : '',
      `Facing ${z.direction}; ground at ${Math.round(groundOf(z))}.`].filter(Boolean).join(' ');
    $('landingKind').value = ['normal', 'inside'].includes(z.kind) ? z.kind : 'normal';
    $('landingKind').disabled = !['normal', 'inside'].includes(z.kind ?? 'normal');
    $('landingLwr').checked = z.lwr !== false;
    $('landingEw').checked = slots.has(k);
    $('landingEw').disabled = !own.length;
    $('landingEw').parentElement.title = own.length ? `Plain Enemy Within lands here: one of the map's own landings is moved to this zone in the package. This map has ${plural(own.length, 'landing')} of its own, so up to ${own.length} zone${own.length === 1 ? '' : 's'} can be marked`
      : 'This map has no landing of its own that the editor can read, so plain Enemy Within plays none of these zones';
    $('landingPlay').hidden = !project || !projectsAvailable();
    const mission = headerMission(), serves = zoneServes(z, mission);
    $('landingPlay').disabled = !serves;
    $('landingPlay').title = serves ? 'Play in game, the squad landing at this zone' + (mission ? ` (${mission.label}, the mission the header shows)` : '')
      : `This zone is kept for another mission than the one the header shows (${mission?.label}): pick that mission in the header to land here`;
    const notes = zoneNotes(z, k, { zones, own, slots });
    $('landingNotes').hidden = !notes.length; $('landingNotes').textContent = notes.join(' ');
  }
  // Notes while editing, none of which blocks: outside the grid, a soldier point over no floor, a piece on one, played
  // under LWR only, played nowhere
  function zoneNotes(z, k, { zones, own, slots }) {
    const notes = [], grid = data.tileGrid, [ox, oy, oz] = grid.origin, [nx, ny, nz] = grid.dimensions, [sx, sy, sz] = grid.size ?? [TILE, TILE, LEVEL];
    const soldiers = zoneSoldiers(z, { zones, own, slots }), ground = groundOf(z);
    if (soldiers.some(s => s.location[0] < ox || s.location[0] > ox + nx * sx || s.location[1] < oy || s.location[1] > oy + ny * sy
                               || ground < oz - 1 || ground > oz + nz * sz)) notes.push('It is outside the tile grid: its soldiers would stand where there are no tiles.');
    // the floor tiles of the ground's level (the compiler's check_zones: the level of the ground plus 2)
    const level = Math.floor((ground + 2 - oz) / sz);
    const floor = new Set((data.tactical?.floorTiles ?? []).filter(f => floorStays(f.actor) && f.tile[2] === level).map(f => `${f.tile[0]},${f.tile[1]}`));
    const flat = [...roots.values()].filter(r => r.userData.source.added && !r.userData.deleted).map(r => new THREE.Box3().setFromObject(r))
      .filter(b => b.max.y - b.min.y <= 40 && Math.abs(b.max.y - ground) <= 20);
    const tall = [...roots.values()].filter(r => r.userData.source.added && !r.userData.deleted).map(r => new THREE.Box3().setFromObject(r))
      .filter(b => b.max.y - b.min.y > 40 && b.min.y < ground + 150 && b.max.y > ground + 8);
    // on a map grown as it is, the map's own low scenery past its far sides: the Build makes it walkable (F-100; the
    // compiler's scenery_floor), and the map's saved floor tiles stop at its own grid
    const ownDims = ownSize()?.dims, ox1 = ownDims ? ox + ownDims[0] * sx : Infinity, oy1 = ownDims ? oy + ownDims[1] * sy : Infinity;
    const scenery = stage?.grid && !cleared ? [...roots.values()]
      .filter(r => !r.userData.source.added && !r.userData.deleted && r.userData.source.actorClass === 'XComLevelActor')
      .map(r => new THREE.Box3().setFromObject(r))
      .filter(b => b.max.y - b.min.y <= 32 && b.min.y >= oz - sz / 4 && b.max.y <= oz + nz * sz && (b.max.x > ox1 || b.max.z > oy1) && Math.abs(b.max.y - ground) <= 20) : [];
    flat.push(...scenery);
    const bare = [], blocked = [];
    soldiers.forEach((s, n) => {
      const [x, y] = s.location, key = `${Math.floor((x - ox) / sx)},${Math.floor((y - oy) / sy)}`;
      if (!floor.has(key) && !flat.some(b => x >= b.min.x && x <= b.max.x && y >= b.min.z && y <= b.max.z)) bare.push(n + 1);
      if (tall.some(b => x >= b.min.x && x <= b.max.x && y >= b.min.z && y <= b.max.z)) blocked.push(n + 1);
    });
    if (bare.length) notes.push(`Soldier point${bare.length === 1 ? '' : 's'} ${bare.join(', ')} ${bare.length === 1 ? 'is' : 'are'} over no floor: lay floor there.`);
    if (blocked.length) notes.push(`A piece stands on soldier point${blocked.length === 1 ? '' : 's'} ${blocked.join(', ')}.`);
    if (!slots.has(k) && z.lwr === false) notes.push('Neither Long War nor plain EW uses it: it is never played.');
    if (slots.has(k) && slots.size < own.length) notes.push(`Plain EW also lands at ${plural(own.length - slots.size, 'more of the map\'s own landing')}, where the map has ${own.length - slots.size === 1 ? 'it' : 'them'}: mark ${own.length - slots.size === 1 ? 'another zone' : 'more zones'} Plain EW to move ${own.length - slots.size === 1 ? 'it' : 'them'}.`);
    return notes;
  }
  $('landingToggle').checked = landingLayer.visible;
  $('landingToggle').onchange = e => { landingLayer.visible = e.target.checked; remember(LANDING_SHOWN, e.target.checked ? '1' : '0'); if (!e.target.checked) pickZone(null); e.target.blur(); };
  const zoneTurn = (k, dir) => (zones => { zones[k] = { ...zones[k], direction: ZONE_DIRECTIONS[(ZONE_DIRECTIONS.indexOf(zones[k].direction) + dir + 4) % 4] }; return zones; });
  $('landingPlay').onclick = landHere;
  const turnZone = dir => changeZone(pickedZone, (zones, k) => zoneTurn(k, dir)(zones), 'Turned the landing zone');
  // A copy is played by Long War; plain EW keeps the zones it had
  function copyZone() {
    const id = uuid();
    changeZone(pickedZone, (zones, k) => {
      const l = zones[k].location, { lwr, ew, ...rest } = zones[k];
      zones.push({ ...rest, id, location: [l[0] + 192, l[1], l[2]] });
      return zones;
    }, 'Copied the landing zone');
    pickZone(id);
  }
  // Deleting the only zone marked Plain EW marks the first zone left, so plain EW always has one
  function deleteZone() {
    let moved = false;
    changeZone(pickedZone, (zones, k) => {
      const [gone] = zones.splice(k, 1);
      if (gone.ew && zones.length && !zones.some(z => z.ew)) { zones[0] = { ...zones[0], ew: true }; moved = true; }
      return zones;
    }, 'Deleted the landing zone');
    if (moved) flashHint('Deleted the landing zone · zone 1 is now plain EW\'s · Ctrl+Z undoes');
    pickZone(null);
  }
  $('landingCopy').onclick = copyZone;
  $('landingDelete').onclick = deleteZone;
  $('landingKind').onchange = e => changeZone(pickedZone, (zones, k) => { zones[k] = { ...zones[k], kind: e.target.value }; return zones; }, 'Changed the landing zone\'s kind');
  $('landingLwr').onchange = e => changeZone(pickedZone, (zones, k) => {
    const { lwr, ...rest } = zones[k]; zones[k] = e.target.checked ? rest : { ...rest, lwr: false }; return zones;
  }, e.target.checked ? 'Long War lands at the zone' : 'Long War no longer lands at the zone');
  // Plain EW: at least one zone, and no more than the map has landings of its own (the user, 13 November)
  $('landingEw').onchange = e => {
    const zones = explicitZones(), k = zones.findIndex(z => z.id === pickedZone), own = data ? ownLandings(data).length : 0;
    const marked = zones.filter(z => z.ew).length;
    if (k < 0) return;
    if (e.target.checked && marked >= own) {
      e.target.checked = false;
      banner(`This map has ${plural(own, 'landing')} of its own, so plain EW can land at ${own === 1 ? 'one zone' : `${own} zones`}: uncheck Plain EW on ${own === 1 ? 'the other zone' : 'another zone'} first.`, [], { timeout: 8000 });
      return;
    }
    if (!e.target.checked && zones[k].ew && marked <= 1) {
      e.target.checked = true;
      banner('Plain EW needs a landing zone: check Plain EW on another zone first.', [], { timeout: 8000 });
      return;
    }
    changeZone(pickedZone, (list, j) => {
      const { ew, ...rest } = list[j]; list[j] = e.target.checked ? { ...rest, ew: true } : rest;
      // the list keeps saying which zones plain EW plays when the last mark of an old list's order goes
      if (!list.some(z => z.ew)) list[j] = { ...rest, ew: true };
      return list;
    }, e.target.checked ? 'Plain EW lands at the zone' : 'Plain EW no longer lands at the zone');
  };
  // Add a landing zone (the piece list's Landing zones kind): the zones are shown, and the next click on the view places
  // one on the tile under it, at the ground grid's height
  function startZonePlacing() {
    setZonesShown(true);
    if (!landingLayer.visible) { landingLayer.visible = true; $('landingToggle').checked = true; remember(LANDING_SHOWN, '1'); refreshLandingZones(); }
    setZonePlacing(true); renderer.domElement.style.cursor = 'crosshair';
    flashHint('Click the tile the new landing zone is to stand on · Esc cancels');
  }
  function stopZonePlacing() {
    if (!zonePlacing) return;
    setZonePlacing(false); renderer.domElement.style.cursor = ''; pieces.setChosen?.(null); restingHint();
  }
  function placeZone(clientX, clientY) {
    setZonePlacing(false); renderer.domElement.style.cursor = ''; pieces.setChosen?.(null);
    const ground = groundHeight(), at = rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -ground), new THREE.Vector3());
    if (!at) return;
    const [ox, oy] = data.tileGrid.origin, first = zonesNow()[0];
    // a zone's StartLoc sits a unit off a tile's corner, as LWR's lines do (Bar's first: 719, -1681)
    const x = ox + Math.round((at.x - ox) / TILE) * TILE - 1, y = oy + Math.round((at.z - oy) / TILE) * TILE - 1, id = uuid();
    const zones = explicitZones(), ew = !zones.some(z => z.ew) && ownLandings(data).length > 0;
    setZones([...zones, { id, location: [x, y, ground + 64], direction: 'north', kind: first?.kind === 'inside' ? 'inside' : 'normal', ...(ew ? { ew: true } : {}) }], 'Added a landing zone');
    pickZone(id);
  }
  // After the cleared mark changes: the menu, the streamed patches' pieces and the view-only lights (a cleared map
  // draws none: the Build takes them out), the ground grid
  function clearedChanged() {
    if (!data) return;
    $('projectSize').hidden = !projectsAvailable();
    $('projectClear').hidden = !projectsAvailable();
    $('projectMissions').hidden = !projectsAvailable();
    $('projectPicture').hidden = !projectsAvailable();
    setMergedBuildings(null);
    refreshMissionPicker();     // a project's missions, or none
    refreshLightVisibility();
    setEffectsDirty(true);
    if (!builderMode) cutaway();
    refreshGroundGrid(); refreshLandingZones();
  }

  return { cancelZoneGizmo, carried, clearedChanged, copyZone, deleteZone, explicitZones, movedLandingActors, pickZone,
           placeZone, placeZoneGizmo, refreshLandingZones, setZoneGizmoMode, setZones, setZonesShown, startZonePlacing,
           stopZonePlacing, turnZone, zoneEntries, zoneGizmo, zoneGizmoHelper, zoneGizmoWanted, zoneHit, zoneProxy,
           zoneSoldiers, zoneState };
}
