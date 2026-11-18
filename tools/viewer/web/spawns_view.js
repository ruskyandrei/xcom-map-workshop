// Spawn points and mission objectives in the view (private/plans/todo/editor-spawns-implementation-plan.md, SP3; it
// took over mission_view.js, mission types plan C2): one list of records that both the Spawns view (Shift+U, the rail's
// button) and the Normal button's "Spawn points and objectives" switch draw, each a marker one size on screen and faint
// through walls, as lights' are. The records:
// - the base map's spawn points (export 33: scene.json `spawns`), but those of a landing (its zone stands for them);
// - the objects of the streams the header's mission streams (export 24: streams[<name>].missionObjects);
// - for a kind the project adds with a donor stream (the council bomb), the donor's objects (scene.json `donors`),
//   unless a stream of the mission is the donor itself;
// - an LWR patch's spawn points (streams[<name>].spawns), read only, with the layer's name.
// One marker an actor: a bomb's button, floor marker, emitters and helper point stay in the inspector. A click on a
// marker opens the inspector (app.js); the stream objects' group gizmo moves them (Part E), and the base map's pods,
// Meld points and drop-in points move, turn and take values where the spawn family builds (SP6: editSpawn). Pure but
// for the marker shapes, which take three.js as an argument so the node tests load this.

// kind -> what it is called, its colour, its marker's shape and the flyout family it shows under
export const KINDS = {
  pod: { label: 'Pod', colour: 0xff9f43, shape: 'ring', family: 'pods' },
  meld: { label: 'Meld point', colour: 0x20bf6b, shape: 'dot', family: 'meld' },
  dropIn: { label: 'Drop-in point', colour: 0xff6b6b, shape: 'arrow', family: 'dropIns' },
  landing: { label: 'Landing', colour: 0x4dd0e1, shape: 'dot', family: 'soldiers' },
  start: { label: 'Player start', colour: 0x4dd0e1, shape: 'dot', family: 'soldiers' },
  soldier: { label: 'Soldier\'s point', colour: 0x4dd0e1, shape: 'dot', family: 'soldiers' },
  bomb: { label: 'The bomb', colour: 0xeb3b5a, shape: 'gem', family: 'objectives' },
  powerNode: { label: 'Power node', colour: 0xfa8231, shape: 'gem', family: 'objectives' },
  capturePoint: { label: 'Capture point', colour: 0xa55eea, shape: 'gem', family: 'objectives' },
  radar: { label: 'Radar array', colour: 0xa55eea, shape: 'gem', family: 'objectives' },
  use: { label: 'Thing to use', colour: 0x45aaf2, shape: 'gem', family: 'objectives' },
  operative: { label: 'Covert operative\'s point', colour: 0x26de81, shape: 'dot', family: 'other' },
  vip: { label: 'VIP\'s point', colour: 0x26de81, shape: 'dot', family: 'other' },
  loot: { label: 'Loot point', colour: 0xfed330, shape: 'dot', family: 'other' },
  point: { label: 'Point', colour: 0xb8c4cc, shape: 'dot', family: 'other' },
  noSpawn: { label: 'No-spawn volume', colour: 0x8a94a6, shape: 'cube', family: 'other' },
  pathNode: { label: 'Patrol node', colour: 0xd1a054, shape: 'diamond', family: 'paths' },
};
// the flyout's families, in order, with whether each shows when nothing is saved (patrol nodes start off)
export const FAMILIES = [
  { id: 'pods', label: 'Pods', on: true }, { id: 'meld', label: 'Meld', on: true },
  { id: 'dropIns', label: 'Drop-in points', on: true }, { id: 'soldiers', label: 'Soldier and start points', on: true },
  { id: 'objectives', label: 'Objectives', on: true }, { id: 'other', label: 'Other points and volumes', on: true },
  { id: 'paths', label: 'Patrol nodes', on: false },
];
const HELPER_ROLES = ['effect', 'rebuild', 'visible', 'waypoint', 'point'];
const ROLE_WORDS = { bomb: 'the bomb', button: 'its button', waypoint: 'its floor marker', effect: 'an effect', rebuild: 'its rebuild volume',
                     visible: 'its visible point', point: 'its helper point (the arrow\'s and camera\'s)', node: 'the node',
                     volume: 'the capture volume', captured: 'the actor it captures', actor: 'a capture actor' };
