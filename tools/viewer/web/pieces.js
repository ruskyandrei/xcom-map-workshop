// The piece list (Add): one entry for each distinct piece this map has, to place fresh copies of.
// An entry is what copying one placed instance takes along: the actor and its linked pieces (a car's body,
// glass and light bar, a prefab's parts). Instances alike in every part (class, archetype, mesh, materials,
// tint) make one entry, with a count. Only pieces the map has placed can be listed: the export holds no others.
import * as THREE from 'three';
import { withoutLocalLights } from './lighting.js';
import { pieceKind, inKind, setKindOptions } from './piece_categories.js';
// Every piece is in a family (the compiler's FAMILIES, served by tools/viewer/families.py with the map's assemblies),
// which says whether the Build makes it and, while it doesn't, the milestone that will: static scenery, destructible
// props, collectibles, ladders, doors, cars, vans, fracturing pieces (walls, storey floors) and physics props
// build. A class with no family of its own comes with M3. Until then such edits are drawn and
// saved, not built. A piece of one of the map's assemblies (a car's parts,
// a door's leaf and frame, a ladder) takes the assembly's family, any other piece its class's; a piece naming a
// partner it isn't assembled with counts as a car's, as the compiler counts it (tools/editor/compiler.py family_of).
// A fracturing piece keeps the pose rule on its own (pieceGrid), as the assemblies do.
let families = null, assemblyFamily = () => null;
/** The families table (families.json) and assemblyFamily(obj): the family of the map's assembly the piece is in or
 *  was copied from, or null. With no table every piece counts as building. */
export function useFamilies(table, familyOfAssembly) { families = table; assemblyFamily = familyOfAssembly; }
const pieceFamily = obj => assemblyFamily(obj) ?? (obj.partner ? 'car' : families?.classFamily[obj.actorClass] ?? 'other');
const familyRecord = obj => families?.families[pieceFamily(obj)] ?? null;
/** Whether the piece keeps the pose rule (poserule.js): whole tiles, storeys and quarter turns from its original. */
export const pieceGrid = obj => Boolean(familyRecord(obj)?.grid);
// A collectible (a UFO power core and the like) is mission loot while it stands. Its copy is a destructible prop that
// breaks at its first damage, as the original does, but isn't loot; a moved or deleted original is hidden, not
// destroyed, so it may still count (the compiler warns the same: LOOT_NOTES in tools/editor/compiler.py).
export const lootNote = obj => (obj.actorClass !== 'XComCollectible' ? null
  : obj.added ? { label: 'Not loot', title: 'A copy of a collectible: it breaks at its first damage, as the original does, but it is not mission loot' }
  : { label: 'Mission loot', title: 'A collectible: the game counts it as loot while it stands. Copies of it are not loot, and if it is moved or deleted it is hidden, so it may still count as loot' });
