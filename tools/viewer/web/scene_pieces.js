// The scene's pieces (refactor stage P8): what the view draws of a piece and how it is found again. Here:
// - picking: the mouse's ray (rayAt) and the first visible, unclipped piece under a screen point (pick), or every one
//   of them, nearest first (pickAll: Ctrl and the wheel step through them, pick_step.js);
// - textures and materials: a texture read (texture), a material made from the export's record (material; a made
//   piece's plain one, plainMaterial, PLAIN_MATERIAL) and the materials' cache by key (materialKey, materialCache);
// - the meshes' and materials' loads, each once, shared by every piece that uses it (track, loaded) and the box round
//   some pieces' meshes (boundsOf);
// - a piece's root built from its mesh file (buildRoot), added to the scene and taken away (addRoots, removeRoots), its
//   unedited matrix (baseMatrix) and every root put where its edit has it (placeObjects);
// - an original actor's own components in the export (partsOf), the original a copy was copied from (originalOf), an
//   original's box of its meshes' vertices (vertexBox) carried to a new pose (movedBox), and a piece's world box from
//   what is drawn of it (boxOf);
// - an added piece made from its template (addedObject: its own id, newId; a made piece's mesh and materials from its
//   numbers, madeShape and madeShapeOf, standing at scale 1, unscaled);
// - the template a record's piece is copied from (templateFor: the map's own original, else another map's piece read)
//   and the exported pose of the original whose pose rule a piece keeps under tile snap (recipeOf).
// An actor's pose at a render matrix, and the matrix of a pose (actorPose, movedMatrix), are plain exports at the top,
// before the factory: they read only their arguments.
//
// createScenePieces takes what it needs of app.js as one argument object, when app.js makes it: the renderer, the
// camera and the scene's content, the pickables, the texture and mesh loaders and the textures' loads, the grid's
// origin, whether a piece is made, an asset's url, a cover piece's template version, a broken piece drawn, the
// selection and the hints. Its own state is inside it (the loads settled, the materials' cache, the originals' parts
// and vertex boxes, the originals by key for templates and recipes); the meshes loaded are editor_state.js's
// (geometryCache).
import * as THREE from 'three';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { TILE } from './constants.js';
import { COVER_KIND } from './cover.js';
import { builderMode, cachePrefix, data, foreignTemplates, geometryCache, loadErrorCount, roots, selected, setLiveCache,
         setLoadErrorCount } from './editor_state.js';
import { actorMatrix, placedPose } from './gizmo.js';
import { madeGroundShape } from './ground.js';
import { freeShape, isFree } from './made_free.js';
import { withLocalLights } from './lighting.js';
import { isPlain } from './made_requests.js';
import { cloneBlasts, fromOf, isStream, sourceKey } from './piece_records.js';
import { pieceGrid } from './pieces.js';
import { targetKey, tidyLocation, tidyRotator } from './project.js';
import { canTake, missingByAddress, readDds } from './texture_file.js';
import { madeSlabShape, madeWallShape } from './walls.js';

// An actor's pose at a render matrix: game location and rotator. A piece that was only moved keeps its source's own
// rotator exactly, so untouched native values stay as they were.
export function actorPose(source, matrix) {
  const pose = placedPose(source, matrix);
  const turn = matrix.clone().multiply(new THREE.Matrix4().fromArray(source.matrix).invert()).elements;
  const same = [0, 1, 2, 4, 5, 6, 8, 9, 10].every(i => Math.abs(turn[i] - (i % 5 === 0 ? 1 : 0)) < 1e-7);
  return { location: pose.location.map(tidyLocation), rotation: same ? [...source.rotation] : pose.rotation.map(tidyRotator) };
}
// The render matrix that puts a source piece's actor at a game pose (the inverse of actorPose).
export const movedMatrix = (source, location, rotation) => actorMatrix(location, rotation)
  .multiply(actorMatrix(source.location, source.rotation).invert()).multiply(new THREE.Matrix4().fromArray(source.matrix));

