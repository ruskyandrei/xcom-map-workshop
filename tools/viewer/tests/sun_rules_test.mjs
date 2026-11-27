// The time of day's rules (sun_rules.js; the game-likeness plan, T-S1) on the curve as it ships (sun_curve.json): the
// curve blended at a time, the side's arc, the map's best time, the curve made a map's own so the bar at its time
// changes nothing, a time set with the fog and grade of the hour (members changed by hand left alone), a value set by
// hand, "As the map has it", the record checked (sun_record_cases.json, which the compiler's test reads too) and the words.
// Run: node tools/viewer/tests/sun_rules_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { asTheMapHasIt, barColours, bestTime, clock, compass, curveAt, directionOf, gameTime, handSet, headingFor,
         lightWords, mapCurve, ownSun, partOfDay, phaseAt, rotationOf, shownTime, sideAt, spanAt, sunTurned, sunView, tidySun,
         timeMarks, timeSet, validSun } from '../web/sun_rules.js';

const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const curve = read('../sun_curve.json');
const near = (a, b, eps = 1e-6, what = '') => {
  if (Array.isArray(a)) { assert.equal(a.length, b.length, what); a.forEach((v, k) => near(v, b[k], eps, what)); return; }
  assert.ok(Math.abs(a - b) <= eps, `${what}: ${a} against ${b}`);
};
const unit = c => c.map(v => v / 255);

// URB_Bar as its export (43) has it: the moon, the sky light and the fog and grade
const bar = {
  lights: [
    { kind: 'point', role: 'static', color: [1, 1, 1], brightness: 1 },
    { kind: 'directional', role: 'dominant', rotation: [-14697, -41323, -27675],
      direction: [-0.10983779884534389, 0.11776196848234088, -0.9869487204125521], color: unit([66, 69, 136]), brightness: 1.100000023841858 },
    { kind: 'sky', role: 'sky', color: unit([89, 107, 160]), brightness: 0.75, lowerColor: unit([255, 203, 162]), lowerBrightness: 0.009999999776482582 },
  ],
  atmosphere: { world: { fog: { bEnabled: true, FogDensity: 0.015, LightInscatteringColor: [0.211765, 0.235294, 0.360784, 1],
                                OppositeLightColor: [0.266667, 0.266667, 0.266667, 1] },
                         postProcess: { Scene_Colorize: [1, 1, 1.2], Scene_Shadows: [0, 0, -0.05], Bloom_Scale: 1 } } },
};
// URB_CommercialStreet's day sun
const street = {
  lights: [{ kind: 'directional', role: 'dominant', rotation: [-7163, 10337, 0], direction: directionOf([-7163, 10337, 0]),
             color: unit([255, 250, 180]), brightness: 1 },
           { kind: 'sky', role: 'sky', color: unit([187, 185, 214]), brightness: 0.8, lowerColor: unit([255, 224, 173]), lowerBrightness: 0.01 }],
  atmosphere: { world: { fog: { LightInscatteringColor: [0.431373, 0.470588, 0.454902, 1], OppositeLightColor: [0.266667, 0.266667, 0.266667, 1] },
                         postProcess: { Scene_Colorize: [1.05, 1, 1.1], Scene_Shadows: [0, 0, -0.05] } } },
};

// the curve: its spans, the light up and how far through its time
assert.deepEqual(spanAt(curve, 10), { light: 'sun', start: 5.5, end: 20.5 });
assert.deepEqual(spanAt(curve, 3), { light: 'moon', start: -3.5, end: 5.5 });
assert.deepEqual(spanAt(curve, 22), { light: 'moon', start: 20.5, end: 29.5 });
assert.deepEqual(phaseAt(curve, 13), { light: 'sun', phase: 0 });
assert.deepEqual(phaseAt(curve, 1), { light: 'moon', phase: 0 });
near(phaseAt(curve, 5.5).phase, -1); near(phaseAt(curve, 20.5).phase, -1); near(phaseAt(curve, 5.4999).phase, 1, 1e-3);
// every row of the curve is a light of its own span; each span has rows; suns no higher than the survey's (56) (F-175)
for (const row of curve.rows) {
  assert.equal(phaseAt(curve, row.time).light, row.light, `row ${row.time}`);
  if (row.light === 'sun') assert.ok(row.height <= 56, `row ${row.time}`);
}
// a row's time gives the row; between two rows, the blend; before a span's first row, the first row's
near(curveAt(curve, 13).color, [255, 245, 215]); near(curveAt(curve, 13).height, 56);
near(curveAt(curve, 11.5).height, (40.22 + 56) / 2); near(curveAt(curve, 11.5).color, [255, 247.5, 197.5]);
near(curveAt(curve, 5.6).height, 11.02); near(curveAt(curve, 1).fog.LightInscatteringColor, unit([54, 60, 92]));
near(curveAt(curve, 23).height, 52.9 + (80.73 - 52.9) * 0.5);       // (21:00 to 01:00 across midnight)
assert.equal(curveAt(curve, 3).light, 'moon');
// the side's arc: a quarter turn before the dial as the light comes up, at it at its highest, a quarter after
near(sideAt(curve, 13, 90), 90); near(sideAt(curve, 5.5, 90), 0); near(sideAt(curve, 20.4999, 90), 180, 1e-2);
near(sideAt(curve, 1, 200), 200); near(sideAt(curve, 20.5, 200), 110);
near(headingFor(curve, 9.25, sideAt(curve, 9.25, 37)), 37);