// What the game's damage does to a piece: export 17's `destruction` (the toughness the piece names, its health and
// flags; tools/viewer/scene_metadata.py has the game's rules), as the panel's Destructible and Health lines.
const FRACTURING_DAMAGE = 'explosions, fire, lasers, plasma, heavy guns and melee';
const FLAG_WORDS = { bFragile: 'fragile', bImmuneToAreaBurnDamage: 'immune to burning', bSuccumbsToDamage: 'one damage type breaks it' };
/** { destructible, health (null when there is none to show), title } for a piece of an export of `version`. */
export function destructionNote(obj, version) {
  if (!(version >= 17) || obj.destruction === undefined) return { destructible: 'Unknown: export the map again', health: null,
    title: 'Exports before version 17 don\'t record toughness: delete the map\'s export folder and open the map again' };
  const d = obj.destruction;
  if (!d) return { destructible: 'No', health: null, title: `A ${obj.actorClass} has no toughness or health: the game's damage doesn't break it` };
  const flags = d.flags.filter(f => f !== 'bInvincible').map(f => FLAG_WORDS[f] ?? f);
  const why = d.defaulted ? 'no toughness set: the class default' : d.toughness;
  const health = d.health != null ? `${d.health} (${[why, ...flags].join(', ')})`
    : d.toughness ? `Unknown (${d.toughness} is in another package)` : null;
  if (d.flags.includes('bInvincible')) {
    const only = d.flags.includes('bSuccumbsToDamage');
    return { destructible: only ? 'Only by one damage type' : 'No: invincible', health: only ? health : null,
      title: `Its toughness, ${d.toughness}, is invincible: ${only ? 'only the one damage type it succumbs to hurts it' : 'damage doesn\'t break it'}` };
  }
  if (d.kind === 'fracture') {
    if (!d.toughness) return { destructible: 'Unknown: no toughness set', health: null,
      title: 'A fracturing piece that names no toughness (852 of the game\'s fracturing pieces don\'t): what the game\'s native code makes of it wasn\'t worked out' };
    return { destructible: 'Yes, a part at a time', health,
      title: `A fracturing piece (a wall, a floor, a window) loses its parts within a hit's radius: hits by ${FRACTURING_DAMAGE}, not bullets. `
        + 'An explosion hits them for 1000, a shot for its world damage; the game\'s native code weighs that against the toughness\'s health (exactly how wasn\'t worked out)' };
  }
  const damage = `Hits take their damage off its health (75 to 125% of each hit's), and at 0 it is destroyed. ${d.flags.includes('bFragile')
    ? 'Fragile: any damage hurts it, bullets too' :`Only hits by ${FRACTURING_DAMAGE} hurt it; bullets don't`}`;
  if (obj.actorClass === 'XComCollectible') return { destructible: 'Yes: its first damage destroys it', health,
    title: `A collectible blows itself up as soon as it is damaged, whatever its health. ${damage}` };
  return { destructible: d.flags.includes('bFragile') ? 'Yes, by any damage' : 'Yes, not by bullets', health, title: damage };
}
const ROLES = { interior: 'Play area', backdrop: 'Backdrop', roof: 'Roofs', helper: 'Helpers' };
const SORTS = {
  name: (a, b) => a.name.localeCompare(b.name) || b.count - a.count,
  size: (a, b) => b.extent - a.extent || a.name.localeCompare(b.name),
  count: (a, b) => b.count - a.count || a.name.localeCompare(b.name),
};
const THUMB = 48;   // thumbnail size, CSS pixels
// The Lights kind: entries app.js adds for a new point or spot light (editor lights plan 3.3), with `light` set to the
// light's kind, `colour` (0 to 1) and `detail`; no sources and no thumbnail scene, an icon drawn instead.
const LIGHTS = 'Lights';
/** A light entry's icon: a bulb with its glow for a point light, a lamp head with its cone and pool for a spot light,
 *  in the light's colour. */
