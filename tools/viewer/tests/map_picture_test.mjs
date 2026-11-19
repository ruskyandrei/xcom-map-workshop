// The Map picture dialog's crop arithmetic (map_picture_crop.js; LWR map packs plan, 4.2): the 2:1 frame kept inside
// the image whatever is dragged, and the sizes it is scaled through to 512 x 256; and the picture in a project's
// state (project.js). Run: node tools/viewer/tests/map_picture_test.mjs
import assert from 'node:assert/strict';
import { HEIGHT, MIN_WIDTH, WIDTH, clampFrame, dragCorner, moveFrame, scaleSteps, sourceRect, startFrame, widest, zoomFrame } from '../web/map_picture_crop.js';
import { sortState, stateKey, validPicture } from '../web/project.js';

const inside = (f, w, h) => f.x >= -1e-9 && f.y >= -1e-9 && f.x + f.w <= w + 1e-9 && f.y + f.h <= h + 1e-9;
const twoToOne = f => Math.abs(f.w - 2 * f.h) < 1e-9;
const ok = (f, w, h) => { assert.ok(inside(f, w, h), JSON.stringify([f, w, h])); assert.ok(twoToOne(f), JSON.stringify(f)); };

// ---- the frame a new image starts with: the largest 2:1 frame, around the middle
assert.deepEqual(startFrame(1920, 1080), { x: 0, y: 60, w: 1920, h: 960 });       // a wide screen: full width
assert.deepEqual(startFrame(1000, 1000), { x: 0, y: 250, w: 1000, h: 500 });
assert.deepEqual(startFrame(3000, 1000), { x: 500, y: 0, w: 2000, h: 1000 });     // wider than 2:1: full height
assert.deepEqual(startFrame(512, 256), { x: 0, y: 0, w: 512, h: 256 });
assert.equal(widest(100, 400), 100);
assert.equal(widest(900, 100), 200);

// ---- moved: stopped at each edge, its size kept
const start = startFrame(1000, 1000);
assert.deepEqual(moveFrame(start, 0, -1000, 1000, 1000), { x: 0, y: 0, w: 1000, h: 500 });
assert.deepEqual(moveFrame(start, 50, 5000, 1000, 1000), { x: 0, y: 500, w: 1000, h: 500 });
const small = { x: 100, y: 100, w: 200, h: 100 };
assert.deepEqual(moveFrame(small, -500, 20, 1000, 1000), { x: 0, y: 120, w: 200, h: 100 });
assert.deepEqual(moveFrame(small, 5000, 5000, 1000, 1000), { x: 800, y: 900, w: 200, h: 100 });
// a frame asked for wider than the image holds, or narrower than the least, is brought to what it can be
assert.deepEqual(clampFrame({ x: -10, y: -10, w: 5000, h: 2500 }, 1000, 800), { x: 0, y: 0, w: 1000, h: 500 });
assert.equal(clampFrame({ x: 10, y: 10, w: 1, h: 0.5 }, 1000, 800).w, MIN_WIDTH);
assert.deepEqual(clampFrame({ x: 0, y: 0, w: 1, h: 1 }, 20, 20), { x: 0, y: 0, w: 20, h: 10 });      // an image smaller than the least

// ---- a corner dragged: the opposite corner stays, 2:1 kept, stopped by the image
let f = dragCorner(small, 'se', 500, 200, 1000, 1000);
assert.deepEqual(f, { x: 100, y: 100, w: 400, h: 200 });
f = dragCorner(small, 'se', 150, 400, 1000, 1000);        // further down than across: the height asks for more
assert.deepEqual(f, { x: 100, y: 100, w: 600, h: 300 });
f = dragCorner(small, 'se', 99999, 99999, 1000, 1000);    // past the image: as large as the room from the fixed corner
assert.deepEqual(f, { x: 100, y: 100, w: 900, h: 450 });
f = dragCorner(small, 'nw', 0, 0, 1000, 1000);            // the south-east corner (300, 200) stays; the top stops it
assert.deepEqual(f, { x: 0, y: 50, w: 300, h: 150 });
ok(f, 1000, 1000);
f = dragCorner(small, 'ne', 600, 190, 1000, 1000);        // the south-west corner (100, 200) stays
assert.deepEqual(f, { x: 100, y: 0, w: 400, h: 200 });
f = dragCorner(small, 'sw', 290, 110, 1000, 1000);        // dragged past the least: the least frame, at the fixed corner
assert.deepEqual(f, { x: 300 - MIN_WIDTH, y: 100, w: MIN_WIDTH, h: MIN_WIDTH / 2 });
f = dragCorner(small, 'se', -500, -500, 1000, 1000);      // dragged through the fixed corner: the least frame, never flipped
assert.deepEqual(f, { x: 100, y: 100, w: MIN_WIDTH, h: MIN_WIDTH / 2 });

