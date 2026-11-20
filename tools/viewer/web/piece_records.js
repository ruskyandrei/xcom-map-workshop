// A copied piece's record (review finding 6): one conversion between a piece as the page holds it and the record a
// project, a prefab and the clipboard keep of it, so a piece is the same piece after a copy and paste, a project saved
// and opened, a prefab saved from a selection, the prefab builder's document and a prefab placed (stamped).
//
// A piece's state is what it is beyond its names and place: { tinted, flags, generated, blasts, breaksFurther }.
// - tinted: a copy of a spawned preview piece keeps its tint.
// - flags: its piece flags (piece_flags.js).
// - generated: a piece made from numbers (a drawn wall, floor or roof, or ground shape: custom geometry plan); a made
//   piece's own blasts are inside it (generated.blasts, generated.breaksFurther).
// - blasts, breaksFurther: a copy of one of the map's fracturing pieces, broken (custom geometry editing plan, E6).
// Nothing here knows three.js or the page: app.js reads a state from a root (stateOfRoot), writes it into a record
// (recordFields) and makes a piece of a record's (stateOf, whose keys are addedObject's options).

/** The fields of a copied piece's record (a project's added record, a prefab's piece) this editor reads and writes;
 * any other is a newer editor's, carried as the file has it (the builder's document, prefabs.py `carried`). */
export const PIECE_FIELDS = new Set(['actor', 'from', 'components', 'location', 'rotation', 'prefab', 'partner', 'tinted',
  'recipe', 'template', 'light', 'cover', 'id', 'flags', 'kind', 'effect', 'sound', 'generated', 'blasts', 'breaksFurther']);
/** The kinds of piece made from numbers (one piece each). */
export const MADE_KINDS = new Set(['fracWall', 'fracSlab', 'ground']);

export const cloneBlasts = blasts => blasts.map(b => ({ at: [...b.at], radius: b.radius }));
const objectOrNull = v => (v && typeof v === 'object' && !Array.isArray(v) ? v : null);

/** A piece's state, every key given and none shared with what it was made from. A made piece's blasts are its
 * generated's, so `blasts` and `breaksFurther` stay off it; breaksFurther goes with blasts only. */
export function pieceState({ tinted = false, flags = null, generated = null, blasts = null, breaksFurther = false } = {}) {
  const made = objectOrNull(generated), broken = !made && Array.isArray(blasts) && blasts.length > 0;
  return { tinted: tinted === true, flags: objectOrNull(flags) ? { ...flags } : null, generated: made ? structuredClone(made) : null,
           blasts: broken ? cloneBlasts(blasts) : null, breaksFurther: broken && breaksFurther === true };
}

/** The state of a piece the page draws, from its root's userData ({ source, flags, blasts, breaksFurther }): a map's
 * own piece is tinted where it is a spawned preview piece, a copy where it was made tinted. */
export const stateOfRoot = ({ source, flags = null, blasts = null, breaksFurther = false }) => pieceState({
  tinted: Boolean(source?.added?.tinted || source?.provenance?.type === 'spawn'), flags,
  generated: source?.added?.generated ?? null, blasts, breaksFurther });

/** A record's state: what a piece made from it holds (addedObject's options). A field it lacks gives the piece none. */
export const stateOf = record => pieceState({ tinted: record?.tinted === true, flags: record?.flags ?? null,
  generated: record?.generated ?? null, blasts: record?.blasts ?? null, breaksFurther: record?.breaksFurther === true });

/** A state as a record's fields: only those it has, in one spelling (and in the order a project has always written
 * them, so a state keyed before reads the same). */
export function recordFields(state) {
  const s = pieceState(state ?? {});
  return { ...(s.tinted ? { tinted: true } : {}), ...(s.generated ? { generated: s.generated } : {}), ...(s.flags ? { flags: s.flags } : {}),
           ...(s.blasts ? { blasts: s.blasts } : {}), ...(s.breaksFurther ? { breaksFurther: true } : {}) };
}