function drawLightIcon(canvas, kind, colour) {
  const g = canvas.getContext('2d'), s = canvas.width, rgb = colour.map(c => Math.round(Math.min(1, c) * 255)).join(', ');
  g.fillStyle = '#1f2a33'; g.fillRect(0, 0, s, s);
  g.save(); g.scale(s / 48, s / 48);
  if (kind === 'point') {
    const glow = g.createRadialGradient(24, 21, 2, 24, 21, 22);
    glow.addColorStop(0, `rgba(${rgb}, 0.95)`); glow.addColorStop(0.45, `rgba(${rgb}, 0.35)`); glow.addColorStop(1, `rgba(${rgb}, 0)`);
    g.fillStyle = glow; g.fillRect(0, 0, 48, 48);
    g.fillStyle = `rgb(${rgb})`; g.strokeStyle = '#0d1418'; g.lineWidth = 1.5;
    g.beginPath(); g.arc(24, 20, 8, Math.PI * 0.8, Math.PI * 2.2); g.lineTo(28, 32); g.lineTo(20, 32); g.closePath(); g.fill(); g.stroke();
    g.fillStyle = '#8a9da9'; g.fillRect(20, 33, 8, 3); g.fillRect(21, 37, 6, 2);
  } else {
    const cone = g.createLinearGradient(0, 12, 0, 42);
    cone.addColorStop(0, `rgba(${rgb}, 0.8)`); cone.addColorStop(1, `rgba(${rgb}, 0.12)`);
    g.fillStyle = cone; g.beginPath(); g.moveTo(20, 13); g.lineTo(28, 13); g.lineTo(40, 40); g.lineTo(8, 40); g.closePath(); g.fill();
    g.fillStyle = `rgba(${rgb}, 0.55)`; g.beginPath(); g.ellipse(24, 40, 16, 4, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#8a9da9'; g.strokeStyle = '#0d1418'; g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(18, 5); g.lineTo(30, 5); g.lineTo(28, 13); g.lineTo(20, 13); g.closePath(); g.fill(); g.stroke();
    g.fillStyle = `rgb(${rgb})`; g.fillRect(20, 12, 8, 2);
  }
  g.restore();
}
/** A landing zone entry's icon: the drop zone's box, the six soldier points and the arrow they face along. */
function drawZoneIcon(canvas) {
  const g = canvas.getContext('2d'), s = canvas.width;
  g.fillStyle = '#1f2a33'; g.fillRect(0, 0, s, s);
  g.save(); g.scale(s / 48, s / 48);
  g.strokeStyle = '#5ab0ff'; g.lineWidth = 2; g.strokeRect(14, 30, 20, 12);
  g.fillStyle = '#5ab0ff';
  for (const [x, y] of [[12, 14], [24, 10], [36, 14], [12, 23], [24, 19], [36, 23]]) { g.beginPath(); g.arc(x, y, 3, 0, Math.PI * 2); g.fill(); }
  g.beginPath(); g.moveTo(24, 6); g.lineTo(20, 2); g.moveTo(24, 6); g.lineTo(28, 2); g.stroke();
  g.restore();
}
// A new spawn point's icon (app.js spawnAddEntries): the Spawns view's marker, an orange ring for a pod, a green dot
// for a Meld point and a grey box for a no-spawn volume, in its halo
function drawSpawnIcon(canvas, kind) {
  const g = canvas.getContext('2d'), s = canvas.width, colour = { pod: '#ff9f43', noSpawn: '#8a94a6' }[kind] ?? '#20bf6b';
  g.fillStyle = '#1f2a33'; g.fillRect(0, 0, s, s);
  g.save(); g.scale(s / 48, s / 48);
  g.strokeStyle = colour; g.globalAlpha = 0.45; g.lineWidth = 3;
  g.beginPath(); g.arc(24, 24, 18, 0, Math.PI * 2); g.stroke();
  g.globalAlpha = 1;
  if (kind === 'pod') { g.lineWidth = 4; g.beginPath(); g.arc(24, 24, 9, 0, Math.PI * 2); g.stroke(); }
  else if (kind === 'noSpawn') {
    g.lineWidth = 2.5; g.globalAlpha = 0.25; g.fillStyle = colour; g.fillRect(14, 16, 20, 16); g.globalAlpha = 1;
    g.strokeRect(14, 16, 20, 16); g.beginPath(); g.moveTo(14, 16); g.lineTo(19, 11); g.lineTo(39, 11); g.lineTo(34, 16);
    g.moveTo(39, 11); g.lineTo(39, 27); g.lineTo(34, 32); g.stroke();
  } else { g.fillStyle = colour; g.beginPath(); g.arc(24, 24, 8, 0, Math.PI * 2); g.fill(); }
  g.restore();
}
const tiles = units => Math.max(1, Math.round(units / 96));   // a floor piece's size across in whole tiles (a curb drops out)
const short = path => path.split('.').at(-1);
// The package path an archetype sits in: a prefab's parts share their prefab's (VEH_MovingVan.Prefab.PRE_MovingVanA).
const outer = a => (a && a !== 'None' && a.includes('.') ? a.slice(0, a.lastIndexOf('.')) : null);
const recipe = o => [o.actorClass, o.archetype, o.mesh, o.materials.join(','), (o.tint ?? []).join(',')].join('|');

/** The map's distinct pieces. groups: the ids of the map's own pieces as copies take them along (deleted ones
 *  included: the list is the map as exported); frameOf(source): the matrix into that actor's own frame;
 *  boundsOf(sources, frame): their box in that frame. */
export function collectPieces({ roots, data, groups, frameOf, boundsOf }) {
  const byKey = new Map();
  const radius = s => data.meshes[s.mesh].bounds?.[6] ?? 0;
  for (const ids of groups) {
    const sources = ids.map(i => roots.get(i).userData.source).filter(s => !s.hidden && !s.environment && !s.added);
    if (!sources.length) continue;
    const key = sources.map(recipe).sort().join('\n');
    const known = byKey.get(key);
    if (known) { known.count++; continue; }
    // The biggest part names the entry and holds the pivot: a car's body, not its glass.
    const pivot = sources.reduce((a, b) => (radius(b) > radius(a) ? b : a));
    const frame = frameOf(pivot), box = boundsOf(sources, frame), size = box.getSize(new THREE.Vector3());
    const mesh = data.meshes[pivot.mesh].name, kind = pieceKind(pivot.actorClass, pieceFamily(pivot));
    // A prefab's parts go by the prefab's name; anything else by its biggest mesh.
    const prefab = sources.length > 1 && outer(pivot.archetype) && sources.every(s => outer(s.archetype) === outer(pivot.archetype))
      ? short(outer(pivot.archetype)) : null;
    const materials = sources.flatMap(s => s.materials.map(m => short(data.materials[m]?.name ?? '')));
    byKey.set(key, {
      key, id: `piece-${byKey.size}`, name: prefab ?? short(mesh), mesh, pkg: mesh.split('.')[0], kind, role: pivot.sceneryRole ?? 'interior',
      sources, pivotIndex: sources.indexOf(pivot), count: 1, materials,
      // An assembly builds when all its parts do.
      // Viewer basis in the actor's frame: x is game X, y is up, z is game Y.
      frame, box, size: [size.x, size.z, size.y], extent: size.length(),
      text: [...sources.map(s => data.meshes[s.mesh].name), ...sources.map(s => s.archetype).filter(a => a !== 'None'),
             pivot.actorClass, kind, ...materials].join(' ').toLowerCase(),
    });
  }
  return [...byKey.values()];
}

// Rows for pieces of This map and recipes in either scope.
export function pieceRow(entry, pixelRatio, choose) {
  if (entry.spawnAdd) {     // the Spawn points kind (app.js spawnAddEntries): placed with a click in the Spawns view
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'libitem'; button.dataset.id = entry.id;
    const thumb = document.createElement('canvas');
    thumb.width = thumb.height = Math.round(THUMB * pixelRatio);
    drawSpawnIcon(thumb, entry.spawnAdd);
    thumb.dataset.drawn = '1';
    const label = document.createElement('span');
    label.append(Object.assign(document.createElement('strong'), { textContent: entry.name }),
      Object.assign(document.createElement('small'), { textContent: `Spawn points · ${entry.pkg}` }),
      Object.assign(document.createElement('small'), { textContent: entry.detail }));
    const tags = Object.assign(document.createElement('span'), { className: 'tags' });
    tags.append(Object.assign(document.createElement('span'), { className: 'tag', textContent: `×${entry.count}`,
      title: `${entry.count} on this map` }));
    button.title = entry.title;
    button.append(thumb, label, tags);
    button.onclick = choose;
    button.thumb = thumb;
    return button;
  }
  if (entry.zone) {     // the Landing zones kind (app.js zoneEntries): placed with a click, as View options' button does
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'libitem'; button.dataset.id = entry.id;
    const thumb = document.createElement('canvas');
    thumb.width = thumb.height = Math.round(THUMB * pixelRatio);
    drawZoneIcon(thumb);
    thumb.dataset.drawn = '1';
    const label = document.createElement('span');
    label.append(Object.assign(document.createElement('strong'), { textContent: entry.name }),
      Object.assign(document.createElement('small'), { textContent: `Landing zones · ${entry.pkg}` }),
      Object.assign(document.createElement('small'), { textContent: entry.detail }));
    const tags = Object.assign(document.createElement('span'), { className: 'tags' });
    tags.append(Object.assign(document.createElement('span'), { className: 'tag', textContent: `×${entry.count}`,
      title: `${entry.count} landing zone${entry.count === 1 ? '' : 's'} on this map now` }));
    button.title = entry.title;
    button.append(thumb, label, tags);
    button.onclick = choose;
    button.thumb = thumb;
    return button;
  }
  if (entry.light) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'libitem'; button.dataset.id = entry.id;
    const thumb = document.createElement('canvas');
    thumb.width = thumb.height = Math.round(THUMB * pixelRatio);
    drawLightIcon(thumb, entry.light, entry.colour);
    thumb.dataset.drawn = '1';
    const label = document.createElement('span');
    label.append(Object.assign(document.createElement('strong'), { textContent: entry.name }),
      Object.assign(document.createElement('small'), { textContent: `${LIGHTS} · ${entry.pkg}` }),
      Object.assign(document.createElement('small'), { textContent: entry.detail }));
    const tags = Object.assign(document.createElement('span'), { className: 'tags' });
    if (entry.count) tags.append(Object.assign(document.createElement('span'), { className: 'tag', textContent: `×${entry.count}`,
      title: `${entry.count} ${entry.light} lights in this map` }));
    if (!entry.builds) tags.append(Object.assign(document.createElement('span'), { className: 'tag test', textContent: 'Test',
      title: entry.note }));
    button.title = entry.title;
    button.append(thumb, label, tags);
    button.onclick = choose;
    button.thumb = thumb;
    return button;
  }
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'libitem'; button.dataset.id = entry.id;
  const thumb = document.createElement('canvas');
  thumb.width = thumb.height = Math.round(THUMB * pixelRatio);
  const label = document.createElement('span');
  const parts = entry.sources.length > 1 ? ` · ${entry.sources.length} parts` : '';
  const [w, d, h] = entry.size.map(Math.round);
  label.append(Object.assign(document.createElement('strong'), { textContent: entry.name }),
    Object.assign(document.createElement('small'), { textContent: `${entry.kind} · ${entry.pkg}${parts}` }),
    Object.assign(document.createElement('small'), entry.cover
      ? (entry.cover.type === 'floor'
        ? { textContent: 'Any size: set once placed', title: 'Placed as one tile; its width and length are set in the piece panel' }
        : { textContent: 'Any size and height, high or low: set once placed',
            title: 'Placed as one tile of high cover; its width, length, height and cover are set in the piece panel' })
      : { textContent: `${w} × ${d} × ${h}${entry.floor ? ` · floor, ${tiles(w)} × ${tiles(d)} tiles` : ''}`,
          title: 'Width × depth × height in game units (a floor tile is 96 across)' }));
  const tags = Object.assign(document.createElement('span'), { className: 'tags' });
  // a cover block or invisible floor (app.js coverEntries) is the editor's own piece: none in the map to count
  tags.append(entry.cover
    ? Object.assign(document.createElement('span'), { className: 'tag', textContent: 'Invisible', title: 'Hidden in the game' })
    : Object.assign(document.createElement('span'), { className: 'tag', textContent: `×${entry.count}`,
      title: `${entry.count} in this map` }));
  button.title = entry.title ?? [entry.mesh, ...[...new Set(entry.materials)].map(m => `Material: ${m}`)].join('\n');
  button.append(thumb, label, tags);
  button.onclick = choose;
  button.thumb = thumb;
  return button;
}

