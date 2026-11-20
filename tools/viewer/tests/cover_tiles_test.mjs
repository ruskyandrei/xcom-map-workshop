// What the game makes of a cover block (cover.js coverTiles, coverGameWords, coverSightWords; moved out of app.js,
// review finding 22): the tiles it reaches and fills, the edges it walls off, the tiles that get cover from it and
// whether it stands across eye height, on the game's numbers (research/native/cover-build.md).
// Run: node tools/viewer/tests/cover_tiles_test.mjs
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

// cover.js draws with three.js only inside its drawing functions: a stand-in is enough for the model
registerHooks({ resolve: (s, c, next) => (s === 'three' ? { url: 'data:text/javascript,export {}', shortCircuit: true } : next(s, c)) });
const { coverGameWords, coverSightWords, coverTiles } = await import('../web/cover.js');

// a piece standing unturned with its corner's floor at (x0, y0, z): its frame as coverFrame gives one
const frameAt = (x0, y0, z) => ({ at: (u, v, w = 0) => [x0 + u, y0 + v, z + w], local: (x, y, h) => [x - x0, y - y0, h - z] });
const grid = [0, 0, 0];
const recipe = { heights: { high: [-12, 96], low: [-12, 84], floor: [-2, 0], block: [-12, 96] } };

// a high block one tile across on a tile: it fills that tile, and the four round it get high cover toward it
const high = { type: 'high', size: [96, 96], heights: [-12, 96] };
let g = coverTiles(high, frameAt(0, 0, 0), grid, recipe);
assert.deepEqual(g.tiles, [{ centre: [48, 48], occupied: true, full: true, carried: true }]);
assert.deepEqual([g.thin, g.walls, g.looked, g.covered, g.seen, g.eye, g.sweep, g.top], [false, 0, 4, 4, 0, 96, true, 0]);
assert.equal(coverGameWords(high, g), 'Hidden in the game. Units can\'t stand in the tile whose middle it fills. Units in the 4 tiles beside it get high cover from it.');
assert.equal(coverSightWords(high, g), 'Sight: it doesn\'t stand across eye height (96 over its floor), so units see and shoot past it.');

// two tiles long, twice as tall and 24 thick, along a tile line: it reaches into the four tiles beside the line
// without filling a middle, walls off the two edges it stands across and blocks sight there
const wall = { type: 'high', size: [192, 24], heights: [-12, 192] };
g = coverTiles(wall, frameAt(0, 84, 0), grid, recipe);
assert.equal(g.tiles.length, 4);
assert.ok(g.tiles.every(t => t.occupied && !t.full && !t.carried));
assert.deepEqual([g.walls, g.seen], [2, 2]);
assert.equal(coverGameWords(wall, g), 'Hidden in the game. It fills no tile\'s middle, so units can stand in the tiles it reaches into. '
  + 'It stops units crossing the 2 tile edges it stands across, as a wall does. Units in the 4 tiles beside it get high cover from it.');
assert.match(coverSightWords(wall, g), /^Sight: it blocks line of sight as a wall does/);

// under 4 units through: no tile filled; a blocker gives no cover; a low block is seen over
const thin = { type: 'high', size: [2, 96], heights: [-12, 96] };
g = coverTiles(thin, frameAt(47, 0, 0), grid, recipe);
assert.equal(g.thin, true);
assert.ok(g.tiles.every(t => !t.occupied));
assert.match(coverGameWords(thin, g), /Under 4 units through/);
const blocker = { type: 'block', size: [96, 96], heights: [-12, 96] };
assert.match(coverGameWords(blocker, coverTiles(blocker, frameAt(0, 0, 0), grid, recipe)), /Units beside it get no cover from it\./);
assert.equal(coverSightWords(blocker, g), 'Sight: units see and shoot through it.');
assert.equal(coverSightWords({ type: 'low' }, g), 'Sight: units see and shoot over it, as over any low cover.');
// a record with no heights of its own takes the recipe's; a level up, its floor's level is the one it stands in
const old = { type: 'low', size: [96, 96] };
g = coverTiles(old, frameAt(96, 0, 64), grid, recipe);
assert.equal(g.top, 64);
assert.deepEqual(g.tiles.map(t => t.centre), [[144, 48]]);
console.log('cover tiles: ok');
