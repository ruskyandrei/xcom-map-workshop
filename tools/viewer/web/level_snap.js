// Floor pieces and Level snap (refactor stage P8; floors.js holds the rules: the floor pieces' kinds and stamps, a
// building's floor under a point and its walking height). Here:
// - the floor pieces: the pieces that carry the map's saved floor tiles, flat, worked out on first use (floorData), and
//   a floor piece's saved floor height over its pivot (floorSupportOf);
// - Level snap (L, the tool strip's button under Snap; remembered in the browser): floor pieces keep to whole levels
//   when placed and moved (setLevelSnap, levelButton);
// - the floor chosen in the Floor picker under a point (chosenStorey).
//
// createLevelSnap takes what it needs of app.js as one argument object, when app.js makes it: the buildings and the
// hints. Its own state is inside it (the floor pieces worked out, the floors' heights); Level snap itself (levelSnap:
// the placing, the gizmo and the keys read it) is editor_state.js's, given the browser's remembered value as this is
// made.
import { buildingsVersion, data, levelSnap, setGhostDirty, setLevelSnapValue } from './editor_state.js';
import { buildingWithFloor, classifyFloors, floorIndex, floorStamps, ownedFloors, stampSignature, storeyHeight,
         worldBox } from './floors.js';
import { recall, remember } from './storage.js';

export function createLevelSnap({ $, allBuildings, restingHint }) {
  // Floor pieces (floors.js has the rules): the pieces that carry the map's saved floor tiles, flat, and not a
  // decoration lying on another floor piece (a rug, a plate). The piece list offers them as Floors; placing one keeps
  // the height it has in the map, moved by whole levels to the saved floor under the cursor, and across it moves freely
  // or by Snap. Worked out on first use (a map is one page).
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
  // Level snap (L, the tool strip's button under Snap; on unless turned off, and remembered): floor pieces keep to whole
  // levels when placed and when moved with the gizmo. Off, they are placed and moved as any piece is.
  const LEVEL_SNAP = 'workshop.levelSnap';
  setLevelSnapValue(recall(LEVEL_SNAP) !== '0');     // (levelSnap: editor_state.js)
  function setLevelSnap(on) {
    setLevelSnapValue(Boolean(on)); remember(LEVEL_SNAP, levelSnap ? '1' : '0'); setGhostDirty(true);
    levelButton(); restingHint();
  }
  function levelButton() {
    const button = $('editLevels');
    button.classList.toggle('on', levelSnap); button.setAttribute('aria-pressed', levelSnap);
    button.title = levelSnap
      ? 'Level snap on (L): floor pieces keep to whole levels (64 units up). Placed, one takes its height in the map moved to '
        + 'the level under the cursor, or to the floor chosen in the Floor picker; moved up or down, it steps by whole levels. '
        + 'Click to turn it off'
      : 'Level snap off (L): floor pieces are placed and moved as any piece is. Click to turn it on';
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

  return { chosenStorey, floorData, floorSupportOf, levelButton, setLevelSnap };
}