const GROUP_WORDS = g => (g === 'bomb' ? 'the bomb' : g.startsWith('node:') ? `power node ${g.slice(5)}` : g.startsWith('capture:') ? `capture point ${g.slice(8)}` : g);
const short = path => String(path ?? '').split('.').pop();

/** Whether a record gets a marker: its kind is one of KINDS, and it isn't a group's helper part. */
export const marked = o => Boolean(KINDS[o?.kind]) && !HELPER_ROLES.includes(o.role);
/** A record's flyout family. */
export const familyOf = o => KINDS[o?.kind]?.family ?? 'other';

/** An entry's key: `<stream or "base">|<actor>` (the stream's name for stream, donor and patch records). */
export const spawnKey = (stream, actor) => `${stream ?? 'base'}|${actor}`;

/** The records both controls draw, as entries {key, layer: 'base' | 'stream' | 'donor' | 'patch', stream, record,
 * readOnly}. data: the export; streams: the header mission's streams (a Set or an array); donor: an added kind's
 * donor ({kind, stream, missionObjects}: data.donors[kind] with its kind) or null. */
export function spawnRecords(data, streams, donor = null) {
  const out = [], set = new Set(streams ?? []);
  for (const r of data?.spawns ?? []) if (!r.landing) out.push({ key: spawnKey(null, r.actor), layer: 'base', stream: null, record: r, readOnly: false });
  for (const name of set) {
    const s = data?.streams?.[name];
    if (!s) continue;
    for (const o of s.missionObjects ?? []) out.push({ key: spawnKey(name, o.actor), layer: 'stream', stream: name, record: o, readOnly: false });
    if (s.kind === 'lwr') for (const r of s.spawns ?? []) out.push({ key: spawnKey(name, r.actor), layer: 'patch', stream: name, record: r, readOnly: true });
  }
  if (donor?.stream && !set.has(donor.stream))
    for (const o of donor.missionObjects ?? []) out.push({ key: spawnKey(donor.stream, o.actor), layer: 'donor', stream: donor.stream, record: o, readOnly: false, donor: donor.kind });
  return out;
}

/** The entries a control draws: marked ones whose family is on (filters: {family: bool}, a missing family as FAMILIES
 * says). */
export function shownEntries(entries, filters = {}) {
  const on = f => (f in filters ? filters[f] !== false : FAMILIES.find(x => x.id === f)?.on !== false);
  return entries.filter(e => marked(e.record) && on(familyOf(e.record)));
}

/** The entries of an entry's group in the same layer (itself alone when it has none). */
export function groupOf(entry, entries) {
  const g = entry.record.group;
  return g ? entries.filter(e => e.stream === entry.stream && e.layer === entry.layer && e.record.group === g) : [entry];
}

/** The panel's title: "Pod 2 of 5", with the mission or the layer. */
export function titleOf(entry, entries, missionLabel) {
  const o = entry.record;
  const same = entries.filter(e => e.layer === entry.layer && e.stream === entry.stream && e.record.kind === o.kind && marked(e.record)
    && (o.kind !== 'capturePoint' || e.record.role === o.role));
  const k = same.findIndex(e => e.key === entry.key), label = KINDS[o.kind]?.label ?? o.kind;
  const where = entry.layer === 'base' ? '' : entry.layer === 'patch' ? `, ${entry.stream} (Long War's patch)`
    : entry.layer === 'donor' ? `, ${missionLabel ?? 'the added mission'} (from ${entry.stream})` : missionLabel ? `, ${missionLabel}` : '';
  return `${label}${same.length > 1 && k >= 0 ? ` ${k + 1} of ${same.length}` : ''}${where}`;
}

/** The record's identity line and its values: [{head, text}] sections 1-3 of the inspector (SP3): the actor, class and
 * archetype ("not in the level's list" where it isn't); its values with where each comes from; its group. fromWords:
 * spawn_rules.js's. */