export function createScenePieces({ assetUrl, camera, content, coverVersion, drawBroken, flashHint, gltfLoader,
                                    gridOrigin, isMade, loadingState, pickables, renderer, select, textureLoader,
                                    texturePromises }) {
  // Picking: the first visible, unclipped piece under a screen point, or null.
  function rayAt(clientX, clientY) {
    const rect = renderer.domElement.getBoundingClientRect(), ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((clientX-rect.left)/rect.width*2-1, -(clientY-rect.top)/rect.height*2+1), camera);
    return ray;
  }
  // (a hit on a piece drawn and not cut away where it falls)
  const shownHit = h => {
    const root = roots.get(h.object.userData.objectId);
    return root?.visible && (root.userData.clippingPlanes || []).every(plane => plane.distanceToPoint(h.point) >= -0.01);
  };
  const pick = (clientX, clientY) => rayAt(clientX, clientY).intersectObjects(pickables).find(shownHit) ?? null;
  const pickAll = (clientX, clientY) => rayAt(clientX, clientY).intersectObjects(pickables).filter(shownHit);
  // A texture the export wrote as the game stores it (a DDS file of DXT or BC5 blocks with its mips) goes to the GPU
  // as it is, where the GPU has the extension its format needs (texture_file.js); elsewhere, and for the extensions
  // the address names as missing (?texfallback=, for the checks), the server's PNG of it (<file>.png).
  const missing = missingByAddress(globalThis.location?.search);
  const hasExtension = name => !missing.has(name) && Boolean(renderer.extensions.has(name));
  const BLOCKS = { PF_DXT1: 'DXT1', PF_DXT3: 'DXT3', PF_DXT5: 'DXT5', PF_BC5: 'BC5' };
  const GPU_FORMATS = { DXT1: THREE.RGBA_S3TC_DXT1_Format, DXT3: THREE.RGBA_S3TC_DXT3_Format,
                        DXT5: THREE.RGBA_S3TC_DXT5_Format, BC5: THREE.RED_GREEN_RGTC2_Format };
  async function compressed(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url}: ${response.status}`);
    const file = readDds(await response.arrayBuffer());
    const tex = new THREE.CompressedTexture(file.mipmaps, file.width, file.height, GPU_FORMATS[file.format]);
    tex.minFilter = file.mipmaps.length > 1 ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
    tex.generateMipmaps = false;
    tex.needsUpdate = true;
    return tex;
  }
  async function texture(id, color = true, sampling = {channel:0,scale:[1,1]}) {
    if (!id || !data.textures[id]) return null;
    const key = `${id}:${color}:${JSON.stringify(sampling)}`;
    // (a texture that failed to load is asked for again by the next material that needs it: track)
    track(texturePromises, key, async () => {
      const record = data.textures[id], url = assetUrl(record.url), srgb = Boolean(color && record.srgb);
      const blocks = record.container === 'dds' ? BLOCKS[record.format] : null;
      const tex = !blocks ? await textureLoader.loadAsync(url)
        : canTake(blocks, srgb, hasExtension) ? await compressed(url) : await textureLoader.loadAsync(`${url}.png`);
      tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      // UE UVs and extracted PNGs both use a top-left origin. Preserve that
      // convention, as glTF does; flipping the upload mirrors every atlas in V.
      tex.flipY = false;
      tex.channel = sampling.channel;
      tex.repeat.set(...sampling.scale);
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
      return tex;
    });
    return texturePromises.get(key);
  }
  // The plain material of a made piece with no look (B2): light grey, shaded by the lights, the floor's tile lines
  // drawn on it (every 96 units from the tile grid's corner, both ways across the ground).
  const PLAIN_MATERIAL = 'plain:made';
  function plainMaterial() {
    const mat = withLocalLights(new THREE.MeshPhongMaterial({ color: 0xc3cbd0, specular: 0x161616, shininess: 8 }));
    const local = mat.onBeforeCompile, origin = gridOrigin() ?? [0, 0];
    mat.onBeforeCompile = (shader, r) => {
      local?.(shader, r);
      shader.uniforms.plainTileOrigin = { value: new THREE.Vector2(origin[0], origin[1]) };
      shader.fragmentShader = `uniform vec2 plainTileOrigin;\n${shader.fragmentShader}`.replace('#include <dithering_fragment>', `#include <dithering_fragment>
      vec2 plainTile = (vLocalWorld.xz - plainTileOrigin) / ${TILE.toFixed(1)};
      vec2 plainDist = abs(fract(plainTile + 0.5) - 0.5) * ${TILE.toFixed(1)};
      float plainWidth = max(0.6, length(fwidth(vLocalWorld.xz)) * 0.8);
      gl_FragColor.rgb *= 1.0 - 0.45 * (1.0 - smoothstep(0.0, plainWidth, min(plainDist.x, plainDist.y)));`);
    };
    mat.customProgramCacheKey = () => 'plain-made';
    return mat;
  }
  async function material(id,overrideTint=null) {
    if (id === PLAIN_MATERIAL) return plainMaterial();
    const info = data.materials[id];
    if (!info) return withLocalLights(new THREE.MeshPhongMaterial({color: 0xbc628f, side: THREE.DoubleSide}));
    // A fractured mesh's inside faces, which the game draws only where a fragment has broken off (export 14)
    if (info.render?.family === 'hidden') return new THREE.MeshBasicMaterial({visible: false});
    if (info.render?.constantColor) {
      const Type=info.render.unlit || info.render.family === 'fogged-civilian' ? THREE.MeshBasicMaterial : THREE.MeshPhongMaterial;
      return withLocalLights(new Type({
        color:new THREE.Color(...info.render.constantColor),side:info.twoSided ? THREE.DoubleSide : THREE.FrontSide,
        transparent:info.blend === 'BLEND_Translucent',depthWrite:info.blend !== 'BLEND_Translucent',
      }));
    }
    if (info.blend === 'BLEND_Modulate') return new THREE.MeshBasicMaterial({
      color:0xa8b9c2,transparent:true,opacity:0.35,depthWrite:false,blending:THREE.MultiplyBlending,premultipliedAlpha:true,
      side: info.twoSided ? THREE.DoubleSide : THREE.FrontSide,
    });
    const glass = ['BLEND_Translucent', 'BLEND_Additive'].includes(info.blend);
    const masked = ['diffuse-alpha','packed-alpha'].includes(info.render?.opacitySource);
    const diffuse = await texture(info.diffuse,true,info.render?.uv);
    const alpha = await texture(info.opacity,false,info.render?.opacityUv);
    const emission = await texture(info.emissive,false,info.render?.emissiveUv);
    const energy = info.render?.family === 'alien-energy';
    const glow = energy ? (info.vectors.DoorColor || [0.4,0.8,3,1]) : (info.vectors.EmsColor_EmsValue || [0,0,0,0]);
    const tint = overrideTint || info.vectors.TintColor || [1, 1, 1];
    const spec = info.vectors.SpcColor_SpcGloss || [0.2, 0.2, 0.2, 12];
    const mat = new THREE.MeshPhongMaterial({
      color: energy ? new THREE.Color(...glow.slice(0,3)) : glass ? 0x7597a2 : diffuse ? new THREE.Color(...tint.slice(0,3)) : 0x9c6b93,
      map: energy ? emission : diffuse, alphaMap:alpha,
      emissive: new THREE.Color(...(emission || energy ? glow.slice(0,3) : [0,0,0])),
      emissiveMap: emission, emissiveIntensity: energy ? 1 : Math.max(0,glow[3] || 0),
      specular: new THREE.Color(...spec.slice(0,3).map(v => Math.min(0.45,Math.max(0,v*0.1)))), shininess: Math.max(1, spec[3] || 12),
      transparent: glass, opacity: glass ? 0.32 : 1, depthWrite: !glass,
      alphaTest: masked ? (info.alphaTest ?? 0.4) : 0, side: info.twoSided || glass ? THREE.DoubleSide : THREE.FrontSide,
    });
    // Packed UE normals need family-specific decoding. Retain them in the manifest
    // rather than silently treating the DXT alpha channel as an ordinary RGB map.
    return withLocalLights(mat);
  }
  // Meshes and materials load once and are shared by every piece that uses them, copies included.
  const materialCache = new Map();     // (the meshes, geometryCache: editor_state.js)
  // Spawned preview pieces (and copies of them) carry their own tint.
  function materialKey(obj, id) {
    const tint = obj.provenance?.type === 'spawn' || obj.added?.tinted ? obj.tint : null;
    return [`${id}:${JSON.stringify(tint)}`, tint];
  }
  // The catch stops an early failure being reported as unhandled before its piece is reached, and drops the failed load,
  // so the next piece that needs it asks again rather than failing for the page's life (review finding 29).
  // Once loaded, a value can also be had at once with loaded(), for drawing in the middle of a frame.
  const settled = new WeakMap();
  function track(map, key, start) {
    if (map.has(key)) return;
    const promise = start();
    promise.then(v => settled.set(promise, v), () => { if (map.get(key) === promise) map.delete(key); });
    map.set(key, promise);
  }
  const loaded = (map, key) => settled.get(map.get(key));
  // The box round some pieces' meshes, in `frame` (for a piece-list entry: its pivot actor's own frame).
  function boundsOf(sources, frame) {
    const box = new THREE.Box3(), part = new THREE.Box3(), m = new THREE.Matrix4();
    for (const source of sources) {
      const gltf = loaded(geometryCache, source.mesh);
      if (!gltf) continue;
      const placed = frame.clone().multiply(new THREE.Matrix4().fromArray(source.matrix));
      gltf.scene.updateMatrixWorld(true);
      gltf.scene.traverse(mesh => {
        if (!mesh.isMesh) return;
        if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
        box.union(part.copy(mesh.geometry.boundingBox).applyMatrix4(m.multiplyMatrices(placed, mesh.matrixWorld)));
      });
    }
    return box;
  }
  // One piece's render root, built from its mesh file. Copies are built this way too: cloning a placed root
  // would also deep-copy its userData through JSON, materials and textures included.
  async function buildRoot(obj) {
    track(geometryCache, obj.mesh, () => gltfLoader.loadAsync(assetUrl(data.meshes[obj.mesh].url)));
    let base;
    try { base = await geometryCache.get(obj.mesh); }
    catch (error) {
      // a made piece the server can't draw (a look it can't make here): its donor's own mesh, as numbers this page
      // doesn't draw are; the Build makes it all the same
      const made = data.meshes[obj.mesh];
      if (!made?.made || !made.fallback) throw error;
      if (!made.warned) { made.warned = true; flashHint(`${made.name}: the editor can't draw it in its look here, so it shows its donor; the Build makes it`); }
      obj.mesh = made.fallback.mesh; obj.materials = [...made.fallback.materials];
      track(geometryCache, obj.mesh, () => gltfLoader.loadAsync(assetUrl(data.meshes[obj.mesh].url)));
      base = await geometryCache.get(obj.mesh);
    }
    const root = data.meshes[obj.mesh].kind === 'skeletal' ? cloneSkeleton(base.scene) : base.scene.clone(true);
    root.userData.source = obj; root.visible = !obj.hidden && !obj.environment;
    root.userData.flags = obj.initialFlags ? { ...obj.initialFlags } : null;     // its piece flags as the project sets them
    const parts = []; root.traverse(child => { if (child.isMesh) parts.push(child); });
    for (let i=0; i<parts.length; ++i) {
      const [key, tint] = materialKey(obj, obj.materials[i]);
      track(materialCache, key, () => material(obj.materials[i], tint));
      parts[i].material = await materialCache.get(key);
      parts[i].userData.baseMaterial = parts[i].material;
      parts[i].castShadow = !parts[i].material.transparent;
      parts[i].receiveShadow = true;
      parts[i].userData.objectId = obj.id;
    }
    root.userData.parts = parts;
    root.userData.blasts = obj.initialBlasts ? cloneBlasts(obj.initialBlasts) : null;     // (E6) drawn without what they knock out
    root.userData.breaksFurther = Boolean(obj.initialBreaksFurther);
    if (root.userData.blasts) drawBroken(root);
    root.matrix.fromArray(obj.matrix); root.matrixAutoUpdate = false; root.matrixWorldNeedsUpdate = true;
    return root;
  }
  function addRoots(list) {
    setLiveCache(null);
    for (const root of list) {
      roots.set(root.userData.source.id, root); content.add(root); pickables.push(...root.userData.parts);
    }
  }
  // Removed roots keep their geometry: an undo puts the same objects back.
  function removeRoots(list) {
    const parts = new Set(list.flatMap(root => root.userData.parts));
    setLiveCache(null);
    for (const root of list) { roots.delete(root.userData.source.id); content.remove(root); }
    pickables.splice(0, pickables.length, ...pickables.filter(p => !parts.has(p)));
  }
  // The piece's unedited matrix: as exported (for a copy, where it was placed).
  function baseMatrix(root) {
    return new THREE.Matrix4().fromArray(root.userData.source.matrix);
  }
  function placeObjects() {
    for (const root of roots.values()) {
      root.matrix.copy(baseMatrix(root)); root.matrixAutoUpdate = false;
      if (root.userData.edit) root.matrix.premultiply(root.userData.edit);
      root.matrixWorldNeedsUpdate = true;
    }
    content.updateMatrixWorld(true);
    if (selected) select(selected, false, true);
  }
  // The scene's pieces built as a map or a prefab's scene opens (app.js's startScene): the map's own and the streamed
  // missions' objects, counted on the loading overlay.
  async function buildPieces(streamObjects, mapName) {
    // Request every mesh and material up front so downloads overlap; pieces are
    // still assembled in scene order below.
    const everything = [...data.objects, ...streamObjects];
    for (const obj of everything) {
      track(geometryCache, obj.mesh, () => gltfLoader.loadAsync(cachePrefix+data.meshes[obj.mesh].url));
      for (const id of obj.materials) { const [key, tint] = materialKey(obj, id); track(materialCache, key, () => material(id, tint)); }
    }
    let built = 0;
    for (const obj of everything) {
      try { addRoots([await buildRoot(obj)]); }
      catch (e) { console.error(obj.actor, e); setLoadErrorCount(loadErrorCount + 1); }
      built++;
      if (built % 8 === 0 || built === everything.length)
        loadingState(`Opening ${mapName}: building its pieces…`, 0.1 + 0.9 * built / everything.length,
                     `${built} of ${everything.length} pieces · meshes and textures load as they are needed`);
    }
    if (!roots.size && !builderMode) throw Error('No meshes could be displayed. See import notes and browser console.');
  }
  // Building-floor listings as the Build gives them (floors.js copyFloors, the Build's native_copy.copy_floors, which
  // pass the same cases): an original where the map has it keeps its own; a copy, or an original moved, joins the floor
  // it now stands in, by the box of its original's mesh vertices carried to where it stands (floorAt). Exports before
  // 15 have no floor volumes: their copies are listed nowhere, as before.
  let originalParts = null;
  const vertexBoxes = new Map(), vertex = new THREE.Vector3();
  // The export's own components of an original actor, by its key (package|level|actor).
  function partsOf(key) {
    if (!originalParts) {
      originalParts = new Map();
      for (const x of data.objects) { const k = targetKey(fromOf(x)); if (!originalParts.has(k)) originalParts.set(k, []); originalParts.get(k).push(x); }
    }
    return originalParts.get(key) ?? [];
  }
  // The export's own piece an added piece was copied from (one of its components), or the piece itself.
  const originalOf = o => (o.added ? partsOf(targetKey(o.added.from))[0] ?? null : o);
  // An original actor's box [x0, x1, y0, y1, z0, z1] of its meshes' vertices where the map has it (the Build's piece_box).
  function vertexBox(original) {
    const key = targetKey(fromOf(original));
    if (vertexBoxes.has(key)) return vertexBoxes.get(key);
    const box = [Infinity, -Infinity, Infinity, -Infinity, Infinity, -Infinity], m = new THREE.Matrix4();
    for (const part of partsOf(key).length ? partsOf(key) : [original]) {
      const gltf = loaded(geometryCache, part.mesh);
      if (!gltf) return null;
      gltf.scene.updateMatrixWorld(true);
      gltf.scene.traverse(mesh => {
        if (!mesh.isMesh) return;
        m.fromArray(part.matrix).multiply(mesh.matrixWorld);
        const position = mesh.geometry.attributes.position;
        for (let i = 0; i < position.count; i++) {
          vertex.fromBufferAttribute(position, i).applyMatrix4(m);
          const g = [vertex.x, vertex.z, vertex.y];
          for (let k = 0; k < 3; k++) { box[2 * k] = Math.min(box[2 * k], g[k]); box[2 * k + 1] = Math.max(box[2 * k + 1], g[k]); }
        }
      });
    }
    vertexBoxes.set(key, box);
    return box;
  }
  // A box carried as a piece is carried from one actor pose to another (the Build's moved_box): its turned corners' box.
  function movedBox(box, before, after) {
    const m = actorMatrix(after.location, after.rotation).multiply(actorMatrix(before.location, before.rotation).invert());
    const out = [Infinity, -Infinity, Infinity, -Infinity, Infinity, -Infinity];
    for (const x of box.slice(0, 2)) for (const y of box.slice(2, 4)) for (const z of box.slice(4, 6)) {
      vertex.set(x, z, y).applyMatrix4(m);
      const g = [vertex.x, vertex.z, vertex.y];
      for (let k = 0; k < 3; k++) { out[2 * k] = Math.min(out[2 * k], g[k]); out[2 * k + 1] = Math.max(out[2 * k + 1], g[k]); }
    }
    return out;
  }
  // A piece's world box [x0, x1, y0, y1, z0, z1] in game axes from what is drawn of it, vertex by vertex when `precise`.
  const drawnBox = new THREE.Box3();
  function boxOf(root, precise = false) {
    root.updateMatrixWorld(true);
    drawnBox.setFromObject(root, precise);
    return drawnBox.isEmpty() ? null : [drawnBox.min.x, drawnBox.max.x, drawnBox.min.z, drawnBox.max.z, drawnBox.min.y, drawnBox.max.y];
  }
  // Adding and deleting pieces. Like moves, these are edits a project keeps and the Build makes.
  // A copy is a new piece built from its source's mesh and materials, with its own id, actor name and pivot.
  // (the clipboard, clipboard, and the copies' serial: editor_state.js)
  const newId = () => `added:${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`;
  // A made piece's mesh and materials; a plain one's (B2) on the plain material, but for the hidden inside faces. `pose`
  // where it stands, when known ({ location, rotation }: a free-form piece's surface aligned to the world is drawn from
  // there; without it, made_handles.js asks for it again once the piece stands in the scene).
  function madeShape(template, generated, pose = null) {
    const shape = madeShapeOf(template, generated, pose);
    return isPlain(generated) && shape.materials
      ? { ...shape, materials: shape.materials.map(m => (data.materials[m]?.render?.family === 'hidden' ? m : PLAIN_MATERIAL)) } : shape;
  }
  // A made piece's mesh and materials from its numbers (walls.js madeWallShape and madeSlabShape, ground.js
  // madeGroundShape: the mesh record goes into the scene's meshes), or {} when the server can't draw them.
  function madeShapeOf(template, generated, pose = null) {
    if (isFree(generated)) return freeShape(template, generated, data.meshes, pose);
    if (generated?.kind === 'fracSlab') return madeSlabShape(template, generated.slab, generated.blasts, data.meshes);
    if (generated?.kind === 'ground') return madeGroundShape(template, generated.ground, data.meshes);
    return generated?.kind === 'fracWall' ? madeWallShape(template, generated.wall, generated.blasts, data.meshes) : {};
  }
  // An added piece: a copy of one source component, as its own actor (output name, entity id, prefab and partner).
  // A made piece stands at scale 1 whatever its donor's (custom geometry plan, M4b: the Build sets its DrawScale and
  // DrawScale3D to 1; a ground donor placed at 4 gives a look like any other): its matrix without the donor's scale.
  function unscaled(matrix) {
    const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
    matrix.decompose(p, q, s);
    return new THREE.Matrix4().compose(p, q, new THREE.Vector3(1, 1, 1));
  }
  function addedObject(template, placed, { actor, entity, prefab, partner, location, rotation, tinted, flags = null, generated = null, blasts = null, breaksFurther = false }) {
    if (generated && ['fracWall', 'fracSlab', 'ground'].includes(generated.kind)) placed = unscaled(placed);
    return { ...template, ...madeShape(template, generated, location && rotation ? { location, rotation } : null), id: newId(), actor, layer: 'added', hidden: false, environment: false, hiddenBy: null, provenance: null,
      // its piece flags as made (piece flags plan): a paste's are its original's request, a project's its record's; the
      // template's settings (pieceFlags) stay its baseline
      initialFlags: flags ? { ...flags } : null,
      // a copy of one of the map's fracturing pieces broken (E6): its blasts, a paste's its original's
      initialBlasts: blasts?.length && !generated ? cloneBlasts(blasts) : null,
      // (and, a roof or floor the game keeps whole, asked to break further in battle: F-139)
      initialBreaksFurther: Boolean(blasts?.length && !generated && breaksFurther),
      // `floors` stays its original's listings (its template's, a copy's included) and `cutout` its original's: the
      // copy's own listings follow where it stands (listingsNow), as the Build lists it.
      floors: originalOf(template)?.floors ?? template.floors ?? [], prefab, partner, matrix: placed.toArray(), location, rotation,
      // `generated`: a fracturing wall the Build makes from numbers on this piece's materials (custom geometry plan,
      // section 0), kept as the project has it; the view draws the mesh made from its numbers (madeShapeOf)
      added: { from: fromOf(template), entity, tinted, ...(generated ? { generated } : {}),
               ...(template.cover ? { template: { kind: COVER_KIND, version: coverVersion(template.added?.template?.version, template.cover.type) } } : {}) } };
  }
  // The originals by key (recipeOf) and by key and component (templateFor), made at their first use.
  let originalIndex = null;
  // The exported pose of the original whose pose rule a piece has (a ladder, door, car, van or fracturing piece: Align
  // to game pose keeps it), or null.
  function recipeOf(o) {
    if (!o || o.isLight || o.isEffect || isStream(o) || !pieceGrid(o)) return null;
    if (!o.added) return { location: o.location, rotation: o.rotation };
    if (!originalIndex) {
      originalIndex = new Map();
      for (const r of roots.values()) if (!r.userData.source.added) originalIndex.set(targetKey(fromOf(r.userData.source)), r.userData.source);
    }
    const original = originalIndex.get(targetKey(o.added.from)) ?? foreignTemplates.get(`${targetKey(o.added.from)}|${o.component}`);
    if (!original) return null;
    // a made wall's height is free (its columns are made for where it stands): it moves by storeys from its own
    return isMade(o) ? { location: [original.location[0], original.location[1], o.location[2]], rotation: original.rotation }
      : { location: original.location, rotation: original.rotation };
  }
  let templates = null;
  function templateFor(from, component) {
    if (!templates) {
      templates = new Map();
      for (const r of roots.values()) if (!r.userData.source.added) templates.set(`${sourceKey(r.userData.source)}|${r.userData.source.component}`, r.userData.source);
    }
    return templates.get(`${targetKey(from)}|${component}`) ?? foreignTemplates.get(`${targetKey(from)}|${component}`);
  }

  return { addedObject, addRoots, baseMatrix, boundsOf, boxOf, buildPieces, buildRoot, loaded, madeShape, material,
           materialCache, materialKey, movedBox, originalOf, partsOf, pick, pickAll, placeObjects, PLAIN_MATERIAL, rayAt,
           recipeOf, removeRoots, templateFor, texture, track, unscaled, vertexBox };
}
