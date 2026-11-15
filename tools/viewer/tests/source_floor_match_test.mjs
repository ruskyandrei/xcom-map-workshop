// A project building's source building, from a piece taken from it (floors.js sourceFloorMatch, the twin of the
// compiler's source_floor_match: the same cases), and the listing carried through edited boxes.
// Run: node tools/viewer/tests/source_floor_match_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { sourceFloorMatch, floorsOf, carriedListing, touchedFloors, ruleListing } from '../web/floors.js';

const cases = JSON.parse(readFileSync(new URL('../../editor/tests/source_floor_match_cases.json', import.meta.url)));
for (const c of cases) {
  const got = sourceFloorMatch(c.buildings, floorsOf({ floors: c.floors.map(boxes => ({ boxes })) }),
                               c.before, { location: c.location, rotation: c.rotation });
  const shown = got && { building: got.building.id, floorMap: Object.keys(got.floorMap).sort((a, b) => a - b).map(k => got.floorMap[k]) };
  assert.deepEqual(shown, c.expect, c.name);
}

// The UFO's roof (XComLevelActor_90, SSRoof): the map lists it on its roof floor only (floor 1's volume excludes it,
// floor 2's includes it), where the rule alone gives both floors. Carried through the edited boxes it stays on the
// roof floor; on a building that is no longer the source's it goes by the rule.
const ufo = cases[0];
const match = sourceFloorMatch(ufo.buildings, floorsOf({ floors: ufo.floors.map(boxes => ({ boxes })) }), ufo.before,
                               { location: ufo.location, rotation: ufo.rotation });
const roof = [-2366.8 + 2496, -381.2 + 2496, -752.8 + 864, 1218.7 + 864, 236.5 + 2, 524.5 + 2];
const rule = floors => ruleListing(touchedFloors(roof, floors), false).map(l => [l.floor, l.cutdownFloor]);
const floors = floorsOf({ floors: ufo.floors.map(boxes => ({ boxes })) });
assert.deepEqual(rule(floors), [[0, 0], [1, 0]]);
assert.deepEqual(carriedListing([[1, 0]], rule(match.moved), rule(floors), match.floorMap).entries, [[1, 0]]);

console.log('source floor match: ok');
