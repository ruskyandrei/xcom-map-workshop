// Ground shapes on the page (custom geometry plan, stage M6): what is pure about the Ground tool. A ground shape is an
// added copy of its look's donor (one of the game's plain pieces, XComLevelActor or StaticMeshActor, whose material it
// is drawn in) carrying `generated: { kind: 'ground', version: 1, ground }`, its numbers in the donor mesh's frame
// (tools/bake/ground.py): `shape` ('patch', 'block', 'ramp' or 'rock'), `x0`, `x1`, `y0`, `y1` its footprint on tile
// lines (the tool writes x0 and y0 0 and puts the piece at the footprint's corner), `height` (a block's top, a ramp's
// high edge over its low one, a rock's top), `seed` (a rock's: each seed another rock), `look` (left out, the first). A
// ramp rises along its frame's +x; the piece stands level, square to the world's axes (its donor's own pitch, roll and
// yaw don't matter: the mesh is ours), and turns by quarter turns. Locations are game units (x, y, z up), rotations
// rotator units (pitch, yaw, roll). A rock whose corners were moved (look picker and rock points plan, R1) carries
// `points`, its ROCK.points points in its frame, and its request is POINTS_VERSION whatever its look (versionedGround).
import { TILE } from './constants.js';
import { wallRotation, wallDirection, spelledLook } from './walls.js';
import { catalogued } from './looks.js';
import { plural } from './dom_words.js';

// The looks, as tools/bake/ground_looks.json lists them (walls_test.mjs compares the two)
export const GROUND_LOOKS = [
  { id: "asphalt", name: "Asphalt", package: "URB_Bar", actor: "XComLevelActor_131", mesh: "grassPlanes.AsphaltPlaneFlat",
    lwrOnly: false, words: "dark street asphalt, as the bar's parking lot", repeat: 320, thickness: 8 },
  { id: "plain-asphalt", name: "Plain asphalt", package: "URB_Bar", actor: "StaticMeshActor_117", mesh: "StreetSet.Meshes.streetBlock_4xAlt",
    lwrOnly: false, words: "even grey asphalt, as the streets beyond the play area", repeat: 320, thickness: 8 },
  { id: "sidewalk", name: "Sidewalk", package: "URB_StreetHurricane_Terror", actor: "XComLevelActor_325", mesh: "Sidewalk.Meshes.Sidewalk32_2x1_NoEdge",
    lwrOnly: false, words: "clean pale pavement slabs", repeat: 192, thickness: 8 },
  { id: "concrete", name: "Concrete", package: "URB_StreetHurricane", actor: "XComLevelActor_224", mesh: "GroundGasStation.Meshes.TileSet_D",
    lwrOnly: false, words: "poured concrete in large tiles, as a gas station's forecourt", repeat: 384, thickness: 8 },
  { id: "grass", name: "Grass", package: "URB_CommercialStreet", actor: "XComLevelActor_129", mesh: "StreetSet.Meshes.streetBlock_4x",
    lwrOnly: false, words: "dark trimmed grass", repeat: 320, thickness: 8 },
  { id: "dirt", name: "Dirt", package: "URB_MilitaryAmmo", actor: "StaticMeshActor_67", mesh: "StreetSet.Meshes.streetBlock_4x",
    lwrOnly: false, words: "bare brown earth", repeat: 320, thickness: 8 },
  { id: "rock", name: "Rock", package: "CLrgScout_ForestTrench", actor: "XComLevelActor_34", mesh: "Rock_E.Meshes.RockE_Destro",
    lwrOnly: false, words: "grey weathered rock", repeat: 244, thickness: 8 }];
const GROUND_SHAPES = ['patch', 'block', 'ramp', 'rock'];
export const ROCK_SEEDS = 2 ** 31;     // a rock's seed is 0 to ROCK_SEEDS - 1 (ground.py)
// the tool's limits; a block's, a ramp's and a rock's height when drawn; a floor tile steeper than about 10 degrees is
// sloped (no cover on it, F-81) and past 45 no floor (ground.py SLOPED, STEEP)
export const GROUND = { maxTiles: 64, maxHeight: 384, minHeight: 8, step: 8, block: 64, ramp: 96, rock: 96,
                        sloped: Math.acos(0.9848) * 180 / Math.PI, steep: 45 };
