// A copied piece's record (web/piece_records.js, review finding 6): a piece's state goes into its record and comes back
// the same, for made pieces (a wall with an opening, a floor, a shaped ground piece) and a broken copy of a map's
// fracturing piece, so a prefab saved from a selection and placed again keeps what each piece is. The whole record
// (refactor stage P2): recordOf and optionsOf, each form and each writer's path. A piece's original and key
// (refactor stage P9): isStream, fromOf and sourceKey.
// Run: node tools/viewer/tests/piece_records_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { MADE_KINDS, PIECE_FIELDS, cloneBlasts, fromOf, isStream, optionsOf, pieceState, recordFields, recordOf, sourceKey, stateOf,
         stateOfRoot } from '../web/piece_records.js';

const wall = { kind: 'fracWall', version: 4, wall: { x0: 0, x1: 288, openings: [{ x0: 96, x1: 192, z0: 0, z1: 208 }], seed: 3 },
               blasts: [{ at: [48, 0, 96], radius: 96 }], breaksFurther: true };
const floor = { kind: 'fracSlab', version: 1, slab: { x0: 0, x1: 192, y0: 0, y1: 288, holes: [{ x0: 96, x1: 192, y0: 96, y1: 192 }], seed: 1, look: 'floor' } };
const ramp = { kind: 'ground', version: 1, ground: { shape: 'ramp', x0: 0, x1: 192, y0: 0, y1: 96, height: 64 } };
const rock = { kind: 'ground', version: 2, ground: { shape: 'rock', x0: 0, x1: 192, y0: 0, y1: 192, height: 96, seed: 7,
                                                    points: [[0, 0, 0], [192, 0, 10], [192, 192, 96], [0, 192, 40]] } };
const blasts = [{ at: [10, 20, 30], radius: 96 }, { at: [-5, 0, 64], radius: 48 }];

// a piece's original and key: a map's own piece is its own original, by its package, level and actor; a copy's original
// is the one it was copied from (its key is still its own names'); a streamed piece is a stream's, and nothing is not
{
  const own = { sourcePackage: 'URB_Bar', layer: 'base', actor: 'TheWorld.PersistentLevel.KAsset_0', component: 'C' };
  assert.deepEqual(fromOf(own), { package: 'URB_Bar', level: 'base', actor: 'TheWorld.PersistentLevel.KAsset_0' });
  assert.equal(sourceKey(own), 'URB_Bar|base|TheWorld.PersistentLevel.KAsset_0');
  const from = { package: 'URB_Bar', level: 'base', actor: 'TheWorld.PersistentLevel.KAsset_0' };
  const copy = { sourcePackage: 'URB_Bar', layer: 'base', actor: 'TheWorld.PersistentLevel.KAsset_0_copy1', added: { from } };
  assert.equal(fromOf(copy), from, 'a copy gives the record of its original itself');
  assert.equal(sourceKey(copy), 'URB_Bar|base|TheWorld.PersistentLevel.KAsset_0_copy1');
  assert.equal(isStream({ ...own, layer: 'stream' }), true);
  for (const o of [own, copy, null, undefined]) assert.equal(isStream(o), false);
}

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

// The whole record: each form's fields in the order the writers have always written them. A unit's id is written when
// it has one (a project's); a prefab's records have none; a recipe light's values come before its pose in a prefab.
const keys = o => Object.keys(o);
const from = { package: 'URB_Bar', level: 'base', actor: 'A' }, pose = { location: [1, 2, 3], rotation: [0, 16384, 0] };
const piece = { id: 'e1', actor: 'A_copy1', from, components: ['A.C2', 'A.C1'], ...pose, prefab: 'copy1:P', partner: 'B_copy2',
                state: pieceState({ tinted: true, flags: { cover: false } }), recipe: { key: 'k', name: 'N' } };
const wrote = recordOf(piece);
assert.deepEqual(keys(wrote), ['id', 'actor', 'from', 'components', 'location', 'rotation', 'prefab', 'partner', 'tinted', 'flags', 'recipe']);
assert.deepEqual(wrote.components, ['A.C1', 'A.C2'], 'the components sorted');
assert.deepEqual(piece.components, ['A.C2', 'A.C1'], 'and the unit\'s own list left as it was');
assert.equal(wrote.from, from, 'the unit\'s values go in as they are');
const { id: _, ...prefabPiece } = piece;
assert.deepEqual(keys(recordOf({ ...prefabPiece, prefab: null, partner: undefined, recipe: null, state: pieceState() }, 'prefab')),
                 ['actor', 'from', 'components', 'location', 'rotation', 'prefab', 'partner']);
