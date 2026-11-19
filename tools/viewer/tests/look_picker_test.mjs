// The look picker's rules (look_picker.js; the look picker plan, P1): a picture's key, the words a look is found by,
// the filters and the cards' order. Run: node tools/viewer/tests/look_picker_test.mjs
import assert from 'node:assert/strict';
import { PICTURE, SIZES, lookText, ordered, pictureKey, shown } from '../web/look_picker.js';

const WALL = { mesh: 'Shop.Meshes.ShopWall_FRACTURED', map: 'URB_Shop', maps: { URB_Shop: 3, URB_Bar: 1 }, name: 'Shop wall',
               setting: 'shop interior', warnings: [] };
const BRICK = { mesh: 'Ware.Meshes.WareWall_FRACTURED', map: 'URB_Ware', maps: { URB_Ware: 1 }, name: 'Brick wall',
                setting: 'brick', warnings: ["its window frames and ledges aren't made"] };
const ALIEN = { mesh: 'Abd.Meshes.AbdWall_FRACTURED', map: 'CAbductor_Cliffside', maps: { CAbductor_Cliffside: 2 }, name: 'Alien wall',
                setting: 'UFO walls (alien)', warnings: [] };
const GRASS = { mesh: 'Farm.Meshes.Plane', material: 'Farm.Materials.Grass', map: 'CSmallScout_Farm', maps: {}, name: 'Grass', setting: 'farm' };
const ROCK = { ...GRASS, material: 'Farm.Materials.Rock', name: 'Rock' };
const simpler = e => ((e.warnings ?? []).length ? [['Simpler', e.warnings.join('; ')]] : []);
const none = () => false;

// a picture's key: 16 hex digits (the server's key form), one per kind, look, sample shape (and drawing version)
const k = pictureKey('wall', WALL, 'wall');
assert.match(k, /^[0-9a-f]{16}$/);
assert.equal(pictureKey('wall', WALL, 'wall'), k);
assert.notEqual(pictureKey('wall', BRICK, 'wall'), k);
assert.notEqual(pictureKey('ground', GRASS, 'rock'), pictureKey('ground', GRASS, 'patch'));
assert.notEqual(pictureKey('ground', GRASS, 'rock'), pictureKey('ground', ROCK, 'rock'));      // (a ground look by its material too)
assert.equal(PICTURE.width / PICTURE.height, 4 / 3);
for (const [w, h] of Object.values(SIZES)) assert.equal(w / h, 4 / 3);

// found by its name, setting, home map, the maps it is in (the catalogue's { map: times }) and its donor
assert.ok(lookText(WALL).includes('urb_bar') && lookText(WALL).includes('shop interior') && lookText(WALL).includes('shopwall_fractured'));
assert.ok(lookText(ROCK).includes('farm.materials.rock'));
assert.ok(lookText({ name: 'Bare', mesh: 'A.B' }).includes('bare'));       // (no maps, setting or material)
const words = text => text.toLowerCase().split(/\s+/).filter(Boolean);
const find = (text, filters = {}, fav = none) => [WALL, BRICK, ALIEN].filter(e => shown(e, words(text), filters, fav, simpler)).map(e => e.name);
assert.deepEqual(find(''), ['Shop wall', 'Brick wall', 'Alien wall']);
assert.deepEqual(find('wall urb'), ['Shop wall', 'Brick wall']);          // (every word)
assert.deepEqual(find('bar'), ['Shop wall']);                           // (a map it is placed in)
assert.deepEqual(find('', { setting: 'brick' }), ['Brick wall']);
assert.deepEqual(find('', { full: true }), ['Shop wall', 'Alien wall']);  // (Full only: not the simpler ones)
assert.deepEqual(find('', { favourites: true }, e => e === ALIEN), ['Alien wall']);

// the order: the piece's own look, the project's, the favourites, then by name
const names = list => list.map(e => e.name);
assert.deepEqual(names(ordered([WALL, BRICK, ALIEN], { kind: 'wall' })), ['Alien wall', 'Brick wall', 'Shop wall']);
assert.deepEqual(names(ordered([WALL, BRICK, ALIEN], { kind: 'wall', isFavourite: e => e === WALL })), ['Shop wall', 'Alien wall', 'Brick wall']);
assert.deepEqual(names(ordered([WALL, BRICK, ALIEN], { kind: 'wall', used: new Set([BRICK.mesh]), isFavourite: e => e === WALL })),
                 ['Brick wall', 'Shop wall', 'Alien wall']);
assert.deepEqual(names(ordered([WALL, BRICK, ALIEN], { kind: 'wall', current: ALIEN.mesh, used: new Set([BRICK.mesh]) })),
                 ['Alien wall', 'Brick wall', 'Shop wall']);
// (a ground look's key is its mesh and material)
assert.deepEqual(names(ordered([GRASS, ROCK], { kind: 'ground', current: `${ROCK.mesh}|${ROCK.material}` })), ['Rock', 'Grass']);
const input = [WALL, BRICK];
ordered(input, { kind: 'wall' });
assert.deepEqual(names(input), ['Shop wall', 'Brick wall']);             // (the list given is left as it was)
console.log('look picker: ok');
