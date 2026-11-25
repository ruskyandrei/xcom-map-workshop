// The Spawns view's records (spawns_view.js; editor spawns implementation plan, SP3): the one list both controls draw
// for a base map, a mission's streams, an added bomb's donor and an LWR patch; one marker an objective; the families;
// the panel's lines. Run: node tools/viewer/tests/spawns_view_test.mjs
import assert from 'node:assert/strict';
import { FAMILIES, KINDS, NEW_VOLUME, SPAWN_VALUE_KEYS, addPlace, addTemplate, boxMiddle, boxWords, copyEntry, copyEntryOf, copyMarkerRecord, copyRecord,
         copyTemplateWhy, deletedEntry, describe, editCopy, editSpawn, familyOf, groupOf, identityLines, marked, recordBox, shownEntries, spawnEditable,
         spawnEntryOf, spawnKey, spawnMoveWords, spawnNamed, spawnOverride, spawnPosed, spawnRecords, titleOf, volumePlace } from '../web/spawns_view.js';
import { fromWords } from '../web/spawn_rules.js';

const L = 'TheWorld.PersistentLevel.';
const pod = (n, extra = {}) => ({ actor: `${L}XComAlienPod_${n}`, actorClass: 'XComAlienPod', kind: 'pod', location: [n * 96, 0, 0],
                                  values: { podIndex: { value: n, from: 'saved' }, use: { value: true, from: 'class' } }, listed: true, uses: [], links: [], ...extra });
const data = {
  name: 'URB_Test',
  spawns: [pod(0), pod(1),
           { actor: `${L}XComMeldContainerSpawnPoint_0`, actorClass: 'XComMeldContainerSpawnPoint', kind: 'meld', location: [0, 96, 0],
             values: { difficulty: { value: 'Hard', from: 'saved' }, destroyedOnTurn: { value: 8, from: 'saved' } }, listed: true },
           { actor: `${L}XComSpawnPoint_18`, actorClass: 'XComSpawnPoint', kind: 'soldier', location: [0, 0, 0], landing: 'PrefabInstance_19' },
           { actor: `${L}PlayerStart_2`, actorClass: 'PlayerStart', kind: 'start', location: [0, 0, 0], landing: 'PrefabInstance_19' },
           { actor: `${L}XComAlienPathNode_0`, actorClass: 'XComAlienPathNode', kind: 'pathNode', location: [0, 0, 0] }],
  streams: {
    URB_Test_Bomb: { kind: 'mission', missionObjects: [
      { actor: `${L}XComLevelActor_1`, actorClass: 'XComLevelActor', kind: 'bomb', group: 'bomb', role: 'bomb', location: [500, 500, 0] },
      { actor: `${L}XComInteractiveLevelActor_1`, actorClass: 'XComInteractiveLevelActor', kind: 'use', group: 'bomb', role: 'button', location: [500, 500, 0] },
      { actor: `${L}Emitter_1`, actorClass: 'Emitter', kind: 'part', group: 'bomb', role: 'effect', location: [500, 500, 0] },
      { actor: `${L}PointInSpace_0`, actorClass: 'PointInSpace', kind: 'part', group: 'bomb', role: 'point', location: [502, 500, 204] },
      { actor: `${L}XComLevelActor_2`, actorClass: 'XComLevelActor', kind: 'powerNode', group: 'node:XComLevelActor_2', role: 'node', location: [900, 0, 0] },
      { actor: `${L}XComAlienPod_0`, actorClass: 'XComAlienPod', kind: 'pod', location: [0, 900, 0] }] },
    patch_test: { kind: 'lwr', objects: [], spawns: [pod(7)] },
  },
  donors: { 'Special/Bomb': { stream: 'URB_Slaughterhouse_Stream', package: 'URB_Slaughterhouse_Stream.upk', missionObjects: [
    { actor: `${L}XComLevelActor_9`, actorClass: 'XComLevelActor', kind: 'bomb', group: 'bomb', role: 'bomb', location: [0, 0, 0] },
    { actor: `${L}PointInSpace_0`, actorClass: 'PointInSpace', kind: 'part', group: 'bomb', role: 'point', location: [2, 0, 204] }] } },
};

