// A made piece's request and its plain look (web/made_requests.js): a donor look's request at its kind's donor
// version with the look in its numbers, a look id's at version 1, a plain one at its kind's plain version, which
// isPlain knows again; a plain piece's default look by its kind (a slab's by its role).
// Run: node tools/viewer/tests/made_requests_test.mjs
import assert from 'node:assert/strict';
import { isPlain, madeRequest, plainLook } from '../web/made_requests.js';
import { DONOR_VERSION } from '../web/looks.js';
import { GROUND_LOOKS } from '../web/ground.js';
import { SLAB_LOOKS, WALL_LOOKS } from '../web/walls.js';

const wall = { length: 384, height: 256 };
const donor = { donor: { package: 'URB_Bar', actor: 'XComDecoFracLevelActor_17' } };

// a donor look's request: its kind's donor version, the look inside the numbers (a copy, not the look's own object)
const asked = madeRequest('fracWall', donor, wall);
assert.deepEqual(asked, { kind: 'fracWall', version: DONOR_VERSION.wall, wall: { ...wall, look: donor.donor } });
assert.notEqual(asked.wall.look, donor.donor);
assert.equal(madeRequest('fracSlab', donor, { size: [2, 2] }).version, DONOR_VERSION.slab);
// a look without a donor (or none): version 1, the numbers as given
assert.deepEqual(madeRequest('fracWall', { id: 'x' }, wall), { kind: 'fracWall', version: 1, wall });
assert.deepEqual(madeRequest('fracSlab', null, { size: [1, 1] }), { kind: 'fracSlab', version: 1, slab: { size: [1, 1] } });
// plain: its kind's plain version, whatever the look; isPlain knows it, and not the others
for (const kind of ['fracWall', 'fracSlab']) {
  const plain = madeRequest(kind, donor, wall, true);
  assert.equal(isPlain(plain), true, kind);
  assert.equal(isPlain(madeRequest(kind, donor, wall)), false, `${kind} with a look`);
  assert.equal(isPlain(madeRequest(kind, null, wall)), false, `${kind} at version 1`);
}
assert.equal(isPlain(null), false);
assert.equal(isPlain(undefined), false);

// a plain piece's default look: the first wall look, the first ground look, a slab's by its role (a roof without one)
assert.deepEqual(plainLook('wall'), { ...WALL_LOOKS[0], plain: true });
assert.deepEqual(plainLook('ground'), { ...GROUND_LOOKS[0], plain: true });
const roof = SLAB_LOOKS.find(l => l.role === 'roof') ?? SLAB_LOOKS[0];
assert.deepEqual(plainLook('slab'), { ...roof, plain: true });
assert.equal(plainLook('slab').plain, true);

console.log('made_requests: ok');
