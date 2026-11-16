// Piece flags on the page (web/piece_flags.js) give what tools/viewer/piece_flags.py gives: every case of
// piece_flag_cases.json (written by test_piece_flags.py --write-cases, which also checks the file is current).
// Run: node tools/viewer/tests/piece_flags_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ROLES, normalize, plan, roles, validFlags } from '../web/piece_flags.js';

const { contract, groups } = JSON.parse(readFileSync(new URL('./piece_flag_cases.json', import.meta.url), 'utf8'));
const CODES = { on: 'o', off: 'x', partial: 'p', unknown: 'u', 'n/a': '-' };
const code = states => ROLES.map(r => CODES[states[r]]).join('');
let planned = 0, described = 0;
for (const [cls, raw, assumed, collides, facts, expected, plans] of groups) {
  assert.deepEqual(roles(contract, cls, raw, facts), expected, `${cls} ${JSON.stringify(raw)}`);
  described++;
  for (const [request, want, normalized] of plans) {
    const where = `${cls} ${JSON.stringify(raw)} ${JSON.stringify(request)}`;
    const p = plan(contract, cls, raw, request, assumed);
    assert.deepEqual([code(p.before), code(p.after), p.writes, p.companions, p.effects, Object.keys(p.unsupported).sort(),
                      Object.keys(p.conflicts).sort(), Object.keys(p.unmet).sort(), p.tiles], want, where);
    if (normalized) assert.deepEqual(normalize(contract, cls, raw, request, assumed, collides), normalized, where);
    planned++;
  }
}
assert.ok(planned > 500 && described > 30, `${planned} plans, ${described} descriptions`);

// a project's flags: known roles, strictly boolean, never empty
assert.ok(validFlags({ walking: false, mouse: true }));
for (const bad of [null, [], {}, { walking: 0 }, { walking: 'false' }, { ethereal: true }, { cover: null }]) assert.ok(!validFlags(bad), JSON.stringify(bad));
console.log(`piece flags: ${planned} plans and ${described} descriptions agree with piece_flags.py`);
