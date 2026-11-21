// The page's side of tests/ladder_cases.json: web/ladders.js ladderEnds gives each case's ends, as
// tools/viewer/ladders.py ends does (test_ladders.py), so the inspector's end marks and the compiler's climb warning
// (ladder-climb) cannot part. Its numbers are held to ladders.py's by twin_constants_test.mjs.
// Run: node tools/viewer/tests/ladders_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ladderEnds, tileOf } from '../web/ladders.js';

const { cases } = JSON.parse(readFileSync(new URL('./ladder_cases.json', import.meta.url), 'utf8'));
assert.ok(cases.length >= 10);
const near = (a, b, what) => {
  assert.equal(a.length, b.length, what);
  a.forEach((v, k) => assert.ok(Math.abs(v - b[k]) <= 1e-9, `${what}: ${JSON.stringify(a)} against ${JSON.stringify(b)}`));
};
for (const c of cases) {
  const floors = new Set(c.floors.map(t => t.join(',')));
  const got = ladderEnds(c.location, c.rotation, c.extentZ, c.origin, floors);
  const { top, foot, ...rest } = got, { top: wantTop, foot: wantFoot, ...want } = c.ends;
  near(top, wantTop, `${c.why}: top`);
  near(foot, wantFoot, `${c.why}: foot`);
  assert.deepEqual(rest, want, c.why);
  // the tiles are those of the points
  assert.deepEqual(tileOf(top, c.origin), want.topTile, c.why);
  assert.deepEqual(tileOf(foot, c.origin), want.footTile, c.why);
}
// every verdict is among the cases: climbs, no foot, no top, neither; a linked top under the top's own tile
const whys = new Set(cases.map(c => c.ends.why.join('+')));
for (const why of ['', 'foot', 'top', 'foot+top']) assert.ok(whys.has(why), `no case whose why is "${why}"`);
assert.ok(cases.some(c => c.ends.linkedTop && c.ends.linkedTop[2] === c.ends.topTile[2] - 1));
console.log(`ladders_test: ok (${cases.length} cases)`);