export function identityLines(entry, entries, fromWords = () => '') {
  const o = entry.record, out = [];
  out.push({ text: `${short(o.actor)} (${o.actorClass}${o.archetype ? `, ${o.archetype}` : ''})${o.listed === false ? ': not in the level\'s list, so the game never places it' : ''}.` });
  if (o.unread) out.push({ text: `Its values could not be read (${o.unread}).` });
  const values = Object.entries(o.values ?? {});
  if (values.length) out.push({ head: 'Values', text: values.map(([k, v]) => `${VALUE_WORDS[k] ?? k} ${valueText(v.value)} ${fromWords(v.from)}`.trim()).join('; ') + '.' });
  if (o.other?.length) out.push({ text: `It also saves ${o.other.join(', ')}.` });
  if (o.group) {
    const members = groupOf(entry, entries).filter(e => e.key !== entry.key).map(e => ROLE_WORDS[e.record.role] ?? e.record.role);
    out.push({ head: 'Group', text: `Part of ${GROUP_WORDS(o.group)} (${ROLE_WORDS[o.role] ?? o.role}); it moves with ${members.length ? [...new Set(members)].join(', ') : 'nothing else'}.` });
  }
  return out;
}
const VALUE_WORDS = { podIndex: 'pod index', commander: 'commander', secondary: 'secondary', use: 'use', numAliens: 'aliens', aliensMin: 'aliens at least',
                      aliensMax: 'aliens at most', podGroup: 'pod group', forceType: 'forced type', alienType: 'alien type',
                      triggerOnView: 'starts when seen', neverActivate: 'never activates', difficulty: 'difficulty',
                      destroyedOnTurn: 'destroyed on turn', spawnGroup: 'spawn group', countdownWhenSeen: 'countdown when seen',
                      behaviour: 'behaviour', forcePlacement: 'forced placement', kismetOnly: 'script only', seekRadius: 'seek radius',
                      unitType: 'unit type' };
const valueText = v => (v === true ? 'yes' : v === false ? 'no' : v === null || v === undefined ? 'none' : String(v).replace(/^ePawnType_|^UNIT_TYPE_/, ''));

/** What the panel says of a record ({title, lines}): the title and the lines of the old mission panel, for the build
 * window's warnings and the tests. */
export function describe(entry, entries, missionLabel) {
  const o = entry.record, lines = identityLines(entry, entries).map(l => l.text);
  lines.push(o.referencedBy?.length ? `Listed by ${o.referencedBy.slice(0, 6).join('; ')}${o.referencedBy.length > 6 ? `; and ${o.referencedBy.length - 6} more` : ''}.`
    : `Nothing in ${entry.layer === 'base' ? 'the map' : 'the stream'} lists it by name.`);
  return { title: titleOf(entry, entries, missionLabel), lines };
}

/** What the panel says of a base record the project can't edit: one of a kind the editor shows only, or a pod, Meld
 * point or drop-in point where the spawn family doesn't build (SP6). */
export const baseEditWords = 'The Build keeps it where the map has it.';

// ---------------------------------------------------------------- base spawn point edits (SP6)

/** The kinds of base spawn point a project moves, turns and gives values (compiler.SPAWN_EDIT_KINDS), and the values
 * of each (compiler.SPAWN_VALUE_KEYS). */
export const SPAWN_EDIT_KINDS = ['pod', 'meld', 'dropIn'];
export const SPAWN_VALUE_KEYS = { pod: ['commander', 'secondary', 'use'], meld: ['difficulty', 'destroyedOnTurn', 'spawnGroup'], dropIn: [] };
/** Whether a base record is one the Build can edit: its kind, in the level's actor list, its values read. */
export const spawnEditable = o => SPAWN_EDIT_KINDS.includes(o?.kind) && o.listed !== false && !o.unread;
// a yaw (rotation units, 65536 a turn) within half a turn of another
const yawNear = (yaw, base) => { let d = ((yaw - base) % 65536 + 65536) % 65536; if (d > 32768) d -= 65536; return base + d; };
const rotationOf = o => (o.rotation ?? [0, 0, 0]).map(v => Math.round(v));
/** Whether an edit stands or faces otherwise than its record. */
export const spawnPosed = (entry, o) => !(entry.location.every((v, i) => Math.abs(v - o.location[i]) < 1e-3)
  && entry.rotation.every((v, i) => v === rotationOf(o)[i]));
