// Looks named by their donor on the page (looks.js, walls.js wallSpec; custom geometry plan, M4): the catalogue read
// once, a donor look found by its mesh (a ground look by its mesh and material), the look the drawing tools take, and
// a wall's heights, insets and storeys by its look. Run: node tools/viewer/tests/looks_test.mjs
import assert from 'node:assert/strict';
import { catalogued, donorLook, entryForPiece, forgetLooks, loadLooks, lookFromEntry, lookTags, lookWords } from '../web/looks.js';
import { endInsetsOf, faceTopOf, raisedWall, storeysOf, topMostOf, wallSpec, wallTop, wallWords, withOpening, toolWall,
         openingKind, storeysInLook, storeyWords } from '../web/walls.js';

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

// a wall's heights by its look: a one-storey donor stands at its own height, which its top handle doesn't change
const one = { x0: 0, x1: 384, openings: [], seed: 1, look: { mesh: ONE.mesh, measure: 1 } };
assert.deepEqual([storeysOf(one), wallTop(one), faceTopOf(one), topMostOf(one)], [1, 192, 180, 168]);
assert.equal(raisedWall(one, 400).wall, one);
assert.deepEqual(endInsetsOf(one), { free: 4, line: 0, through: -6 });
assert.equal(wallSpec(one).half, 7);
// a two-storey donor: one storey lower loses its storey off the top
const tall = { ...one, look: { mesh: TALL.mesh, measure: 1 } };
assert.deepEqual([storeysOf(tall), wallTop(tall), faceTopOf(tall)], [2, 400, 380]);
const low = raisedWall(tall, -150).wall;
assert.deepEqual([storeysOf(low), wallTop(low), faceTopOf(low)], [1, 200, 180]);
assert.equal(wallWords(low), '4 tiles long, one storey (216 tall)');
// a three-storey donor: one storey loses both storeys over its first; its top handle and button go between 1 and 3
const three = { ...one, look: { mesh: THREE.mesh, measure: 1 } };
assert.deepEqual([storeysOf(three), wallTop(three), wallSpec(three).lower], [3, 576, true]);
const low3 = raisedWall(three, -200).wall;
assert.deepEqual([storeysOf(low3), wallTop(low3)], [1, 192]);
assert.equal(raisedWall(three, -100).wall, three);          // (under half the 384 it would lose)
assert.ok(!('storeys' in raisedWall(low3, 200).wall));
assert.equal(wallWords(three), '4 tiles long, three storeys (592 tall)');
assert.equal(storeyWords(1), 'one storey');
// a look made at its donor's height only: no lower wall, and a one-storey wall changed to it takes its storeys
const gable = { ...one, look: { mesh: ONLY_TWO.mesh, measure: 1 } };
assert.deepEqual([storeysOf(gable), wallSpec(gable).lower], [2, false]);
assert.equal(raisedWall(gable, -300).wall, gable);
assert.equal(storeysInLook(low, gable), 2);
assert.equal(storeysInLook(low, three), 1);
assert.equal(storeysInLook(tall, three), 3);
// a doorway reaches the look's bottom
const door = withOpening(tall, 'doorway').wall.openings[0];
assert.deepEqual([door.z0, openingKind(door)], [-16, 'doorway']);
assert.equal(withOpening(one, 'doorway').wall.openings[0].z0, 0);
assert.ok(toolWall(withOpening(one, 'doorway').wall));
// a donor look whose catalogue holds nothing is drawn as the Bar's
const unknown = { ...one, look: { mesh: 'Nowhere.Meshes.Wall', measure: 1 } };
assert.deepEqual([wallTop(unknown), endInsetsOf(unknown).free], [384, 8]);
console.log('looks: ok');