// ---- the base map alone: its points, but the landing's (its zone stands for them)
let entries = spawnRecords(data, []);
assert.deepEqual(entries.map(e => e.layer), ['base', 'base', 'base', 'base']);
assert.ok(!entries.some(e => e.record.landing));
assert.equal(entries[0].key, spawnKey(null, `${L}XComAlienPod_0`));
assert.equal(entries[0].key, `base|${L}XComAlienPod_0`);
// patrol nodes start off; the rest show
assert.deepEqual(shownEntries(entries).map(e => e.record.kind), ['pod', 'pod', 'meld']);
assert.deepEqual(shownEntries(entries, { paths: true, pods: false }).map(e => e.record.kind), ['meld', 'pathNode']);
assert.equal(FAMILIES.find(f => f.id === 'paths').on, false);
assert.equal(familyOf({ kind: 'bomb' }), 'objectives');
assert.equal(familyOf({ kind: 'mystery' }), 'other');

// ---- a mission: its stream's objects and the patch's points, one marker an objective
entries = spawnRecords(data, ['URB_Test_Bomb', 'patch_test']);
const stream = entries.filter(e => e.layer === 'stream'), patch = entries.filter(e => e.layer === 'patch');
assert.equal(stream.length, 6);
assert.deepEqual(patch.map(e => [e.readOnly, e.stream]), [[true, 'patch_test']]);
const markedKinds = shownEntries(entries).filter(e => e.layer === 'stream').map(e => `${e.record.kind}:${e.record.role ?? ''}`);
assert.deepEqual(markedKinds, ['bomb:bomb', 'use:button', 'powerNode:node', 'pod:']);     // the emitter and the helper point aren't marked
assert.ok(!marked({ kind: 'part', role: 'point' }));
const bomb = stream.find(e => e.record.kind === 'bomb');
assert.equal(groupOf(bomb, entries).length, 4);
assert.equal(titleOf(bomb, entries, 'Council bomb'), 'The bomb, Council bomb');
assert.equal(titleOf(patch[0], entries, 'Council bomb'), 'Pod, patch_test (Long War\'s patch)');
// two pods of the base map: numbered within their layer
const basePods = entries.filter(e => e.layer === 'base' && e.record.kind === 'pod');
assert.equal(titleOf(basePods[1], entries, null), 'Pod 2 of 2');

// ---- an added bomb: the donor's objects, unless a stream of the mission is the donor itself
const donor = { kind: 'Special/Bomb', ...data.donors['Special/Bomb'] };
entries = spawnRecords(data, [], donor);
const donors = entries.filter(e => e.layer === 'donor');
assert.equal(donors.length, 2);
assert.ok(donors.every(e => e.stream === 'URB_Slaughterhouse_Stream' && e.donor === 'Special/Bomb' && !e.readOnly));
assert.equal(titleOf(donors[0], entries, 'Council bomb (added)'), 'The bomb, Council bomb (added) (from URB_Slaughterhouse_Stream)');
assert.equal(spawnRecords(data, ['URB_Slaughterhouse_Stream'], donor).filter(e => e.layer === 'donor').length, 0);

// ---- the panel's lines: identity, values with where each comes from, the group
let lines = identityLines(entries.find(e => e.record.kind === 'meld'), entries, fromWords);
assert.equal(lines[0].text, 'XComMeldContainerSpawnPoint_0 (XComMeldContainerSpawnPoint).');
assert.equal(lines[1].head, 'Values');
assert.equal(lines[1].text, 'difficulty Hard (the map\'s); destroyed on turn 8 (the map\'s).');
lines = identityLines(bomb, spawnRecords(data, ['URB_Test_Bomb']), fromWords);
const group = lines.find(l => l.head === 'Group');
assert.ok(group.text.includes('Part of the bomb (the bomb); it moves with its button, an effect, its helper point'), group.text);
// an actor the level doesn't list, one whose values couldn't be read
lines = identityLines({ layer: 'base', record: { ...pod(3), listed: false, unread: 'bad bytes' } }, [], fromWords);
assert.ok(lines[0].text.includes('not in the level\'s list'));
assert.ok(lines[1].text.includes('could not be read (bad bytes)'));
// describe (the build window's lines): nothing lists it
const d = describe(entries.find(e => e.record.kind === 'meld'), entries, null);
assert.equal(d.title, 'Meld point');
assert.equal(d.lines.at(-1), 'Nothing in the map lists it by name.');
assert.ok(Object.values(KINDS).every(k => FAMILIES.some(f => f.id === k.family)));