const round = (v, step) => step * Math.round(v / step);
const sign = v => (v < 0 ? -1 : 1);
const tidy = v => { const r = Math.round(v * 1e4) / 1e4; return r === 0 ? 0 : r; };

/** A ground shape's look: one of GROUND_LOOKS by its id, or a donor look (M4: { mesh, material, measure }) as the
 *  catalogue has it, with its repeat and thickness (null when no catalogue read holds it). */
export function groundLookOf(g) {
  const look = g?.look ?? GROUND_LOOKS[0].id;
  if (typeof look !== 'object') return GROUND_LOOKS.find(l => l.id === look) ?? null;
  const cat = catalogued('ground', look);
  return cat ? { id: null, name: cat.name, package: cat.map, actor: cat.actor, mesh: cat.mesh, material: cat.material,
                 lwrOnly: Boolean(cat.lwrOnly), words: cat.setting ?? '', repeat: cat.recipe.repeat, thickness: cat.recipe.thickness ?? 8,
                 donor: { mesh: look.mesh, material: look.material, measure: look.measure } } : null;
}
const groundTiles = g => [Math.round((g.x1 - g.x0) / TILE), Math.round((g.y1 - g.y0) / TILE)];
// a patch's top over the ground it lies on (ground.PATCH_LIFT): the blank map's floor planes are drawn 2 over their
// collision (F-137)
const PATCH_LIFT = 3;
/** The shape's box in its mesh's frame [x0, x1, y0, y1, z0, z1] (ground.local_box): a patch's top PATCH_LIFT over the
 *  ground it lies on, its plate under it; a block or ramp on it. */
export function groundBox(g) {
  const z = g.shape === 'patch' ? [PATCH_LIFT - (groundLookOf(g)?.thickness ?? 8), PATCH_LIFT] : [0, g.height];
  return [g.x0, g.x1, g.y0, g.y1, ...z];
}
/** Whether the numbers are ones the tool edits (x0 and y0 0, whole tiles, a height in range, a listed look; a rock's
 *  moved points as pointsValid). */
export function toolGround(g) {
  const whole = v => Math.abs(v / TILE - Math.round(v / TILE)) < 1e-6;
  if (!g || !GROUND_SHAPES.includes(g.shape) || g.x0 !== 0 || g.y0 !== 0 || !whole(g.x1) || !whole(g.y1) || !groundLookOf(g)) return false;
  const [nx, ny] = groundTiles(g);
  return nx >= 1 && ny >= 1 && nx <= GROUND.maxTiles && ny <= GROUND.maxTiles
    && (g.shape === 'patch' || (g.height >= 1 && g.height <= GROUND.maxHeight))
    && (g.shape !== 'rock' || (Number.isInteger(g.seed) && g.seed >= 0 && g.seed < ROCK_SEEDS))
    && (g.points === undefined || (g.shape === 'rock' && pointsValid(g)));
}
/** The shape a drag from `start` to `end` ([x, y] on the ground) draws: the rectangle between the tile edges nearest
 *  them (a click: one tile; at most GROUND.maxTiles each way), on the ground at `z`. A ramp rises toward the drag's end
 *  along the drag's longer way (its frame's x that way); a patch or block keeps its frame's axes the world's. Gives
 *  { location, rotation, ground, tiles: [along x, along y] (in the world) }. */
