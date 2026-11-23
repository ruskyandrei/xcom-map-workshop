// The kinds of mission on the page (missions.js; private/plans/done/mission-types-plan.md): an export's mission as a
// kind, the landing zones a mission uses, the play dialog's line, the kinds a project adds (the twin of missions.py's
// ADDED_KINDS), and the project's missions in its state (project.js). Run: node tools/viewer/tests/missions_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ADDED_KINDS, addedMission, carriedMapInfo, kindKey, mapInfoRecord, mapInfoWords, missionNote, missionTypes, tidyMapInfo,
         validMapInfo, zoneServes } from '../web/missions.js';
import { sortState, stateKey } from '../web/project.js';

// ---- the kind of an export's mission
assert.equal(kindKey({ type: 'Abduction', label: 'Abduction' }), 'Abduction');
assert.equal(kindKey({ type: 'Special', label: 'Council bomb' }), 'Special/Bomb');
assert.equal(kindKey({ type: 'Special', label: 'Something else' }), 'Special');
assert.equal(kindKey(null), '');
// export 37 says the kind itself (the label is taken only from an older export)
assert.equal(kindKey({ type: 'Special', label: 'Council bomb, reworded', kind: 'Special/Bomb' }), 'Special/Bomb');
assert.equal(kindKey({ type: 'Abduction', label: 'Abduction', kind: 'Abduction' }), 'Abduction');
assert.deepEqual(missionTypes({ type: 'Special', label: 'Council rescue' }), { missionType: 'eMission_Special', councilType: 'eFCMType_Rescue' });
// a zone kept for no mission serves every one; one kept for the bomb serves the bomb alone
const bomb = { type: 'Special', label: 'Council bomb' }, abduction = { type: 'Abduction', label: 'Abduction' };
assert.ok(zoneServes({}, bomb));
assert.ok(zoneServes({ missionType: 'eMission_Special', councilType: 'eFCMType_Bomb' }, bomb));
assert.ok(!zoneServes({ missionType: 'eMission_Special', councilType: 'eFCMType_Bomb' }, abduction));
assert.ok(zoneServes({ missionType: 'eMission_Abduction', councilType: 'eFCMType_None' }, abduction));

// ---- the play dialog's note: the state where it is a problem, what is missing, the notes, one paragraph each
const kinds = { Abduction: { words: 'Hangs at the start under Long War', missing: ['No civilian looks.'], notes: ['Enemies: four pods of Sectoids.'] } };
assert.equal(missionNote(kinds, abduction), 'Hangs at the start under Long War.\nNo civilian looks.\nEnemies: four pods of Sectoids.');
assert.equal(missionNote({ Abduction: { words: '', missing: [], notes: ['Enemies: four pods of Sectoids.'] } }, abduction),
             'Enemies: four pods of Sectoids.');
assert.equal(missionNote(kinds, bomb), '');
assert.equal(missionNote(null, abduction), '');