// ---- base spawn point edits (SP6): a pod, a Meld point or a drop-in point moves alone, turns by quarters and takes
// the values of its kind; back where and as the map has it, it is no edit
const P = { ...pod(2), rotation: [0, -16384, 0], savesRotation: true, values: { ...pod(2).values, commander: { value: false, from: 'class' } } };
const M = data.spawns[2];
assert.ok(spawnEditable(P) && spawnEditable(M) && spawnEditable({ kind: 'dropIn', location: [0, 0, 0] }));
for (const o of [{ ...P, listed: false }, { ...P, unread: 'bad' }, { kind: 'soldier' }, { kind: 'noSpawn' }, null]) assert.ok(!spawnEditable(o));
assert.deepEqual(SPAWN_VALUE_KEYS.pod, ['commander', 'secondary', 'use']);
let edit = editSpawn(P, null, { delta: [96, 0, 0] });
assert.deepEqual(edit, { stream: null, actor: P.actor, location: [288, 0, 0], rotation: [0, -16384, 0], spawn: {} });
assert.ok(spawnPosed(edit, P));
assert.equal(editSpawn(P, edit, { delta: [-96, 0, 0] }), null);
// quarter turns: four bring it back; the yaw stays within half a turn of the map's
edit = editSpawn(P, null, { turn: 16384 });
assert.deepEqual(edit.rotation, [0, 0, 0]);
assert.equal(spawnMoveWords(P, edit), 'Turned a quarter right from where the map has it.');
edit = editSpawn(P, edit, { turn: 16384 }); edit = editSpawn(P, edit, { turn: 16384 });
assert.deepEqual(edit.rotation, [0, -32768, 0]);
assert.equal(editSpawn(P, edit, { turn: 16384 }), null);
edit = editSpawn(P, editSpawn(P, null, { delta: [192, 0, 64] }), { turn: -16384 });
assert.equal(spawnMoveWords(P, edit), 'Moved 2 tiles across, 1 level up and turned a quarter left from where the map has it.');
// values: one set to the map's goes; one of another value stays; undefined puts it back
edit = editSpawn(P, null, { spawn: { commander: true } });
assert.deepEqual(edit.spawn, { commander: true });
assert.equal(spawnMoveWords(P, edit), '');
assert.equal(editSpawn(P, edit, { spawn: { commander: false } }), null);
assert.equal(editSpawn(P, edit, { spawn: { commander: undefined } }), null);
assert.deepEqual(editSpawn(M, null, { spawn: { difficulty: 'Hard', destroyedOnTurn: 6 } }).spawn, { destroyedOnTurn: 6 });
// the override: the pose only when it moved or turned, the values when it has any
assert.deepEqual(spawnOverride('URB_Test', P, editSpawn(P, null, { spawn: { commander: true } })),
                 { target: { package: 'URB_Test', level: 'base', actor: P.actor }, spawn: { commander: true } });
assert.deepEqual(spawnOverride('URB_Test', P, editSpawn(P, null, { delta: [0, 96, 0] })),
                 { target: { package: 'URB_Test', level: 'base', actor: P.actor }, location: [192, 96, 0], rotation: [0, -16384, 0] });
// a saved override read back: whole pose, values or both, only its kind's keys; else carried (null)
const T = { package: 'URB_Test', level: 'base', actor: P.actor };
assert.deepEqual(spawnEntryOf(P, { target: T, spawn: { use: false } }),
                 { stream: null, actor: P.actor, location: [192, 0, 0], rotation: [0, -16384, 0], spawn: { use: false } });
