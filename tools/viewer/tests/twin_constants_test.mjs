// The page's side of tests/twin_constants.json (review finding 55): constants the page and Python each write, pinned in
// one file both sides' tests read (test_twin_constants.py checks Python's), as limits.json is.
// Run: node tools/viewer/tests/twin_constants_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { LIGHT_LIMITS } from '../web/light_rules.js';
import { VALUE_LIMITS } from '../web/effects_rules.js';
import { FRAC_WALL, END_INSETS } from '../web/walls.js';
import { GROUND, ROCK_SEEDS } from '../web/ground.js';
import { EVAC_SIZE, GROUND as LANDING_GROUND, INSIDE_BACK, OFFSETS, QUARTER, SOLDIERS } from '../web/spawns.js';
import { SHIPS } from '../web/missions_panel.js';
import { SOFT } from '../web/piece_categories.js';
import { LISTED_CLASSES } from '../web/floors.js';

const twin = JSON.parse(readFileSync(new URL('./twin_constants.json', import.meta.url), 'utf8'));

assert.deepEqual(LIGHT_LIMITS, twin.lightRanges);
assert.deepEqual({ scale: VALUE_LIMITS.scale, radiusMax: VALUE_LIMITS.radius[1], volumeMax: VALUE_LIMITS.volume[1],
                   pitch: VALUE_LIMITS.pitch, parameterMax: VALUE_LIMITS.parameter }, twin.effectValues);
// (a sound's radius and volume go from 0, as the compiler's checks do)
assert.deepEqual([VALUE_LIMITS.radius[0], VALUE_LIMITS.volume[0]], [0, 0]);
assert.deepEqual({ minLength: FRAC_WALL.minLength, maxLength: FRAC_WALL.maxLength }, twin.madeWall);
assert.deepEqual(END_INSETS, twin.endInsets);
const { sloped, ...ground } = twin.ground;
assert.deepEqual({ maxTiles: GROUND.maxTiles, maxHeight: GROUND.maxHeight, rockSeeds: ROCK_SEEDS, steep: GROUND.steep }, ground);
assert.ok(Math.abs(GROUND.sloped - sloped) < 1e-9, GROUND.sloped);
assert.deepEqual({ quarter: QUARTER, ground: LANDING_GROUND, insideBack: INSIDE_BACK, offsets: OFFSETS, soldiers: SOLDIERS, evacSize: EVAC_SIZE },
                 twin.landing);
assert.deepEqual(SHIPS.map(([value]) => value), twin.ships);
assert.deepEqual(SOFT, twin.softFamilies);
assert.deepEqual([...LISTED_CLASSES], twin.listedClasses);
console.log('twin_constants_test: ok');