assert.equal(recordOf({ ...prefabPiece, prefab: undefined, partner: undefined, state: null }).partner, null);
const cover = { form: 'cover', id: 'e2', actor: 'CoverBlock_copy3', template: { kind: 'cover', version: 2 }, cover: { type: 'low', size: [96, 96], heights: [-12, 84] }, ...pose };
assert.deepEqual(keys(recordOf(cover)), ['id', 'actor', 'template', 'cover', 'location', 'rotation']);
assert.notEqual(recordOf(cover).cover, cover.cover, 'a cover block\'s cover is copied');
const spot = { form: 'light', id: 'e3', actor: 'SpotLight_copy4', template: { kind: 'spot', version: 1 }, light: { brightness: 2 }, ...pose };
assert.deepEqual(keys(recordOf(spot)), ['id', 'actor', 'template', 'location', 'rotation', 'light']);
const { id: __, ...prefabSpot } = spot;
assert.deepEqual(keys(recordOf(prefabSpot, 'prefab')), ['actor', 'template', 'light', 'location', 'rotation']);
const lamp = { form: 'light', id: 'e4', actor: 'PointLight_0_copy5', from, component: 'A.PointLightComponent_0', ...pose, light: {} };
assert.deepEqual(recordOf(lamp), { id: 'e4', actor: 'PointLight_0_copy5', from, components: ['A.PointLightComponent_0'], ...pose });
assert.deepEqual(recordOf({ ...lamp, light: { radius: 512 } }).light, { radius: 512 });
const sound = { form: 'effect', id: 'e5', actor: 'AmbientSoundSimple_0_copy6', kind: 'sound', from, ...pose, values: { volume: [0.5, 0.6] } };
assert.deepEqual(keys(recordOf(sound)), ['id', 'actor', 'kind', 'from', 'location', 'rotation', 'sound']);
assert.deepEqual(keys(recordOf({ ...sound, kind: 'flare', values: null })), ['id', 'actor', 'kind', 'from', 'location', 'rotation']);

// ... and read back: what makes each one's root again
assert.deepEqual(optionsOf(wrote), { actor: 'A_copy1', entity: 'e1', prefab: 'copy1:P', partner: 'B_copy2', ...pose,
                                     tinted: true, flags: { cover: false }, generated: null, blasts: null, breaksFurther: false });
assert.deepEqual(keys(optionsOf(wrote)), ['actor', 'entity', 'prefab', 'partner', 'location', 'rotation', 'tinted', 'flags', 'generated', 'blasts', 'breaksFurther']);
const given = pieceState({ blasts: [{ at: [0, 0, 0], radius: 48 }] });
assert.equal(optionsOf({ actor: 'X', id: 'e9', ...pose }, 'piece', given).blasts, given.blasts, 'a state given is handed on as it is');
assert.deepEqual(optionsOf({ ...recordOf(cover), tinted: true, flags: { cover: true } }, 'cover'),
                 { actor: 'CoverBlock_copy3', entity: 'e2', prefab: null, partner: null, ...pose, tinted: false });
assert.deepEqual(optionsOf(recordOf(spot), 'light'), { actor: 'SpotLight_copy4', entity: 'e3', ...pose, recipe: { kind: 'spot', version: 1 },
                                                      light: { brightness: 2 }, from: undefined, component: undefined });
assert.deepEqual(optionsOf(recordOf(lamp), 'light'), { actor: 'PointLight_0_copy5', entity: 'e4', ...pose, recipe: undefined, light: undefined, from,
                                                      component: 'A.PointLightComponent_0' });
assert.deepEqual(optionsOf({ ...recordOf(sound), sound: { volume: [0.5, 0.6], follow: 'none', parameters: [{ name: 'P', value: 2 }] } }, 'effect'),
                 { actor: 'AmbientSoundSimple_0_copy6', entity: 'e5', kind: 'sound', from, ...pose, values: { volume: [0.5, 0.6], parameters: { P: 2 } } });

