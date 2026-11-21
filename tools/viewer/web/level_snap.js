// Floor pieces (refactor stage P8; floors.js holds the rules: the floor pieces' kinds and stamps, a building's floor
// under a point and its walking height). Level snap, the toggle that kept floor pieces to whole levels, went on
// 21 November 2026 (the custom geometry improvements plan, decision D5): Align to level (align.js) does it when asked.
// Here:
// - the floor pieces: the pieces that carry the map's saved floor tiles, flat, worked out on first use (floorData), and
//   a floor piece's saved floor height over its pivot (floorSupportOf);
// - the floor chosen in the Floor picker under a point (chosenStorey).
//
// createLevelSnap takes what it needs of app.js as one argument object, when app.js makes it: the buildings. Its own
// state is inside it (the floor pieces worked out, the floors' heights).
import { buildingsVersion, data } from './editor_state.js';
import { buildingWithFloor, classifyFloors, floorIndex, floorStamps, ownedFloors, stampSignature, storeyHeight,
         worldBox } from './floors.js';

export function createLevelSnap({ $, allBuildings }) {
  // Floor pieces (floors.js has the rules): the pieces that carry the map's saved floor tiles, flat, and not a
  // decoration lying on another floor piece (a rug, a plate). The piece list offers them as Floors; one is placed as
  // any piece is, and Align to level puts it on its levels. Worked out on first use (a map is one page).
  let floorInfo = null;
  function floorData() {
    if (!floorInfo) {
      const tiles = data.preview ? [] : data.tactical?.floorTiles ?? [];
      const actors = new Map();
      for (const o of data.objects) {
        if (o.layer !== 'base' || o.hidden || o.environment) continue;
        if (!actors.has(o.actor)) actors.set(o.actor, { actor: o.actor, parts: [], location: o.location });
        actors.get(o.actor).parts.push(o);
      }
      const floors = ownedFloors(tiles);
      const kinds = classifyFloors([...floors.keys()].filter(a => actors.has(a)).map(a => ({ actor: a, box: worldBox(actors.get(a).parts, data.meshes) })));
      floorInfo = { kinds, stamps: floorStamps([...actors.values()], kinds, floors), index: floorIndex(tiles) };
    }
    return floorInfo;
  }
  // The floor chosen in the Floor picker under a point: { z (its walking height, floors.js storeyHeight), building, floor }
  // of the building whose floor stands there, else the nearest with that floor; null with All.
  const storeyHeights = new Map();
  function chosenStorey(x, y) {
    const value = $('floor').value;
    const every = allBuildings();
    if (!value || value === 'all' || !every.length) return null;
    const k = Number(value) - 1, b = buildingWithFloor(every, k, x, y);
    if (b < 0) return null;
    const key = `${every[b].id}:${k}:${buildingsVersion}`;
    if (!storeyHeights.has(key)) storeyHeights.set(key, storeyHeight(every[b].floors[k], data.preview ? [] : data.tactical?.floorTiles));
    const z = storeyHeights.get(key);
    return z == null ? null : { z, building: b, floor: k };
  }
  // A floor piece's saved floor height over its pivot, or null for any other piece (several components, a car's part).
  function floorSupportOf(sources) {
    if (!data || sources.length !== 1 || sources[0].partner) return null;
    return floorData().stamps.get(stampSignature(sources))?.support ?? null;
  }
  // A floor piece's height in its map (its levels: Align to level moves it to that height moved by whole levels): an
  // original's exported height; a copy's original's, when the copy is of this map's piece (a copy keeps its own place);
  // else the height of the map's piece it is stamped like. null for any other piece.
  function floorBaseOf(sources) {
    if (floorSupportOf(sources) == null) return null;
    const o = sources[0];
    if (!o.added) return o.location[2];
    const from = o.added.from, same = o2 => o2.actor === from?.actor && o2.layer === from?.level;
    const original = from?.package?.toLowerCase() === data.name?.toLowerCase() ? data.objects.find(same) : null;
    return original?.location?.[2] ?? floorData().stamps.get(stampSignature(sources))?.z ?? null;
  }

  return { chosenStorey, floorBaseOf, floorData, floorSupportOf };
}
