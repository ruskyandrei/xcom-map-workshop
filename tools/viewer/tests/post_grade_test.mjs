// The map's bloom and grade as the game draws them (post_grade.js; game-likeness plan, C3). Run:
// node tools/viewer/tests/post_grade_test.mjs
import assert from 'node:assert/strict';
import { GRADE_GLSL, POST_DEFAULTS, bloomShare, bloomWeight, gradePixel, overrideFlag, postSettings, postUniforms,
         volumeAt } from '../web/post_grade.js';

const near = (got, want, what) => got.forEach((v, k) => assert.ok(Math.abs(v - want[k]) < 1e-4, `${what}: ${got} not ${want}`));

// URB_Bar's world settings as the export gives them (every member filled: its saved ones over the defaults)
const bar = { world: { postProcess: { ...POST_DEFAULTS, DOF_BlurBloomKernelSize: 32, Scene_Colorize: [1, 1, 1.2],
                                      Scene_Shadows: [0, 0, -0.05] } }, volumes: [] };
const u = postUniforms(postSettings(bar));
// a mid grey: the game's gamma (0.2 ^ (1 / 2.2) = 0.48117), blue lifted by the shadows' -0.05 and scaled by 1.2
near(gradePixel(u, [0.2, 0.2, 0.2]), [0.48117, 0.48117, 0.63740], 'grey');
// black: the blue lift shows in the darkest places (0.05 * 1.2)
near(gradePixel(u, [0, 0, 0]), [0, 0, 0.06], 'black');
// the defaults change nothing but the gamma (a plain 2.2 power, not the sRGB curve)
const plain = postUniforms(postSettings(null));
near(gradePixel(plain, [0.2, 0.5, 1]), [0.48117, 0.72974, 1], 'defaults');
near(gradePixel(plain, [0.001, 0, 0]), [0.04329, 0, 0], 'deep dark');          // (sRGB would give 0.0129)
// over 1 is clipped before the gamma (the game's scene colour saturates in its blend pass); the Brightness scales first
near(gradePixel(plain, [3, 0.5, 0]), [1, 0.72974, 0], 'clipped');
near(gradePixel(postUniforms(postSettings(null), 2), [0.25, 0.6, 0]), [0.72974, 1, 0], 'brightness');
// highlights divide, mid-tones are a power, desaturation mixes toward the weighted grey
const graded = members => postUniforms(postSettings({ world: { postProcess: { ...POST_DEFAULTS, ...members } } }));
near(gradePixel(graded({ Scene_HighLights: [2, 2, 2] }), [1, 1, 1]), [0.5, 0.5, 0.5], 'highlights');
near(gradePixel(graded({ Scene_MidTones: [2, 2, 2] }), [0.2, 0.2, 0.2]), [0.23152, 0.23152, 0.23152], 'mid-tones');
near(gradePixel(graded({ Scene_Desaturation: 1 }), [1, 0, 0]), [0.3, 0.3, 0.3], 'desaturated');
near(gradePixel(graded({ Scene_Desaturation: 0.5 }), [1, 0, 0]), [0.65, 0.15, 0.15], 'half desaturated');
// the scene effect off: no grade, only the gamma
near(gradePixel(graded({ bEnableSceneEffect: false, Scene_Colorize: [2, 0, 0] }), [0.2, 0.2, 0.2]), [0.48117, 0.48117, 0.48117], 'no effect');

// the bloom: how far a tap's brightest channel is over the threshold, halved; all of it where the scene is dark
assert.equal(bloomWeight([3, 1, 1], 1), 1);
assert.equal(bloomWeight([1.5, 0, 0], 1), 0.25);
assert.equal(bloomWeight([0.9, 0.9, 0.9], 1), 0);
assert.equal(bloomShare([0, 0, 0], 10), 1);
assert.equal(bloomShare([1, 1, 1], 10), 1);
assert.ok(Math.abs(bloomShare([2, 2, 2], 10) - 10 / 64) < 1e-9);
assert.equal(postUniforms(postSettings(bar)).bloomOn, 1);
assert.equal(graded({ bEnableBloom: false }).bloomOn, 0);
assert.equal(graded({ Bloom_Scale: 0 }).bloomOn, 0);

// a volume: its flagged members over the world's, the rest the world's; a flagged member it did not save is the default
assert.equal(overrideFlag('bEnableBloom'), 'bOverride_EnableBloom');
assert.equal(overrideFlag('Scene_Colorize'), 'bOverride_Scene_Colorize');
const road = { world: { postProcess: { ...POST_DEFAULTS, Bloom_Scale: 0.5, Scene_Colorize: [1.1, 1, 1], Scene_Desaturation: 0.3 } },
               volumes: [{ name: 'PostProcessVolume_1', box: { min: [-3149, 995, -127], max: [-787, 3357, 1077] }, priority: 0,
                           enabled: true, unbound: false,
                           settings: { bOverride_Scene_Colorize: true, bOverride_Scene_Desaturation: true, Bloom_Scale: 2,
                                       Scene_Colorize: [1.2, 1.2, 1.2] } }] };
const inside = postSettings(road, [-2000, 2000, 0]), outside = postSettings(road, [0, 0, 0]);
assert.equal(inside.volume, 'PostProcessVolume_1');
assert.deepEqual(inside.Scene_Colorize, [1.2, 1.2, 1.2]);
assert.equal(inside.Bloom_Scale, 0.5);                      // (saved but not flagged: the world's)
assert.equal(inside.Scene_Desaturation, 0);                 // (flagged but not saved: the default)
assert.equal(outside.volume, null);
assert.deepEqual(outside.Scene_Colorize, [1.1, 1, 1]);
assert.equal(postSettings(road).volume, null);              // (no place: the world's)
// the highest priority holds; a disabled volume is passed over; an unbound one holds everywhere
const high = { ...road.volumes[0], name: 'high', priority: 5, settings: { bOverride_Scene_Colorize: true, Scene_Colorize: [2, 2, 2] } };
assert.equal(volumeAt({ volumes: [road.volumes[0], high] }, [-2000, 2000, 0]).name, 'high');
assert.equal(volumeAt({ volumes: [{ ...high, enabled: false }] }, [-2000, 2000, 0]), null);
assert.equal(volumeAt({ volumes: [{ ...high, unbound: true, box: null }] }, [90000, 0, 0]).name, 'high');

// the GLSL declares the uniforms the chain sets, none named as three's own functions (a luminance() is in its chunks)
for (const name of ['gradeShadows', 'gradeInverseHighlights', 'gradeMidTones', 'gradeKeep', 'gradeLuminance', 'gradeColorize']) {
  assert.match(GRADE_GLSL, new RegExp(`uniform \\w+ ${name};`));
}
assert.doesNotMatch(GRADE_GLSL, /uniform \w+ luminance;/);
console.log('post grade: ok');
