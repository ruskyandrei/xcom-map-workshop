// The building floors a piece is listed on, as the Build lists it (refactor stage P8; floors.js holds the rules:
// touchedFloors, ruleListing, copyFloors, floorAt, carriedListing; tools/bake/buildings.py the Build's side). Here:
// - where the project's buildings list a piece, by the game editor's rule from the box of what is drawn of it where it
//   stands, the map's own buildings changed carrying what the map saved (projectListings);
// - where the map's own buildings that are not changed list it: its saved listings, or a copy's moved to the floor it
//   stands in (mapListings); both together (listingsNow);
// - the key of the pieces' edits (moved, deleted) that the cutaway, the ground grid and Level snap follow (editedKey).
//
// createFloorListings takes what it needs of app.js as one argument object, when app.js makes it: the buildings and
// the map's buildings changed, a piece's box and its original's carried to where it stands. It keeps no state of its
// own: what it works out for a piece is kept on the piece's root (its listings and their key).
import { buildings, buildingsVersion, data, foreignTemplates, roots } from './editor_state.js';
import { carriedListing, copyFloors, floorAt, floorMapOf, floorsOf, LISTED_CLASSES, ruleListing, sourceFloorMatch,
         touchedFloors } from './floors.js';
import { placedPose } from './gizmo.js';
import { targetKey } from './project.js';

