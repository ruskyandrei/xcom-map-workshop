// Cache everything's pictures (precache_pictures.js): what there is to draw, by map, what it takes, and what a run lets
// go of the page's tables. Run: node tools/viewer/tests/precache_pictures_test.mjs
import assert from 'node:assert/strict';
import { COST, LOOK_SAMPLES, batches, createTableRelease, estimate, lookItems, pieceItems } from '../web/precache_pictures.js';

// the look picker's samples: a wall's and a slab's by their kind, a ground look's in each of the four shapes
assert.deepEqual(LOOK_SAMPLES, { wall: ['wall'], slab: ['slab'], ground: ['patch', 'block', 'ramp', 'rock'] });

// the looks: one item a sample, those the server keeps left out
const keyOf = (kind, entry, sample) => `${kind}|${entry.mesh}|${sample}`;
const lists = [
  { kind: 'wall', looks: [{ mesh: 'A.Wall', map: 'URB_Bar', name: 'Bar wall' }, { mesh: 'B.Wall', map: 'URB_Shop', name: 'Shop wall' }] },
  { kind: 'slab', looks: [{ mesh: 'A.Slab', map: 'URB_Bar', name: 'Bar floor' }] },
  { kind: 'ground', looks: [{ mesh: 'C.Plane', material: 'C.Grass', map: 'CSmallScout_Farm', name: 'Grass' }] },
];
const looks = lookItems(lists, new Set(['wall|B.Wall|wall', 'ground|C.Plane|rock']), keyOf);
assert.equal(looks.total, 2 + 1 + 4);
assert.equal(looks.missing, 5);
assert.deepEqual(looks.items.map(i => i.want[0].key),
                 ['wall|A.Wall|wall', 'slab|A.Slab|slab', 'ground|C.Plane|patch', 'ground|C.Plane|block', 'ground|C.Plane|ramp']);
assert.deepEqual(looks.items.map(i => i.name),
                 ['Bar wall (wall look)', 'Bar floor (floor or roof look)', 'Grass (ground look, as a patch)', 'Grass (ground look, as a block)',
                  'Grass (ground look, as a ramp)']);
assert.ok(looks.items.every(i => i.type === 'look' && i.want.length === 1 && i.want[0].size === 'look'));
assert.equal(looks.items[2].map, 'CSmallScout_Farm');
assert.equal(lookItems([], new Set(), keyOf).total, 0);

// the Add panel's: a piece's two pictures, an effect's while effects are drawn (and placeable), never a sound's or a
// lens flare's; only the pictures the server lacks
const keysOf = e => ({ small: `${e.key}`, large: `${e.key}L` });
const source = pkg => ({ kind: 'map', package: pkg, level: 'base', actor: 'A_1' });
const entries = [
  { key: 'p1', name: 'Curb', family: 'scenery', placeable: true, source: source('URB_Bar') },
  { key: 'p2', name: 'Crate', family: 'destructible', placeable: false, source: source('URB_Shop') },     // (drawn, placeable or not)
  { key: 'p3', name: 'Lamp', family: 'scenery', placeable: true, source: source('URB_Bar') },
  { key: 'e1', name: 'Fire', family: 'effect', placeable: true, source: source('URB_Bar') },
  { key: 'e2', name: 'Spark', family: 'effect', placeable: false, source: source('URB_Bar') },
  { key: 's1', name: 'Hum', family: 'sound', placeable: true, source: source('URB_Bar') },
  { key: 'f1', name: 'Glare', family: 'flare', placeable: true, source: source('URB_Bar') },
];
const kept = new Set(['p1', 'p1L', 'p3L']);
const pieces = pieceItems(entries, kept, keysOf);
assert.equal(pieces.total, 2 * 4);
assert.deepEqual(pieces.items.map(i => [i.entry.key, i.type, i.want.map(w => w.size)]),
                 [['p2', 'piece', ['small', 'large']], ['p3', 'piece', ['small']], ['e1', 'effect', ['small', 'large']]]);
assert.equal(pieces.missing, 5);
assert.equal(pieces.items[0].map, 'URB_Shop');
const noEffects = pieceItems(entries, kept, keysOf, { effects: false });
assert.equal(noEffects.total, 2 * 3);
assert.deepEqual(noEffects.items.map(i => i.entry.key), ['p2', 'p3']);
assert.deepEqual(pieceItems(undefined, kept, keysOf), { total: 0, missing: 0, items: [] });     // (no library read yet)

// in batches: each map's together (its name's case aside), in the order the maps first come, maps joined until a batch
// has the fewest items asked for (a map with more is a batch of its own)
const all = [...looks.items, ...pieces.items];
const shape = list => list.map(b => [b.maps, b.items.length]);
assert.deepEqual(shape(batches(all, 1)), [[['URB_Bar'], 4], [['CSmallScout_Farm'], 3], [['URB_Shop'], 1]]);
assert.deepEqual(shape(batches(all, 5)), [[['URB_Bar', 'CSmallScout_Farm'], 7], [['URB_Shop'], 1]]);
assert.deepEqual(shape(batches(all, 100)), [[['URB_Bar', 'CSmallScout_Farm', 'URB_Shop'], 8]]);
assert.deepEqual(batches(all, 1)[0].items.map(i => i.name), ['Bar wall (wall look)', 'Bar floor (floor or roof look)', 'Lamp', 'Fire']);
assert.deepEqual(shape(batches([{ map: 'URB_Bar' }, { map: 'urb_bar' }], 1)), [[['URB_Bar'], 2]]);
assert.deepEqual(batches([]), []);

