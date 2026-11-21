// The play area, the map's size as the project sets it and the rail's Map grid (refactor stage P8). Here:
// - the play area: the map's level volume, the box the game's tile grid fills, drawn as lines and faint walls, and View
//   options' Play area (drawPlayArea, setPlayArea);
// - the map's size as the project sets it (Map menu, Map grid; prefab plan 5.11): the map's own size kept (ownSize),
//   the grid a stage asks for (stageDims), the grid drawn at a size (showGrid) and a size set, its new area drawn as a
//   faint sheet (setStage);
// - the rail's Map grid (the user, 13 November): what the grid can be (gridRule), the cursor's floors on it
//   (storeysNow), its handles (placeGridHandles, gridHit, gridHandleAt), its panel (gridPanel), the tool (setGridTool),
//   a new size as one undo step (commitStage) and a handle's drag (startGridDrag, moveGridDrag, endGridDrag), with the
//   panel's buttons.
//
// The grid's origin (gridOrigin) and the corner the game counts its tiles from (tileCorner) are plain exports at the
// top, before the factory: they read only the scene (editor_state.js's data).
//
// createMapGrid takes what it needs of app.js as one argument object, when app.js makes it: the camera's controls,
// the renderer and the scene, the gizmo, picking and the handles' line (alongLine), a piece's box, the made slabs, the
// Clear map's notes and the ground grid, the project's change, the popups and the hints. Its own state is inside it
// (whether the tool showed the play area); the map's own size, the tool and a drag (ownGrid, gridTool, gridDrag: app.js's
// scene start, pointer handlers, keys and test hooks read or set them) are editor_state.js's. app.js's pointer handlers
// call the drags; its View options' Play area calls setPlayArea.
import * as THREE from 'three';
import { LEVEL, TILE } from './constants.js';
import { activeMapId, builderMode, cleared, data, gridDrag, gridTool, ownGrid, roots, setGridDrag, setGridToolValue,
         setOwnGrid, setStageValue, stage } from './editor_state.js';
import { cursorStoreys } from './floors.js';
import { STAGE_MAPS, stageMax, tidyStage, validStage } from './project.js';
import { recall, remember } from './storage.js';

export const gridOrigin = () => data?.tileGrid?.origin?.slice(0, 2) ?? null;
// The corner the game counts its tiles from (export 26's tileGrid.tiles, its world data's WorldBounds; for an older
// export a unit under the origin, as on every installed map), [x, y, z]: a point's tile (a ladder's ends, a mission
// object's, a soldier's spot, the floor under a piece placed) is counted from it, as compiler.py tile_corner has it.
// Placing (snap, the lines, the grid rule) keeps the origin, the level volume's corner, where the maps' pieces stand.
export const tileCorner = () => data?.tileGrid?.tiles ?? data?.tileGrid?.origin?.map(v => v - 1) ?? null;

