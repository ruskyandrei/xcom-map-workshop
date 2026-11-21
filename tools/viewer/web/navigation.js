// Navigation (refactor stage P9): how the user drives the view and the editor. Here:
// - the camera: Frame and the framing of a piece or the map (frame), the arrow keys and WASD moving it and Q and E
//   turning it (panCamera, which the draw loop runs each frame), the look-drag along the view, the wheel's zoom to the
//   point under the cursor, and View options' camera speeds and "Keys move along the view";
// - the gizmo's buttons: Move, Rotate, Select and the axes, the pivot (remembered), and snap (setSnapMode and its
//   button; SNAPS and RECIPE_NOTE, which the selection's grid chip says too), kept up after each edit by the edit hub's
//   `tools` refresh;
// - the editor's keys (index.html's help panel lists them), each calling the area that owns what it does.
//
// createNavigation takes what it needs of app.js as one argument object, when app.js makes it, where the camera's keys
// were (after the factories whose functions the keys call); its own state is inside it (the keys held, the speeds, a
// look-drag, the wheel's anchor, the near plane the last framing set). The top level only declares.
import * as THREE from 'three';
import { QUARTER } from './constants.js';
import { onHub, runHub } from './edit_hub.js';
import { allRoots, assigning, breaking, builder, builderMode, coverDrag, data, effectsOn, gridDrag, gridTool, hintTimer,
         levelSnap, lightDrag, lightRadius, lightRoots, lightsOn, lookPicking, ownPicked, ownSet, pickBox, pickDrag,
         pickedEffect, pickedSpawn, pickedZone, pickTool, pieces, placing, rockPoint, roots, selected, setAssigning,
         setGhostDirty, setLightRadius, setOwnPickedValue, setSnapModeValue, snapMode, soloOn, spawnPlacing, spawnsOn,
         spawnZonePick, volumeDrag, volumesOn, volumeTool, wallDrag, wallDrawing, zonePlacing,
         zonesOn } from './editor_state.js';
import { recall, remember } from './storage.js';
import { focusBounds, visibleBounds } from './view_layout.js';
import { modalOpen } from './modal.js';

// (snapMode, the snap setting, 'off', 'fine' or 'tile': editor_state.js)
// Snap cycles off, fine steps, whole tiles. Under tile snap a selection with a ladder, door, car, van or fracturing piece
// takes the recipe snap (gizmo.js recipeMove, poserule.js): the Build maps what the map saves per tile exactly only for
// such a pose. Snap off or fine, such a piece moves as any piece does, and off the grid the Build warns (refreshGrid).
const SNAPS = {
  off: ['fine', '', 'Snap off. Click for steps of 24 units and 15°'],
  fine: ['tile', '24', 'Snap: steps of 24 units from where the piece stood, and 15°. Click for whole tiles'],
  tile: ['off', '96', 'Snap: whole tiles (96 across, 64 up) from where the piece stood, and 90° turns. Click to turn snap off'],
};
export const RECIPE_NOTE = 'Recipe snap: under tile snap, ladders, doors, cars, vans and fracturing pieces (walls, storey floors) move by whole tiles (96 across) and storeys (64 up) and '
  + 'turn by quarter turns about the vertical, from where the original stands, so the Build maps what the map '
  + 'saves for their tiles exactly. Click to turn snap off: they then move freely';