// The recorded cases (piece_record_cases.json): one scene on the Bar holding every kind of piece, the records its three
// writers gave before this module wrote them (a project, a prefab, the builder's document), and what its readers handed
// on (a project's and the builder's applyState, a prefab's clip, a paste). Each record is recordOf's of its unit, field
// for field and in the same order (a project's saved key, stateKey, reads a state keyed before as the same).
const cases = JSON.parse(readFileSync(new URL('./piece_record_cases.json', import.meta.url), 'utf8'));
const inOrder = (a, b, what) => assert.equal(JSON.stringify(a), JSON.stringify(b), what);
const kinds = new Set();
for (const c of cases.writers) {
  // (a prefab's partner is named by its name in the prefab, and its records moved to its origin, after recordOf: `after`)
  inOrder({ ...recordOf(c.unit, c.path), ...c.after }, c.record, `${c.writer}'s ${c.kind}`);
  kinds.add(`${c.writer}: ${c.kind}`);
}
for (const writer of ['project', 'prefab', 'builder'])
  for (const kind of ['copy', 'copy (partner)', 'tinted copy', 'copy of two components', 'copy of another map\'s piece', 'fracWall', 'fracSlab',
                      'ground ramp', 'ground rock', 'broken copy', 'cover high', 'cover floor', 'cover block', 'spot light (recipe)',
                      'point light (recipe)', 'effect', 'sound', 'flare', ...(writer === 'project' ? ['light copy'] : [])])
    assert.ok(kinds.has(`${writer}: ${kind}`), `no recorded ${writer} record of a ${kind}`);
const absent = v => v === '<undefined>';      // (a clip entry without the field)
const stateKeys = ['tinted', 'flags', 'generated', 'blasts', 'breaksFurther'];
const stateIn = o => Object.fromEntries(stateKeys.map(k => [k, o[k]]));
const sites = new Set();
for (const c of cases.readers) {
  const what = `${c.site}, ${c.form} ${c.record.actor}`, got = optionsOf(c.record, c.form, c.state);
  sites.add(`${c.site}: ${c.form}`);
  assert.equal(got.actor, c.record.actor, what);
  assert.equal(got.entity, c.record.id, what);
  assert.equal(got.location, c.record.location, `${what}: the record's own location`);
  if (c.options) {
    // addedObject's options: those applyState gave, in the same order; a paste's in optionsOf's order (it takes them by name)
    assert.deepEqual(got, c.options, what);
    if (c.site.startsWith('applyState')) assert.deepEqual(Object.keys(got), Object.keys(c.options), what);
    if (c.state) assert.equal(got.generated, c.state.generated, `${what}: the state given is handed on`);
  } else if (c.added && c.form === 'light') {
    // what addedLight was given: its actor, and among its values every one the record sets (the page adds the rest)
    assert.equal(c.added.actor, got.actor, what);
    for (const [k, v] of Object.entries(got.light ?? {})) assert.deepEqual(c.added.values[k], v, `${what}: ${k}`);
    assert.deepEqual(got.recipe, c.record.template, what);
  } else if (c.added) {
    assert.deepEqual({ actor: got.actor, entity: got.entity, values: got.values }, c.added, what);
  } else {
    // a prefab's clip entry: its unit, link and partner, state and values
    const e = c.entry;
    assert.equal(e.unit, got.actor, what);
    if (c.form === 'piece') {
      assert.deepEqual(c.state, stateOf(c.record), `${what}: the record's state`);
      assert.deepEqual({ link: e.link, partner: e.partner, state: e.state }, { link: got.prefab, partner: got.partner, state: stateIn(got) }, what);
    } else if (c.form === 'cover') assert.deepEqual([e.link, e.partner], [got.prefab, got.partner], what);
    else if (c.form === 'light') assert.deepEqual(got.recipe, c.record.template, what);
    else if (absent(e.values)) assert.equal(c.record.kind, 'flare', `${what}: only a lens flare is placed with no values`);
    else assert.deepEqual(e.values, got.values, what);
  }
}
assert.equal(sites.size, 14, [...sites].join('; '));
console.log(`piece records: ${4} made pieces and a broken copy go into their records and come back the same; each form's record written and read; `
  + `${cases.writers.length} recorded records written and ${cases.readers.length} read as before`);
