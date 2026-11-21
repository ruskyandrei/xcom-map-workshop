// Cover blocks and invisible floors (refactor stage P8; EXP-32; cover.js holds what is pure about a cover piece: its
// box, its tiles, its sizes and its words). A cover block or an invisible floor is an invisible piece the Build makes
// from a recipe, drawn here from a box the page makes itself. Here:
// - a cover piece as a piece of the scene: its recipe and the version a block is saved with (coverRecipe,
//   coverVersion, validCoverValues), its mesh and material (ensureCover), its template (coverSource, coverOf) and the
//   Add panel's Invisible kind (coverEntries);
// - the ground under an invisible floor, as the game's floor trace finds it: the map's collision asked for once
//   (askLineCollision, collisionMesh), the ground under a point (groundAt, solidGround), a floor's tiles' centres and
//   how far its top stands over the ground there (floorCentres, floorClearances), and Fit to ground (fitFloor);
// - the piece panel's cover section (coverPanel, floorNote, commitCover) and a new record put on a piece (applyCover;
//   setCover, one undo step);
// - the handles on a picked cover piece (handleCover, coverFacesNow, updateCoverHandles, coverHandleNear,
//   hoverCoverHandle) and their drags (startCoverDrag, moveCoverDrag, endCoverDrag).
//
// createCoverWiring takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the camera,
// the renderer and the scene, the pieces' parts and the meshes' caches, the handles' helpers, the Buildings view's
// hint, the selection and the hints. Its own state is inside it (whether the map's collision was asked for, the
// hovered handle, the pieces' boxes kept); the map's collision as read (lineCollision, lineCollisionFailed: the pieces
// of other maps add theirs, the test hooks read it) and a handle's drag (coverDrag) are editor_state.js's.
import * as THREE from 'three';
import { TILE } from './constants.js';
import { COVER_KIND, COVER_MATERIAL, coverBox, coverFaces, coverFrame, coverGameWords, coverMaterial, coverMeshId,
         coverMeshRecord, coverScene, coverSightWords, coverStart, coverTiles, floorStart, isBlocker, isFloor,
         lengthWords, normalCover, resizedCover, retyped, sizeWords } from './cover.js';
import { onHub } from './edit_hub.js';
import { activeMapId, builderMode, coverDrag, data, families, geometryCache, lightsOn, lineCollision,
         lineCollisionFailed, placing, roots, selected, setCoverDrag, setLineCollision, setLineCollisionFailed,
         snapMode, volumeDrag, volumesOn, zonesOn } from './editor_state.js';
import { actorMatrix } from './gizmo.js';
import { scaleMarker } from './lights_view.js';

