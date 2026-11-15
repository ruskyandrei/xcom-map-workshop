// The map's own buildings made editable (private/plans/done/map-buildings-editable-plan.md): the project records
// (project.js) and the page's plain functions (floors.js). Run: node tools/viewer/tests/map_buildings_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validBuilding, tidyBuilding, sortState, mapBuildingId } from '../web/project.js';
import { carriedListing, floorMapOf, buildingProblems } from '../web/floors.js';

const replaces = { package: 'URB_Bar', level: 'base', actor: 'TheWorld.PersistentLevel.XComBuildingVolume_2' };
const box = [0, 0, 16, 96, 96, 208];

// ---- E1: the records
assert.equal(mapBuildingId('PersistentLevel', 'TheWorld.PersistentLevel.XComBuildingVolume_2'), 'map:PersistentLevel.XComBuildingVolume_2');
const changed = { id: 'map:PersistentLevel.XComBuildingVolume_2', name: 'XComBuildingVolume_2', kind: 'building', replaces,
                  floors: [{ boxes: [box, [96, 0, 16, 192, 96, 208.00004]], volumes: [null, 'XComFloorVolume_3'] }] };
assert.ok(validBuilding(changed));
// a map building's boxes and volumes are sorted together
assert.deepEqual(tidyBuilding({ ...changed, floors: [{ boxes: [[96, 0, 16, 192, 96, 208], box], volumes: ['XComFloorVolume_3', null] }] }).floors,
                 [{ boxes: [box, [96, 0, 16, 192, 96, 208]], volumes: [null, 'XComFloorVolume_3'] }]);
assert.deepEqual(tidyBuilding(changed).floors[0].boxes[1], [96, 0, 16, 192, 96, 208]);
// volumes go with replaces, and only there; as long as the boxes, each a name or null
assert.ok(!validBuilding({ ...changed, floors: [{ boxes: [box] }] }));
assert.ok(!validBuilding({ ...changed, floors: [{ boxes: [box], volumes: [] }] }));
assert.ok(!validBuilding({ ...changed, floors: [{ boxes: [box], volumes: [''] }] }));
assert.ok(!validBuilding({ id: 'p', floors: [{ boxes: [box], volumes: [null] }] }));
assert.ok(validBuilding({ id: 'p', floors: [{ boxes: [box] }] }));
assert.ok(!validBuilding({ ...changed, replaces: { package: 'URB_Bar', level: 'base' } }));
// a deleted one: replaces, deleted, no floors
const deleted = { id: changed.id, replaces, deleted: true };
assert.ok(validBuilding(deleted));
assert.deepEqual(tidyBuilding(deleted), deleted);
assert.ok(!validBuilding({ ...deleted, floors: changed.floors }));
assert.ok(!validBuilding({ id: 'p', deleted: true }));
assert.ok(!validBuilding({ ...deleted, deleted: false }));
// malformed ones are carried as they are by sortState
const odd = { id: 'map:x', replaces, floors: 'none' };
assert.deepEqual(sortState({ overrides: [], added: [], buildings: [odd, changed] }).buildings, [tidyBuilding(changed), odd]);

// ---- E4: the carried listing, the twin of the Build's buildings.carried (the same cases)
for (const c of JSON.parse(readFileSync(new URL('../../bake/tests/carried_listing_cases.json', import.meta.url)))) {
  const got = carriedListing(c.saved, c.oldRule, c.newRule, c.floorMap);
  assert.deepEqual([got.entries, got.kept], [c.entries, c.kept], c.name);
}
assert.deepEqual(floorMapOf([['a'], ['b']], [[null], ['a'], ['b']]), { 0: 1, 1: 2 });
assert.deepEqual(floorMapOf([['a', 'c'], ['b']], [['a'], [null]]), { 0: 0, 1: null });
// problems: only for the boxes `fresh` names (a map building's boxes as the map has them are not said)
const grid = { origin: [0, 0, 0], dimensions: [10, 10, 12], size: [96, 96, 64] };
const shed = { floors: [{ boxes: [[0, 0, 16, 384, 384, 300]] }, { boxes: [[0, 0, 208, 384, 384, 400]] }] };
assert.equal(buildingProblems(shed, grid, []).length, 2);
assert.equal(buildingProblems(shed, grid, [], false, () => false).length, 0);
assert.deepEqual(buildingProblems(shed, grid, [], false, k => k === 0), ['floor 1 overlaps floor 2']);

console.log('map buildings: ok');
