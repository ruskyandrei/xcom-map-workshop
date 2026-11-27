// A baked Build's own light on the page (game-likeness plan, stage B4): which of the project's pieces are as the
// project's last baked Build made them, and so lit by that Build's lightmaps in the Game look. Pure: records, keys and
// words, no three.js. The wiring is build_light.js; the drawing baked_light.js.
//
// A baked Build's manifest names the built actor each project piece became (`builtActors`: the project's own name for
// the piece, a moved original's actor or an added piece's output name, to the actor the Build made) and keeps a copy
// of the project as it was built (`asBuilt`); the server exports that Build's lightmaps into the cache
// (tools/viewer/build_light.py: `pieces`, each built component's record as export 45 has a piece's). A piece is as
// built where its record in the project now is the record it had as built, but for what makes no difference to its
// light (UNLIT). Its built component is then its own (one of the map's pieces where the map has it) or the one the
// Build made for it (a moved original's copy, an added piece), named by the built actor and the component's own name:
// a copy keeps its components' names under its new actor (tools/bake/native_copy.py clone_assembly, transplant.py).

import { memberKey } from './project.js';

// What of a record makes no difference to a piece's light: its flags (settings the game reads), the prefab and partner
// it was placed with, the prefab builder's recipe.
const UNLIT = new Set(['flags', 'prefab', 'partner', 'recipe']);
// How far apart two numbers of a record may be and still be the same (a pose read again from its matrix: project.js
// keeps 4 decimals of a place and 3 of a turn)
const EPS = 1e-3;

/** The project's records by key: an original's override by its target (`orig|<package>|<level>|<actor>`), an added
 *  thing's by its output name (`added|<actor>`), as the groups' keys (project.js memberKey). */
export function recordsByKey(state) {
  const out = new Map();
  for (const r of state?.overrides ?? []) if (r?.target?.actor) out.set(memberKey(r.target), r);
  for (const r of state?.added ?? []) if (typeof r?.actor === 'string') out.set(memberKey({ added: r.actor }), r);
  return out;
}

/** Whether two records are the same for a piece's light: every value but UNLIT's, numbers within EPS, a value that is
 *  undefined as one left out. */
export function sameRecord(a, b, top = true) {
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) <= EPS;
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, k) => sameRecord(v, b[k], false));
  }
  if (a && b && typeof a === 'object' && typeof b === 'object') {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) {
      if (top && UNLIT.has(k)) continue;
      if (a[k] === undefined && b[k] === undefined) continue;
      if (!sameRecord(a[k], b[k], false)) return false;
    }
    return true;
  }
  return a === b;
}

/** The keys whose records differ between the project now (`now`, a document's state) and as built (`built`): a Set. A
 *  record in one alone differs. */
export function changedSince(now, built) {
  const a = recordsByKey(now), b = recordsByKey(built), out = new Set();
  for (const [k, r] of a) if (!b.has(k) || !sameRecord(r, b.get(k))) out.add(k);
  for (const k of b.keys()) if (!a.has(k)) out.add(k);
  return out;
}

/** Whether an original's record as built moved it (the Build made it again as a copy, which `builtActors` names): a
 *  pose and not deleted. */
export const movedAsBuilt = record => Boolean(record && !record.deleted && (record.location || record.rotation));

/** A piece's built component: for an added piece or an original moved as built, the actor `builtActors` names for it
 *  with the component's own name (null where it names none, or a list: a made piece the Build cut into parts, whose
 *  parts the page doesn't draw); else the component itself. */
export function builtComponent(builtActors, { actor, component, copied }) {
  if (!copied) return component;
  const built = builtActors?.[actor];
  return typeof built === 'string' ? `${built}.${component.split('.').at(-1)}` : null;
}

/** Where a light stood as built and how far it reached, { location, radius } in game units, from its record as built:
 *  an override's pose and values over the light as exported (`exported`), an added light's own; null where it has no
 *  place or no reach (deleted, a light without a radius). */
export function lightPlace(record, exported = null) {
  if (!record || record.deleted) return null;
  const location = record.location ?? exported?.location, radius = record.light?.radius ?? exported?.radius;
  return Array.isArray(location) && location.length === 3 && Number.isFinite(radius) && radius > 0 ? { location: [...location], radius } : null;
}

/** View options' line for a Build's light: its time (`when`, as the page writes a time) and how many pieces changed
 *  since; with its tip. */
export function buildWords(when, changed) {
  const since = changed ? `${changed} ${changed === 1 ? 'piece' : 'pieces'} changed since` : 'nothing changed since';
  return { text: `Lit by the Build of ${when} · ${since}`,
           title: 'In the Game look, the pieces as the project\'s last baked Build made them are lit by its own lightmaps. '
                  + 'A piece changed since, and the pieces a light changed since reaches, are lit live' };
}