export function createCoverWiring({ $, alongLine, camera, editChanged, gizmo, gridOrigin, HANDLE_PICK, materialCache,
                                    pickables, PL, projector, renderer, restingHint, sceneChanged, select, showPop,
                                    track, volumeHint, world }) {
  // Cover blocks (cover.js): invisible pieces that give cover, made by the Build from a recipe (compiler.COVER_RECIPES,
  // served in families.json). A block is a piece like any other here, drawn from a box the page makes itself (its
  // synthetic mesh and material in data.meshes and data.materials, and in the caches as if loaded), at its corner.
  const coverRecipe = () => families?.coverRecipes ?? null;
  // The recipe version a block is saved with: its own while that version makes its type (a blocker needs version 2), else
  // the latest. A later version only adds types, so a block built by either is the same.
  const coverVersion = (version, type) => {
    const r = coverRecipe();
    return version != null && r?.types?.[version]?.includes(type) ? version : r?.latest;
  };
  // A record this page can make (cover.js, in units), as compiler.cover_shape reads one: up to the recipe's tiles across,
  // and a block's heights at most the tallest whole-tile block's apart.
  const validCoverValues = c => {
    const r = coverRecipe();
    if (!r || !c || !Object.hasOwn(r.heights, c.type) || !Array.isArray(c.size) || c.size.length !== 2) return false;
    const across = r.maxTiles * TILE, flat = r.flat?.includes(c.type);
    if (!c.size.every(v => Number.isFinite(v) && v > 0 && v <= across)) return false;
    if (flat) return Object.keys(c).length === 2;
    const span = r.heights.high[1] - r.heights.high[0] + r.heightStep * (r.maxHeight - 1), h = c.heights;
    return Object.keys(c).length === 3 && Array.isArray(h) && h.length === 2 && h.every(v => Number.isFinite(v) && Math.abs(v) <= across)
      && h[1] - h[0] > 0 && h[1] - h[0] <= span;
  };
  function ensureCover(c) {
    const recipe = coverRecipe(), mesh = coverMeshId(c), material = `${COVER_MATERIAL}:${c.type}`;
    data.meshes[mesh] ??= coverMeshRecord(c, recipe);
    data.materials[material] ??= { name: isFloor(c) ? 'Invisible floor (hidden in the game)'
      : isBlocker(c) ? 'Blocker, no cover (hidden in the game)' : `Cover block, ${c.type} cover (hidden in the game)` };
    track(geometryCache, mesh, () => Promise.resolve(coverScene(c, recipe)));
    track(materialCache, `${material}:null`, () => Promise.resolve(coverMaterial(c.type)));
    return { mesh, materials: [material] };
  }
  // A cover block's template, as a placed piece of the map would be: its corner at `location`.
  function coverSource(c, location, rotation) {
    const { mesh, materials } = ensureCover(c);
    const pkg = data.source.file.split(/[\\/]/).at(-1), actor = `${PL}${isFloor(c) ? 'InvisibleFloor' : 'CoverBlock'}`;
    return { id: `cover-template:${mesh}`, actor, component: `${actor}.StaticMeshComponent_0`, sourcePackage: pkg, layer: COVER_KIND,
             actorClass: 'XComLevelActor', componentClass: 'StaticMeshComponent', archetype: 'None', mesh, materials,
             location: [...location], rotation: [...rotation], scale: [1, 1, 1], matrix: actorMatrix(location, rotation).toArray(),
             tint: [1, 1, 1, 1], hidden: false, environment: false, hiddenBy: null, floors: [], prefab: null, partner: null,
             referencedBy: [], breaks: [], destruction: null, cutout: false, areaLights: [], editorLayers: [], provenance: null,
             cover: { ...c } };
  }
  // The Add panel's Invisible kind: a Cover block (coverStart: one tile of high cover) and an Invisible floor (floorStart:
  // one tile), sized with their handles once placed and their cover set in the piece panel (the user's call: no row per
  // size). The corner stands on a tile corner, so tile snap keeps it on the grid.
  const INVISIBLE_KIND = 'Invisible';
  function coverEntries() {
    const recipe = coverRecipe();
    if (!recipe || !data || data.preview) return [];
    const [ox, oy] = gridOrigin() ?? [0, 0], z = data.tileGrid?.origin?.[2] ?? 0;
    const entry = (c, key, id, name, words, title) => {
      const source = coverSource(c, [ox, oy, z], [0, 0, 0]);
      const [lo, hi] = coverBox(c, recipe);
      const box = new THREE.Box3(new THREE.Vector3(lo[0], lo[2], lo[1]), new THREE.Vector3(hi[0], hi[2], hi[1]));
      const size = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]];
      return { key, id, name, mesh: name, pkg: 'invisible in the game', kind: INVISIBLE_KIND, role: 'interior', sources: [source],
               pivotIndex: 0, count: 0, materials: [], milestone: 1, frame: actorMatrix(source.location, source.rotation).invert(),
               box, size, extent: Math.hypot(...size), cover: c, text: words, title };
    };
    const block = coverStart(recipe), floor = floorStart();
    return [
      entry(block, 'cover', 'cover-block', 'Cover block', 'cover block invisible hidden high low cover tall blocker walking none wall',
            'An invisible block, as LWR\'s patches place them: hidden in the game, it blocks movement and gives units beside it high '
            + 'or low cover (units see over low cover), or with Cover set to None no cover at all (units see past it). Placed by its '
            + 'first tile under the cursor as one tile of high cover; drag its handles to size it (with the snap setting\'s steps, '
            + `up to ${recipe.maxTiles} tiles across) and set its cover in the piece panel. The Build makes it on any install`),
      entry(floor, 'floor-plate', 'invisible-floor', 'Invisible floor', 'invisible floor hidden plate walkway walkable',
            'An invisible floor units can stand on: a thin plate hidden in the game, its top at the height it is placed at '
            + '(EXP-32). Placed by its first tile under the cursor; drag its handles to size it, its height with the Z arrow. '
            + 'The Build makes it on any install')];
  }
  // A saved cover block's template at its pose, or null for one this page can't make (an unknown recipe version or size).
  function coverOf(entity) {
    const recipe = coverRecipe(), c = normalCover(entity.cover, recipe);
    if (!recipe?.versions.includes(entity.template.version) || !validCoverValues(c)) return null;
    // as a copy of the Add panel's template (fromOf: the same package, level and actor), made by the saved version
    const source = coverSource(c, entity.location, entity.rotation);
    return { ...source, added: { from: { package: source.sourcePackage, level: COVER_KIND, actor: source.actor },
                                 template: { ...entity.template } } };
  }
  // Invisible floors and the ground (EXP-32): the game looks for a tile's floor along one line straight down through the
  // tile's centre and takes the first standable surface it meets, so a floor plate is the tile's floor (and a flat one,
  // on a ramp) only where its top is over the ground at the tile's centre. That line meets a piece's collision, which
  // for most pieces is a set of convex hulls standing over the drawn surface wherever it dips (up to 5 units on the
  // farm's ramp, where a floor 1 unit over the drawn ramp wasn't found: run 2), so the ground here is the collision's.
  // FLOOR_CLEARANCE is how far over it a floor from the Add panel, or Fit to ground, puts it (1.1 over the hulls was
  // found in run 2).
  const FLOOR_CLEARANCE = 1;
  const groundRay = new THREE.Raycaster();
  // The game's collision for line checks by mesh (collision.json, tools/viewer/collision.py), asked for once, when a
  // floor first needs the ground: mesh id -> { simple: false } (its triangles: the drawn mesh stands for them) or
  // { simple: true, solids } (its convex hulls and boxes, each a mesh in the piece's mesh frame with its centre; none:
  // the game's line passes through it). Until it comes, and for a mesh it doesn't cover (streamed patches'), the drawn
  // mesh stands in.
  let lineCollisionAsked = false;     // (lineCollision, lineCollisionFailed: editor_state.js)
  const collisionMaterial = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  function collisionMesh(c) {
    if (!c) return undefined;
    if (!c.simple) return { simple: false };
    const solids = (c.elements ?? []).map(t => {
      const at = new Float32Array(t.length);
      for (let i = 0; i < t.length; i += 3) { at[i] = t[i]; at[i + 1] = t[i + 2]; at[i + 2] = t[i + 1]; }   // game axes to the page's
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(at, 3));
      geometry.computeBoundingSphere(); geometry.computeBoundingBox();
      const mesh = new THREE.Mesh(geometry, collisionMaterial);
      mesh.matrixAutoUpdate = false;
      return { mesh, centre: geometry.boundingBox.getCenter(new THREE.Vector3()) };
    });
    return { simple: true, solids };
  }
  // A hit's face normal in the world, turned to point out of the solid (whatever the triangle's winding).
  const groundNormal = new THREE.Vector3(), groundCentre = new THREE.Vector3(), groundUp = new THREE.Raycaster();
  function outwardY(hit, solid) {
    groundNormal.copy(hit.face.normal).transformDirection(solid.mesh.matrixWorld);
    groundCentre.copy(solid.centre).applyMatrix4(solid.mesh.matrixWorld);
    return groundNormal.dot(groundCentre.sub(hit.point).negate()) < 0 ? -groundNormal.y : groundNormal.y;
  }
  // Where the floor line meets one solid, as the game's floor trace takes it: a top it enters through looking up more
  // than 0.7 (a steeper face is no floor, and the line goes on through); a line that starts inside the solid leaves it
  // through a face looking down first, and the solid's top over it is the ground there (it stands over the line's
  // start: the floor is inside it). Null where it gives none.
  function solidGround(solid, root) {
    solid.mesh.matrixWorld.copy(root.matrixWorld);
    const first = groundRay.intersectObject(solid.mesh, false)[0];
    if (!first) return null;
    const up = outwardY(first, solid);
    if (up > 0.7) return first.point.y;
    if (up >= 0) return null;
    groundUp.set(new THREE.Vector3(first.point.x, first.point.y + 1e5, first.point.z), new THREE.Vector3(0, -1, 0));
    const top = groundUp.intersectObject(solid.mesh, false)[0];
    return top && outwardY(top, solid) > 0.7 ? top.point.y : null;
  }
  function askLineCollision() {
    if (lineCollisionAsked) return;
    lineCollisionAsked = true;
    if (builderMode) { lineCollision ?? setLineCollision(new Map()); return; }
    // (one map per page: the answer is always the open map's)
    fetch(`/maps/${encodeURIComponent(activeMapId)}/collision.json`).then(r => (r.ok ? r.json() : null)).catch(() => null).then(reply => {
      lineCollision ?? setLineCollision(new Map());
      setLineCollisionFailed(!reply?.meshes);
      for (const [id, c] of Object.entries(reply?.meshes ?? {})) lineCollision.set(id, collisionMesh(c));
      const root = selected && roots.get(selected);
      if (root && isFloor(root.userData.source.cover)) floorNote(root);
    });
  }
  // Each piece's box (drawn mesh, a little wider, as its hulls may be), kept while it doesn't move.
  const groundBoxes = new WeakMap();
  function groundBox(root) {
    let kept = groundBoxes.get(root);
    if (!kept || !kept.at.equals(root.matrixWorld)) {
      kept = { box: new THREE.Box3().setFromObject(root).expandByScalar(8), at: root.matrixWorld.clone() };
      groundBoxes.set(root, kept);
    }
    return kept.box;
  }
  /** The height (game z) of the map's surface straight below (x, y) from `fromZ`: the highest ground the line meets on a
   *  visible piece, by its collision where that has come (solidGround: a solid the line starts in gives its top), by the
   *  drawn mesh until then; the editor's own hidden pieces skipped; null where there is none. */
  function groundAt(x, y, fromZ) {
    askLineCollision();
    groundRay.set(new THREE.Vector3(x, fromZ, y), new THREE.Vector3(0, -1, 0));
    let top = null;
    const higher = z => { if (z != null && (top == null || z > top)) top = z; };
    for (const root of roots.values()) {
      const source = root.userData.source;
      if (!root.visible || source.cover || !root.userData.parts?.length || !groundRay.ray.intersectsBox(groundBox(root))) continue;
      const c = lineCollision?.get(source.mesh);
      if (c?.simple) for (const solid of c.solids) higher(solidGround(solid, root));
      else higher(groundRay.intersectObjects(root.userData.parts, false)[0]?.point.y);
    }
    return top;
  }
  // A cover piece against the tiles round it (cover.js coverTiles, the game's tile rebuild as research/native/cover-build.md
  // has it): its frame in the world, the tile grid's corner and the cover recipe.
  const coverTilesOf = root => coverTiles(root.userData.source.cover, coverFrame(root),
    [...(gridOrigin() ?? [0, 0]), data?.tileGrid?.origin?.[2] ?? 0], coverRecipe());
  /** An invisible floor's tiles' centres on its top, [x, y, z] game units each: the map's tiles whose centre it covers,
   *  where the game looks for a tile's floor (one line straight down through the centre). */
  function floorCentres(root) {
    const { tiles, top } = coverTilesOf(root);
    return tiles.filter(t => t.carried).map(t => [...t.centre, top]);
  }
  /** How far an invisible floor's top stands over the ground at each of its tiles' centres (null where none is under). */
  const floorClearances = root => floorCentres(root).map(([x, y, z]) => { const g = groundAt(x, y, z + 96); return g == null ? null : z - g; });
  const units = v => `${Math.round(v * 10) / 10} unit${Math.abs(Math.round(v * 10) / 10) === 1 ? '' : 's'}`;
  // The floor section's note: its size, and where its top stands over the ground at its tiles' centres.
  function floorNote(root) {
    const c = root.userData.source.cover, carried = floorCentres(root).length, gaps = floorClearances(root).filter(v => v != null);
    const under = gaps.filter(v => v < 0).length, one = carried === 1;
    const [lo, hi] = coverBox(c, coverRecipe());
    let ground = carried ? 'No ground under it.' : 'It covers no tile\'s centre, where the game looks for a floor: it carries no tile.';
    if (under) ground = `Below the ground at the centre of ${one ? 'its tile' : `${under} of its ${carried} tiles`}: the game finds `
      + 'the ground there, not this floor. Fit to ground lifts it.';
    else if (gaps.length) {
      const least = Math.min(...gaps), most = Math.max(...gaps);
      ground = `Its top is ${one || Math.abs(most - least) < 0.05 ? units(least) : `${units(least)} to ${units(most)}`} over the ground at `
        + `${one ? 'its tile\'s centre' : 'its tiles\' centres'}, where the game looks for a floor.`;
    }
    if (gaps.length) ground += !lineCollision ? ' (Reading the ground\'s collision…)'
      : lineCollisionFailed ? ' (Measured from the drawn ground: the game\'s collision couldn\'t be read, and it can stand a few units higher.)'
      : ' (The ground\'s collision, as the game sees it.)';
    $('coverSize').textContent = `${sizeWords(c.size)} across, ${hi[2] - lo[2]} thin; it carries ${carried === 1 ? 'one tile' : `${carried} tiles`} `
      + '(the ones whose centre it covers).';
    $('coverNote').textContent = `Hidden in the game: units can stand on it. ${ground}`;
    $('coverFit').disabled = !gaps.length;
  }
  // Fit to ground: the selected floor raised or lowered so its top stands FLOOR_CLEARANCE over the ground at the tile
  // centre where the ground is highest; one undo step.
  function fitFloor() {
    const root = roots.get(selected), pose = gizmo.pose();
    if (!root || !isFloor(root.userData.source.cover) || !pose) return;
    const gaps = floorClearances(root).filter(v => v != null);
    if (!gaps.length) return;
    const shift = FLOOR_CLEARANCE - Math.min(...gaps);
    if (Math.abs(shift) < 0.01) { floorNote(root); return; }
    gizmo.setPose([pose.location[0], pose.location[1], pose.location[2] + shift], null);
  }
  // The piece panel's cover section: its cover, its size in words (the handles set it) and what the game will do with it.
  function coverPanel(root) {
    const c = root.userData.source.cover, focused = document.activeElement, recipe = coverRecipe(), floor = isFloor(c);
    $('coverHead').textContent = floor ? 'Invisible floor' : isBlocker(c) ? 'Blocker' : 'Cover block';
    $('coverHeight').querySelector('option[value="block"]').hidden = !recipe?.heights?.block;
    if (!floor && focused !== $('coverHeight')) $('coverHeight').value = c.type;
    $('coverTypeRow').hidden = floor;
    $('coverFitRow').hidden = !floor;
    if (floor) { $('coverSight').textContent = ''; floorNote(root); return; }
    const [h0, h1] = c.heights, below = h0 < 0 ? `${lengthWords(-h0)} below its floor` : h0 > 0 ? `${lengthWords(h0)} over its floor` : 'its floor';
    $('coverSize').textContent = `${sizeWords(c.size)} across, from ${below} to ${lengthWords(h1)} ${h1 < 0 ? 'below' : 'above'} it.`;
    const g = coverTilesOf(root);
    $('coverSight').textContent = coverSightWords(c, g);
    $('coverNote').textContent = coverGameWords(c, g);
  }
  // A record and a render matrix put on a cover piece, its box drawn anew (no undo step: setCover and the handles' drags
  // make one).
  function applyCover(root, c, matrix = null) {
    const o = root.userData.source, { mesh, materials } = ensureCover(c);
    Object.assign(o, { cover: { ...c }, mesh, materials });
    const base = coverScene(c, coverRecipe()), material = coverMaterial(c.type);
    const old = new Set(root.userData.parts);
    root.clear();
    const parts = [];
    for (const child of base.scene.children) {
      root.add(child);
      if (!child.isMesh) continue;
      Object.assign(child.userData, { baseMaterial: material, objectId: o.id });
      child.material = material; child.castShadow = false; child.receiveShadow = false;
      parts.push(child);
    }
    root.userData.parts = parts;
    pickables.splice(0, pickables.length, ...pickables.filter(p => !old.has(p)), ...parts);
    if (matrix) gizmo.applyMatrices([root], [matrix]);
    root.updateMatrixWorld(true);
    sceneChanged();
  }
  // A new size, cover or corner for a block (`matrix`: its render matrix after, when its corner moves): one undo step.
  function setCover(root, next, matrix = null, before = { cover: { ...root.userData.source.cover }, matrix: root.matrix.clone() }) {
    const o = root.userData.source;
    const same = JSON.stringify(next) === JSON.stringify(before.cover) && (!matrix || matrix.equals(before.matrix));
    if (!validCoverValues(next) || same) { applyCover(root, before.cover, before.matrix); coverPanel(root); return; }
    gizmo.record({ redo: () => { applyCover(root, next, matrix ?? before.matrix); select(o.id, false, true); },
                   undo: () => { applyCover(root, before.cover, before.matrix); select(o.id, false, true); } });
  }
  function commitCover() {
    const root = roots.get(selected);
    if (!root?.userData.source.cover || isFloor(root.userData.source.cover)) return;
    setCover(root, retyped(root.userData.source.cover, coverRecipe(), $('coverHeight').value));
  }
  // ---- a cover block's or invisible floor's handles (private/plans/done/cover-block-handles-plan.md, decisions 2 and 3):
  // with one selected, a white handle off each face along the piece's own axes (four sides, and a block's top and
  // bottom), drawn and picked as a building box's are. A drag moves that face by the snap setting's steps
  // (cover.js resizedCover): a low side's drag moves the corner too, so the opposite side stays; Esc puts it back, and
  // the drag is one undo step.
  const COVER_FACE_WORDS = { '-x': 'Side −X', '+x': 'Side +X', '-y': 'Side −Y', '+y': 'Side +Y', '-z': 'Bottom', '+z': 'Top' };
  const SNAP_STEPS = { off: 'steps of 1 unit', fine: 'steps of 24', tile: 'whole tiles' };
  const coverHandleLayer = new THREE.Group(); world.add(coverHandleLayer);
  const coverHandles = new Map(Object.keys(COVER_FACE_WORDS).map(key => {
    const material = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), material);
    mesh.renderOrder = 9; mesh.raycast = () => {}; mesh.userData.material = material; coverHandleLayer.add(mesh);
    return [key, mesh];
  }));
  const coverStems = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(36), 3)),
                                            new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, depthTest: false }));
  coverStems.renderOrder = 8; coverStems.raycast = () => {}; coverStems.frustumCulled = false; coverHandleLayer.add(coverStems);
  let coverHover = null;     // (coverDrag: editor_state.js)
  // The cover piece the handles are on: the one piece picked, shown, in the Normal view, nothing being placed.
  function handleCover() {
    const root = roots.get(selected);
    if (!root?.userData.source.cover || root.userData.deleted || !root.visible || placing || volumesOn || lightsOn || zonesOn
        || gizmo.picks().ids.length !== 1) return null;
    return root;
  }
  // Its faces now, in the view: each { face: [key, axis, side], at (the face's middle), dir (out along the axis), centre,
  // half (the box's half size along it) }.
  function coverFacesNow(root) {
    const c = root.userData.source.cover, [lo, hi] = coverBox(c, coverRecipe());
    root.updateMatrixWorld(true);
    const toView = ([x, y, z]) => new THREE.Vector3(x, z, y).applyMatrix4(root.matrixWorld);
    const middle = [0, 1, 2].map(k => (lo[k] + hi[k]) / 2), centre = toView(middle);
    return coverFaces(c).map(face => {
      const [, axis, side] = face, p = [...middle];
      p[axis] = side < 0 ? lo[axis] : hi[axis];
      const at = toView(p), out = [...p];
      out[axis] += side;
      return { face, at, dir: toView(out).sub(at).normalize(), centre, half: (hi[axis] - lo[axis]) / 2 };
    });
  }
  // Where a handle is drawn: out from its face, clear of the gizmo's arrows (as a building box's, handlePoint).
  function coverHandlePoint(f) {
    const d = camera.position.distanceTo(f.centre);
    return f.centre.clone().addScaledVector(f.dir, Math.max(f.half + d * 0.035, d * 0.2));
  }
  function updateCoverHandles() {
    const root = coverDrag?.root ?? handleCover();
    coverHandleLayer.visible = Boolean(root) && !gizmo.controls.dragging;
    if (!coverHandleLayer.visible) { if (coverHover) hoverCoverHandle(null); return; }
    const faces = new Map(coverFacesNow(root).map(f => [f.face[0], f])), lit = coverDrag?.face[0] ?? coverHover;
    const stems = coverStems.geometry.attributes.position;
    let n = 0;
    for (const [key, mesh] of coverHandles) {
      const f = faces.get(key);
      mesh.visible = Boolean(f);
      if (!f) continue;
      mesh.position.copy(coverHandlePoint(f));
      mesh.userData.material.color.setHex(key === lit ? 0xffe27a : 0xffffff);
      scaleMarker(mesh, camera, mesh.position);
      stems.setXYZ(n++, f.at.x, f.at.y, f.at.z); stems.setXYZ(n++, mesh.position.x, mesh.position.y, mesh.position.z);
    }
    for (; n < 12; n++) stems.setXYZ(n, 0, 0, 0);
    stems.needsUpdate = true;
  }
  function coverHandleNear(x, y) {
    const root = handleCover();
    if (!root || gizmo.controls.dragging) return null;
    const project = projector();
    return coverFacesNow(root).map(f => { const s = project(coverHandlePoint(f)); return s && { f, d: Math.hypot(s[0] - x, s[1] - y) }; })
      .filter(c => c && c.d <= HANDLE_PICK + 2).sort((a, b) => a.d - b.d)[0]?.f ?? null;
  }
  function hoverCoverHandle(f) {
    const key = f?.face?.[0] ?? f ?? null;
    if (key === coverHover) return;
    coverHover = key;
    renderer.domElement.style.cursor = key ? 'grab' : '';
    renderer.domElement.title = key ? `${COVER_FACE_WORDS[key]}: drag to size it (${SNAP_STEPS[snapMode]}, as the snap setting)` : '';
  }
  function startCoverDrag(e) {
    if (e.button !== 0 || coverDrag || volumeDrag || gizmo.controls.dragging) return false;
    const f = coverHandleNear(e.clientX, e.clientY);
    if (!f) return false;
    const root = handleCover(), from = alongLine(e.clientX, e.clientY, f.at, f.dir);
    if (from == null) return false;
    setCoverDrag({ root, face: f.face, at: f.at, dir: f.dir, from, pointerId: e.pointerId,
                  before: { cover: { ...root.userData.source.cover }, matrix: root.matrix.clone() }, after: null });
    showPop(null);
    renderer.domElement.setPointerCapture(e.pointerId);
    renderer.domElement.style.cursor = 'grabbing';
    return true;
  }
  function moveCoverDrag(e) {
    const d = coverDrag, t = alongLine(e.clientX, e.clientY, d.at, d.dir);
    if (t == null) return;
    const { cover, shift } = resizedCover(d.before.cover, coverRecipe(), d.face, t - d.from, snapMode);
    // a low side moved: the corner moves along the piece's own axis (dir points out of that side, so back along it)
    const matrix = d.before.matrix.clone();
    if (shift) matrix.premultiply(new THREE.Matrix4().makeTranslation(...d.dir.clone().multiplyScalar(-shift).toArray()));
    d.after = { cover, matrix };
    applyCover(d.root, cover, matrix);
    coverPanel(d.root);
    const [h0, h1] = cover.heights ?? [];
    volumeHint(`${COVER_FACE_WORDS[d.face[0]]}: ${sizeWords(cover.size)}${cover.heights ? `, from ${Math.round(h0 * 100) / 100} to ${Math.round(h1 * 100) / 100}` : ''} (${SNAP_STEPS[snapMode]})`);
  }
  function endCoverDrag(keep) {
    const d = coverDrag;
    if (!d) return false;
    setCoverDrag(null);
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
    renderer.domElement.style.cursor = '';
    if (keep && d.after) setCover(d.root, d.after.cover, d.after.matrix, d.before);
    else { applyCover(d.root, d.before.cover, d.before.matrix); coverPanel(d.root); }
    restingHint(); editChanged();
    return true;
  }

  // After an edit (the edit hub, edit_hub.js): a picked invisible floor's height over the ground, once a drag ends.
  onHub('edit', 'floor-note', () => {
    if (selected && isFloor(roots.get(selected)?.userData.source.cover) && !gizmo.controls.dragging) floorNote(roots.get(selected));
  });
  // As something is picked (the edit hub's select runs): the cover section shown for a cover piece, and filled.
  onHub('select-sections', 'cover', root => { $('coverBox').hidden = !root?.userData.source?.cover; });
  onHub('select-cover', 'cover', root => { coverPanel(root); });

  return { askLineCollision, collisionMesh, commitCover, coverEntries, coverFacesNow, coverHandleNear, coverHandlePoint,
           coverOf, coverPanel, coverRecipe, coverVersion, endCoverDrag, fitFloor, FLOOR_CLEARANCE, groundAt,
           handleCover, hoverCoverHandle, moveCoverDrag, setCover, startCoverDrag, updateCoverHandles };
}
