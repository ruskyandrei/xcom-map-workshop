// Ground shapes on the page (custom geometry plan, stage M6): what is pure about the Ground tool. A ground shape is an
// added copy of its look's donor (one of the game's plain pieces, XComLevelActor or StaticMeshActor, whose material it
// is drawn in) carrying `generated: { kind: 'ground', version: 1, ground }`, its numbers in the donor mesh's frame
// (tools/bake/ground.py): `shape` ('patch', 'block', 'ramp' or 'rock'), `x0`, `x1`, `y0`, `y1` its footprint on tile
// lines (the tool writes x0 and y0 0 and puts the piece at the footprint's corner), `height` (a block's top, a ramp's
// high edge over its low one, a rock's top), `seed` (a rock's: each seed another rock), `look` (left out, the first). A
// ramp rises along its frame's +x; the piece stands level, square to the world's axes (its donor's own pitch, roll and
// yaw don't matter: the mesh is ours), and turns by quarter turns. Locations are game units (x, y, z up), rotations
// rotator units (pitch, yaw, roll).
import { TILE } from './poserule.js';
import { wallRotation, wallDirection } from './walls.js';

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
export const GROUND_SHAPES = ['patch', 'block', 'ramp', 'rock'];
export const ROCK_SEEDS = 2 ** 31;     // a rock's seed is 0 to ROCK_SEEDS - 1 (ground.py)
// the tool's limits; a block's, a ramp's and a rock's height when drawn; a floor tile steeper than about 10 degrees is
// sloped (no cover on it, F-81) and past 45 no floor (ground.py SLOPED, STEEP)
export const GROUND = { maxTiles: 16, maxHeight: 384, minHeight: 8, step: 8, block: 64, ramp: 96, rock: 96,
                        sloped: Math.acos(0.9848) * 180 / Math.PI, steep: 45 };
const round = (v, step) => step * Math.round(v / step);
const sign = v => (v < 0 ? -1 : 1);
const tidy = v => { const r = Math.round(v * 1e4) / 1e4; return r === 0 ? 0 : r; };
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

export const groundLookOf = g => GROUND_LOOKS.find(l => l.id === (g?.look ?? GROUND_LOOKS[0].id)) ?? null;
export const groundTiles = g => [Math.round((g.x1 - g.x0) / TILE), Math.round((g.y1 - g.y0) / TILE)];
/** The shape's box in its mesh's frame [x0, x1, y0, y1, z0, z1] (ground.local_box): a patch's top a unit over the
 *  ground it lies on, its plate under it; a block or ramp on it. */
export function groundBox(g) {
  const z = g.shape === 'patch' ? [1 - (groundLookOf(g)?.thickness ?? 8), 1] : [0, g.height];     // (a patch a unit over the ground)
  return [g.x0, g.x1, g.y0, g.y1, ...z];
}
/** Whether the numbers are ones the tool edits (x0 and y0 0, whole tiles, a height in range, a listed look). */
export function toolGround(g) {
  const whole = v => Math.abs(v / TILE - Math.round(v / TILE)) < 1e-6;
  if (!g || !GROUND_SHAPES.includes(g.shape) || g.x0 !== 0 || g.y0 !== 0 || !whole(g.x1) || !whole(g.y1) || !groundLookOf(g)) return false;
  const [nx, ny] = groundTiles(g);
  return nx >= 1 && ny >= 1 && nx <= GROUND.maxTiles && ny <= GROUND.maxTiles
    && (g.shape === 'patch' || (g.height >= 1 && g.height <= GROUND.maxHeight))
    && (g.shape !== 'rock' || (Number.isInteger(g.seed) && g.seed >= 0 && g.seed < ROCK_SEEDS));
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
              ...(look.id !== GROUND_LOOKS[0].id ? { look: look.id } : {}) };
  return { location: [tidy(at[0]), tidy(at[1]), tidy(z)], rotation, ground: g, tiles: [nx, ny] };
}
/** The shape with one side ('x0', 'x1', 'y0', 'y1', in its frame) moved `delta` units outwards, in whole tiles, kept
 *  to 1..GROUND.maxTiles. Gives { ground, shift: [dx, dy] (how far its corner moves, in its frame) }. */
export function resizedGround(g, side, delta) {
  const [nx, ny] = groundTiles(g), axis = side[0] === 'x' ? 0 : 1, n = axis ? ny : nx;
  const step = Math.max(1 - n, Math.min(GROUND.maxTiles - n, Math.round(delta / TILE)));
  const shift = [0, 0];
  if (side[1] === '0') shift[axis] = -step * TILE;
  return { ground: { ...g, [`${side[0]}1`]: (n + step) * TILE }, shift };
}
/** The shape with its height (a block's top, a ramp's high edge) moved by `delta`, in steps of GROUND.step, kept to
 *  GROUND.minHeight..maxHeight; a patch is left as it is. */
export function raisedGround(g, delta) {
  if (g.shape === 'patch') return g;
  return { ...g, height: Math.max(GROUND.minHeight, Math.min(GROUND.maxHeight, round(g.height + delta, GROUND.step))) };
}
/** Another rock in the same footprint and height: the next seed. */
export const anotherRock = g => ({ ...g, seed: ((g.seed ?? 0) + 1) % ROCK_SEEDS });
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
  return { ground: { ...g, x1: nw, y1: nh }, location: at.map(tidy), rotation: turned };
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
