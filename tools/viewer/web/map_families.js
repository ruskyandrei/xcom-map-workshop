// The map's families and assemblies (refactor stage P9): the families of pieces the server worked out for the map
// (families.json, tools/viewer/families.py: the compiler's own) set as they arrive, each of the map's originals' assembly
// with the link tag its copies' pieces share (useMapFamilies), and a piece's assembly, the map's own or, for a piece of
// another map, its map's as its records are read (assemblyOf; foreignAssemblies, which the templates of other maps'
// pieces fill: library_templates.js). The families themselves (families) and the landing's pieces (landingActors) are
// editor_state.js's.
//
// createMapFamilies takes a piece's original (fromOf) and the gizmo (regrouped once the assemblies are known) when
// app.js makes it, after the gizmo. Its own state is inside it: the assemblies by original, the other maps' assemblies.
import { short } from './dom_words.js';
import { data, setFamilies, setLandingActors } from './editor_state.js';
import { useFamilies } from './pieces.js';
import { targetKey } from './project.js';
import { fromOf } from './piece_records.js';

export function createMapFamilies({ gizmo }) {
  // The families of pieces and the map's assemblies (families.json, tools/viewer/families.py: the compiler's own), or
  // null from a server without them. assemblyIndex: an original's key (package|level|actor) to its assembly.
  let assemblyIndex = new Map();     // (the families, families: editor_state.js)
  // foreignAssemblies: the same for the assemblies of other maps' pieces, as their records are read (libraryTemplate).
  const foreignAssemblies = new Map();
  const assemblyOf = o => {
    if (!o) return null;
    const key = targetKey(fromOf(o));
    return assemblyIndex.get(key) ?? foreignAssemblies.get(key) ?? null;
  };
  // The map's families arrived: an assembly also knows the link tag its copies' pieces share where a piece has no prefab
  // of its own (pasteSnapshot): its members' prefab (Police Station's standalone light bar joins its sedan's), else its
  // pivot (a door's leaf and frame share no prefab).
  function useMapFamilies(table) {
    setFamilies(table); assemblyIndex = new Map();
    const prefabOf = new Map(data.objects.filter(o => o.prefab && o.layer === 'base').map(o => [o.actor, o.prefab]));
    for (const a of table?.assemblies ?? []) {
      const tag = a.members.length > 1 ? (a.members.map(m => prefabOf.get(m)).find(Boolean) ?? short(a.pivot)) : null;
      const assembly = { ...a, tag };
      for (const m of a.members) assemblyIndex.set(targetKey({ package: table.map, level: 'base', actor: m }), assembly);
    }
    useFamilies(table, o => assemblyOf(o)?.family ?? null);
    setLandingActors(Array.isArray(table?.landing) ? new Set(table.landing) : null);
    gizmo.regroup();
  }

  return { assemblyOf, foreignAssemblies, useMapFamilies };
}
