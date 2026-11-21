// Cover blocks' and invisible floors' records on the page (cover.js; private/plans/done/cover-block-handles-plan.md):
// older records read as records in units, the handles' faces, a face moved by the snap setting's steps (across from the
// opposite side, up and down from the type's first top or bottom), a new cover type's heights, and the words the panel
// shows. Run: node tools/viewer/tests/cover_test.mjs
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

// cover.js draws with three.js only inside its drawing functions: a stand-in is enough for what is tested here
registerHooks({ resolve: (s, c, next) => (s === 'three' ? { url: 'data:text/javascript,export {}', shortCircuit: true } : next(s, c)) });
const { coverFaces, coverMeshId, coverStart, floorStart, lengthWords, normalCover, resizedCover, retyped, sizeWords,
        MIN_ACROSS, MIN_HIGH } = await import('../web/cover.js');

// the latest recipe as families.py hands it to the page (compiler.COVER_RECIPES[2])
const recipe = { heights: { high: [-12, 96], low: [-12, 84], floor: [-2, 0], block: [-12, 96] },
                 maxTiles: 16, maxHeight: 8, heightStep: 96, flat: ['floor'] };

// ---- older records: whole tiles, and the first ones
assert.deepEqual(normalCover({ width: 2, length: 1, height: 'low' }, recipe), { type: 'low', size: [192, 96], heights: [-12, 84] });
assert.deepEqual(normalCover({ width: 1, length: 3, type: 'high', height: 2 }, recipe), { type: 'high', size: [96, 288], heights: [-12, 192] });
assert.deepEqual(normalCover({ width: 2, length: 2, type: 'floor', height: 1 }, recipe), { type: 'floor', size: [192, 192] });
const units = { type: 'block', size: [48, 8], heights: [20, 60] };
assert.deepEqual(normalCover(units, recipe), units);
assert.deepEqual(coverStart(recipe), { type: 'high', size: [96, 96], heights: [-12, 96] });
assert.deepEqual(floorStart(), { type: 'floor', size: [96, 96] });
assert.equal(coverMeshId(units), 'cover:48x8x20_60:block');
assert.equal(coverMeshId(floorStart()), 'cover:96x96:floor');

// ---- the handles: four sides and top and bottom for a block, four sides for a floor
assert.deepEqual(coverFaces(coverStart(recipe)).map(f => f[0]), ['-x', '+x', '-y', '+y', '-z', '+z']);
assert.deepEqual(coverFaces(floorStart()).map(f => f[0]), ['-x', '+x', '-y', '+y']);
const face = key => coverFaces(coverStart(recipe)).find(f => f[0] === key);

// ---- across: the size counts from the opposite side; `delta` is out from the piece
const block = coverStart(recipe);
assert.deepEqual(resizedCover(block, recipe, face('+x'), 130, 'tile'), { cover: { ...block, size: [192, 96] }, shift: 0 });
assert.deepEqual(resizedCover(block, recipe, face('+x'), 40, 'tile').cover.size, [96, 96]);       // under half a tile: none
// out on a low side: the corner moves back by what was added, so the far side stays
assert.deepEqual(resizedCover(block, recipe, face('-y'), 110, 'tile'), { cover: { ...block, size: [96, 192] }, shift: -96 });
assert.deepEqual(resizedCover(block, recipe, face('-x'), -48.4, 'off'), { cover: { ...block, size: [47.6, 96] }, shift: 48.4 });   // snap off: no rounding
assert.deepEqual(resizedCover(block, recipe, face('+y'), 30, 'fine').cover.size, [96, 120]);
assert.deepEqual(resizedCover(block, recipe, face('+y'), -80, 'fine').cover.size, [96, 24]);      // a step of 24 at least
assert.deepEqual(resizedCover(block, recipe, face('+x'), -500, 'tile').cover.size, [96, 96]);     // a tile at least
assert.deepEqual(resizedCover(block, recipe, face('+x'), -500, 'off').cover.size, [MIN_ACROSS, 96]);
assert.deepEqual(resizedCover(block, recipe, face('+x'), 5000, 'tile').cover.size, [16 * 96, 96]); // the recipe's most
// the distance moved is stepped (the custom geometry improvements plan, 3.2): a size off the steps keeps its offset
assert.deepEqual(resizedCover({ ...block, size: [50, 96] }, recipe, face('+x'), 30, 'fine').cover.size, [74, 96]);
assert.deepEqual(resizedCover({ ...block, size: [50, 96] }, recipe, face('+x'), -40, 'fine').cover.size, [26, 96]);
assert.deepEqual(resizedCover({ ...block, size: [50, 96] }, recipe, face('+x'), -100, 'fine').cover.size, [26, 96]);   // (the last step that keeps 8)

// ---- up and down: the distance moved in the snap's up steps (tile: levels of 64)
assert.deepEqual(resizedCover(block, recipe, face('+z'), 100, 'tile').cover.heights, [-12, 224]);
assert.deepEqual(resizedCover(block, recipe, face('+z'), 30, 'fine').cover.heights, [-12, 120]);
assert.deepEqual(resizedCover(block, recipe, face('+z'), -55.6, 'off').cover.heights, [-12, 40.4]);
const low = { ...block, type: 'low', heights: [-12, 84] };
assert.deepEqual(resizedCover(low, recipe, face('+z'), 90, 'tile').cover.heights, [-12, 148]);
assert.deepEqual(resizedCover(low, recipe, face('+z'), 20, 'fine').cover.heights, [-12, 108]);
// the bottom: out is down, in is up
assert.deepEqual(resizedCover(block, recipe, face('-z'), -100, 'tile').cover.heights, [52, 96]);       // up a level: two would pass the top
assert.deepEqual(resizedCover(block, recipe, face('-z'), 30, 'fine').cover.heights, [-36, 96]);
assert.deepEqual(resizedCover(block, recipe, face('-z'), -200, 'off').cover.heights, [96 - MIN_HIGH, 96]);   // never past the top
assert.deepEqual(resizedCover(block, recipe, face('+z'), -200, 'off').cover.heights, [-12, -12 + MIN_HIGH]);
assert.equal(resizedCover(block, recipe, face('+z'), 100, 'tile').shift, 0);
// the record handed in is left as it was
assert.deepEqual(block, coverStart(recipe));

// ---- a new cover type: heights on the old type's tile steps move to the new type's, any other stays
assert.deepEqual(retyped({ ...block, heights: [-12, 192] }, recipe, 'low').heights, [-12, 180]);
assert.deepEqual(retyped({ ...block, heights: [-12, 40] }, recipe, 'low').heights, [-12, 40]);
assert.deepEqual(retyped({ ...block, heights: [84, 192] }, recipe, 'block').heights, [84, 192]);
assert.deepEqual(retyped(low, recipe, 'high').heights, [-12, 96]);

// ---- words
assert.equal(lengthWords(96), '1 tile'); assert.equal(lengthWords(288), '3 tiles'); assert.equal(lengthWords(40), '40 units');
assert.equal(sizeWords([192, 96]), '2 × 1 tiles'); assert.equal(sizeWords([48, 96]), '48 × 96 units');
console.log('cover_test: ok');
