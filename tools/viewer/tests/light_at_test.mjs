// The light at a place (light_rules.js lightAt; game-likeness plan, E2): what a lit particle's colour is multiplied by,
// from the sky light's two colours by the normal's height, the sun by its cosine, and each point or spot light by its
// cosine, UE3's falloff and its cone. Run: node tools/viewer/tests/light_at_test.mjs
import assert from 'node:assert/strict';
import { lightAt } from '../web/light_rules.js';

const near = (got, want, e = 1e-9) => got.forEach((v, k) => assert.ok(Math.abs(v - want[k]) < e, `${got} is not ${want}`));
const up = [0, 1, 0];

// the sky: its upper colour facing up, its lower facing down, half each facing sideways
const sky = { sky: [0.4, 0.5, 0.6], ground: [0.2, 0.1, 0], up };
near(lightAt(sky, [0, 0, 0], [0, 1, 0]), [0.4, 0.5, 0.6]);
near(lightAt(sky, [0, 0, 0], [0, -1, 0]), [0.2, 0.1, 0]);
near(lightAt(sky, [0, 0, 0], [1, 0, 0]), [0.3, 0.3, 0.3]);

// the sun by the cosine to it, none from behind
const sun = { sun: [2, 1, 0.5], toSun: [0, 1, 0], up };
near(lightAt(sun, [0, 0, 0], [0, 1, 0]), [2, 1, 0.5]);
near(lightAt(sun, [0, 0, 0], [Math.SQRT1_2, Math.SQRT1_2, 0]), [2 * Math.SQRT1_2, Math.SQRT1_2, 0.5 * Math.SQRT1_2]);
near(lightAt(sun, [0, 0, 0], [0, -1, 0]), [0, 0, 0]);

// a point light: (1 - (d / R)^2)^F, by the cosine; nothing past its radius
const point = { position: [0, 100, 0], radius: 200, colour: [1, 0.5, 0.25], falloff: 2, direction: [0, -1, 0], cosOuter: -2, coneScale: 0 };
near(lightAt({ locals: [point] }, [0, 0, 0], [0, 1, 0]), [0.5625, 0.28125, 0.140625]);     // (1 - 1/4)^2 = 0.5625
near(lightAt({ locals: [point] }, [0, -150, 0], [0, 1, 0]), [0, 0, 0]);
near(lightAt({ locals: [point] }, [0, 0, 0], [1, 0, 0]), [0, 0, 0]);                       // side on

// a spot light: inside its inner cone whole, outside its outer none
const cosOuter = Math.cos(Math.PI / 4), coneScale = 1 / (Math.cos(Math.PI / 8) - cosOuter);
const spot = { ...point, cosOuter, coneScale };
near(lightAt({ locals: [spot] }, [0, 0, 0], [0, 1, 0]), [0.5625, 0.28125, 0.140625]);
near(lightAt({ locals: [spot] }, [150, 50, 0], [0, 1, 0]).map(v => +v.toFixed(9)), [0, 0, 0]);

// all three add up
const all = lightAt({ ...sky, ...sun, locals: [point] }, [0, 0, 0], [0, 1, 0]);
near(all, [0.4 + 2 + 0.5625, 0.5 + 1 + 0.28125, 0.6 + 0.5 + 0.140625]);
console.log('light_at: ok');
