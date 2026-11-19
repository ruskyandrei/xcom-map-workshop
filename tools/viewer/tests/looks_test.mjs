// Looks named by their donor on the page (looks.js, walls.js wallSpec; custom geometry plan, M4): the catalogue read
// once, a donor look found by its mesh (a ground look by its mesh and material), the look the drawing tools take, and
// a wall's heights, insets and storeys by its look. Run: node tools/viewer/tests/looks_test.mjs
import assert from 'node:assert/strict';
import { catalogued, donorLook, entryForPiece, forgetLooks, loadLooks, lookFromEntry, lookTags, lookWords } from '../web/looks.js';
import { endInsetsOf, faceTopOf, raisedWall, storeysOf, topMostOf, wallSpec, wallTop, wallWords, withOpening, toolWall,
         openingEdges, storeysInLook, storeyWords, openingsInLook } from '../web/walls.js';

const ONE = { mesh: 'Shop.Meshes.ShopWall_FRACTURED', map: 'URB_Shop', actor: 'XComFracLevelActor_12', maps: { URB_Shop: 3 },
              name: 'Shop wall', setting: 'shop interior', lwrOnly: false, warnings: [], twin: 'ok',
              facts: { size: { length: 576, height: 192, thickness: 14 }, inside: true, storeys: [1], verdict: 'swept' },
              recipe: { bottom: 0, top: 192, storey: null, face: [0, 180], half: 6, endInset: 4, sections: 3 } };
const TALL = { mesh: 'Ware.Meshes.WareWall_FRACTURED', map: 'URB_Ware', actor: 'XComDecoFracLevelActor_2', maps: { URB_Ware: 1 },
               name: 'Warehouse wall', setting: 'brick', lwrOnly: true, warnings: ["its window frames and ledges aren't made"],
               twin: 'ok', facts: { size: { length: 960, height: 400, thickness: 20 }, inside: false, storeys: [1, 2], verdict: 'modelled' },
               recipe: { bottom: -16, top: 400, storey: 200, face: [8, 380], half: 9, endInset: 8, sections: 5 } };
const THREE = { mesh: 'Out.Meshes.OutpostWall_FRACTURED', map: 'URB_Outpost', actor: 'XComDecoFracLevelActor_4', maps: {},
                name: 'Outpost wall', setting: 'stucco', lwrOnly: false, warnings: [], twin: 'ok',
                facts: { size: { length: 768, height: 592, thickness: 24 }, inside: false, storeys: [1, 3], verdict: 'swept' },
                recipe: { bottom: -16, top: 576, storey: 192, face: [12, 576], half: 12, endInset: 8, sections: 4 } };
const ONLY_TWO = { ...TALL, mesh: 'Ware.Meshes.Gable_FRACTURED', facts: { ...TALL.facts, storeys: [2] } };
const GRASS = { mesh: 'Farm.Meshes.Plane', material: 'Farm.Materials.Grass', map: 'CSmallScout_Farm', actor: 'XComLevelActor_7',
                maps: {}, name: 'Grass', setting: 'farm', lwrOnly: false, warnings: [], twin: 'ok',
                facts: { thickness: 8, painted: true }, recipe: { thickness: 8, repeat: 256, sections: 1 } };
const answers = { '/looks/walls.json': { kind: 'wall', measure: 1, looks: [ONE, TALL, THREE, ONLY_TWO] },
                  '/looks/ground.json': { kind: 'ground', measure: 1, looks: [GRASS] } };
let asked = 0;
const fetcher = async url => { asked++; return { ok: url in answers, json: async () => answers[url] }; };

forgetLooks();
await Promise.all([loadLooks('wall', fetcher), loadLooks('wall', fetcher), loadLooks('ground', fetcher), loadLooks('slab', fetcher)]);
assert.equal(asked, 3);                      // (read once each)
assert.equal(catalogued('wall', { mesh: ONE.mesh, measure: 1 }), ONE);
assert.equal(catalogued('wall', 'bar-inside'), null);
assert.equal(catalogued('ground', { mesh: GRASS.mesh, material: GRASS.material, measure: 1 }), GRASS);
assert.equal(catalogued('ground', { mesh: GRASS.mesh, material: 'Farm.Materials.Mud', measure: 1 }), null);
assert.equal(entryForPiece('wall', TALL.mesh), TALL);
assert.deepEqual(donorLook('ground', GRASS), { mesh: GRASS.mesh, material: GRASS.material, measure: 1 });

// the look the tools take: the catalogue's placing, or the one chosen (a library row's, a piece in the view)
let look = lookFromEntry('wall', ONE);
assert.deepEqual([look.package, look.actor, look.donor], ['URB_Shop', 'XComFracLevelActor_12', { mesh: ONE.mesh, measure: 1 }]);
look = lookFromEntry('wall', TALL, { package: 'URB_Ware_Night', actor: 'TheWorld.PersistentLevel.XComDecoFracLevelActor_9' });
assert.deepEqual([look.package, look.actor, look.lwrOnly], ['URB_Ware_Night', 'XComDecoFracLevelActor_9', true]);
assert.match(lookWords('wall', TALL), /brick, 960 long and 400 tall in its map, an outside wall/);
assert.deepEqual(lookTags(TALL).map(t => t[0]), ['Simpler', 'LWR']);
// plain ends alone don't mark a look Simpler (most walls have them); with another warning they are listed too
const ends = "the detail at its ends (a corner or a jamb) isn't made: its ends are plain";
assert.deepEqual(lookTags({ ...ONE, warnings: [ends] }), []);
assert.match(lookTags({ ...TALL, warnings: [ends, ...TALL.warnings] })[0][1], /plain; its window frames/);