// the map's own: Bar's moon at 01:00 on the curve, the side where the map has it; the street's sun at 10:00 (of two
// times as like, the earlier)
const own = ownSun(bar);
near(own.height, 80.73, 0.01); near(own.side, 313.0, 0.05); assert.deepEqual(own.color, [66, 69, 136]);
assert.deepEqual(own.sky.color, [89, 107, 160]);
assert.equal(ownSun({ lights: [{ kind: 'directional', role: 'static' }] }), null);
assert.equal(bestTime(curve, own), 1);
const streetOwn = ownSun(street);
assert.equal(bestTime(curve, streetOwn), 9 + 55 / 60);
// the rotation of a height and side, and back
assert.deepEqual(rotationOf(own.height, own.side, -27675).map((v, k) => Math.abs(((v - own.rotation[k]) % 65536 + 65536) % 65536) <= 1 || Math.abs(((v - own.rotation[k]) % 65536 + 65536) % 65536 - 65536) <= 1), [true, true, true]);
near(directionOf(own.rotation), bar.lights[1].direction, 1e-4);

// the curve made the Bar's own: at its time and heading nothing changes (no record, no fog or colour)
const mine = mapCurve(curve, own, 1);
const shown = shownTime(null, own, curve);
assert.equal(shown.time, 1); near(shown.heading, own.side, 1e-6);
assert.deepEqual(timeSet({ curve: mine, own, time: 1, heading: shown.heading }), { sun: null, atmosphere: null });
near(curveAt(mine, 1).fog.LightInscatteringColor, [0.211765, 0.235294, 0.360784]);
assert.ok(!mine.rows.some(r => r.light === 'moon' && r.time !== 1 && Math.abs(r.time - 1) < 1.5));

// noon: the curve's light, the sky's, the fog and grade of the hour set and marked, the record valid and counted
const noon = timeSet({ curve: mine, own, time: 13, heading: shown.heading });
assert.ok(validSun(noon.sun, curve), JSON.stringify(noon.sun));
assert.deepEqual(noon.sun.light.color, [255, 245, 215]); assert.equal(noon.sun.light.brightness, 1.1);
near(noon.sun.light.rotation[0], Math.round(-56 * 65536 / 360), 0);
assert.deepEqual(noon.sun.sky, { color: [150, 150, 170], brightness: 0.6, lowerColor: [255, 224, 173], lowerBrightness: 0.01 });
assert.deepEqual(noon.atmosphere.fog.LightInscatteringColor, [0.423529, 0.439216, 0.435294, 1]);
assert.deepEqual(noon.atmosphere.postProcess, { Scene_Colorize: [1, 1, 1], Scene_Shadows: [0, 0, 0] });
assert.equal(noon.atmosphere.fog.OppositeLightColor, undefined);      // (the Bar's own, 68 grey: no change)
assert.deepEqual(timeMarks(noon.sun, noon.atmosphere), { 'fog.LightInscatteringColor': 'time', 'fog.OppositeLightColor': null,
                                                         'postProcess.Scene_Colorize': 'time', 'postProcess.Scene_Shadows': 'time' });
assert.equal(gameTime(noon.sun, curve), 'day');
near(sideAt(curve, 13, noon.sun.heading), own.side, 0.01);
// and back to the Bar's own time: nothing again
assert.deepEqual(timeSet({ curve: mine, own, before: noon.sun, atmosphere: noon.atmosphere, time: 1, heading: shown.heading }),
                 { sun: null, atmosphere: null });
// the dial turned at the Bar's own time: only the light's side
const turned = timeSet({ curve: mine, own, time: 1, heading: shown.heading + 90 });
assert.deepEqual([turned.sun.light.color, turned.sun.atmosphere, turned.atmosphere], [[66, 69, 136], undefined, null]);
assert.notDeepEqual(turned.sun.light.rotation, own.rotation);

// a fog colour changed by hand (the Fog and colour section) is left alone and marked custom; the rest follow the time
const red = [1, 0, 0, 1];
const byHand = { ...noon.atmosphere, fog: { ...noon.atmosphere.fog, LightInscatteringColor: red } };
assert.equal(timeMarks(noon.sun, byHand)['fog.LightInscatteringColor'], 'custom');
const dusk = timeSet({ curve: mine, own, before: noon.sun, atmosphere: byHand, time: 20, heading: shown.heading });
assert.deepEqual(dusk.atmosphere.fog.LightInscatteringColor, red);
assert.deepEqual(dusk.atmosphere.fog.OppositeLightColor, [0.219608, 0.2, 0.313725, 1]);
assert.deepEqual(dusk.atmosphere.postProcess.Scene_Colorize, [1.1, 0.95, 0.8]);
assert.equal(timeMarks(dusk.sun, dusk.atmosphere)['fog.LightInscatteringColor'], 'custom');
// "As the map has it": no record, the time's members out, the one changed by hand kept
assert.deepEqual(asTheMapHasIt(dusk.sun, dusk.atmosphere, own), { sun: null, atmosphere: { fog: { LightInscatteringColor: red } } });
assert.deepEqual(asTheMapHasIt(noon.sun, noon.atmosphere, own), { sun: null, atmosphere: null });