export function drawnGround(start, end, { origin, z, shape, look = GROUND_LOOKS[0], height = null, seed = 1 }) {
  const edge = (v, k) => origin[k] + round(v - origin[k], TILE);
  const span = k => {
    const a = edge(start[k], k);
    let b = edge(end[k], k);
    if (b === a) b = a + TILE * sign(end[k] - start[k]);
    const tiles = Math.min(GROUND.maxTiles, Math.round(Math.abs(b - a) / TILE));
    return [Math.min(a, a + sign(b - a) * tiles * TILE), tiles];
  };
  const [x0, nx] = span(0), [y0, ny] = span(1);
  const d = [end[0] - start[0], end[1] - start[1]];
  const axis = shape === 'ramp' && Math.abs(d[1]) > Math.abs(d[0]) ? 1 : 0;
  const direction = shape === 'ramp' ? sign(d[axis]) : 1;
  const rotation = wallRotation([0, 0, 0], axis, direction);       // level and square to the world, whatever the donor's
  // the frame's x (along the run) and y (a quarter turn anticlockwise from it); the corner where both are lowest
  const [dx, dy] = wallDirection(rotation[1]), px = -dy, py = dx;
  const corners = [[x0, y0], [x0 + nx * TILE, y0], [x0, y0 + ny * TILE], [x0 + nx * TILE, y0 + ny * TILE]];
  const at = corners.reduce((best, c) => (c[0] * dx + c[1] * dy <= best[0] * dx + best[1] * dy + 1e-6
                                         && c[0] * px + c[1] * py <= best[0] * px + best[1] * py + 1e-6 ? c : best));
  const run = axis === 0 ? nx : ny, across = axis === 0 ? ny : nx;
  const g = { shape, x0: 0, x1: run * TILE, y0: 0, y1: across * TILE,
              ...(shape === 'patch' ? {} : { height: height ?? GROUND[shape] }),
              ...(shape === 'rock' ? { seed } : {}),
              ...(look.donor ? { look: { ...look.donor } } : look.id !== GROUND_LOOKS[0].id ? { look: look.id } : {}) };
  return { location: [tidy(at[0]), tidy(at[1]), tidy(z)], rotation, ground: g, tiles: [nx, ny] };
}
/** The shape with one side ('x0', 'x1', 'y0', 'y1', in its frame) moved `delta` units outwards, in whole tiles, kept
 *  to 1..GROUND.maxTiles. Gives { ground, shift: [dx, dy] (how far its corner moves, in its frame) }. */
export function resizedGround(g, side, delta) {
  const [nx, ny] = groundTiles(g), axis = side[0] === 'x' ? 0 : 1, n = axis ? ny : nx;
  const step = Math.max(1 - n, Math.min(GROUND.maxTiles - n, Math.round(delta / TILE)));
  const shift = [0, 0];
  if (side[1] === '0') shift[axis] = -step * TILE;
  // (a rock's moved points stretch with it, from the side that stays: x * new / old either way, as the frame's 0 moves
  // with the near side)
  const points = g.points && g.points.map(p => p.map((v, k) => (k === axis ? tidy(v * (n + step) / n) : v)));
  return { ground: { ...g, [`${side[0]}1`]: (n + step) * TILE, ...(points ? { points } : {}) }, shift };
}
/** The shape with its height (a block's top, a ramp's high edge) moved by `delta`, in steps of GROUND.step, kept to
 *  GROUND.minHeight..maxHeight; a patch is left as it is. */
export function raisedGround(g, delta) {
  if (g.shape === 'patch') return g;
  const height = Math.max(GROUND.minHeight, Math.min(GROUND.maxHeight, round(g.height + delta, GROUND.step)));
  // (a rock's moved points stretch up with it)
  const points = g.points && g.points.map(([x, y, z]) => [x, y, tidy(z * height / g.height)]);
  return { ...g, height, ...(points ? { points } : {}) };
}
/** Another rock in the same footprint and height: the next seed, its moved points cleared (D-6). */
export const anotherRock = g => { const { points: _, ...rest } = g; return { ...rest, seed: ((g.seed ?? 0) + 1) % ROCK_SEEDS }; };
/** The rock as its seed makes it: its moved points cleared ("Reset points"). */
export const resetRock = g => { const { points: _, ...rest } = g; return rest; };

// ---- a rock's moved points (look picker and rock points plan, R1)
/** A rock's points (ground.py ROCK_POINTS: rings of 7, 8, 6 and 3), the first `ring` its ground ring, on the ground. */
export const ROCK = { points: 24, ring: 7 };
/** The request version of a rock with moved points, whatever its look (tools/editor/compiler.py POINTS_VERSION). */
export const POINTS_VERSION = 4;
const PLAIN_GROUND = 3, DONOR_GROUND = 2;
/** Whether a rock's moved points are ones it can be made of (ground.py check_points): ROCK.points of [x, y, z], each
 *  within its footprint and between 0 and its height, its ground ring on the ground. */