/** A base spawn point's edit after a change: moved by `delta` (game units), turned by `turn` (rotation units; its yaw
 * kept within half a turn of the map's, so four quarter turns bring it back), `spawn` values merged (a key set to
 * undefined, or to the map's value, goes back to the map's). entry: its edit before ({stream: null, actor, location,
 * rotation, spawn}) or null. Returns the edit, or null when it is back where and as the map has it. */
export function editSpawn(o, entry, { delta = [0, 0, 0], turn = 0, spawn = null } = {}) {
  const was = entry ?? { location: [...o.location], rotation: rotationOf(o), spawn: {} };
  const location = was.location.map((v, i) => Math.round((v + delta[i]) * 1000) / 1000);
  const rotation = [was.rotation[0], yawNear(was.rotation[1] + turn, rotationOf(o)[1]), was.rotation[2]];
  const values = { ...(was.spawn ?? {}) };
  for (const [key, v] of Object.entries(spawn ?? {})) {
    if (v === undefined || v === o.values?.[key]?.value) delete values[key]; else values[key] = v;
  }
  const next = { stream: null, actor: o.actor, location, rotation, spawn: values };
  return spawnPosed(next, o) || Object.keys(values).length ? next : null;
}
/** A base spawn point's override (the project's `overrides` record, compiler.spawn_override): its pose only where it
 * moved or turned, its values where it has any. pkg: the map's package (the export's name). */
export function spawnOverride(pkg, o, entry) {
  const out = { target: { package: pkg, level: 'base', actor: entry.actor } };
  if (entry.deleted) return { ...out, deleted: true };
  if (!o || spawnPosed(entry, o)) Object.assign(out, { location: [...entry.location], rotation: [...entry.rotation] });
  if (Object.keys(entry.spawn ?? {}).length) out.spawn = { ...entry.spawn };
  return out;
}
/** A saved override's edit of base record `o`, or null when the page doesn't take it (it is then carried and saved
 * back unchanged): a record of a kind it edits with a whole pose or values or both, and only the values of its kind;
 * or its delete (SP7: `deleted: true` alone). */
export function spawnEntryOf(o, record) {
  if (spawnEditable(o) && record.deleted === true && Object.keys(record).every(k => ['target', 'deleted'].includes(k)))
    return { stream: null, actor: o.actor, location: [...o.location], rotation: rotationOf(o), spawn: {}, deleted: true };
  if (!spawnEditable(o) || Object.keys(record).some(k => !['target', 'location', 'rotation', 'spawn'].includes(k))) return null;
  const posed = Array.isArray(record.location) && record.location.length === 3 && record.location.every(Number.isFinite)
    && Array.isArray(record.rotation) && record.rotation.length === 3 && record.rotation.every(Number.isFinite);
  if (!posed && (record.location !== undefined || record.rotation !== undefined)) return null;
  const values = record.spawn;
  if (values !== undefined && (!values || typeof values !== 'object' || Array.isArray(values)
    || Object.keys(values).some(k => !SPAWN_VALUE_KEYS[o.kind].includes(k)))) return null;
  if (!posed && !values) return null;
  return { stream: null, actor: o.actor, location: posed ? [...record.location] : [...o.location],
           rotation: posed ? record.rotation.map(v => Math.round(v)) : rotationOf(o), spawn: { ...(values ?? {}) } };
}
// ---------------------------------------------------------------- base spawn point copies (SP7)

/** The kinds a project copies (compiler.SPAWN_COPY_KINDS). */
export const SPAWN_COPY_KINDS = ['pod', 'meld'];
const shortName = a => String(a ?? '').split('.').pop();
/** Why a base record can't be copied ('' when it can): a copy is made only from a plain pod (no commander or secondary
 * flag, no forced type, no link to another actor) or any Meld point, in the level's list with its values read. */
