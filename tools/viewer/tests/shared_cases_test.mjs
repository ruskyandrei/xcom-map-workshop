// The page's side of the case files Python's tests read too (review finding 55): each module the cases name is run
// on them here, in node, so the suite checks both twins and not only the Python one.
// - tests/cone_cases.json: light_rules.js effectiveCone (lights.effective_cone in test_lights.py);
// - tools/editor/tests/pose_rule_cases.json: poserule.js gridMove and nearestGridPose (the compiler's pose rule in
//   test_compiler.py);
// - tools/bake/tests/floor_membership_cases.json: floors.js floorAt and copyFloors (native_copy.floor_at and
//   copy_floors in test_native_copy.py);
// - tools/editor/tests/stage_levels_cases.json: prefab_document.js prefabStageLevels (prefab_stage.stage_levels);
// - tools/editor/tests/wall_join_cases.json: walls.js wallJoins (compiler.wall_joins in test_compiler_generated.py);
// - tools/editor/tests/free_join_cases.json: walls.js freeWallJoins (made_edits.free_wall_joins in test_compiler_free.py);
// - tools/editor/tests/mapping_origin_cases.json: made_mapping.js mappingOrigin (made_edits.mapping_origin in
//   test_compiler_free.py).
// Run: node tools/viewer/tests/shared_cases_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { effectiveCone } from '../web/light_rules.js';
import { gridMove, nearestGridPose } from '../web/poserule.js';
import { copyFloors, floorAt } from '../web/floors.js';
import { prefabStageLevels } from '../web/prefab_document.js';
import { freeWallJoins, wallJoins } from '../web/walls.js';
import { mappingOrigin } from '../web/made_mapping.js';

const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const near = (a, b, eps, what) => {
  assert.equal(a.length, b.length, what);
  a.forEach((v, k) => assert.ok(Math.abs(v - b[k]) <= eps, `${what}: ${JSON.stringify(a)} against ${JSON.stringify(b)}`));
};

// the cones: the effective half-angles, to ten places as test_lights.py has them
const cones = read('./cone_cases.json').cases;
assert.ok(cones.length >= 10);
for (const c of cones) near(effectiveCone(c.inner, c.outer), c.effective, 1e-10, c.why);

// the pose rule: valid or not and why, the quarter turns and the move; and the nearest pose on the grid
const poses = read('../../editor/tests/pose_rule_cases.json').cases;
assert.ok(poses.length >= 10);
for (const c of poses) {
  const m = gridMove(c.source.location, c.source.rotation, c.pose.location, c.pose.rotation, c.origin);
  assert.deepEqual([m.valid, m.why, m.turns], [c.valid, c.why, c.turns], c.case);
  near(m.translation, c.translation, 1e-3, c.case);
  const n = nearestGridPose(c.source.location, c.source.rotation, c.pose.location, c.pose.rotation, c.origin);
  assert.deepEqual(n.rotation, c.nearest.rotation, c.case);
  near(n.location, c.nearest.location, 1e-3, c.case);
}

// the building floors: the floor a box stands in, and a copy's listings
const floors = read('../../bake/tests/floor_membership_cases.json');
assert.ok(floors.floorAt.length && floors.copyFloors.length);
for (const c of floors.floorAt) {
  const at = floorAt(c.buildings.map(list => ({ floors: list.map(boxes => ({ boxes })) })), c.box);
  assert.deepEqual(at ? [at.building, at.floor] : null, c.at, c.case);
}
for (const c of floors.copyFloors) {
  const got = copyFloors(c.listings.map(([building, floor, cutdownFloor]) => ({ building, floor, cutdownFloor })),
                         c.here && { building: c.here[0], floor: c.here[1] }, c.there && { building: c.there[0], floor: c.there[1] },
                         b => c.floors[b]);
  assert.deepEqual(got.map(l => [l.building, l.floor, l.cutdownFloor]), c.expect, c.case);
}

// a prefab test's stage height
const stages = read('../../editor/tests/stage_levels_cases.json').cases;
for (const [top, levels] of stages) assert.equal(prefabStageLevels([0, 0, 0, 96, 96, top]), levels, String(top));

// the wall joints: compiler.wall_joins' cases (test_compiler_generated.py), through walls.js wallJoins
const joints = read('../../editor/tests/wall_join_cases.json').cases;
for (const c of joints) {
  const found = wallJoins(c.walls.map(w => ({ key: w.key, location: w.at, rotation: [0, w.yaw ?? 0, 0],
                                              wall: { x0: 0, x1: w.length ?? 384, openings: [], seed: 1, ...(w.storeys === 1 ? { storeys: 1 } : {}) } })));
  assert.deepEqual(Object.fromEntries(Object.entries(found).map(([k, v]) => [k, v.ends])), c.ends, c.case);
  for (const [key, joins] of Object.entries(c.joins ?? {})) assert.deepEqual(found[key].joins, joins, c.case);
}
// free-form walls at any angle: made_edits.free_wall_joins' cases (test_compiler_free.py), through walls.js freeWallJoins
const freeJoints = read('../../editor/tests/free_join_cases.json').cases;
for (const c of freeJoints) {
  const found = freeWallJoins(c.walls.map(w => ({ key: w.key, location: w.at, rotation: [0, w.yaw, 0],
                                                  wall: { free: 1, x0: w.x0, x1: w.x1, y0: w.y[0], y1: w.y[1], z0: w.z[0], z1: w.z[1] } })));
  assert.deepEqual(Object.fromEntries(Object.entries(found).map(([k, v]) => [k, v.ends])), c.ends, c.case);
  assert.deepEqual(Object.fromEntries(Object.entries(found).map(([k, v]) => [k, v.joins.map(j => j.how)])), c.joins, c.case);
}
// where a world-aligned surface's texture is counted from: made_edits.mapping_origin's cases (test_compiler_free.py)
const origins = read('../../editor/tests/mapping_origin_cases.json').cases;
assert.ok(origins.length >= 10);
for (const c of origins) assert.deepEqual(mappingOrigin(c.kind, c.mapping ?? null, c.location, c.rotation), c.origin, c.case);
console.log(`shared_cases_test: ok (${cones.length} cones, ${poses.length} poses, ${floors.floorAt.length + floors.copyFloors.length} floor `
  + `cases, ${stages.length} stage heights, ${joints.length} wall joints, ${freeJoints.length} free-form joints, `
  + `${origins.length} texture origins)`);
