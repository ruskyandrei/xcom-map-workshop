// The Spawns view's records (spawns_view.js; editor spawns implementation plan, SP3): the one list both controls draw
// for a base map, a mission's streams, an added bomb's donor and an LWR patch; one marker an objective; the families;
// the panel's lines. Run: node tools/viewer/tests/spawns_view_test.mjs
import assert from 'node:assert/strict';
import { FAMILIES, KINDS, describe, familyOf, groupOf, identityLines, marked, shownEntries, spawnKey, spawnRecords, titleOf } from '../web/spawns_view.js';
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
console.log('spawns view: ok');