export function copyTemplateWhy(o) {
  if (!SPAWN_COPY_KINDS.includes(o?.kind)) return o?.kind === 'dropIn' ? 'drop-in points are moved, not copied' : 'only pods and Meld points are copied';
  if (o.listed === false) return 'it is not in the level\'s list';
  if (o.unread) return 'its values could not be read';
  if (o.kind !== 'pod') return '';
  const v = k => o.values?.[k]?.value;
  const why = [v('commander') && 'the commander\'s place', v('secondary') && 'a secondary pod', v('forceType') && 'of a forced alien type',
               o.links?.length && `linked to ${o.links.map(l => shortName(l.actor)).join(', ')}`].filter(Boolean);
  return why.length ? `it is ${why.join(' and ')}: a copy is made only from a plain pod` : '';
}
/** The base spawn point a new one of `kind` from the Add panel is a copy of (its Spawn points kind: a Pod, a Meld
 * point): the map's first that copyTemplateWhy lets be copied (a plain pod, any listed Meld point), or null. `records`:
 * the export's spawns (a landing's points are never one). */
export function addTemplate(records, kind) {
  if (!SPAWN_COPY_KINDS.includes(kind)) return null;
  return (records ?? []).find(o => o.kind === kind && !o.landing && !copyTemplateWhy(o)) ?? null;
}
/** Where a new spawn point placed at game point `at` (the click's, on the floor under it) stands: on the tile under
 * the click by whole tiles from its template (so it keeps the template's place within a tile), at the template's
 * height above its own floor (`templateFloor`, `floor`: the surface under each; null where none is found). */
export function addPlace(template, at, floor, templateFloor) {
  const [tx, ty, tz] = template.location;
  const over = templateFloor == null ? 0 : Math.min(Math.max(tz - templateFloor, 0), 128);
  const x = tx + Math.round((at[0] - tx) / 96) * 96, y = ty + Math.round((at[1] - ty) / 96) * 96;
  return [x, y, Math.round((floor ?? at[2]) + over)];
}
/** A copy's entry ({stream: 'copy', copy: {id, kind, from}, actor, location, rotation, spawn}: kept as
 * `copy|${actor}`) of template `o`. */
export const copyEntry = (o, { id, actor, location, rotation, spawn = {} }) =>
  ({ stream: 'copy', copy: { id, kind: o.kind, from: o.actor }, actor, location: [...location], rotation: [...rotation], spawn: { ...spawn } });
/** A copy's added record (compiler.spawn_add's): pkg the map's package. */
export function copyRecord(pkg, entry) {
  return { id: entry.copy.id, kind: entry.copy.kind, actor: entry.actor, from: { package: pkg, level: 'base', actor: entry.copy.from },
           location: [...entry.location], rotation: [...entry.rotation], ...(Object.keys(entry.spawn).length ? { spawn: { ...entry.spawn } } : {}) };
}
/** A saved copy's entry, or null when the page doesn't take it (carried back unchanged): its template `o` of the same
 * kind and copyable, an id, a name, a whole pose and only its kind's values. */
export function copyEntryOf(o, record) {
  const finite = v => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite);
  if (!o || o.kind !== record.kind || copyTemplateWhy(o) || typeof record.id !== 'string' || !record.id || typeof record.actor !== 'string'
    || !finite(record.location) || !finite(record.rotation)
    || Object.keys(record).some(k => !['id', 'kind', 'actor', 'from', 'location', 'rotation', 'spawn'].includes(k))) return null;
  const values = record.spawn;
  if (values !== undefined && (!values || typeof values !== 'object' || Array.isArray(values)
    || Object.keys(values).some(k => !SPAWN_VALUE_KEYS[o.kind].includes(k)))) return null;
  return copyEntry(o, { id: record.id, actor: record.actor, location: record.location, rotation: record.rotation.map(v => Math.round(v)), spawn: values ?? {} });
}
/** A copy's entry after a change: moved by `delta`, turned by `turn` (its yaw within half a turn of its template's),
 * `spawn` values merged (one set to its template's value, or undefined, goes back to the template's). */
