// A copied piece's record (review finding 6): one conversion between a piece as the page holds it and the record a
// project, a prefab and the clipboard keep of it, so a piece is the same piece after a copy and paste, a project saved
// and opened, a prefab saved from a selection, the prefab builder's document and a prefab placed (stamped).
//
// The whole record (refactor stage P2): this module is the one writer and the one reader of an added thing's record,
// whatever it is: a copy of a piece (of this map or another, a made wall, floor or ground piece, a broken copy), a
// cover block, a light (a copy of a map's light, or the editor's own recipe light), an effect, a sound or a lens flare.
// - recordOf(unit, path): what the page knows of one added thing (a unit, gathered from its roots or a clip's entry)
//   as its record, in the fields and the order a project, a prefab and the builder's document have always written.
// - optionsOf(record, form, state): a record as what makes its root again (addedObject's options for a piece or a cover
//   block; for a light and an effect, what addedLight and addedEffect are given, which the page completes with the
//   template it finds).
//
// A piece's state is what it is beyond its names and place: { tinted, flags, generated, blasts, breaksFurther }.
// - tinted: a copy of a spawned preview piece keeps its tint.
// - flags: its piece flags (piece_flags.js).
// - generated: a piece made from numbers (a drawn wall, floor or roof, or ground shape: custom geometry plan); a made
//   piece's own blasts are inside it (generated.blasts, generated.breaksFurther).
// - blasts, breaksFurther: a copy of one of the map's fracturing pieces, broken (custom geometry editing plan, E6).
// Nothing here knows three.js or the page: app.js reads a state from a root (stateOfRoot), writes it into a record
// (recordFields, through recordOf) and makes a piece of a record's (stateOf, through optionsOf).
import { keptValues } from './effects_rules.js';

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

/** An added thing's record from what the page knows of it (a unit), in the one shape a project, a prefab and the
 * builder's document keep. The unit's `form` says what it is:
 * - 'piece' (the default): a copy of a piece { id, actor, from, components (each of its components once, in any
 *   order: the record lists them sorted), location, rotation, prefab, partner (its link tag and its partner's name;
 *   none: null), state (pieceState's), recipe (the library's { key, name }, or none) };
 * - 'cover': a cover block { id, actor, template (its recipe, { kind, version }), cover, location, rotation };
 * - 'light': a recipe light { id, actor, template, light (every value), location, rotation }, or a copy of a map's
 *   light { id, actor, from, component, location, rotation, light (only the values changed from its original's) };
 * - 'effect': an effect, a sound or a lens flare { id, actor, kind, from, location, rotation, values (as saved:
 *   effects_rules.js savedValues; none: null) }.
 * `id` (the project's entity id) is written only when the unit has one: a prefab's records have none. `path` is the
 * writer's: 'project' (a project, and the builder's document) or 'prefab' (a prefab saved from a selection), which has
 * always put a recipe light's values before its pose. Only `cover` and the components are copied: the unit's other
 * values go into the record as they are. */
export function recordOf(unit, path = 'project') {
  const { form = 'piece', actor, location, rotation } = unit, id = 'id' in unit ? { id: unit.id } : {};
  if (form === 'cover') return { ...id, actor, template: unit.template, cover: { ...unit.cover }, location, rotation };
  if (form === 'effect') return { ...id, actor, kind: unit.kind, from: unit.from, location, rotation, ...(unit.values ? { [unit.kind]: unit.values } : {}) };
  if (form === 'light') {
    if (unit.template) return path === 'prefab' ? { ...id, actor, template: unit.template, light: unit.light, location, rotation }
      : { ...id, actor, template: unit.template, location, rotation, light: unit.light };
    return { ...id, actor, from: unit.from, components: [unit.component], location, rotation,
             ...(unit.light && Object.keys(unit.light).length ? { light: unit.light } : {}) };
  }
  return { ...id, actor, from: unit.from, components: [...unit.components].sort(), location, rotation, prefab: unit.prefab ?? null,
           partner: unit.partner ?? null, ...recordFields(unit.state), ...(unit.recipe ? { recipe: unit.recipe } : {}) };
}

/** A record as what makes its root again, by its `form` (recordOf's; the page tells a copy of a map's light from a copy
 * of a piece by the light it names):
 * - 'piece': addedObject's options { actor, entity (the record's id), prefab, partner, location, rotation, and the
 *   piece's state: `state` when given (a paste's clip entry carries its own), else the record's (stateOf) };
 * - 'cover': addedObject's options for a cover block, which takes no link, tint, flags or blasts from its record;
 * - 'light': what addedLight is made from { actor, entity, location, rotation, recipe (a recipe light's template, else
 *   none), light (its values as saved), from, component (the map light's it copies) }: the page finds its source;
 * - 'effect': what addedEffect is given { actor, entity, kind, from, location, rotation, values (as the page keeps them:
 *   effects_rules.js keptValues) }.
 * The record's own arrays and objects are handed on as they are (a state is the copy stateOf makes). */
export function optionsOf(record, form = 'piece', state = null) {
  const { actor, id: entity, location, rotation } = record;
  if (form === 'cover') return { actor, entity, prefab: null, partner: null, location, rotation, tinted: false };
  if (form === 'light') return { actor, entity, location, rotation, recipe: record.template, light: record.light, from: record.from,
                                 component: record.components?.[0] };
  if (form === 'effect') return { actor, entity, kind: record.kind, from: record.from, location, rotation, values: keptValues(record[record.kind]) };
  return { actor, entity, prefab: record.prefab ?? null, partner: record.partner ?? null, location, rotation, ...(state ?? stateOf(record)) };
}