export function createFloorListings({ allBuildings, boxOf, mapEdits, mapIdOf, movedBox, originalOf, short,
                                      vertexBox }) {
  // (the classes a building floor lists: floors.js LISTED_CLASSES)
  // Where the project's buildings list a piece, by the game editor's rule as the Build applies it (floors.js
  // touchedFloors and ruleListing; tools/bake/buildings.py): from the box of what is drawn of it where it stands.
  function projectListings(root) {
    const o = root.userData.source;
    if (!allBuildings().some(b => b.project) || o.cover || o.hidden || !LISTED_CLASSES.has(o.actorClass)) return [];
    const key = `${buildingsVersion}|${root.matrix.elements.join(',')}`;
    if (root.userData.ownListingsKey === key) return root.userData.ownListings;
    const out = [], rough = boxOf(root)?.slice();
    const template = o.added && (o.foreign ? foreignTemplates.get(`${targetKey(o.added.from)}|${o.component}`) : originalOf(o));
    const sourceBuildings = template && (template.foreign?.buildings ?? data.buildings);
    const before = template && { location: template.floorLocation ?? template.location, rotation: template.rotation };
    const pose = before && placedPose(o, root.matrix);
    const authored = new Set();
    // The rule's answer for a box against floors, as [[floor, cutdownFloor]]. A piece that collides with nothing is on
    // none: the game lists what touches a floor volume, and only a piece that collides touches one (F-87; `collides`
    // false in exports that carry it, the Build's native_copy.collides).
    const collides = o.collides !== false;
    const rule = (at, floors) => (collides ? ruleListing(touchedFloors(at, floors), Boolean(o.cutout)).map(l => [l.floor, l.cutdownFloor]) : []);
    if (rough) {
      let box = null;
      for (const b of allBuildings()) {
        if (!b.project) continue;
        if (b.map) {
          // one of the map's own, changed (map buildings plan, section 3): what the map saved where the rule's answer
          // did not change, with the old boxes at the piece's old pose against the new boxes at its new pose
          const original = o.foreign ? null : originalOf(o);
          const saved = (original?.floors ?? []).filter(l => l.building === b.map.id).map(l => [l.floor, l.cutdownFloor]);
          if (!saved.length && !touchedFloors(rough, b.floors, -Infinity).length) continue;
          box ??= boxOf(root, true)?.slice();
          if (!box) break;
          const old = !original ? null : !o.added && !root.userData.edit ? box : vertexBox(original);
          const fmap = floorMapOf(b.map.floors.map(f => f.volumes.map(short)), b.project.floors.map(f => f.volumes));
          const oldRule = old ? rule(old, b.map.floors) : [];
          const newRule = old || !original ? rule(box, b.floors) : [];
          for (const [floor, cut] of carriedListing(saved, oldRule, newRule, fmap).entries) out.push({ building: b.id, floor, cutdownFloor: cut });
          continue;
        }
        // a building that comes from the piece's own map: what the map saved (its hand-made inclusion and exclusion
        // lists among it) where the rule gives the same with the map's boxes as with the building's, which may have been
        // edited since (the Build's buildings.members with the compiler's carry)
        const match = sourceBuildings && sourceFloorMatch(sourceBuildings, b.floors, before, pose);
        if (match) {
          authored.add(b.project.id);
          const saved = (template.floors ?? []).filter(l => l.building === match.building.id).map(l => [l.floor, l.cutdownFloor]);
          box ??= boxOf(root, true)?.slice();
          const [oldRule, newRule] = box ? [rule(box, match.moved), rule(box, b.floors)] : [[], []];
          for (const [floor, cut] of carriedListing(saved, oldRule, newRule, match.floorMap).entries) out.push({ building: b.id, floor, cutdownFloor: cut });
          continue;
        }
        if (!touchedFloors(rough, b.floors, -Infinity).length) continue;
        box ??= boxOf(root, true)?.slice();
        if (!box) break;
        for (const [floor, cut] of rule(box, b.floors)) out.push({ building: b.id, floor, cutdownFloor: cut });
      }
    }
    root.userData.authoredFloors = authored;
    root.userData.ownListingsKey = key; root.userData.ownListings = out;
    return out;
  }
  const listingsNow = root => (allBuildings().some(b => b.project) ? [...mapListings(root), ...projectListings(root)] : mapListings(root));
  // Where the map's own buildings that are not changed list a piece: its saved listings, or a copy's moved to the floor
  // it stands in (copyFloors, as the Build's edit_floor_caches). A changed or deleted one lists nothing here: its
  // listing is projectListings', and a copy standing in a changed one is left to it (its floor found by its new boxes).
  function mapListings(root) {
    const o = root.userData.source, edits = mapEdits(), keep = l => !edits.exportIds.has(l.building);
    if (!o.added && !root.userData.edit) return edits.exportIds.size ? (o.floors || []).filter(keep) : o.floors || [];
    const original = originalOf(o), listings = original?.floors ?? [];
    if (!listings.length || !(data.exporterVersion >= 15) || !data.buildings?.length) return [];
    const key = `${root.matrix.elements.join(',')}|${buildingsVersion}`;
    if (root.userData.listingsKey === key) return root.userData.listings;
    const exported = data.buildings, index = new Map(exported.map((b, i) => [b.id, i]));
    const before = vertexBox(original);
    if (!before) return [];
    const live = new Map(buildings.map(b => [b.id, b]));
    const now = exported.map(b => {
      if (!edits.exportIds.has(b.id)) return b;
      const record = live.get(mapIdOf(b));
      return { ...b, floors: record ? floorsOf(record) : [] };
    });
    const from = { location: original.location, rotation: original.rotation }, pose = placedPose(o, root.matrix);
    const here = floorAt(exported, before), there = floorAt(now, movedBox(before, from, pose));
    const result = there && edits.exportIds.has(exported[there.building].id) ? []
      : copyFloors(listings.filter(l => index.has(l.building) && keep(l)).map(l => ({ ...l, building: index.get(l.building) })),
                   here, there, b => exported[b].floors.length).map(l => ({ ...l, building: exported[l.building].id }));
    root.userData.listingsKey = key; root.userData.listings = result;
    return result;
  }
  // After an edit ends (a drag let go, an undo): copies and moved pieces may stand in other floors now, and the Floor
  // tiles overlay hatches moved and deleted pieces' tiles. The cutaway follows when what it depends on changed.
  // (cutKey, the edits the cutaway last followed: cutaway.js)
  function editedKey() {
    let key = '';
    for (const r of roots.values()) if (r.userData.edit || r.userData.deleted) key += `${r.userData.source.id}:${r.userData.deleted ? 'x' : r.matrix.elements.join(',')}|`;
    return key;
  }

  return { editedKey, listingsNow, projectListings };
}