export function editCopy(o, entry, { delta = [0, 0, 0], turn = 0, spawn = null } = {}) {
  const values = { ...entry.spawn };
  for (const [key, v] of Object.entries(spawn ?? {})) {
    if (v === undefined || v === o.values?.[key]?.value) delete values[key]; else values[key] = v;
  }
  return { ...entry, location: entry.location.map((v, i) => Math.round((v + delta[i]) * 1000) / 1000),
           rotation: [entry.rotation[0], yawNear(entry.rotation[1] + turn, rotationOf(o)[1]), entry.rotation[2]], spawn: values };
}
/** The record a copy's marker and panel show: its template's under the copy's name, at its place, with its values
 * (the project's marked so), named and used by nothing, linked to nothing. */
export function copyMarkerRecord(o, entry) {
  // (what the template saves is the copy's as its template's)
  const own = Object.fromEntries(Object.entries(o.values ?? {}).map(([k, v]) => [k, v.from === 'saved' ? { ...v, from: 'template' } : v]));
  return { ...o, actor: entry.actor, location: [...entry.location], rotation: [...entry.rotation], savesRotation: true,
           values: { ...own, ...Object.fromEntries(Object.entries(entry.spawn).map(([k, v]) => [k, { value: v, from: 'project' }])),
                     ...(o.kind === 'pod' ? { podIndex: { value: 'its own', from: 'project' } } : {}) },
           uses: [], links: [], referencedBy: [], other: [], copyOf: o.actor };
}
/** Whether something names a base record (export 33's uses and the names listing it), as compiler.spawn_names reads
 * it: a delete of it is kept back. */
export const spawnNamed = o => Boolean(o?.uses?.length || o?.referencedBy?.length || o?.unread);

/** The panel's words for an edit's move and turn ("" when it stands as the map has it). */
export function spawnMoveWords(o, entry) {
  if (!entry || !spawnPosed(entry, o)) return '';
  const d = entry.location.map((v, i) => v - o.location[i]), levels = Math.abs(Math.round(d[2] / 64));
  const tiles = Math.round(Math.hypot(d[0], d[1]) / 96), quarters = Math.round((entry.rotation[1] - rotationOf(o)[1]) / 16384);
  const parts = [];
  if (tiles) parts.push(`moved ${tiles} ${tiles === 1 ? 'tile' : 'tiles'} across`);
  if (levels) parts.push(`${parts.length ? '' : 'moved '}${levels} ${levels === 1 ? 'level' : 'levels'} ${d[2] > 0 ? 'up' : 'down'}`);
  if (quarters) parts.push(`turned ${Math.abs(quarters) === 2 ? 'half a turn' : `a quarter ${quarters > 0 ? 'right' : 'left'}`}`);
  else if (entry.rotation[1] !== rotationOf(o)[1]) parts.push('turned');
  if (!parts.length) parts.push('moved less than a tile');
  const text = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0];
  return `${text[0].toUpperCase()}${text.slice(1)} from where the map has it.`;
}

// ---------------------------------------------------------------- markers (three.js passed in)

// A spawn marker's size against a light's (both one size on screen, lights_view.js scaleMarker): larger, as the user
// found the small ones hard to see (18 November 2026)
export const SPAWN_MARKER_SIZE = 1.7;
// how strongly a marker shows through walls, and its halo, plain and picked
const GHOST = { plain: 0.5, picked: 0.8 }, HALO = { plain: 0.75, picked: 1, pale: 0.4 };

function shape(THREE, kind) {
  switch (KINDS[kind]?.shape) {
    case 'arrow': return new THREE.ConeGeometry(0.45, 1.1, 10).rotateX(Math.PI).translate(0, 0.55, 0);
    case 'ring': return new THREE.TorusGeometry(0.55, 0.14, 6, 18).rotateX(Math.PI / 2);
    case 'gem': return new THREE.OctahedronGeometry(0.6);
    case 'diamond': return new THREE.OctahedronGeometry(0.32);
    case 'cube': return new THREE.BoxGeometry(0.6, 0.6, 0.6);
    default: return new THREE.SphereGeometry(0.5, 12, 8);
  }
}