// ---- the wheel: about the pointer while there is room, never out of the image
f = zoomFrame({ x: 200, y: 200, w: 400, h: 200 }, 0.5, 400, 300, 1000, 1000);
assert.deepEqual(f, { x: 300, y: 250, w: 200, h: 100 });
f = zoomFrame({ x: 200, y: 200, w: 400, h: 200 }, 2, 200, 200, 1000, 1000);       // about its corner: the corner stays
assert.deepEqual(f, { x: 200, y: 200, w: 800, h: 400 });
f = zoomFrame({ x: 200, y: 200, w: 400, h: 200 }, 100, 400, 300, 1000, 1000);     // out to the widest
assert.deepEqual(f, { x: 0, y: 50, w: 1000, h: 500 });
f = zoomFrame({ x: 200, y: 200, w: 400, h: 200 }, 0.0001, 400, 300, 1000, 1000);
assert.equal(f.w, MIN_WIDTH);
ok(f, 1000, 1000);

// ---- whatever is done, the frame is 2:1 and inside (a walk of made-up drags over odd image sizes)
let seed = 7;
const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
for (const [w, h] of [[1920, 1080], [300, 4000], [4000, 300], [33, 17], [5, 5], [513, 256]]) {
  let g = startFrame(w, h);
  ok(g, w, h);
  for (let k = 0; k < 400; k++) {
    const px = (random() * 3 - 1) * w, py = (random() * 3 - 1) * h, pick = Math.floor(random() * 3);
    g = pick === 0 ? moveFrame(g, px, py, w, h)
      : pick === 1 ? dragCorner(g, ['nw', 'ne', 'sw', 'se'][Math.floor(random() * 4)], px, py, w, h)
      : zoomFrame(g, 0.25 + random() * 3, px, py, w, h);
    ok(g, w, h);
    assert.ok(g.w > 0);
    const [sx, sy, sw, sh] = sourceRect(g, w, h);
    assert.ok(Number.isInteger(sx) && Number.isInteger(sy) && sw >= 1 && sh >= 1 && sx >= 0 && sy >= 0 && sx + sw <= w && sy + sh <= h);
  }
}

// ---- the stepped scaling: halved while more than twice the size, then one smooth step to 512 x 256
assert.deepEqual([WIDTH, HEIGHT], [512, 256]);
assert.deepEqual(scaleSteps(512), [[512, 256]]);
assert.deepEqual(scaleSteps(300), [[512, 256]]);                  // a small frame: scaled up, in one step
assert.deepEqual(scaleSteps(1024), [[512, 256]]);                 // exactly twice: one step
assert.deepEqual(scaleSteps(1025), [[513, 257], [512, 256]]);
assert.deepEqual(scaleSteps(1920), [[960, 480], [512, 256]]);
assert.deepEqual(scaleSteps(4000), [[2000, 1000], [1000, 500], [512, 256]]);
assert.deepEqual(scaleSteps(4096), [[2048, 1024], [1024, 512], [512, 256]]);
assert.deepEqual(scaleSteps(8192), [[4096, 2048], [2048, 1024], [1024, 512], [512, 256]]);
for (const fw of [513, 777, 1500, 2047, 2049, 5000, 12000]) {
  const steps = scaleSteps(fw);
  assert.deepEqual(steps.at(-1), [512, 256]);
  let from = fw;
  for (const [w] of steps) { assert.ok(from / w <= 2 + 1e-9 && w >= WIDTH, `${fw}: ${from} to ${w}`); from = w; }
}

// ---- the picture in a project's state: carried by sortState, part of what makes two states differ
const sha = 'ab'.repeat(32);
assert.ok(validPicture({ sha256: sha }));
for (const bad of [null, undefined, {}, { sha256: 'xyz' }, { sha256: sha.toUpperCase() }, { sha256: sha, file: 'x.png' }, [sha]])
  assert.ok(!validPicture(bad), JSON.stringify(bad));
const base = { overrides: [], added: [] };
assert.deepEqual(sortState({ ...base, picture: { sha256: sha } }).picture, { sha256: sha });
assert.equal(sortState(base).picture, null);
assert.equal(sortState({ ...base, picture: { sha256: 'nope' } }).picture, null);
assert.notEqual(stateKey(sortState(base)), stateKey(sortState({ ...base, picture: { sha256: sha } })));
assert.notEqual(stateKey(sortState({ ...base, picture: { sha256: sha } })), stateKey(sortState({ ...base, picture: { sha256: 'cd'.repeat(32) } })));
assert.equal(stateKey(sortState(base)), stateKey(sortState({ ...base, picture: null })));

console.log('map picture: ok');
