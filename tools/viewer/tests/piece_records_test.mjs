// A copied piece's record (web/piece_records.js, review finding 6): a piece's state goes into its record and comes back
// the same, for made pieces (a wall with an opening, a floor, a shaped ground piece) and a broken copy of a map's
// fracturing piece, so a prefab saved from a selection and placed again keeps what each piece is.
// Run: node tools/viewer/tests/piece_records_test.mjs
import assert from 'node:assert/strict';
import { MADE_KINDS, PIECE_FIELDS, cloneBlasts, pieceState, recordFields, stateOf, stateOfRoot } from '../web/piece_records.js';

const wall = { kind: 'fracWall', version: 4, wall: { x0: 0, x1: 288, openings: [{ x0: 96, x1: 192, z0: 0, z1: 208 }], seed: 3 },
               blasts: [{ at: [48, 0, 96], radius: 96 }], breaksFurther: true };
const floor = { kind: 'fracSlab', version: 1, slab: { x0: 0, x1: 192, y0: 0, y1: 288, holes: [{ x0: 96, x1: 192, y0: 96, y1: 192 }], seed: 1, look: 'floor' } };
const ramp = { kind: 'ground', version: 1, ground: { shape: 'ramp', x0: 0, x1: 192, y0: 0, y1: 96, height: 64 } };
const rock = { kind: 'ground', version: 2, ground: { shape: 'rock', x0: 0, x1: 192, y0: 0, y1: 192, height: 96, seed: 7,
                                                    points: [[0, 0, 0], [192, 0, 10], [192, 192, 96], [0, 192, 40]] } };
const blasts = [{ at: [10, 20, 30], radius: 96 }, { at: [-5, 0, 64], radius: 48 }];

// a made piece: its numbers (with its own blasts inside) and flags go into the record and come back; no outer blasts
for (const generated of [wall, floor, ramp, rock]) {
  const source = { added: { generated, from: { package: 'URB_Bar', level: 'base', actor: 'A' } } };
  const state = stateOfRoot({ source, flags: { cover: false }, blasts: null });
  assert.deepEqual(state, { tinted: false, flags: { cover: false }, generated, blasts: null, breaksFurther: false });
  assert.notEqual(state.generated, generated, 'the state is a copy, not the piece\'s own object');
  const fields = recordFields(state);
  assert.deepEqual(fields, { generated, flags: { cover: false } });
  assert.deepEqual(stateOf({ actor: 'X', ...fields }), state, generated.kind);
  assert.ok(MADE_KINDS.has(generated.kind));
}

// a broken copy of a map's fracturing piece (E6): its blasts and Breaks further in battle, and a spawned piece's tint
{
  const source = { provenance: { type: 'spawn' }, actorClass: 'XComFracLevelActor' };
  const state = stateOfRoot({ source, flags: null, blasts, breaksFurther: true });
  assert.deepEqual(recordFields(state), { tinted: true, blasts, breaksFurther: true });
  assert.deepEqual(stateOf(recordFields(state)), state);
  assert.notEqual(state.blasts[0].at, blasts[0].at);
}
// a made piece's blasts are its own (generated.blasts): blasts beside its numbers are never written
assert.deepEqual(recordFields({ generated: floor, blasts, breaksFurther: true }), { generated: floor });
// Breaks further goes with blasts only; empty blasts are none; nothing set is nothing written
assert.deepEqual(recordFields({ blasts: [], breaksFurther: true }), {});
assert.deepEqual(recordFields({ breaksFurther: true }), {});
assert.deepEqual(recordFields(null), {});
assert.deepEqual(stateOf({}), { tinted: false, flags: null, generated: null, blasts: null, breaksFurther: false });
// a malformed field (from a file elsewhere) gives the piece none of it, not a throw
assert.deepEqual(stateOf({ tinted: 'yes', flags: [true], generated: 'wall', blasts: 'many', breaksFurther: 1 }),
                 { tinted: false, flags: null, generated: null, blasts: null, breaksFurther: false });
assert.deepEqual(pieceState(), { tinted: false, flags: null, generated: null, blasts: null, breaksFurther: false });
// the order a project has always written them in (so a state keyed before this module reads the same)
assert.deepEqual(Object.keys(recordFields({ tinted: true, generated: wall, flags: { cover: true } })), ['tinted', 'generated', 'flags']);
assert.deepEqual(Object.keys(recordFields({ tinted: true, flags: { cover: true }, blasts, breaksFurther: true })), ['tinted', 'flags', 'blasts', 'breaksFurther']);
assert.deepEqual(cloneBlasts(blasts), blasts);

// every field a state writes is one the editor knows (the builder carries only the others as the file has them)
for (const k of Object.keys(recordFields({ tinted: true, generated: wall, flags: { cover: true } })).concat(['blasts', 'breaksFurther']))
  assert.ok(PIECE_FIELDS.has(k), k);
console.log(`piece records: ${4} made pieces and a broken copy go into their records and come back the same`);