// a wall's heights by its look: a one-storey donor stands at its own height; its top handle stacks it (B4)
const one = { x0: 0, x1: 384, openings: [], seed: 1, look: { mesh: ONE.mesh, measure: 1 } };
assert.deepEqual([storeysOf(one), wallTop(one), faceTopOf(one), topMostOf(one)], [1, 192, 180, 168]);
assert.deepEqual([storeysOf(raisedWall(one, 400).wall), wallTop(raisedWall(one, 400).wall)], [3, 576]);
assert.deepEqual(endInsetsOf(one), { free: 4, line: 0, through: -6 });
assert.equal(wallSpec(one).half, 7);
// a two-storey donor: one storey lower loses its storey off the top
const tall = { ...one, look: { mesh: TALL.mesh, measure: 1 } };
assert.deepEqual([storeysOf(tall), wallTop(tall), faceTopOf(tall)], [2, 400, 380]);
const low = raisedWall(tall, -150).wall;
assert.deepEqual([storeysOf(low), wallTop(low), faceTopOf(low)], [1, 200, 180]);
assert.equal(wallWords(low), '4 tiles long, one storey (216 tall)');
// a three-storey donor: one storey loses both storeys over its first; two are two one-storey pieces stacked (B4)
const three = { ...one, look: { mesh: THREE.mesh, measure: 1 } };
assert.deepEqual([storeysOf(three), wallTop(three), wallSpec(three).lower], [3, 576, true]);
const low3 = raisedWall(three, -390).wall;
assert.deepEqual([storeysOf(low3), wallTop(low3)], [1, 192]);
assert.equal(raisedWall(three, -80).wall, three);           // (under half a storey)
assert.deepEqual([storeysOf(raisedWall(three, -200).wall), wallTop(raisedWall(three, -200).wall)], [2, 400]);
assert.ok(!('storeys' in raisedWall(low3, 390).wall));
assert.equal(wallWords(three), '4 tiles long, three storeys (592 tall)');
assert.equal(storeyWords(1), 'one storey');
// a look made at its donor's height only: no lower wall, and a one-storey wall changed to it takes its storeys
const gable = { ...one, look: { mesh: ONLY_TWO.mesh, measure: 1 } };
assert.deepEqual([storeysOf(gable), wallSpec(gable).lower], [2, false]);
assert.equal(raisedWall(gable, -300).wall, gable);
assert.equal(storeysInLook(low, gable), 2);
assert.equal(storeysInLook(low, three), 1);
assert.equal(storeysInLook(tall, three), 3);
// a doorway starts with its threshold; cut to the floor, it reaches the look's bottom
const door = withOpening(tall, 'doorway').wall.openings[0];
assert.deepEqual([door.z0, openingEdges(tall, door).bottom], [8, false]);
assert.ok(openingEdges(tall, { ...door, z0: -16 }).bottom);
assert.equal(withOpening(one, 'doorway').wall.openings[0].z0, 8);
// a look of another bottom: a gap cut to the old bottom is cut to the new one, none starts below it, the rest stay
// (the user, 19 November 2026: a doorway from a look whose bottom is -16 kept it in one whose bottom is 0)
const gaps = { ...tall, openings: [{ x0: 0, x1: 96, z0: -16, z1: 160 }, { x0: 192, x1: 288, z0: 64, z1: 160 }] };
const moved = openingsInLook(gaps, { ...gaps, look: one.look });
assert.deepEqual(moved.openings.map(o => o.z0), [0, 64]);
assert.deepEqual(openingsInLook(moved, { ...moved, look: tall.look }).openings.map(o => o.z0), [-16, 64]);
assert.deepEqual(openingsInLook(gaps, { ...gaps, look: one.look, openings: [{ x0: 0, x1: 96, z0: -8, z1: 160 }] }).openings[0].z0, 0);
assert.equal(openingsInLook(one, one), one);
// a gap starting below its wall's bottom (a wall saved before that) is still the tool's: cut to the floor
const below = { ...one, x1: 2784, seed: 903191, openings: [{ x0: 1344, x1: 1440, z0: -16, z1: 160 }] };
assert.ok(toolWall(below) && openingEdges(below, below.openings[0]).bottom);
assert.ok(!toolWall({ ...below, openings: [{ x0: 1344, x1: 1440, z0: -40, z1: -20 }] }));
assert.ok(toolWall(withOpening(one, 'doorway').wall));
// a donor look whose catalogue holds nothing is drawn as the Bar's
const unknown = { ...one, look: { mesh: 'Nowhere.Meshes.Wall', measure: 1 } };
assert.deepEqual([wallTop(unknown), endInsetsOf(unknown).free], [384, 8]);
console.log('looks: ok');