/** The panel: filter, kind, where and sort; rows with a thumbnail, name, kind, size and count.
 *  preview(entry) gives a drawn-only copy in the entry's frame (or null); onChoose(entry or null) on a click. */
export function createPieceBrowser({ els, renderer, preview, onChoose }) {
  let entries = null, chosen = null, queue = [];
  const rows = new Map();
  // Thumbnails use the main renderer so they share the view's tone mapping and colour.
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#1f2a33');
  const key = new THREE.DirectionalLight(0xfff4e6, 2.4);
  key.position.set(0.7, 1, 0.9);
  scene.add(new THREE.HemisphereLight(0xdde8f0, 0x4a4540, 2.2), key);
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 10000);
  const view = new THREE.Vector3(1, 0.9, 1.3).normalize();

  function load(list) {
    entries = list;
    setKindOptions(els.kind, entries);
    const roles = [...new Set(entries.filter(e => !e.light && !e.zone && !e.spawnAdd).map(e => e.role))];
    els.where.replaceChildren(new Option('Anywhere', 'all'), ...roles.map(r => new Option(ROLES[r] ?? r, r)));
    els.where.hidden = roles.length < 2;
  }
  function row(entry) {
    if (!rows.has(entry.key)) {
      rows.set(entry.key, pieceRow(entry, renderer.getPixelRatio(), () => onChoose(chosen?.key === entry.key ? null : entry)));
    }
    return rows.get(entry.key);
  }
  function render() {
    if (!entries) return;
    const words = els.filter.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const kind = els.kind.value;
    const shown = entries.filter(e => inKind(e, kind)
      && (els.where.value === 'all' || e.light || e.zone || e.spawnAdd || e.role === els.where.value) && words.every(w => e.text.includes(w)));
    shown.sort(SORTS[els.sort.value]);
    els.list.replaceChildren(...shown.map(row));
    for (const [k, b] of rows) b.classList.toggle('on', k === chosen?.key);
    // pieces and lights counted apart
    const count = (list, what) => list.filter(e => (what === 'light' ? Boolean(e.light) : !e.light && !e.zone && !e.spawnAdd)).length;
    const say = (n, of, what) => (n === of ? `${of} ${what}${of === 1 ? '' : 's'}` : `${n} of ${of} ${what}s`);
    const total = [count(shown, 'piece') && say(count(shown, 'piece'), count(entries, 'piece'), 'piece'),
                   count(shown, 'light') && say(count(shown, 'light'), count(entries, 'light'), 'light')].filter(Boolean).join(' and ');
    els.foot.textContent = shown.length ? `${total} · click one, then click in the view to place it` : 'No piece matches';
    queue = shown.filter(e => !row(e).thumb.dataset.drawn);
  }
  /** Draw pictures ({ object, box, thumb: a canvas } each) as the list's own are drawn; only while a frame is drawn,
   *  before the view. False when the view is too small to draw in. */
  function paintThumbs(jobs) {
    const size = renderer.getSize(new THREE.Vector2()), canvas = renderer.domElement;
    const px = Math.round(THUMB * renderer.getPixelRatio());
    if (size.x < THUMB || size.y < THUMB) return false;
    renderer.setScissorTest(true);
    renderer.setViewport(0, 0, THUMB, THUMB); renderer.setScissor(0, 0, THUMB, THUMB);
    withoutLocalLights(() => {
      for (const { object, box, thumb } of jobs) {
        const sphere = box.getBoundingSphere(new THREE.Sphere()), r = Math.max(sphere.radius, 1);
        const distance = r / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.02;
        camera.position.copy(sphere.center).addScaledVector(view, distance);
        camera.near = Math.max(0.1, distance - r * 1.5); camera.far = distance + r * 1.5;
        camera.lookAt(sphere.center); camera.updateProjectionMatrix();
        scene.add(object); renderer.render(scene, camera); scene.remove(object);
        object.traverse(part => part.isSkinnedMesh && part.skeleton.dispose());
        thumb.getContext('2d').drawImage(canvas, 0, canvas.height - px, px, px, 0, 0, thumb.width, thumb.height);
        thumb.dataset.drawn = '1';
      }
    });
    renderer.setScissorTest(false); renderer.setViewport(0, 0, size.x, size.y);
    return true;
  }
  /** Draw one larger picture (the look picker's, look picker plan P0): `object` framed by `box` into `canvas` at its
   *  own size and shape, lit and seen as the list's pictures are; only while a frame is drawn, before the view. False
   *  when the view is too small to draw in. */
  function paintPicture(object, box, canvas) {
    const size = renderer.getSize(new THREE.Vector2()), target = renderer.domElement, ratio = renderer.getPixelRatio();
    // (the canvas's shape kept: a view smaller than it draws smaller, scaled up)
    const fit = Math.min(1, size.x * ratio / canvas.width, size.y * ratio / canvas.height);
    const w = Math.round(canvas.width / ratio * fit), h = Math.round(canvas.height / ratio * fit);
    if (w < 64 || h < 48) return false;
    const aspect = w / h, fov = camera.fov;
    renderer.setScissorTest(true);
    renderer.setViewport(0, 0, w, h); renderer.setScissor(0, 0, w, h);
    withoutLocalLights(() => {
      const sphere = box.getBoundingSphere(new THREE.Sphere()), r = Math.max(sphere.radius, 1);
      // (the sphere fits the narrower of the two angles)
      const half = Math.min(THREE.MathUtils.degToRad(fov / 2), Math.atan(Math.tan(THREE.MathUtils.degToRad(fov / 2)) * aspect));
      const distance = r / Math.sin(half) * 1.02;
      camera.aspect = aspect;
      camera.position.copy(sphere.center).addScaledVector(view, distance);
      camera.near = Math.max(0.1, distance - r * 1.5); camera.far = distance + r * 1.5;
      camera.lookAt(sphere.center); camera.updateProjectionMatrix();
      scene.add(object); renderer.render(scene, camera); scene.remove(object);
      const pw = Math.round(w * ratio), ph = Math.round(h * ratio);
      canvas.getContext('2d').drawImage(target, 0, target.height - ph, pw, ph, 0, 0, canvas.width, canvas.height);
      camera.aspect = 1; camera.updateProjectionMatrix();
    });
    renderer.setScissorTest(false); renderer.setViewport(0, 0, size.x, size.y);
    return true;
  }
  // Called each frame before the view is drawn.
  function drawThumbs() {
    if (!queue.length || els.panel.hidden) return;
    const size = renderer.getSize(new THREE.Vector2()), jobs = [];
    if (size.x < THUMB || size.y < THUMB) return;
    for (let n = 0; n < 4 && queue.length; n++) {
      const entry = queue.shift(), object = preview(entry);
      if (object) jobs.push({ object, box: entry.box, thumb: row(entry).thumb });
    }
    paintThumbs(jobs);
  }
  els.filter.addEventListener('input', render);
  els.filter.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (els.filter.value) { els.filter.value = ''; render(); } else els.filter.blur();
    e.preventDefault();
  });
  for (const el of [els.kind, els.where, els.sort]) el.addEventListener('change', render);

  return {
    get open() { return !els.panel.hidden; },
    /** Show or hide the panel; collect() gives the entries the first time it opens. */
    show(on, collect) {
      if (on && !entries) load(collect());
      els.panel.hidden = !on;
      if (on) render();
    },
    /** Mark the entry being placed (null: none). */
    setChosen(entry) {
      chosen = entry;
      for (const [k, b] of rows) b.classList.toggle('on', k === entry?.key);
    },
    entries: () => entries ?? [],
    drawThumbs, paintThumbs, paintPicture,
  };
}