// The halo every marker stands in: a ring of its colour with a dark edge, clear in the middle so the shape shows, drawn
// over everything and facing the camera, so a marker stands out from bright floors and dark rooms alike. One texture
// for all (white, tinted by each marker's colour; the dark edge stays dark).
let haloMap = null;
function haloTexture(THREE) {
  if (haloMap || typeof document === 'undefined') return haloMap;
  const size = 64, c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d'), mid = size / 2;
  const glow = g.createRadialGradient(mid, mid, 0, mid, mid, mid);
  glow.addColorStop(0, 'rgba(255,255,255,0)'); glow.addColorStop(0.5, 'rgba(255,255,255,0)');
  glow.addColorStop(0.72, 'rgba(255,255,255,0.85)'); glow.addColorStop(0.86, 'rgba(255,255,255,0.35)');
  glow.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = glow; g.fillRect(0, 0, size, size);
  g.beginPath(); g.arc(mid, mid, size * 0.43, 0, Math.PI * 2);
  g.strokeStyle = 'rgba(0,0,0,0.9)'; g.lineWidth = 3; g.stroke();
  haloMap = new THREE.CanvasTexture(c);
  return haloMap;
}

/** A marker: a solid shape, the same fainter over everything (so it shows through walls), and a halo of its colour
 * round it. readOnly (a patch's, a deleted point): drawn paler. */
export function makeSpawnMarker(THREE, kind, readOnly = false) {
  const colour = new THREE.Color(KINDS[kind]?.colour ?? 0xffffff);
  if (readOnly) colour.lerp(new THREE.Color(0x808080), 0.5);
  const solid = new THREE.MeshBasicMaterial({ color: colour });
  const ghost = new THREE.MeshBasicMaterial({ color: colour, transparent: true, opacity: GHOST.plain, depthTest: false, depthWrite: false });
  const geometry = shape(THREE, kind), marker = new THREE.Group();
  const front = new THREE.Mesh(geometry, solid), behind = new THREE.Mesh(geometry, ghost);
  behind.renderOrder = 6;
  for (const m of [front, behind]) { m.raycast = () => {}; marker.add(m); }
  let halo = null;
  const map = haloTexture(THREE);
  if (map) {
    halo = new THREE.Sprite(new THREE.SpriteMaterial({ map, color: colour, transparent: true, opacity: readOnly ? HALO.pale : HALO.plain,
                                                        depthTest: false, depthWrite: false }));
    halo.scale.set(2.6, 2.6, 1);
    halo.renderOrder = 5;
    halo.raycast = () => {};
    marker.add(halo);
  }
  marker.userData = { front, behind, solid, ghost, halo, colour, readOnly };
  return marker;
}

/** A pointer on a marker showing the way its point faces (yaw in rotation units: 0 along the game's x, a quarter turn
 * along its y), in the marker's colours. */
export function addFacingPointer(THREE, marker, yaw) {
  const a = yaw / 65536 * Math.PI * 2;
  // (the view's basis is x, up, y: the game's direction (cos a, sin a) is the view's (cos a, 0, sin a))
  const geometry = new THREE.ConeGeometry(0.26, 0.9, 10).rotateZ(-Math.PI / 2).translate(1.15, 0, 0).rotateY(-a);
  const { solid, ghost } = marker.userData;
  const front = new THREE.Mesh(geometry, solid), behind = new THREE.Mesh(geometry, ghost);
  behind.renderOrder = 6;
  for (const m of [front, behind]) { m.raycast = () => {}; marker.add(m); }
}

/** A marker brighter while its record is picked. */
export function paintSpawnMarker(THREE, marker, picked) {
  const { solid, ghost, halo, colour, readOnly } = marker.userData;
  const c = colour.clone();
  if (picked) c.lerp(new THREE.Color(0xffffff), 0.45);
  solid.color.copy(c); ghost.color.copy(c); ghost.opacity = picked ? GHOST.picked : GHOST.plain;
  if (halo) {
    halo.material.color.copy(c);
    halo.material.opacity = picked ? HALO.picked : readOnly ? HALO.pale : HALO.plain;
    halo.scale.setScalar(picked ? 3.1 : 2.6);
  }
}
