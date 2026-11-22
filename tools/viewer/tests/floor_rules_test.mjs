// floors.js's plain rules on synthetic cases (moved here from the browser smoke's check_floor_rules, review finding 59;
// the Build's building-floor cases are shared_cases_test.mjs's): floors and decorations (a rug on a floor, an 18-unit
// sidewalk on the asphalt, a plate on the sidewalk, a plane on nothing, a wall), the yawed and scaled box of a piece,
// saved floors, floor stamps (one component only), the level height, the floor under a point, a building floor's
// walking height and the building for a floor; a made floor's tiles in words, and whether a slab is turned.
// Run: node tools/viewer/tests/floor_rules_test.mjs
import assert from 'node:assert/strict';
import { buildingWithFloor, changedTiles, classifyFloors, floorIndex, floorStamps, floorUnder, levelHeight, nearestLevel, ownedFloors, slabTileWords,
         slabTurned, stampSignature, storeyHeight, worldBox } from '../web/floors.js';

// boxes [x0, y0, z0, x1, y1, z1]
const kinds = classifyFloors([
  { actor: 'asphalt', box: [0, 0, 0, 960, 960, 0] }, { actor: 'sidewalk', box: [100, 100, -2, 868, 504, 16] },
  { actor: 'barfloor', box: [2000, 0, 0, 3152, 1152, 4] }, { actor: 'rug', box: [2100, 100, 4, 2338, 259, 9] },
  { actor: 'plate', box: [300, 300, 16, 492, 684, 16] }, { actor: 'lone', box: [5000, 0, 100, 5192, 192, 100] },
  { actor: 'wall', box: [0, 0, 0, 96, 960, 300] }, { actor: 'slab', box: [2100, 600, 4, 2300, 800, 24] },
  { actor: 'high rug', box: [2400, 100, 40, 2600, 200, 44] }]);
assert.deepEqual(Object.fromEntries(kinds), { asphalt: 'floor', sidewalk: 'floor', barfloor: 'floor', rug: 'decoration',
  plate: 'decoration', lone: 'floor', wall: 'other', slab: 'floor', 'high rug': 'floor' });

// the actor's yawed, scaled box from its mesh bounds
const box = worldBox([{ mesh: 'm', location: [100, 200, 0], rotation: [0, 16384, 0], scale: [2, 1, 1] }], { m: { bounds: [10, 0, 5, 10, 4, 5, 20] } });
assert.equal(box.map(v => Math.round(v * 1000) / 1000).join(), '96,200,0,104,240,10');

// saved floors: the median height on the most common level
const tiles = [[0, 0, 0, 16], [1, 0, 0, 16], [2, 0, 0, 17], [0, 0, 1, 80]].map(([x, y, l, z]) => ({ tile: [x, y, l], location: [48 + 96 * x, 48, z], actor: 'S' }));
assert.deepEqual(ownedFloors(tiles).get('S'), { z: 16, level: 0, count: 4 });

// floor stamps: one-component floor pieces only, with their saved floor over the pivot
const part = (actor, mesh) => ({ actor, actorClass: 'XComLevelActor', archetype: 'None', mesh, materials: ['m'], scale: [1, 1, 1], tint: [1, 1, 1, 1] });
const stamps = floorStamps([{ actor: 'S', parts: [part('S', 'side')], location: [0, 0, 0] },
                            { actor: 'V', parts: [part('V', 'roof'), part('V', 'cab')], location: [0, 0, 60] }],
                           new Map([['S', 'floor'], ['V', 'floor']]), new Map([['S', { z: 16 }], ['V', { z: 75 }]]));
assert.equal(stamps.size, 1);
assert.equal(stamps.get(stampSignature([part('S', 'side')]))?.support, 16);
assert.equal(stamps.get(stampSignature([part('S', 'side')]))?.z, 0);       // (its levels: Align to level's)

// the level height: a sidewalk (pivot 0, its floor 16 over it) on the road, on a sidewalk, upstairs; a storey's floor
// (pivot 192, its floor 2 over it) dropped on the ground
assert.deepEqual([levelHeight(0, 16, 0), levelHeight(0, 16, 16), levelHeight(0, 16, 18), levelHeight(0, 16, 208), levelHeight(192, 2, 2),
                  levelHeight(192, 2, 66)], [0, 0, 0, 192, 0, 64]);
// Align to level: the pivot's height to the nearest of its map height moved by whole levels
assert.deepEqual([nearestLevel(0, 0), nearestLevel(31.9, 0), nearestLevel(32, 0), nearestLevel(100.5, 16), nearestLevel(-20, 16)],
                 [0, 0, 64, 80, -48]);