// a colour set by hand (More): marked, kept by the bar; the game's time of day by hand
const tinted = handSet({ curve: mine, own, before: noon.sun, atmosphere: noon.atmosphere, key: 'color', value: [10, 20, 30] });
assert.deepEqual([tinted.light.color, tinted.custom], [[10, 20, 30], ['color']]);
const later = timeSet({ curve: mine, own, before: tinted, atmosphere: noon.atmosphere, time: 16, heading: shown.heading });
assert.deepEqual([later.sun.light.color, later.sun.custom], [[10, 20, 30], ['color']]);
assert.equal(later.sun.light.brightness, 1);
const night = handSet({ curve: mine, own, before: null, key: 'timeOfDay', value: 'night' });
assert.equal(night.timeOfDay, 'night'); assert.equal(night.time, 1); assert.deepEqual(night.light.rotation, own.rotation);
assert.equal(handSet({ curve: mine, own, before: night, key: 'timeOfDay', value: 'auto' }), null);
assert.equal(handSet({ curve: mine, own, before: null, key: 'brightness', value: 3 }).light.brightness, 3);

// the record checked (the cases the compiler's test reads too) and tidied
for (const c of read('./sun_record_cases.json').cases) assert.equal(validSun(c.record, curve), c.valid, c.why);
assert.equal(tidySun(null, own, curve), null);
assert.deepEqual(tidySun({ odd: 1 }, own, curve), { odd: 1 });          // (carried as it is)
const tidied = tidySun({ ...noon.sun, time: 13.000004, heading: 313.123456 }, own, curve);
assert.deepEqual([tidied.time, tidied.heading], [13, 313.12]);

// the street: its own at 10:00 changes nothing; the afternoon is the curve's
const streets = mapCurve(curve, streetOwn, bestTime(curve, streetOwn)), at = shownTime(null, streetOwn, curve);
assert.deepEqual(timeSet({ curve: streets, own: streetOwn, time: at.time, heading: at.heading }), { sun: null, atmosphere: null });
const afternoon = timeSet({ curve: streets, own: streetOwn, time: 16, heading: at.heading });
assert.deepEqual(afternoon.sun.sky.color, [125, 129, 108]);
const midnight = timeSet({ curve: streets, own: streetOwn, time: 0, heading: at.heading });
assert.equal(gameTime(midnight.sun, curve), 'night'); assert.ok(midnight.sun.light.color[2] > midnight.sun.light.color[0]);

// what the view draws
const view = sunView(noon.sun);
near(view.light.direction, directionOf(noon.sun.light.rotation)); near(view.light.color, unit([255, 245, 215]));
near(view.sky.lowerColor, unit([255, 224, 173]));
assert.equal(sunView(null), null);
// the map's baked sun shadows stand for its own light only (B3): a light turned by more than half a degree (here a degree in pitch) is another
assert.equal(sunTurned(null, bar), false);
assert.equal(sunTurned(sunView({ light: { rotation: own.rotation, color: [66, 69, 136], brightness: 1 } }), bar), false);
assert.equal(sunTurned(sunView({ light: { rotation: [own.rotation[0] + 182, own.rotation[1], 0], color: [66, 69, 136], brightness: 1 } }), bar), true);
assert.equal(sunTurned(view, bar), true);
assert.equal(sunTurned(view, { lights: [] }), false);

// words
assert.equal(clock(7 + 10 / 60), '07:10'); assert.equal(clock(0), '00:00'); assert.equal(clock(23.999), '00:00');
assert.deepEqual([1, 6, 10, 13, 16, 19.5].map(t => partOfDay(curve, t)), ['night', 'dawn', 'morning', 'midday', 'afternoon', 'dusk']);
assert.deepEqual([0, 67.5, 90, 180, 337.6].map(compass), ['north', 'east-north-east', 'east', 'south', 'north-north-west']);
assert.equal(lightWords(curve, { time: 7, light: { rotation: rotationOf(14, 67.5), color: [255, 139, 45] } }),
             'Sun low in the east-north-east, warm, long shadows');
assert.equal(lightWords(curve, noon.sun), `Sun high in the ${compass(own.side)}, white, short shadows`);
assert.equal(lightWords(curve, { time: 1, light: { rotation: own.rotation, color: own.color } }), 'Moon high in the north-west, blue, short shadows');
// the bar's colours: night darker than noon
const colours = barColours(curve, 24), sum = css => css.match(/\d+/g).map(Number).reduce((s, v) => s + v, 0);
assert.equal(colours.length, 24);
assert.ok(sum(colours[0]) < sum(colours[12]) / 2, `${colours[0]} against ${colours[12]}`);
console.log('sun_rules ok');
