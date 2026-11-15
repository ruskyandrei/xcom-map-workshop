// The kinds of mission on the page (missions.js; private/plans/done/mission-types-plan.md): an export's mission as a
// kind, the landing zones a mission uses, the play dialog's line, the kinds a project adds (the twin of missions.py's
// ADDED_KINDS), and the project's missions in its state (project.js). Run: node tools/viewer/tests/missions_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ADDED_KINDS, ADDED_STATE, addedMission, kindKey, missionNote, missionTypes, zoneServes } from '../web/missions.js';
import { sortState, stateKey } from '../web/project.js';

// ---- the kind of an export's mission
assert.equal(kindKey({ type: 'Abduction', label: 'Abduction' }), 'Abduction');
assert.equal(kindKey({ type: 'Special', label: 'Council bomb' }), 'Special/Bomb');
assert.equal(kindKey({ type: 'Special', label: 'Something else' }), 'Special');
assert.equal(kindKey(null), '');
assert.deepEqual(missionTypes({ type: 'Special', label: 'Council rescue' }), { missionType: 'eMission_Special', councilType: 'eFCMType_Rescue' });
// a zone kept for no mission serves every one; one kept for the bomb serves the bomb alone
const bomb = { type: 'Special', label: 'Council bomb' }, abduction = { type: 'Abduction', label: 'Abduction' };
assert.ok(zoneServes({}, bomb));
assert.ok(zoneServes({ missionType: 'eMission_Special', councilType: 'eFCMType_Bomb' }, bomb));
assert.ok(!zoneServes({ missionType: 'eMission_Special', councilType: 'eFCMType_Bomb' }, abduction));
assert.ok(zoneServes({ missionType: 'eMission_Abduction', councilType: 'eFCMType_None' }, abduction));

// ---- the play dialog's note: the state, what is missing, the notes, one paragraph each
const kinds = { Abduction: { words: 'Played and working', missing: ['No civilian looks.'], notes: ['Enemies: four pods of Sectoids.'] } };
assert.equal(missionNote(kinds, abduction), 'Played and working.\nNo civilian looks.\nEnemies: four pods of Sectoids.');
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
assert.ok(python.includes(`ADDED_STATE = '${ADDED_STATE.replace(/\.$/, '')}'`));
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
console.log('missions_test: ok');
