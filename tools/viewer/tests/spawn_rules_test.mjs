// What the game does with a spawn point (spawn_rules.js; editor spawns implementation plan, SP2): the inspector's
// "In the game" lines for each row of the plan's table, on plain Enemy Within and with Long War's mutators active, and
// the uses in words. Run: node tools/viewer/tests/spawn_rules_test.mjs
import assert from 'node:assert/strict';
import { consumerWords, fromWords, scriptedUsers, useLines, waveWords } from '../web/spawn_rules.js';

const LWR = { kind: 'lwr', landing: 'active', bomb: 'active', meld: 'active', pods: 'active', dropIns: 'active',
              config: { dropMin: 7, dropMax: 32, meldContainers: 3 } };
const EW = { kind: 'ew', landing: 'absent', bomb: 'absent', meld: 'absent', pods: 'absent', dropIns: 'absent', config: {} };
const abduction = { type: 'Abduction', label: 'Abduction' }, hq = { type: 'HQAssault', label: 'Base defence' };
const base = { type: 'AlienBase', label: 'Alien base' }, crash = { type: 'Crash', label: 'Crashed UFO' };
const bomb = { type: 'Special', label: 'Council bomb' }, terror = { type: 'TerrorSite', label: 'Terror' };
const has = (lines, text) => lines.some(l => l.includes(text));

// ---- pods
const pod = { kind: 'pod', values: { podIndex: { value: 0 }, commander: { value: false }, use: { value: true } }, uses: [] };
let w = consumerWords(pod, { rules: EW, mission: abduction });
assert.ok(has(w, 'One of the places the game deploys pods at'));
assert.ok(!has(w, 'Long War'));
w = consumerWords(pod, { rules: LWR, mission: abduction });
assert.ok(has(w, 'Long War replaces the map\'s pods'));
assert.ok(has(consumerWords(pod, { rules: LWR, mission: hq }), 'Long War leaves the pods of Base defence'));
const commander = { ...pod, values: { ...pod.values, commander: { value: true } } };
assert.ok(has(consumerWords(commander, { rules: LWR, mission: base }), 'keeps the commander\'s place'));
assert.ok(has(consumerWords(pod, { rules: LWR, mission: crash }), 'inside the UFO'));
assert.ok(has(consumerWords({ ...pod, values: { ...pod.values, use: { value: false } } }, { rules: EW }), 'Use is off'));

// ---- Meld
const meld = { kind: 'meld', values: { difficulty: { value: 'Hard' }, destroyedOnTurn: { value: 8 }, spawnGroup: { value: 1 } } };
w = consumerWords(meld, { rules: EW, mission: abduction });
assert.ok(has(w, 'spawn group (1), a hard one first'));
assert.ok(has(w, 'Hard; it is destroyed on turn 8'));
assert.ok(!has(w, 'Long War'));
assert.ok(has(consumerWords(meld, { rules: LWR, mission: abduction }), 'replaces every Meld point when it finds 3 places'));
assert.ok(has(consumerWords(meld, { rules: EW, mission: terror }), 'Terror spawns no Meld'));
assert.ok(has(consumerWords({ kind: 'meld', values: { destroyedOnTurn: { value: -1 } } }, { rules: EW }), 'no countdown'));

// ---- scripted and wave drop-ins
const scripted = { kind: 'dropIn', uses: [{ by: 'SeqAct_SpawnAlien_4', byClass: 'SeqAct_SpawnAlien', how: 'direct', link: 'SpawnPoints' }] };
const listed = { kind: 'dropIn', uses: [{ by: 'SeqAct_AccessObjectList_2', byClass: 'SeqAct_AccessObjectList', how: 'indirect', link: 'Object List', then: ['SeqAct_SpawnAlien_1'] }] };
assert.deepEqual(scriptedUsers(scripted), ['SeqAct_SpawnAlien_4']);
assert.deepEqual(scriptedUsers(listed), ['SeqAct_SpawnAlien_1']);
w = consumerWords(scripted, { rules: EW });
assert.deepEqual(w, ['Used by SeqAct_SpawnAlien_4.']);
w = consumerWords(scripted, { rules: LWR });
assert.ok(has(w, 'near a soldier instead (7 to 32 tiles)'));
assert.ok(has(consumerWords(scripted, { rules: LWR, placed: true }), 'plays here'));
assert.ok(has(consumerWords(scripted, { rules: LWR, mapExcluded: true }), 'names the base map, not the variant'));
const wave = { kind: 'dropIn', uses: [{ how: 'wave', by: 'XComWaveSystem_0', set: 1, wave: 2, group: 3, index: 1, role: 'destination' }] };
w = consumerWords(wave, { rules: LWR });
assert.ok(has(w, 'Destination of XComWaveSystem_0 set 1, wave 2, group 3'));
assert.ok(has(w, 'does not move a wave\'s units'));
assert.ok(!has(w, 'near a soldier'));
assert.ok(has(consumerWords({ kind: 'dropIn', uses: [] }, { rules: EW }), 'Nothing in its package'));

// ---- the bomb and the nodes; the landing
assert.deepEqual(consumerWords({ kind: 'bomb' }, { rules: EW, mission: bomb }), ['Plays where it stands.']);
assert.ok(has(consumerWords({ kind: 'powerNode' }, { rules: LWR, mission: bomb }), 'they play here when it doesn\'t'));
assert.ok(has(consumerWords({ kind: 'soldier', tag: 'Group0' }, { rules: LWR, mission: abduction }), 'one of the map\'s landing lines'));
assert.ok(has(consumerWords({ kind: 'start' }, { rules: EW }), 'The squad\'s landing'));
assert.ok(has(consumerWords({ kind: 'soldier' }, { rules: LWR, mission: { type: 'CaptureAndHold', label: 'Data recovery' } }), 'leaves the landing of Data recovery'));
// rules not read yet, or a family unread
assert.ok(has(consumerWords(pod, { rules: null }), 'still being read'));
assert.ok(has(consumerWords(pod, { rules: { ...LWR, pods: 'unknown' } }), 'could not be read'));

// ---- uses in words
assert.equal(waveWords({ role: 'origin', by: 'XComWaveSystem_1', set: 17, wave: 1, group: 1 }), 'origin of XComWaveSystem_1 set 17, wave 1, group 1');
const lines = useLines({ uses: [...scripted.uses, ...listed.uses, ...wave.uses, { how: 'event', by: 'SeqEvent_OnRevealPod_0', podId: 2 },
                               { how: 'typed', by: 'XComAlienPod_3', property: 'ContingentPods' }, { how: 'variable', by: 'SeqVar_Object_9', link: 'ObjValue' }],
                        links: [{ property: 'PathNodes', actor: 'TheWorld.PersistentLevel.XComAlienPathNode_4' }] });
assert.deepEqual(lines.usedBy, ['SeqAct_SpawnAlien_4 SpawnPoints', 'SeqAct_AccessObjectList_2 Object List (an object list, then SeqAct_SpawnAlien_1)',
                                'destination of XComWaveSystem_0 set 1, wave 2, group 3', 'SeqEvent_OnRevealPod_0 (fires when pod 2 is revealed)',
                                'XComAlienPod_3\'s ContingentPods', 'SeqVar_Object_9 (a Kismet variable nothing reads)']);
assert.deepEqual(lines.uses, ['PathNodes: XComAlienPathNode_4']);
assert.equal(fromWords('saved'), '(the map\'s)');
assert.equal(fromWords('class'), '(the class\'s)');
console.log('spawn rules: ok');