export function createNavigation({ $, applyLighting, builderRecords, camera, cancelMissionGizmo, cancelPointDrag,
                                   cancelZoneGizmo, content, controls, copySelection, copySpawn, copyZone,
                                   deleteSelection, deleteSpawn, deleteWallOpening, deleteZone, dragHint, editBaseSpawn,
                                   editSpawnCopy, endCoverDrag, endGridDrag, endLightDrag, endPickDrag, endVolumeDrag,
                                   endWallDrag, flashHint, frameEffect, gizmo, groupShortcut, isMadeSlab, isMadeWall,
                                   lightPanel, madeRoot, mapBreakable, missionGizmo, openBuild, paste, pick, pickEffect,
                                   pickZone, playArea, projectsAvailable, rayAt, refreshVolumes, releaseRockPoint,
                                   renderer, restingHint, saveProject, select, setEffectsShown, setGridTool,
                                   setLevelSnap, setLightsShown, setNormalView, setOwnPicked, setPickedSpawn,
                                   setPickTool, setPlayArea, setSolo, setSpawnsShown, setVolumesShown, setVolumeTool,
                                   setZoneGizmoMode, setZonesShown, showFileDialog, showMapBrowser, showPieces, showPop,
                                   spawnDeleted, spawnEntry, spawnMovable, startBreak, startLookPick, stopBreak,
                                   stopLookPick, stopPickBox, stopPlacing, stopSpawnPlacing, stopWallDrawing,
                                   stopZonePlacing, sun, takePickBox, TURNED_KINDS, turnZone, undoStep, volumePanel,
                                   wallGhost, wallHint, zoneGizmo }) {
  onHub('edit', 'tools', () => {
    for (const [id, m] of [['editMove','translate'],['editRotate','rotate'],['editOff','off']]) $(id).classList.toggle('on', gizmo.mode === m);
    snapButton();
    const world = gizmo.space === 'world';
    $('editSpace').querySelector('use').setAttribute('href', world ? '#i-world' : '#i-local');
    $('editSpace').title = world ? "World axes: click for the piece's own axes (X)" : "The piece's own axes: click for world axes (X)";
    const centre = gizmo.pivot === 'centre';
    $('editPivot').querySelector('use').setAttribute('href', centre ? '#i-pivot-centre' : '#i-pivot-origin');
    $('editPivot').classList.toggle('on', centre);
    $('editPivot').setAttribute('aria-pressed', String(centre));
    $('editPivot').title = centre
      ? "Pivot: the selection's centre (with tile snap, the nearest tile centre or corner). Click to move and turn about each piece's own origin (C)"
      : "Pivot: each piece's own origin. Click to move and turn about the selection's centre (C)";
    $('selected').disabled = !selected;
  });
  function snapButton() {
    const button = $('editSnap'), recipe = gizmo.recipe;
    button.classList.toggle('on', snapMode !== 'off'); button.setAttribute('aria-pressed', snapMode !== 'off');
    button.title = recipe ? `${RECIPE_NOTE}.` : SNAPS[snapMode][2];
    $('snapBadge').textContent = recipe ? 'R' : SNAPS[snapMode][1];
  }
  let frameNear = 2;    // the near plane the last framing set (the wheel zoom brings it in close up)
  function frame(root = content) {
    const interior=$('scenery').value==='interior';
    const box = (root === 'playable' || root === content && interior) && data.playableBounds
      ? focusBounds(data)
      : root === content ? visibleBounds(roots,data?.playableBounds)
      : root?.userData?.light ? new THREE.Box3().setFromCenterAndSize(new THREE.Vector3().setFromMatrixPosition(root.matrix),
                                                                      new THREE.Vector3(1, 1, 1).multiplyScalar(Math.min(800, Math.max(200, root.userData.values.radius ?? 400))))
      : new THREE.Box3().setFromObject(root);
    if (builderMode && root === content && !builder.loading) {
      const b = builderRecords().box;
      if (!b.isEmpty()) box.union(b);
      if (box.isEmpty() || box.getSize(new THREE.Vector3()).length() < 1) box.set(new THREE.Vector3(-576, 0, -576), new THREE.Vector3(576, 192, 576));
    }
    if(interior && root!==content && root!=='playable')box.intersect(focusBounds(data));
    if(root!==content && root!=='playable')box.max.y=Math.min(box.max.y,root.userData.cutHeight ?? Infinity);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = size.length() * 0.5;
    const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * Math.max(1, 1 / camera.aspect) * 1.1;
    controls.target.copy(center);
    camera.position.copy(center).add((interior ? new THREE.Vector3(0.55,1.5,1.1) : new THREE.Vector3(1,1.15,1.35)).normalize().multiplyScalar(distance));
    camera.near = frameNear = Math.max(0.2, distance / 5000); camera.far = Math.max(100000, distance * 8);
    camera.updateProjectionMatrix(); controls.update();
    if(root===content || root==='playable') {
      setLightRadius(Math.max(700,size.length()*0.55));sun.target.position.copy(center);
      Object.assign(sun.shadow.camera,{left:-lightRadius,right:lightRadius,top:lightRadius,bottom:-lightRadius,near:1,far:lightRadius*6});
      sun.shadow.camera.updateProjectionMatrix();applyLighting();
    }
  }
  $('editMove').onclick = () => gizmo.setMode('translate');
  $('editRotate').onclick = () => gizmo.setMode('rotate');
  $('editOff').onclick = () => gizmo.setMode('off');
  $('editSpace').onclick = () => gizmo.toggleSpace();
  // The pivot (C): each piece's own origin, or the selection's centre (Discord feedback S4); remembered on this computer.
  const PIVOT = 'workshop.pivot';
  function togglePivot() {
    gizmo.setPivot(gizmo.pivot === 'centre' ? 'origin' : 'centre');
    remember(PIVOT, gizmo.pivot);
  }
  if (recall(PIVOT) === 'centre') gizmo.setPivot('centre', true);    // (the button shows it at the first editChanged)
  $('editPivot').onclick = togglePivot;
  function setSnapMode(next) {
    setSnapModeValue(next); gizmo.setSnap(next); setGhostDirty(true);
    snapButton(); runHub('snap', roots.get(selected));
  }
  $('editSnap').onclick = () => setSnapMode(SNAPS[snapMode][0]);
  // The arrow keys and WASD move the camera while held. By default they pan across the map: Up/W and Down/S along the
  // view's direction laid flat, Left/A and Right/D across it, so the camera keeps its height and angle. With View
  // options' "Keys move along the view" ticked, Up/W and Down/S move forward and back the way the camera faces (climbing
  // or descending with its tilt), Left/A and Right/D sideways across it. Either way the orbit target moves with the
  // camera. The speed is the same on every map and at every zoom: PAN_SPEED units a second, well under what the distance
  // used to give after Interior's framing on most maps (about 9,000 units away); Shift moves three times as fast.
  // Q and E turn the view left and right while held, about the vertical, keeping the camera's tilt: by default the
  // camera circles the point it looks at (as XCOM's own camera turns), and with "Keys move along the view" it turns where
  // it stands, the point it looks at swinging round it. TURN_SPEED a second; Shift three times as fast.
  const PAN_KEYS = { arrowup: 'forward', w: 'forward', arrowdown: 'back', s: 'back', arrowleft: 'left', a: 'left', arrowright: 'right', d: 'right' };
  const TURN_KEYS = { q: 1, e: -1 };    // a positive turn about +Y swings forward towards the screen's left
  const TURN_SPEED = THREE.MathUtils.degToRad(60);
  const PAN_SPEED = 5000;    // about 52 tiles a second (7,200 at first: the user found it a little fast)
  const FLY_KEYS = 'workshop.flyKeys';
  const panKeys = new Set();
  let panFast = false, flyKeys = recall(FLY_KEYS) === '1';
  // View options' camera speeds (Discord feedback S2, S3): each a factor on its default, remembered on this computer.
  // Move speed scales PAN_SPEED, key turn speed TURN_SPEED, and drag turn speed OrbitControls' orbit and the look-drag
  // along the view (LOOK_PER_SCREEN). A double-click on a slider puts it back to 1; letting go of one gives the keys back
  // to the camera.
  const CAMERA_SPEEDS = { moveSpeed: 'workshop.moveSpeed', turnSpeed: 'workshop.turnSpeed', dragSpeed: 'workshop.dragSpeed' };
  const cameraSpeed = { moveSpeed: 1, turnSpeed: 1, dragSpeed: 1 };
  for (const [id, key] of Object.entries(CAMERA_SPEEDS)) {
    const input = $(id), saved = Number(recall(key));
    if (saved > 0) input.value = String(saved);    // (a range input keeps a saved value inside its own limits)
    const show = () => {
      cameraSpeed[id] = Number(input.value);
      $(`${id}Value`).textContent = `×${cameraSpeed[id].toFixed(2)}`;
      controls.rotateSpeed = cameraSpeed.dragSpeed;
    };
    show();
    input.oninput = () => { show(); remember(key, input.value); };
    input.onchange = () => input.blur();
    input.ondblclick = () => { input.value = '1'; input.oninput(); input.blur(); };
  }
  function turnCamera(dt) {
    const turn = [...panKeys].reduce((sum, k) => sum + (TURN_KEYS[k] ?? 0), 0);
    if (!turn) return;
    const angle = turn * TURN_SPEED * cameraSpeed.turnSpeed * (panFast ? 3 : 1) * dt, up = new THREE.Vector3(0, 1, 0);
    if (flyKeys) controls.target.sub(camera.position).applyAxisAngle(up, angle).add(camera.position);
    else camera.position.sub(controls.target).applyAxisAngle(up, angle).add(controls.target);
    camera.lookAt(controls.target);    // so this frame's move goes by the turned view
  }
  function panCamera(dt) {
    if (!panKeys.size) return;
    turnCamera(dt);
    const forward = new THREE.Vector3().subVectors(controls.target, camera.position);
    if (!flyKeys) {
      forward.setY(0);
      // Looking straight down, forward is the top of the screen.
      if (forward.lengthSq() < 1e-6) forward.set(0, 1, 0).applyQuaternion(camera.quaternion).setY(0);
    }
    if (forward.lengthSq() < 1e-6) return;
    forward.normalize();
    // Sideways is the screen's right, level with the ground (also looking straight down, when forward x up is nothing).
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion).setY(0);
    if (right.lengthSq() < 1e-6) return;
    right.normalize();
    const held = new Set([...panKeys].map(k => PAN_KEYS[k])), move = new THREE.Vector3();
    if (held.has('forward')) move.add(forward);
    if (held.has('back')) move.sub(forward);
    if (held.has('right')) move.add(right);
    if (held.has('left')) move.sub(right);
    if (move.lengthSq() < 1e-6) return;
    const speed = PAN_SPEED * cameraSpeed.moveSpeed * (panFast ? 3 : 1);
    move.normalize().multiplyScalar(speed * dt);
    camera.position.add(move); controls.target.add(move);
  }
  // Along the view, a left-drag looks round from where the camera stands instead of orbiting: the camera keeps its place
  // and the point it looks at swings round it at the same distance, dragging right looking right and up looking up
  // (LOOK_PER_SCREEN for a drag the view's height; the tilt stops just short of straight up or down). OrbitControls'
  // own rotate is off then; its pans (right-drag, or Shift, Ctrl or Cmd with the left button) and the wheel stay. A press
  // the gizmo or a light's handle takes is left to them, and a press that barely moves is still a click.
  const LOOK_PER_SCREEN = Math.PI / 2;
  let look = null;    // { id, x, y } while a look-drag is held
  function lookBy(yaw, pitch) {
    const aim = new THREE.Spherical().setFromVector3(new THREE.Vector3().subVectors(controls.target, camera.position));
    aim.theta += yaw;
    aim.phi = THREE.MathUtils.clamp(aim.phi - pitch, 0.01, Math.PI - 0.01);
    controls.target.copy(camera.position).add(new THREE.Vector3().setFromSpherical(aim));
    camera.lookAt(controls.target);
  }
  renderer.domElement.addEventListener('pointerdown', e => {
    if (!flyKeys || e.button !== 0 || e.ctrlKey || e.shiftKey || e.metaKey || !controls.enabled || gizmo.busy()) return;
    look = { id: e.pointerId, x: e.clientX, y: e.clientY };
    zoomAnchor = null;
  });
  renderer.domElement.addEventListener('pointermove', e => {
    if (!look || e.pointerId !== look.id) return;
    if (!controls.enabled) { look = null; return; }    // the gizmo took the drag after all
    const k = LOOK_PER_SCREEN * cameraSpeed.dragSpeed / Math.max(1, renderer.domElement.clientHeight);
    lookBy(-(e.clientX - look.x) * k, -(e.clientY - look.y) * k);
    look.x = e.clientX; look.y = e.clientY;
  });
  for (const type of ['pointerup', 'pointercancel']) renderer.domElement.addEventListener(type, e => { if (look?.id === e.pointerId) look = null; });
  function setFlyKeys(on) {
    flyKeys = Boolean(on); remember(FLY_KEYS, flyKeys ? '1' : '0');
    controls.enableRotate = !flyKeys; look = null;
  }
  $('flyKeys').checked = flyKeys;
  controls.enableRotate = !flyKeys;
  $('flyKeys').onchange = e => { setFlyKeys(e.target.checked); e.target.blur(); };
  // The wheel zooms towards what is under the cursor. OrbitControls' own zoom scaled the distance to the orbit target, so
  // each notch moved a share of a shrinking distance and never passed the target: on a big map, zoomed far in towards
  // anything but the target, scrolling all but stopped. Here a notch moves the camera ZOOM_STEP of the way to the surface
  // under the cursor (else the ground level with the target, else a point on the cursor's ray as far as the target), so
  // that point stays under the cursor, and the orbit target moves onto the view's centre line at that point's depth:
  // orbiting, panning and the next notch work about what is looked at. Zooming out moves away from it the same way.
  // A burst of wheel events with the cursor still keeps the first one's point (a raycast once per burst).
  const ZOOM_STEP = 0.18, ZOOM_BURST = 250;
  let zoomAnchor = null;   // { point, x, y, time }
  function zoomPoint(clientX, clientY) {
    const now = performance.now();
    if (zoomAnchor && now - zoomAnchor.time < ZOOM_BURST && Math.hypot(clientX - zoomAnchor.x, clientY - zoomAnchor.y) < 4) {
      zoomAnchor.time = now;
      return zoomAnchor.point;
    }
    const ray = rayAt(clientX, clientY).ray, reach = camera.position.distanceTo(controls.target);
    let point = data ? pick(clientX, clientY)?.point?.clone() : null;
    if (!point) {
      const ground = ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -controls.target.y), new THREE.Vector3());
      point = ground && ground.distanceTo(camera.position) < reach * 4 ? ground : ray.at(Math.max(reach, 1), new THREE.Vector3());
    }
    zoomAnchor = { point, x: clientX, y: clientY, time: now };
    return point;
  }
  function wheelZoom(e) {
    e.preventDefault();
    if (gizmo.controls.dragging) return;
    // pixels, lines or pages to notches (a mouse notch is about 100 pixels; a touchpad sends many small ones)
    const pixels = e.deltaY * (e.deltaMode === 1 ? 33 : e.deltaMode === 2 ? 800 : 1);
    const notches = THREE.MathUtils.clamp(pixels / 100, -3, 3);
    if (!notches) return;
    const point = zoomPoint(e.clientX, e.clientY);
    const forward = new THREE.Vector3().subVectors(controls.target, camera.position).normalize();
    // scrolled up (deltaY below 0) zooms in, as OrbitControls did: under 1 nears the point, over 1 backs away
    const factor = Math.pow(1 - ZOOM_STEP, -notches);
    const next = point.clone().addScaledVector(new THREE.Vector3().subVectors(camera.position, point), factor);
    if (next.distanceTo(point) > camera.far * 0.5) return;    // as far out as the view reaches
    camera.position.copy(next);
    const depth = Math.max(1, new THREE.Vector3().subVectors(point, camera.position).dot(forward));
    controls.target.copy(camera.position).addScaledVector(forward, depth);
    // close in, the near plane comes in too, so the surface isn't cut away; back out it returns to the framing's
    const near = THREE.MathUtils.clamp(depth / 50, 0.2, frameNear);
    if (Math.abs(near - camera.near) > 1e-3) { camera.near = near; camera.updateProjectionMatrix(); }
    controls.update();
  }
  controls.enableZoom = false;
  controls.addEventListener('start', () => { zoomAnchor = null; });    // orbited or panned: a new burst picks again
  renderer.domElement.addEventListener('wheel', wheelZoom, { passive: false });
  document.addEventListener('keyup', e => {
    panKeys.delete(e.key.toLowerCase());
    panFast = e.shiftKey;
  });
  // Shift pressed while a move or turn key is already held speeds the camera up at once (it used to wait for the next key
  // press: Discord feedback B1)
  document.addEventListener('keydown', e => { if (e.key === 'Shift') panFast = true; });
  window.addEventListener('blur', () => { panKeys.clear(); panFast = false; });
  // The editor's keys (index.html's help panel lists them for users): V select, T box select, G move, R rotate (while
  // placing, R and Shift+R turn the piece), P the Add panel, M the map browser, X world or local axes, C the pivot
  // (origin or centre), F frame, L level snap, O solo the selected lights, B Break on a picked wall, floor or roof that
  // breaks (else the play area), I the eyedropper while drawing; Shift+N, B, L, Z, U and X the six views (in the
  // Buildings view N draws a new box); arrow keys and WASD move the camera and Q and E turn it; Escape cancels a drag,
  // stops placing, drawing or a pick, closes a menu or, when there is none of those, clears the selection; Ctrl+Z /
  // Ctrl+Y (or Ctrl+Shift+Z) undo and redo, Ctrl+C / X / V copy, cut and paste, Ctrl+G groups the selection and
  // Ctrl+Shift+G ungroups the selected group, Delete deletes; a picked landing zone or spawn point takes Delete, Ctrl+D
  // (a copy) and [ ] (a quarter turn); Ctrl+S saves, Ctrl+B builds and Ctrl+O loads a project. Typing in a field never
  // triggers them (Ctrl+S, B and O aside), and Ctrl+C with nothing selected is the browser's own copy. An open dialog
  // (modalOpen) keeps the keys.
  document.addEventListener('keydown', e => {
    const key = e.key.toLowerCase();
    if (modalOpen()) { if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'f', 'b'].includes(key)) e.preventDefault(); return; }
    if ((e.ctrlKey || e.metaKey) && key === 's') { e.preventDefault(); if (!e.repeat) saveProject(); return; }
    if ((e.ctrlKey || e.metaKey) && key === 'o') { e.preventDefault(); if (!e.repeat) showFileDialog('load'); return; }
    if ((e.ctrlKey || e.metaKey) && key === 'b') { e.preventDefault(); if (!e.repeat) openBuild(); return; }
    if (e.target.closest?.('input, select, textarea, [contenteditable]')) return;
    // while a light's handle is dragged, Escape puts it back and other keys wait
    if (lightDrag) { if (key === 'escape') endLightDrag(false); e.preventDefault(); return; }
    if (volumeDrag) { if (key === 'escape') endVolumeDrag(false); e.preventDefault(); return; }
    if (coverDrag) { if (key === 'escape') endCoverDrag(false); e.preventDefault(); return; }
    if (wallDrag) { if (key === 'escape') endWallDrag(false); e.preventDefault(); return; }
    if (rockPoint && key === 'escape') { if (!cancelPointDrag()) releaseRockPoint(); e.preventDefault(); return; }
    if (wallDrawing && key === 'escape') {
      if (wallDrawing.start) { try { renderer.domElement.releasePointerCapture(wallDrawing.pointerId); } catch { /* released */ }
        wallDrawing.start = null; wallDrawing.pointerId = null; wallGhost.visible = false; wallHint(); }
      else stopWallDrawing();
      e.preventDefault(); return;
    }
    if (pickDrag) { if (key === 'escape') endPickDrag(false); e.preventDefault(); return; }
    if (zoneGizmo.dragging) { if (key === 'escape') cancelZoneGizmo(); e.preventDefault(); return; }
    if (missionGizmo.dragging) { if (key === 'escape') cancelMissionGizmo(); e.preventDefault(); return; }
    if (gridDrag) { if (key === 'escape') endGridDrag(false); e.preventDefault(); return; }
    if (gridTool && key === 'escape' && !pickedZone && !selected && !placing) { setGridTool(false); e.preventDefault(); return; }
    if (zonePlacing && key === 'escape') { stopZonePlacing(); e.preventDefault(); return; }
    if (spawnPlacing && key === 'escape') { stopSpawnPlacing(); e.preventDefault(); return; }
    if (lookPicking && key === 'escape') { stopLookPick(); e.preventDefault(); return; }
    if (breaking && key === 'escape') { stopBreak(); e.preventDefault(); return; }
    // B: Break on the picked made wall, floor or roof, or off again (B5)
    if (key === 'b' && !e.ctrlKey && !e.metaKey && !e.altKey && !e.repeat
        && (breaking || isMadeWall(madeRoot(selected)?.userData.source) || isMadeSlab(madeRoot(selected)?.userData.source)
            || mapBreakable(roots.get(selected)?.userData.source))) {
      if (breaking) stopBreak(); else startBreak();
      e.preventDefault(); return;
    }
    // I: the eyedropper, while a wall, slab or ground tool draws (M4c; the look picker's own I is its panel's)
    if (key === 'i' && !e.ctrlKey && !e.metaKey && !e.altKey && wallDrawing) {
      startLookPick(wallDrawing.ground ? 'ground' : wallDrawing.slab ? 'slab' : 'wall');
      e.preventDefault(); return;
    }
    // a picked landing zone: Delete, Ctrl+D copies, G and R its gizmo's arrows or ring, [ and ] turn it, Escape lets it
    // go (Ctrl+Z undoes as for anything)
    if (pickedZone && !selected && !e.altKey) {
      if (key === 'delete' && !e.ctrlKey && !e.metaKey) { deleteZone(); e.preventDefault(); return; }
      if ((e.ctrlKey || e.metaKey) && key === 'd') { copyZone(); e.preventDefault(); return; }
      if (key === '[' || key === ']') { turnZone(key === '[' ? -1 : 1); e.preventDefault(); return; }
      if ((key === 'g' || key === 'r') && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
        setZoneGizmoMode(key === 'r' ? 'rotate' : 'translate'); e.preventDefault(); return;
      }
      if (key === 'escape') { pickZone(null); e.preventDefault(); return; }
    }
    // the Effects view: Escape lets the picked marker go (a drag or a placing first gives way)
    if (effectsOn && pickedEffect && key === 'escape' && !e.ctrlKey && !e.metaKey && !e.altKey && !gizmo.busy() && !placing) { pickEffect(null); e.preventDefault(); return; }
    // a picked spawn marker (or a zone the Spawns view describes): Escape lets it go
    if ((pickedSpawn || spawnZonePick) && !selected && key === 'escape' && !e.ctrlKey && !e.metaKey && !e.altKey && !gizmo.busy() && !placing) { setPickedSpawn(null); e.preventDefault(); return; }
    // a picked base pod, Meld point or drop-in point, or a copy (SP6, SP7), as a landing zone: Delete, Ctrl+D copies,
    // [ and ] turn a drop-in point a quarter
    {
      const se = pickedSpawn && !selected && !e.altKey && !placing && !gizmo.busy() ? spawnEntry(pickedSpawn) : null;
      if (se && ['base', 'copy'].includes(se.layer) && projectsAvailable() && (spawnMovable(se) || spawnDeleted(se))) {
        if (key === 'delete' && !e.ctrlKey && !e.metaKey) { deleteSpawn(pickedSpawn); e.preventDefault(); return; }
        if ((e.ctrlKey || e.metaKey) && key === 'd') { copySpawn(pickedSpawn); e.preventDefault(); return; }
        // (a drop-in point only: a pod's facing aims nothing, the user, 18 November 2026)
        if ((key === '[' || key === ']') && !e.ctrlKey && !e.metaKey && TURNED_KINDS.includes(se.record.kind) && spawnMovable(se)) {
          const turn = key === '[' ? -QUARTER : QUARTER, hint = `Turned a quarter ${turn > 0 ? 'right' : 'left'}`;
          if (se.layer === 'copy') editSpawnCopy(se.record.actor, { turn }, hint); else editBaseSpawn(se.record.actor, { turn }, hint);
          e.preventDefault(); return;
        }
      }
    }
    // the select box: Enter takes what is inside (Shift+Enter adds it to the selection), Escape puts the box away
    if ((pickTool || pickBox) && !e.ctrlKey && !e.metaKey && !e.altKey && !placing) {
      if (key === 'escape' && !gizmo.controls.dragging) { stopPickBox(); e.preventDefault(); return; }
      if (key === 'enter' && pickBox) { takePickBox(e.shiftKey); e.preventDefault(); return; }
    }
    if (volumesOn && !e.ctrlKey && !e.metaKey && !e.altKey && !placing) {
      if (key === 'escape' && volumeTool) { setVolumeTool(null); e.preventDefault(); return; }
      if (key === 'escape' && ownPicked && !selected) { setOwnPicked(null); e.preventDefault(); return; }
      if (key === 'n' && !e.shiftKey) { setVolumeTool(volumeTool === 'new' ? null : 'new'); e.preventDefault(); return; }
      if (key === 'r') { flashHint('A building\'s box is not turned'); e.preventDefault(); return; }
    }
    if (e.ctrlKey || e.metaKey) {
      if (e.altKey) return;
      if (key === 'z' && !e.shiftKey) undoStep();
      else if (key === 'y' || (key === 'z' && e.shiftKey)) undoStep(true);
      else if ((key === 'c' || key === 'x') && selected) copySelection(key === 'x');
      else if (key === 'v') paste();
      else if (key === 'g') { if (!e.repeat && !volumesOn && !lightsOn) groupShortcut(e.shiftKey); }
      else return;
    } else if (key === 'delete') { if (!selected && !ownSet.size) return; if (!deleteWallOpening()) deleteSelection(); }
    else if (key === 'escape') {
      if (assigning) { setAssigning(null); lightPanel(); flashHint('Assigning cancelled'); }
      else if (gizmo.cancel()) dragHint(false);
      else if (placing) stopPlacing();
      else if (document.querySelector('.pop:not([hidden])')) showPop(null);
      else if (selected) select(null);
      else if (ownSet.size || (ownPicked && !volumesOn)) { ownSet.clear(); setOwnPickedValue(null); refreshVolumes(); volumePanel(); }
      else return;
    }
    else if (e.altKey) return;
    else if (PAN_KEYS[key] || TURN_KEYS[key]) { panKeys.add(key); panFast = e.shiftKey; }
    else if (key === 'p') { if (data) showPieces(!pieces.open); }
    else if (key === 'm') showMapBrowser();
    else if (key === 'r') {
      // While placing, R turns the piece a quarter turn about its pivot (Shift+R the other way); otherwise it is Rotate.
      if (!placing) { gizmo.setMode('rotate'); e.preventDefault(); return; }
      placing.turns = (placing.turns + (e.shiftKey ? 3 : 1)) % 4; setGhostDirty(true);
      clearTimeout(hintTimer); restingHint();
    }
    else if (key === 'v') gizmo.setMode('off');
    else if (key === 't') { if (data && !e.repeat) setPickTool(!(pickTool || pickBox)); }
    else if (key === 'g') gizmo.setMode('translate');
    else if (key === 'x') { if (e.shiftKey) { if (data) setEffectsShown(!effectsOn); } else gizmo.toggleSpace(); }
    else if (key === 'c') togglePivot();
    else if (key === 'b') {
      if (e.shiftKey) { if (data) setVolumesShown(!volumesOn); }
      else { if (!playArea.children.length) return; setPlayArea(!playArea.visible); }
    }
    else if (key === 'l') { if (e.shiftKey) { if (data) setLightsShown(!lightsOn); } else setLevelSnap(!levelSnap); }
    else if (key === 'n') { if (!e.shiftKey || !data) return; setNormalView(); }
    else if (key === 'z') { if (!e.shiftKey || !data) return; setZonesShown(!zonesOn); }
    else if (key === 'u') { if (!e.shiftKey || !data) return; setSpawnsShown(!spawnsOn); }
    else if (key === 'o') { if (!lightRoots.has(selected)) return; setSolo(!soloOn); }
    else if (key === 'f') { if (!(effectsOn && frameEffect())) frame(selected ? allRoots.get(selected) : undefined); }
    else return;
    e.preventDefault();
  });

  return { frame, panCamera, setSnapMode };
}