export function createMapGrid({ $, alongLine, boxOf, controls, flashHint, gizmo, groundWords, isMadeSlab,
                                projectChanged, rayAt, refreshGroundGrid, renderer, showPop, sizeNotes, world }) {
  // The play area: the map's level volume (playableBounds), the box the game's tile grid fills, which units can't leave.
  // Drawn light: its edges as lines and its four sides as faint see-through walls, from the lowest tile level up to the
  // top of the highest, never picked and never cut by Interior or the floor cutaway. View options' Play area, or B,
  // turns it off and on (remembered in the browser).
  const PLAY_AREA_SHOWN = 'workshop.playArea', PLAY_AREA_COLOR = 0xffb347;
  const playArea = new THREE.Group(); world.add(playArea);
  playArea.visible = recall(PLAY_AREA_SHOWN) !== '0';
  const playAreaMaterials = {
    line: new THREE.LineBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.75, depthWrite: false }),
    // the same edges faintly through whatever stands in front, so Full's tall buildings don't hide it
    through: new THREE.LineBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.22, depthWrite: false, depthTest: false }),
    wall: new THREE.MeshBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }),
    none: new THREE.MeshBasicMaterial({ visible: false }),
  };
  function drawPlayArea() {
    for (const child of [...playArea.children]) { child.geometry.dispose(); playArea.remove(child); }
    const bounds = data?.scope === 'map' && data.playableBounds;
    $('playAreaRow').hidden = !bounds;
    if (!bounds) return;
    const min = new THREE.Vector3(...bounds.min), max = new THREE.Vector3(...bounds.max);
    const size = new THREE.Vector3().subVectors(max, min), centre = new THREE.Vector3().addVectors(min, max).multiplyScalar(0.5);
    const box = new THREE.BoxGeometry(size.x, size.y, size.z);
    const edgeGeometry = new THREE.EdgesGeometry(box);
    const edges = new THREE.LineSegments(edgeGeometry, playAreaMaterials.line);
    const through = new THREE.LineSegments(edgeGeometry.clone(), playAreaMaterials.through);
    // a box's faces in order +x, -x, +y, -y, +z, -z: the sides only, no lid or floor
    const walls = new THREE.Mesh(box, [playAreaMaterials.wall, playAreaMaterials.wall, playAreaMaterials.none, playAreaMaterials.none, playAreaMaterials.wall, playAreaMaterials.wall]);
    for (const part of [edges, through, walls]) { part.position.copy(centre); part.renderOrder = 2; playArea.add(part); }
    edges.name = 'playAreaEdges'; walls.name = 'playAreaWalls';
  }
  function setPlayArea(on) {
    playArea.visible = Boolean(on); $('playAreaToggle').checked = playArea.visible;
    remember(PLAY_AREA_SHOWN, playArea.visible ? '1' : '0');
  }
  $('playAreaToggle').checked = playArea.visible;
  // The map's size as the project sets it (Map menu, Map grid; prefab plan 5.11). The Build makes the map's tile
  // grid that many tiles from its own corner, so it grows along +X and +Y. Here the scene's grid and play area take the
  // size, so everything that reads them (the play area's box, the tile grid, Interior) follows, and the new area is
  // drawn as a faint sheet at the grid's bottom: green where the Build is to lay the map's ground, grey where the
  // project lays its own.
  const stageArea = new THREE.Group(); world.add(stageArea);
  const stageMaterials = {
    ground: new THREE.MeshBasicMaterial({ color: 0x5f8a3a, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }),
    bare: new THREE.MeshBasicMaterial({ color: 0x8a97a0, transparent: true, opacity: 0.2, side: THREE.DoubleSide, depthWrite: false }),
    line: new THREE.LineBasicMaterial({ color: PLAY_AREA_COLOR, transparent: true, opacity: 0.45, depthWrite: false }),
  };
  // (ownGrid, the map's own size as exported: editor_state.js)
  function ownSize() {
    if (!ownGrid && !builderMode && data?.scope === 'map' && !data.preview && data.tileGrid?.dimensions && data.tileGrid.origin && data.playableBounds)
      setOwnGrid({ dims: [...data.tileGrid.dimensions], max: [...data.playableBounds.max] });
    return ownGrid;
  }
  // The map's size can be set on any whole map (13 November), growing only while it is as it is, and any way, in any of
  // the three, once it is cleared (Clear map plan, section 6). Whether this is the bare map a new map starts from
  // (project.js STAGE_MAPS): the Build lays its ground over the new area.
  const bareMap = () => STAGE_MAPS.includes(activeMapId);
  // The grid a stage asks for, as [nx, ny, nz], when this map can take it; else null (the map's own size)
  function stageDims(next, own = ownSize()) {
    if (!own || !next || !validStage(next, own.dims)) return null;
    const want = [next.grid[0], next.grid[1], next.grid[2] ?? own.dims[2]];
    // a map as it is only grows (the user, 13 November: the blank map's rule for every map); a cleared map any way
    if (!cleared && (want[0] < own.dims[0] || want[1] < own.dims[1] || want[2] < own.dims[2])) return null;
    return want.some((v, k) => v !== own.dims[k]) ? want : null;
  }
  // The grid drawn at `dims` (the play area's box and everything that reads the scene's grid), without changing the
  // project: the Clear map dialog's numbers while they are typed, and setStage
  function showGrid(dims) {
    const own = ownSize();
    if (!own) return;
    const [nx, ny, nz] = dims ?? own.dims, [ox, oy, oz] = data.tileGrid.origin, [sx, sy, sz] = data.tileGrid.size ?? [TILE, TILE, LEVEL];
    data.tileGrid.dimensions[0] = nx; data.tileGrid.dimensions[1] = ny; data.tileGrid.dimensions[2] = nz;
    data.playableBounds.max[0] = dims ? ox + nx * sx : own.max[0];
    data.playableBounds.max[2] = dims ? oy + ny * sy : own.max[2];
    data.playableBounds.max[1] = dims ? oz + nz * sz : own.max[1];
    drawPlayArea(); refreshGroundGrid();
    placeGridHandles(); if (gridTool && !gridDrag) gridPanel();
  }
  function setStage(next) {
    const own = ownSize();
    for (const child of [...stageArea.children]) { child.geometry.dispose(); stageArea.remove(child); }
    const dims = stageDims(next, own);
    // a size this map can't take (smaller than the map's own, not cleared) is kept as the project has it, not drawn
    setStageValue(dims ? tidyStage(next) : (next && validStage(next, own?.dims) && !cleared ? tidyStage(next) : null));
    if (!own) return;
    showGrid(dims);
    // a map grown as it is: the new area as a faint sheet, green where the Build lays the map's ground (where it is laid
    // as planes), grey where the project asked for none
    if (!dims || cleared) return;
    const [nx, ny] = dims, [ox, oy, oz] = data.tileGrid.origin, [sx, sy] = data.tileGrid.size ?? [TILE, TILE];
    const x1 = ox + own.dims[0] * sx, x2 = ox + nx * sx, y1 = oy + own.dims[1] * sy, y2 = oy + ny * sy;
    for (const [ax, ay, bx, by] of [[x1, oy, x2, y2], [ox, y1, x1, y2]]) {
      if (bx - ax < 1 || by - ay < 1) continue;
      const sheet = new THREE.Mesh(new THREE.PlaneGeometry(bx - ax, by - ay), stage.ground === false ? stageMaterials.bare : stageMaterials.ground);
      sheet.rotation.x = -Math.PI / 2; sheet.position.set((ax + bx) / 2, oz + 0.5, (ay + by) / 2);
      sheet.renderOrder = 1; sheet.name = 'stageGround'; stageArea.add(sheet);
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(sheet.geometry), stageMaterials.line);
      edge.rotation.copy(sheet.rotation); edge.position.copy(sheet.position); stageArea.add(edge);
    }
  }
  // ---------------------------------------------------------------- Map grid (the user, 13 November)
  // The rail's Map grid: the play area's box with a handle on each side the grid can move: its far X and Y sides and its
  // top. The corner and the bottom never move (the Build grows and shrinks the grid there). A handle drags along its
  // axis by whole tiles (96 across) or levels (64 up), and each drag is one undo step. A map as it is, the blank map
  // included, only grows, across and up; a cleared map also shrinks and gets lower. The panel reads out
  // the size and the notes (sizeNotes: zones outside, no room for LWR's pods, the ground above the grid).
  let gridForcedPlay = false;     // (gridTool, gridDrag: editor_state.js)
  const gridHandles = new THREE.Group(); world.add(gridHandles); gridHandles.visible = false;
  // game axis -> the view's (x, up, y basis): 0 is view x, 1 (game y) view z, 2 (up) view y
  const GRID_AXES = [{ axis: 0, view: [1, 0, 0], color: 0xff5a5a }, { axis: 1, view: [0, 0, 1], color: 0x4a9cff }, { axis: 2, view: [0, 1, 0], color: 0x5ad17a }];
  const gridHandleMaterials = new Map(GRID_AXES.map(a => [a.axis, new THREE.MeshBasicMaterial({ color: a.color, depthTest: false, transparent: true, opacity: 0.95 })]));
  const gridHandleLine = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6, depthTest: false });
  // What the grid can be here: the axes with a handle and each one's bounds, in tiles and levels
  function gridRule() {
    const own = ownSize();
    if (!own) return null;
    // a map as it is grows across and up (the user, 13 November: up too); a cleared map any way. Up to 256 tiles and 30
    // levels, or the map's own where more (stageMax)
    return { axes: [0, 1, 2], min: cleared ? [1, 1, 1] : [...own.dims], max: stageMax(own.dims) };
  }
  // The cursor's floors on the grid as the project has it (floors.js cursorStoreys; the Build's shell.py), with the made
  // floors' and roofs' own over their footprints (floors.js madeStoreys; the Build's made_cursors.py)
  const madeSlabBoxes = () => [...roots.values()].filter(r => !r.userData.deleted && isMadeSlab(r.userData.source))
    .map(r => boxOf(r)).filter(Boolean).map(b => ({ box: [b[0], b[2], b[4], b[1], b[3], b[5]] }));
  let storeysKept = null;
  const storeysNow = () => {
    const own = ownSize()?.dims ?? null, slabs = madeSlabBoxes();
    const key = JSON.stringify([cleared, own, data?.tileGrid?.dimensions ?? null, slabs]);
    if (storeysKept?.data !== data || storeysKept.key !== key) storeysKept = { data, key, value: cursorStoreys(data, { cleared, own, slabs }) };
    return storeysKept.value;
  };
  // The stage a grid of `dims` asks for (null: the map's own)
  function stageFor(dims) {
    const own = ownSize();
    if (dims.every((v, k) => v === own.dims[k])) return null;
    if (cleared) return { grid: [...dims] };
    return { grid: dims[2] === own.dims[2] ? [dims[0], dims[1]] : [...dims], ...(stage?.ground === false ? { ground: false } : {}) };
  }
  // Where a handle stands (the view's basis): the middle of its side of the play area's box
  function gridHandleAt(axis) {
    const b = data.playableBounds, mid = [0, 1, 2].map(k => (b.min[k] + b.max[k]) / 2);
    return axis === 0 ? new THREE.Vector3(b.max[0], mid[1], mid[2]) : axis === 1 ? new THREE.Vector3(mid[0], mid[1], b.max[2])
      : new THREE.Vector3(mid[0], b.max[1], mid[2]);
  }
  function placeGridHandles() {
    for (const c of [...gridHandles.children]) { c.traverse(o => o.geometry?.dispose()); gridHandles.remove(c); }
    const rule = gridTool && data?.playableBounds ? gridRule() : null;
    gridHandles.visible = Boolean(rule);
    if (!rule) return;
    const b = data.playableBounds, span = Math.max(b.max[0] - b.min[0], b.max[2] - b.min[2]), size = Math.max(90, span * 0.032);
    for (const a of GRID_AXES.filter(g => rule.axes.includes(g.axis))) {
      const at = gridHandleAt(a.axis), dir = new THREE.Vector3(...a.view), handle = new THREE.Group();
      const cone = new THREE.Mesh(new THREE.ConeGeometry(size * 0.45, size * 1.2, 20), gridHandleMaterials.get(a.axis));
      cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir); cone.position.copy(dir.clone().multiplyScalar(size * 1.6));
      const grip = new THREE.Mesh(new THREE.SphereGeometry(size * 0.42, 18, 12), gridHandleMaterials.get(a.axis));
      const stem = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), dir.clone().multiplyScalar(size * 1.1)]), gridHandleLine);
      for (const part of [cone, grip, stem]) { part.renderOrder = 12; part.userData.gridAxis = a.axis; handle.add(part); }
      stem.raycast = () => {};
      handle.position.copy(at);
      gridHandles.add(handle);
    }
  }
  function gridHit(clientX, clientY) {
    if (!gridHandles.visible) return null;
    const hit = rayAt(clientX, clientY).intersectObjects(gridHandles.children, true).find(h => h.object.userData.gridAxis !== undefined);
    return hit ? hit.object.userData.gridAxis : null;
  }
  function gridPanel(dims = [...data.tileGrid.dimensions]) {
    const panel = $('gridPanel');
    panel.hidden = !gridTool;
    if (!gridTool) return;
    const own = ownSize(), rule = gridRule();
    if (!own || !rule) { $('gridSize').textContent = 'This view has no map grid to change.'; $('gridHow').textContent = ''; $('gridGroundRow').hidden = true; $('gridNotes').hidden = true; return; }
    const [nx, ny, nz] = dims, same = dims.every((v, k) => v === own.dims[k]);
    $('gridSize').textContent = `${nx} × ${ny} tiles, ${nz} level${nz === 1 ? '' : 's'}${same ? ': the map\'s own' : ` (the map's own: ${own.dims[0]} × ${own.dims[1]} × ${own.dims[2]})`}.`;
    $('gridHow').textContent = cleared
      ? 'Drag a handle: red moves the far X side, blue the far Y side and green the top, by whole tiles and levels, larger or smaller. The corner and the bottom stay where they are.'
      : 'Drag a handle to make the map larger: red along X and blue along Y by whole tiles, green higher by whole levels. It can\'t be smaller or lower than the map\'s own: clear the map for that.';
    const grows = !cleared && (nx > own.dims[0] || ny > own.dims[1]);
    $('gridGroundRow').hidden = cleared;
    $('gridGround').checked = stage?.ground !== false; $('gridGround').disabled = !grows;
    $('gridOwn').disabled = !stage;
    const notes = sizeNotes(dims);
    if (cleared) notes.push(groundWords(nz));
    if (!cleared && !bareMap() && grows) notes.push('The Build lays more of the map\'s ground over the new area only where the map\'s ground is laid as planes (Bar\'s is), and makes the map\'s own low scenery there (its ground and pavements) walkable; elsewhere lay floors.');
    if (!cleared && nz > own.dims[2]) notes.push('The cursor reaches the new levels by storeys the Build adds over the whole grid, above the map\'s own.');
    $('gridNotes').hidden = !notes.length; $('gridNotes').textContent = notes.join(' ');
  }
  function setGridTool(on) {
    setGridToolValue(Boolean(on) && Boolean(data) && data.scope === 'map' && !data.preview && !builderMode);
    $('editGrid').classList.toggle('on', gridTool); $('editGrid').setAttribute('aria-pressed', String(gridTool));
    // the play area is shown while the handles are, and put back as it was after
    if (gridTool && !playArea.visible) { playArea.visible = true; gridForcedPlay = true; }
    else if (!gridTool && gridForcedPlay) { playArea.visible = false; gridForcedPlay = false; }
    placeGridHandles(); gridPanel();
    if (gridTool) flashHint(cleared ? 'Drag the play area\'s handles to resize the grid' : 'Drag the play area\'s handles to make the grid larger or higher');
  }
  // One undo step for a new size
  function commitStage(next, words) {
    const before = stage;
    if (JSON.stringify(before ?? null) === JSON.stringify(next ?? null)) { setStage(stage); return; }
    gizmo.record({ redo: () => { setStage(next); projectChanged(); }, undo: () => { setStage(before); projectChanged(); } });
    if (words) flashHint(`${words} · Ctrl+Z undoes`);
  }
  function startGridDrag(e) {
    if (!gridTool || e.button !== 0) return false;
    const axis = gridHit(e.clientX, e.clientY);
    if (axis === null) return false;
    const origin = gridHandleAt(axis), dir = new THREE.Vector3(...GRID_AXES[axis].view), t0 = alongLine(e.clientX, e.clientY, origin, dir);
    if (t0 === null) return false;
    setGridDrag({ axis, origin, dir, t0, from: [...data.tileGrid.dimensions], dims: [...data.tileGrid.dimensions], pointerId: e.pointerId });
    controls.enabled = false; renderer.domElement.style.cursor = 'grabbing';
    return true;
  }
  function moveGridDrag(e) {
    const d = gridDrag, t = alongLine(e.clientX, e.clientY, d.origin, d.dir);
    if (t === null) return;
    const step = (data.tileGrid.size ?? [TILE, TILE, LEVEL])[d.axis], rule = gridRule();
    const n = Math.min(rule.max[d.axis], Math.max(rule.min[d.axis], d.from[d.axis] + Math.round((t - d.t0) / step)));
    if (n === d.dims[d.axis]) return;
    d.dims[d.axis] = n;
    showGrid(d.dims); gridPanel(d.dims);
  }
  function endGridDrag(keep) {
    const d = gridDrag;
    setGridDrag(null); controls.enabled = true; renderer.domElement.style.cursor = '';
    if (!d) return;
    if (keep && d.dims.some((v, k) => v !== d.from[k])) commitStage(stageFor(d.dims), `The map grid is ${d.dims[0]} × ${d.dims[1]} × ${d.dims[2]}`);
    else setStage(stage);
  }
  $('editGrid').onclick = () => setGridTool(!gridTool);
  $('projectSize').onclick = () => { showPop(null); setGridTool(true); };
  $('gridDone').onclick = () => setGridTool(false);
  $('gridOwn').onclick = () => commitStage(null, 'The map grid is the map\'s own');
  $('gridGround').onchange = e => {
    if (!stage) return;
    const { ground, ...rest } = stage;
    commitStage(e.target.checked ? rest : { ...rest, ground: false }, e.target.checked ? 'The Build lays ground over the new area' : 'The new area gets no ground');
  };

  return { drawPlayArea, endGridDrag, gridHandleAt, gridHandles, gridHit, moveGridDrag, ownSize, playArea, setGridTool,
           setPlayArea, setStage, startGridDrag, storeysNow };
}
