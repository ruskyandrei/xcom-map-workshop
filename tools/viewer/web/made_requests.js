// A made piece's request and its plain look (refactor stage P9): what a project records of a wall, floor, roof or
// ground shape made from numbers (its kind, its request's version and its numbers, a donor look's inside them:
// madeRequest), whether a request is a plain one (isPlain), and the default look a plain piece of a kind is made in
// (plainLook). Pure: the looks' and the shapes' tables come from looks.js, walls.js and ground.js; node reads it
// (made_requests_test.mjs).
import { GROUND_LOOKS, POINTS_VERSION, versionedGround } from './ground.js';
import { DONOR_VERSION } from './looks.js';
import { SLAB_LOOKS, slabLookOf, WALL_LOOKS } from './walls.js';

// A made piece's request (custom geometry plan, M4): a donor look's at its kind's DONOR_VERSION with the look in its
// numbers, a look id's (or none) at version 1 as before.
// A made piece drawn plain (custom geometry editing plan, B2, 19 November 2026): its kind's default look's numbers at
// its kind's PLAIN_VERSION, drawn in a plain material until a look is chosen in the piece panel; the Build makes it in
// that default look and says so (compiler made-no-look).
const PLAIN_VERSION = { fracWall: 4, fracSlab: 3, ground: 3 };
// (MADE_KINDS, the kinds of made piece, one piece each made from numbers: piece_records.js)
// (a free-form piece says so in its numbers: `plain`, made_free.js)
const FREE_VERSION = { fracWall: 5, fracSlab: 4, ground: 5 }, KEY = { fracWall: 'wall', fracSlab: 'slab', ground: 'ground' };
export const isPlain = g => Boolean(g) && (g.version === FREE_VERSION[g.kind] ? g[KEY[g.kind]]?.plain === true
  : g.version === PLAIN_VERSION[g.kind] || (g.kind === 'ground' && g.version === POINTS_VERSION && g.ground?.look === undefined));
export const madeRequest = (kind, look, numbers, plain = false) => {
  const key = { fracWall: 'wall', fracSlab: 'slab', ground: 'ground' }[kind];
  // (a rock with moved points: POINTS_VERSION whatever its look, versionedGround)
  if (plain) return versionedGround({ kind, version: PLAIN_VERSION[kind], [key]: numbers });
  return versionedGround(look?.donor ? { kind, version: DONOR_VERSION[key], [key]: { ...numbers, look: { ...look.donor } } } : { kind, version: 1, [key]: numbers });
};
// The default look a plain piece of `kind` is made in: the Bar's inside wall, the Bar's floor or roof by the slab's
// role, asphalt (a look marked `plain`, which setMadeLook makes a plain request of).
export function plainLook(kind, numbers = null) {
  if (kind === 'wall') return { ...WALL_LOOKS[0], plain: true };
  if (kind === 'ground') return { ...GROUND_LOOKS[0], plain: true };
  const role = slabLookOf(numbers ?? {})?.role ?? 'roof';
  return { ...(SLAB_LOOKS.find(l => l.role === role) ?? SLAB_LOOKS[0]), plain: true };
}