assert.deepEqual(spawnEntryOf(P, { target: T, location: [0, 0, 0], rotation: [0, 0, 0] }).spawn, {});
for (const r of [{ target: T }, { target: T, deleted: true, spawn: {} }, { target: T, location: [0, 0, 0] }, { target: T, spawn: { difficulty: 'Hard' } },
                 { target: T, spawn: [] }, { target: T, spawn: { use: false }, flags: {} }]) assert.equal(spawnEntryOf(P, r), null, JSON.stringify(r));
assert.equal(spawnEntryOf({ ...P, kind: 'soldier' }, { target: T, spawn: {} }), null);
// the panel's values show the project's own as such
lines = identityLines({ layer: 'base', record: { ...M, values: { ...M.values, destroyedOnTurn: { value: 6, from: 'project' } } } }, [], fromWords);
assert.ok(lines[1].text.includes('destroyed on turn 6 (the project\'s)'), lines[1].text);

// ---- copies and deletes (SP7): a delete is an override of its own; a copy is an added record of a plain template
assert.deepEqual(spawnEntryOf(P, { target: T, deleted: true }), { stream: null, actor: P.actor, location: [192, 0, 0], rotation: [0, -16384, 0], spawn: {}, deleted: true });
assert.deepEqual(spawnOverride('URB_Test', P, spawnEntryOf(P, { target: T, deleted: true })), { target: T, deleted: true });
assert.equal(copyTemplateWhy(P), '');
assert.equal(copyTemplateWhy(M), '');
assert.ok(copyTemplateWhy({ ...P, values: { ...P.values, commander: { value: true } } }).includes('the commander\'s place'));
assert.ok(copyTemplateWhy({ ...P, links: [{ property: 'PathNode', actor: `${L}XComAlienPathNode_4` }] }).includes('linked to XComAlienPathNode_4'));
assert.ok(copyTemplateWhy({ kind: 'dropIn' }).includes('not copied'));
assert.ok(copyTemplateWhy({ ...P, listed: false }));
const C = copyEntry(P, { id: 'c1', actor: `${P.actor}_copy1`, location: [288, 0, 0], rotation: [0, -16384, 0] });
assert.deepEqual(C, { stream: 'copy', copy: { id: 'c1', kind: 'pod', from: P.actor }, actor: `${P.actor}_copy1`, location: [288, 0, 0], rotation: [0, -16384, 0], spawn: {} });
// a copy's values: one equal to its template's goes; turns stay within half a turn of its template's
let C2 = editCopy(P, C, { delta: [0, 96, 0], turn: 16384, spawn: { commander: true, use: true } });
assert.deepEqual([C2.location, C2.rotation, C2.spawn], [[288, 96, 0], [0, 0, 0], { commander: true }]);
C2 = editCopy(P, C2, { spawn: { commander: undefined } });
assert.deepEqual(C2.spawn, {});
const R = copyRecord('URB_Test', editCopy(P, C, { spawn: { use: false } }));
assert.deepEqual(R, { id: 'c1', kind: 'pod', actor: `${P.actor}_copy1`, from: T, location: [288, 0, 0], rotation: [0, -16384, 0], spawn: { use: false } });
assert.deepEqual(copyEntryOf(P, R), editCopy(P, C, { spawn: { use: false } }));
for (const bad of [{ ...R, kind: 'meld' }, { ...R, id: '' }, { ...R, location: [0, 0] }, { ...R, spawn: { difficulty: 'Hard' } }, { ...R, flags: {} }])
  assert.equal(copyEntryOf(P, bad), null, JSON.stringify(bad));