// ---- the kinds a project adds (D2): the same kinds as missions.py's ADDED_KINDS, Long War's and the UFO's marked
const python = readFileSync(new URL('../missions.py', import.meta.url), 'utf8');
const table = python.slice(python.indexOf('ADDED_KINDS = {'), python.indexOf('\n}', python.indexOf('ADDED_KINDS = {')));
assert.deepEqual(Object.keys(ADDED_KINDS), [...table.matchAll(/^ {4}'([^']+)': dict\(/gm)].map(m => m[1]));
for (const [kind, k] of Object.entries(ADDED_KINDS)) {
  const row = table.slice(table.indexOf(`'${kind}'`)).split(/\n {4}'/)[0];
  assert.equal(Boolean(k.lwr), /lwr=True/.test(row), kind);
  assert.equal(Boolean(k.ufo), /ufo=True/.test(row), kind);
  assert.ok(k.needs.length > 10, kind);
}
assert.deepEqual(addedMission('Special/Bomb'), { type: 'Special', label: 'Council bomb', streams: [], added: true });
assert.equal(kindKey(addedMission('Special/Bomb')), 'Special/Bomb');
assert.equal(kindKey(addedMission('Crash')), 'Crash');

// ---- the project's missions in its state: absent is null (every mission of the base map), and part of the key
const plain = sortState({ overrides: [], added: [] });
assert.equal(plain.missions, null);
const some = sortState({ overrides: [], added: [], missions: [{ record: 0 }, { kind: 'Crash', ship: 'eShip_UFOAbductor' }] });
assert.deepEqual(some.missions, [{ record: 0 }, { kind: 'Crash', ship: 'eShip_UFOAbductor' }]);
assert.notEqual(stateKey(plain), stateKey(some));
assert.notEqual(stateKey(some), stateKey(sortState({ overrides: [], added: [], missions: [{ record: 0 }] })));
assert.equal(stateKey(plain), stateKey(sortState({ overrides: [], added: [], missions: null })));

// ---- what Long War Rebalance is told of the map (the project's lwrMapInfo, schema 6; Map settings)
for (const good of [{}, { alienDensity: 'Light' }, { holdTheLine: 'No' }, { alienDensity: 'Swarming', holdTheLine: 'Yes' }]) assert.ok(validMapInfo(good), JSON.stringify(good));
for (const bad of [null, undefined, 'Moderate', ['Moderate'], { alienDensity: 'Huge' }, { alienDensity: 'moderate' }, { holdTheLine: false },
                   { alienDensity: 'Light', weather: 'Rain' }]) assert.ok(!validMapInfo(bad), JSON.stringify(bad));
// (one of texts the page can't read is carried; any other shape is dropped)
assert.ok(carriedMapInfo({ alienDensity: 'Huge' }) && carriedMapInfo({ weather: 'Rain' }));
assert.ok(!carriedMapInfo({ holdTheLine: false }) && !carriedMapInfo('Moderate') && !carriedMapInfo(null));
assert.deepEqual(Object.keys(tidyMapInfo({ holdTheLine: 'No', alienDensity: 'Heavy' })), ['alienDensity', 'holdTheLine']);
assert.equal(tidyMapInfo({}), null);
// the window's controls: a size or none, Hold the Line kept off or not
assert.equal(mapInfoRecord('', false), null);
assert.deepEqual(mapInfoRecord('Moderate', false), { alienDensity: 'Moderate' });
assert.deepEqual(mapInfoRecord('', true), { holdTheLine: 'No' });
assert.deepEqual(mapInfoRecord('Heavy', true, { alienDensity: 'Light' }), { alienDensity: 'Heavy', holdTheLine: 'No' });
assert.equal(mapInfoRecord('Enormous', false), null);
// (a Yes written by hand stays while Hold the Line is not kept off, and goes when it is)
assert.deepEqual(mapInfoRecord('Light', false, { holdTheLine: 'Yes' }), { alienDensity: 'Light', holdTheLine: 'Yes' });
assert.deepEqual(mapInfoRecord('', true, { holdTheLine: 'Yes' }), { holdTheLine: 'No' });
assert.equal(mapInfoWords({ alienDensity: 'Moderate', holdTheLine: 'No' }), 'abductions up to Moderate, no Hold the Line');
assert.equal(mapInfoWords(null), '');
// in the project's state: absent is null, an empty one says nothing, and it is part of the key
assert.equal(plain.lwrMapInfo, null);
assert.equal(sortState({ overrides: [], added: [], lwrMapInfo: {} }).lwrMapInfo, null);
const told = sortState({ overrides: [], added: [], lwrMapInfo: { holdTheLine: 'No', alienDensity: 'Moderate' } });
assert.deepEqual(told.lwrMapInfo, { alienDensity: 'Moderate', holdTheLine: 'No' });
assert.notEqual(stateKey(plain), stateKey(told));
assert.equal(stateKey(told), stateKey(sortState({ overrides: [], added: [], lwrMapInfo: { alienDensity: 'Moderate', holdTheLine: 'No' } })));
assert.notEqual(stateKey(told), stateKey(sortState({ overrides: [], added: [], lwrMapInfo: { alienDensity: 'Moderate' } })));
// one a newer editor wrote is carried as saved; another shape is dropped
assert.deepEqual(sortState({ overrides: [], added: [], lwrMapInfo: { alienDensity: 'Huge' } }).lwrMapInfo, { alienDensity: 'Huge' });
assert.equal(sortState({ overrides: [], added: [], lwrMapInfo: 'Moderate' }).lwrMapInfo, null);
console.log('missions_test: ok');