// what it takes: an item's seconds, a picture's bytes
const cost = estimate([...looks.items, ...pieces.items]);
assert.equal(cost.bytes, 5 * COST.look.bytes + 3 * COST.piece.bytes + 2 * COST.effect.bytes);
assert.equal(cost.seconds, Math.round(5 * COST.look.seconds + 2 * COST.piece.seconds + COST.effect.seconds));
assert.deepEqual(estimate([]), { seconds: 0, bytes: 0 });

// the tables let go after a run: what was put in since the snapshot is taken out and freed, except what the view draws
// (and a record whose meshes it draws) and what is still loading or failed; what was there before stays as it was
const disposed = [];
const thing = name => ({ name, dispose: () => disposed.push(name) });
const mesh = name => { const geometry = thing(`${name} geometry`); const part = { geometry }; return { scene: { traverse: f => f(part) }, geometry }; };
const texture = name => ({ ...thing(name), isTexture: true });
const old = mesh('old'), drawnMesh = mesh('drawn'), lost = mesh('lost');
const drawnMap = texture('drawn map'), lostMap = texture('lost map');
const drawnMaterial = { ...thing('drawn material'), map: drawnMap }, lostMaterial = { ...thing('lost material'), map: lostMap };
// (a table holds a promise each; what each load gave is known at once once it is in: scene_pieces.js loaded)
const settled = new Map();
const put = (map, key, value) => { const promise = Promise.resolve(value); map.set(key, promise); if (value !== undefined) settled.set(promise, value); };
const loaded = (map, key) => settled.get(map.get(key));
const tables = { meshes: new Map(), materials: new Map(), textures: new Map(), records: new Map() };
put(tables.meshes, 'old', old);
const lines = new Map([['old', {}]]);
const world = { traverse: f => [{ geometry: old.geometry }, { geometry: drawnMesh.geometry, material: drawnMaterial }].forEach(f) };
let busy = true, resumed = 0;
const release = createTableRelease({ tables, loaded, collision: () => lines, world, busy: () => busy, resume: () => { resumed++; }, wait: 5,
                                     roots: () => new Map([['r1', { userData: { source: { mesh: 'placed' } } }]]) });
const before = release.snapshot();
put(tables.meshes, 'drawn', drawnMesh);
put(tables.meshes, 'lost', lost);
put(tables.meshes, 'loading', undefined);       // (still loading, or failed: someone else's)
put(tables.materials, 'drawn', drawnMaterial);
put(tables.materials, 'lost', lostMaterial);
put(tables.textures, 'drawn', drawnMap);
put(tables.textures, 'lost', lostMap);
// (a record's load is not the tables' track: what it gives is noted as it comes, idle() waiting for it)
tables.records.set('keeps', Promise.resolve({ sources: [{ mesh: 'drawn' }] }));
tables.records.set('goes', Promise.resolve({ sources: [{ mesh: 'lost' }] }));
let reading;
tables.records.set('reading', new Promise(resolve => { reading = resolve; }));
const failing = Promise.reject(Error('not read'));
failing.catch(() => {});
tables.records.set('failing', failing);
for (const key of ['drawn', 'lost', 'placed']) lines.set(key, {});
// releaseWhenIdle() waits while a panel draws a picture of its own, holding the panels meanwhile (they begin no other),
// and for the records read since to come in; then lets go at once, nothing coming between, and the panels carry on
let waited = false;
assert.equal(release.holding, false);
const idle = release.releaseWhenIdle(before).then(() => { waited = true; });
await new Promise(resolve => setTimeout(resolve, 20));
assert.equal(waited, false);
assert.equal(release.holding, true);
assert.equal(tables.meshes.has('lost'), true);
busy = false;
await new Promise(resolve => setTimeout(resolve, 20));
assert.equal(waited, false);
reading({ sources: [{ mesh: 'lost' }] });
await idle;
assert.equal(release.holding, false);
assert.equal(resumed, 1);
assert.deepEqual([...tables.meshes.keys()].sort(), ['drawn', 'loading', 'old']);
assert.deepEqual([...tables.materials.keys()], ['drawn']);
assert.deepEqual([...tables.textures.keys()], ['drawn']);
assert.deepEqual([...tables.records.keys()].sort(), ['failing', 'keeps']);      // (a failed one drops itself: libraryTemplate)
assert.deepEqual([...lines.keys()].sort(), ['drawn', 'old', 'placed']);
assert.deepEqual(disposed.sort(), ['lost geometry', 'lost map', 'lost material']);
// (with no collision read yet, nothing to let go of there)
const bare = createTableRelease({ tables: { meshes: new Map(), materials: new Map(), textures: new Map(), records: new Map() },
                                  loaded, collision: () => null, world: { traverse() {} }, roots: () => new Map() });
const nothing = bare.snapshot();
await bare.idle(nothing);
bare.release(nothing);
console.log('precache pictures: ok');