assert.equal(copyEntryOf({ ...P, values: { ...P.values, secondary: { value: true } } }, R), null);
// its marker's record: the template's under its own name, its values (the template's saved ones as its template's), named by nothing
const shown = copyMarkerRecord(P, editCopy(P, C, { spawn: { use: false } }));
assert.deepEqual([shown.actor, shown.location, shown.copyOf, shown.uses, shown.links], [`${P.actor}_copy1`, [288, 0, 0], P.actor, [], []]);
assert.deepEqual([shown.values.use, shown.values.podIndex.from, shown.values.commander.from], [{ value: false, from: 'project' }, 'project', 'class']);
assert.equal(copyMarkerRecord(M, copyEntry(M, { id: 'm', actor: 'x', location: [0, 0, 0], rotation: [0, 0, 0] })).values.difficulty.from, 'template');
assert.equal(fromWords('template'), '(its template\'s)');
// what names a point keeps its delete back
assert.ok(!spawnNamed(P));
assert.ok(spawnNamed({ ...P, uses: [{ how: 'event' }] }) && spawnNamed({ ...P, referencedBy: ['x'] }) && spawnNamed({ ...P, unread: 'bad' }));
// new spawn points from the Add panel (18 November 2026): a copy of the map's first plain pod or first Meld
// point, never a landing's point, a commander's pod or a point of another kind
assert.equal(addTemplate(data.spawns, 'pod').actor, `${L}XComAlienPod_0`);
assert.equal(addTemplate([{ ...pod(0), values: { commander: { value: true } } }, pod(3)], 'pod').actor, `${L}XComAlienPod_3`);
assert.equal(addTemplate(data.spawns, 'meld').actor, `${L}XComMeldContainerSpawnPoint_0`);
assert.equal(addTemplate(data.spawns, 'dropIn'), null);
assert.equal(addTemplate([{ ...pod(0), values: { forceType: { value: 'eChar_Sectoid' } } }], 'pod'), null);
assert.equal(addTemplate(undefined, 'pod'), null);
// placed on the tile under the click by whole tiles from its template, at its height above its own floor
const T48 = { location: [1968, 144, 48] };
assert.deepEqual(addPlace(T48, [2300, 10, 300], 256, 0), [2256, 48, 304]);
assert.deepEqual(addPlace(T48, [1960, 150, 40], null, null), [1968, 144, 40]);
assert.deepEqual(addPlace(T48, [1600, -210, 12], 0, null), [1584, -240, 0]);
assert.deepEqual(addPlace({ location: [0, 0, 900] }, [0, 0, 0], 0, 0), [0, 0, 128]);      // (a height over its floor kept to a level or two)

// ---- multiplayer teams' starts get no marker (18 November 2026); a deleted base point shows only with the
// flyout's Deleted points switch
const mp = n => ({ actor: `${L}XComSpawnPoint_${n}`, actorClass: 'XComSpawnPoint', kind: 'point', location: [0, 0, 0], unitType: n === 1 ? 8 : 9 });
assert.ok(!marked(mp(1)) && !marked(mp(2)));
assert.ok(marked({ kind: 'point', unitType: 1 }) && marked({ kind: 'loot', unitType: 4 }));
const withDeleted = spawnRecords({ spawns: [pod(0), pod(1), mp(1)] }, []), gone = e => e.record.actor.endsWith('_1') && e.record.kind === 'pod';
assert.deepEqual(shownEntries(withDeleted, {}, gone).map(e => e.record.actor), [`${L}XComAlienPod_0`]);
assert.deepEqual(shownEntries(withDeleted, { deleted: true }, gone).map(e => e.record.actor), [`${L}XComAlienPod_0`, `${L}XComAlienPod_1`]);
assert.equal(FAMILIES.find(f => f.id === 'deleted').on, false);

// ---- a no-spawn volume: moved and sized by its box, its two switches its values; copied, or made new (NEW_VOLUME)
const VOL = { actor: `${L}XComNoSpawnVolume_0`, actorClass: 'XComNoSpawnVolume', kind: 'noSpawn', location: [-384, -480, 96], rotation: [0, 0, 0],
              listed: true, box: { min: [-864, -576, 0], max: [-384, -384, 256] }, uses: [], links: [], referencedBy: [],
              values: { aliens: { value: true, from: 'class' }, civilians: { value: true, from: 'class' } } };