export function pointsValid(g) {
  const pts = g.points, slack = 1e-3;
  return Array.isArray(pts) && pts.length === ROCK.points && pts.every((p, i) => Array.isArray(p) && p.length === 3
    && p.every(v => typeof v === 'number' && Number.isFinite(v))
    && p[0] >= g.x0 - slack && p[0] <= g.x1 + slack && p[1] >= g.y0 - slack && p[1] <= g.y1 + slack
    && p[2] >= -slack && p[2] <= g.height + slack && (i >= ROCK.ring || Math.abs(p[2]) <= slack));
}
/** The rock with point `index` of `points` (its own, or its seed's from the server) moved to `to` ([x, y, z] in its
 *  frame): a point of the ground ring stays on the ground, none goes below it; past the footprint the footprint grows
 *  by whole tiles (D-4), toward -x or -y its corner moving back by the tiles added and every point shifted by as much,
 *  so nothing else moves in the world; up to GROUND.maxTiles, a point past that kept at the edge. Its height is its
 *  highest point's (at least GROUND.minHeight, at most GROUND.maxHeight). Gives { ground, shift: [dx, dy] } (how far
 *  its corner moves, in its frame, as resizedGround's). */
export function movedPoint(g, points, index, to) {
  const pts = points.map(p => [...p]);
  pts[index] = [to[0], to[1], index < ROCK.ring ? 0 : Math.max(0, Math.min(GROUND.maxHeight, to[2]))];
  const out = { ...g }, shift = [0, 0];
  for (const k of [0, 1]) {
    let n = Math.round(g[k ? 'y1' : 'x1'] / TILE);
    const lo = Math.min(...pts.map(p => p[k])), hi = Math.max(...pts.map(p => p[k]));
    const below = Math.min(GROUND.maxTiles - n, lo < -1e-6 ? Math.ceil(-lo / TILE - 1e-9) : 0);
    n += below;
    if (below) { for (const p of pts) p[k] += below * TILE; shift[k] = -below * TILE; }
    const above = Math.min(GROUND.maxTiles - n, hi + below * TILE > n * TILE + 1e-6 ? Math.ceil((hi + below * TILE - n * TILE) / TILE - 1e-9) : 0);
    n += above;
    for (const p of pts) p[k] = Math.max(0, Math.min(n * TILE, p[k]));
    out[k ? 'y1' : 'x1'] = n * TILE;
  }
  out.height = tidy(Math.max(GROUND.minHeight, ...pts.map(p => p[2])));
  out.points = pts.map(p => p.map(tidy));
  return { ground: out, shift };
}
/** A made ground piece's request with the version its numbers need: POINTS_VERSION while a rock has moved points (its
 *  look then written out: none for a plain one, the first look's id rather than left out), and back to its look's
 *  (a look id 1, a donor look DONOR_GROUND, none: plain) once they are cleared. Other requests as they are. */
export function versionedGround(generated) {
  if (generated?.kind !== 'ground' || !generated.ground) return generated;
  const g = generated.ground, look = g.look;
  if (g.points) {
    if (generated.version === POINTS_VERSION) return generated;
    if (generated.version === PLAIN_GROUND) { const { look: _, ...rest } = g; return { ...generated, version: POINTS_VERSION, ground: rest }; }
    return { ...generated, version: POINTS_VERSION, ground: look === undefined ? { ...g, look: GROUND_LOOKS[0].id } : g };
  }
  if (generated.version !== POINTS_VERSION) return generated;
  return { ...generated, version: look === undefined ? PLAIN_GROUND : typeof look === 'object' ? DONOR_GROUND : 1 };
}
/** The shape turned a quarter turn anticlockwise about its footprint's middle: its frame's x and y swap ends, so a ramp
 *  rises the next way round. Gives { ground, location, rotation }. */
