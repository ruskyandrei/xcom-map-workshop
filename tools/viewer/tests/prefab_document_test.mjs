import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { measurePrefab, normalizePrefab, reconcilePrefab, orderedWrites, PREFAB_GRID_LEVELS, PREFAB_PLAYED_LEVELS, PREFAB_GRID_TOP,
         PREFAB_MIN_Z, PREFAB_MAX_Z, PREFAB_TILES } from '../web/prefab_document.js';
import { STAGE_LEVELS_MAX, STAGE_GRID_MAX, BUILDING_FLOORS_MAX } from '../web/project.js';

// the page's limits are the Python ones (tools/viewer/tests/limits.json, which test_prefab_builder.py checks too)
const limits = JSON.parse(readFileSync(new URL('./limits.json', import.meta.url)));
assert.deepEqual({ gridLevels: PREFAB_GRID_LEVELS, playedLevels: PREFAB_PLAYED_LEVELS, gridTop: PREFAB_GRID_TOP, minZ: PREFAB_MIN_Z,
                   maxZ: PREFAB_MAX_Z, tiles: PREFAB_TILES, stageLevels: STAGE_LEVELS_MAX, stageGrid: STAGE_GRID_MAX,
                   buildingFloors: BUILDING_FLOORS_MAX }, limits);

for (const c of JSON.parse(readFileSync(new URL('./prefab_size_cases.json', import.meta.url)))) {
  const result = measurePrefab([[c.name, c.box]]);
  // (the limits warn and refuse nothing: plan "sturdier prefabs", R7)
  assert.equal(result.warnings.length > 0, c.large, c.name);
  assert.equal(result.supported, true, c.name);
  assert.deepEqual(result.errors, [], c.name);
  if ('tall' in c) assert.equal(result.tall, c.tall, c.name);
  assert.deepEqual(result.tiles, c.tiles, c.name);
  if ('outside' in c) assert.equal(result.outside.length > 0, c.outside, c.name);
}
for (const c of JSON.parse(readFileSync(new URL('./prefab_translation_cases.json', import.meta.url)))) {
  const records = { pieces: [{ actor: 'piece', location: c.worldPosition }],
    buildings: [{ id: 'b', floors: [{ boxes: [c.worldBox] }] }] };
  const result = normalizePrefab(records, [['building', c.worldBox]]);
  assert.deepEqual(result.origin, c.origin, c.name);
  assert.deepEqual(result.pieces[0].location, c.localPosition, c.name);
  assert.deepEqual(result.buildings[0].floors[0].boxes[0], c.localBox, c.name);
}
const records = {
  pieces: [{ actor: 'visible', from: {}, location: [-192, 0, 64], partner: 'missing', prefab: 'link' },
    { actor: 'missing', from: {}, location: [96, 96, 64], partner: 'visible', prefab: 'link', recipe: { key: 'recipe' } }],
  buildings: [{ id: 'b', floors: [{ boxes: [[-192, 0, 0, 0, 192, 240]] }] }],
  groups: [{ id: 'g', members: [{ added: 'visible' }, { added: 'missing' }, { building: 'b' }] }],
};
const before = structuredClone(records);
const saved = normalizePrefab(records, [['visible', [-192, 0, 0, 0, 192, 240]]], { envelope: [0, 0, 0, 768, 576, 0], unknown: ['missing'] });
assert.deepEqual(records, before);
assert.deepEqual(saved.origin, [-192, 0, 0]);
assert.deepEqual(saved.tiles, [10, 6]);
assert.deepEqual(saved.pieces.map(p => p.location), [[0, 0, 64], [288, 96, 64]]);
assert.equal(saved.pieces[1].partner, 'visible');
assert.deepEqual(saved.groups, records.groups);
assert.equal(saved.buildings[0].id, 'b');
assert.equal(saved.size.verified, false);
const removed = reconcilePrefab([records.pieces[0]], records.buildings, [
  {id:'inner',members:[{added:'visible'},{added:'missing'}]},
  {id:'outer',members:[{group:'inner'},{building:'b'}]},
]);
assert.equal(removed.pieces[0].partner, null);
assert.deepEqual(removed.groups, [{id:'outer',breakTogether:false,members:[{added:'visible'},{building:'b'}]}]);
const writes = orderedWrites(), events = [];
let release;
const delayed = new Promise(resolve => { release = resolve; });
const put = writes.run(async () => { events.push('put-start'); await delayed; events.push('put-end'); });
const drop = writes.run(() => events.push('drop'));
await Promise.resolve(); assert.deepEqual(events, ['put-start']);
release(); await Promise.all([put, drop]); assert.deepEqual(events, ['put-start','put-end','drop']);
console.log('Prefab document: shared boundaries, normalization, graph repair and ordered writes passed.');
