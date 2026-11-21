// The made pieces' drawing (refactor stage P7; the custom geometry plan's M1, M5 and M6 and the custom geometry
// editing plan's B1 to B3; walls.js and ground.js hold what is pure about the wall, slab and ground tools). Here:
// - the Build menu: the Add button's flyout, whose tools start drawing a made piece at once (BUILD_TOOLS, startBuild,
//   markBuildTool);
// - a wall, a room (with a roof and its building), a floor or roof, or a ground shape drawn: started in a look
//   (startWallDrawing, stopWallDrawing, wallHint), dragged out over the ground with its ghost (startWallDraw,
//   moveWallDraw, drawnNow, showWallGhost) and made as an added copy of the look's donor when the drag lets go
//   (endWallDraw), a room as one locked group;
// - the tops of the made walls a roof is drawn on (wallTopsRound).
//
// createMadeDrawing takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the camera,
// the renderer and the scene, the made pieces' donor template and request, the ground under the pointer, the paste,
// the Buildings view's boxes and the groups' lock. Its own state is the ghosts' meshes; what other areas read or set
// (the Build menu's tool, the drawing under way) is editor_state.js's.
import * as THREE from 'three';
import { builderMode, data, hintTimer, library, pieces, roots, setBuildTool, setWallDrawing,
         wallDrawing } from './editor_state.js';
import { drawnGround, groundBox as groundShapeBox, groundWords as groundShapeWords, slopeWords } from './ground.js';
import { drawnRoom, drawnSlab, drawnWall, roomRoof, SLAB, SLAB_LOOKS, slabLookOf, storeysOf, WALL, wallSpec,
         wallTop } from './walls.js';
import { plural, text } from './dom_words.js';