export function turnedGround(g, location, rotation) {
  const [dx, dy] = wallDirection(rotation[1]), px = -dy, py = dx;
  const w = g.x1, h = g.y1;
  const mid = [location[0] + dx * w / 2 + px * h / 2, location[1] + dy * w / 2 + py * h / 2];
  const turned = [rotation[0], rotation[1] + 16384, rotation[2]];
  const [ex, ey] = wallDirection(turned[1]), qx = -ey, qy = ex;
  // the new frame's x runs the old y's length
  const nw = h, nh = w;
  const at = [mid[0] - ex * nw / 2 - qx * nh / 2, mid[1] - ey * nw / 2 - qy * nh / 2, location[2]];
  // (a rock's moved points turn with it: the old (x, y) is the new (y, w - x))
  const points = g.points && g.points.map(([x, y, z]) => [y, tidy(w - x), z]);
  return { ground: { ...g, x1: nw, y1: nh, ...(points ? { points } : {}) }, location: at.map(tidy), rotation: turned };
}
/** A ramp's slope in degrees (0 for a patch or block). */
export const slopeOf = g => (g.shape === 'ramp' ? Math.atan2(g.height, g.x1 - g.x0) * 180 / Math.PI : 0);
/** What the game does on its top, in words (ground.slope_words is the twin). */
export function slopeWords(g) {
  const s = slopeOf(g);
  if (s <= 0) return '';
  if (s > GROUND.steep) return `its slope (${Math.round(s)} degrees) is no floor: units can't stand on it`;
  if (s > GROUND.sloped) return `its slope (${Math.round(s)} degrees) is walked, but its tiles are sloped: a unit on it gets no cover, as on every slope of the game's steeper than about 10 degrees`;
  return `its slope (${Math.round(s)} degrees) is walked and gives cover as flat ground does`;
}
const SHAPE_WORDS = { patch: 'Patch', block: 'Block', ramp: 'Ramp', rock: 'Rock' };
export function groundWords(g) {
  const [a, b] = groundTiles(g);
  const size = `${a} by ${b} tile${a * b === 1 ? '' : 's'}`;
  if (g.shape === 'patch') return `${SHAPE_WORDS.patch}, ${size}`;
  if (g.shape === 'block' || g.shape === 'rock') return `${SHAPE_WORDS[g.shape]}, ${size}, ${Math.round(g.height)} high`;
  return `${SHAPE_WORDS.ramp}, ${plural(a, 'tile')} long and ${plural(b, 'tile')} wide, rising ${Math.round(g.height)}`;
}

// ---- a ground shape's mesh (custom geometry plan, M6): drawn from /generated/ground.glb by the editor's server
// (generated.py), its one section on its template's material; the mesh record goes into the scene's meshes.
export const madeGroundNumbers = g => ({ shape: g.shape, x0: g.x0, x1: g.x1, y0: g.y0, y1: g.y1, ...(g.shape === 'patch' ? {} : { height: g.height }),
                                         ...(g.shape === 'rock' ? { seed: g.seed } : {}), ...(g.shape === 'rock' && g.points ? { points: g.points } : {}),
                                         ...(g.look && g.look !== GROUND_LOOKS[0].id ? { look: spelledLook(g.look) } : {}) });
export function groundBounds(g) {
  const b = groundBox(g), h = [0, 1, 2].map(k => (b[2 * k + 1] - b[2 * k]) / 2);
  return [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2, ...h, Math.hypot(...h)];
}
/** A ground shape's { mesh, materials } from its numbers, or {} when the tool would refuse them. */
export function madeGroundShape(template, g, meshes) {
  if (!g || !toolGround({ ...g, x0: 0, y0: 0, x1: g.x1 - g.x0, y1: g.y1 - g.y0 })) return {};
  const numbers = madeGroundNumbers(g), key = `made:ground:${JSON.stringify(numbers)}`;
  if (!meshes[key]) {
    meshes[key] = { name: `${meshes[template.mesh]?.name ?? 'ground'}, made from numbers`, kind: 'static', made: true,
      look: meshes[template.mesh]?.name ?? null, fallback: { mesh: template.mesh, materials: [...template.materials] },
      url: `/generated/ground.glb?${new URLSearchParams({ ground: JSON.stringify(numbers) })}`,
      sections: [{ slot: 0, count: 1 }], bounds: groundBounds(numbers) };
  }
  return { mesh: key, materials: [template.materials[0]] };
}
