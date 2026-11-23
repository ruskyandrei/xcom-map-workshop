// The copy carried to another map or prefab (carried_clip.js; the editor controls and clipboard plan, Part C). Run:
// node tools/viewer/tests/carried_clip_test.mjs
import assert from 'node:assert/strict';
import { CARRIED_FORMAT, CARRIED_WORDS, packCarried, unpackCarried } from '../web/carried_clip.js';

const copy = {
  id: 'c1', from: { map: 'URB_Bar', prefab: null, project: 'p1' }, name: 'Desk and 2 other pieces', words: '3 pieces and 1 light',
  pivot: [96, 192, 0], pivotActor: 'TheWorld.PersistentLevel.Desk_copy1',
  pieces: [{ actor: 'TheWorld.PersistentLevel.Desk_copy1', from: { package: 'URB_Bar', level: 'base', actor: 'TheWorld.PersistentLevel.Desk' },
             components: ['TheWorld.PersistentLevel.Desk.StaticMeshComponent_0'], location: [96, 192, 0], rotation: [0, 16384, 0], prefab: null, partner: null,
             tinted: true, flags: { walking: 'off' } }],
  groups: [{ id: 'g1', breakTogether: false, members: [{ added: 'TheWorld.PersistentLevel.Desk_copy1' }, { building: 'b1' }] }],
  buildings: [{ id: 'b1', name: 'Shed', kind: 'building', floors: [{ boxes: [[0, 0, 0, 192, 192, 192]] }] }],
  donors: [{ package: 'URB_Bar', sha256: 'a'.repeat(64) }], left: ['Lamp: a piece of a level the mission streams in, not of a map'],
};

// packed and unpacked, the records come back as they were
const { text } = packCarried(copy);
const back = unpackCarried(text).doc;
assert.equal(back.format, CARRIED_FORMAT);
for (const key of ['id', 'from', 'name', 'words', 'pivot', 'pivotActor', 'pieces', 'groups', 'buildings', 'donors', 'left']) assert.deepEqual(back[key], copy[key], key);
assert.equal(back.boxes, undefined);
// the Buildings view's boxes go along when they are the copy
const boxes = [{ box: [0, 0, 0, 96, 96, 64], building: 'b2', floor: 0, meta: { name: 'Hut', kind: 'building' } }];
assert.deepEqual(unpackCarried(packCarried({ ...copy, boxes }).text).doc.boxes, boxes);

// a landing zone or marks go along as `thing`; a broken one is refused
const zone = { kind: 'zone', zone: { direction: 'east', kind: 'normal', location: [96, 192, 64] } };
assert.deepEqual(unpackCarried(packCarried({ ...copy, pieces: [], groups: [], buildings: [], thing: zone }).text).doc.thing, zone);
const marks = { kind: 'marks', marks: [{ offset: [0, 0, 0], toward: [[1, 1]], low: [] }, { offset: [1, 0, 0], toward: [[-1, 1]], low: [[-1, 1]] }] };
assert.deepEqual(unpackCarried(packCarried({ ...copy, thing: marks }).text).doc.thing, marks);
assert.deepEqual(unpackCarried(JSON.stringify({ ...JSON.parse(text), thing: { kind: 'zone', zone: {} } })), { error: CARRIED_WORDS.unread });
// (a zone whose height is unset, the ground's, goes along as it is)
const low = { kind: 'zone', zone: { direction: 'north', location: [96, 192, null] } };
assert.deepEqual(unpackCarried(packCarried({ ...copy, thing: low }).text).doc.thing, low);

// nothing kept: none; a text that isn't one, or of another format, is refused with its sentence
assert.equal(unpackCarried(null), null);
assert.equal(unpackCarried(''), null);
assert.deepEqual(unpackCarried('{not json'), { error: CARRIED_WORDS.unread });
assert.deepEqual(unpackCarried(JSON.stringify({ ...JSON.parse(text), format: 2 })), { error: CARRIED_WORDS.otherFormat });
assert.deepEqual(unpackCarried(JSON.stringify({ ...JSON.parse(text), pieces: {} })), { error: CARRIED_WORDS.unread });
assert.deepEqual(unpackCarried(JSON.stringify({ ...JSON.parse(text), pivot: [1, 2] })), { error: CARRIED_WORDS.unread });

// too large: a small marker is kept instead, which says so on arrival
const large = packCarried(copy, 200);
assert.equal(large.text, undefined);
assert.ok(large.tooLarge.length < 200);
assert.deepEqual(unpackCarried(large.tooLarge), { tooLarge: copy.name, id: 'c1' });
assert.equal(CARRIED_WORDS.tooLarge('Desk'), 'Desk was too large to bring along: save it as a prefab to place it in another map');

console.log('carried_clip: ok');
