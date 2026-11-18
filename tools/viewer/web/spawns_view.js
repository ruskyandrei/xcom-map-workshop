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
// marker opens the inspector (app.js); the stream objects' group gizmo moves them (Part E), the base map's are view
// only until stage SP6. Pure but for the marker shapes, which take three.js as an argument so the node tests load this.

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

/** Where the edit of a base record will come from (SP3: view only until stage SP6). */
export const baseEditWords = 'The Build keeps it where the map has it: base spawn points are edited from a later stage.';

// ---------------------------------------------------------------- markers (three.js passed in)

function shape(THREE, kind) {
  switch (KINDS[kind]?.shape) {
    case 'arrow': return new THREE.ConeGeometry(0.45, 1.1, 10).rotateX(Math.PI).translate(0, 0.55, 0);
    case 'ring': return new THREE.TorusGeometry(0.55, 0.14, 6, 18).rotateX(Math.PI / 2);
    case 'gem': return new THREE.OctahedronGeometry(0.6);
    case 'diamond': return new THREE.OctahedronGeometry(0.32);
    case 'cube': return new THREE.BoxGeometry(0.6, 0.6, 0.6);
    default: return new THREE.SphereGeometry(0.4, 12, 8);
  }
}

/** A marker: a solid shape, and the same faint over everything, so it shows through walls. readOnly (a patch's): drawn
 * paler. */
export function makeSpawnMarker(THREE, kind, readOnly = false) {
  const colour = new THREE.Color(KINDS[kind]?.colour ?? 0xffffff);
  if (readOnly) colour.lerp(new THREE.Color(0x808080), 0.5);
  const solid = new THREE.MeshBasicMaterial({ color: colour });
  const ghost = new THREE.MeshBasicMaterial({ color: colour, transparent: true, opacity: 0.3, depthTest: false, depthWrite: false });
  const geometry = shape(THREE, kind), marker = new THREE.Group();
  const front = new THREE.Mesh(geometry, solid), behind = new THREE.Mesh(geometry, ghost);
  behind.renderOrder = 6;
  for (const m of [front, behind]) { m.raycast = () => {}; marker.add(m); }
  marker.userData = { front, behind, solid, ghost, colour };
  return marker;
}

/** A marker brighter while its record is picked. */
export function paintSpawnMarker(THREE, marker, picked) {
  const { solid, ghost, colour } = marker.userData;
  const c = colour.clone();
  if (picked) c.lerp(new THREE.Color(0xffffff), 0.45);
  solid.color.copy(c); ghost.color.copy(c); ghost.opacity = picked ? 0.6 : 0.3;
}
