// The copy carried to another map or prefab (Discord S17; the editor controls and clipboard plan, Part C): what Ctrl+C
// or Ctrl+X copied, kept by the tab when the page leaves for another map or prefab, so that Ctrl+V there places it.
// It is a prefab's records without the file (prefab_place.js prefabRecords, run on the copy's own pieces): its pieces,
// groups and buildings in prefab_document.js's shapes, on the tile grid's own space (0 is the grid's corner at its
// bottom level), with the copy's pivot in that space; the Buildings view's copy of floor boxes (relative to the tile
// grid's corner) under `boxes`; a landing zone or diagonal cover marks copied (plain data) under `thing`
// ({ kind: 'zone', zone: its fields, its location from the grid's corner } or { kind: 'marks', marks: each one's
// corners and tile from the first one's }). This module is the format's one reader and writer (carried_clip_test.mjs);
// clipboard.js packs it as the page leaves (document_session.js goTo) and reads it on paste.

export const CARRIED_FORMAT = 1;
// The tab's storage key (storage.js rememberSession: kept for the tab alone, while it stays open).
export const CARRIED_KEY = 'workshop.clip';
// The carried copy the tab has said came along (its id): the arrival's hint says it once.
export const CARRIED_TOLD = 'workshop.clipTold';
// The most a carried copy holds, in characters of its text: a tab keeps about five million (its storage's quota), and
// the page keeps a little of its own there. A larger copy is not carried: a prefab is the way for something that large.
export const CARRIED_MAX = 4_000_000;

export const CARRIED_WORDS = {
  arrived: 'The copy came along: Ctrl+V places it here',
  tooLarge: name => `${name ?? 'The copy'} was too large to bring along: save it as a prefab to place it in another map`,
  unread: 'The copy brought from the last map could not be read: copy it again',
  otherFormat: 'The copy brought from the last map was made by another version of the editor: copy it again',
};

const isList = v => Array.isArray(v);
const isPoint = v => isList(v) && v.length === 3 && v.every(Number.isFinite);
// (a landing zone's place: its height may be unset, the ground's then)
const isPlace = v => isList(v) && v.length === 3 && Number.isFinite(v[0]) && Number.isFinite(v[1]) && (v[2] === null || Number.isFinite(v[2]));

/** A copy as the text the tab keeps: { text }, or { tooLarge: text } (a marker, itself small, that says so on arrival)
 *  when its text is over `max` characters. `copy`: { id, from ({ map, prefab, project }: where it was copied), name,
 *  words, pivot (game units, the records' space), pivotActor (the record holding the pivot, or null), pieces, groups,
 *  buildings, donors, left (what won't go, as sentences), boxes (the Buildings view's copy, or none) }. */
export function packCarried(copy, max = CARRIED_MAX) {
  const doc = {
    format: CARRIED_FORMAT, id: copy.id ?? null, from: copy.from ?? {}, name: copy.name ?? 'The copy', words: copy.words ?? '',
    pivot: copy.pivot, pivotActor: copy.pivotActor ?? null, pieces: copy.pieces ?? [], groups: copy.groups ?? [],
    buildings: copy.buildings ?? [], donors: copy.donors ?? [], left: copy.left ?? [], ...(copy.boxes ? { boxes: copy.boxes } : {}),
    ...(copy.thing ? { thing: copy.thing } : {}),
  };
  const text = JSON.stringify(doc);
  if (text.length > max) return { tooLarge: JSON.stringify({ format: CARRIED_FORMAT, id: doc.id, name: doc.name, tooLarge: true }) };
  return { text };
}

/** The tab's carried text read back: { doc }, { tooLarge: name } for a copy that was too large to bring, or
 *  { error: a sentence }; null for none. */
export function unpackCarried(text) {
  if (text == null || text === '') return null;
  let doc;
  try { doc = JSON.parse(text); } catch { return { error: CARRIED_WORDS.unread }; }
  if (!doc || typeof doc !== 'object') return { error: CARRIED_WORDS.unread };
  if (doc.format !== CARRIED_FORMAT) return { error: CARRIED_WORDS.otherFormat };
  if (doc.tooLarge) return { tooLarge: typeof doc.name === 'string' ? doc.name : null, id: doc.id ?? null };
  const lists = ['pieces', 'groups', 'buildings', 'donors', 'left'];
  if (!isPoint(doc.pivot) || lists.some(k => !isList(doc[k])) || (doc.boxes !== undefined && !isList(doc.boxes))) return { error: CARRIED_WORDS.unread };
  const thing = doc.thing;
  if (thing !== undefined && !(thing?.kind === 'zone' ? isPlace(thing.zone?.location) : thing?.kind === 'marks' && isList(thing.marks))) return { error: CARRIED_WORDS.unread };
  return { doc };
}