export function createMadeDrawing({ $, addVolumes, askLineCollision, busyStart, camera, flashHint, fromOf, gizmo,
                                    gridOrigin, groundAt, groundHeight, isMadeWall, lockAsGroup, lookWall, madeRequest,
                                    movedMatrix, newBuilding, pasteSnapshot, pick, plainLook, rayAt, renderer,
                                    restingHint, showPieces, stopPlacing, stopSpawnPlacing, stopZonePlacing,
                                    wallTemplate, world }) {
  // ---- the Build menu (custom geometry editing plan, B1, 19 November 2026): the Add button's flyout starts drawing a made
  // piece at once; the find box finds the same tools by their words
  // (drawn plain, B2: in its kind's default look's shape, the look chosen afterwards in the piece panel)
  const BUILD_TOOLS = {
    wall: { name: 'Wall', words: 'wall walls fracturing', start: () => startWallDrawing(plainLook('wall'), { plain: true }) },
    room: { name: 'Room', words: 'room rooms walls box', start: () => startWallDrawing(plainLook('wall'), { room: true, plain: true }) },
    roomroof: { name: 'Room with a roof', words: 'room rooms roof building walls', start: () => startWallDrawing(plainLook('wall'), { room: true, roof: true, plain: true }) },
    floor: { name: 'Floor', words: 'floor floors storey slab upstairs', start: () => startWallDrawing(plainLook('slab', { look: 'floor' }), { slab: true, plain: true }) },
    roof: { name: 'Roof', words: 'roof roofs slab ceiling', start: () => startWallDrawing(plainLook('slab', { look: 'roof' }), { slab: true, plain: true }) },
    ...Object.fromEntries(['patch', 'block', 'ramp', 'rock'].map(shape => [shape, {
      name: `Ground ${shape}`, words: `ground terrain ${shape}${shape === 'rock' ? ' boulder stone' : shape === 'ramp' ? ' slope' : ' platform'}`,
      start: () => startWallDrawing(plainLook('ground'), { ground: shape, plain: true }) }])),
  };
  // (buildTool, the Build menu's tool being drawn: editor_state.js)
  function startBuild(key) {
    const tool = BUILD_TOOLS[key];
    if (!tool || !data || data.preview || builderMode) return;
    if (pieces.open) showPieces(false);
    tool.start();
    markBuildTool(key);
  }
  function markBuildTool(key) {
    setBuildTool(key);
    for (const b of $('buildFlyout').querySelectorAll('button[data-build]')) b.classList.toggle('on', b.dataset.build === key);
  }
  for (const b of $('buildFlyout').querySelectorAll('button[data-build]')) {
    b.onclick = () => { startBuild(b.dataset.build); b.blur(); };
  }
  // The tops of the made walls along a rectangle's sides ([x0, x1, y0, y1], standing on about `floor`): the highest, or null.
  function wallTopsRound(rect, floor) {
    let top = null;
    for (const r of roots.values()) {
      if (r.userData.deleted || !r.visible || !isMadeWall(r.userData.source)) continue;
      const b = new THREE.Box3().setFromObject(r);
      if (b.isEmpty() || b.max.x < rect[0] - 16 || b.min.x > rect[1] + 16 || b.max.z < rect[2] - 16 || b.min.z > rect[3] + 16) continue;
      if (Math.abs(b.min.y - WALL.bottom - floor) > 64) continue;
      const inside = b.min.x > rect[0] + 16 && b.max.x < rect[1] - 16 && b.min.z > rect[2] + 16 && b.max.z < rect[3] - 16;
      if (!inside) top = Math.max(top ?? -Infinity, b.max.y);
    }
    return top;
  }
  // (wallDrawing, the made piece being drawn: editor_state.js)
  const wallGhostMaterial = new THREE.MeshBasicMaterial({ color: 0x82d5ce, transparent: true, opacity: 0.4, depthWrite: false });
  // (a wall's ghost, and three more for a room's other sides)
  const wallGhosts = [0, 1, 2, 3, 4].map(() => {
    const ghost = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), wallGhostMaterial);
    ghost.visible = false; ghost.matrixAutoUpdate = false; ghost.raycast = () => {}; ghost.renderOrder = 7; world.add(ghost);
    return ghost;
  });
  const wallGhost = { set visible(on) { for (const g of wallGhosts) g.visible = on; } };
  async function startWallDrawing(look, { room = false, slab = false, roof = false, ground = null, plain = false } = {}) {
    stopPlacing(); stopZonePlacing(); stopSpawnPlacing(); stopWallDrawing();
    const drawing = setWallDrawing({ look, room, slab, roof, ground, plain, template: null, start: null });
    renderer.domElement.style.cursor = 'crosshair';
    pieces.setChosen(null);
    const done = busyStart(`Reading ${look.name}…`);
    try {
      const template = await wallTemplate(look);
      const roofTemplate = roof ? await wallTemplate(SLAB_LOOKS[0]) : null;
      if (wallDrawing !== drawing) return;
      drawing.template = template; drawing.roofTemplate = roofTemplate;
      askLineCollision();
      wallHint();
    } catch (error) {
      if (wallDrawing === drawing) { stopWallDrawing(); flashHint(`${look.name} can't be drawn: ${error.message}`); }
    } finally { done(); }
  }
  function wallHint(words = null) {
    clearTimeout(hintTimer);
    const hint = $('dragHint');
    hint.hidden = false;
    // (a plain piece is named by its kind; its look is chosen afterwards in the piece panel)
    const d = wallDrawing, of = d.plain ? '' : ` of ${d.look.name.toLowerCase()}`;
    hint.replaceChildren(words ?? (d.ground
      ? `Drawing a ${d.ground}${of}: press on the ground at one corner, drag to the other${d.ground === 'ramp' ? ' (it rises toward the end)' : ''}, let go · Shift keeps drawing · `
      : d.slab
      ? `Drawing a ${d.plain ? (d.look.role === 'roof' ? 'roof' : 'floor') : d.look.name.toLowerCase()}: press at one corner, drag to the other, let go · Shift keeps drawing · `
      : d.room
      ? `Drawing a room${d.plain ? '' : `${of}s`}${d.roof ? ' with a roof' : ''}: press on the ground at one corner, drag to the other, let go · Shift keeps drawing · `
      : `Drawing a ${d.plain ? 'wall' : d.look.name}: press on the ground at one end, drag along a tile line, let go · Shift keeps drawing · `));
    text(hint, 'kbd', 'Esc'); hint.append(' stops');
  }
  function stopWallDrawing() {
    if (!wallDrawing) return;
    if (wallDrawing.pointerId != null) try { renderer.domElement.releasePointerCapture(wallDrawing.pointerId); } catch { /* released */ }
    setWallDrawing(null); wallGhost.visible = false; renderer.domElement.style.cursor = '';
    pieces.setChosen(null); library.setChosen(null); markBuildTool(null); restingHint();
  }
  // The point of the ground (or a piece) under the pointer, in game units; and the floor under it.
  function wallGround(clientX, clientY) {
    const hit = pick(clientX, clientY)?.point
      ?? rayAt(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -groundHeight()), new THREE.Vector3());
    return hit ? [hit.x, hit.z, hit.y] : null;
  }
  function drawnNow(d, at) {
    const options = { origin: gridOrigin() ?? [0, 0], template: d.template, floor: d.floor, seed: d.seed };
    if (d.ground) return drawnGround(d.start.slice(0, 2), at.slice(0, 2), { ...options, z: d.floor, shape: d.ground, look: d.look });
    if (d.slab) {
      const flat = drawnSlab(d.start.slice(0, 2), at.slice(0, 2), { ...options, z: d.floor, look: d.look });
      if (d.look.role !== 'roof') return flat;
      // a roof: on the tops of the made walls round it, else two storeys over the floor
      const [x, y] = flat.location, top = wallTopsRound([x, x + flat.slab.x1, y, y + flat.slab.y1], d.floor);
      return { ...flat, location: [x, y, Math.round((top ?? d.floor + WALL.top) * 1000) / 1000] };     // (no walls: the Bar's two storeys)
    }
    if (!d.room) return drawnWall(d.start.slice(0, 2), at.slice(0, 2), options);
    const room = drawnRoom(d.start.slice(0, 2), at.slice(0, 2), { ...options, camera: [camera.position.x, camera.position.z] });
    return d.roof ? { ...room, roof: roomRoof(room, { template: d.roofTemplate, floor: d.floor, seed: d.seed + 4, top: wallTop(lookWall(d.look)) }) } : room;
  }
  // The ghost: the wall's solid at the pose drawn (its box in the donor mesh's frame, at the copy's place); a room's four.
  function showWallGhost(template, drawn) {
    if (drawn.slab) { showSlabGhost(template, drawn, 0); for (const g of wallGhosts.slice(1)) g.visible = false; return; }
    if (drawn.ground) {
      const ghost = wallGhosts[0], b = groundShapeBox(drawn.ground);
      ghost.visible = true;
      ghost.matrix.copy(movedMatrix(template, drawn.location, drawn.rotation))
        .multiply(new THREE.Matrix4().makeTranslation((b[0] + b[1]) / 2, (b[4] + b[5]) / 2, (b[2] + b[3]) / 2))
        .multiply(new THREE.Matrix4().makeScale(b[1] - b[0], Math.max(4, b[5] - b[4]), b[3] - b[2]));
      ghost.matrixWorldNeedsUpdate = true;
      for (const g of wallGhosts.slice(1)) g.visible = false;
      return;
    }
    if (drawn.roof) { showSlabGhost(wallDrawing.roofTemplate, drawn.roof, 4); }
    else wallGhosts[4].visible = false;
    const walls = drawn.walls ?? [drawn];
    wallGhosts.forEach((ghost, k) => {
      const w = walls[k];
      ghost.visible = Boolean(w);
      if (!w) return;
      const lw = { ...w.wall, ...lookWall(wallDrawing?.look) }, spec = wallSpec(lw), top = wallTop(lw);
      const a = spec.endInset, b = w.wall.x1 - spec.endInset;
      ghost.matrix.copy(movedMatrix(template, w.location, w.rotation))
        .multiply(new THREE.Matrix4().makeTranslation((a + b) / 2, (top + spec.bottom) / 2, 0))
        .multiply(new THREE.Matrix4().makeScale(b - a, top - spec.bottom, 2 * spec.half));
      ghost.matrixWorldNeedsUpdate = true;
    });
  }
  // A slab's ghost (k: which ghost): its footprint between its look's heights (at least 4 thick, to be seen).
  function showSlabGhost(template, drawn, k) {
    const ghost = wallGhosts[k], look = slabLookOf(drawn.slab), mid = (look.top + look.bottom) / 2;
    ghost.visible = true;
    ghost.matrix.copy(movedMatrix(template, drawn.location, drawn.rotation))
      .multiply(new THREE.Matrix4().makeTranslation(drawn.slab.x1 / 2, mid, drawn.slab.y1 / 2))
      .multiply(new THREE.Matrix4().makeScale(drawn.slab.x1, Math.max(4, look.top - look.bottom), drawn.slab.y1));
    ghost.matrixWorldNeedsUpdate = true;
  }
  const drawnWords = d => (d.ground ? `${d.last.tiles[0]} by ${d.last.tiles[1]} tiles${d.ground === 'ramp' ? ` · ${slopeWords(d.last.ground)}` : ''}`
    : d.slab || d.room ? `${d.last.tiles[0]} by ${d.last.tiles[1]} tiles${d.last.tiles.includes(d.slab ? SLAB.maxTiles : WALL.maxTiles) ? ' (the largest)' : ''}`
    : `${plural(d.last.tiles, 'tile')}${d.last.tiles === WALL.maxTiles ? ' (the longest)' : ''}`);
  function startWallDraw(e) {
    const d = wallDrawing;
    if (!d?.template || e.button !== 0 || d.start) return false;
    const at = wallGround(e.clientX, e.clientY);
    if (!at) return false;
    d.start = at; d.floor = groundAt(at[0], at[1], at[2] + 8) ?? at[2]; d.pointerId = e.pointerId;
    d.seed = 1 + Math.floor(Math.random() * 999999);
    d.last = drawnNow(d, at);
    renderer.domElement.setPointerCapture(e.pointerId);
    showWallGhost(d.template, d.last);
    wallHint(`${drawnWords(d)} · let go to make it · `);
    return true;
  }
  function moveWallDraw(e) {
    const d = wallDrawing, at = wallGround(e.clientX, e.clientY);
    if (!at) return;
    // the far end along the line the drag runs on, at the start's floor (a point on a piece behind is taken at its
    // place on the ground plane through the start)
    const ray = rayAt(e.clientX, e.clientY).ray, plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -d.start[2]);
    const flat = ray.intersectPlane(plane, new THREE.Vector3());
    d.last = drawnNow(d, flat ? [flat.x, flat.z, flat.y] : at);
    showWallGhost(d.template, d.last);
    wallHint(`${drawnWords(d)} · let go to make it · `);
  }
  async function endWallDraw(keep) {
    const d = wallDrawing;
    if (!d?.start) return;
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* released */ }
    const made = d.last, template = d.template, look = d.look, room = d.room, roofTemplate = d.roofTemplate, floor = d.floor, plain = d.plain;
    const chooseWords = plain ? ' · choose its look in the piece panel' : '';
    d.start = null; d.pointerId = null; wallGhost.visible = false;
    if (!keep) stopWallDrawing(); else wallHint();
    if (made.ground) {
      await pasteSnapshot({ entries: [{ source: { ...template, added: { from: fromOf(template), generated: madeRequest('ground', look, made.ground, plain) } },
                                        matrix: movedMatrix(template, made.location, made.rotation) }], pivotIndex: 0, name: look.name }, new THREE.Matrix4());
      flashHint(`Made a ${groundShapeWords(made.ground).toLowerCase()}${plain ? '' : ` of ${look.name.toLowerCase()}`} · its white handles size it${made.ground.shape === 'patch' ? '' : ', the top one raises it'}${chooseWords}`);
      return;
    }
    if (made.slab) {
      await pasteSnapshot({ entries: [{ source: { ...template, added: { from: fromOf(template), generated: madeRequest('fracSlab', look, made.slab, plain) } },
                                        matrix: movedMatrix(template, made.location, made.rotation) }], pivotIndex: 0, name: look.name }, new THREE.Matrix4());
      flashHint(`Made a ${plain ? (look.role === 'roof' ? 'roof' : 'floor') : look.name.toLowerCase()}, ${made.tiles[0]} by ${made.tiles[1]} tiles · its white handles grow it; Add hole is in the piece panel${chooseWords}`);
      return;
    }
    const entries = (made.walls ?? [made]).map(w => ({
      source: { ...template, added: { from: fromOf(template), generated: madeRequest('fracWall', look, w.wall, plain) } },
      matrix: movedMatrix(template, w.location, w.rotation) }));
    if (made.roof)
      entries.push({ source: { ...roofTemplate, added: { from: fromOf(roofTemplate), generated: madeRequest('fracSlab', SLAB_LOOKS[0], made.roof.slab, plain) } },
                     matrix: movedMatrix(roofTemplate, made.roof.location, made.roof.rotation) });
    await pasteSnapshot({ entries, pivotIndex: 0, name: room ? (plain ? 'room' : `room of ${look.name.toLowerCase()}s`) : plain ? 'wall' : look.name }, new THREE.Matrix4());
    // (a room is one locked group, its building with it when it has one: B3, D-2)
    const pasted = gizmo.picks().ids;
    if (made.roof) {
      // its building: the room's rectangle, a floor for each storey, breaking at the storeys' heights, and one over them
      // for the roof, as the game's are: URB_Bar's lists its walls on floor 0 cut down at floor 2, its upstairs floor
      // slab on floor 1 and its roof on floor 2. The game lists a piece in a floor only when its bottom is more than 20
      // under that floor's top, so a slab belongs to the floor it is the bottom of (EXP-76 run E: with the floors 16
      // higher, the floor and roof were in none and never cut away)
      const [x0, y0] = made.roof.location, x1 = x0 + made.roof.slab.x1, y1 = y0 + made.roof.slab.y1, z = floor;
      // (the look's: a wall's floors break at each of its storeys and at its top, a one-storey wall's at its top)
      const lw = lookWall(look), spec = wallSpec(lw), top = wallTop(lw);
      const breaks = [spec.bottom, ...Array.from({ length: storeysOf(lw) - 1 }, (_, k) => spec.storey * (k + 1)), top];
      const boxes = addVolumes([...breaks.slice(0, -1).map((b, k) => ({ box: [x0, y0, z + b, x1, y1, z + breaks[k + 1]], floor: k })),
                                { box: [x0, y0, z + top, x1, y1, z + top + WALL.storey], floor: breaks.length - 1 }], newBuilding());
      // (a wall the active piece, so the panel is the room's, not its building's)
      gizmo.setSelection([...pasted, ...boxes.map(r => r.userData.source.id)], pasted[0]);
      lockAsGroup();
      gizmo.joinLast(3);
      flashHint(`Made a room, ${made.tiles[0]} by ${made.tiles[1]} tiles, with a roof and a building round it: picked as one (Ungroup edits its walls one by one); the roof is cut away when the cursor is inside${chooseWords} · Ctrl+Z takes it out`);
      return;
    }
    if (room) { gizmo.setSelection(pasted, pasted[0]); lockAsGroup(); gizmo.joinLast(2); }
    flashHint(room ? `Made a room, ${made.tiles[0]} by ${made.tiles[1]} tiles: four walls joined at the corners, a doorway in the near side, picked as one (Ungroup edits its walls one by one)${chooseWords}`
      : `Made a ${plain ? 'wall' : look.name}, ${plural(made.tiles, 'tile')} long · its white handles lengthen it; Add gap is in the piece panel${chooseWords}`);
  }

  return { BUILD_TOOLS, endWallDraw, moveWallDraw, startBuild, startWallDraw, startWallDrawing, stopWallDrawing,
           wallGhost, wallHint };
}