// the floor under a point: the saved floor it lies on, else the point
const grid = { origin: [0, 0, 0], size: [96, 96, 64], dims: [50, 50, 10] };
const index = floorIndex([{ tile: [5, 5, 0], location: [528, 528, 16], actor: 'A' }, { tile: [5, 5, 3], location: [528, 528, 208], actor: 'B' }]);
assert.equal(floorUnder(index, grid, [530, 530, 17]).z, 16);
assert.equal(floorUnder(index, grid, [530, 530, 210]).z, 208);
assert.equal(floorUnder(index, grid, [530, 530, 60]).z, 16);
assert.equal(floorUnder(index, grid, [700, 700, 3]).floor, null);

// a building floor's walking height: its saved floor tiles near its bottom (not the 381 ones a level up, nor those
// outside its volume), else its bottom; none without volumes
const storey = { bottom: 208, boxes: [{ min: [0, 0, 208], max: [960, 960, 400] }] };
const st = [[100, 100, 210], [200, 100, 210], [300, 100, 381], [5000, 5000, 210], [400, 100, 212]].map(location => ({ location }));
assert.equal(storeyHeight(storey, st), 210);
assert.equal(storeyHeight(storey, []), 208);
assert.equal(storeyHeight({ bottom: 0, boxes: [] }, st), null);

// the building for a floor: the one standing over the point, else the nearest with that floor
const v = (x0, x1) => ({ boxes: [{ min: [x0, 0, 0], max: [x1, 960, 200] }] });
const bs = [{ floors: [v(0, 960), v(0, 960)] }, { floors: [v(2000, 2960)] }];
assert.deepEqual([buildingWithFloor(bs, 1, 2500, 100), buildingWithFloor(bs, 0, 2500, 100), buildingWithFloor(bs, 0, 1500, 100),
                  buildingWithFloor(bs, 0, 500, 100), buildingWithFloor(bs, 5, 0, 0)], [0, 1, 1, 0, -1]);

// a made floor's tiles in words (F-147): nothing when it covers no tile in part; a turned slab is yaw alone
assert.equal(slabTileWords({ floor: [[1, 1]], part: [] }), null);
const words = slabTileWords({ floor: [[10, 9], [11, 9]], part: [[11, 10, 0.289], [12, 9, 0.242]] });
assert.equal(words.short, 'floor on 2 of 4 tiles');
assert.ok(words.long.startsWith("It is floor on 2 tiles: a tile is floor where it covers the tile's centre"), words.long);
assert.ok(words.long.endsWith('so the 2 tiles at its edge it covers in part are no floor at its height.'), words.long);
assert.ok(slabTileWords({ floor: [], part: [[0, 0, 0.1]] }).long.includes('the 1 tile at its edge it covers in part is no floor'));
assert.deepEqual([slabTurned([0, 3641, 0]), slabTurned([0, 16384, 0]), slabTurned([0, -32768, 0]), slabTurned([2048, 3000, 0])],
                 [true, false, false, false]);
console.log('floor rules: ok');

// the tiles a change stands on (native_copy.changed_tiles' twin): a barrel 54 wide centred at x 1190 on the farm's grid
// (origin -2496, -3552, -128) stands on tiles 37 and 38 in x, 11 to 13 in y, levels 0 and 1 (its top 11 into level 1);
// the scout's corner (39, 12, 0) beside it is not among them, and one on the corner stands on it
{
  const farm = { origin: [-2496, -3552, -128], dims: [67, 70, 17] };
  const got = changedTiles([[1163, -2380, -117, 1217, -2326, -53]], farm.origin, farm.dims);
  assert.deepEqual([...got].sort(), ['37,11,0', '37,11,1', '37,12,0', '37,12,1', '37,13,0', '37,13,1',
                                     '38,11,0', '38,11,1', '38,12,0', '38,12,1', '38,13,0', '38,13,1']);
  assert.ok(!got.has('39,12,0'));
  const on = changedTiles([[2228, -1420, -117, 2282, -1366, -53]], farm.origin, farm.dims);
  assert.ok(on.has('49,22,0'));
  // a box over two levels, cut to the grid
  const tall = changedTiles([[-2496, -3552, -128, -2400, -3456, 10]], farm.origin, farm.dims);
  assert.deepEqual([...tall].filter(k => k.startsWith('0,0,')).sort(), ['0,0,0', '0,0,1', '0,0,2']);
}
