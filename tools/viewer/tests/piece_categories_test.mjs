// The Add panel's kinds (piece_categories.js): the pieces' by class and family, and since stage FX4 of the effects and
// sounds plan the effects' and sounds' (tools/viewer/effects_library.py names them), with Effects and Sounds for all
// of each, listed only where the list has some.
// Run: node tools/viewer/tests/piece_categories_test.mjs
import assert from 'node:assert/strict';
import { effectKind, inKind, pieceKind, setKindOptions } from '../web/piece_categories.js';

globalThis.Option = class { constructor(text, value) { this.text = text; this.value = value; } };
const select = () => ({ value: 'all', options: [], replaceChildren(...options) { this.options = options; } });

// pieces
assert.equal(pieceKind('XComDestructibleActor', 'destructible'), 'Destructible');
assert.equal(pieceKind('XComDestructibleActor', 'car'), 'Car');
assert.equal(pieceKind('Emitter', 'effect'), 'Other');

// effects and sounds
const steam = { effect: 'effect', kind: effectKind('effect', 'Smoke and steam') };
const fire = { effect: 'effect', kind: effectKind('effect', 'Fire') };
const hum = { effect: 'sound', kind: effectKind('sound', 'Machines') };
const crate = { kind: 'Scenery' };
assert.equal(steam.kind, 'fx:Smoke and steam');
assert.equal(hum.kind, 'snd:Machines');
assert.equal(effectKind('effect', undefined), 'fx:Other');
assert.deepEqual([steam, fire, hum, crate].filter(e => inKind(e, 'effects')), [steam, fire]);
assert.deepEqual([steam, fire, hum, crate].filter(e => inKind(e, 'sounds')), [hum]);
assert.deepEqual([steam, fire, hum, crate].filter(e => inKind(e, 'fx:Fire')), [fire]);
assert.deepEqual([steam, fire, hum, crate].filter(e => inKind(e, 'Scenery')), [crate]);
assert.equal([steam, fire, hum, crate].filter(e => inKind(e, 'all')).length, 4);

// the menu: Effects and Sounds with their kinds only where there are some, each with its count
const s = select();
setKindOptions(s, [steam, fire, hum, crate]);
const label = value => s.options.find(o => o.value === value)?.text;
assert.equal(label('effects'), 'Effects (2)');
assert.equal(label('fx:Fire'), 'Effects: Fire (1)');
assert.equal(label('fx:Water'), 'Effects: Water (0)');
assert.equal(label('sounds'), 'Sounds (1)');
assert.equal(label('snd:Machines'), 'Sounds: Machines (1)');
assert.equal(label('Scenery'), 'Scenery (1)');
const pieces = select();
setKindOptions(pieces, [crate]);
assert.equal(pieces.options.some(o => o.value === 'effects' || o.value.startsWith('fx:') || o.value === 'sounds'), false);
// a chosen kind stays chosen
const kept = select();
kept.value = 'fx:Fire';
setKindOptions(kept, [fire]);
assert.equal(kept.value, 'fx:Fire');
console.log('piece_categories: ok');
