// The looks a made wall, floor or roof slab, or ground shape can take (custom geometry plan, stage M4): any of the
// game's own pieces of that kind, named by their donor. tools/bake/looks.py lists them (GET /looks/walls.json,
// /looks/slabs.json, /looks/ground.json): each its donor's mesh (and a ground look's material), the map and actor of
// the placing it was measured on, the maps it is placed in, a readable name, its setting, what the made piece lacks
// (`warnings`) and the recipe's numbers the page draws by.
//
// A made piece names its look as `look: { mesh, measure }` (a ground look's also `material`) in its request (a wall's
// version 3, a slab's or ground shape's version 2); the copy it is made on is of the donor placing chosen (the
// catalogue's, a library row's, or a piece picked in the view), which the Build clones.

export const LOOK_FILES = { wall: 'walls', slab: 'slabs', ground: 'ground' };
// a made piece's request version once its look is named by its donor
export const DONOR_VERSION = { wall: 3, slab: 2, ground: 2 };

const lists = {}, pending = {};

/** The key a look is listed under: its mesh, a ground look's mesh and material. */
export const lookKey = (kind, mesh, material = null) => (kind === 'ground' ? `${mesh}|${material ?? ''}` : mesh);

/** The kind's catalogue, read once: { kind, measure, looks: [entry], byKey: Map }. */
export function loadLooks(kind, fetcher = fetch) {
  if (lists[kind]) return Promise.resolve(lists[kind]);
  if (!pending[kind]) {
    pending[kind] = fetcher(`/looks/${LOOK_FILES[kind]}.json`)
      .then(r => (r.ok ? r.json() : { looks: [] }))
      .catch(() => ({ looks: [] }))
      .then(answer => {
        const byKey = new Map((answer.looks ?? []).map(e => [lookKey(kind, e.mesh, e.material), e]));
        lists[kind] = { kind, measure: answer.measure ?? null, looks: answer.looks ?? [], byKey };
        delete pending[kind];
        return lists[kind];
      });
  }
  return pending[kind];
}

/** The kind's catalogue if it has been read, else null. */
export const looksLoaded = kind => lists[kind] ?? null;

/** The catalogue entry a donor look ({ mesh, measure, material? }) names, or null (a look id, an unread catalogue, a
 *  donor no catalogue holds). */
export function catalogued(kind, look) {
  if (!look || typeof look !== 'object') return null;
  return lists[kind]?.byKey.get(lookKey(kind, look.mesh, look.material)) ?? null;
}

/** The catalogue entry for a piece of a map: its mesh (and a ground piece's first material), or null. */
export function entryForPiece(kind, mesh, material = null) {
  const list = lists[kind];
  if (!list || !mesh) return null;
  return list.byKey.get(lookKey(kind, mesh, material)) ?? null;
}

/** The request's look for a catalogue entry: { mesh, measure } (a ground look's with its material). */
export function donorLook(kind, entry) {
  const measure = lists[kind]?.measure ?? 1;
  return kind === 'ground' ? { mesh: entry.mesh, material: entry.material, measure } : { mesh: entry.mesh, measure };
}

/** A look the drawing tools take ({ id, name, package, actor, mesh, lwrOnly, words, donor, recipe, warnings }) from a
 *  catalogue entry, its donor placing `source` ({ package, actor }: a library row's, or a piece picked in the view)
 *  or, without one, the placing the catalogue measured. */
export function lookFromEntry(kind, entry, source = null) {
  const pkg = source?.package ?? entry.map, actor = String(source?.actor ?? entry.actor).split('.').at(-1);
  return { id: null, name: entry.name, package: pkg, actor, mesh: entry.mesh, lwrOnly: Boolean(entry.lwrOnly),
           words: lookWords(kind, entry), donor: donorLook(kind, entry), recipe: { ...entry.recipe },
           warnings: [...(entry.warnings ?? [])], setting: entry.setting ?? '', facts: { ...(entry.facts ?? {}) } };
}

/** A look's words for a row's tooltip: its setting, its size and what the made piece lacks. */
export function lookWords(kind, entry) {
  const f = entry.facts ?? {}, size = f.size;
  const parts = [entry.setting || null];
  if (kind === 'wall' && size) parts.push(`${Math.round(size.length)} long and ${Math.round(size.height)} tall in its map`);
  if (kind === 'wall' && f.inside != null) parts.push(f.inside ? 'an inside wall' : 'an outside wall');
  if (kind === 'slab' && f.role) parts.push(f.kind && f.kind !== 'flat' ? `a ${f.kind} ${f.role}, made flat` : `a ${f.role}`);
  if (kind === 'ground' && f.painted) parts.push('painted in its commonest colour');
  return parts.filter(Boolean).join(', ');
}

/** The tags a look's row shows ([text, title]): what the made piece lacks, and whether only Long War Rebalance has it. */
export function lookTags(entry) {
  const tags = [];
  if (entry.warnings?.length) tags.push(['Simpler', `Made simpler than its donor: ${entry.warnings.join('; ')}`]);
  if (entry.lwrOnly) tags.push(['LWR', 'Only Long War Rebalance has this piece: the Build makes it on an install of Long War Rebalance']);
  return tags;
}

/** For the tests: forget what was read. */
export function forgetLooks() { for (const k of Object.keys(lists)) delete lists[k]; }