assert.ok(spawnEditable(VOL) && !spawnEditable({ ...VOL, box: null }));
assert.deepEqual(recordBox(VOL), [-864, -576, 0, -384, -384, 256]);
let ve = editSpawn(VOL, null, { delta: [96, 0, 64] });
assert.deepEqual(ve.box, [-768, -576, 64, -288, -384, 320]);
assert.deepEqual(ve.location, boxMiddle(ve.box));
assert.equal(editSpawn(VOL, ve, { delta: [-96, 0, -64] }), null);                  // back where the map has it
ve = editSpawn(VOL, null, { box: [-864, -576, 0, -192, -384, 256] });
assert.equal(spawnMoveWords(VOL, ve), 'Sized 7 by 2 tiles, 4 levels high (the map\'s is 5 by 2 tiles, 4 levels high) and moved 1 tile across from where the map has it.');
assert.deepEqual(spawnOverride('URB_Test', VOL, ve), { target: { package: 'URB_Test', level: 'base', actor: VOL.actor }, box: [-864, -576, 0, -192, -384, 256] });
const valued = editSpawn(VOL, null, { spawn: { civilians: false, aliens: true } });
assert.deepEqual([valued.spawn, spawnOverride('URB_Test', VOL, valued).box], [{ civilians: false }, undefined]);
assert.deepEqual(spawnEntryOf(VOL, spawnOverride('URB_Test', VOL, ve)), ve);
assert.deepEqual(spawnEntryOf(VOL, { target: {}, spawn: { aliens: false } }).spawn, { aliens: false });
assert.equal(spawnEntryOf(VOL, { target: {}, location: [0, 0, 0], rotation: [0, 0, 0] }), null);
assert.equal(spawnEntryOf(VOL, { target: {}, box: [0, 0, 0, 0, 1, 1] }), null);
assert.deepEqual(spawnEntryOf(VOL, { target: {}, deleted: true }), deletedEntry(VOL));
assert.deepEqual(deletedEntry(VOL).box, recordBox(VOL));
// copies: of the map's volume (its size), or a new one where the map has none to copy
assert.equal(copyTemplateWhy(VOL), '');
assert.equal(addTemplate([VOL], 'noSpawn'), VOL);
assert.equal(addTemplate([pod(0)], 'noSpawn'), NEW_VOLUME);
const grid = { origin: [-2784, -1920, 0], size: [96, 96, 64] };
// (5 by 2 tiles: the clicked tile third of five across, first of two up; the bottom on the floor's level)
assert.deepEqual(volumePlace(VOL, [-100, -100, 40], 64, grid), [-384, -192, 64, 96, 0, 320]);
assert.deepEqual(volumePlace(NEW_VOLUME, [10, 10, 0], null, grid), [-96, -96, 0, 192, 192, 256]);
const vc = copyEntry(NEW_VOLUME, { id: 'n', actor: `${L}XComNoSpawnVolume_copy1`, box: [-96, -96, 0, 192, 192, 256] });
assert.deepEqual([vc.copy.from, vc.location], [null, [48, 48, 128]]);
assert.deepEqual(copyRecord('URB_Test', vc), { id: 'n', kind: 'noSpawn', actor: `${L}XComNoSpawnVolume_copy1`, box: [-96, -96, 0, 192, 192, 256] });
assert.deepEqual(copyEntryOf(NEW_VOLUME, copyRecord('URB_Test', vc)), vc);
const vt = copyEntry(VOL, { id: 't', actor: `${VOL.actor}_copy2`, box: [0, 0, 0, 96, 96, 64], spawn: { aliens: false } });
assert.deepEqual(copyRecord('URB_Test', vt).from, { package: 'URB_Test', level: 'base', actor: VOL.actor });
assert.deepEqual(copyEntryOf(VOL, copyRecord('URB_Test', vt)), vt);
assert.equal(copyEntryOf(NEW_VOLUME, copyRecord('URB_Test', vt)), null);          // (a copy's record names its template)
assert.deepEqual(editCopy(VOL, vt, { delta: [96, 0, 0] }).box, [96, 0, 0, 192, 96, 64]);
assert.deepEqual(editCopy(VOL, vt, { spawn: { aliens: true } }).spawn, {});
assert.deepEqual(copyMarkerRecord(VOL, vt).box, { min: [0, 0, 0], max: [96, 96, 64] });
assert.equal(boxWords([0, 0, 0, 96, 96, 64]), '1 by 1 tile, 1 level high');
console.log('spawns view: ok');
