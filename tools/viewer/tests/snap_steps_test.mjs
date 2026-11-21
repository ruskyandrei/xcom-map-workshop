// The one snap policy (snap_steps.js; the custom geometry improvements plan, section 3). Run: node
// tools/viewer/tests/snap_steps_test.mjs
import assert from 'node:assert/strict';
import { SNAP_STEPS, stepped, steppedMove, stepsOf } from '../web/snap_steps.js';

// the table: off continuous, fine 24 and 15°, tile 96 across, 64 up and 90°
assert.deepEqual(SNAP_STEPS.off, { across: 0, up: 0, turn: 0 });
assert.deepEqual(SNAP_STEPS.fine, { across: 24, up: 24, turn: 15 });
assert.deepEqual(SNAP_STEPS.tile, { across: 96, up: 64, turn: 90 });
assert.equal(stepsOf('nonsense'), SNAP_STEPS.off);
assert.ok(Object.isFrozen(SNAP_STEPS.fine));

// a distance in whole steps; a step of 0 leaves it, to fractions of a unit
assert.equal(stepped(0.375, 0), 0.375);
assert.equal(stepped(35.9, 24), 24);
assert.equal(stepped(36, 24), 48);
assert.equal(stepped(-36, 24), -24);         // (halves toward +infinity, as Math.round)
assert.ok(Object.is(stepped(-3, 24), 0));    // never -0
assert.equal(stepped(-50, 96), -96);

// a move in game axes: across by the across step, up by the up step
assert.deepEqual(steppedMove([37.3, -50.2, 10.7], 'off'), [37.3, -50.2, 10.7]);
assert.deepEqual(steppedMove([37.3, -50.2, 10.7], 'fine'), [48, -48, 0]);
assert.deepEqual(steppedMove([150, -50.2, 40], 'tile'), [192, -96, 64]);

console.log('snap steps tests passed');
