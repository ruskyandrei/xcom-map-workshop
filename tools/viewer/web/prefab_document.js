// Shared document operations. Working coordinates never move; only a serialized copy
// is normalized. Unknown geometry keeps its previous envelope.
// Heights (prefab plan 5.6b, prefab_bounds.py; 30 levels since 14 November 2026): the grid is 30 levels of 64 from the
// prefab's ground (the game's own maps go to 18: the test stage's least height), and anything may stick out 192
// units under or over it (a hull, a roof, floor boxes, lights), with no tiles there. The limits warn and refuse
// nothing (measurePrefab's `warnings`; `errors` stays empty and `supported` true for the callers that read them).
export const PREFAB_GRID_LEVELS = 30, PREFAB_PLAYED_LEVELS = 18;
// (the largest map the editor makes, project.js STAGE_GRID_MAX: 256 tiles a side since 16 November 2026, 128 before)
export const PREFAB_TILES = 256, PREFAB_SLACK = 0.5, PREFAB_GRID_TOP = PREFAB_GRID_LEVELS * 64, PREFAB_ALLOWANCE = 192;
export const PREFAB_PLAYED_TOP = PREFAB_PLAYED_LEVELS * 64;
export const PREFAB_MIN_Z = -PREFAB_ALLOWANCE, PREFAB_MAX_Z = PREFAB_GRID_TOP + PREFAB_ALLOWANCE;
export function measurePrefab(boxes, unknown = []) {
  const bounds = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity], offenders = [], outside = [];
  for (const [name, b] of boxes) {
    for (let k = 0; k < 3; k++) { bounds[k] = Math.min(bounds[k], b[k]); bounds[k + 3] = Math.max(bounds[k + 3], b[k + 3]); }
    if (b[2] < PREFAB_MIN_Z - PREFAB_SLACK || b[5] > PREFAB_MAX_Z + PREFAB_SLACK) offenders.push(name);
    else if ((b[2] < -PREFAB_SLACK || b[5] > PREFAB_GRID_TOP + PREFAB_SLACK) && !outside.includes(name)) outside.push(name);
  }
  if (!boxes.length) bounds.fill(0);
  const origin = [0, 1].map(k => Math.floor((bounds[k] + PREFAB_SLACK) / 96) * 96).concat(0);
  const tiles = [0, 1].map(k => Math.max(1, Math.ceil((bounds[k + 3] - origin[k] - PREFAB_SLACK) / 96)));
  const warnings = [];
  if (Math.max(...tiles) > PREFAB_TILES) warnings.push(`${tiles[0]} by ${tiles[1]} tiles is over ${PREFAB_TILES} by ${PREFAB_TILES} tiles, the largest map the editor makes: no map holds it whole, and it can't be tested on the stage`);
  if (offenders.length) warnings.push(`height ${bounds[2].toFixed(1)} to ${bounds[5].toFixed(1)} reaches past ${PREFAB_MIN_Z} to ${PREFAB_MAX_Z} units, where a map has no tiles: ${[...new Set(offenders)].slice(0, 8).join(', ')}`);
  return { bounds, tiles, origin, unknown, errors: [], warnings, supported: true, verified: !unknown.length, outside,
           tall: bounds[5] > PREFAB_PLAYED_TOP + PREFAB_SLACK };
}
export function normalizePrefab(records, boxes, { ground = 0, envelope = null, unknown = [] } = {}) {
  const shifted = boxes.map(([name, b]) => [name, b.map((v, k) => v - (k % 3 === 2 ? ground : 0))]);
  if (envelope) shifted.push(['Unresolved footprint', [...envelope]]);
  const size = measurePrefab(shifted, unknown), origin = [...size.origin]; origin[2] = ground;
  const here = p => p.map((v, k) => Number((v - origin[k % 3]).toFixed(4)));
  return { ...records, tiles: size.tiles, pieces: records.pieces.map(p => ({ ...p, location: here(p.location) })),
    buildings: records.buildings.map(b => ({ ...b, floors: b.floors.map(f => ({ boxes: f.boxes.map(here).sort() })) })), size, origin };
}
// Reconcile intentional deletion, keeping unreadable records in the reference graph.
export function reconcilePrefab(pieces, buildings, groups) {
  const actors = new Set(pieces.map(p => p.actor)), ids = new Set(buildings.map(b => b.id));
  const tree = new Map(groups.map(g => [g.id, { id: g.id, breakTogether: g.breakTogether === true,
    members: g.members.filter(m => m.group !== undefined || (m.added !== undefined ? actors.has(m.added) : ids.has(m.building))) }]));
  for (let changed = true; changed;) {
    changed = false;
    for (const [id, g] of tree) {
      g.members = g.members.filter(m => m.group === undefined || tree.has(m.group));
      if (g.members.length >= 2) continue;
      tree.delete(id); changed = true;
      for (const parent of tree.values()) parent.members = parent.members.flatMap(m => m.group === id ? g.members : [m]);
    }
  }
  return { pieces: pieces.map(p => p.from ? { ...p, partner: actors.has(p.partner) ? p.partner : null } : p), groups: [...tree.values()] };
}
export function orderedWrites() {
  let tail = Promise.resolve();
  return { run(task) { const result = tail.then(task); tail = result.catch(() => {}); return result; }, wait: () => tail };
}
export function emptyPrefabScene() {
  return { name: 'Prefab', scope: 'map', prefabWorkspace: true, exporterVersion: 999, source: { file: '' }, objects: [], meshes: {}, materials: {}, textures: {},
    lights: [], lightMetadata: {}, buildings: [], diagnostics: [], counts: { meshes: 0, textures: 0 },
    tileGrid: { origin: [0, 0, 0], size: [96, 96, 64], dimensions: [128, 128, PREFAB_GRID_LEVELS] } };
}
